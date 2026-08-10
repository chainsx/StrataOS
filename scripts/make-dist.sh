#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT_DIR="$(dirname "${PROJECT_DIR}")"
VERSION="$(awk -F= '$1 == "STRATA_VERSION" {print $2; exit}' "${PROJECT_DIR}/defconfigs/x86_64_defconfig")"
EPOCH="$(awk -F= '$1 == "STRATA_SOURCE_DATE_EPOCH" {print $2; exit}' "${PROJECT_DIR}/defconfigs/x86_64_defconfig")"
ARCHIVE="${PARENT_DIR}/strataos-project-${VERSION}.tar.gz"

find "${PROJECT_DIR}" -type d -name __pycache__ -prune -exec rm -rf {} +

tar --create --gzip --file "${ARCHIVE}" \
    --sort=name \
    --mtime="@${EPOCH}" \
    --owner=0 --group=0 --numeric-owner \
    --pax-option=delete=atime,delete=ctime \
    --exclude='strataos/.git' \
    --exclude='strataos/.config' \
    --exclude='strataos/build' \
    --exclude='strataos/dl' \
    --exclude='strataos/output' \
    --exclude='*/__pycache__' \
    --exclude='*/__pycache__/*' \
    --exclude='strataos/*.tar.gz' \
    --exclude='strataos/*.zip' \
    -C "${PARENT_DIR}" strataos

(cd "${PARENT_DIR}" && sha256sum "$(basename "${ARCHIVE}")" \
    > "$(basename "${ARCHIVE}").sha256")
printf 'Created %s\n' "${ARCHIVE}"
