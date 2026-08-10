#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

from common import BuildError, ROOT, copytree_clean, extract, jobs, log, run
from build_policy import (
    RUNTIME_ASM_COMPILE_FLAGS, RUNTIME_C_COMPILE_FLAGS,
    RUNTIME_CXX_COMPILE_FLAGS, RUNTIME_LINK_FLAGS, join_flags,
    target_cxx_header_flags, target_libcxx_include_dir,
)
from config import load, validate
from fetch import fetch_source
from recipes import load_recipe, load_toolchain_input
from elf_audit import audit_elf_tree, verify_needed_closure


def triples(arch: str) -> tuple[str, str]:
    if arch == "x86_64":
        return "x86_64-linux-musl", "x86_64"
    return "aarch64-linux-musl", "arm64"


def write_wrapper(path: Path, triple: str, llvm_bin: Path, sysroot: Path, *, cxx: bool = False) -> None:
    """Write a GCC-compatible command name backed by Clang/LLD.

    Autoconf projects commonly discover compilers through GCC-compatible names
    and query options such as -dumpmachine and -print-file-name.  The wrapper
    answers those probes from the isolated StrataOS sysroot and then delegates
    compilation to the official LLVM toolchain.
    """
    compiler = "clang++" if cxx else "clang"
    cxx_compile_flags = (
        ' -nostdinc++ -isystem "$SYSROOT/usr/include/c++/v1" '
        if cxx else ""
    )
    cxx_link_flags = (
        ' -stdlib=libc++ --unwindlib=libunwind'
        if cxx else ""
    )
    cxx_guard = (
        '[ -f "$SYSROOT/usr/include/c++/v1/__config_site" ] || '
        '{ echo "target libc++ headers are incomplete: missing __config_site" >&2; exit 1; }\n'
        if cxx else ""
    )
    text = f"""#!/bin/sh
set -eu
TRIPLE='{triple}'
SYSROOT='{sysroot}'
CLANG='{llvm_bin / compiler}'
LLVM_BIN='{llvm_bin}'

print_sysroot_file() {{
    name=$1
    for candidate in \
        "$SYSROOT/usr/lib/$name" \
        "$SYSROOT/lib/$name" \
        "$SYSROOT/usr/lib/$TRIPLE/$name" \
        "$SYSROOT/lib/$TRIPLE/$name"
    do
        if [ -e "$candidate" ]; then
            echo "$candidate"
            return 0
        fi
    done
    return 1
}}

for arg in "$@"; do
    case "$arg" in
        -dumpmachine) echo "$TRIPLE"; exit 0 ;;
        -dumpversion|-dumpfullversion) exec "$CLANG" "$arg" ;;
        -print-sysroot) echo "$SYSROOT"; exit 0 ;;
        -print-prog-name=ld) echo "$LLVM_BIN/ld.lld"; exit 0 ;;
        -print-prog-name=as) echo "$LLVM_BIN/clang"; exit 0 ;;
        -print-file-name=*)
            name=${{arg#*=}}
            if result=$(print_sysroot_file "$name"); then
                echo "$result"
                exit 0
            fi
            ;;
    esac
done

{cxx_guard}LINKING=true
for arg in "$@"; do
    case "$arg" in
        -c|-E|-S|-fsyntax-only|-M|-MM) LINKING=false ;;
    esac
done
if [ "$LINKING" = true ]; then
    exec "$CLANG" --target="$TRIPLE" --sysroot="$SYSROOT"{cxx_compile_flags} \
        -fuse-ld=lld --rtlib=compiler-rt{cxx_link_flags} \
        -Wl,-rpath-link,"$SYSROOT/lib" -Wl,-rpath-link,"$SYSROOT/usr/lib" "$@"
fi
exec "$CLANG" --target="$TRIPLE" --sysroot="$SYSROOT"{cxx_compile_flags} "$@"
"""
    path.write_text(text)
    path.chmod(0o755)


def find_library(root: Path, name: str) -> Path | None:
    candidates = sorted(root.rglob(name))
    return candidates[0] if candidates else None


def missing_cxx_runtime_libraries(sysroot: Path) -> tuple[str, ...]:
    """Return the target C++ shared runtimes required by downstream packages."""
    required = ("libc++.so.1", "libunwind.so.1")
    return tuple(name for name in required if find_library(sysroot, name) is None)


def _capture_line(command: list[str]) -> str:
    completed = run(command, capture=True)
    lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    if not lines:
        raise BuildError(f"command returned no output: {' '.join(command)}")
    return lines[-1]


def _runtime_candidate_score(path: Path, arch: str) -> tuple[int, str]:
    text = path.as_posix().lower()
    architecture_tokens = {
        "x86_64": ("x86_64",),
        "arm64": ("aarch64", "arm64"),
    }[arch]
    score = 0
    if any(token in text for token in architecture_tokens):
        score += 100
    if "linux" in text:
        score += 30
    if "gnu" in text:
        score += 10
    if "android" in text or "windows" in text or "darwin" in text:
        score -= 200
    if path.name == "libclang_rt.builtins.a":
        score += 20
    return score, text


def install_compiler_rt_target_runtime(llvm_dst: Path, llvm_bin: Path, triple: str, arch: str) -> Path:
    """Make the official native LLVM compiler-rt usable for a musl triple.

    LLVM's Linux prebuilt archives commonly ship compiler-rt under a GNU target
    runtime directory.  When Clang is retargeted to ``*-linux-musl`` it probes a
    sibling musl directory which is absent, so musl's configure leaves LIBCC
    empty and libc.so later fails on compiler-emitted helpers such as __muldc3.

    StrataOS only supports same-architecture native builds.  The compiler-rt
    builtins and crtbegin/crtend objects are ABI-level architecture runtimes,
    so copy the small required subset from the official native Linux directory
    into the exact directory selected by Clang's musl driver.
    """
    clang = llvm_bin / "clang"
    expected = Path(_capture_line([
        str(clang), f"--target={triple}", "--rtlib=compiler-rt",
        "-print-libgcc-file-name",
    ]))
    if not expected.is_absolute():
        expected = (llvm_dst / expected).resolve()
    try:
        expected.relative_to(llvm_dst.resolve())
    except ValueError as exc:
        raise BuildError(f"Clang returned compiler runtime outside LLVM tree: {expected}") from exc

    candidates: list[Path] = []
    for pattern in ("libclang_rt.builtins.a", "libclang_rt.builtins-*.a"):
        candidates.extend(path for path in llvm_dst.rglob(pattern) if path.is_file())
    candidates = sorted(set(candidates), key=lambda path: _runtime_candidate_score(path, arch), reverse=True)
    if not candidates or _runtime_candidate_score(candidates[0], arch)[0] < 100:
        raise BuildError(f"official LLVM archive has no native compiler-rt builtins for {arch}")
    source = candidates[0]

    expected.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != expected.resolve():
        shutil.copy2(source, expected)
    for pattern, canonical_name in (
        ("*crtbegin*.o", "clang_rt.crtbegin.o"),
        ("*crtend*.o", "clang_rt.crtend.o"),
    ):
        for runtime_object in source.parent.glob(pattern):
            shutil.copy2(runtime_object, expected.parent / runtime_object.name)
            # Older LLVM layouts suffix these objects with the architecture,
            # while per-target layouts use the canonical unsuffixed names.
            canonical = expected.parent / canonical_name
            if not canonical.exists():
                shutil.copy2(runtime_object, canonical)

    # Use a full capture for symbol validation rather than the single-line probe helper.
    completed = run([str(llvm_bin / "llvm-nm"), "--defined-only", str(expected)], capture=True)
    symbols = completed.stdout or ""
    required = {"__muldc3", "__mulsc3"}
    required.add("__mulxc3" if arch == "x86_64" else "__multc3")
    missing = sorted(symbol for symbol in required if symbol not in symbols)
    if missing:
        raise BuildError(
            f"compiler-rt builtins for {arch} miss required symbols: {', '.join(missing)}"
        )

    driver_path = Path(_capture_line([
        str(clang), f"--target={triple}", "--rtlib=compiler-rt",
        "-print-libgcc-file-name",
    ]))
    if not driver_path.exists():
        raise BuildError(f"Clang still cannot resolve compiler-rt builtins for {triple}: {driver_path}")
    log(f"compiler-rt target runtime ready: {driver_path}")
    return driver_path


def verify_runtime_driver_plan(llvm_bin: Path, triple: str, sysroot: Path, build_root: Path) -> str:
    """Fail before the long runtime build if Clang would select host GCC/ld.

    CMAKE_LINKER only identifies a linker executable to CMake; it does not add
    -fuse-ld=lld to Clang's driver command.  The -### trace is authoritative for
    crt objects and implicit runtime libraries and catches the exact class of
    failures that otherwise appears at the final libc++.so link step.
    """
    probe = build_root / "runtime-driver-probe"
    probe.mkdir(parents=True, exist_ok=True)
    source = probe / "probe.cpp"
    source.write_text("extern \"C\" int value(void) { return 0; }\n")
    completed = run([
        str(llvm_bin / "clang++"), f"--target={triple}", f"--sysroot={sysroot}",
        *RUNTIME_LINK_FLAGS, "-shared", "-nostdlib++", "-###", str(source),
        "-o", str(probe / "libprobe.so"),
    ], capture=True)
    trace = completed.stdout or ""
    if "ld.lld" not in trace:
        raise BuildError("Clang runtime driver plan does not select LLD")
    forbidden = ("/usr/bin/ld", "crtbeginS.o", "crtendS.o", "-lgcc", "-lgcc_s", "-latomic")
    found = [token for token in forbidden if token in trace]
    if found:
        raise BuildError("Clang runtime driver plan leaks host/GCC inputs: " + ", ".join(found))
    return trace


def verify_runtime_link_plan(build_dir: Path, llvm_bin: Path) -> Path:
    candidates = sorted(build_dir.rglob("cxx_shared.dir/link.txt"))
    if not candidates:
        raise BuildError("libc++ shared-library link plan was not generated")
    link = candidates[0]
    text = link.read_text(errors="replace")
    required = (str(llvm_bin / "clang++"), "-fuse-ld=lld", "--rtlib=compiler-rt", "--unwindlib=none")
    missing = [token for token in required if token not in text]
    if missing:
        raise BuildError("libc++ link plan misses required driver flags: " + ", ".join(missing))
    forbidden = ("/usr/bin/ld", "-lgcc", "-lgcc_s", "-latomic", "crtbeginS.o", "crtendS.o")
    found = [token for token in forbidden if token in text]
    if found:
        raise BuildError("libc++ link plan contains forbidden host/GCC inputs: " + ", ".join(found))
    return link


def smoke_test_musl_link(llvm_bin: Path, triple: str, sysroot: Path, build_root: Path) -> None:
    smoke = build_root / "musl-link-smoke"
    shutil.rmtree(smoke, ignore_errors=True)
    smoke.mkdir(parents=True)
    source = smoke / "complex.c"
    output = smoke / "complex"
    source.write_text(
        "#include <complex.h>\n"
        "volatile double complex a = 1.0 + 2.0 * I;\n"
        "volatile double complex b = 3.0 + 4.0 * I;\n"
        "int main(void) { volatile double complex c = a * b; return creal(c) == -5.0 ? 0 : 1; }\n"
    )
    run([
        str(llvm_bin / "clang"), f"--target={triple}", f"--sysroot={sysroot}",
        "-fuse-ld=lld", "--rtlib=compiler-rt", str(source), "-o", str(output),
    ])
    if not output.exists():
        raise BuildError("musl/compiler-rt link smoke test did not produce an executable")


def verify_libcxx_musl_configuration(build_dir: Path) -> Path:
    candidates = sorted(build_dir.rglob("__config_site"))
    for candidate in candidates:
        text = candidate.read_text(errors="replace")
        if "#define _LIBCPP_HAS_MUSL_LIBC" in text:
            return candidate
    rendered = ", ".join(str(path) for path in candidates) or "none generated"
    raise BuildError(
        "libc++ was not configured for musl: _LIBCPP_HAS_MUSL_LIBC is absent "
        f"from generated __config_site files ({rendered})"
    )


def libc_defines_symbol(llvm_bin: Path, sysroot: Path, symbol: str) -> bool:
    """Return whether the target musl libc exports *symbol* dynamically."""
    libc = find_library(sysroot, "libc.so")
    if libc is None:
        raise BuildError("target musl libc.so is missing before LLVM runtime configuration")
    completed = run(
        [str(llvm_bin / "llvm-nm"), "--dynamic", "--defined-only", str(libc)],
        capture=True,
    )
    return any(line.split() and line.split()[-1] == symbol for line in (completed.stdout or "").splitlines())


def check_cmake_unused_variables(output: str, context: str) -> None:
    marker = "Manually-specified variables were not used by the project:"
    if marker not in output:
        return
    tail = output.split(marker, 1)[1]
    unused: list[str] = []
    for raw in tail.splitlines():
        line = raw.strip()
        if not line:
            if unused:
                break
            continue
        if line.startswith("--") or line.startswith("CMake Warning"):
            if unused:
                break
            continue
        if line.replace("_", "").isalnum():
            unused.append(line)
        elif unused:
            break
    detail = ", ".join(unused) if unused else "unknown variables"
    raise BuildError(f"{context}: CMake ignored manually specified variables: {detail}")


def runtime_cmake_variables(arguments: list[str]) -> set[str]:
    variables: set[str] = set()
    for argument in arguments:
        if not argument.startswith("-D") or "=" not in argument:
            continue
        name = argument[2:].split("=", 1)[0].split(":", 1)[0]
        if name.startswith(("LIBCXX_", "LIBCXXABI_", "LIBUNWIND_")) or name == "LLVM_ENABLE_RUNTIMES":
            variables.add(name)
    return variables


def verify_runtime_cmake_variable_references(llvm_source: Path, arguments: list[str]) -> None:
    """Reject runtime cache variables absent from the selected LLVM source.

    LLVM runtime option names do change between releases.  A variable that is
    absent from every runtime CMake source file cannot influence the build and
    should be rejected before the expensive configure/compile phase.  The
    post-configure unused-variable check remains authoritative for variables
    that are present only in inactive branches.
    """
    roots = [
        llvm_source / "runtimes",
        llvm_source / "libcxx",
        llvm_source / "libcxxabi",
        llvm_source / "libunwind",
        llvm_source / "cmake",
    ]
    corpus_parts: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or not (path.name == "CMakeLists.txt" or path.suffix == ".cmake"):
                continue
            corpus_parts.append(path.read_text(errors="replace"))
    if not corpus_parts:
        raise BuildError("LLVM runtime CMake sources are missing")
    corpus = "\n".join(corpus_parts)
    missing = sorted(name for name in runtime_cmake_variables(arguments) if name not in corpus)
    if missing:
        raise BuildError(
            "LLVM runtime options are not declared by the selected LLVM source: "
            + ", ".join(missing)
        )


def verify_runtime_compile_plan(build_dir: Path) -> None:
    """Reject link-driver flags that leaked into compile-only command flags."""
    offenders: list[str] = []
    for path in sorted(build_dir.rglob("flags.make")):
        for raw in path.read_text(errors="replace").splitlines():
            if not raw.startswith(("C_FLAGS =", "CXX_FLAGS =", "ASM_FLAGS =")):
                continue
            for token in ("-fuse-ld=", "--rtlib=", "--unwindlib="):
                if token in raw:
                    offenders.append(f"{path}:{token}")
    if offenders:
        raise BuildError(
            "LLVM runtime compile plan contains link-only flags: " + ", ".join(offenders[:8])
        )


def verify_libcxxabi_tls_atexit_configuration(build_dir: Path, expected: bool) -> None:
    """Ensure libc++abi does not create a strong libc TLS-dtor reference by mistake.

    CMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY is required while bootstrapping
    libc++, but it also makes check_library_exists() incapable of proving that a
    symbol is linkable.  The result is therefore forced from the already-built
    musl libc and verified in both CMakeCache and generated compile definitions.
    """
    cache = build_dir / "CMakeCache.txt"
    if not cache.is_file():
        raise BuildError("LLVM runtime CMakeCache.txt is missing")
    text = cache.read_text(errors="replace")
    match = re.search(
        r"^LIBCXXABI_HAS_CXA_THREAD_ATEXIT_IMPL:[^=]+=(ON|OFF|TRUE|FALSE|1|0)$",
        text,
        re.M,
    )
    if not match:
        raise BuildError("libc++abi TLS destructor capability is absent from CMakeCache")
    actual = match.group(1) in {"ON", "TRUE", "1"}
    if actual != expected:
        raise BuildError(
            "libc++abi TLS destructor capability disagrees with target libc "
            f"(expected {expected}, configured {actual})"
        )
    definition = "HAVE___CXA_THREAD_ATEXIT_IMPL"
    generated = "\n".join(
        path.read_text(errors="replace")
        for path in sorted(build_dir.rglob("flags.make"))
        if path.is_file()
    )
    if expected and definition not in generated:
        raise BuildError("libc++abi did not enable the target libc TLS destructor symbol")
    if not expected and definition in generated:
        raise BuildError("libc++abi incorrectly created a strong __cxa_thread_atexit_impl reference")


def verify_libcxx_musl_library_policy(build_dir: Path) -> None:
    """Verify the LLVM 22 musl runtime library policy.

    STATIC_LIBRARY try-compiles cannot reliably prove that target libraries are
    linkable.  Only cache variables actually accepted by the selected LLVM
    source are forced.  Removed variables such as LIBCXX_HAS_C_LIB and
    LIBCXX_HAS_M_LIB must not be reintroduced.
    """
    cache = build_dir / "CMakeCache.txt"
    if not cache.is_file():
        raise BuildError("LLVM runtime CMakeCache.txt is missing")
    text = cache.read_text(errors="replace")
    expected = {
        "LIBCXX_HAS_PTHREAD_API": True,
        "LIBCXX_HAS_RT_LIB": False,
        "LIBCXX_HAS_PTHREAD_LIB": False,
        "LIBCXX_HAS_ATOMIC_LIB": False,
        "LIBCXXABI_HAS_C_LIB": True,
        "LIBCXXABI_HAS_PTHREAD_LIB": False,
        "LIBUNWIND_HAS_DL_LIB": False,
        "LIBUNWIND_HAS_PTHREAD_LIB": False,
    }
    for name, wanted in expected.items():
        match = re.search(
            rf"^{re.escape(name)}:[^=]+=(ON|OFF|TRUE|FALSE|1|0)$",
            text,
            re.M,
        )
        if not match:
            raise BuildError(f"LLVM runtime cache is missing forced policy variable {name}")
        actual = match.group(1) in {"ON", "TRUE", "1"}
        if actual != wanted:
            raise BuildError(
                f"LLVM runtime policy variable {name} is {actual}, expected {wanted}"
            )


def verify_target_libcxx_installation(sysroot: Path) -> Path:
    """Validate installed target C++ headers before any package consumes them."""
    include = target_libcxx_include_dir(sysroot)
    required = ("__config", "__config_site", "cstddef", "locale")
    missing = [name for name in required if not (include / name).is_file()]
    if missing:
        raise BuildError(
            "target libc++ installation is incomplete under "
            f"{include}: missing {', '.join(missing)}"
        )
    return include


def smoke_test_libcxx_link(llvm_bin: Path, triple: str, sysroot: Path, build_root: Path) -> None:
    smoke = build_root / "libcxx-smoke"
    shutil.rmtree(smoke, ignore_errors=True)
    smoke.mkdir(parents=True)
    source = smoke / "locale.cpp"
    output = smoke / "locale"
    source.write_text(
        "#include <locale>\n"
        "#include <string>\n"
        "int main() { std::locale l = std::locale::classic(); "
        "return std::use_facet<std::ctype<char>>(l).is(std::ctype_base::alpha, 'A') ? 0 : 1; }\n"
    )
    include = verify_target_libcxx_installation(sysroot)
    run([
        str(llvm_bin / "clang++"), f"--target={triple}", f"--sysroot={sysroot}",
        *target_cxx_header_flags(sysroot),
        "-fuse-ld=lld", "--rtlib=compiler-rt", "--unwindlib=libunwind",
        "-stdlib=libc++", str(source), "-o", str(output),
    ])
    native_include = llvm_bin.parent / "include" / "c++" / "v1"
    if include.resolve() == native_include.resolve():
        raise BuildError("target libc++ headers unexpectedly resolve to the host LLVM tree")
    if not output.exists():
        raise BuildError("libc++ musl locale smoke test did not produce an executable")


def bootstrap(config_path: Path, output: Path) -> Path:
    config = load(config_path)
    validate(config)
    linux = load_recipe("linux")
    if linux.build_system != "kernel" or linux.source is None:
        raise BuildError(f"{linux.path}: Linux must use the kernel build system and a source")
    arch = config["STRATA_ARCH"]
    triple, kernel_arch = triples(arch)
    j = jobs(int(config.get("STRATA_JOBS", "0")))
    dl = output / "dl"
    src = output / "bootstrap-src"
    toolchain = output / "toolchain"
    sysroot = toolchain / "sysroot"
    stamp = toolchain / ".complete"
    fingerprint = "\n".join([
        f"arch={arch}",
        f"linux={linux.version}",
        f"llvm={config['STRATA_LLVM_VERSION']}",
        f"musl={config['STRATA_MUSL_VERSION']}",
        f"cmake={config['STRATA_CMAKE_VERSION']}",
        "bootstrap_schema=10",
    ]) + "\n"
    if stamp.exists() and stamp.read_text() == fingerprint:
        missing = missing_cxx_runtime_libraries(sysroot)
        if not missing:
            return toolchain
        log(
            "toolchain cache is missing target C++ runtime libraries; rebuilding: "
            + ", ".join(missing)
        )

    llvm = load_toolchain_input("llvm-prebuilt")
    llvm_source = load_toolchain_input("llvm-source")
    cmake = load_toolchain_input("cmake")
    musl = load_toolchain_input("musl")
    expected_versions = {
        "llvm-prebuilt": config["STRATA_LLVM_VERSION"],
        "llvm-source": config["STRATA_LLVM_VERSION"],
        "cmake": config["STRATA_CMAKE_VERSION"],
        "musl": config["STRATA_MUSL_VERSION"],
    }
    for input_recipe in (llvm, llvm_source, cmake, musl):
        if input_recipe.version != expected_versions[input_recipe.name]:
            raise BuildError(
                f"{input_recipe.path}: version disagrees with build configuration"
            )
    llvm_archive = fetch_source(llvm.source_for_arch(arch), llvm.version, dl)
    llvm_source_archive = fetch_source(
        llvm_source.source_for_arch(arch), llvm_source.version, dl
    )
    cmake_archive = fetch_source(cmake.source_for_arch(arch), cmake.version, dl)
    linux_archive = fetch_source(linux.source_for_arch(arch), linux.version, dl)
    musl_archive = fetch_source(musl.source_for_arch(arch), musl.version, dl)

    llvm_prebuilt = extract(llvm_archive, src / "llvm-prebuilt", strip_components=1, parallelism=j)
    llvm_source = extract(llvm_source_archive, src / "llvm-project", strip_components=1, parallelism=j)
    cmake_src = extract(cmake_archive, src / "cmake", strip_components=1, parallelism=j)
    linux_src = extract(linux_archive, src / "linux", strip_components=1, parallelism=j)
    musl_src = extract(musl_archive, src / "musl", strip_components=1, parallelism=j)

    if toolchain.exists():
        shutil.rmtree(toolchain)
    toolchain.mkdir(parents=True)
    llvm_dst = toolchain / "llvm"
    copytree_clean(llvm_prebuilt, llvm_dst)
    llvm_bin = llvm_dst / "bin"
    cmake_dst = toolchain / "cmake"
    copytree_clean(cmake_src, cmake_dst)
    cmake = cmake_dst / "bin" / "cmake"
    if not (llvm_bin / "clang").exists():
        raise BuildError("LLVM archive layout is not recognized; clang is missing")
    if not cmake.exists():
        raise BuildError("CMake archive layout is not recognized")

    compiler_rt_builtins = install_compiler_rt_target_runtime(
        llvm_dst, llvm_bin, triple, arch
    )

    sysroot.mkdir(parents=True)
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{llvm_bin}:{cmake_src / 'bin'}:{env.get('PATH', '')}",
            "CC": str(llvm_bin / "clang"),
            "CXX": str(llvm_bin / "clang++"),
            "HOSTCC": str(llvm_bin / "clang"),
            "HOSTCXX": str(llvm_bin / "clang++"),
            "LLVM": "1",
            "LLVM_IAS": "1",
            "SOURCE_DATE_EPOCH": config.get("STRATA_SOURCE_DATE_EPOCH", "0"),
        }
    )
    run(
        [
            "make", f"-j{j}", f"ARCH={kernel_arch}", "LLVM=1", "headers_install",
            f"INSTALL_HDR_PATH={sysroot / 'usr'}",
        ],
        cwd=linux_src,
        env=env,
    )

    musl_build = output / "bootstrap-build" / "musl"
    shutil.rmtree(musl_build, ignore_errors=True)
    musl_build.mkdir(parents=True)
    cc = f"{llvm_bin / 'clang'} --target={triple} --sysroot={sysroot} -fuse-ld=lld --rtlib=compiler-rt"
    musl_env = env | {
        "CC": cc,
        "AR": str(llvm_bin / "llvm-ar"),
        "RANLIB": str(llvm_bin / "llvm-ranlib"),
        "LIBCC": str(compiler_rt_builtins),
    }
    run(
        [str(musl_src / "configure"), f"--target={triple}", "--prefix=/usr", "--syslibdir=/lib", "--enable-shared"],
        cwd=musl_build,
        env=musl_env,
    )
    run(["make", f"-j{j}", f"LIBCC={compiler_rt_builtins}"], cwd=musl_build, env=musl_env)
    run(["make", f"DESTDIR={sysroot}", "install"], cwd=musl_build, env=musl_env)
    smoke_test_musl_link(llvm_bin, triple, sysroot, output / "bootstrap-build")

    # Verify musl shared runtime and loader were installed (not just static libc.a).
    # The smoke_test_musl_link above only checks linkability, not runtime files.
    _triple_arch = "x86_64" if "x86_64" in triple else "aarch64"
    _loader_name = f"ld-musl-{_triple_arch}.so.1"
    _libc_so = sysroot / "usr/lib/libc.so"
    _loader = sysroot / "lib" / _loader_name
    if not _libc_so.is_file() or not (_loader.is_symlink() or _loader.is_file()):
        raise BuildError(
            f"musl shared runtime incomplete: libc.so={_libc_so.is_file()}, "
            f"loader={_loader} exists={_loader.exists()}\n"
            "  This usually means the musl 'make install' step failed to install "
            "shared libraries despite --enable-shared. Check the build log above."
        )

    runtimes_build = output / "bootstrap-build" / "llvm-runtimes"
    shutil.rmtree(runtimes_build, ignore_errors=True)
    runtimes_build.mkdir(parents=True)
    has_cxa_thread_atexit_impl = libc_defines_symbol(
        llvm_bin, sysroot, "__cxa_thread_atexit_impl"
    )
    runtime_flags = [
        str(cmake), "-S", str(llvm_source / "runtimes"), "-B", str(runtimes_build),
        "-G", "Unix Makefiles",
        "-DLLVM_ENABLE_RUNTIMES=libunwind;libcxxabi;libcxx",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_SYSTEM_NAME=Linux",
        f"-DCMAKE_SYSROOT={sysroot}",
        f"-DCMAKE_C_COMPILER={llvm_bin / 'clang'}",
        f"-DCMAKE_CXX_COMPILER={llvm_bin / 'clang++'}",
        f"-DCMAKE_ASM_COMPILER={llvm_bin / 'clang'}",
        f"-DCMAKE_C_COMPILER_TARGET={triple}",
        f"-DCMAKE_CXX_COMPILER_TARGET={triple}",
        f"-DCMAKE_ASM_COMPILER_TARGET={triple}",
        f"-DCMAKE_AR={llvm_bin / 'llvm-ar'}",
        f"-DCMAKE_RANLIB={llvm_bin / 'llvm-ranlib'}",
        f"-DCMAKE_NM={llvm_bin / 'llvm-nm'}",
        f"-DCMAKE_LINKER={llvm_bin / 'ld.lld'}",
        "-DCMAKE_INSTALL_PREFIX=/usr",
        "-DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY",
        f"-DCMAKE_C_FLAGS_INIT={join_flags(RUNTIME_C_COMPILE_FLAGS)}",
        f"-DCMAKE_CXX_FLAGS_INIT={join_flags(RUNTIME_CXX_COMPILE_FLAGS)}",
        f"-DCMAKE_ASM_FLAGS_INIT={join_flags(RUNTIME_ASM_COMPILE_FLAGS)}",
        f"-DCMAKE_EXE_LINKER_FLAGS_INIT={join_flags(RUNTIME_LINK_FLAGS)}",
        f"-DCMAKE_SHARED_LINKER_FLAGS_INIT={join_flags(RUNTIME_LINK_FLAGS)}",
        f"-DCMAKE_MODULE_LINKER_FLAGS_INIT={join_flags(RUNTIME_LINK_FLAGS)}",
        "-DLIBCXX_HAS_MUSL_LIBC=ON",
        "-DLIBCXX_HAS_PTHREAD_API=ON",
        "-DLIBCXX_HAS_RT_LIB=OFF",
        "-DLIBCXX_HAS_PTHREAD_LIB=OFF",
        f"-DLIBCXXABI_HAS_CXA_THREAD_ATEXIT_IMPL={'ON' if has_cxa_thread_atexit_impl else 'OFF'}",
        "-DLIBCXX_USE_COMPILER_RT=ON",
        "-DLIBCXX_HAS_ATOMIC_LIB=OFF",
        "-DLIBCXXABI_USE_COMPILER_RT=ON",
        "-DLIBUNWIND_USE_COMPILER_RT=ON",
        "-DLIBCXXABI_USE_LLVM_UNWINDER=ON",
        "-DLIBCXXABI_HAS_C_LIB=ON",
        "-DLIBCXXABI_HAS_PTHREAD_LIB=OFF",
        "-DLIBUNWIND_HAS_DL_LIB=OFF",
        "-DLIBUNWIND_HAS_PTHREAD_LIB=OFF",
        "-DLIBCXX_ENABLE_STATIC_ABI_LIBRARY=ON",
        "-DLIBCXXABI_ENABLE_STATIC_UNWINDER=ON",
        "-DLIBCXX_INCLUDE_TESTS=OFF",
        "-DLIBCXXABI_INCLUDE_TESTS=OFF",
        "-DLIBUNWIND_INCLUDE_TESTS=OFF",
        "-DLIBCXX_INCLUDE_BENCHMARKS=OFF",
        "-DLIBCXX_ENABLE_SHARED=ON",
        "-DLIBCXX_ENABLE_STATIC=ON",
        "-DLIBCXXABI_ENABLE_SHARED=OFF",
        "-DLIBCXXABI_ENABLE_STATIC=ON",
        "-DLIBUNWIND_ENABLE_SHARED=ON",
        "-DLIBUNWIND_ENABLE_STATIC=ON",
    ]
    verify_runtime_cmake_variable_references(llvm_source, runtime_flags)
    verify_runtime_driver_plan(llvm_bin, triple, sysroot, output / "bootstrap-build")
    configured = run(runtime_flags, env=env, capture=True)
    check_cmake_unused_variables(configured.stdout or "", "LLVM runtimes")
    verify_libcxx_musl_configuration(runtimes_build)
    verify_libcxxabi_tls_atexit_configuration(
        runtimes_build, has_cxa_thread_atexit_impl
    )
    verify_libcxx_musl_library_policy(runtimes_build)
    verify_runtime_compile_plan(runtimes_build)
    verify_runtime_link_plan(runtimes_build, llvm_bin)
    run([str(cmake), "--build", str(runtimes_build), "--parallel", str(j)], env=env)
    run([str(cmake), "--install", str(runtimes_build)], env=env | {"DESTDIR": str(sysroot)})
    smoke_test_libcxx_link(llvm_bin, triple, sysroot, output / "bootstrap-build")

    # GCC-compatible command names are discovery aliases only; all generated
    # C and C++ ELF files are compiled by Clang and linked by LLD. C++ uses libc++.
    libdir = sysroot / "usr" / "lib"
    libdir.mkdir(parents=True, exist_ok=True)
    missing = missing_cxx_runtime_libraries(sysroot)
    if missing:
        raise BuildError(
            "target C++ runtime installation failed: missing " + ", ".join(missing)
        )
    libcxx = find_library(sysroot, "libc++.so.1")
    assert libcxx is not None
    if libcxx.parent != libdir:
        for candidate in libcxx.parent.glob("libc++*.so*"):
            destination = libdir / candidate.name
            if not destination.exists():
                shutil.copy2(candidate, destination, follow_symlinks=False)
    unwind = find_library(sysroot, "libunwind.so.1")
    assert unwind is not None
    if unwind.parent != libdir:
        for candidate in unwind.parent.glob("libunwind.so*"):
            destination = libdir / candidate.name
            if not destination.exists():
                shutil.copy2(candidate, destination, follow_symlinks=False)

    # The bootstrap toolchain itself is subject to the same ABI boundary as
    # later packages.  Catch libgcc_s/libatomic/glibc leakage immediately.
    runtime_readelf = llvm_bin / "llvm-readelf"
    audit_elf_tree(sysroot, runtime_readelf, arch)
    verify_needed_closure(sysroot, runtime_readelf, (sysroot,), arch)

    bindir = toolchain / "bin"
    bindir.mkdir()
    write_wrapper(bindir / f"{triple}-gcc", triple, llvm_bin, sysroot)
    write_wrapper(bindir / f"{triple}-cc", triple, llvm_bin, sysroot)
    write_wrapper(bindir / f"{triple}-g++", triple, llvm_bin, sysroot, cxx=True)
    write_wrapper(bindir / f"{triple}-c++", triple, llvm_bin, sysroot, cxx=True)
    write_wrapper(bindir / f"{triple}-cpp", triple, llvm_bin, sysroot)
    for target, source in {
        "ar": "llvm-ar", "ranlib": "llvm-ranlib", "nm": "llvm-nm",
        "objcopy": "llvm-objcopy", "objdump": "llvm-objdump", "readelf": "llvm-readelf",
        "size": "llvm-size", "strings": "llvm-strings", "strip": "llvm-strip", "ld": "ld.lld",
    }.items():
        (bindir / f"{triple}-{target}").symlink_to(llvm_bin / source)
    assembler = bindir / f"{triple}-as"
    assembler.write_text(f"#!/bin/sh\nexec '{llvm_bin / 'clang'}' --target='{triple}' -c -x assembler \"$@\"\n")
    assembler.chmod(0o755)

    (toolchain / "metadata.env").write_text(
        "\n".join([
            f"STRATA_ARCH={arch}", f"STRATA_TRIPLE={triple}",
            f"STRATA_LLVM_VERSION={config['STRATA_LLVM_VERSION']}",
            f"STRATA_MUSL_VERSION={config['STRATA_MUSL_VERSION']}",
            f"STRATA_KERNEL_HEADERS={linux.version}",
            "STRATA_CXX_RUNTIME=libc++",
        ]) + "\n"
    )
    stamp.write_text(fingerprint)
    log(f"toolchain ready: {toolchain}")
    return toolchain


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        bootstrap(args.config.resolve(), args.output.resolve())
    except BuildError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
