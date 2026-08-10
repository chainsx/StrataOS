#!/bin/sh
set -eu

phase=${STRATA_PHASE:?usage: STRATA_PHASE must be build|test|install}
: "${STRATA_BUILD_DIR:?}"
: "${STRATA_DESTDIR:?}"

build_binary() {
    name=$1
    source=$2
    shift 2
    "$CC" $CFLAGS "$source" -o "$STRATA_BUILD_DIR/$name" $LDFLAGS "$@"
}

case "$phase" in
    build)
        mkdir -p "$STRATA_BUILD_DIR"
        build_binary strata-wsproxy src/wsproxy.c -lcrypto
        build_binary strata-authproxy src/authproxy.c
        build_binary strata-authenticate src/authenticate.c
        build_binary strata-tlsproxy src/tlsproxy.c -lssl -lcrypto
        ;;
    test)
        for binary in strata-wsproxy strata-authproxy strata-authenticate strata-tlsproxy; do
            test -x "$STRATA_BUILD_DIR/$binary"
        done
        for asset in index.html app.js style.css viewer.html viewer.js webapp-controls.css; do
            test -f "assets/$asset"
        done
        ;;
    install)
        mkdir -p "$STRATA_DESTDIR/usr/sbin"
        mkdir -p "$STRATA_DESTDIR/usr/share/strata-webui/www"
        install -m 755 "$STRATA_BUILD_DIR/strata-wsproxy" "$STRATA_DESTDIR/usr/sbin/"
        install -m 755 "$STRATA_BUILD_DIR/strata-authproxy" "$STRATA_DESTDIR/usr/sbin/"
        install -m 755 "$STRATA_BUILD_DIR/strata-authenticate" "$STRATA_DESTDIR/usr/sbin/"
        install -m 755 "$STRATA_BUILD_DIR/strata-tlsproxy" "$STRATA_DESTDIR/usr/sbin/"
        for asset in index.html app.js style.css viewer.html viewer.js webapp-controls.css; do
            install -m 644 "assets/$asset" "$STRATA_DESTDIR/usr/share/strata-webui/www/"
        done
        ;;
    *)
        echo "usage: STRATA_PHASE={build|test|install} $0" >&2
        exit 1
        ;;
esac
