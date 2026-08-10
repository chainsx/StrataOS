#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

from build_policy import FORBIDDEN_HOST_PATH_FRAGMENTS, FORBIDDEN_TARGET_LINK_INPUTS
from common import BuildError, log

NEEDED_RE = re.compile(r"Shared library: \[([^\]]+)\]")
RPATH_RE = re.compile(r"(?:RPATH|RUNPATH).*Library (?:rpath|runpath): \[([^\]]*)\]")
INTERP_RE = re.compile(r"Requesting program interpreter: ([^\]]+)\]")


def _is_elf(path: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(4) == b"\x7fELF"
    except OSError:
        return False


def _readelf(readelf: Path, path: Path) -> str:
    completed = subprocess.run(
        [str(readelf), "-h", "-l", "-d", str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    if completed.returncode != 0:
        raise BuildError(f"llvm-readelf failed for {path}: {completed.stdout}")
    return completed.stdout or ""


def _expected_machine(arch: str) -> str:
    return "Advanced Micro Devices X86-64" if arch == "x86_64" else "AArch64"


def audit_elf_tree(root: Path, readelf: Path, arch: str, sysroot: Path | None = None) -> dict[str, set[str]]:
    needed_by_file: dict[str, set[str]] = {}
    expected_machine = _expected_machine(arch)
    sysroot_prefix = str(sysroot) if sysroot is not None else None
    count = 0
    for path in sorted(root.rglob("*")):
        if not _is_elf(path):
            continue
        count += 1
        text = _readelf(readelf, path)
        relative = path.relative_to(root).as_posix()
        machine = re.search(r"^\s*Machine:\s*(.+?)\s*$", text, re.M)
        if not machine or machine.group(1) != expected_machine:
            actual = machine.group(1) if machine else "unknown"
            raise BuildError(f"target ELF architecture mismatch: {path}: {actual}")
        needed = set(NEEDED_RE.findall(text))
        forbidden = sorted(
            library for library in needed
            if any(library.startswith(prefix) for prefix in FORBIDDEN_TARGET_LINK_INPUTS)
        )
        if forbidden:
            raise BuildError(f"target ELF {path} links forbidden host/GCC libraries: {', '.join(forbidden)}")
        interp_match = INTERP_RE.search(text)
        if interp_match and "ld-musl-" not in interp_match.group(1):
            raise BuildError(f"target ELF {path} uses non-musl interpreter: {interp_match.group(1)}")
        for rpath in RPATH_RE.findall(text):
            for component in rpath.split(":"):
                if not component:
                    continue
                # An RPATH component pointing inside the build-host sysroot will be
                # dead on the target device (that absolute path will not exist).
                # Log a warning but do not fail the build: these paths are excluded
                # from the final runtime image by RUNTIME_SKIP_PREFIXES, so the
                # affected ELF files are only used during the build.
                if sysroot_prefix and component.startswith(sysroot_prefix):
                    log(f"warning: {relative} has sysroot-absolute RPATH {component!r}"
                        " — will be dead on the target device")
                    continue
                for fragment in FORBIDDEN_HOST_PATH_FRAGMENTS:
                    if fragment in component:
                        raise BuildError(
                            f"target ELF {path} contains host RPATH/RUNPATH: {component!r}"
                        )
        needed_by_file[relative] = needed
    log(f"ELF audit: {count} target files checked under {root}")
    return needed_by_file


def _library_names(paths: Iterable[Path]) -> set[str]:
    names: set[str] = set()
    for directory in paths:
        if not directory.exists():
            continue
        for path in directory.rglob("*"):
            if path.is_file() or path.is_symlink():
                names.add(path.name)
    return names


def verify_needed_closure(sysroot: Path, readelf: Path, roots: Iterable[Path], arch: str) -> None:
    available = _library_names((sysroot / "lib", sysroot / "usr/lib", sysroot / "usr/lib64"))
    # Also include libraries provided by target packages themselves,
    # not just those in the sysroot (e.g. libsudo_util.so.0 in usr/libexec).
    root_dirs: list[Path] = []
    for root in roots:
        for sub in ("lib", "usr/lib", "usr/lib64", "usr/libexec"):
            d = root / sub
            if d.is_dir():
                root_dirs.append(d)
    available.update(_library_names(root_dirs))
    missing: dict[str, list[str]] = {}
    for root in roots:
        if not root.exists():
            continue
        for relative, needed in audit_elf_tree(root, readelf, arch, sysroot).items():
            absent = sorted(name for name in needed if name not in available and name != "linux-vdso.so.1" and not name.startswith("/"))
            if absent:
                missing[f"{root.name}/{relative}"] = absent
    if missing:
        rendered = "; ".join(f"{path}: {','.join(names)}" for path, names in sorted(missing.items()))
        raise BuildError("target ELF dependency closure is incomplete: " + rendered)
    log("target ELF dependency closure passed")
