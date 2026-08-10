#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from common import BuildError, ROOT
from config import load_data

# One policy is shared by wrappers, Autotools, CMake, Meson and the synthetic
# probes.  Keep compiler runtime and linker selection explicit; CMAKE_LINKER by
# itself does not make the Clang driver select LLD.
def target_build_options(arch: str, *, lto: str | None = None) -> dict[str, str]:
    if arch not in {"x86_64", "arm64"}:
        raise BuildError(f"unsupported target architecture for build policy: {arch}")
    options = load_data(ROOT / "configs" / "build" / f"{arch}.conf")
    if options.get("format") != "1":
        raise BuildError(f"invalid build policy format for {arch}")
    if options.get("optimization") not in {"-O2", "-O3", "-Os", "-Oz"}:
        raise BuildError(f"invalid optimization policy for {arch}")
    if options.get("lto") not in {"none", "thin", "full"}:
        raise BuildError(f"invalid LTO policy for {arch}")
    if options.get("section_gc") not in {"yes", "no"}:
        raise BuildError(f"invalid section GC policy for {arch}")
    cpu_flags = options.get("cpu_flags", "")
    if cpu_flags and not all(flag.startswith(("-m", "-mcpu=", "-march=")) for flag in cpu_flags.split()):
        raise BuildError(f"invalid CPU flags policy for {arch}")
    if lto is not None:
        if lto not in {"none", "thin", "full"}:
            raise BuildError(f"invalid LTO override for {arch}")
        options = {**options, "lto": lto}
    return options


def target_c_compile_flags(arch: str, *, lto: str | None = None) -> tuple[str, ...]:
    options = target_build_options(arch, lto=lto)
    flags = [options["optimization"], "-pipe", "-fPIC", "-fstack-protector-strong", "-D_FORTIFY_SOURCE=2", "-D__BYTE_ORDER=__BYTE_ORDER__"]
    if options["lto"] != "none":
        flags.append(f"-flto={options['lto']}")
    if options["section_gc"] == "yes":
        flags.extend(("-ffunction-sections", "-fdata-sections"))
    flags.extend(options.get("cpu_flags", "").split())
    return tuple(flags)


def target_cxx_compile_flags(arch: str, *, lto: str | None = None) -> tuple[str, ...]:
    return target_c_compile_flags(arch, lto=lto)


def target_link_flags(arch: str, *, lto: str | None = None) -> tuple[str, ...]:
    options = target_build_options(arch, lto=lto)
    flags = ["-fuse-ld=lld", "--rtlib=compiler-rt", "-Wl,-z,relro,-z,now"]
    if options["lto"] != "none":
        flags.append(f"-flto={options['lto']}")
    if options["section_gc"] == "yes":
        flags.append("-Wl,--gc-sections")
    return tuple(flags)


def target_cxx_link_flags(arch: str, *, lto: str | None = None) -> tuple[str, ...]:
    return (*target_link_flags(arch, lto=lto), "-stdlib=libc++", "--unwindlib=libunwind")


# Compatibility defaults for policy-only callers. Build paths select the
# architecture-specific functions above explicitly.
TARGET_C_COMPILE_FLAGS = target_c_compile_flags("x86_64")
TARGET_CXX_COMPILE_FLAGS = target_cxx_compile_flags("x86_64")
TARGET_LINK_FLAGS = target_link_flags("x86_64")
TARGET_CXX_LINK_FLAGS = target_cxx_link_flags("x86_64")


def target_libcxx_include_dir(sysroot: Path) -> Path:
    """Return the only permitted target libc++ include directory."""
    return sysroot / "usr" / "include" / "c++" / "v1"


def target_cxx_header_flags(sysroot: Path) -> tuple[str, ...]:
    """Prevent Clang from selecting headers bundled with the host LLVM archive."""
    return ("-nostdinc++", "-isystem", str(target_libcxx_include_dir(sysroot)))
# LLVM runtimes are a bootstrap exception: compilation flags and link-driver
# policy must stay separate.  Passing -fuse-ld/--rtlib/--unwindlib through
# CMAKE_{C,CXX}_FLAGS makes every compile-only invocation warn that the
# arguments are unused and can break projects that enable
# -Werror=unused-command-line-argument.
RUNTIME_C_COMPILE_FLAGS = ("-O2", "-pipe", "-fPIC")
RUNTIME_CXX_COMPILE_FLAGS = RUNTIME_C_COMPILE_FLAGS
RUNTIME_ASM_COMPILE_FLAGS = ("-fPIC",)
RUNTIME_LINK_FLAGS = (
    "-fuse-ld=lld", "--rtlib=compiler-rt", "--unwindlib=none",
    "-Wl,-z,relro,-z,now",
)

HOST_C_COMPILE_FLAGS = ("-O2", "-pipe", "-fPIC")
HOST_CXX_COMPILE_FLAGS = HOST_C_COMPILE_FLAGS
HOST_LINK_FLAGS = ("-fuse-ld=lld",)

SANITIZED_ENVIRONMENT = {
    "CPATH": "",
    "C_INCLUDE_PATH": "",
    "CPLUS_INCLUDE_PATH": "",
    "OBJC_INCLUDE_PATH": "",
    "LIBRARY_PATH": "",
    "LD_LIBRARY_PATH": "",
    "LD_PRELOAD": "",
    "PKG_CONFIG_PATH": "",
    "PKG_CONFIG_DIR": "",
    "CMAKE_PREFIX_PATH": "",
    "CMAKE_INCLUDE_PATH": "",
    "CMAKE_LIBRARY_PATH": "",
    "PERL5LIB": "",
    "ACLOCAL_PATH": "",
    "PYTHONPATH": "",
    "PYTHONSTARTUP": "",
    "CCACHE_DISABLE": "1",
}

FORBIDDEN_TARGET_LINK_INPUTS = (
    "libstdc++.so", "libgcc_s.so", "libatomic.so", "libc.so.6",
)
FORBIDDEN_HOST_PATH_FRAGMENTS = (
    "/usr/lib/x86_64-linux-gnu", "/usr/lib/aarch64-linux-gnu",
    "/lib/x86_64-linux-gnu", "/lib/aarch64-linux-gnu", "/home/",
)


def join_flags(flags: tuple[str, ...] | list[str]) -> str:
    return " ".join(flags)


def target_runtime_library_paths(sysroot: Path) -> tuple[Path, ...]:
    return (
        sysroot / "lib",
        sysroot / "usr/lib",
        sysroot / "usr/lib64",
    )
