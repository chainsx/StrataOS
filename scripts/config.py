#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import BuildError, ROOT, atomic_write, host_arch

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
DATA_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
REQUIRED = {
    "STRATA_ARCH",
    "STRATA_VERSION",
    "STRATA_LLVM_VERSION",
    "STRATA_MUSL_VERSION",
    "STRATA_CMAKE_VERSION",
    "STRATA_BOOTLOADER",
    "STRATA_DEFAULT_HOSTNAME",
}


def load(path: Path) -> dict[str, str]:
    if not path.exists():
        raise BuildError(f"configuration does not exist: {path}; run make <arch>_defconfig")
    result: dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise BuildError(f"{path}:{lineno}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"')
        if not KEY_RE.fullmatch(key):
            raise BuildError(f"{path}:{lineno}: invalid key {key!r}")
        if key in result:
            raise BuildError(f"{path}:{lineno}: duplicate key {key}")
        result[key] = value
    missing = sorted(REQUIRED - result.keys())
    if missing:
        raise BuildError("missing configuration keys: " + ", ".join(missing))
    return result


def load_data(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        raise BuildError(f"missing data configuration: {path}")
    for lineno, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise BuildError(f"{path}:{lineno}: expected key=value")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not DATA_KEY_RE.fullmatch(key):
            raise BuildError(f"{path}:{lineno}: invalid key {key!r}")
        if key in result:
            raise BuildError(f"{path}:{lineno}: duplicate key {key}")
        result[key] = value
    return result


def as_int(config: dict[str, str], key: str, default: int | None = None) -> int:
    if key not in config:
        if default is None:
            raise BuildError(f"missing integer configuration: {key}")
        return default
    try:
        return int(config[key], 10)
    except ValueError as exc:
        raise BuildError(f"{key} must be an integer") from exc


def enabled(config: dict[str, str], key: str, default: bool = True) -> bool:
    value = config.get(key, "1" if default else "0")
    if value not in {"0", "1"}:
        raise BuildError(f"{key} must be 0 or 1")
    return value == "1"


def validate_component_policy() -> None:
    """Validate the ESP policy against the published component manifests."""
    policy_path = ROOT / "configs/runtime/components.conf"
    policy = load_data(policy_path)
    if policy.get("format") != "1":
        raise BuildError(f"{policy_path}: format must be 1")

    manifests = sorted((ROOT / "components").glob("*/component.conf"))
    names: set[str] = set()
    requires: dict[str, tuple[str, ...]] = {}
    for manifest in manifests:
        data = load_data(manifest)
        name = data.get("name")
        if not name or name != manifest.parent.name:
            raise BuildError(f"{manifest}: invalid component name")
        names.add(name)
        requires[name] = tuple(
            item for item in data.get("requires", "").split(",") if item
        )

    expected_keys = {"format"} | {f"component.{name}.enabled" for name in names}
    unknown = sorted(set(policy) - expected_keys)
    missing = sorted(expected_keys - set(policy))
    if unknown:
        raise BuildError(f"{policy_path}: unknown keys: {', '.join(unknown)}")
    if missing:
        raise BuildError(f"{policy_path}: missing keys: {', '.join(missing)}")
    if policy.get("component.system-core.enabled") != "yes":
        raise BuildError(f"{policy_path}: system-core must remain enabled")

    for name in sorted(names):
        key = f"component.{name}.enabled"
        if policy[key] not in {"yes", "no"}:
            raise BuildError(f"{policy_path}: {key} must be yes or no")
        if policy[key] == "yes":
            disabled = [
                dependency for dependency in requires[name]
                if policy.get(f"component.{dependency}.enabled") != "yes"
            ]
            if disabled:
                raise BuildError(
                    f"{policy_path}: enabled component {name} requires enabled "
                    + ", ".join(disabled)
                )


def validate(config: dict[str, str], *, native: bool = True) -> None:
    if config["STRATA_ARCH"] not in {"x86_64", "arm64"}:
        raise BuildError("STRATA_ARCH must be x86_64 or arm64")
    bootloader = config["STRATA_BOOTLOADER"]
    if bootloader not in {"limine-efi", "extlinux"}:
        raise BuildError("STRATA_BOOTLOADER must be limine-efi or extlinux")
    if bootloader == "limine-efi" and not config.get("STRATA_LIMINE_VERSION"):
        raise BuildError("STRATA_LIMINE_VERSION is required for STRATA_BOOTLOADER=limine-efi")
    removed = sorted({
        "STRATA_DEFAULT_USER", "STRATA_ENABLE_GRAPHICS", "STRATA_ENABLE_OPENSSH",
    } & config.keys())
    if removed:
        raise BuildError(
            "removed configuration keys must be deleted: " + ", ".join(removed)
        )
    if native and config["STRATA_ARCH"] != host_arch():
        raise BuildError(
            f"native-only build requested for {config['STRATA_ARCH']} on {host_arch()}; "
            "run this configuration on matching hardware"
        )
    for key in ("STRATA_JOBS", "STRATA_QEMU_DISK_MIB", "STRATA_SOURCE_DATE_EPOCH"):
        if key in config and as_int(config, key) < 0:
            raise BuildError(f"{key} must not be negative")
    for key in (
        "STRATA_ENABLE_DOCKER",
        "STRATA_ENABLE_FIREWALL",
        "STRATA_ENABLE_FAIL2BAN", "STRATA_ENABLE_CJK_FONTS",
        "STRATA_ENABLE_DIAGNOSTICS",
    ):
        enabled(config, key)
    if enabled(config, "STRATA_ENABLE_FAIL2BAN") and not enabled(config, "STRATA_ENABLE_FIREWALL"):
        raise BuildError("STRATA_ENABLE_FAIL2BAN requires STRATA_ENABLE_FIREWALL=1")
    disk = load_data(ROOT / "configs/image/disk.conf")
    if as_int(disk, "partition.esp.size_mib") < 96:
        raise BuildError("partition.esp.size_mib must be at least 96")
    if as_int(disk, "partition.data.min_size_mib") < 1024:
        raise BuildError("partition.data.min_size_mib must be at least 1024")
    validate_component_policy()


def normalize(path: Path) -> None:
    config = load(path)
    validate(config, native=False)
    body = "\n".join(f"{key}={config[key]}" for key in sorted(config)) + "\n"
    atomic_write(path, body)


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("normalize")
    command.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "normalize":
        normalize(args.config)


if __name__ == "__main__":
    main()
