#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

validate_disk_config() {
    awk -F '=' '
        function bad(message) {
            print "disk.conf: " message > "/dev/stderr"
            failed = 1
        }
        /^[[:space:]]*(#|$)/ { next }
        index($0, "=") == 0 { bad("invalid line " NR); next }
        {
            key = substr($0, 1, index($0, "=") - 1)
            value = substr($0, index($0, "=") + 1)
            if (seen[key]++) bad("duplicate key " key)
            values[key] = value
        }
        END {
            if (values["format"] != "1") bad("format must be 1")
            if (values["table"] != "gpt") bad("table must be gpt")
            if (values["disk.guid"] !~ /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/)
                bad("disk.guid is invalid")
            if (values["partition.esp.guid"] !~ /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/ ||
                values["partition.data.guid"] !~ /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/)
                bad("partition GUID is invalid")
            if (values["disk.guid"] == values["partition.esp.guid"] ||
                values["disk.guid"] == values["partition.data.guid"] ||
                values["partition.esp.guid"] == values["partition.data.guid"])
                bad("disk and partition GUIDs must be unique")
            if (values["partition.esp.type_guid"] != "c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
                bad("ESP type GUID is invalid")
            if (values["partition.data.type_guid"] != "0fc63daf-8483-4772-8e79-3d69d8477de4")
                bad("Linux data type GUID is invalid")
            if (values["sector_size"] !~ /^(512|4096)$/) bad("sector_size must be 512 or 4096")
            if (values["alignment_mib"] !~ /^[1-9][0-9]*$/) bad("alignment_mib must be positive")
            if (values["image.size_mib"] !~ /^[0-9]+$/) bad("image.size_mib must be numeric")
            if (values["partition.esp.number"] != "1") bad("ESP must be partition 1")
            if (values["partition.data.number"] != "2") bad("data must be partition 2")
            if (values["partition.esp.size_mib"] !~ /^[0-9]+$/ ||
                values["partition.esp.size_mib"] + 0 < 64)
                bad("ESP must be at least 64 MiB")
            if (values["partition.esp.filesystem"] != "fat32") bad("ESP filesystem must be fat32")
            if (values["partition.data.filesystem"] != "ext4")
                bad("data filesystem must be ext4")
            if (values["partition.data.size_mib"] != "remaining" &&
                values["partition.data.size_mib"] !~ /^[0-9]+$/)
                bad("data size must be remaining or numeric")
            if (values["partition.data.min_size_mib"] !~ /^[0-9]+$/ ||
                values["partition.data.min_size_mib"] + 0 < 1024)
                bad("data minimum must be at least 1024 MiB")
            if (values["partition.data.reserved_percent"] !~ /^[0-9]+$/ ||
                values["partition.data.reserved_percent"] + 0 > 10)
                bad("reserved percent must be between 0 and 10")
            if (values["partition.data.usage_type"] != "largefile4")
                bad("partition.data.usage_type must be largefile4")
            if (values["partition.data.auto_grow"] !~ /^(yes|no)$/)
                bad("partition.data.auto_grow must be yes or no")
            if (values["partition.esp.label"] !~ /^[A-Z0-9_]{1,11}$/)
                bad("invalid FAT label")
            if (values["partition.data.label"] !~ /^[A-Za-z0-9._-]{1,16}$/)
                bad("invalid data label")
            if (values["partition.esp.label"] == values["partition.data.label"])
                bad("partition labels must differ")
            if (values["partition.esp.mount"] !~ /^\/[A-Za-z0-9._\/-]+$/ ||
                values["partition.data.mount"] !~ /^\/[A-Za-z0-9._\/-]+$/)
                bad("partition mount points must be absolute safe paths")
            minimum = (values["partition.esp.size_mib"] + 0) + (values["partition.data.min_size_mib"] + 0) + ((values["alignment_mib"] + 0) * 2)
            if (values["image.size_mib"] + 0 < minimum)
                bad("image is too small for configured partitions")
            exit failed
        }
    ' "${PROJECT_DIR}/configs/image/disk.conf" || fail "invalid disk configuration"
}

validate_storage_config() {
    awk -F '=' '
        function bad(message) {
            print "storage.conf: " message > "/dev/stderr"
            failed = 1
        }
        /^[[:space:]]*(#|$)/ { next }
        index($0, "=") == 0 { bad("invalid line " NR); next }
        {
            key = substr($0, 1, index($0, "=") - 1)
            value = substr($0, index($0, "=") + 1)
            if (seen[key]++) bad("duplicate key " key)
            values[key] = value
        }
        END {
            if (values["format"] != "2") bad("format must be 2")
            for (key in values) {
                if (key !~ /^backend\.[a-z][a-z0-9-]*\.type$/) continue
                id = key
                sub(/^backend\./, "", id)
                sub(/\.type$/, "", id)
                type = values[key]
                source = values["backend." id ".source"]
                path = values["backend." id ".path"]
                filesystem = values["backend." id ".filesystem"]
                if (type != "filesystem")
                    bad("backend " id " must use the implemented filesystem type")
                if (source !~ /^(LABEL|PARTUUID)=[A-Za-z0-9._-]+$/)
                    bad("backend " id " must use LABEL= or PARTUUID=")
                if (filesystem != "ext4")
                    bad("backend " id " must use ext4")
                if (path !~ /^\/[A-Za-z0-9._\/-]+$/ || path ~ /(^|\/)\.\.($|\/)/)
                    bad("backend " id " has an unsafe path")
            }

            component_backend = values["components.backend"]
            if (component_backend != "data")
                bad("components.backend must be data in format 2")
            if (values["components.path"] != "components")
                bad("components.path must be components in format 2")
            if (values["components.protection"] != "sha256-slot")
                bad("components.protection must be sha256-slot")

            backend = values["volume.default.backend"]
            mirror = values["volume.default.mirror_backend"]
            if (values["backend." backend ".type"] != "filesystem")
                bad("default volume backend is invalid")
            if (values["backend." mirror ".type"] != "filesystem")
                bad("default mirror backend is invalid")
            if (values["volume.default.redundancy"] !~ /^(none|mirror|integrity-mirror)$/)
                bad("invalid default redundancy")
            if (values["volume.default.integrity"] != "crc32c")
                bad("volume.default.integrity must be crc32c")
            if (values["volume.default.preallocate"] !~ /^(yes|no)$/)
                bad("preallocate must be yes or no")
            if (values["volume.default.growth"] != "boot-only")
                bad("default growth must be boot-only")
            if (values["volume.default.fsck"] !~ /^(preen|readonly|manual)$/)
                bad("invalid fsck policy")
            exit failed
        }
    ' "${PROJECT_DIR}/configs/runtime/storage.conf" || fail "invalid storage configuration"
}

validate_logging_config() {
    awk -F '=' '
        function bad(message) {
            print "logging.conf: " message > "/dev/stderr"
            failed = 1
        }
        /^[[:space:]]*(#|$)/ { next }
        NF != 2 { bad("invalid line " NR); next }
        {
            key = $1
            value = $2
            if (seen[key]++) bad("duplicate key " key)
            values[key] = value
        }
        END {
            if (values["mode"] !~ /^(persistent|volatile)$/)
                bad("mode must be persistent or volatile")
            if (values["early_boot_log"] !~ /^(yes|no)$/)
                bad("early_boot_log must be yes or no")
            if (values["kernel_log"] !~ /^(yes|no)$/)
                bad("kernel_log must be yes or no")
            if (values["operation_log"] !~ /^(yes|no)$/)
                bad("operation_log must be yes or no")
            if (values["max_file_kib"] !~ /^[0-9]+$/ ||
                values["max_file_kib"] < 64)
                bad("max_file_kib must be at least 64")
            if (values["rotate_count"] !~ /^[0-9]+$/ ||
                values["rotate_count"] < 1)
                bad("rotate_count must be a positive integer")
            if (values["boot_log_count"] !~ /^[0-9]+$/ ||
                values["boot_log_count"] < 1)
                bad("boot_log_count must be a positive integer")
            exit failed
        }
    ' "${PROJECT_DIR}/configs/runtime/logging.conf" \
        || fail "invalid logging configuration"
}

for script in "${PROJECT_DIR}"/scripts/*.sh "${PROJECT_DIR}"/initramfs/init; do
    bash -n "${script}" || fail "syntax check failed: ${script}"
done

component_scripts="$(find "${PROJECT_DIR}/components" -type f \
    \( -path '*/rootfs/etc/init.d/*' -o -path '*/rootfs/usr/local/sbin/*' -o -path '*/rootfs/usr/libexec/*' \) \
    -print)"
while IFS= read -r script; do
    [[ -z "${script}" ]] && continue
    bash -n "${script}" || fail "syntax check failed: ${script}"
done <<< "${component_scripts}"

for arch in x86_64 arm64; do
    config="${PROJECT_DIR}/configs/kernel/${arch}/kernel.config"
    [[ -s "${config}" ]] || fail "missing ${config}"

    duplicates="$(awk '
        match($0, /CONFIG_[A-Za-z0-9_]+/) {
            symbol = substr($0, RSTART, RLENGTH)
            count[symbol]++
        }
        END { for (symbol in count) if (count[symbol] > 1) print symbol }
    ' "${config}")"
    [[ -z "${duplicates}" ]] \
        || fail "duplicate symbols in ${config}: ${duplicates}"
done

while read -r symbol expected; do
    [[ -z "${symbol}" || "${symbol}" == \#* ]] && continue
    for config in "${PROJECT_DIR}"/configs/kernel/*/kernel.config; do
        grep -qx "${symbol}=${expected}" "${config}" \
            || fail "${symbol}=${expected} missing from ${config}"
    done
done < "${PROJECT_DIR}/configs/kernel/required-symbols.list"

validate_disk_config
validate_storage_config
validate_logging_config
"${PROJECT_DIR}/scripts/validate-components.sh"

data_label="$(awk -F= '$1 == "partition.data.label" { print $2; exit }' \
    "${PROJECT_DIR}/configs/image/disk.conf")"
storage_source="$(awk '$0 ~ /^backend\.data\.source=/ { print substr($0, index($0, "=") + 1); exit }' \
    "${PROJECT_DIR}/configs/runtime/storage.conf")"
[[ "${storage_source}" == "LABEL=${data_label}" ]] \
    || fail "disk data label and storage backend disagree"
data_filesystem="$(awk -F= '$1 == "partition.data.filesystem" { print $2; exit }' \
    "${PROJECT_DIR}/configs/image/disk.conf")"
storage_filesystem="$(awk -F= '$1 == "backend.data.filesystem" { print $2; exit }' \
    "${PROJECT_DIR}/configs/runtime/storage.conf")"
[[ "${storage_filesystem}" == "${data_filesystem}" ]] \
    || fail "disk data filesystem and storage backend disagree"

config_value() {
    local key="$1" file="$2"
    awk -v wanted="${key}" '
        $0 ~ ("^" wanted "=") {
            print substr($0, index($0, "=") + 1)
            exit
        }
    ' "${file}"
}

image_mib="$(config_value 'image.size_mib' "${PROJECT_DIR}/configs/image/disk.conf")"
esp_mib="$(config_value 'partition.esp.size_mib' "${PROJECT_DIR}/configs/image/disk.conf")"
alignment_mib="$(config_value 'alignment_mib' "${PROJECT_DIR}/configs/image/disk.conf")"
data_mib="$(config_value 'partition.data.size_mib' "${PROJECT_DIR}/configs/image/disk.conf")"
reserved_percent="$(config_value 'partition.data.reserved_percent' "${PROJECT_DIR}/configs/image/disk.conf")"
if [[ "${data_mib}" == remaining ]]; then
    data_mib=$((image_mib - esp_mib - alignment_mib * 2))
fi
usable_data_mib=$((data_mib * (100 - reserved_percent) / 100))
component_volume_mib="$(awk -F= '
    $1 ~ /^storage\.[0-9]+\.initial_size_mib$/ { total += $2 }
    END { print total + 0 }
' "${PROJECT_DIR}"/components/*/component.conf)"
# Component volume files are sparse by default and are created only on first
# activation. The release image therefore needs room for components and volume
# metadata, while deployment media and QEMU should provide the declared usable
# capacity before first boot.
preallocate="$(config_value 'volume.default.preallocate' "${PROJECT_DIR}/configs/runtime/storage.conf")"
auto_grow="$(config_value 'partition.data.auto_grow' "${PROJECT_DIR}/configs/image/disk.conf")"
if [[ "${preallocate}" == yes ]]; then
    required_data_mib=$((component_volume_mib + 1024))
    (( usable_data_mib >= required_data_mib )) \
        || fail "preallocated component volumes need at least ${required_data_mib} usable MiB"
elif [[ "${auto_grow}" != yes ]]; then
    fail "sparse release image requires partition.data.auto_grow=yes"
fi

printf 'StrataOS configuration validation passed.\n'
