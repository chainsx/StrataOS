#define _GNU_SOURCE
#include <crypt.h>
#include <errno.h>
#include <grp.h>
#include <pwd.h>
#include <shadow.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define PASSWORD_LIMIT 4096

static int constant_equal(const char *left, const char *right) {
    size_t a = strlen(left), b = strlen(right), length = a > b ? a : b;
    unsigned difference = (unsigned)(a ^ b);
    for (size_t i = 0; i < length; ++i) {
        unsigned char x = i < a ? (unsigned char)left[i] : 0;
        unsigned char y = i < b ? (unsigned char)right[i] : 0;
        difference |= x ^ y;
    }
    return difference == 0;
}

static int valid_username(const char *name) {
    size_t length = strlen(name);
    if (!length || length > 64 || name[0] == '-') return 0;
    for (const unsigned char *p = (const unsigned char *)name; *p; ++p)
        if (!( (*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
               (*p >= '0' && *p <= '9') || *p == '_' || *p == '-' || *p == '.')) return 0;
    return 1;
}

static int administrator(const struct passwd *account) {
    if (account->pw_uid == 0) return 1;
    struct group *wheel = getgrnam("wheel");
    if (!wheel) return 0;
    if (account->pw_gid == wheel->gr_gid) return 1;
    for (char **member = wheel->gr_mem; member && *member; ++member)
        if (strcmp(*member, account->pw_name) == 0) return 1;
    return 0;
}

int main(int argc, char **argv) {
    static const char dummy_hash[] =
        "$6$strata-webui$WGIziRj/9xRqP4M2kOqW.WlEGLJQjcaRvWjNTu6xzsTlcWwSrfhB9dWZVtM1uGyZ0saE2f9AHe6cXWpnAJt7t0";
    char password[PASSWORD_LIMIT + 1];
    if (argc != 2 || !valid_username(argv[1])) return 1;
    size_t used = fread(password, 1, PASSWORD_LIMIT + 1, stdin);
    if (used == 0 || used > PASSWORD_LIMIT || ferror(stdin)) return 1;
    password[used] = 0;

    errno = 0;
    struct passwd *account = getpwnam(argv[1]);
    struct spwd *shadow = account ? getspnam(argv[1]) : NULL;
    const char *stored = shadow && shadow->sp_pwdp ? shadow->sp_pwdp : dummy_hash;
    int usable = account && shadow && administrator(account) && stored[0] && stored[0] != '!' && stored[0] != '*';
    long today = (long)(time(NULL) / 86400);
    if (shadow && shadow->sp_expire >= 0 && today > shadow->sp_expire) usable = 0;
    if (shadow && shadow->sp_max >= 0 && shadow->sp_lstchg >= 0 &&
        today > shadow->sp_lstchg + shadow->sp_max) usable = 0;

    struct crypt_data data = {0};
    char *calculated = crypt_r(password, stored, &data);
    memset(password, 0, sizeof(password));
    if (!calculated || !usable || !constant_equal(calculated, stored)) return 1;
    printf("%s\n", account->pw_name);
    return 0;
}
