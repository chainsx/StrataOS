#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <time.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

#define LIMIT 65536

static int write_all(int fd, const void *data, size_t len) {
    const unsigned char *p = data;
    while (len) {
        ssize_t n = write(fd, p, len);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return -1;
        p += n;
        len -= (size_t)n;
    }
    return 0;
}

static int session_valid(const char *directory, const char *token) {
    if (strlen(token) != 64) return 0;
    for (const unsigned char *p = (const unsigned char *)token; *p; ++p)
        if (!((*p >= '0' && *p <= '9') || (*p >= 'a' && *p <= 'f') || (*p >= 'A' && *p <= 'F'))) return 0;
    char path[512], line[256], *end;
    if (snprintf(path, sizeof(path), "%s/%s", directory, token) >= (int)sizeof(path)) return 0;
    FILE *file = fopen(path, "r");
    if (!file || !fgets(line, sizeof(line), file)) { if (file) fclose(file); return 0; }
    fclose(file);
    errno = 0;
    unsigned long long expires = strtoull(line, &end, 10);
    return !errno && end != line && (*end == '\t' || *end == ' ') && expires > (unsigned long long)time(NULL);
}

static int cookie_authorized(char *request, const char *session_dir) {
    char supplied[129] = "";
    for (char *line = request; line && *line;) {
        char *next = strstr(line, "\r\n");
        if (next) *next = 0;
        if (!strncasecmp(line, "Cookie:", 7)) {
            char *item = line + 7;
            while (*item) {
                while (*item == ' ' || *item == ';') ++item;
                if (!strncmp(item, "strata_terminal=", 16)) {
                    item += 16;
                    size_t length = strcspn(item, "; \t\r\n");
                    if (length < sizeof(supplied)) {
                        memcpy(supplied, item, length);
                        supplied[length] = 0;
                    }
                    break;
                }
                item += strcspn(item, ";");
            }
        }
        if (next) { *next = '\r'; line = next + 2; } else break;
    }
    return session_valid(session_dir, supplied);
}

static int connect_backend(uint16_t port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address = {
        .sin_family = AF_INET, .sin_port = htons(port),
        .sin_addr = { .s_addr = htonl(INADDR_LOOPBACK) },
    };
    if (fd < 0 || connect(fd, (void *)&address, sizeof(address)) < 0) {
        if (fd >= 0) close(fd);
        return -1;
    }
    return fd;
}

static int relay(int client, int backend) {
    unsigned char buffer[LIMIT];
    for (;;) {
        struct pollfd descriptors[2] = {{client, POLLIN, 0}, {backend, POLLIN, 0}};
        if (poll(descriptors, 2, -1) < 0) { if (errno == EINTR) continue; return -1; }
        for (int index = 0; index < 2; ++index) {
            if (!(descriptors[index].revents & (POLLIN | POLLHUP | POLLERR))) continue;
            int source = index ? backend : client, destination = index ? client : backend;
            ssize_t count = read(source, buffer, sizeof(buffer));
            if (count <= 0) return 0;
            if (write_all(destination, buffer, (size_t)count) < 0) return -1;
        }
    }
}

static void serve(int client, uint16_t backend_port, const char *session_dir) {
    char request[LIMIT + 1];
    size_t used = 0;
    while (used < LIMIT) {
        ssize_t count = read(client, request + used, LIMIT - used);
        if (count <= 0) return;
        used += (size_t)count;
        request[used] = 0;
        if (strstr(request, "\r\n\r\n")) break;
    }
    if (!strstr(request, "\r\n\r\n") || !cookie_authorized(request, session_dir)) {
        const char denied[] = "HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\nCache-Control: no-store\r\nConnection: close\r\n\r\n";
        write_all(client, denied, sizeof(denied) - 1);
        return;
    }
    char *end = strstr(request, "\r\n\r\n");
    const char trusted[] = "\r\nX-Strata-Authenticated: yes";
    size_t tail = used - (size_t)(end - request);
    if (used + sizeof(trusted) >= sizeof(request)) return;
    memmove(end + sizeof(trusted) - 1, end, tail);
    memcpy(end, trusted, sizeof(trusted) - 1);
    used += sizeof(trusted) - 1;
    int backend = connect_backend(backend_port);
    if (backend < 0) return;
    if (write_all(backend, request, used) == 0) relay(client, backend);
    close(backend);
}

int main(int argc, char **argv) {
    int listen_port = 7681, backend_port = 7682, option;
    const char *session_dir = "/run/strata-webui/auth-sessions";
    const char *listen_address = NULL;
    while ((option = getopt(argc, argv, "l:b:t:i:")) != -1) {
        if (option == 'l') listen_port = atoi(optarg);
        else if (option == 'b') backend_port = atoi(optarg);
        else if (option == 't') session_dir = optarg;
        else if (option == 'i') listen_address = optarg;
        else return 2;
    }
    signal(SIGCHLD, SIG_IGN);
    signal(SIGPIPE, SIG_IGN);
    if (listen_address) {
        int listener = socket(AF_INET, SOCK_STREAM, 0), one = 1;
        if (listener >= 0) setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
        struct sockaddr_in address = {.sin_family = AF_INET, .sin_port = htons((uint16_t)listen_port)};
        if (listener < 0 || inet_pton(AF_INET, listen_address, &address.sin_addr) != 1 ||
            bind(listener, (void *)&address, sizeof(address)) < 0 || listen(listener, 32) < 0) {
            perror("strata-authproxy");
            if (listener >= 0) close(listener);
            return 1;
        }
        for (;;) {
            int client = accept(listener, NULL, NULL);
            if (client < 0) { if (errno == EINTR) continue; return 1; }
            pid_t child = fork();
            if (child == 0) { close(listener); serve(client, (uint16_t)backend_port, session_dir); close(client); _exit(0); }
            close(client);
        }
    }
    int listener = socket(AF_INET6, SOCK_STREAM, 0), one = 1, off = 0;
    setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
    setsockopt(listener, IPPROTO_IPV6, IPV6_V6ONLY, &off, sizeof(off));
    struct sockaddr_in6 address = {
        .sin6_family = AF_INET6, .sin6_port = htons((uint16_t)listen_port),
        .sin6_addr = IN6ADDR_ANY_INIT,
    };
    if (listener < 0 || bind(listener, (void *)&address, sizeof(address)) < 0 || listen(listener, 32) < 0) {
        perror("strata-authproxy");
        return 1;
    }
    for (;;) {
        int client = accept(listener, NULL, NULL);
        if (client < 0) { if (errno == EINTR) continue; return 1; }
        pid_t child = fork();
        if (child == 0) { close(listener); serve(client, (uint16_t)backend_port, session_dir); close(client); _exit(0); }
        close(client);
    }
}
