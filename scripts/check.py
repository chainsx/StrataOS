#!/usr/bin/env python3
from __future__ import annotations

import argparse
import compileall
import os
import re
import subprocess
from pathlib import Path

from common import BuildError, ROOT
from config import load, load_data, validate
from package_builder import HOST_RECIPES, component_package_names, load_recipes, topological_order
from recipe_audit import audit_static_recipes
from recipes import load_toolchain_inputs

EXPECTED_COMPONENTS = {
    "system-core", "kernel-modules", "network", "python", "diagnostics", "openssh", "docker",
    "fonts-cjk", "firewall", "fail2ban",
}


def fail(message: str) -> None:
    raise BuildError(message)


def check_recipes(config: dict[str, str]) -> None:
    recipes = load_recipes()
    audit_static_recipes(recipes)
    requested = [*HOST_RECIPES, *component_package_names(config)]
    order = topological_order(recipes, requested)
    if len(order) != len(set(order)):
        fail("package graph contains duplicate nodes")
    for recipe in recipes.values():
        if recipe.source is None:
            continue
        for arch in ("x86_64", "arm64"):
            recipe.source_for_arch(arch)
    toolchain_inputs = load_toolchain_inputs()
    required_toolchain_inputs = {"llvm-prebuilt", "llvm-source", "cmake", "meson", "musl", "limine"}
    if set(toolchain_inputs) != required_toolchain_inputs:
        fail("toolchain input recipes are incomplete")
    for input_recipe in toolchain_inputs.values():
        for arch in ("x86_64", "arm64"):
            input_recipe.source_for_arch(arch)
    assigned: dict[str, str] = {}
    for component in EXPECTED_COMPONENTS:
        path = ROOT / "components" / component / "packages.list"
        for raw in path.read_text().splitlines():
            name = raw.strip()
            if not name or name.startswith("#"):
                continue
            if name not in recipes:
                fail(f"component {component} references unknown recipe {name}")
            if recipes[name].kind != "target":
                fail(f"component {component} references host recipe {name}")
            if name in assigned:
                fail(f"package {name} is assigned to both {assigned[name]} and {component}")
            assigned[name] = component
    required = {
        "busybox", "openrc", "zsh", "openssh", "docker-static",
        "fail2ban",
    }
    if not required.issubset(assigned):
        fail("required runtime package assignments are incomplete")
    declared_special_options = {
        "host-ninja": ("configure_args",),
        "host-zstd": ("build_args", "install_args"),
        "zstd": ("build_args", "install_args"),
        "host-squashfs-tools": ("build_args",),
        "bzip2": ("build_args",),
        "libcap": ("build_args", "install_args"),
        "openssl": ("configure_args", "install_args"),
        "argon2": ("build_args", "install_args"),
        "busybox": ("install_args",),
        "lvm2": ("configure_args", "build_args", "install_args"),
        "mdadm": ("build_args", "install_args"),
        "iproute2": ("configure_args", "build_args", "install_args"),
        "dhcpcd": ("configure_args",),
    }
    for name, phases in declared_special_options.items():
        recipe = recipes[name]
        for phase in phases:
            if not getattr(recipe, phase):
                fail(f"special package {name} must declare {phase} in its TOML recipe")


def check_components(config: dict[str, str]) -> None:
    names: set[str] = set()
    priorities: set[int] = set()
    component_priorities: dict[str, int] = {}
    requirements: dict[str, list[str]] = {}
    volume_keys: set[tuple[str, str]] = set()
    mountpoints: set[str] = set()
    for path in sorted((ROOT / "components").glob("*/component.conf")):
        item = load_data(path)
        name = item.get("name", "")
        if item.get("format") != "1" or not re.fullmatch(r"[a-z][a-z0-9-]*", name):
            fail(f"invalid component identity: {path}")
        if item.get("version") != config["STRATA_VERSION"]:
            fail(f"component version does not match StrataOS release: {path}")
        if name in names:
            fail(f"duplicate component name: {name}")
        names.add(name)
        priority = int(item["priority"], 10)
        if priority in priorities:
            fail(f"duplicate component priority: {priority}")
        priorities.add(priority)
        component_priorities[name] = priority
        if item.get("architectures") != "x86_64,arm64":
            fail(f"source component architecture template is invalid: {path}")
        parsed_requires = [value for value in item.get("requires", "").split(",") if value]
        requirements[name] = parsed_requires
        count = int(item.get("storage.count", "0"), 10)
        local_ids: set[str] = set()
        for index in range(count):
            prefix = f"storage.{index}."
            volume_id = item[prefix + "id"]
            mountpoint = item[prefix + "mount"]
            if volume_id in local_ids or mountpoint in mountpoints:
                fail(f"duplicate component volume identity in {path}")
            local_ids.add(volume_id)
            mountpoints.add(mountpoint)
            volume_keys.add((name, volume_id))
            if item[prefix + "format"] != "ext4":
                fail(f"component volumes must use ext4: {path}")
            if item[prefix + "redundancy"] not in {"inherit", "none", "mirror", "integrity-mirror"}:
                fail(f"invalid redundancy declaration: {path}")
    if names != EXPECTED_COMPONENTS:
        fail(f"unexpected component set: {sorted(names)}")
    for name, dependencies in requirements.items():
        for dependency in dependencies:
            if dependency not in names:
                fail(f"component {name} requires unknown component {dependency}")
            if component_priorities[dependency] >= component_priorities[name]:
                fail(f"component {name} dependency {dependency} must load earlier")
    required_volumes = {
        ("system-core", "state"), ("openssh", "identity"),
        ("network", "leases"), ("fail2ban", "database"),
        ("docker", "docker"),
    }
    if not required_volumes.issubset(volume_keys):
        fail("required component-owned volumes are missing")


def check_kernel() -> None:
    linux = load_recipes().get("linux")
    if linux is None or linux.build_system != "kernel" or linux.source is None:
        fail("Linux package recipe is missing or invalid")
    required: dict[str, str] = {}
    for raw in (ROOT / "configs/kernel/required-symbols.list").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        symbol, value = line.split()
        required[symbol] = value
    for arch in ("x86_64", "arm64"):
        path = ROOT / "configs/kernel" / arch / "kernel.config"
        lines = path.read_text().splitlines()
        if len(lines) > 450:
            fail(f"kernel seed is not sufficiently focused: {path}")
        symbols: dict[str, str] = {}
        for line in lines:
            match = re.match(r"(CONFIG_[A-Za-z0-9_]+)=(.*)$", line)
            if match:
                if match.group(1) in symbols:
                    fail(f"duplicate kernel symbol {match.group(1)} in {path}")
                symbols[match.group(1)] = match.group(2)
        for symbol, value in required.items():
            if symbols.get(symbol) != value:
                fail(f"{symbol}={value} missing from {path}")
        if symbols.get("CONFIG_MODULES") != "y":
            fail(f"kernel module support is required: {path}")


def shell_files() -> list[Path]:
    result = [ROOT / "initramfs/init", ROOT / "initramfs/bin/strata-componentd"]
    result.extend(ROOT.glob("scripts/*.sh"))
    for path in ROOT.glob("components/**/rootfs/**/*"):
        if path.is_file() and (
            "/etc/init.d/" in path.as_posix()
            or "/usr/libexec/" in path.as_posix()
            or "/usr/local/sbin/" in path.as_posix()
        ):
            result.append(path)
    result.extend(ROOT.glob("components/*/hooks/*"))
    return sorted(set(result))


def check_shell() -> None:
    for path in shell_files():
        text = path.read_text()
        interpreter = "bash" if text.startswith(("#!/usr/bin/env bash", "#!/bin/bash")) else "sh"
        subprocess.run([interpreter, "-n", str(path)], check=True)
        target = path == ROOT / "initramfs/init" or "initramfs/bin" in path.as_posix() or "/rootfs/" in path.as_posix()
        if target and re.search(r"\{[A-Za-z0-9_./-]+,[A-Za-z0-9_,./-]+\}", text):
            fail(f"non-POSIX brace expansion: {path}")
        if text.startswith("#!") and not os.access(path, os.X_OK):
            fail(f"script is not executable: {path}")


def check_storage_logging_and_security() -> None:
    if (ROOT / "SOURCE-MANIFEST.sha256").exists():
        fail("deprecated SOURCE-MANIFEST.sha256 remains in the source tree")
    storage = load_data(ROOT / "configs/runtime/storage.conf")
    logging = load_data(ROOT / "configs/runtime/logging.conf")
    disk = load_data(ROOT / "configs/image/disk.conf")
    if storage.get("volume.default.redundancy") != "none":
        fail("default data redundancy must remain none")
    if storage.get("volume.default.integrity") != "crc32c":
        fail("integrity-mirror must use crc32c")
    if disk.get("partition.data.filesystem") != "ext4":
        fail("outer data partition must use the implemented ext4 backend")
    if disk.get("partition.data.auto_grow") != "yes":
        fail("first-boot data partition growth must be enabled")
    if int(logging.get("boot_log_count", "0"), 10) < 1:
        fail("boot log retention is not configured")
    componentd = (ROOT / "initramfs/bin/strata-componentd").read_text()
    for token in ("mdadm --create", "--level=1", "integritysetup format", "e2fsck", "resize2fs", "mismatch_cnt", "operations.log"):
        if token not in componentd and token not in (ROOT / "components/system-core/rootfs/usr/local/sbin/strataos-storage-scrub").read_text():
            fail(f"storage runtime misses: {token}")
    ssh = (
        ROOT / "components/openssh/rootfs/etc/ssh/sshd_config.d/10-strataos.conf"
    ).read_text()
    for line in ("PermitRootLogin yes", "PasswordAuthentication yes", "KbdInteractiveAuthentication no", "PubkeyAuthentication yes"):
        if line not in ssh:
            fail(f"missing SSH security default: {line}")
    rootfs_source = (ROOT / "scripts/rootfs.py").read_text()
    if '"strata": (1000, 1000)' in rootfs_source or "strata:x:1000:1000" in rootfs_source:
        fail("deprecated default strata account remains")
    if "ROOT_INITIAL_PASSWORD_HASH" not in rootfs_source:
        fail("initial root password is missing")
    initial_setup = (
        ROOT / "components/system-core/rootfs/usr/libexec/strataos/initial-setup"
    ).read_text()
    for token in ("passwd root", "useradd -m -U", "initial-setup-complete"):
        if token not in initial_setup:
            fail(f"initial account setup misses: {token}")
    image_builder = (ROOT / "scripts/image.py").read_text()
    if "authorized_keys" in image_builder:
        fail("build-time authorized key injection remains enabled")


def check_native_pipeline() -> None:
    package_builder = (ROOT / "scripts/package_builder.py").read_text()
    image_builder = (ROOT / "scripts/image.py").read_text()
    components = (ROOT / "scripts/components.py").read_text()
    bootstrap = (ROOT / "scripts/bootstrap_toolchain.py").read_text()
    for token in ("topological_order", "merge_into_sysroot", "package-work", "DESTDIR", "source-aware build parameter audit", "audit_elf_tree"):
        if token not in package_builder:
            fail(f"native package pipeline misses {token}")
    for token in ("EFI PART", "partition_entry", "write_gpt_image", "mke2fs"):
        if token not in image_builder:
            fail(f"native image pipeline misses {token}")
    for token in ("packages.json", "packages.list", "ownership_for", "mksquashfs"):
        if token not in components:
            fail(f"component packaging misses {token}")
    for token in ("install_compiler_rt_target_runtime", "LIBCC", "smoke_test_musl_link", "verify_runtime_driver_plan", "verify_runtime_link_plan"):
        if token not in bootstrap:
            fail(f"toolchain bootstrap misses {token}")
    forbidden = "build" + "root"
    generated_roots = {".git", ".libs", "build", "dl", "output"}
    candidates: list[Path] = []
    for entry in ROOT.iterdir():
        if entry.name in generated_roots:
            continue
        candidates.extend(entry.rglob("*") if entry.is_dir() else (entry,))
    source_files = [
        path for path in candidates
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    ]
    for path in source_files:
        try:
            text = path.read_text(errors="ignore").lower()
        except OSError:
            continue
        if forbidden in text:
            fail(f"external build backend reference remains in {path}")
        forbidden_kernel_baseline = "arm" + "bian"
        change_log_prefix = "change" + "log"
        if forbidden_kernel_baseline in text:
            fail(f"external kernel baseline name remains in {path}")
        if path.name.lower().startswith(change_log_prefix) or path.name.lower() in {"changes", "changes.md"}:
            fail(f"historical conversation log must not be shipped: {path}")
    for path in source_files:
        if path.suffix in {".ext4", ".img"}:
            fail(f"pre-created data or disk image is not allowed in source tree: {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--packages-only", action="store_true")
    args = parser.parse_args()
    try:
        config = load(args.config.resolve())
        validate(config, native=False)
        check_recipes(config)
        if args.packages_only:
            print("StrataOS package recipes validated.")
            return
        check_components(config)
        check_kernel()
        check_shell()
        check_storage_logging_and_security()
        check_native_pipeline()
        if not compileall.compile_dir(ROOT / "scripts", quiet=1, force=True):
            fail("Python compilation failed")
        print("StrataOS project checks passed.")
    except (BuildError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
