#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import os
import shutil
import stat
from pathlib import Path

from common import BuildError, ROOT, log
from components import merge_tree, package_names
from config import load, validate


def pad4(value: int) -> int:
    return (-value) & 3


def write_newc(root: Path, destination: Path, epoch: int) -> None:
    entries = [root, *sorted(root.rglob("*"), key=lambda p: p.relative_to(root).as_posix())]
    ino = 1
    with destination.open("wb") as out:
        for path in entries:
            relative = "." if path == root else path.relative_to(root).as_posix()
            st = path.lstat()
            if path.is_symlink():
                mode = stat.S_IFLNK | stat.S_IMODE(st.st_mode)
                data = os.readlink(path).encode()
                nlink = 1
            elif path.is_dir():
                mode = stat.S_IFDIR | stat.S_IMODE(st.st_mode)
                data = b""
                nlink = 2
            elif path.is_file():
                mode = stat.S_IFREG | stat.S_IMODE(st.st_mode)
                data = path.read_bytes()
                nlink = 1
            else:
                raise BuildError(f"unsupported initramfs entry: {path}")
            name = relative.encode() + b"\0"
            fields = (
                ino, mode, 0, 0, nlink, epoch, len(data), 0, 0, 0, 0, len(name), 0,
            )
            header = b"070701" + b"".join(f"{value:08x}".encode() for value in fields)
            out.write(header)
            out.write(name)
            out.write(b"\0" * pad4(len(header) + len(name)))
            out.write(data)
            out.write(b"\0" * pad4(len(data)))
            ino += 1
        name = b"TRAILER!!!\0"
        fields = (ino, 0, 0, 0, 1, epoch, 0, 0, 0, 0, 0, len(name), 0)
        header = b"070701" + b"".join(f"{value:08x}".encode() for value in fields)
        out.write(header)
        out.write(name)
        out.write(b"\0" * pad4(len(header) + len(name)))


def command_exists(root: Path, command: str) -> bool:
    return any((root / prefix / command).exists() or (root / prefix / command).is_symlink() for prefix in ("bin", "sbin", "usr/bin", "usr/sbin"))


def validate_util_linux_tools(root: Path) -> None:
    for relative, capability in (
        ("sbin/blkid", "label lookup"),
        ("bin/mount", "mount option parsing"),
        ("sbin/losetup", "loop allocation output"),
        ("sbin/switch_root", "deferred initramfs cleanup"),
    ):
        command = root / relative
        if command.is_symlink() and command.resolve().name == "busybox":
            raise BuildError(
                f"initramfs requires util-linux {command.name} with {capability} support"
            )


def build_initramfs(config_path: Path, output: Path) -> Path:
    config = load(config_path)
    validate(config)
    stage = output / "initramfs/root"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    for package in package_names("system-core"):
        package_root = output / "packages" / package / "root"
        if not package_root.exists():
            raise BuildError(f"missing package root for initramfs: {package}")
        merge_tree(package_root, stage, runtime_only=True)
    merge_tree(ROOT / "initramfs", stage)
    util_switch_root = output / "packages/util-linux/root/sbin/switch_root"
    if not util_switch_root.is_file():
        raise BuildError(f"missing util-linux switch_root: {util_switch_root}")
    staged_switch_root = stage / "sbin/switch_root"
    staged_switch_root.unlink(missing_ok=True)
    shutil.copy2(util_switch_root, staged_switch_root)
    for directory in ("proc", "sys", "dev", "run", "newroot", "tmp", "run/strataos", "run/strata-esp", "run/strata-data"):
        (stage / directory).mkdir(parents=True, exist_ok=True)
    (stage / "init").chmod(0o755)
    (stage / "bin/strata-componentd").chmod(0o755)
    required = (
        "sh", "awk", "grep", "sort", "stat", "sha256sum", "cut", "cp",
        "truncate", "dmesg", "blkid", "blockdev", "lsblk", "sfdisk", "partx", "losetup",
        "mount", "umount", "switch_root", "mkfs.ext4", "e2fsck", "resize2fs",
        "mdadm", "integritysetup", "dmsetup",
    )
    missing = [name for name in required if not command_exists(stage, name)]
    if missing:
        raise BuildError("initramfs misses required commands: " + ", ".join(missing))
    validate_util_linux_tools(stage)
    out_dir = output / "initramfs"
    out_dir.mkdir(parents=True, exist_ok=True)
    cpio = out_dir / "initramfs.cpio"
    compressed = out_dir / "initramfs.cpio.gz"
    epoch = int(config.get("STRATA_SOURCE_DATE_EPOCH", "0"), 10)
    write_newc(stage, cpio, epoch)
    with cpio.open("rb") as source, compressed.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch, compresslevel=9) as target:
            shutil.copyfileobj(source, target)
    cpio.unlink()
    log(f"initramfs: {compressed}")
    return compressed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_initramfs(args.config.resolve(), args.output.resolve())
    except (BuildError, OSError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
