#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from pathlib import Path

from common import BuildError, ROOT, jobs, log, run, sha256_file
from config import enabled, load, load_data, validate
from rootfs import (
    add_runlevel_link,
    configure_logging,
    install_base_configuration,
    install_base_runlevels,
    ownership_for,
)

RUNTIME_SKIP_PREFIXES = (
    "usr/include/",
    "usr/share/aclocal/",
    "usr/share/doc/",
    "usr/share/gtk-doc/",
    "usr/share/info/",
    "usr/share/man/",
    "usr/lib/cmake/",
    "usr/lib/pkgconfig/",
    "usr/share/pkgconfig/",
)

BUILD_ONLY_WRAPPER_NAMES = {"pkgconf-native", "run-target"}
BUILD_ONLY_COMPILER_WRAPPER = re.compile(
    r".+-linux-musl-(?:cc|c\+\+|gcc|g\+\+)$"
)


def prefer_complete_commands(root: Path, output: Path) -> None:
    """Point BusyBox aliases at complete packaged implementations when present."""
    commands: dict[str, tuple[Path, Path]] = {}
    for package in ("coreutils", "iputils", "iproute2", "shadow"):
        package_root = output / "packages" / package / "root"
        for relative_dir in ("usr/bin", "usr/sbin", "bin", "sbin"):
            directory = package_root / relative_dir
            if not directory.is_dir():
                continue
            for command in sorted(directory.iterdir(), key=lambda item: item.name):
                if command.is_file() or command.is_symlink():
                    commands.setdefault(
                        command.name,
                        (command, command.relative_to(package_root)),
                    )

    for relative_dir in ("bin", "sbin", "usr/bin", "usr/sbin"):
        directory = root / relative_dir
        if not directory.is_dir():
            continue
        for command in sorted(directory.iterdir(), key=lambda item: item.name):
            preferred_entry = commands.get(command.name)
            if not preferred_entry or not command.is_symlink():
                continue
            preferred_source, preferred = preferred_entry
            if Path(os.readlink(command)).name != "busybox":
                continue
            preferred_path = root / preferred
            if preferred_path == command:
                command.unlink()
                copy_entry(preferred_source, command)
                continue
            command.unlink()
            command.symlink_to(os.path.relpath(preferred_path, command.parent))


def verify_no_build_wrappers(root: Path) -> None:
    leaked = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.name in BUILD_ONLY_WRAPPER_NAMES
        or BUILD_ONLY_COMPILER_WRAPPER.fullmatch(path.name)
    ]
    if leaked:
        raise BuildError(
            "build-only wrapper leaked into component root: " + ", ".join(leaked)
        )


def same_entry(a: Path, b: Path) -> bool:
    if not b.exists() and not b.is_symlink():
        return False
    sa = a.lstat()
    sb = b.lstat()
    if stat.S_IFMT(sa.st_mode) != stat.S_IFMT(sb.st_mode):
        return False
    if a.is_symlink():
        return os.readlink(a) == os.readlink(b)
    if a.is_file():
        return sa.st_size == sb.st_size and sha256_file(a) == sha256_file(b)
    return a.is_dir() and b.is_dir()
def copy_entry(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.unlink(missing_ok=True)
        destination.symlink_to(os.readlink(source))
    elif source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        shutil.copystat(source, destination, follow_symlinks=False)
    elif source.is_file():
        shutil.copy2(source, destination, follow_symlinks=False)
    else:
        raise BuildError(f"unsupported special file in component tree: {source}")
def runtime_path(relative: str, source: Path) -> bool:
    if any(relative.startswith(prefix) for prefix in RUNTIME_SKIP_PREFIXES):
        return False
    if relative.startswith("usr/bin/") and source.name.endswith("-config"):
        return False
    if source.is_file() and not source.is_symlink():
        if source.suffix in {".a", ".la"}:
            return False
        if relative.endswith(("/charset.alias", "/gdbus-codegen", "/glib-genmarshal", "/glib-mkenums")):
            return False
    return True
def merge_tree(
    source: Path,
    destination: Path,
    *,
    runtime_only: bool = False,
    replace_existing: bool = False,
) -> None:
    if not source.exists():
        return
    for entry in sorted(source.rglob("*"), key=lambda p: p.as_posix()):
        relative = entry.relative_to(source)
        if runtime_only and not runtime_path(relative.as_posix(), entry):
            continue
        target = destination / relative
        if target.exists() or target.is_symlink():
            if same_entry(entry, target):
                continue
            if entry.is_dir() and target.is_dir() and not entry.is_symlink() and not target.is_symlink():
               continue
            if replace_existing:
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                copy_entry(entry, target)
                continue
            log(f"payload collision skipped (first writer wins): {relative}")
            continue
        copy_entry(entry, target)
def package_names(component: str) -> list[str]:
    path = ROOT / "components" / component / "packages.list"
    result: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            result.append(line)
    return result
def package_version(output: Path, name: str) -> str:
    metadata = load_data(output / "packages" / name / "package.env")
    return metadata["version"]
def assemble_component_root(component: str, output: Path, config: dict[str, str]) -> tuple[Path, list[dict[str, str]]]:
    root = output / "component-roots" / component
    shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    provenance: list[dict[str, str]] = []
    for package in package_names(component):
        package_root = output / "packages" / package / "root"
        if not package_root.exists():
            raise BuildError(f"missing package root for component {component}: {package}")
        merge_tree(package_root, root, runtime_only=True)
        provenance.append({"name": package, "version": package_version(output, package)})
    if component == "kernel-modules":
        modules_root = output / "kernel/modules-root"
        if not modules_root.is_dir():
            raise BuildError("kernel modules are missing; run make kernel before make components")
        merge_tree(modules_root, root, runtime_only=True)
    # The project-authored rootfs is an overlay over package defaults.  In
    # particular, service policy files such as localmount must replace the
    # upstream package copy rather than being silently discarded.
    merge_tree(
        ROOT / "components" / component / "rootfs",
        root,
        replace_existing=True,
    )
    if component == "system-core":
        install_base_configuration(root, config)
        install_base_runlevels(root)
        configure_logging(root)
        prefer_complete_commands(root, output)
    component_conf = load_data(ROOT / "components" / component / "component.conf")
    for service in [item for item in component_conf.get("services", "").split(",") if item]:
        level = "boot" if service in {"strataos-storage", "strataos-logging"} else "default"
        add_runlevel_link(root, level, service)
    verify_no_build_wrappers(root)
    return root, provenance
def metadata_for_tree(root: Path) -> dict[str, tuple[int, int, int]]:
    result: dict[str, tuple[int, int, int]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        result[relative] = ownership_for(relative, mode)
    return result
def pseudo_quote(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'
def write_metadata_pseudo(stage: Path, root: Path, metadata: dict[str, tuple[int, int, int]]) -> Path:
    lines: list[str] = []
    paths = [stage / "meta", stage / "meta/strataos", root]
    paths.extend(sorted(stage.rglob("*"), key=lambda item: item.as_posix()))
    seen: set[Path] = set()
    for path in paths:
        if path in seen or (not path.exists() and not path.is_symlink()):
            continue
        seen.add(path)
        if path == root:
            mode, uid, gid = (0o755, 0, 0)
        elif root in path.parents:
            relative = path.relative_to(root).as_posix()
            mode, uid, gid = metadata.get(relative, (stat.S_IMODE(path.lstat().st_mode), 0, 0))
        else:
            mode, uid, gid = (stat.S_IMODE(path.lstat().st_mode), 0, 0)
        lines.append(f"{pseudo_quote(path.relative_to(stage).as_posix())} m {mode:04o} {uid} {gid}")
    pseudo = stage.parent / f".{stage.name}-metadata.pseudo"
    pseudo.write_text("\n".join(lines) + "\n")
    return pseudo
def tree_manifest(root: Path, metadata: dict[str, tuple[int, int, int]]) -> list[dict[str, str | int]]:
    result: list[dict[str, str | int]] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        relative = path.relative_to(root).as_posix()
        st = path.lstat()
        mode, uid, gid = metadata.get(relative, (stat.S_IMODE(st.st_mode), 0, 0))
        common: dict[str, str | int] = {"path": relative, "mode": mode, "uid": uid, "gid": gid}
        if path.is_symlink():
            result.append(common | {"type": "symlink", "target": os.readlink(path)})
        elif path.is_dir():
            result.append(common | {"type": "directory"})
        elif path.is_file():
            result.append(common | {"type": "file", "sha256": sha256_file(path), "size": st.st_size})
        else:
            raise BuildError(f"special file is not allowed in a component: {path}")
    return result
def write_file_hashes(root: Path, destination: Path) -> None:
    lines: list[str] = []
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        if path.is_file() and not path.is_symlink():
            lines.append(f"{sha256_file(path)}  rootfs/{path.relative_to(root).as_posix()}")
        elif path.is_symlink():
            digest = hashlib.sha256(os.readlink(path).encode()).hexdigest()
            lines.append(f"{digest}  rootfs/{path.relative_to(root).as_posix()} ->")
    destination.write_text("\n".join(lines) + ("\n" if lines else ""))
def package_component(
    component: str,
    root_tree: Path,
    provenance: list[dict[str, str]],
    output: Path,
    config: dict[str, str],
) -> Path:
    source_dir = ROOT / "components" / component
    component_conf = load_data(source_dir / "component.conf")
    name = component_conf["name"]
    version = component_conf["version"]
    stage = output / "component-stage" / name
    shutil.rmtree(stage, ignore_errors=True)
    root = stage / "rootfs"
    meta = stage / "meta/strataos"
    shutil.copytree(root_tree, root, symlinks=True)
    meta.mkdir(parents=True)
    metadata = metadata_for_tree(root)

    component_lines: list[str] = []
    for raw in (source_dir / "component.conf").read_text().splitlines():
        if raw.startswith("architectures="):
            component_lines.append(f"architectures={config['STRATA_ARCH']}")
        else:
            component_lines.append(raw)
    (meta / "component.conf").write_text("\n".join(component_lines) + "\n")
    hooks = source_dir / "hooks"
    if hooks.is_dir():
        shutil.copytree(hooks, meta / "hooks", symlinks=True)
    write_file_hashes(root, meta / "files.sha256")
    (meta / "packages.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    manifest = {
        "format": 1,
        "name": name,
        "version": version,
        "architecture": config["STRATA_ARCH"],
        "priority": int(component_conf["priority"]),
        "requires": [x for x in component_conf.get("requires", "").split(",") if x],
        "packages": provenance,
        "files": tree_manifest(root, metadata),
    }
    (meta / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")

    images = output / "components"
    images.mkdir(parents=True, exist_ok=True)
    temporary = images / f".{name}-{version}.squashfs.tmp"
    temporary.unlink(missing_ok=True)
    pseudo = write_metadata_pseudo(stage, root, metadata)
    mksquashfs = output / "host/bin/mksquashfs"
    if not mksquashfs.exists():
        raise BuildError("host mksquashfs is missing; build packages first")
    epoch = config.get("STRATA_SOURCE_DATE_EPOCH", "0")
    run(
        [
            str(mksquashfs), str(stage), str(temporary), "-noappend",
            "-root-uid", "0", "-root-gid", "0", "-root-mode", "0755",
            "-comp", "zstd", "-Xcompression-level", "15",
            "-processors", str(jobs(int(config.get("STRATA_JOBS", "0")))), "-no-xattrs",
            "-mkfs-time", epoch, "-all-time", epoch, "-pf", str(pseudo),
        ]
    )
    digest = sha256_file(temporary)
    final = images / f"{name}-{version}-{digest}.squashfs"
    final.unlink(missing_ok=True)
    temporary.replace(final)
    log(f"component: {final.name}")
    return final


def component_storage_versions(component_conf: dict[str, str]) -> list[dict[str, str | int]]:
    """Return persistent-state compatibility fields needed before an update."""
    storage: list[dict[str, str | int]] = []
    for index in range(int(component_conf.get("storage.count", "0"), 10)):
        prefix = f"storage.{index}."
        storage.append(
            {
                "id": component_conf[prefix + "id"],
                "schema": int(component_conf[prefix + "schema"], 10),
                "lifecycle": component_conf[prefix + "lifecycle"],
            }
        )
    return storage


def write_component_versions(
    config: dict[str, str],
    output: Path,
    built_by_name: dict[str, Path],
    slot: Path,
) -> Path:
    """Write the release-side catalog consumed by future component updaters."""
    components: list[dict[str, object]] = []
    for name, artifact in sorted(
        built_by_name.items(),
        key=lambda item: int(load_data(ROOT / "components" / item[0] / "component.conf")["priority"]),
    ):
        component_conf = load_data(ROOT / "components" / name / "component.conf")
        components.append(
            {
                "name": component_conf["name"],
                "version": component_conf["version"],
                "architecture": config["STRATA_ARCH"],
                "type": component_conf["type"],
                "priority": int(component_conf["priority"], 10),
                "requires": [item for item in component_conf.get("requires", "").split(",") if item],
                "after": [item for item in component_conf.get("after", "").split(",") if item],
                "storage": component_storage_versions(component_conf),
                "artifact": {
                    "path": f"components/{artifact.name}",
                    "sha256": sha256_file(artifact),
                    "size": artifact.stat().st_size,
                },
            }
        )

    catalog = {
        "format": 1,
        "product": "StrataOS",
        "release": {
            "version": config["STRATA_VERSION"],
            "architecture": config["STRATA_ARCH"],
        },
        "slot": {
            "name": "A",
            "components_list": {
                "path": "slots/A/components.list",
                "sha256": sha256_file(slot),
            },
        },
        "components": components,
    }
    destination = output / "components" / "component-versions.json"
    destination.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n")
    destination.with_suffix(".json.sha256").write_text(
        f"{sha256_file(destination)}  {destination.name}\n"
    )
    return destination


def build_components(config_path: Path, output: Path) -> list[Path]:
    config = load(config_path)
    validate(config)
    selected = ["system-core", "kernel-modules", "network", "python", "openssh"]

    if enabled(config, "STRATA_ENABLE_DIAGNOSTICS"):
        selected.append("diagnostics")

    if enabled(config, "STRATA_ENABLE_DOCKER"):
        selected.append("docker")
    if enabled(config, "STRATA_ENABLE_GRAPHICS"):
        selected.append("graphics")
    if enabled(config, "STRATA_ENABLE_CJK_FONTS"):
        selected.append("fonts-cjk")
    if enabled(config, "STRATA_ENABLE_FIREWALL"):
        selected.append("firewall")
    if enabled(config, "STRATA_ENABLE_FAIL2BAN"):
        selected.append("fail2ban")
    shutil.rmtree(output / "components", ignore_errors=True)
    built_by_name: dict[str, Path] = {}
    priorities: dict[str, int] = {}
    for component in selected:
        root, provenance = assemble_component_root(component, output, config)
        built_by_name[component] = package_component(component, root, provenance, output, config)
        priorities[component] = int(load_data(ROOT / "components" / component / "component.conf")["priority"])
    built = [built_by_name[name] for name in sorted(selected, key=lambda item: priorities[item])]
    slot = output / "slot-A"
    shutil.rmtree(slot, ignore_errors=True)
    slot.mkdir(parents=True)
    (slot / "components.list").write_text("".join(f"components/{path.name}\n" for path in built))
    index = [
        {"file": path.name, "sha256": sha256_file(path), "size": path.stat().st_size}
        for path in built
    ]
    (output / "component-index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    catalog = write_component_versions(
        config, output, built_by_name, slot / "components.list"
    )
    log(f"component versions: {catalog}")
    return built
