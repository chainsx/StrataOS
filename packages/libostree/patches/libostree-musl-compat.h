#ifndef STRATAOS_LIBOSTREE_MUSL_COMPAT_H
#define STRATAOS_LIBOSTREE_MUSL_COMPAT_H
#ifndef TEMP_FAILURE_RETRY
#define TEMP_FAILURE_RETRY(expression)                                      \
  (__extension__ ({ long int __result;                                      \
    do __result = (long int) (expression);                                  \
    while (__result == -1L && errno == EINTR);                              \
    __result; }))
#endif
#endif
