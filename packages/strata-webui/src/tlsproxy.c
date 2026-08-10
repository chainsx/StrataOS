#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <openssl/err.h>
#include <openssl/ssl.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <unistd.h>

#define BUFFER_SIZE 65536

static int write_all(int descriptor, const void *data, size_t length) {
    const unsigned char *position = data;
    while (length) {
        ssize_t written = write(descriptor, position, length);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) return -1;
        position += written;
        length -= (size_t)written;
    }
    return 0;
}

static int ssl_write_all(SSL *connection, const void *data, size_t length) {
    const unsigned char *position = data;
    while (length) {
        int chunk = length > INT32_MAX ? INT32_MAX : (int)length;
        int written = SSL_write(connection, position, chunk);
        if (written > 0) {
            position += written;
            length -= (size_t)written;
            continue;
        }
        int error = SSL_get_error(connection, written);
        if (error != SSL_ERROR_WANT_READ && error != SSL_ERROR_WANT_WRITE) return -1;
        struct pollfd wait = {
            .fd = SSL_get_fd(connection),
            .events = error == SSL_ERROR_WANT_READ ? POLLIN : POLLOUT,
        };
        if (poll(&wait, 1, -1) < 0 && errno != EINTR) return -1;
    }
    return 0;
}

static int connect_backend(uint16_t port) {
    int descriptor = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in address = {
        .sin_family = AF_INET,
        .sin_port = htons(port),
        .sin_addr = {.s_addr = htonl(INADDR_LOOPBACK)},
    };
    if (descriptor < 0 || connect(descriptor, (void *)&address, sizeof(address)) < 0) {
        if (descriptor >= 0) close(descriptor);
        return -1;
    }
    return descriptor;
}

static int relay(SSL *client, int backend) {
    unsigned char buffer[BUFFER_SIZE];
    int client_fd = SSL_get_fd(client);
    for (;;) {
        struct pollfd descriptors[2] = {
            {client_fd, POLLIN, 0}, {backend, POLLIN, 0},
        };
        int ready = SSL_pending(client) ? 1 : poll(descriptors, 2, -1);
        if (ready < 0) {
            if (errno == EINTR) continue;
            return -1;
        }
        if (SSL_pending(client) || (descriptors[0].revents & (POLLIN | POLLHUP | POLLERR))) {
            int count = SSL_read(client, buffer, sizeof(buffer));
            if (count <= 0) {
                int error = SSL_get_error(client, count);
                if (error == SSL_ERROR_WANT_READ || error == SSL_ERROR_WANT_WRITE) continue;
                return error == SSL_ERROR_ZERO_RETURN ? 0 : -1;
            }
            if (write_all(backend, buffer, (size_t)count) < 0) return -1;
        }
        if (descriptors[1].revents & (POLLIN | POLLHUP | POLLERR)) {
            ssize_t count = read(backend, buffer, sizeof(buffer));
            if (count <= 0) return 0;
            if (ssl_write_all(client, buffer, (size_t)count) < 0) return -1;
        }
    }
}

static void serve(SSL_CTX *context, int descriptor, uint16_t backend_port) {
    SSL *connection = SSL_new(context);
    if (!connection) return;
    SSL_set_fd(connection, descriptor);
    if (SSL_accept(connection) == 1) {
        int backend = connect_backend(backend_port);
        if (backend >= 0) {
            relay(connection, backend);
            close(backend);
        }
        SSL_shutdown(connection);
    }
    SSL_free(connection);
}

int main(int argc, char **argv) {
    int listen_port = 9090, backend_port = 9091, option;
    const char *certificate = NULL, *private_key = NULL;
    while ((option = getopt(argc, argv, "l:b:c:k:")) != -1) {
        if (option == 'l') listen_port = atoi(optarg);
        else if (option == 'b') backend_port = atoi(optarg);
        else if (option == 'c') certificate = optarg;
        else if (option == 'k') private_key = optarg;
        else return 2;
    }
    if (listen_port < 1 || listen_port > 65535 || backend_port < 1 || backend_port > 65535 ||
        !certificate || !private_key) {
        fprintf(stderr, "usage: strata-tlsproxy -l PORT -b LOOPBACK_PORT -c CERTIFICATE -k PRIVATE_KEY\n");
        return 2;
    }

    SSL_CTX *context = SSL_CTX_new(TLS_server_method());
    if (!context) return 1;
    SSL_CTX_set_min_proto_version(context, TLS1_2_VERSION);
    SSL_CTX_set_options(context, SSL_OP_NO_COMPRESSION);
    if (SSL_CTX_use_certificate_chain_file(context, certificate) != 1 ||
        SSL_CTX_use_PrivateKey_file(context, private_key, SSL_FILETYPE_PEM) != 1 ||
        SSL_CTX_check_private_key(context) != 1) {
        ERR_print_errors_fp(stderr);
        SSL_CTX_free(context);
        return 1;
    }

    signal(SIGCHLD, SIG_IGN);
    signal(SIGPIPE, SIG_IGN);
    int listener = socket(AF_INET6, SOCK_STREAM, 0), one = 1, off = 0;
    if (listener >= 0) {
        setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &one, sizeof(one));
        setsockopt(listener, IPPROTO_IPV6, IPV6_V6ONLY, &off, sizeof(off));
    }
    struct sockaddr_in6 address = {
        .sin6_family = AF_INET6,
        .sin6_port = htons((uint16_t)listen_port),
        .sin6_addr = IN6ADDR_ANY_INIT,
    };
    if (listener < 0 || bind(listener, (void *)&address, sizeof(address)) < 0 || listen(listener, 32) < 0) {
        perror("strata-tlsproxy");
        if (listener >= 0) close(listener);
        SSL_CTX_free(context);
        return 1;
    }
    for (;;) {
        int client = accept(listener, NULL, NULL);
        if (client < 0) {
            if (errno == EINTR) continue;
            break;
        }
        pid_t child = fork();
        if (child == 0) {
            close(listener);
            serve(context, client, (uint16_t)backend_port);
            close(client);
            _exit(0);
        }
        close(client);
    }
    close(listener);
    SSL_CTX_free(context);
    return 1;
}
