#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
from pathlib import Path
from typing import Iterable

from common import BuildError, ROOT, atomic_write, extract, jobs, log, run, sha256_file
from build_policy import (
    HOST_C_COMPILE_FLAGS, HOST_CXX_COMPILE_FLAGS, HOST_LINK_FLAGS, SANITIZED_ENVIRONMENT,
    target_c_compile_flags, target_cxx_compile_flags, target_cxx_link_flags, target_link_flags,
    target_cxx_header_flags,
    join_flags,
)
from elf_audit import audit_elf_tree, verify_needed_closure
from recipe_audit import audit_source_recipes, audit_static_recipes, write_audit_report
from config import enabled, load, validate
from fetch import fetch_source
from recipes import Recipe, load_recipes, load_toolchain_input

HOST_RECIPES = (
    "host-ninja",
    "host-zlib",
    "host-zstd",
    "host-pkgconf",
    "host-squashfs-tools",
    "host-e2fsprogs",
    "host-dosfstools",
    "host-mtools",
    "host-python",
)

LLVM_RUNTIME_SONAMES = ("libc++.so.1", "libunwind.so.1")


def has_llvm_runtime_libraries(root: Path) -> bool:
    """Whether an llvm-runtime package contains its required shared runtimes."""
    return all(
        any(path.is_file() or path.is_symlink() for path in root.rglob(name))
        for name in LLVM_RUNTIME_SONAMES
    )

_KCONFIG_ASSIGNMENT = re.compile(r"^CONFIG_([A-Za-z0-9_]+)=(.*)$")
_KCONFIG_UNSET = re.compile(r"^# CONFIG_([A-Za-z0-9_]+) is not set$")
def read_kconfig_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        raise BuildError(f"Kconfig output is missing: {path}")
    for raw in path.read_text(errors="replace").splitlines():
        assignment = _KCONFIG_ASSIGNMENT.fullmatch(raw.strip())
        if assignment:
            values[assignment.group(1)] = assignment.group(2)
        unset = _KCONFIG_UNSET.fullmatch(raw.strip())
        if unset:
            values[unset.group(1)] = "n"
    return values
def read_kconfig_fragment(path: Path) -> dict[str, str]:
    requested: dict[str, str] = {}
    if not path.is_file():
        raise BuildError(f"Kconfig fragment is missing: {path}")
    for lineno, raw in enumerate(path.read_text(errors="replace").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _KCONFIG_ASSIGNMENT.fullmatch(line)
        if not match:
            raise BuildError(f"{path}:{lineno}: invalid Kconfig fragment line: {line}")
        symbol, value = match.groups()
        if value not in {"y", "m", "n"} and not (
            re.fullmatch(r'-?[0-9]+', value)
            or re.fullmatch(r'0x[0-9A-Fa-f]+', value)
            or (len(value) >= 2 and value.startswith('"') and value.endswith('"'))
        ):
            raise BuildError(f"{path}:{lineno}: unsupported Kconfig value for CONFIG_{symbol}: {value}")
        previous = requested.get(symbol)
        if previous is not None and previous != value:
            raise BuildError(f"{path}:{lineno}: conflicting values for CONFIG_{symbol}")
        requested[symbol] = value
    if not requested:
        raise BuildError(f"Kconfig fragment is empty: {path}")
    return requested
def apply_kconfig_fragment(config: Path, fragment: Path) -> dict[str, str]:
    requested = read_kconfig_fragment(fragment)
    if not config.is_file():
        raise BuildError(f"base Kconfig output is missing: {config}")
    output: list[str] = []
    written: set[str] = set()
    for raw in config.read_text(errors="replace").splitlines():
        stripped = raw.strip()
        assignment = _KCONFIG_ASSIGNMENT.fullmatch(stripped)
        unset = _KCONFIG_UNSET.fullmatch(stripped)
        symbol = assignment.group(1) if assignment else unset.group(1) if unset else None
        if symbol is None or symbol not in requested:
            output.append(raw)
            continue
        if symbol in written:
            continue
        value = requested[symbol]
        output.append(f"# CONFIG_{symbol} is not set" if value == "n" else f"CONFIG_{symbol}={value}")
        written.add(symbol)
    for symbol, value in requested.items():
        if symbol not in written:
            output.append(f"# CONFIG_{symbol} is not set" if value == "n" else f"CONFIG_{symbol}={value}")
    atomic_write(config, "\n".join(output) + "\n")
    return requested
def verify_kconfig_fragment(config: Path, requested: dict[str, str]) -> None:
    effective = read_kconfig_values(config)
    mismatches = [
        f"CONFIG_{symbol}: requested {value}, effective {effective.get(symbol, 'missing')}"
        for symbol, value in requested.items()
        if effective.get(symbol) != value
    ]
    if mismatches:
        preview = "; ".join(mismatches[:12])
        if len(mismatches) > 12:
            preview += f"; ... and {len(mismatches) - 12} more"
        raise BuildError(f"BusyBox Kconfig fragment was not fully applied: {preview}")

RUNTIME_SKIP_PREFIXES = (
    "usr/include/",
    "usr/share/aclocal/",
    "usr/share/doc/",
    "usr/share/gtk-doc/",
    "usr/share/info/",
    "usr/share/man/",
    "usr/share/pkgconfig/",
    "usr/lib/cmake/",
    "usr/lib/pkgconfig/",
)
def topological_order(recipes: dict[str, Recipe], requested: Iterable[str]) -> list[str]:
    order: list[str] = []
    state: dict[str, int] = {}

    def visit(name: str) -> None:
        if name not in recipes:
            raise BuildError(f"unknown package recipe: {name}")
        current = state.get(name, 0)
        if current == 1:
            raise BuildError(f"package dependency cycle includes {name}")
        if current == 2:
            return
        state[name] = 1
        for dependency in recipes[name].dependencies:
            visit(dependency)
        state[name] = 2
        order.append(name)

    for item in requested:
        visit(item)
    return order
def component_package_names(config: dict[str, str]) -> list[str]:
    enabled_components = {"system-core", "network", "python", "openssh"}

    if enabled(config, "STRATA_ENABLE_DIAGNOSTICS"):
        enabled_components.add("diagnostics")

    if enabled(config, "STRATA_ENABLE_DOCKER"):
        enabled_components.add("docker")
    if enabled(config, "STRATA_ENABLE_CJK_FONTS"):
        enabled_components.add("fonts-cjk")
    if enabled(config, "STRATA_ENABLE_FIREWALL"):
        enabled_components.add("firewall")
    if enabled(config, "STRATA_ENABLE_FAIL2BAN"):
        enabled_components.add("fail2ban")
    names: list[str] = []
    seen: set[str] = set()
    for component in sorted(enabled_components):
        path = ROOT / "components" / component / "packages.list"
        for raw in path.read_text().splitlines():
            name = raw.strip()
            if not name or name.startswith("#"):
                continue
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names
def triple_for(arch: str) -> str:
    return "x86_64-linux-musl" if arch == "x86_64" else "aarch64-linux-musl"
def build_triplet() -> str:
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "x86_64-pc-linux-gnu"
    if machine in {"aarch64", "arm64"}:
        return "aarch64-unknown-linux-gnu"
    raise BuildError(f"unsupported build machine: {machine}")
class PackageBuilder:
    def __init__(self, config_path: Path, output: Path):
        self.config_path = config_path
        self.config = load(config_path)
        validate(self.config)
        self.output = output
        self.recipes = load_recipes()
        self.arch = self.config["STRATA_ARCH"]
        self.triple = triple_for(self.arch)
        self.toolchain = output / "toolchain"
        self.sysroot = self.toolchain / "sysroot"
        self.llvm_bin = self.toolchain / "llvm" / "bin"
        self.cmake_bin = self.toolchain / "cmake" / "bin"
        self.host = output / "host"
        self.host_bin = self.host / "bin"
        self.package_root = output / "packages"
        self.work_root = output / "package-work"
        self.src_root = output / "src" / "packages"
        self.dl = output / "dl"
        self.epoch = self.config.get("STRATA_SOURCE_DATE_EPOCH", "0")
        self.parallel = jobs(int(self.config.get("STRATA_JOBS", "0")))
        self._source_cache: dict[str, Path | None] = {}
        if not (self.toolchain / ".complete").exists():
            raise BuildError("toolchain is not bootstrapped; run make toolchain")
        for directory in (self.host_bin, self.package_root, self.work_root, self.src_root):
            directory.mkdir(parents=True, exist_ok=True)
        self.prepare_meson()
        self.write_cross_files()

    def prepare_meson(self) -> None:
        meson = load_toolchain_input("meson")
        archive = fetch_source(meson.source_for_arch(self.arch), meson.version, self.dl)
        source = extract(archive, self.output / "host-tools" / "meson", strip_components=1, parallelism=self.parallel)
        wrapper = self.host_bin / "meson"
        wrapper.write_text(
            "#!/bin/sh\n"
            f"exec python3 '{source / 'meson.py'}' \"$@\"\n"
        )
        wrapper.chmod(0o755)

    def write_cross_files(self) -> None:
        generated = self.output / "generated"
        target_cxx_flags = (
            *target_cxx_compile_flags(self.arch),
            *target_cxx_header_flags(self.sysroot),
        )

        generated.mkdir(parents=True, exist_ok=True)
        cpu = "x86_64" if self.arch == "x86_64" else "aarch64"
        family = cpu
        endian = "little"

        loader_name = "ld-musl-x86_64.so.1" if self.arch == "x86_64" else "ld-musl-aarch64.so.1"
        runner = generated / "run-target"
        qemu_name = "qemu-x86_64-static" if self.arch == "x86_64" else "qemu-aarch64-static"
        atomic_write(
            runner,
            "#!/bin/sh\n"
            "set -eu\n"
            f"SYSROOT='{self.sysroot}'\n"
            f"QEMU='{qemu_name}'\n"
            "if command -v \"$QEMU\" >/dev/null 2>&1; then\n"
            "  exec \"$QEMU\" -L \"$SYSROOT\" \"$@\"\n"
            "fi\n"
            f"LOADER='{self.sysroot / 'lib' / loader_name}'\n"
            "if [ -L \"$LOADER\" ]; then\n"
            "  TARGET=$(readlink \"$LOADER\")\n"
            "  case \"$TARGET\" in /*) LOADER=\"$SYSROOT$TARGET\" ;; esac\n"
            "fi\n"
            "[ -x \"$LOADER\" ] && exec \"$LOADER\" --library-path \"$SYSROOT/lib:$SYSROOT/usr/lib\" \"$@\"\n"
            "echo \"run-target: no runner available ($QEMU not found, $LOADER not executable)\" >&2\n"
            "exit 126\n",
            0o755,
        )

        native_pkgconf = generated / "pkgconf-native"
        atomic_write(
            native_pkgconf,
            "#!/bin/sh\n"
            "unset PKG_CONFIG PKG_CONFIG_PATH PKG_CONFIG_DIR PKG_CONFIG_SYSROOT_DIR PKG_CONFIG_LIBDIR\n"
            "unset PKG_CONFIG_ALLOW_SYSTEM_CFLAGS PKG_CONFIG_ALLOW_SYSTEM_LIBS\n"
            f"export PKG_CONFIG_PATH='{self.host / 'lib/pkgconfig'}:{self.host / 'share/pkgconfig'}'\n"
            f"exec '{self.host_bin / 'pkgconf'}' \"$@\"\n",
            0o755,
        )

        native = generated / "meson-native.ini"
        atomic_write(
            native,
            "[binaries]\n"
            f"c = '{self.llvm_bin / 'clang'}'\n"
            f"cpp = '{self.llvm_bin / 'clang++'}'\n"
            f"ar = '{self.llvm_bin / 'llvm-ar'}'\n"
            f"strip = '{self.llvm_bin / 'llvm-strip'}'\n"
            f"pkg-config = '{native_pkgconf}'\n"
            f"llvm-config = '{self.host_bin / 'llvm-config'}'\n"
            f"mesa_clc = '{self.host_bin / 'mesa_clc'}'\n"
            f"vtn_bindgen2 = '{self.host_bin / 'vtn_bindgen2'}'\n"
            f"glslangValidator = '{self.host_bin / 'glslangValidator'}'\n"
            "\n[built-in options]\n"
            f"c_args = {list(HOST_C_COMPILE_FLAGS)!r}\n"
            f"cpp_args = {list(HOST_CXX_COMPILE_FLAGS)!r}\n"
            f"c_link_args = {list(HOST_LINK_FLAGS)!r}\n"
            f"cpp_link_args = {list(HOST_LINK_FLAGS)!r}\n"
        )

        target = generated / "meson-cross.ini"
        atomic_write(
            target,
            "[binaries]\n"
            f"c = '{self.toolchain / 'bin' / (self.triple + '-cc')}'\n"
            f"cpp = '{self.toolchain / 'bin' / (self.triple + '-c++')}'\n"
            f"ar = '{self.toolchain / 'bin' / (self.triple + '-ar')}'\n"
            f"strip = '{self.toolchain / 'bin' / (self.triple + '-strip')}'\n"
            f"pkg-config = '{self.host_bin / 'pkgconf'}'\n"
            f"exe_wrapper = '{runner}'\n"
            "\n[host_machine]\n"
            "system = 'linux'\n"
            f"cpu_family = '{family}'\n"
            f"cpu = '{cpu}'\n"
            f"endian = '{endian}'\n"
            "\n[properties]\n"
            f"sys_root = '{self.sysroot}'\n"
            "needs_exe_wrapper = true\n"
            "\n[built-in options]\n"
            f"c_args = {list(target_c_compile_flags(self.arch))!r}\n"
            f"cpp_args = {list(target_cxx_flags)!r}\n"
            f"c_link_args = {list(target_link_flags(self.arch))!r}\n"
            f"cpp_link_args = {list(target_cxx_link_flags(self.arch))!r}\n"
        )

        toolchain = generated / "cmake-toolchain.cmake"
        atomic_write(
            toolchain,
            "set(CMAKE_SYSTEM_NAME Linux)\n"
            f"set(CMAKE_SYSTEM_PROCESSOR {cpu})\n"
            f"set(CMAKE_SYSROOT \"{self.sysroot}\")\n"
            f"set(CMAKE_C_COMPILER \"{self.toolchain / 'bin' / (self.triple + '-cc')}\")\n"
            f"set(CMAKE_CXX_COMPILER \"{self.toolchain / 'bin' / (self.triple + '-c++')}\")\n"
            f"set(CMAKE_AR \"{self.toolchain / 'bin' / (self.triple + '-ar')}\")\n"
            f"set(CMAKE_RANLIB \"{self.toolchain / 'bin' / (self.triple + '-ranlib')}\")\n"
            f"set(CMAKE_NM \"{self.toolchain / 'bin' / (self.triple + '-nm')}\")\n"
            f"set(CMAKE_STRIP \"{self.toolchain / 'bin' / (self.triple + '-strip')}\")\n"
            f"set(CMAKE_CROSSCOMPILING_EMULATOR \"{runner}\")\n"
            f"set(CMAKE_C_FLAGS_INIT \"{join_flags(target_c_compile_flags(self.arch))}\")\n"
            f"set(CMAKE_CXX_FLAGS_INIT \"{join_flags(target_cxx_flags)}\")\n"
            f"set(CMAKE_EXE_LINKER_FLAGS_INIT \"{join_flags(target_link_flags(self.arch))}\")\n"
            f"set(CMAKE_SHARED_LINKER_FLAGS_INIT \"{join_flags(target_link_flags(self.arch))}\")\n"
            f"set(CMAKE_MODULE_LINKER_FLAGS_INIT \"{join_flags(target_link_flags(self.arch))}\")\n"
            "set(CMAKE_POSITION_INDEPENDENT_CODE ON)\n"
            "set(CMAKE_SKIP_RPATH ON)\n"
            "set(CMAKE_C_BYTE_ORDER LITTLE_ENDIAN)\n"
            "set(CMAKE_CXX_BYTE_ORDER LITTLE_ENDIAN)\n"
            "set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)\n"
            "set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)\n"
            "set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)\n"
            "set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)\n"
            "set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)\n"
        )
        site = generated / "config.site"
        atomic_write(
            site,
            "ac_cv_func_malloc_0_nonnull=yes\n"
            "ac_cv_func_realloc_0_nonnull=yes\n"
            "ac_cv_func_getpgrp_void=yes\n"
            "ac_cv_c_bigendian=no\n"
            "ac_cv_file__dev_ptmx=yes\n"
            "ac_cv_file__dev_ptc=no\n"
        )

        # Ensure musl shared runtime (libc.so, loader, stubs) is in the sysroot.
        # The bootstrap's musl make install should provide these, but if they're
        # absent (e.g. after an incomplete bootstrap), reinstall from the build.
        self._ensure_musl_runtime()

        # Fix absolute symlinks in the sysroot that point within the sysroot.
        # musl install creates ld-musl-*.so.1 -> /usr/lib/libc.so which breaks
        # qemu-user because it resolves absolute symlinks against the host root.
        for _libdir in (self.sysroot / "lib", self.sysroot / "usr/lib"):
            if not _libdir.is_dir():
                continue
            for _item in sorted(_libdir.iterdir()):
                if not _item.is_symlink():
                    continue
                _target = _item.readlink()
                if not _target.is_absolute():
                    continue
                _resolved = self.sysroot / _target.relative_to("/")
                if _resolved.exists():
                    _rel = os.path.relpath(_resolved, _item.parent)
                    _item.unlink()
                    _item.symlink_to(_rel)

    def recipe_lto(self, recipe: Recipe) -> str | None:
        return None if recipe.lto == "inherit" else recipe.lto

    def recipe_meson_cross_files(self, recipe: Recipe) -> list[Path]:
        base = self.output / "generated/meson-cross.ini"
        lto = self.recipe_lto(recipe)
        if recipe.kind != "target" or lto is None:
            return [base]
        override = self.output / "generated" / f"meson-cross-lto-{lto}.ini"
        cxx_flags = (*target_cxx_compile_flags(self.arch, lto=lto), *target_cxx_header_flags(self.sysroot))
        atomic_write(
            override,
            "[built-in options]\n"
            f"c_args = {list(target_c_compile_flags(self.arch, lto=lto))!r}\n"
            f"cpp_args = {list(cxx_flags)!r}\n"
            f"c_link_args = {list(target_link_flags(self.arch, lto=lto))!r}\n"
            f"cpp_link_args = {list(target_cxx_link_flags(self.arch, lto=lto))!r}\n",
        )
        return [base, override]

    def _ensure_musl_runtime(self) -> None:
        """Ensure musl shared runtime files are in the sysroot.

        The bootstrap's musl make install should provide libc.so and the dynamic
        loader, but if they're absent (incomplete bootstrap / clean rebuild),
        reinstall from the cached bootstrap build directory (no host dependency).
        Also creates libm.so/libm.a symlinks pointing to libc since musl
        includes math in libc, not a separate libm.
        """
        libc_so = self.sysroot / "usr/lib/libc.so"
        _libm_so = self.sysroot / "usr/lib/libm.so"
        loader = self.sysroot / "lib/ld-musl-x86_64.so.1"
        if self.arch == "arm64":
            loader = self.sysroot / "lib/ld-musl-aarch64.so.1"
        libm_so_broken = _libm_so.is_symlink() and not _libm_so.resolve(strict=False).exists()
        if not libc_so.is_file() or not (loader.is_symlink() or loader.is_file()) or libm_so_broken:
            musl_build = self.output / "bootstrap-build/musl"
            if not (musl_build / "lib/libc.so").is_file():
                raise BuildError(
                    "musl shared runtime is missing from the sysroot and the "
                    "bootstrap build directory is unavailable; re-run 'make toolchain'"
                )
            run(["make", f"DESTDIR={self.sysroot}", "install"], cwd=musl_build, capture=True)
            log("reinstalled musl shared runtime from bootstrap build")

        # musl includes math in libc; create libm symlinks for packages
        # that link with -lm (json-c, etc.) without host library dependency.
        # Also fix musl-installed libm.a which is an empty stub — replace it
        # with a symlink to libc.a so that -lm resolves all math symbols.
        for _dir in (self.sysroot / "usr/lib",):
            if not _dir.is_dir():
                continue
            _libm_so = _dir / "libm.so"
            if not _libm_so.exists() or _libm_so.is_symlink() and not _libm_so.resolve(strict=False).exists():
                _libm_so.unlink(missing_ok=True)
                _libm_so.symlink_to("libc.so")
            _libm_a = _dir / "libm.a"
            if _libm_a.exists() and not _libm_a.is_symlink():
                _libm_a.unlink()
                _libm_a.symlink_to("libc.a")
            elif not _libm_a.exists():
                _libm_a.symlink_to("libc.a")
        # ncurses configured with --enable-widec installs only libncursesw;
        # create libncurses.so symlink for packages (readline, etc.) that
        # link with -lncurses.
        for _dir in (self.sysroot / "usr/lib",):
            if not _dir.is_dir():
                continue
            for _name in ("libncurses.so", "libncurses.so.6"):
                _p = _dir / _name
                # The wide ncurses library can be merged later from a cached
                # package.  Keep its compatibility link even while dangling.
                if not _p.exists() and not _p.is_symlink():
                    _p.symlink_to(_name.replace("ncurses", "ncursesw"))
    def context(self, recipe: Recipe, source: Path | None, build: Path, root: Path) -> dict[str, str]:
        ctx = {
            "root": str(ROOT),
            "package": str(recipe.directory),
            "output": str(self.output),
            "source": str(source or ""),
            "build": str(build),
            "destdir": str(root),
            "sysroot": str(self.sysroot),
            "host": str(self.host),
            "triple": self.triple,
            "arch": self.arch,
            "version": recipe.version,
            "host_cc": str(self.llvm_bin / "clang"),
            "host_cxx": str(self.llvm_bin / "clang++"),
        }
        return ctx

    def expand_args(self, args: Iterable[str], context: dict[str, str]) -> list[str]:
        return [value.format(**context) for value in args]

    def source_for(self, recipe: Recipe) -> Path | None:
        if recipe.name in self._source_cache:
            return self._source_cache[recipe.name]
        if recipe.source is None:
            self._source_cache[recipe.name] = None
            return None
        item = recipe.source_for_arch(self.arch)
        archive = fetch_source(item, recipe.version, self.dl)
        if item.archive == "file":
            result: Path | None = archive
        else:
            result = extract(
                archive, self.src_root / recipe.name,
                strip_components=item.strip_components,
                parallelism=self.parallel,
            )
            self.apply_source_patches(recipe, result)
        self._source_cache[recipe.name] = result
        return result

    def apply_source_patches(self, recipe: Recipe, source: Path) -> None:
        if not recipe.patches:
            return
        patch_paths = tuple(recipe.patch_path(name) for name in recipe.patches)
        missing = [str(path) for path in patch_paths if not path.is_file()]
        if missing:
            raise BuildError(f"{recipe.path}: missing source patches: {', '.join(missing)}")
        fingerprint = "".join(
            f"{path.name} {sha256_file(path)}\n" for path in patch_paths
        )
        marker = source / ".strata-source-patches"
        if marker.is_file() and marker.read_text() == fingerprint:
            return
        if marker.exists():
            raise BuildError(f"{recipe.name}: source patches changed; remove {source} and retry")
        for patch in patch_paths:
            run(["patch", "--batch", "--forward", "-p1", "--input", str(patch)], cwd=source)
        atomic_write(marker, fingerprint)

    def base_env(self, kind: str, recipe: Recipe, context: dict[str, str]) -> dict[str, str]:
        path = ":".join(
            str(item)
            for item in (
                self.host_bin,
                self.cmake_bin,
                self.toolchain / "bin",
                self.llvm_bin,
                Path(os.environ.get("PATH", "/usr/bin:/bin")),
            )
        )
        build_home = self.output / "build-home"
        build_home.mkdir(parents=True, exist_ok=True)
        env = {
            "PATH": path,
            "HOME": str(build_home),
            "SOURCE_DATE_EPOCH": self.epoch,
            "ZERO_AR_DATE": "1",
            "LC_ALL": "C",
            "LANG": "C",
            "CONFIG_SHELL": "/bin/sh",
            "ARFLAGS": "crD",
            **SANITIZED_ENVIRONMENT,
        }
        cppflags = self.expand_args(recipe.cppflags, context)
        if kind == "host":
            env.update(
                {
                    "CC": str(self.llvm_bin / "clang"),
                    "CXX": str(self.llvm_bin / "clang++"),
                    "AR": str(self.llvm_bin / "llvm-ar"),
                    "RANLIB": str(self.llvm_bin / "llvm-ranlib"),
                    "NM": str(self.llvm_bin / "llvm-nm"),
                    "STRIP": str(self.llvm_bin / "llvm-strip"),
                    "PKG_CONFIG_PATH": f"{self.host / 'lib/pkgconfig'}:{self.host / 'share/pkgconfig'}",
                    "CPPFLAGS": " ".join([f"-I{self.host / 'include'}", *cppflags]),
                    "LDFLAGS": " ".join([f"-L{self.host / 'lib'}", f"-Wl,-rpath,{self.host / 'lib'}", *HOST_LINK_FLAGS]),
                    "CFLAGS": join_flags(HOST_C_COMPILE_FLAGS),
                    "CXXFLAGS": join_flags(HOST_CXX_COMPILE_FLAGS),
                }
            )
        else:
            target_bin = self.toolchain / "bin"
            host_cc = str(self.llvm_bin / "clang")
            host_cxx = str(self.llvm_bin / "clang++")
            env.update(
                {
                    "CC": str(target_bin / f"{self.triple}-cc"),
                    "CXX": str(target_bin / f"{self.triple}-c++"),
                    "AR": str(target_bin / f"{self.triple}-ar"),
                    "RANLIB": str(target_bin / f"{self.triple}-ranlib"),
                    "NM": str(target_bin / f"{self.triple}-nm"),
                    "STRIP": str(target_bin / f"{self.triple}-strip"),
                    "OBJCOPY": str(target_bin / f"{self.triple}-objcopy"),
                    "READELF": str(target_bin / f"{self.triple}-readelf"),
                    "LD": str(target_bin / f"{self.triple}-ld"),
                    "CC_FOR_BUILD": host_cc,
                    "CXX_FOR_BUILD": host_cxx,
                    "BUILD_CC": host_cc,
                    "BUILD_CXX": host_cxx,
                    "HOSTCC": host_cc,
                    "HOSTCXX": host_cxx,
                    "PKG_CONFIG": str(self.host_bin / "pkgconf"),
                    "PKG_CONFIG_SYSROOT_DIR": str(self.sysroot),
                    "PKG_CONFIG_LIBDIR": ":".join(
                        str(path)
                        for path in (
                            self.sysroot / "usr/lib/pkgconfig",
                            self.sysroot / "usr/share/pkgconfig",
                            self.sysroot / "lib/pkgconfig",
                        )
                    ),
                    "PKG_CONFIG_ALLOW_SYSTEM_CFLAGS": "0",
                    "PKG_CONFIG_ALLOW_SYSTEM_LIBS": "0",
                    "CONFIG_SITE": str(self.output / "generated/config.site"),
                    "CPPFLAGS": " ".join(cppflags),
                    "CFLAGS": join_flags(target_c_compile_flags(self.arch, lto=self.recipe_lto(recipe))),
                    "CXXFLAGS": join_flags((*target_cxx_compile_flags(self.arch, lto=self.recipe_lto(recipe)), *target_cxx_header_flags(self.sysroot))),
                    "LDFLAGS": join_flags(target_link_flags(self.arch, lto=self.recipe_lto(recipe))),
                }
            )
        for assignment in recipe.environment:
            name, value = assignment.split("=", 1)
            env[name] = value.format(**context)
        return env

    def recipe_fingerprint(self, recipe: Recipe, source: Path | None) -> str:
        digest = hashlib.sha256()
        digest.update(b"package-fingerprint-v2\0")
        digest.update(recipe.path.read_bytes())
        for patch in recipe.patches:
            digest.update(recipe.patch_path(patch).read_bytes())
        if recipe.build_system == "local":
            for local_input in sorted(
                path for path in recipe.path.parent.rglob("*")
                if path.is_file() and path != recipe.path
            ):
                digest.update(str(local_input.relative_to(recipe.path.parent)).encode())
                digest.update(b"\0")
                digest.update(local_input.read_bytes())
        digest.update((ROOT / "scripts/package_builder.py").read_bytes())
        digest.update((ROOT / "scripts/build_policy.py").read_bytes())
        if recipe.special == "busybox":
            digest.update(recipe.config_path("busybox.fragment").read_bytes())
        digest.update(self.arch.encode())
        digest.update((self.toolchain / ".complete").read_bytes())
        if source is not None:
            marker = source / ".strata-extracted" if source.is_dir() else source
            if marker.is_file():
                digest.update(marker.read_bytes())
        for dep in recipe.dependencies:
            stamp = self.package_stamp(self.recipes[dep])
            if stamp.exists():
                digest.update(stamp.read_bytes())
        return digest.hexdigest() + "\n"

    def package_stamp(self, recipe: Recipe) -> Path:
        if recipe.kind == "host":
            return self.output / "stamps" / f"{recipe.name}.complete"
        return self.package_root / recipe.name / ".complete"

    def package_destdir(self, recipe: Recipe) -> Path:
        if recipe.kind == "host":
            return self.host
        return self.package_root / recipe.name / "root"

    def preflight(self, requested: Iterable[str]) -> list[str]:
        order = topological_order(self.recipes, requested)
        selected_recipes = {name: self.recipes[name] for name in order}
        audit_static_recipes(selected_recipes)
        sources = {name: self.source_for(self.recipes[name]) for name in order}
        entries = audit_source_recipes(selected_recipes, sources)
        write_audit_report(
            self.output / "reports/build-parameter-audit.json",
            self.arch,
            entries,
            "source-aware",
        )
        log(f"source-aware build parameter audit passed for {len(order)} packages")
        return order

    def build(self, requested: Iterable[str], *, preflight: bool = True, resume: bool = False) -> None:
        order = self.preflight(requested) if preflight else topological_order(self.recipes, requested)
        completed: list[str] = []
        self.write_build_state(order, completed, "building", None, resume)
        for name in order:
            self.write_build_state(order, completed, "building", name, resume)
            try:
                self.build_one(self.recipes[name], resume=resume)
            except Exception:
                self.write_build_state(order, completed, "failed", name, resume)
                raise
            completed.append(name)
        self.write_build_state(order, completed, "complete", None, resume)

    def write_build_state(
        self, order: list[str], completed: list[str], status: str,
        current: str | None, resume: bool,
    ) -> None:
        path = self.output / "reports/package-build-state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(path, json.dumps({
            "format": 1,
            "requested": order,
            "completed": completed,
            "status": status,
            "current": current,
            "resume": resume,
        }, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def _check_configure_output(recipe: Recipe, text: str, build_system: str) -> None:
        lowered = text.lower()
        if build_system == "autotools" and "unrecognized options" in lowered:
            raise BuildError(f"{recipe.name}: configure rejected one or more declared options")
        if build_system == "cmake" and "manually-specified variables were not used by the project" in lowered:
            marker = "Manually-specified variables were not used by the project:"
            tail = text.split(marker, 1)[1]
            ignored: list[str] = []
            for raw in tail.splitlines():
                line = raw.strip()
                if not line:
                    if ignored:
                        break
                    continue
                if line.startswith("--") or line.startswith("CMake Warning"):
                    if ignored:
                        break
                    continue
                if re.fullmatch(r"[A-Za-z0-9_]+", line):
                    ignored.append(line)
                elif ignored:
                    break
            detail = ", ".join(ignored) if ignored else "unknown variables"
            raise BuildError(f"{recipe.name}: CMake ignored manually specified variables: {detail}")
    def audit_generated_build_plan(
        self, recipe: Recipe, build: Path, env: dict[str, str]
    ) -> None:
        if recipe.kind != "target":
            return
        metadata_candidates = [
            build / "CMakeCache.txt", build / "config.status",
            build / "meson-info/intro-buildoptions.json",
        ]
        command_candidates = [build / "Makefile", build / "build.ninja"]
        command_candidates.extend(build.rglob("*.ninja"))
        command_candidates.extend(build.rglob("link.txt"))
        metadata_parts: list[str] = []
        command_parts: list[str] = []
        checked: list[str] = []
        seen: set[Path] = set()
        for path in [*metadata_candidates, *command_candidates]:
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            checked.append(str(path))
            content = path.read_text(errors="replace")
            if path in metadata_candidates:
                metadata_parts.append(content)
            else:
                command_parts.append(content)
        if not command_parts:
            raise BuildError(f"{recipe.name}: configure generated no auditable build commands")
        all_text = "\n".join([*metadata_parts, *command_parts])
        command_text = "\n".join(command_parts)
        requires_compiler = True
        meson_targets = build / "meson-info/intro-targets.json"
        if meson_targets.is_file():
            targets = json.loads(meson_targets.read_text())
            languages = {
                source.get("language", "unknown")
                for target in targets
                for source in target.get("target_sources", [])
            }
            # Data-only Meson projects legitimately contain only custom
            # generators (for example xkeyboard-config's rules compiler).
            requires_compiler = bool(languages - {"unknown"})
        if requires_compiler and env["CC"] not in all_text and Path(env["CC"]).name not in all_text:
            raise BuildError(f"{recipe.name}: generated build plan does not reference target compiler")
        forbidden_patterns = {
            "host linker": r"(?:^|[\s=\"'])/(?:usr/)?bin/ld(?:[\s\"']|$)",
            "host GCC compiler": r"(?:^|[\s=\"'])/(?:usr/)?bin/(?:gcc|g\+\+)(?:[\s\"']|$)",
            "GCC runtime": r"(?:^|\s)-l(?:gcc|gcc_s|stdc\+\+|atomic)(?:\s|$)",
            "host multiarch library": r"/(?:usr/)?lib/(?:x86_64-linux-gnu|aarch64-linux-gnu)",
        }
        found = [name for name, pattern in forbidden_patterns.items() if re.search(pattern, command_text, re.M)]
        if found:
            raise BuildError(f"{recipe.name}: generated build plan leaks " + ", ".join(found))
        report = self.output / "reports/generated-build-plans" / f"{recipe.name}.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({
            "format": 1, "name": recipe.name, "build_system": recipe.build_system,
            "compiler": env["CC"] if requires_compiler else None,
            "files": checked, "status": "ok" if requires_compiler else "data-only-ok",
        }, indent=2, sort_keys=True) + "\n")

    def write_effective_parameters(
        self, recipe: Recipe, source: Path | None, env: dict[str, str], context: dict[str, str]
    ) -> None:
        keys = (
            "CC", "CXX", "AR", "RANLIB", "NM", "STRIP", "LD",
            "CC_FOR_BUILD", "CXX_FOR_BUILD", "BUILD_CC", "BUILD_CXX",
            "CPPFLAGS", "CFLAGS", "CXXFLAGS", "LDFLAGS",
            "PKG_CONFIG", "PKG_CONFIG_SYSROOT_DIR", "PKG_CONFIG_LIBDIR", "CONFIG_SITE",
            *(assignment.split("=", 1)[0] for assignment in recipe.environment),
        )
        report = {
            "format": 1,
            "name": recipe.name,
            "version": recipe.version,
            "kind": recipe.kind,
            "build_system": recipe.build_system,
            "special": recipe.special,
            "source": str(source or ""),
            "dependencies": list(recipe.dependencies),
            "configure_args": self.expand_args(recipe.configure_args, context),
            "build_args": self.expand_args(recipe.build_args, context),
            "install_args": self.expand_args(recipe.install_args, context),
            "environment": {key: env[key] for key in keys if key in env},
            "parallel_jobs": self.parallel,
        }
        path = self.output / "reports/effective-build-parameters" / f"{recipe.name}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")

    def prepare_build_directory(self, build: Path, expected: str, resume: bool) -> bool:
        marker = build.parent / ".strata-build-fingerprint"
        reusable = resume and build.is_dir() and marker.is_file() and marker.read_text() == expected
        if not reusable:
            shutil.rmtree(build.parent, ignore_errors=True)
        build.mkdir(parents=True, exist_ok=True)
        atomic_write(marker, expected)
        return reusable

    def build_one(self, recipe: Recipe, *, resume: bool = False) -> None:
        if recipe.build_system == "kernel":
            raise BuildError(f"{recipe.name}: use the dedicated make kernel stage")
        source = self.source_for(recipe)
        stamp = self.package_stamp(recipe)
        expected = self.recipe_fingerprint(recipe, source)
        if stamp.exists() and stamp.read_text() == expected:
            root = self.package_destdir(recipe)
            if recipe.name != "llvm-runtime" or has_llvm_runtime_libraries(root):
                log(f"package cached: {recipe.name}")
                return
            log("llvm-runtime cache is missing C++ runtime libraries; rebuilding")
        build = self.work_root / recipe.name / "build"
        package_dir = self.package_root / recipe.name
        root = self.package_destdir(recipe)
        if recipe.kind == "target":
            self.remove_from_sysroot(root)
            shutil.rmtree(package_dir, ignore_errors=True)
            root.mkdir(parents=True, exist_ok=True)
        if self.prepare_build_directory(build, expected, resume):
            log(f"resuming package work: {recipe.name}")
        context = self.context(recipe, source, build, root)
        env = self.base_env(recipe.kind, recipe, context)
        context.update({
            "cc": env["CC"], "cxx": env.get("CXX", env["CC"]), "ar": env["AR"],
            "ranlib": env["RANLIB"], "nm": env["NM"], "strip": env["STRIP"],
            "build_cc": env.get("BUILD_CC", context["host_cc"]),
            "hostcc": env.get("HOSTCC", context["host_cc"]),
            "cflags": env.get("CFLAGS", ""), "ldflags": env.get("LDFLAGS", ""),
            "install_prefix": str(self.host if recipe.kind == "host" else Path("/usr")),
            "openssl_target": "linux-x86_64" if self.arch == "x86_64" else "linux-aarch64",
        })
        self.write_effective_parameters(recipe, source, env, context)
        log(f"building {recipe.kind} package {recipe.name}-{recipe.version}")
        if recipe.build_system == "autotools":
            self.build_autotools(recipe, source, build, root, env, context)
        elif recipe.build_system == "cmake":
            self.build_cmake(recipe, source, build, root, env, context)
        elif recipe.build_system == "meson":
            self.build_meson(recipe, source, build, root, env, context)
        elif recipe.build_system == "local":
            self.build_local(recipe, source, build, root, env, context)
        else:
            self.build_special(recipe, source, build, root, env, context)
        if recipe.kind == "target":
            self.normalize_target_root(root)
            audit_elf_tree(root, self.llvm_bin / "llvm-readelf", self.arch, self.sysroot)
            self.merge_into_sysroot(root)
            metadata = package_dir / "package.env"
            atomic_write(
                metadata,
                f"name={recipe.name}\nversion={recipe.version}\n"
                f"source={recipe.source_for_arch(self.arch).url if recipe.source else ''}\n",
            )
        stamp.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(stamp, expected)

    def build_autotools(
        self, recipe: Recipe, source: Path | None, build: Path, root: Path,
        env: dict[str, str], context: dict[str, str]
    ) -> None:
        if source is None or not source.is_dir():
            raise BuildError(f"{recipe.name}: autotools source directory is missing")
        configure = source / "configure"
        if not configure.exists():
            raise BuildError(f"{recipe.name}: release archive has no configure script")
        prefix = str(self.host) if recipe.kind == "host" else "/usr"
        command = [str(configure), f"--prefix={prefix}"]
        if recipe.kind == "target":
            command += [f"--host={self.triple}", f"--build={build_triplet()}"]
        command += self.expand_args(recipe.configure_args, context)
        completed = run(command, cwd=build, env=env, capture=True)
        self._check_configure_output(recipe, completed.stdout or "", "autotools")
        self.audit_generated_build_plan(recipe, build, env)
        run(["make", f"-j{self.parallel}", *self.expand_args(recipe.build_args, context)], cwd=build, env=env)
        if recipe.kind == "host":
            run(["make", "install", *self.expand_args(recipe.install_args, context)], cwd=build, env=env)
        else:
            run(["make", f"DESTDIR={root}", "INSTALL_OWNER=", "install", *self.expand_args(recipe.install_args, context)], cwd=build, env=env)

    def build_cmake(
        self, recipe: Recipe, source: Path | None, build: Path, root: Path,
        env: dict[str, str], context: dict[str, str]
    ) -> None:
        if source is None or not source.is_dir():
            raise BuildError(f"{recipe.name}: CMake source directory is missing")
        command = [
            str(self.cmake_bin / "cmake"), "-S", str(source), "-B", str(build),
            "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
        ]
        if recipe.kind == "host":
            command += [
                f"-DCMAKE_INSTALL_PREFIX={self.host}",
                f"-DCMAKE_C_COMPILER={self.llvm_bin / 'clang'}",
                f"-DCMAKE_AR={self.llvm_bin / 'llvm-ar'}",
                f"-DCMAKE_RANLIB={self.llvm_bin / 'llvm-ranlib'}",
                f"-DCMAKE_NM={self.llvm_bin / 'llvm-nm'}",
                f"-DCMAKE_LINKER={self.llvm_bin / 'ld.lld'}",
                f"-DCMAKE_C_FLAGS_INIT={join_flags(HOST_C_COMPILE_FLAGS)}",
                f"-DCMAKE_EXE_LINKER_FLAGS_INIT={join_flags(HOST_LINK_FLAGS)}",
                f"-DCMAKE_SHARED_LINKER_FLAGS_INIT={join_flags(HOST_LINK_FLAGS)}",
                f"-DCMAKE_MODULE_LINKER_FLAGS_INIT={join_flags(HOST_LINK_FLAGS)}",
            ]
        else:
            command += [
                f"-DCMAKE_TOOLCHAIN_FILE={self.output / 'generated/cmake-toolchain.cmake'}",
                "-DCMAKE_INSTALL_PREFIX=/usr",
            ]
            lto = self.recipe_lto(recipe)
            if lto is not None:
                cxx_flags = (*target_cxx_compile_flags(self.arch, lto=lto), *target_cxx_header_flags(self.sysroot))
                link_flags = target_link_flags(self.arch, lto=lto)
                command += [
                    f"-DCMAKE_C_FLAGS={join_flags(target_c_compile_flags(self.arch, lto=lto))}",
                    f"-DCMAKE_CXX_FLAGS={join_flags(cxx_flags)}",
                    f"-DCMAKE_EXE_LINKER_FLAGS={join_flags(link_flags)}",
                    f"-DCMAKE_SHARED_LINKER_FLAGS={join_flags(link_flags)}",
                    f"-DCMAKE_MODULE_LINKER_FLAGS={join_flags(link_flags)}",
                ]
        command += self.expand_args(recipe.configure_args, context)
        completed = run(command, env=env, capture=True)
        self._check_configure_output(recipe, completed.stdout or "", "cmake")
        self.audit_generated_build_plan(recipe, build, env)
        run([str(self.cmake_bin / "cmake"), "--build", str(build), "--parallel", str(self.parallel), *self.expand_args(recipe.build_args, context)], env=env)
        install_env = env.copy()
        if recipe.kind == "target":
            install_env["DESTDIR"] = str(root)
        run([str(self.cmake_bin / "cmake"), "--install", str(build), *self.expand_args(recipe.install_args, context)], env=install_env)

    def build_meson(
        self, recipe: Recipe, source: Path | None, build: Path, root: Path,
        env: dict[str, str], context: dict[str, str]
    ) -> None:
        if source is None or not source.is_dir():
            raise BuildError(f"{recipe.name}: Meson source directory is missing")
        command = [
            str(self.host_bin / "meson"), "setup", str(build), str(source),
            "--buildtype=release", "--wrap-mode=nodownload",
        ]
        if recipe.kind == "host":
            command += [f"--prefix={self.host}", "--libdir=lib"]
        else:
            command += [
                *[f"--cross-file={path}" for path in self.recipe_meson_cross_files(recipe)],
                f"--native-file={self.output / 'generated/meson-native.ini'}",
                "--prefix=/usr", "--libdir=lib",
            ]
        command += self.expand_args(recipe.configure_args, context)
        completed = run(command, env=env, capture=True)
        if "unknown options" in (completed.stdout or "").lower():
            raise BuildError(f"{recipe.name}: Meson rejected one or more declared options")
        self.audit_generated_build_plan(recipe, build, env)
        run([str(self.host_bin / "ninja"), "-C", str(build), f"-j{self.parallel}", *self.expand_args(recipe.build_args, context)], env=env)
        install_env = env.copy()
        if recipe.kind == "target":
            install_env["DESTDIR"] = str(root)
        run([str(self.host_bin / "ninja"), "-C", str(build), "-j1", "install", *self.expand_args(recipe.install_args, context)], env=install_env)

    def build_special(
        self, recipe: Recipe, source: Path | None, build: Path, root: Path,
        env: dict[str, str], context: dict[str, str]
    ) -> None:
        handlers = {
            "musl-runtime": self.special_musl_runtime,
            "llvm-runtime": self.special_llvm_runtime,
            "ninja": self.special_ninja,
            "zstd": self.special_zstd,
            "squashfs-tools": self.special_squashfs,
            "bzip2": self.special_bzip2,
            "libcap": self.special_libcap,
            "openssl": self.special_openssl,
            "ca-certificates": self.special_ca_certificates,
            "font-file": self.special_font_file,
            "argon2": self.special_argon2,
            "busybox": self.special_busybox,
            "lvm2": self.special_lvm2,
            "mdadm": self.special_mdadm,
            "iproute2": self.special_iproute2,
            "dhcpcd": self.special_dhcpcd,
            "docker-static": self.special_docker,
            "fail2ban": self.special_fail2ban,
            "host-python-module": self.special_host_python_module,
        }
        handler = handlers.get(recipe.special or "")
        if handler is None:
            raise BuildError(f"{recipe.name}: unknown special handler {recipe.special}")
        handler(recipe, source, build, root, env, context)

    def special_host_python_module(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if recipe.kind != "host" or source is None or not source.is_dir():
            raise BuildError(f"{recipe.name}: host Python module source is missing")
        module_name = env.get("PYTHON_MODULE", recipe.name.removeprefix("host-").replace("-", "_"))
        source_relative = env.get("PYTHON_SOURCE", module_name)
        relative_path = Path(source_relative)
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", module_name):
            raise BuildError(f"{recipe.name}: invalid Python module name {module_name}")
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise BuildError(f"{recipe.name}: invalid Python module source path {source_relative}")
        module_source = source / relative_path
        if not module_source.is_dir():
            raise BuildError(f"{recipe.name}: source archive misses Python module {source_relative}")
        site_packages = self.host / "lib/python3.13/site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        destination = site_packages / module_name
        shutil.rmtree(destination, ignore_errors=True)
        shutil.copytree(
            module_source, destination,
            ignore=shutil.ignore_patterns("tests", "*.pyc", "__pycache__"),
        )
        run([str(self.host_bin / "python3"), "-c", f"import {module_name}"], env=env)

    def special_fail2ban(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("fail2ban source is missing")
        python_lib = root / "usr/lib/python3.13/site-packages"
        shutil.copytree(
            source / "fail2ban", python_lib / "fail2ban",
            ignore=shutil.ignore_patterns("tests", "*.pyc", "__pycache__"),
        )
        for name in ("fail2ban-client", "fail2ban-server", "fail2ban-regex"):
            script = (source / "bin" / name).read_text()
            script = re.sub(r"^#!.*$", "#!/usr/bin/python3", script, count=1, flags=re.M)
            atomic_write(root / "usr/bin" / name, script, 0o755)
        shutil.copytree(source / "config", root / "etc/fail2ban")
        for directory in ("fail2ban.d", "jail.d"):
            (root / "etc/fail2ban" / directory).mkdir(parents=True, exist_ok=True)

    def special_musl_runtime(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        for relative in ("lib", "usr/lib"):
            origin = self.sysroot / relative
            if not origin.exists():
                continue
            for item in origin.glob("libc.so"):
                self.copy_entry(item, root / relative / item.name)
            for pattern in ("ld-musl-*.so.1", "libc.so", "libm.so", "libm.a", "libpthread.a", "librt.a", "libdl.a"):
                for item in origin.glob(pattern):
                    self.copy_entry(item, root / relative / item.name)

    def special_llvm_runtime(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        for pattern in ("libc++.so*", "libunwind.so*", "libclang_rt.builtins*.so*", "libclang_rt.builtins*.a"):
            for item in sorted(self.sysroot.rglob(pattern)):
                relative = item.relative_to(self.sysroot)
                self.copy_entry(item, root / relative)


    def special_ninja(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("ninja source is missing")
        completed = run(
            [str(self.cmake_bin / "cmake"), "-S", str(source), "-B", str(build),
             "-G", "Unix Makefiles", *self.expand_args(recipe.configure_args, context)],
            env=env, capture=True,
        )
        self._check_configure_output(recipe, completed.stdout or "", "cmake")
        run([str(self.cmake_bin / "cmake"), "--build", str(build), "--parallel", str(self.parallel), *self.expand_args(recipe.build_args, context)], env=env)
        shutil.copy2(build / "ninja", self.host_bin / "ninja")
        (self.host_bin / "ninja").chmod(0o755)

    def special_zstd(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("zstd source is missing")
        args = [
            "make", "-C", str(source), f"-j{self.parallel}",
            f"CC={env['CC']}", f"AR={env['AR']}", f"RANLIB={env['RANLIB']}",
            f"CFLAGS={env['CFLAGS']}",
            *self.expand_args(recipe.build_args, context),
        ]
        run(args, env=env)
        install = [
            "make", "-C", str(source), "install",
            *self.expand_args(recipe.install_args, context),
        ]
        if recipe.kind == "target":
            install.append(f"DESTDIR={root}")
        run(install, env=env)

    def special_squashfs(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("squashfs-tools source is missing")
        directory = source / "squashfs-tools"
        custom = env | {
            "CFLAGS": f"{join_flags(HOST_C_COMPILE_FLAGS)} -I{self.host / 'include'}",
            "LDFLAGS": f"{join_flags(HOST_LINK_FLAGS)} -L{self.host / 'lib'} -Wl,-rpath,{self.host / 'lib'}",
        }
        flags = self.expand_args(recipe.build_args, context)
        run(["make", f"-j{self.parallel}", *flags], cwd=directory, env=custom)
        for name in ("mksquashfs", "unsquashfs"):
            shutil.copy2(directory / name, self.host_bin / name)
            (self.host_bin / name).chmod(0o755)

    def special_bzip2(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("bzip2 source is missing")
        run(["make", "clean"], cwd=source, env=env)
        run([
            "make", f"-j{self.parallel}", f"CC={env['CC']}", f"AR={env['AR']}",
            f"RANLIB={env['RANLIB']}", f"CFLAGS={env['CFLAGS']}", f"LDFLAGS={env['LDFLAGS']}",
            *self.expand_args(recipe.build_args, context),
        ], cwd=source, env=env)
        run([
            "make", "-f", "Makefile-libbz2_so", f"CC={env['CC']}",
            f"CFLAGS={env['CFLAGS']}", f"LDFLAGS={env['LDFLAGS']}",
        ], cwd=source, env=env)
        prefix = root / "usr"
        (prefix / "bin").mkdir(parents=True, exist_ok=True)
        (prefix / "lib").mkdir(parents=True, exist_ok=True)
        (prefix / "include").mkdir(parents=True, exist_ok=True)
        for name in ("bzip2", "bzip2recover"):
            shutil.copy2(source / name, prefix / "bin" / name)
        shutil.copy2(source / "bzlib.h", prefix / "include/bzlib.h")
        shutil.copy2(source / "libbz2.a", prefix / "lib/libbz2.a")
        shared = next(source.glob("libbz2.so.*"))
        shutil.copy2(shared, prefix / "lib" / shared.name)
        # Create SONAME symlink: the ELF embeds NEEDED libbz2.so.1.0
        # but the file is libbz2.so.1.0.8.
        soname = "libbz2.so.1.0"
        if not (prefix / "lib" / soname).exists():
           (prefix / "lib" / soname).symlink_to(shared.name)
        (prefix / "lib/libbz2.so.1").symlink_to(shared.name)
        (prefix / "lib/libbz2.so").symlink_to("libbz2.so.1")

    def special_libcap(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("libcap source is missing")
        args = [
            "make", f"-j{self.parallel}", f"CC={env['CC']}", f"AR={env['AR']}",
            f"RANLIB={env['RANLIB']}", f"BUILD_CC={env['BUILD_CC']}",
            f"CFLAGS={env['CFLAGS']}", f"LDFLAGS={env['LDFLAGS']}",
            *self.expand_args(recipe.build_args, context),
        ]
        run(args, cwd=source, env=env)
        run(["make", f"DESTDIR={root}", f"BUILD_CC={env['BUILD_CC']}", *self.expand_args(recipe.install_args, context), "install"], cwd=source, env=env)

    def special_openssl(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("OpenSSL source is missing")
        command = [
            str(source / "Configure"), *self.expand_args(recipe.configure_args, context),
        ]
        run(command, cwd=build, env=env)
        run(["make", f"-j{self.parallel}"], cwd=build, env=env)
        run(["make", f"DESTDIR={root}", *self.expand_args(recipe.install_args, context)], cwd=build, env=env)

    def special_ca_certificates(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_file():
            raise BuildError("CA certificate bundle is missing")
        destination = root / "etc/ssl/certs/ca-certificates.crt"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        link = root / "etc/ssl/cert.pem"
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to("certs/ca-certificates.crt")

    def special_font_file(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_file() or source.suffix.lower() not in {".otf", ".ttf", ".ttc"}:
            raise BuildError("font-file source must be an OTF, TTF or TTC file")
        destination = root / "usr/share/fonts/strataos" / source.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def special_argon2(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("argon2 source is missing")
        run([
            "make", f"-j{self.parallel}", f"CC={env['CC']}", f"AR={env['AR']}",
            f"CFLAGS={env['CFLAGS']} -Iinclude -Isrc", f"LDFLAGS={env['LDFLAGS']}",
            *self.expand_args(recipe.build_args, context),
        ], cwd=source, env=env)
        run(["make", f"DESTDIR={root}", *self.expand_args(recipe.install_args, context), "install"], cwd=source, env=env)

    def special_busybox(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("BusyBox source is missing")
        run(["make", f"O={build}", "allnoconfig"], cwd=source, env=env)
        fragment = recipe.config_path("busybox.fragment")
        requested = apply_kconfig_fragment(build / ".config", fragment)
        run(["make", f"O={build}", "oldconfig"], cwd=source, env=env)
        verify_kconfig_fragment(build / ".config", requested)
        run(["make", f"O={build}", f"-j{self.parallel}", f"CC={env['CC']}", f"AR={env['AR']}", f"RANLIB={env['RANLIB']}", f"NM={env['NM']}", f"STRIP={env['STRIP']}", f"HOSTCC={env['HOSTCC']}"], cwd=source, env=env)
        run(["make", f"O={build}", f"CC={env['CC']}", f"HOSTCC={env['HOSTCC']}", f"CONFIG_PREFIX={root}", *self.expand_args(recipe.install_args, context), "install"], cwd=source, env=env)

        # BusyBox CONFIG_TEST=y builds the test applet but make install may
        # skip the [ symlink. Create it explicitly so ash scripts can use [.
        bracket = root / "usr/bin/["
        if not bracket.exists():
            bracket.symlink_to("../../bin/busybox")

    def special_lvm2(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("LVM2 source is missing")
        configure = source / "configure"
        run([str(configure), f"--host={self.triple}", f"--build={build_triplet()}", *self.expand_args(recipe.configure_args, context)], cwd=build, env=env)
        run(["make", f"-j{self.parallel}", *self.expand_args(recipe.build_args, context)], cwd=build, env=env)
        run(["make", f"DESTDIR={root}", *self.expand_args(recipe.install_args, context)], cwd=build, env=env)

    def special_mdadm(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("mdadm source is missing")
        run([
            "make", f"-j{self.parallel}", f"CC={env['CC']}",
            f"CXFLAGS={env['CFLAGS']} {' '.join(self.expand_args(recipe.build_args, context))}",
            f"LDFLAGS={env['LDFLAGS']}",
        ], cwd=source, env=env)
        run(["make", f"DESTDIR={root}", *self.expand_args(recipe.install_args, context), "install"], cwd=source, env=env)

    def special_iproute2(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("iproute2 source is missing")
        config_mk = source / "config.mk"
        config_mk.write_text(
            f"CC:={env['CC']}\nAR:={env['AR']}\nPKG_CONFIG:={env['PKG_CONFIG']}\n"
            + "\n".join(self.expand_args(recipe.configure_args, context)) + "\n"
        )
        run(["make", f"-j{self.parallel}", *self.expand_args(recipe.build_args, context)], cwd=source, env=env)
        run(["make", f"DESTDIR={root}", *self.expand_args(recipe.install_args, context), "install"], cwd=source, env=env)

    def special_dhcpcd(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("dhcpcd source is missing")
        run([str(source / "configure"), f"--host={self.triple}", *self.expand_args(recipe.configure_args, context)], cwd=source, env=env)
        run(["make", f"-j{self.parallel}", *self.expand_args(recipe.build_args, context)], cwd=source, env=env)
        run(["make", f"DESTDIR={root}", *self.expand_args(recipe.install_args, context), "install"], cwd=source, env=env)


    def special_docker(self, recipe: Recipe, source: Path | None, build: Path, root: Path, env: dict[str, str], context: dict[str, str]) -> None:
        if source is None or not source.is_dir():
            raise BuildError("Docker static archive is missing")
        bindir = root / "usr/bin"
        bindir.mkdir(parents=True, exist_ok=True)
        candidates = list(source.iterdir())
        if len(candidates) == 1 and candidates[0].is_dir():
            candidates = list(candidates[0].iterdir())
        for item in candidates:
            if item.is_file():
                shutil.copy2(item, bindir / item.name)
                (bindir / item.name).chmod(0o755)
        missing = [name for name in ("docker", "dockerd", "containerd", "runc") if not (bindir / name).exists()]
        if missing:
            raise BuildError("Docker archive misses: " + ", ".join(missing))

    def build_local(
        self, recipe: Recipe, source: Path | None, build: Path, root: Path,
        env: dict[str, str], context: dict[str, str]
    ) -> None:
        for phase, commands in (
            ("build", recipe.build_args),
            ("test", recipe.test_args),
            ("install", recipe.install_args),
        ):
            if not commands:
                raise BuildError(f"{recipe.name}: local recipe has no {phase} command")
            local_env = env | {
                "STRATA_BUILD_DIR": str(build),
                "STRATA_DESTDIR": str(root),
                "STRATA_PHASE": phase,
            }
            for command in self.expand_args(commands, context):
                run(["/bin/sh", "-ec", command], cwd=recipe.directory, env=local_env)

    def run_build_system_probes(self) -> None:
        probe = self.output / "probes/build-systems"
        shutil.rmtree(probe, ignore_errors=True)
        probe.mkdir(parents=True)
        env = self.base_env("target", self.recipes["zlib"], self.context(
            self.recipes["zlib"], None, probe, probe / "root"
        ))
        c_source = probe / "probe.c"
        cxx_source = probe / "probe.cpp"
        c_source.write_text(
            "#include <pthread.h>\n#include <stdatomic.h>\n"
            "static void *worker(void *p) { return p; }\n"
            "int main(void) { pthread_t t; atomic_int x = 0; "
            "return pthread_create(&t, 0, worker, 0) || atomic_load(&x); }\n"
        )
        cxx_source.write_text(
            "#include <atomic>\n#include <filesystem>\n#include <locale>\n#include <thread>\n"
            "int main() { std::atomic<int> x{0}; std::thread t([&]{++x;}); t.join(); "
            "return std::filesystem::path(\"/\").empty() || x.load() != 1 || std::locale::classic().name().empty(); }\n"
        )
        run([env["CC"], str(c_source), "-pthread", "-o", str(probe / "c-probe")], env=env)
        run([env["CXX"], str(cxx_source), "-pthread", "-o", str(probe / "cxx-probe")], env=env)
        run([env["CC"], "-shared", str(c_source), "-pthread", "-o", str(probe / "libc-probe.so")], env=env)
        run([env["CXX"], "-shared", str(cxx_source), "-pthread", "-o", str(probe / "libcxx-probe.so")], env=env)

        cmake_source = probe / "cmake-src"
        cmake_build = probe / "cmake-build"
        cmake_source.mkdir()
        (cmake_source / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.20)\n"
            "project(strata_probe LANGUAGES C CXX)\n"
            "find_package(Threads REQUIRED)\n"
            "add_executable(c_probe ../probe.c)\n"
            "target_link_libraries(c_probe PRIVATE Threads::Threads)\n"
            "add_library(cxx_probe SHARED ../probe.cpp)\n"
            "target_link_libraries(cxx_probe PRIVATE Threads::Threads)\n"
        )
        probe_configured = run([
            str(self.cmake_bin / "cmake"), "-S", str(cmake_source), "-B", str(cmake_build),
            "-G", "Ninja", f"-DCMAKE_TOOLCHAIN_FILE={self.output / 'generated/cmake-toolchain.cmake'}",
        ], env=env, capture=True)
        self._check_configure_output(self.recipes["zlib"], probe_configured.stdout or "", "cmake")
        run([str(self.cmake_bin / "cmake"), "--build", str(cmake_build), "--parallel", str(self.parallel)], env=env)

        meson_source = probe / "meson-src"
        meson_build = probe / "meson-build"
        meson_source.mkdir()
        (meson_source / "meson.build").write_text(
            "project('strata-probe', ['c', 'cpp'])\n"
            "threads = dependency('threads')\n"
            "executable('c-probe', '../probe.c', dependencies: threads)\n"
            "shared_library('cxx-probe', '../probe.cpp', dependencies: threads)\n"
        )
        run([
            str(self.host_bin / "meson"), "setup", str(meson_build), str(meson_source),
            f"--cross-file={self.output / 'generated/meson-cross.ini'}",
            f"--native-file={self.output / 'generated/meson-native.ini'}",
            "--wrap-mode=nodownload",
        ], env=env)
        run([str(self.host_bin / "ninja"), "-C", str(meson_build), f"-j{self.parallel}"], env=env)
        audited = probe / "target-artifacts"
        audited.mkdir()
        for artifact in (
            probe / "c-probe", probe / "cxx-probe", probe / "libc-probe.so", probe / "libcxx-probe.so",
            cmake_build / "c_probe", cmake_build / "libcxx_probe.so",
            meson_build / "c-probe", meson_build / "libcxx-probe.so",
        ):
            shutil.copy2(artifact, audited / artifact.name)
        audit_elf_tree(audited, self.llvm_bin / "llvm-readelf", self.arch, self.sysroot)
        log("compiler, CMake and Meson target probes passed")

    def copy_entry(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            destination.unlink(missing_ok=True)
            destination.symlink_to(os.readlink(source))
        elif source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)

    def normalize_target_root(self, root: Path) -> None:
        for path in sorted(root.rglob("*"), reverse=True):
            rel = path.relative_to(root).as_posix()
            if any(rel.startswith(prefix) for prefix in ("usr/share/doc/", "usr/share/info/", "usr/share/man/")):
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)
            elif path.is_file() and path.suffix == ".la":
                path.unlink()

    def remove_from_sysroot(self, root: Path) -> None:
        if not root.exists():
            return
        # Core musl runtime files are owned by the toolchain, not by
        # individual packages.  Removing them from the sysroot breaks
        # every subsequent link step (e.g. -lm, -lc, -lrt, -lpthread).
        _PROTECTED_SYSROOT_FILES = {
            Path("usr/lib/libc.so"),
            Path("usr/lib/libm.so"),
            Path("usr/lib/libm.a"),
            Path("usr/lib/librt.a"),
            Path("usr/lib/libpthread.a"),
            Path("usr/lib/libdl.a"),
            Path("lib/ld-musl-x86_64.so.1"),
            Path("lib/ld-musl-aarch64.so.1"),
        }
        _TOOLCHAIN_RUNTIME_PREFIXES = (
            "libc++.so",
            "libunwind.so",
            "libclang_rt.builtins",
        )
        for source in sorted(root.rglob("*"), reverse=True):
            if not (source.is_file() or source.is_symlink()):
                continue
            relative = source.relative_to(root)
            # These runtimes are installed by bootstrap_toolchain.  llvm-runtime
            # packages copies them for distribution, but must not remove the
            # source files before its special handler reads the sysroot.
            toolchain_runtime = (
                relative.parent == Path("usr/lib")
                and relative.name.startswith(_TOOLCHAIN_RUNTIME_PREFIXES)
            )
            if relative in _PROTECTED_SYSROOT_FILES or toolchain_runtime:
                continue
            (self.sysroot / relative).unlink(missing_ok=True)

    def merge_into_sysroot(self, root: Path) -> None:
        for source in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
            relative = source.relative_to(root)
            destination = self.sysroot / relative
            if source.is_dir() and not source.is_symlink():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if destination.exists() or destination.is_symlink():
                if source.is_symlink() and destination.is_symlink() and os.readlink(source) == os.readlink(destination):
                    continue
                if source.is_file() and destination.is_file() and sha256_file(source) == sha256_file(destination):
                    continue
                log(f"sysroot file collision skipped: {relative}")
            self.copy_entry(source, destination)
def verify_package_outputs(config_path: Path, output: Path) -> None:
    config = load(config_path)
    validate(config)
    required = {
        "system-core": ("bin/sh", "sbin/openrc", "bin/zsh", "sbin/mkfs.ext4", "sbin/e2fsck", "sbin/resize2fs", "sbin/mdadm", "sbin/integritysetup", "sbin/dmsetup"),
        "network": ("sbin/ip", "sbin/dhcpcd", "bin/ping"),
        "python": ("usr/bin/python3",),
        "openssh": ("usr/sbin/sshd", "usr/bin/ssh-keygen"),
        "diagnostics": ("usr/bin/htop", "usr/bin/lsof"),
        "firewall": ("usr/sbin/nft",),
        "fail2ban": ("usr/bin/fail2ban-server",),
        "fonts-cjk": ("usr/share/fonts/strataos/NotoSansSC-Regular.otf",),
    }
    for component, paths in required.items():
        if component == "fonts-cjk" and not enabled(config, "STRATA_ENABLE_CJK_FONTS"):
            continue
        if component == "firewall" and not enabled(config, "STRATA_ENABLE_FIREWALL"):
            continue
        if component == "fail2ban" and not enabled(config, "STRATA_ENABLE_FAIL2BAN"):
            continue
        if component == "diagnostics" and not enabled(config, "STRATA_ENABLE_DIAGNOSTICS"):
            continue
        package_names = [line.strip() for line in (ROOT / "components" / component / "packages.list").read_text().splitlines() if line.strip() and not line.startswith("#")]
        union: set[str] = set()
        for name in package_names:
            root = output / "packages" / name / "root"
            if not root.exists():
                raise BuildError(f"missing package root: {name}")
            union.update(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() or path.is_symlink())
        missing = [path for path in paths if path not in union]
        # In a merged-/usr layout, /bin → /usr/bin and /sbin → /usr/sbin.
        # Accept either the canonical path or its usr/-prefixed variant.
        missing = [path for path in missing if f"usr/{path}" not in union]
        if missing:
            raise BuildError(f"component {component} misses runtime paths: {', '.join(missing)}")
def build_packages(config_path: Path, output: Path, *, resume: bool = False) -> None:
    builder = PackageBuilder(config_path, output)
    target_packages = component_package_names(builder.config)
    requested = [*HOST_RECIPES, *target_packages]
    builder.preflight(requested)
    builder.build(HOST_RECIPES, preflight=False, resume=resume)
    builder.run_build_system_probes()
    builder.build(target_packages, preflight=False, resume=resume)
    verify_package_outputs(config_path, output)
    roots = [builder.package_root / name / "root" for name in target_packages]
    verify_needed_closure(builder.sysroot, builder.llvm_bin / "llvm-readelf", roots, builder.arch)
    log("native package graph complete")
def main() -> None:
    parser = argparse.ArgumentParser(description="Build StrataOS native packages")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="reuse matching incomplete package work")
    parser.add_argument("packages", nargs="*")
    args = parser.parse_args()
    try:
        builder = PackageBuilder(args.config.resolve(), args.output.resolve())
        requested = args.packages or [*HOST_RECIPES, *component_package_names(builder.config)]
        builder.build(requested, resume=args.resume)
        verify_package_outputs(args.config.resolve(), args.output.resolve())
    except (BuildError, OSError) as exc:
        raise SystemExit(str(exc))
if __name__ == "__main__":
    main()
