#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${PROJECT_DIR}/configs/image/disk.conf"

get_value() {
    local key="$1"
    awk -v wanted="${key}" '
        index($0, "=") && substr($0, 1, index($0, "=") - 1) == wanted {
            print substr($0, index($0, "=") + 1)
            exit
        }
    ' "${CONFIG}"
}

align_up() {
    local value="$1" alignment="$2"
    printf '%d\n' "$(( (value + alignment - 1) / alignment * alignment ))"
}

sector_size="$(get_value sector_size)"
alignment_mib="$(get_value alignment_mib)"
image_mib="$(get_value image.size_mib)"
esp_mib="$(get_value partition.esp.size_mib)"
data_mib="$(get_value partition.data.size_mib)"
data_min_mib="$(get_value partition.data.min_size_mib)"

sectors_per_mib=$((1024 * 1024 / sector_size))
alignment_sectors=$((alignment_mib * sectors_per_mib))
disk_sectors=$((image_mib * sectors_per_mib))

esp_start="${alignment_sectors}"
esp_sectors=$((esp_mib * sectors_per_mib))
esp_end=$((esp_start + esp_sectors - 1))
data_start="$(align_up "$((esp_end + 1))" "${alignment_sectors}")"

if [[ "${data_mib}" == remaining ]]; then
    # Leave one alignment unit for the backup GPT and future boot metadata.
    data_end=$((disk_sectors - alignment_sectors - 1))
else
    data_end=$((data_start + data_mib * sectors_per_mib - 1))
fi

(( data_end < disk_sectors - 33 )) || {
    printf 'ERROR: configured data partition overlaps backup GPT\n' >&2
    exit 1
}
data_sectors=$((data_end - data_start + 1))
actual_data_mib=$((data_sectors / sectors_per_mib))
(( actual_data_mib >= data_min_mib )) || {
    printf 'ERROR: data partition is %d MiB, minimum is %d MiB\n' \
        "${actual_data_mib}" "${data_min_mib}" >&2
    exit 1
}

printf 'disk.table=gpt\n'
printf 'disk.guid=%s\n' "$(get_value disk.guid)"
printf 'disk.size_mib=%s\n' "${image_mib}"
printf 'disk.sector_size=%s\n' "${sector_size}"
printf 'partition.esp.start_sector=%s\n' "${esp_start}"
printf 'partition.esp.guid=%s\n' "$(get_value partition.esp.guid)"
printf 'partition.esp.type_guid=%s\n' "$(get_value partition.esp.type_guid)"
printf 'partition.esp.end_sector=%s\n' "${esp_end}"
printf 'partition.esp.size_mib=%s\n' "${esp_mib}"
printf 'partition.esp.filesystem=%s\n' "$(get_value partition.esp.filesystem)"
printf 'partition.esp.label=%s\n' "$(get_value partition.esp.label)"
printf 'partition.data.start_sector=%s\n' "${data_start}"
printf 'partition.data.guid=%s\n' "$(get_value partition.data.guid)"
printf 'partition.data.type_guid=%s\n' "$(get_value partition.data.type_guid)"
printf 'partition.data.end_sector=%s\n' "${data_end}"
printf 'partition.data.size_mib=%s\n' "${actual_data_mib}"
printf 'partition.data.filesystem=%s\n' "$(get_value partition.data.filesystem)"
printf 'partition.data.label=%s\n' "$(get_value partition.data.label)"
