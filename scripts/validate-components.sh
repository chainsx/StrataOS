#!/usr/bin/env bash
set -Eeuo pipefail
shopt -s nullglob

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPONENTS_DIR="${PROJECT_DIR}/components"

fail() {
    printf 'ERROR: %s\n' "$*" >&2
    exit 1
}

declare -A component_names=() component_requires=() visit_state=() \
    rootfs_paths=() volume_images=() volume_mounts=()
component_files=("${COMPONENTS_DIR}"/*/component.conf)
[[ "${#component_files[@]}" -gt 0 ]] || fail "no component manifests found"

for manifest in "${component_files[@]}"; do
    directory="$(basename "$(dirname "${manifest}")")"
    packages="$(dirname "${manifest}")/packages.list"
    [[ -s "${packages}" ]] || fail "missing package list for ${directory}"

    awk -F '=' -v expected_name="${directory}" '
        function bad(message) {
            print FILENAME ": " message > "/dev/stderr"
            failed = 1
        }
        function csv(value, allow_empty, item, count, parts) {
            if (value == "") return allow_empty
            count = split(value, parts, ",")
            for (item = 1; item <= count; item++)
                if (parts[item] !~ /^[a-z][a-z0-9-]*$/) return 0
            return 1
        }
        /^[[:space:]]*(#|$)/ { next }
        NF != 2 { bad("invalid line " NR); next }
        {
            key = $1
            value = $2
            if (seen[key]++) bad("duplicate key " key)
            values[key] = value
            if (key !~ /^(format|name|version|summary|type|architectures|priority|requires|after|services|storage.count)$/ &&
                key !~ /^storage\.[0-9]+\.(id|image|mount|format|initial_size_mib|growth|redundancy|lifecycle|schema|legacy_component)$/ &&
                key !~ /^storage\.[0-9]+\.bind\.count$/ &&
                key !~ /^storage\.[0-9]+\.bind\.[0-9]+\.(source|target|seed|when)$/ &&
                key !~ /^x\.[a-z0-9.-]+$/)
                bad("unknown key " key)
        }
        END {
            if (values["format"] != "1") bad("format must be 1")
            if (values["name"] != expected_name) bad("name must match directory")
            if (values["name"] !~ /^[a-z][a-z0-9-]*$/) bad("invalid name")
            if (values["version"] !~ /^[A-Za-z0-9][A-Za-z0-9._+-]*$/) bad("invalid version")
            if (values["summary"] == "") bad("summary is required")
            if (values["type"] !~ /^(base|feature|kernel|firmware)$/) bad("invalid type")
            if (values["architectures"] !~ /^(x86_64,arm64|arm64,x86_64|x86_64|arm64)$/)
                bad("unsupported architectures")
            if (values["priority"] !~ /^[0-9]+$/ || values["priority"] > 999)
                bad("priority must be between 0 and 999")
            if (!csv(values["requires"], 1)) bad("invalid requires list")
            if (!csv(values["after"], 1)) bad("invalid after list")
            if (!csv(values["services"], 1)) bad("invalid services list")
            if (values["storage.count"] !~ /^[0-9]+$/ || values["storage.count"] > 8)
                bad("storage.count must be between 0 and 8")

            count = values["storage.count"] + 0
            for (i = 0; i < count; i++) {
                prefix = "storage." i "."
                id = values[prefix "id"]
                image = values[prefix "image"]
                mount = values[prefix "mount"]
                if (id !~ /^[a-z][a-z0-9-]*$/) bad(prefix "id is invalid")
                if (image !~ /^[a-z][a-z0-9-]*\.ext4$/) bad(prefix "image is invalid")
                if (mount !~ /^\/[A-Za-z0-9._\/-]+$/ || mount ~ /(^|\/)\.\.($|\/)/)
                    bad(prefix "mount is unsafe")
                if (values[prefix "format"] != "ext4") bad(prefix "format must be ext4")
                if (values[prefix "initial_size_mib"] !~ /^[0-9]+$/ ||
                    values[prefix "initial_size_mib"] < 16)
                    bad(prefix "initial_size_mib must be at least 16")
                if (values[prefix "growth"] !~ /^(inherit|fixed|grow-only)$/)
                    bad(prefix "growth is invalid")
                if (values[prefix "redundancy"] !~ /^(inherit|none|mirror|integrity-mirror)$/)
                    bad(prefix "redundancy is invalid")
                if (values[prefix "lifecycle"] !~ /^(retain|snapshot|purge-on-remove)$/)
                    bad(prefix "lifecycle is invalid")
                if (values[prefix "schema"] !~ /^[1-9][0-9]*$/)
                    bad(prefix "schema must be positive")
                legacy = values[prefix "legacy_component"]
                if (legacy != "" && (legacy !~ /^[a-z][a-z0-9-]*$/ || legacy == values["name"]))
                    bad(prefix "legacy_component is invalid")
                bind_count = values[prefix "bind.count"]
                if (bind_count !~ /^[0-9]+$/ || bind_count + 0 > 16)
                    bad(prefix "bind.count must be between 0 and 16")
                for (binding = 0; binding < bind_count + 0; binding++) {
                    bind_prefix = prefix "bind." binding "."
                    source = values[bind_prefix "source"]
                    target = values[bind_prefix "target"]
                    if (source !~ /^[A-Za-z0-9._\/-]+$/ ||
                        source ~ /(^|\/)\.\.($|\/)/ || source ~ /^\//)
                        bad(bind_prefix "source is unsafe")
                    if (target !~ /^\/[A-Za-z0-9._\/-]+$/ ||
                        target ~ /(^|\/)\.\.($|\/)/)
                        bad(bind_prefix "target is unsafe")
                    if (values[bind_prefix "seed"] !~ /^(copy|empty|overlay)$/)
                        bad(bind_prefix "seed is invalid")
                    if (values[bind_prefix "when"] !~ /^(always|logging-persistent)$/)
                        bad(bind_prefix "when is invalid")
                }
            }
            exit failed
        }
    ' "${manifest}" || fail "invalid component manifest: ${manifest}"

    name="$(awk -F= '$1 == "name" { print $2; exit }' "${manifest}")"
    [[ -z "${component_names[${name}]:-}" ]] || fail "duplicate component ${name}"
    component_names["${name}"]=1
    component_requires["${name}"]="$(awk -F= '$1 == "requires" { print $2; exit }' "${manifest}")"

    awk '
        /^[[:space:]]*(#|$)/ { next }
        $0 !~ /^[a-z0-9][a-z0-9+._-]*$/ { exit 1 }
        seen[$0]++ { exit 1 }
    ' "${packages}" || fail "invalid package list: ${packages}"

    rootfs="$(dirname "${manifest}")/rootfs"
    if [[ -d "${rootfs}" ]]; then
        payloads="$(find "${rootfs}" \( -type f -o -type l \) -print)"
        while IFS= read -r payload; do
            [[ -z "${payload}" ]] && continue
            relative="${payload#${rootfs}/}"
            [[ -z "${rootfs_paths[${relative}]:-}" ]] \
                || fail "rootfs path ${relative} is supplied by both ${rootfs_paths[${relative}]} and ${name}"
            rootfs_paths["${relative}"]="${name}"
        done <<< "${payloads}"
    fi

    count="$(awk -F= '$1 == "storage.count" { print $2; exit }' "${manifest}")"
    for ((index = 0; index < count; index++)); do
        image="$(awk -F= -v key="storage.${index}.image" '$1 == key { print $2; exit }' "${manifest}")"
        mount="$(awk -F= -v key="storage.${index}.mount" '$1 == key { print $2; exit }' "${manifest}")"
        [[ -z "${volume_images[${image}]:-}" ]] \
            || fail "volume image ${image} is owned by both ${volume_images[${image}]} and ${name}"
        [[ -z "${volume_mounts[${mount}]:-}" ]] \
            || fail "mount ${mount} is owned by both ${volume_mounts[${mount}]} and ${name}"
        volume_images["${image}"]="${name}"
        volume_mounts["${mount}"]="${name}"
    done

    for hook in "$(dirname "${manifest}")"/hooks/*; do
        phase="$(basename "${hook}")"
        [[ -f "${hook}" && -x "${hook}" ]] || fail "hook must be an executable file: ${hook}"
        [[ "${phase}" =~ ^(install|pre-refresh|migrate|post-refresh|rollback|remove)$ ]] \
            || fail "unsupported hook phase: ${hook}"
        bash -n "${hook}" || fail "invalid hook syntax: ${hook}"
    done
done

for manifest in "${component_files[@]}"; do
    name="$(awk -F= '$1 == "name" { print $2; exit }' "${manifest}")"
    requires="$(awk -F= '$1 == "requires" { print $2; exit }' "${manifest}")"
    IFS=',' read -r -a dependencies <<< "${requires}"
    for dependency in "${dependencies[@]}"; do
        [[ -z "${dependency}" ]] && continue
        [[ -n "${component_names[${dependency}]:-}" ]] \
            || fail "component ${name} requires missing component ${dependency}"
        [[ "${dependency}" != "${name}" ]] || fail "component ${name} depends on itself"
    done
done

visit_component() {
    local name="$1" dependency
    local state="${visit_state[${name}]:-0}"
    local -a dependencies=()
    [[ "${state}" != 1 ]] || fail "component dependency cycle includes ${name}"
    [[ "${state}" != 2 ]] || return 0
    visit_state["${name}"]=1
    IFS=',' read -r -a dependencies <<< "${component_requires[${name}]}"
    for dependency in "${dependencies[@]}"; do
        [[ -z "${dependency}" ]] || visit_component "${dependency}"
    done
    visit_state["${name}"]=2
}

for name in "${!component_names[@]}"; do
    visit_component "${name}"
done

printf 'Validated %d StrataOS component manifests.\n' "${#component_files[@]}"
