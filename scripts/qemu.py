#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import platform
import shutil
from pathlib import Path

from common import BuildError, run
from config import load, load_data, validate


def _find_uefi_firmware(arch: str) -> tuple[Path, Path]:
    """Return (code_path, vars_template_path) for UEFI firmware."""
    override = os.environ.get("STRATA_UEFI_FIRMWARE")
    if override:
        code = Path(override)
        vars_tmpl = code.parent / code.name.replace("CODE", "VARS")
        if code.is_file() and vars_tmpl.is_file():
            return code, vars_tmpl
        raise BuildError(
            f"STRATA_UEFI_FIRMWARE={override}: "
            "both CODE and VARS files must exist"
        )

    if arch == "x86_64":
        pairs: list[tuple[str, str]] = [
            ("/usr/share/OVMF/OVMF_CODE_4M.fd", "/usr/share/OVMF/OVMF_VARS_4M.fd"),
            ("/usr/share/OVMF/OVMF_CODE.fd", "/usr/share/OVMF/OVMF_VARS.fd"),
            ("/usr/share/edk2/x64/OVMF_CODE.fd", "/usr/share/edk2/x64/OVMF_VARS.fd"),
            ("/usr/share/qemu/OVMF_CODE.fd", "/usr/share/qemu/OVMF_VARS.fd"),
        ]
    else:
        pairs = [
            ("/usr/share/AAVMF/AAVMF_CODE.fd", "/usr/share/AAVMF/AAVMF_VARS.fd"),
            ("/usr/share/edk2/aarch64/QEMU_EFI.fd", None),
            ("/usr/share/qemu-efi-aarch64/QEMU_EFI.fd", None),
        ]
    for code_s, vars_s in pairs:
        code = Path(code_s)
        if not code.is_file():
            continue
        if vars_s is None:
            # arm64 single-file firmware
            return code, code
        vars_tmpl = Path(vars_s)
        if vars_tmpl.is_file():
            return code, vars_tmpl
    raise BuildError(
        "UEFI firmware not found; install ovmf or set "
        "STRATA_UEFI_FIRMWARE=/path/to/OVMF_CODE.fd"
    )


def qemu_disk_mib(config: dict[str, str]) -> int:
    disk = load_data(Path(__file__).resolve().parents[1] / "configs/image/disk.conf")
    storage = load_data(Path(__file__).resolve().parents[1] / "configs/runtime/storage.conf")
    redundancy = storage.get("volume.default.redundancy", "none")
    factor = 2 if redundancy in {"mirror", "integrity-mirror"} else 1
    declared = 0
    enabled = {"system-core", "network", "python", "openssh"}
    if config.get("STRATA_ENABLE_DIAGNOSTICS") == "1":
        enabled.add("diagnostics")
    if config.get("STRATA_ENABLE_DOCKER") == "1":
        enabled.add("docker")
    if config.get("STRATA_ENABLE_GRAPHICS") == "1":
        enabled.add("graphics")
    if config.get("STRATA_ENABLE_CJK_FONTS") == "1":
        enabled.add("fonts-cjk")
    if config.get("STRATA_ENABLE_FIREWALL") == "1":
        enabled.add("firewall")
    if config.get("STRATA_ENABLE_FAIL2BAN") == "1":
        enabled.add("fail2ban")
    components = Path(__file__).resolve().parents[1] / "components"
    for metadata in components.glob("*/component.conf"):
        if metadata.parent.name not in enabled:
            continue
        item = load_data(metadata)
        count = int(item.get("storage.count", "0"), 10)
        for index in range(count):
            declared += int(item[f"storage.{index}.initial_size_mib"], 10) * factor
    minimum = int(disk["partition.esp.size_mib"], 10) + declared + 2048
    requested = int(config.get("STRATA_QEMU_DISK_MIB", str(max(32768, minimum))))
    if requested < minimum:
        raise BuildError(
            f"STRATA_QEMU_DISK_MIB={requested} is too small; "
            f"at least {minimum} MiB is required"
        )
    return requested


def prepare_overlay(raw_image: Path, output: Path, config: dict[str, str]) -> Path:
    qemu_img = shutil.which("qemu-img")
    if not qemu_img:
        raise BuildError("qemu-img not found; install qemu-utils")
    overlay = output / "images" / f"{raw_image.stem}-qemu.qcow2"
    marker = overlay.with_suffix(overlay.suffix + ".base-mtime")
    fingerprint = (
        f"{raw_image.resolve()}\n"
        f"{raw_image.stat().st_mtime_ns}\n"
        f"{qemu_disk_mib(config)}\n"
    )
    if not overlay.exists() or not marker.exists() or marker.read_text() != fingerprint:
        overlay.unlink(missing_ok=True)
        run(
            [
                qemu_img,
                "create",
                "-f", "qcow2",
                "-F", "raw",
                "-b", str(raw_image.resolve()),
                str(overlay),
                f"{qemu_disk_mib(config)}M",
            ]
        )
        marker.write_text(fingerprint)
    return overlay


def prepare_vars(
    vars_template: Path,
    output: Path,
    raw_image: Path,
    firmware_profile: str,
) -> Path:
    """Copy VARS state, refreshing it when the image or PCI topology changes."""
    vars_file = output / "images" / f"{raw_image.stem}-VARS.fd"
    marker = vars_file.with_suffix(vars_file.suffix + ".base-state")
    fingerprint = (
        f"{vars_template.resolve()}\n"
        f"{vars_template.stat().st_mtime_ns}\n"
        f"{vars_template.stat().st_size}\n"
        f"{raw_image.resolve()}\n"
        f"{raw_image.stat().st_mtime_ns}\n"
        f"{firmware_profile}\n"
    )
    if not vars_file.exists() or not marker.exists() or marker.read_text() != fingerprint:
        shutil.copy2(vars_template, vars_file)
        marker.write_text(fingerprint)
    return vars_file


def qemu_acceleration_args(
    arch: str,
    *,
    kvm_accessible: bool | None = None,
    host_arch: str | None = None,
) -> list[str]:
    """Select hardware acceleration only when KVM can run the target arch."""
    if kvm_accessible is None:
        kvm_accessible = os.access("/dev/kvm", os.R_OK | os.W_OK)
    if host_arch is None:
        host_arch = platform.machine()
    aliases = {"amd64": "x86_64", "aarch64": "arm64"}
    normalized_host = aliases.get(host_arch.lower(), host_arch.lower())
    if kvm_accessible and normalized_host == arch:
        return ["-accel", "kvm", "-cpu", "host"]
    fallback_cpu = "max" if arch == "x86_64" else "cortex-a72"
    return ["-accel", "tcg", "-cpu", fallback_cpu]


def qemu_graphics_args(enabled: bool) -> list[str]:
    """Expose a VirGL render node while keeping QEMU console-driven."""
    if not enabled:
        return ["-nographic"]
    return [
        "-display", "egl-headless,gl=on",
        "-device", "virtio-gpu-gl-pci",
        "-serial", "mon:stdio",
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        config = load(args.config.resolve())
        validate(config, native=False)
        if config["STRATA_BOOTLOADER"] != "limine-efi":
            raise BuildError(
                "make qemu requires STRATA_BOOTLOADER=limine-efi; "
                "boot extlinux images with U-Boot or board firmware"
            )
        arch = config["STRATA_ARCH"]
        output = args.output.resolve()
        image = output / "images" / f"strataos-{config['STRATA_VERSION']}-{arch}.img"
        if not image.exists():
            raise BuildError(f"image not found: {image}")

        code_fd, vars_template = _find_uefi_firmware(arch)
        gpu_enabled = os.environ.get("STRATA_QEMU_GPU", "virgl").lower() != "none"
        vars_fd = prepare_vars(
            vars_template,
            output,
            image,
            "virgl" if gpu_enabled else "serial",
        )

        qemu = shutil.which(
            "qemu-system-x86_64" if arch == "x86_64" else "qemu-system-aarch64"
        )
        if not qemu:
            raise BuildError("QEMU executable not found")
        overlay = prepare_overlay(image, output, config)

        netdev = "user,id=net0,hostfwd=tcp::2222-:22"
        command = [
            qemu,
            "-no-reboot",
            "-m", "4096",
            "-smp", "2",
            "-drive", f"if=pflash,format=raw,readonly=on,file={code_fd}",
            "-drive", f"if=pflash,format=raw,file={vars_fd}",
            "-drive", f"if=none,id=strata_disk,format=qcow2,cache=unsafe,file={overlay}",
            "-device", "virtio-blk-pci,drive=strata_disk,bootindex=1",
            "-netdev", netdev,
            "-device", "virtio-net-pci,netdev=net0,bootindex=2",
            "-boot", "order=c,strict=on",
        ]
        if arch == "x86_64":
            command += ["-machine", "q35"]
        else:
            command += ["-machine", "virt"]
        command += qemu_graphics_args(gpu_enabled)
        command += qemu_acceleration_args(arch)
        run(command)
    except (BuildError, OSError, ValueError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
