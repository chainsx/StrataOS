from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from common import BuildError, ROOT


@dataclass(frozen=True)
class Source:
    url: str
    sha256: str | None
    archive: str | None
    strip_components: int
    filename: str | None = None


@dataclass(frozen=True)
class SourceSet:
    default: Source | None
    by_arch: dict[str, Source]

    def for_arch(self, arch: str) -> Source:
        source = self.by_arch.get(arch, self.default)
        if source is None:
            raise BuildError(f"source is not available for architecture {arch}")
        return source


@dataclass(frozen=True)
class Recipe:
    name: str
    version: str
    source: SourceSet | None
    kind: str
    build_system: str
    dependencies: tuple[str, ...]
    configure_args: tuple[str, ...]
    cppflags: tuple[str, ...]
    special: str | None
    path: Path
    lto: str = "inherit"
    environment: tuple[str, ...] = ()
    patches: tuple[str, ...] = ()
    build_args: tuple[str, ...] = ()
    install_args: tuple[str, ...] = ()
    test_args: tuple[str, ...] = ()

    @property
    def directory(self) -> Path:
        return self.path.parent

    def patch_path(self, name: str) -> Path:
        return self.directory / "patches" / name

    def config_path(self, name: str) -> Path:
        return self.directory / "configs" / name

    def source_for_arch(self, arch: str) -> Source:
        if self.source is None:
            raise BuildError(f"{self.path}: recipe has no source")
        try:
            return self.source.for_arch(arch)
        except BuildError as exc:
            raise BuildError(f"{self.path}: {exc}") from exc


@dataclass(frozen=True)
class ToolchainInput:
    name: str
    version: str
    source: SourceSet
    path: Path

    def source_for_arch(self, arch: str) -> Source:
        try:
            return self.source.for_arch(arch)
        except BuildError as exc:
            raise BuildError(f"{self.path}: {exc}") from exc


def _string_list(value: object, key: str, path: Path) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BuildError(f"{path}: {key} must be an array of strings")
    return tuple(value)


def _environment_list(value: object, path: Path) -> tuple[str, ...]:
    entries = _string_list(value, "environment", path)
    for entry in entries:
        name, separator, _ = entry.partition("=")
        if not separator or not (
            re.fullmatch(r"[A-Z_][A-Z0-9_]*", name)
            or re.fullmatch(r"ac_cv_[a-z0-9_]+", name)
        ):
            raise BuildError(f"{path}: environment entries must use NAME=value")
    return entries


def _patch_list(value: object, path: Path) -> tuple[str, ...]:
    entries = _string_list(value, "patches", path)
    for entry in entries:
        patch = Path(entry)
        if patch.is_absolute() or ".." in patch.parts or patch.suffix != ".patch":
            raise BuildError(f"{path}: patches must name relative .patch files")
    return entries


def _source(value: object, path: Path) -> Source:
    if not isinstance(value, dict):
        raise BuildError(f"{path}: source entry must be a table")
    allowed = {"url", "sha256", "archive", "strip_components", "filename"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise BuildError(f"{path}: unknown source keys: {', '.join(unknown)}")
    url = value.get("url")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise BuildError(f"{path}: source URL must use HTTPS")
    sha256 = value.get("sha256")
    if sha256 is not None and (
        not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256)
    ):
        raise BuildError(f"{path}: source sha256 must be a lowercase SHA-256 digest")
    archive = value.get("archive")
    if archive is not None and archive != "file":
        raise BuildError(f"{path}: source archive must be file when specified")
    strip_components = value.get("strip_components", 1)
    if isinstance(strip_components, bool) or not isinstance(strip_components, int) or strip_components < 0:
        raise BuildError(f"{path}: source strip_components must be a non-negative integer")
    filename = value.get("filename")
    if filename is not None and (
        not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+{}-]*", filename)
    ):
        raise BuildError(f"{path}: source filename must be a safe file name")
    return Source(url, sha256, archive, strip_components, filename)


def _source_set(value: object, path: Path) -> SourceSet:
    if value is None:
        return SourceSet(None, {})
    if not isinstance(value, dict):
        raise BuildError(f"{path}: source must be a table")
    arch_names = {"x86_64", "arm64"}
    base = {key: item for key, item in value.items() if key not in arch_names}
    arch_tables = {key: item for key, item in value.items() if key in arch_names}
    unknown = sorted(set(value) - arch_names - {"url", "sha256", "archive", "strip_components", "filename"})
    if unknown:
        raise BuildError(f"{path}: unknown source tables: {', '.join(unknown)}")
    default = _source(base, path) if base else None
    selected: dict[str, Source] = {}
    for arch, item in arch_tables.items():
        selected[arch] = _source(item, path)
    if default is None and not selected:
        raise BuildError(f"{path}: source table is empty")
    if default is None and set(selected) != arch_names:
        raise BuildError(f"{path}: architecture-only source requires x86_64 and arm64 tables")
    return SourceSet(default, selected)


def load_recipes() -> dict[str, Recipe]:
    result: dict[str, Recipe] = {}
    for path in sorted((ROOT / "packages").glob("*/*.toml")):
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        allowed = {
            "name", "version", "source", "kind", "build_system", "special", "lto",
            "dependencies", "configure_args", "build_args", "install_args",
            "test_args", "cppflags", "environment", "patches",
        }
        unknown = sorted(set(raw) - allowed)
        if unknown:
            raise BuildError(f"{path}: unknown recipe keys: {', '.join(unknown)}")
        name = raw.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9+.-]*", name):
            raise BuildError(f"{path}: invalid package name")
        if path.stem != name or path.parent.name != name:
            raise BuildError(f"{path}: recipe and directory names must match package name")
        version = raw.get("version")
        if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", version):
            raise BuildError(f"{path}: invalid package version")
        source = _source_set(raw.get("source"), path) if "source" in raw else None
        kind = raw.get("kind")
        if kind not in {"host", "target"}:
            raise BuildError(f"{path}: kind must be host or target")
        build_system = raw.get("build_system")
        if build_system not in {"autotools", "cmake", "meson", "local", "special", "kernel"}:
            raise BuildError(f"{path}: invalid build_system")
        special = raw.get("special")
        if build_system == "special" and not isinstance(special, str):
            raise BuildError(f"{path}: special handler is required")
        if build_system != "special" and special is not None:
            raise BuildError(f"{path}: special is only valid for special recipes")
        lto = raw.get("lto", "inherit")
        if lto not in {"inherit", "none", "thin", "full"}:
            raise BuildError(f"{path}: lto must be inherit, none, thin or full")
        if kind == "host" and lto != "inherit":
            raise BuildError(f"{path}: LTO overrides are only valid for target recipes")
        recipe = Recipe(
            name=name,
            version=version,
            source=source,
            kind=kind,
            build_system=build_system,
            dependencies=_string_list(raw.get("dependencies"), "dependencies", path),
            configure_args=_string_list(raw.get("configure_args"), "configure_args", path),
            cppflags=_string_list(raw.get("cppflags"), "cppflags", path),
            special=special if isinstance(special, str) else None,
            path=path,
            lto=lto,
            environment=_environment_list(raw.get("environment"), path),
            patches=_patch_list(raw.get("patches"), path),
            build_args=_string_list(raw.get("build_args"), "build_args", path),
            install_args=_string_list(raw.get("install_args"), "install_args", path),
            test_args=_string_list(raw.get("test_args"), "test_args", path),
        )
        if name in result:
            raise BuildError(f"duplicate recipe: {name}")
        result[name] = recipe
    for recipe in result.values():
        missing = sorted(set(recipe.dependencies) - result.keys())
        if missing:
            raise BuildError(f"{recipe.path}: unknown dependencies: {', '.join(missing)}")
        for dependency in recipe.dependencies:
            if recipe.kind == "host" and result[dependency].kind != "host":
                raise BuildError(
                    f"{recipe.path}: host recipe depends on target recipe {dependency}"
                )
    return result


def load_recipe(name: str) -> Recipe:
    recipes = load_recipes()
    try:
        return recipes[name]
    except KeyError as exc:
        raise BuildError(f"unknown package recipe: {name}") from exc


def load_toolchain_inputs() -> dict[str, ToolchainInput]:
    result: dict[str, ToolchainInput] = {}
    for path in sorted((ROOT / "toolchains").glob("*.toml")):
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
        unknown = sorted(set(raw) - {"name", "version", "source"})
        if unknown:
            raise BuildError(f"{path}: unknown toolchain input keys: {', '.join(unknown)}")
        name = raw.get("name")
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9+.-]*", name):
            raise BuildError(f"{path}: invalid toolchain input name")
        if path.stem != name:
            raise BuildError(f"{path}: input name must match file name")
        version = raw.get("version")
        if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", version):
            raise BuildError(f"{path}: invalid toolchain input version")
        if "source" not in raw:
            raise BuildError(f"{path}: toolchain input requires a source")
        source = _source_set(raw["source"], path)
        if name in result:
            raise BuildError(f"duplicate toolchain input: {name}")
        result[name] = ToolchainInput(name, version, source, path)
    if not result:
        raise BuildError("no toolchain input recipes found")
    return result


def load_toolchain_input(name: str) -> ToolchainInput:
    try:
        return load_toolchain_inputs()[name]
    except KeyError as exc:
        raise BuildError(f"unknown toolchain input: {name}") from exc


def all_source_inputs() -> tuple[Recipe | ToolchainInput, ...]:
    recipes = tuple(recipe for recipe in load_recipes().values() if recipe.source is not None)
    return (*recipes, *load_toolchain_inputs().values())
