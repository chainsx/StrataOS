#!/usr/bin/env python3
from __future__ import annotations

import argparse
import binascii
import json
import os
import shutil
import struct
import uuid
from pathlib import Path

from common import BuildError, ROOT, extract, jobs, log, run, sha256_file
from config import load, load_data, validate
from fetch import fetch_source
from recipes import load_recipe, load_toolchain_input


def find_tool(host: Path, *names: str) -> Path:
    for name in names:
        for candidate in (host / "bin" / name, host / "sbin" / name, *host.rglob(name)):
            if candidate.is_file() and candidate.stat().st_mode & 0o111:
                return candidate
    raise BuildError("host tool not found: " + " or ".join(names))


def find_limine_efi(root: Path, arch: str) -> Path:
    filename = "BOOTX64.EFI" if arch == "x86_64" else "BOOTAA64.EFI"
    matches = [path for path in root.rglob("*.EFI") if path.name.upper() == filename]
    if not matches:
        raise BuildError(f"Limine archive does not contain {filename}")
    return matches[0]


def int_value(data: dict[str, str], key: str) -> int:
    try:
        return int(data[key], 10)
    except (KeyError, ValueError) as exc:
        raise BuildError(f"{key} must be an integer") from exc


def kernel_command_line(arch: str, esp_label: str, data_label: str, data_fs: str) -> str:
    console = (
        "console=tty0 console=ttyS0,115200"
        if arch == "x86_64"
        else "console=ttyAMA0,115200 console=tty0"
    )
    # x86_64 KVM guests suffer from TSC clocksource watchdog false positives.
    clocksource_args = "clocksource=tsc tsc=nowatchdog" if arch == "x86_64" else ""
    return " ".join(
        value
        for value in (
            "rdinit=/init",
            f"strata.esp_label={esp_label}",
            f"strata.data_label={data_label}",
            f"strata.data_fs={data_fs}",
            console,
            clocksource_args,
            "panic=10",
        )
        if value
    )


def extlinux_config(command_line: str) -> str:
    return (
        "DEFAULT strataos\n"
        "PROMPT 0\n"
        "TIMEOUT 30\n\n"
        "LABEL strataos\n"
        "    MENU LABEL StrataOS\n"
        "    LINUX /strataos/kernel\n"
        "    INITRD /strataos/initramfs.cpio.gz\n"
        f"    APPEND {command_line}\n"
    )


def limine_config(command_line: str) -> str:
    return (
        "timeout: 3\n\n"
        "/StrataOS\n"
        "    protocol: linux\n"
        "    path: boot():/strataos/kernel\n"
        "    module_path: boot():/strataos/initramfs.cpio.gz\n"
        f"    cmdline: {command_line}\n"
    )


def align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def utf16_name(name: str) -> bytes:
    encoded = name.encode("utf-16le")
    if len(encoded) > 72:
        raise BuildError(f"GPT partition name is too long: {name}")
    return encoded + b"\0" * (72 - len(encoded))


def partition_entry(type_guid: str, part_guid: str, first: int, last: int, name: str) -> bytes:
    return struct.pack(
        "<16s16sQQQ72s",
        uuid.UUID(type_guid).bytes_le,
        uuid.UUID(part_guid).bytes_le,
        first,
        last,
        0,
        utf16_name(name),
    )


def gpt_header(
    current_lba: int,
    backup_lba: int,
    first_usable: int,
    last_usable: int,
    disk_guid: str,
    entries_lba: int,
    entries_crc: int,
    sector_size: int,
) -> bytes:
    header_size = 92
    header = bytearray(sector_size)
    struct.pack_into(
        "<8sIIIIQQQQ16sQIII",
        header,
        0,
        b"EFI PART",
        0x00010000,
        header_size,
        0,
        0,
        current_lba,
        backup_lba,
        first_usable,
        last_usable,
        uuid.UUID(disk_guid).bytes_le,
        entries_lba,
        128,
        128,
        entries_crc,
    )
    crc = binascii.crc32(header[:header_size]) & 0xFFFFFFFF
    struct.pack_into("<I", header, 16, crc)
    return bytes(header)


def write_gpt_image(
    destination: Path,
    image_bytes: int,
    sector_size: int,
    disk_guid: str,
    partitions: list[dict[str, int | str | Path]],
) -> None:
    if image_bytes % sector_size:
        raise BuildError("disk image size must be sector aligned")
    total_lbas = image_bytes // sector_size
    last_lba = total_lbas - 1
    entries_size = 128 * 128
    entries_sectors = entries_size // sector_size
    primary_entries_lba = 2
    backup_entries_lba = last_lba - entries_sectors
    first_usable = primary_entries_lba + entries_sectors
    last_usable = backup_entries_lba - 1
    entries = bytearray(entries_size)
    for index, item in enumerate(partitions):
        entry = partition_entry(
            str(item["type_guid"]),
            str(item["guid"]),
            int(item["first_lba"]),
            int(item["last_lba"]),
            str(item["name"]),
        )
        entries[index * 128 : (index + 1) * 128] = entry
    entries_crc = binascii.crc32(entries) & 0xFFFFFFFF
    primary = gpt_header(
        1, last_lba, first_usable, last_usable, disk_guid,
        primary_entries_lba, entries_crc, sector_size,
    )
    backup = gpt_header(
        last_lba, 1, first_usable, last_usable, disk_guid,
        backup_entries_lba, entries_crc, sector_size,
    )
    mbr = bytearray(sector_size)
    protective_count = min(last_lba, 0xFFFFFFFF)
    struct.pack_into("<B3sB3sII", mbr, 446, 0, b"\0\x02\0", 0xEE, b"\xff\xff\xff", 1, protective_count)
    mbr[510:512] = b"\x55\xaa"
    with destination.open("wb") as disk:
        disk.truncate(image_bytes)
        disk.seek(0)
        disk.write(mbr)
        disk.seek(sector_size)
        disk.write(primary)
        disk.seek(primary_entries_lba * sector_size)
        disk.write(entries)
        disk.seek(backup_entries_lba * sector_size)
        disk.write(entries)
        disk.seek(last_lba * sector_size)
        disk.write(backup)
        for item in partitions:
            image = Path(item["image"])
            partition_bytes = (int(item["last_lba"]) - int(item["first_lba"]) + 1) * sector_size
            if image.stat().st_size > partition_bytes:
                raise BuildError(f"partition image is too large: {image}")
            disk.seek(int(item["first_lba"]) * sector_size)
            with image.open("rb") as source:
                shutil.copyfileobj(source, disk, 4 * 1024 * 1024)


def build_image(config_path: Path, output: Path) -> Path:
    config = load(config_path)
    validate(config)
    disk = load_data(ROOT / "configs/image/disk.conf")
    storage = load_data(ROOT / "configs/runtime/storage.conf")
    arch = config["STRATA_ARCH"]
    bootloader = config["STRATA_BOOTLOADER"]
    parallel = jobs(int(config.get("STRATA_JOBS", "0")))
    host = output / "host"
    kernel = output / "kernel/kernel"
    initramfs = output / "initramfs/initramfs.cpio.gz"
    components_dir = output / "components"
    slot = output / "slot-A/components.list"
    component_versions = components_dir / "component-versions.json"
    component_versions_hash = component_versions.with_suffix(".json.sha256")
    for path in (kernel, initramfs, components_dir, slot, component_versions, component_versions_hash):
        if not path.exists():
            raise BuildError(f"missing image input: {path}")

    mkfs_fat = find_tool(host, "mkfs.fat", "mkfs.vfat")
    mcopy = find_tool(host, "mcopy")
    mke2fs = find_tool(host, "mkfs.ext4", "mke2fs")

    efi: Path | None = None
    if bootloader == "limine-efi":
        limine_input = load_toolchain_input("limine")
        if limine_input.version != config["STRATA_LIMINE_VERSION"]:
            raise BuildError(f"{limine_input.path}: version disagrees with build configuration")
        limine_source = limine_input.source_for_arch(arch)
        limine_archive = fetch_source(limine_source, limine_input.version, output / "dl")
        limine = extract(
            limine_archive, output / "src/limine", strip_components=limine_source.strip_components,
            parallelism=parallel,
        )
        efi = find_limine_efi(limine, arch)

    staging = output / "image-staging"
    shutil.rmtree(staging, ignore_errors=True)
    esp_root = staging / "esp"
    data_root = staging / "data"
    inputs = staging / "inputs"
    final_dir = output / "images"
    for directory in (esp_root, data_root, inputs, final_dir):
        directory.mkdir(parents=True, exist_ok=True)

    strata_esp = esp_root / "strataos"
    (strata_esp / "config").mkdir(parents=True)
    shutil.copy2(kernel, strata_esp / "kernel")
    shutil.copy2(initramfs, strata_esp / "initramfs.cpio.gz")
    config_files = {
        "disk.conf": ROOT / "configs/image/disk.conf",
        "storage.conf": ROOT / "configs/runtime/storage.conf",
        "logging.conf": ROOT / "configs/runtime/logging.conf",
        "components.conf": ROOT / "configs/runtime/components.conf",
    }
    for filename, source_path in config_files.items():
        shutil.copy2(source_path, strata_esp / "config" / filename)
    esp_label = disk["partition.esp.label"]
    data_label = disk["partition.data.label"]
    data_fs = disk["partition.data.filesystem"]
    command_line = kernel_command_line(arch, esp_label, data_label, data_fs)
    if data_fs != "ext4":
        raise BuildError("native image builder currently supports ext4 for the outer data partition")
    esp_entries = [strata_esp]
    if bootloader == "limine-efi":
        if efi is None:
            raise BuildError("Limine EFI binary is missing")
        boot_name = "BOOTX64.EFI" if arch == "x86_64" else "BOOTAA64.EFI"
        (esp_root / "EFI/BOOT").mkdir(parents=True)
        shutil.copy2(efi, esp_root / "EFI/BOOT" / boot_name)
        (esp_root / "limine.conf").write_text(limine_config(command_line))
        esp_entries.append(esp_root / "EFI")
    else:
        extlinux_dir = esp_root / "extlinux"
        extlinux_dir.mkdir()
        (extlinux_dir / "extlinux.conf").write_text(extlinux_config(command_line))
        esp_entries.append(extlinux_dir)

    data_path = storage.get("backend.data.path", "/strataos")
    if not data_path.startswith("/") or ".." in Path(data_path).parts:
        raise BuildError("backend.data.path must be a safe absolute path")
    strata_data = data_root / data_path.lstrip("/")
    for relative in ("components", "slots/A", "volumes", "state/boot", "transactions"):
        (strata_data / relative).mkdir(parents=True, exist_ok=True)
    for component in sorted(components_dir.glob("*.squashfs")):
        shutil.copy2(component, strata_data / "components" / component.name)
    shutil.copy2(slot, strata_data / "slots/A/components.list")
    shutil.copy2(component_versions, strata_data / component_versions.name)
    shutil.copy2(component_versions_hash, strata_data / component_versions_hash.name)
    (strata_data / "active-slot").write_text("A\n")
    release = {
        "name": "StrataOS",
        "version": config["STRATA_VERSION"],
        "architecture": arch,
        "bootloader": bootloader,
        "linux": load_recipe("linux").version,
        "llvm": config["STRATA_LLVM_VERSION"],
        "build_backend": "strataos-native",
        "component_protection": "sha256-filename-and-slot-list",
        "component_catalog": {
            "path": component_versions.name,
            "sha256": sha256_file(component_versions),
        },
        "components": [
            {"file": path.name, "sha256": sha256_file(path)}
            for path in sorted((strata_data / "components").glob("*.squashfs"))
        ],
    }
    (strata_data / "release.json").write_text(json.dumps(release, indent=2, sort_keys=True) + "\n")

    sector_size = int_value(disk, "sector_size")
    image_mib = int_value(disk, "image.size_mib")
    esp_mib = int_value(disk, "partition.esp.size_mib")
    alignment_mib = int_value(disk, "alignment_mib")
    data_min_mib = int_value(disk, "partition.data.min_size_mib")
    sectors_per_mib = 1024 * 1024 // sector_size
    alignment_sectors = alignment_mib * sectors_per_mib
    backup_gpt_sectors = (128 * 128) // sector_size + 1
    total_sectors = image_mib * sectors_per_mib
    esp_first = alignment_sectors
    esp_sectors = esp_mib * sectors_per_mib
    esp_last = esp_first + esp_sectors - 1
    data_first = align_up(esp_last + 1, alignment_sectors)
    # Calculate data partition size from actual content + 100 MiB headroom.
    data_content_bytes = sum(
        (f.stat().st_size if f.is_file() else 0) for f in data_root.rglob("*") if not f.is_symlink()
    )
    data_content_mib = (data_content_bytes + 1024 * 1024 - 1) // (1024 * 1024)
    data_size_mib = align_up(data_content_mib + 100, alignment_mib)
    data_sectors = data_size_mib * sectors_per_mib
    data_last = data_first + data_sectors - 1
    # Recalculate total image size: ESP + data + GPT overhead, aligned.
    image_sectors = align_up(data_last + 1 + align_up(backup_gpt_sectors, alignment_sectors), alignment_sectors)
    image_bytes = image_sectors * sector_size
    data_mib = data_sectors // sectors_per_mib

    esp_image = inputs / "esp.vfat"
    data_image = inputs / "data.ext4"
    with esp_image.open("wb") as handle:
        handle.truncate(esp_sectors * sector_size)
    run([str(mkfs_fat), "-F", "32", "-n", esp_label, str(esp_image)])
    env = {"MTOOLS_SKIP_CHECK": "1"}
    for entry in esp_entries:
        run([str(mcopy), "-i", str(esp_image), "-s", str(entry), "::/"], env=env)
    if bootloader == "limine-efi":
        run([str(mcopy), "-i", str(esp_image), str(esp_root / "limine.conf"), "::/limine.conf"], env=env)

    with data_image.open("wb") as handle:
        handle.truncate(data_sectors * sector_size)
    run([
        str(mke2fs), "-F", "-t", "ext4", "-m", disk["partition.data.reserved_percent"],
        "-T", disk["partition.data.usage_type"],
        "-O", "metadata_csum,64bit,dir_index,extent", "-L", data_label,
        "-d", str(data_root), str(data_image),
    ])

    disk_name = f"strataos-{config['STRATA_VERSION']}-{arch}.img"
    disk_image = final_dir / disk_name
    write_gpt_image(
        disk_image,
        image_bytes,
        sector_size,
        disk["disk.guid"],
        [
            {
                "name": "StrataOS ESP", "type_guid": disk["partition.esp.type_guid"],
                "guid": disk["partition.esp.guid"], "first_lba": esp_first,
                "last_lba": esp_last, "image": esp_image,
            },
            {
                "name": "StrataOS Data", "type_guid": disk["partition.data.type_guid"],
                "guid": disk["partition.data.guid"], "first_lba": data_first,
                "last_lba": data_last, "image": data_image,
            },
        ],
    )
    (final_dir / f"{disk_name}.sha256").write_text(f"{sha256_file(disk_image)}  {disk_image.name}\n")
    plan = {
        "image_mib": image_sectors // sectors_per_mib,
        "sector_size": sector_size,
        "esp": {"first_lba": esp_first, "last_lba": esp_last, "size_mib": esp_mib},
        "data": {"first_lba": data_first, "last_lba": data_last, "size_mib": data_mib, "filesystem": data_fs},
        "first_boot_auto_grow": disk.get("partition.data.auto_grow", "yes"),
    }
    (final_dir / f"{disk_name}.layout.json").write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    log(f"disk image: {disk_image}")
    return disk_image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_image(args.config.resolve(), args.output.resolve())
    except (BuildError, OSError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
