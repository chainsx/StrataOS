#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from bootstrap_toolchain import bootstrap
from common import BuildError, configure_build_log, jobs, log, require_commands
from components import build_components
from config import load, validate
from image import build_image
from initramfs import build_initramfs
from kernel import build_kernel
from package_builder import build_packages


def clean_output(output: Path) -> None:
    downloads = output / "dl"
    preserved = None
    if downloads.exists():
        preserved = output.parent / f".{output.name}-dl-preserved"
        shutil.rmtree(preserved, ignore_errors=True)
        downloads.replace(preserved)
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True, exist_ok=True)
    if preserved and preserved.exists():
        preserved.replace(output / "dl")
    log(f"cleaned {output}; downloads preserved")


def main() -> None:
    parser = argparse.ArgumentParser(description="StrataOS native build orchestrator")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="reuse matching incomplete package work")
    parser.add_argument(
        "command",
        choices=["toolchain", "packages", "kernel", "components", "initramfs", "image", "all", "clean"],
    )
    args = parser.parse_args()
    config_path = args.config.resolve()
    output = args.output.resolve()
    try:
        if args.command == "clean":
            clean_output(output)
            return
        config = load(config_path)
        validate(config)
        parallel = jobs(int(config.get("STRATA_JOBS", "0")))
        commands = [
            "awk", "bc", "bison", "bzip2", "file", "find", "flex", "gzip",
            "make", "patch", "perl", "rsync", "sed", "tar", "unzip", "which", "xz",
        ]
        # LLVM/CMake/musl bootstrap inputs include both .tar.xz and .tar.gz.
        # xz provides -T itself; pigz is required for threaded gzip decoding
        # whenever the requested build parallelism is greater than one.
        if parallel > 1:
            commands.append("pigz")
        require_commands(commands)
        output.mkdir(parents=True, exist_ok=True)
        configure_build_log(output / "logs/build.log")
        log(f"parallel compile jobs: {parallel}")
        stages = {
            "toolchain": lambda: bootstrap(config_path, output),
            "packages": lambda: build_packages(config_path, output, resume=args.resume),
            "kernel": lambda: build_kernel(config_path, output),
            "components": lambda: build_components(config_path, output),
            "initramfs": lambda: build_initramfs(config_path, output),
            "image": lambda: build_image(config_path, output),
        }
        if args.command == "all":
            for name in ("toolchain", "packages", "kernel", "components", "initramfs", "image"):
                stages[name]()
        else:
            stages[args.command]()
    except (BuildError, OSError) as exc:
        raise SystemExit(f"StrataOS build failed: {exc}")


if __name__ == "__main__":
    main()
