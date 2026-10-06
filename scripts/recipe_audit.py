#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable, Mapping

from common import BuildError, ROOT, extract, jobs, log
from config import load, validate
from fetch import fetch_source

AUTOTOOLS_STANDARD = {
    "--help", "--version", "--quiet", "--silent", "--cache-file", "--config-cache",
    "--no-create", "--srcdir", "--prefix", "--exec-prefix", "--bindir", "--sbindir",
    "--libexecdir", "--sysconfdir", "--sharedstatedir", "--localstatedir", "--runstatedir",
    "--libdir", "--includedir", "--oldincludedir", "--datarootdir", "--datadir",
    "--infodir", "--localedir", "--mandir", "--docdir", "--htmldir", "--dvidir",
    "--pdfdir", "--psdir", "--program-prefix", "--program-suffix", "--program-transform-name",
    "--build", "--host", "--target",
    "--enable-findmnt", "--enable-blockdev",
}
MESON_BUILTINS = {
    "default_library", "buildtype", "warning_level", "werror", "strip", "b_lto",
    "b_pie", "b_staticpic", "c_args", "cpp_args", "c_link_args", "cpp_link_args",
    "prefix", "libdir", "bindir", "sbindir", "sysconfdir", "localstatedir",
}
CMAKE_BUILTINS = {
    "BUILD_SHARED_LIBS", "BUILD_TESTING",
}
SPECIAL_CONTRACTS: dict[str, tuple[str, ...]] = {
    "ninja": ("CMakeLists.txt",),
    "zstd": ("Makefile",),
    "squashfs-tools": ("squashfs-tools/Makefile",),
    "bzip2": ("Makefile", "Makefile-libbz2_so"),
    "libcap": ("Makefile",),
    "openssl": ("Configure",),
    "ca-certificates": (),
    "font-file": (),
    "argon2": ("Makefile",),
    "busybox": ("Makefile", "scripts/kconfig/Makefile"),
    "openrc": ("Makefile",),
    "lvm2": ("configure",),
    "mdadm": ("Makefile",),
    "iproute2": ("Makefile",),
    "dhcpcd": ("configure",),
    "docker-static": (),
    "host-glslang": ("bin/glslangValidator",),
    "musl-runtime": (),
    "llvm-runtime": (),
    "llvm-libs": ("llvm/CMakeLists.txt", "libclc/CMakeLists.txt"),
    "fail2ban": ("fail2ban/server", "config/action.d/nftables.conf", "bin/fail2ban-server"),
    "host-python-module": (),
}

SPECIAL_HANDLER_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "ninja": ("recipe.configure_args", "recipe.build_args", "--parallel"),
    "zstd": ("recipe.build_args", "recipe.install_args", "env=env"),
    "squashfs-tools": ("recipe.build_args", "CFLAGS", "LDFLAGS"),
    "bzip2": ("recipe.build_args", "CC=", "AR=", "Makefile-libbz2_so"),
    "libcap": ("recipe.build_args", "recipe.install_args", "BUILD_CC="),
    "openssl": ("recipe.configure_args", "recipe.install_args", "make", "-j"),
    "argon2": ("recipe.build_args", "recipe.install_args", "make", "-j"),
    "busybox": ("recipe.install_args", "CC=", "AR=", "RANLIB=", "NM=", "STRIP=", "HOSTCC="),
    "lvm2": ("recipe.configure_args", "recipe.build_args", "recipe.install_args"),
    "mdadm": ("recipe.build_args", "recipe.install_args", "CXFLAGS="),
    "iproute2": ("recipe.configure_args", "recipe.install_args", "PKG_CONFIG:="),
    "dhcpcd": ("recipe.configure_args", "recipe.build_args", "recipe.install_args"),
    "docker-static": ("Docker archive misses",),
    "host-glslang": ("glslangValidator", "host_bin", "chmod"),
    "ca-certificates": ("ca-certificates.crt",),
    "font-file": ("usr/share/fonts/strataos", "OTF, TTF or TTC"),
    "musl-runtime": ("libc.so",),
    "llvm-libs": ("recipe.configure_args", "llvm-tblgen", "--parallel", "DESTDIR", "libclc"),
    "llvm-runtime": ("libc++.so", "libunwind.so"),
    "fail2ban": ("python3.13/site-packages", "fail2ban-client", "config"),
    "host-python-module": ("site-packages", "copytree", "import {module_name}"),
}


def _method_body(source: str, method: str) -> str:
    match = re.search(
        rf"^    def {re.escape(method)}\([^\n]*\).*?(?=^    def |^def |\Z)",
        source,
        re.M | re.S,
    )
    return match.group(0) if match else ""


def audit_special_handlers() -> None:
    path = ROOT / "scripts/package_builder.py"
    source = path.read_text(errors="replace")
    method_names = {
        "squashfs-tools": "special_squashfs",
        "ca-certificates": "special_ca_certificates",
        "docker-static": "special_docker",
        "musl-runtime": "special_musl_runtime",
        "llvm-runtime": "special_llvm_runtime",
    }
    for special, required in SPECIAL_HANDLER_REQUIREMENTS.items():
        method = method_names.get(special, "special_" + special.replace("-", "_"))
        body = _method_body(source, method)
        if not body:
            raise BuildError(f"special build handler is missing: {method}")
        missing = [token for token in required if token not in body]
        if missing:
            raise BuildError(f"{method} misses audited build parameters: {', '.join(missing)}")


def audit_global_build_policy() -> None:
    policy = (ROOT / "scripts/build_policy.py").read_text(errors="replace")
    bootstrap = (ROOT / "scripts/bootstrap_toolchain.py").read_text(errors="replace")
    package_builder = (ROOT / "scripts/package_builder.py").read_text(errors="replace")
    for token in ("-fuse-ld=lld", "--rtlib=compiler-rt", "-stdlib=libc++", "--unwindlib=libunwind", "-nostdinc++"):
        if token not in policy:
            raise BuildError(f"global target build policy misses {token}")
    for token in (
        "verify_runtime_driver_plan", "verify_runtime_link_plan",
        "verify_libcxxabi_tls_atexit_configuration", "verify_libcxx_musl_library_policy",
        "LIBCXX_HAS_ATOMIC_LIB=OFF", "LIBCXX_HAS_PTHREAD_API=ON",
        "LIBCXX_HAS_PTHREAD_LIB=OFF", "LIBCXXABI_HAS_CXA_THREAD_ATEXIT_IMPL",
        "check_cmake_unused_variables",
        "verify_needed_closure", "verify_target_libcxx_installation",
    ):
        if token not in bootstrap:
            raise BuildError(f"toolchain preflight misses {token}")
    for token in (
        "meson-native.ini", "CMAKE_CROSSCOMPILING_EMULATOR", "source-aware build parameter audit",
        "target_cxx_header_flags",
        "effective-build-parameters", "generated-build-plans", "audit_elf_tree", "verify_needed_closure",
    ):
        if token not in package_builder:
            raise BuildError(f"package build policy misses {token}")
    audit_special_handlers()



def _option_key(argument: str, build_system: str) -> str:
    if build_system == "autotools":
        return argument.split("=", 1)[0]
    if build_system in {"cmake", "meson"}:
        return argument[2:].split("=", 1)[0]
    return argument


def _recipe_args(recipe: object) -> tuple[str, ...]:
    return tuple(getattr(recipe, "configure_args", ()))


def audit_static_recipes(recipes: Mapping[str, object]) -> list[dict[str, object]]:
    audit_global_build_policy()
    report: list[dict[str, object]] = []
    forbidden = ("-march=native", "-mtune=native", "-mcpu=native", "-lstdc++", "-lgcc")
    for name in sorted(recipes):
        recipe = recipes[name]
        build_system = str(getattr(recipe, "build_system"))
        args = _recipe_args(recipe)
        seen: set[str] = set()
        for argument in args:
            if build_system == "autotools":
                if not argument.startswith("--"):
                    raise BuildError(f"{name}: invalid Autotools option {argument}")
            elif build_system in {"cmake", "meson"}:
                if not argument.startswith("-D") or "=" not in argument:
                    raise BuildError(f"{name}: invalid {build_system} option {argument}")
                key = _option_key(argument, build_system)
                if not re.fullmatch(r"[A-Za-z0-9_.+-]+", key):
                    raise BuildError(f"{name}: invalid option name {key}")
            key = _option_key(argument, build_system)
            if key in seen:
                raise BuildError(f"{name}: duplicate configure option {key}")
            seen.add(key)
            lowered = argument.lower()
            for token in forbidden:
                if token in lowered:
                    raise BuildError(f"{name}: forbidden host/compiler runtime flag {token}")
        for flag in tuple(getattr(recipe, "cppflags", ())):
            lowered = flag.lower()
            if any(token in lowered for token in forbidden):
                raise BuildError(f"{name}: forbidden cppflag {flag}")
        for phase in ("build_args", "test_args", "install_args"):
            for argument in tuple(getattr(recipe, phase, ())):
                lowered = argument.lower()
                for token in forbidden:
                    if token in lowered:
                        raise BuildError(f"{name}: forbidden {phase} flag {token}")
        if build_system == "special":
            special = str(getattr(recipe, "special", ""))
            if special not in SPECIAL_CONTRACTS:
                raise BuildError(f"{name}: no audit contract for special handler {special}")
        report.append({
            "name": name,
            "kind": str(getattr(recipe, "kind")),
            "build_system": build_system,
            "configure_args": list(args),
            "build_args": list(getattr(recipe, "build_args", ())),
            "install_args": list(getattr(recipe, "install_args", ())),
            "status": "static-ok",
        })
    return report


def _canonical_autotools_option(option: str) -> str:
    if option.startswith("--disable-"):
        return "--enable-" + option.removeprefix("--disable-")
    if option.startswith("--without-"):
        return "--with-" + option.removeprefix("--without-")
    return option


def _autotools_options(source: Path) -> set[str]:
    configure = source / "configure"
    if not configure.exists():
        raise BuildError(f"Autotools source has no configure script: {source}")
    completed = subprocess.run(
        [str(configure), "--help"], cwd=source, env={**os.environ, "LC_ALL": "C"},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60,
        check=False,
    )
    text = completed.stdout or ""
    options = {
        _canonical_autotools_option(option)
        for option in re.findall(r"(?<![A-Za-z0-9_])(--[A-Za-z0-9][A-Za-z0-9_-]*)", text)
    }
    if not options:
        raise BuildError(f"cannot extract configure options from {configure}")
    return options | AUTOTOOLS_STANDARD


def _cmake_calls(text: str) -> Iterable[tuple[str, str]]:
    """Yield CMake command names and argument bodies with balanced parentheses."""
    starter = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)\s*\(")
    cursor = 0
    while True:
        match = starter.search(text, cursor)
        if not match:
            return
        depth = 1
        quote: str | None = None
        escaped = False
        index = match.end()
        while index < len(text) and depth:
            char = text[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = None
            else:
                if char in {"'", '"'}:
                    quote = char
                elif char == "#":
                    newline = text.find("\n", index)
                    if newline < 0:
                        index = len(text)
                        break
                    index = newline
                elif char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
            index += 1
        if depth == 0:
            yield match.group(1).lower(), text[match.end():index - 1]
            cursor = index
        else:
            cursor = match.end()


def _cmake_tokens(body: str) -> list[str]:
    return [
        quoted_double or quoted_single or bare
        for quoted_double, quoted_single, bare in re.findall(
            r'"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\'|([^\s()]+)',
            body,
        )
    ]


def _cmake_options(source: Path) -> set[str]:
    options = set(CMAKE_BUILTINS)
    files = {source / "CMakeLists.txt"}
    files.update(source.rglob("CMakeLists.txt"))
    files.update(source.rglob("*.cmake"))
    found_cmake = False
    for path in sorted(files):
        relative_parts = path.relative_to(source).parts
        if not path.is_file() or any(part in {"build", "_build", ".git"} for part in relative_parts):
            continue
        found_cmake = True
        text = path.read_text(errors="replace")
        for command, body in _cmake_calls(text):
            tokens = _cmake_tokens(body)
            if not tokens:
                continue
            if command in {"option", "cmake_dependent_option"} or command.endswith("option"):
                options.add(tokens[0])
                continue
            upper_tokens = [token.upper() for token in tokens]
            if command == "set" and "CACHE" in upper_tokens[1:]:
                options.add(tokens[0])
                continue
            if command == "set_property" and upper_tokens[0] == "CACHE" and len(tokens) > 1:
                options.add(tokens[1])
                continue
            # Projects such as Expat wrap set(... CACHE ...) in a helper macro and
            # pass the public variable as the first argument, e.g.
            # expat_shy_set(EXPAT_BUILD_DOCS OFF CACHE BOOL ...).
            if command.endswith("set") and "CACHE" in upper_tokens[1:]:
                options.add(tokens[0])
            # CHECK_FUNCTION_EXISTS_GLIBC creates internal CACHE variables.
            if command.upper() == "CHECK_FUNCTION_EXISTS_GLIBC" and len(tokens) >= 2:
                options.add(tokens[1])
    if not found_cmake:
        raise BuildError(f"CMake source has no CMakeLists.txt: {source}")
    return options


def _meson_option_blocks(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    cursor = 0
    starter = re.compile(r"\boption\s*\(\s*(['\"])([^'\"]+)\1", re.S)
    while True:
        match = starter.search(text, cursor)
        if not match:
            break
        depth = 0
        quote: str | None = None
        escaped = False
        end = match.end()
        index = match.start()
        while index < len(text):
            char = text[index]
            if quote:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif text.startswith(quote, index):
                    index += len(quote) - 1
                    quote = None
                index += 1
                continue
            if char in {"'", '"'}:
                triple = char * 3
                quote = triple if text.startswith(triple, index) else char
                index += len(quote)
                continue
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
            index += 1
        result[match.group(2)] = text[match.start():end]
        cursor = end
    return result


def _meson_options(source: Path) -> dict[str, str]:
    paths = [source / "meson.options", source / "meson_options.txt"]
    result: dict[str, str] = {}
    for path in paths:
        if path.is_file():
            result.update(_meson_option_blocks(path.read_text(errors="replace")))
    if not (source / "meson.build").exists():
        raise BuildError(f"Meson source has no meson.build: {source}")
    return result


def _meson_deprecated_value_aliases(block: str) -> dict[str, str]:
    match = re.search(r"\bdeprecated\s*:\s*\{([^}]*)\}", block, re.S)
    if not match:
        return {}
    return {
        source: target
        for source, target in re.findall(
            r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]",
            match.group(1),
        )
    }


def _validate_meson_value(package: str, key: str, value: str, block: str) -> None:
    type_match = re.search(r"\btype\s*:\s*['\"]([^'\"]+)", block)
    # Format-string placeholders (e.g. {mesa_llvm}) are expanded at build
    # time using arch-specific context variables.  Skip static validation
    # for these values — they will be verified at configure time by Meson.
    if "{" in value and "}" in value:
        return
    option_type = type_match.group(1) if type_match else "string"
    if option_type == "boolean" and value not in {"true", "false"}:
        raise BuildError(f"{package}: Meson boolean {key} must be true/false, got {value}")
    if option_type == "feature" and value not in {"enabled", "disabled", "auto"}:
        aliases = _meson_deprecated_value_aliases(block)
        if value not in aliases or aliases[value] not in {"enabled", "disabled", "auto"}:
            raise BuildError(f"{package}: Meson feature {key} has invalid value {value}")
    if option_type == "combo":
        choices_match = re.search(r"\bchoices\s*:\s*\[([^\]]*)\]", block, re.S)
        if choices_match:
            choices = {
                value
                for _quote, value in re.findall(
                    r"(['\"])(.*?)\1", choices_match.group(1), re.S
                )
            }
            if choices and value not in choices:
                raise BuildError(f"{package}: Meson combo {key}={value} not in {sorted(choices)}")


def audit_source_recipes(
    recipes: Mapping[str, object], source_paths: Mapping[str, Path | None]
) -> list[dict[str, object]]:
    static = {item["name"]: item for item in audit_static_recipes(recipes)}
    cache: dict[tuple[str, str], object] = {}
    for name in sorted(recipes):
        recipe = recipes[name]
        source = source_paths.get(name)
        build_system = str(getattr(recipe, "build_system"))
        if source is None:
            static[name]["source_status"] = "generated-or-toolchain-owned"
            continue
        if source.is_file():
            if build_system != "special":
                raise BuildError(f"{name}: non-special recipe source is not a directory")
            static[name]["source_status"] = "file-contract-ok"
            continue
        if build_system == "autotools":
            cache_key = (str(source.resolve()), "autotools")
            options = cache.setdefault(cache_key, _autotools_options(source))
            assert isinstance(options, set)
            for argument in _recipe_args(recipe):
                key = _canonical_autotools_option(_option_key(argument, build_system))
                if key not in options:
                    raise BuildError(f"{name}: configure option is not advertised by source: {key}")
        elif build_system == "cmake":
            cache_key = (str(source.resolve()), "cmake")
            options = cache.setdefault(cache_key, _cmake_options(source))
            assert isinstance(options, set)
            for argument in _recipe_args(recipe):
                key = _option_key(argument, build_system)
                if key.startswith("CMAKE_"):
                    continue
                if key not in options:
                    raise BuildError(f"{name}: CMake variable is not declared by source: {key}")
        elif build_system == "meson":
            cache_key = (str(source.resolve()), "meson")
            blocks = cache.setdefault(cache_key, _meson_options(source))
            assert isinstance(blocks, dict)
            for argument in _recipe_args(recipe):
                key = _option_key(argument, build_system)
                value = argument.split("=", 1)[1]
                if key in MESON_BUILTINS:
                    continue
                if key not in blocks:
                    raise BuildError(f"{name}: Meson option is not declared by source: {key}")
                _validate_meson_value(name, key, value, blocks[key])
        else:
            special = str(getattr(recipe, "special", ""))
            for relative in SPECIAL_CONTRACTS[special]:
                if not (source / relative).exists():
                    raise BuildError(f"{name}: special handler expects missing source path {relative}")
        static[name]["source_status"] = "source-options-ok"
    return [static[name] for name in sorted(static)]


def write_audit_report(path: Path, arch: str, entries: Iterable[dict[str, object]], mode: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "format": 1,
        "architecture": arch,
        "mode": mode,
        "packages": list(entries),
    }, indent=2, sort_keys=True) + "\n")


def _fetch_sources(
    recipes: Mapping[str, object], arch: str, output: Path, parallelism: int
) -> dict[str, Path | None]:
    result: dict[str, Path | None] = {}
    for name, recipe in recipes.items():
        if getattr(recipe, "source", None) is None:
            result[name] = None
            continue
        item = recipe.source_for_arch(arch)
        archive = fetch_source(item, recipe.version, output / "dl")
        if item.archive == "file":
            result[name] = archive
        else:
            result[name] = extract(
                archive, output / "preflight-src" / name,
                strip_components=item.strip_components,
                parallelism=parallelism,
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit StrataOS package build parameters")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true", help="download/extract sources and validate source options")
    args = parser.parse_args()
    from package_builder import HOST_RECIPES, component_package_names, load_recipes, topological_order

    config = load(args.config.resolve())
    validate(config, native=False)
    all_recipes = load_recipes()
    order = topological_order(all_recipes, [*HOST_RECIPES, *component_package_names(config)])
    recipes = {name: all_recipes[name] for name in order}
    if args.fetch:
        parallel = jobs(int(config.get("STRATA_JOBS", "0")))
        sources = _fetch_sources(
            recipes, config["STRATA_ARCH"], args.output.resolve(), parallel
        )
        entries = audit_source_recipes(recipes, sources)
        mode = "source-aware"
    else:
        entries = audit_static_recipes(recipes)
        mode = "static"
    report = args.output.resolve() / "reports/build-parameter-audit.json"
    write_audit_report(report, config["STRATA_ARCH"], entries, mode)
    log(f"build parameter audit passed for {len(entries)} packages ({mode})")
    log(f"audit report: {report}")


if __name__ == "__main__":
    try:
        main()
    except (BuildError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
