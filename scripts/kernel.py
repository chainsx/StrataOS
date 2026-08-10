#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

from common import BuildError, ROOT, extract, jobs, log, run
from config import load, validate
from fetch import fetch_source
from recipes import load_recipe


KERNEL_CONFIGS = ROOT / "configs/kernel"


def kernel_arch(arch: str) -> str:
    return "x86_64" if arch == "x86_64" else "arm64"


def kernel_target(arch: str) -> str:
    return "bzImage" if arch == "x86_64" else "Image"

def kernel_image(arch: str) -> str:
    return "arch/x86/boot/bzImage" if arch == "x86_64" else "arch/arm64/boot/Image"


def required_symbols() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in (KERNEL_CONFIGS / "required-symbols.list").read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        symbol, value = line.split(None, 1)
        result[symbol] = value
    return result


def config_value(body: str, symbol: str) -> str:
    prefix = symbol + "="
    for line in body.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
        if line == f"# {symbol} is not set":
            return "n"
    return "missing"


def verify_config(path: Path) -> None:
    body = path.read_text()
    failures = [
        f"{symbol}={config_value(body, symbol)}"
        for symbol, expected in required_symbols().items()
        if config_value(body, symbol) != expected
    ]
    if failures:
        raise BuildError("final kernel configuration is incomplete: " + ", ".join(failures))


def build_kernel(config_path: Path, output: Path) -> Path:
    config = load(config_path)
    validate(config)
    arch = config["STRATA_ARCH"]
    parallel = jobs(int(config.get("STRATA_JOBS", "0")))
    recipe = load_recipe("linux")
    if recipe.build_system != "kernel" or recipe.source is None:
        raise BuildError(f"{recipe.path}: Linux must use the kernel build system and a source")
    source_entry = recipe.source_for_arch(arch)
    archive = fetch_source(source_entry, recipe.version, output / "dl")
    source = extract(
        archive, output / "src/linux", strip_components=source_entry.strip_components,
        parallelism=parallel,
    )

    build = output / "kernel/build"
    image_dir = output / "kernel"
    stamp = image_dir / ".complete"
    fingerprint = "\n".join(
        [
            f"arch={arch}",
            f"linux={recipe.version}",
            f"llvm={config['STRATA_LLVM_VERSION']}",
            recipe.path.read_text(),
            (KERNEL_CONFIGS / arch / "kernel.config").read_text(),
        ]
    )
    if stamp.exists() and stamp.read_text() == fingerprint:
        return image_dir / "kernel"
    shutil.rmtree(build, ignore_errors=True)
    build.mkdir(parents=True)
    image_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(KERNEL_CONFIGS / arch / "kernel.config", build / ".config")
    llvm_bin = output / "toolchain/llvm/bin"
    if not (llvm_bin / "clang").exists():
        raise BuildError("LLVM toolchain is missing; run make toolchain")
    env = {
        "PATH": f"{llvm_bin}:{os.environ.get('PATH', '')}",
        "LLVM": "1",
        "LLVM_IAS": "1",
        "HOSTCC": str(llvm_bin / "clang"),
        "HOSTCXX": str(llvm_bin / "clang++"),
        "SOURCE_DATE_EPOCH": config.get("STRATA_SOURCE_DATE_EPOCH", "0"),
        "KBUILD_BUILD_USER": "strataos",
        "KBUILD_BUILD_HOST": "builder",
        "KBUILD_BUILD_TIMESTAMP": "@" + config.get("STRATA_SOURCE_DATE_EPOCH", "0"),
    }
    make_base = [
        "make",
        "-C",
        str(source),
        f"O={build}",
        f"ARCH={kernel_arch(arch)}",
        "LLVM=1",
        "LLVM_IAS=1",
    ]
    run([*make_base, "olddefconfig"], env=env)
    verify_config(build / ".config")
    run([*make_base, f"-j{parallel}", kernel_target(arch)], env=env)
    run([*make_base, f"-j{parallel}", "modules"], env=env)
    built = build / kernel_image(arch)
    if not built.exists():
        raise BuildError(f"kernel build did not produce {kernel_image(arch)}")
    shutil.copy2(built, image_dir / "kernel")
    shutil.copy2(build / ".config", image_dir / "kernel.config")
    modules_root = image_dir / "modules-root"
    shutil.rmtree(modules_root, ignore_errors=True)
    run([*make_base, "modules_install", f"INSTALL_MOD_PATH={modules_root}", "DEPMOD=/bin/true"], env=env)
    if not any(modules_root.rglob("*.ko")):
        raise BuildError("kernel module configuration produced no loadable modules")
    (image_dir / "clang-version.txt").write_text(
        run([str(llvm_bin / "clang"), "--version"], capture=True).stdout or ""
    )
    stamp.write_text(fingerprint)
    log(f"kernel image: {image_dir / 'kernel'}")
    return image_dir / "kernel"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        build_kernel(args.config.resolve(), args.output.resolve())
    except (BuildError, OSError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
