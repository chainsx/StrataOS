#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Iterable, Mapping, Sequence, TextIO

ROOT = Path(__file__).resolve().parents[1]
_BUILD_LOG: Path | None = None


class BuildError(RuntimeError):
    pass


def configure_build_log(path: Path | None) -> None:
    global _BUILD_LOG
    _BUILD_LOG = path
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n=== StrataOS build invocation ===\n")


def _append_log(text: str) -> None:
    if _BUILD_LOG is None:
        return
    with _BUILD_LOG.open("a", encoding="utf-8", errors="replace") as handle:
        handle.write(text)
        if text and not text.endswith("\n"):
            handle.write("\n")


def log(message: str) -> None:
    line = f"[StrataOS] {message}"
    print(line, flush=True)
    _append_log(line)


def _render(command: Sequence[str] | str) -> str:
    if isinstance(command, str):
        return command
    return shlex.join(str(item) for item in command)


def _makeflags_without_parallelism(value: str) -> str:
    """Remove inherited jobserver and -j options from GNU MAKEFLAGS.

    StrataOS invokes package makefiles through Python rather than through a
    recursive $(MAKE) recipe.  Explicitly parallel child makes therefore use
    their own bounded jobserver; serial configure/install makes must not
    accidentally inherit the top-level jobserver.
    """
    try:
        tokens = shlex.split(value)
    except ValueError:
        return ""
    kept: list[str] = []
    skip_next = False
    for index, token in enumerate(tokens):
        if skip_next:
            skip_next = False
            continue
        if token in {"-j", "--jobs"}:
            if index + 1 < len(tokens) and tokens[index + 1].isdigit():
                skip_next = True
            continue
        if token.startswith("-j") or token.startswith("--jobs="):
            continue
        if token.startswith("--jobserver-auth=") or token.startswith("--jobserver-fds="):
            continue
        kept.append(token)
    return shlex.join(kept)


def _is_make_command(command: Sequence[str] | str) -> bool:
    if isinstance(command, str) or not command:
        return False
    return Path(str(command[0])).name in {"make", "gmake"}


def _is_cmake_build_command(command: Sequence[str] | str) -> bool:
    if isinstance(command, str) or not command:
        return False
    return Path(str(command[0])).name == "cmake" and "--build" in [str(x) for x in command[1:]]


def _drop_make_recursion_environment(merged: dict[str, str]) -> None:
    # These commands are launched by Python, not by a recursive $(MAKE) recipe.
    # An explicit -j/--parallel value creates the child scheduler, so retaining
    # the parent's jobserver descriptors or MAKELEVEL is both invalid and noisy.
    for variable in ("MAKEFLAGS", "GNUMAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKE_RESTARTS"):
        merged.pop(variable, None)


def run(
    command: Sequence[str] | str,
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    cmd = command if isinstance(command, str) else [str(x) for x in command]
    rendered = _render(command)
    log("+ " + rendered)
    merged = os.environ.copy()
    if env:
        merged.update({str(k): str(v) for k, v in env.items()})
    if _is_make_command(command):
        for variable in ("MAKEFLAGS", "GNUMAKEFLAGS"):
            cleaned = _makeflags_without_parallelism(merged.get(variable, ""))
            if cleaned:
                merged[variable] = cleaned
            else:
                merged.pop(variable, None)
        # Direct make invocations retain harmless presentation flags but must
        # not inherit the top-level recursion state.
        for variable in ("MFLAGS", "MAKELEVEL", "MAKE_RESTARTS"):
            merged.pop(variable, None)
    elif _is_cmake_build_command(command):
        # CMake's Makefiles generator launches gmake itself.  Passing both the
        # parent's jobserver and --parallel causes gmake to reset jobserver mode.
        _drop_make_recursion_environment(merged)
    try:
        if capture:
            completed = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=merged,
                shell=isinstance(cmd, str),
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )
            if completed.stdout:
                _append_log(completed.stdout)
            if check and completed.returncode != 0:
                raise subprocess.CalledProcessError(
                    completed.returncode, cmd, output=completed.stdout
                )
            return completed

        if _BUILD_LOG is None:
            return subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                env=merged,
                shell=isinstance(cmd, str),
                check=check,
                text=True,
            )

        process = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=merged,
            shell=isinstance(cmd, str),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        assert process.stdout is not None
        with _BUILD_LOG.open("a", encoding="utf-8", errors="replace") as build_log:
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                build_log.write(line)
                build_log.flush()
        returncode = process.wait()
        if check and returncode != 0:
            raise subprocess.CalledProcessError(returncode, cmd)
        return subprocess.CompletedProcess(cmd, returncode)
    except FileNotFoundError as exc:
        first = cmd[0] if isinstance(cmd, list) else rendered.split()[0]
        raise BuildError(f"command not found: {first}") from exc
    except subprocess.CalledProcessError as exc:
        raise BuildError(
            f"command failed with status {exc.returncode}: {rendered}"
        ) from exc


def require_commands(names: Iterable[str]) -> None:
    missing = [name for name in names if shutil.which(name) is None]
    if missing:
        raise BuildError("missing bootstrap commands: " + ", ".join(missing))


def host_arch() -> str:
    raw = platform.machine().lower()
    if raw in {"x86_64", "amd64"}:
        return "x86_64"
    if raw in {"aarch64", "arm64"}:
        return "arm64"
    raise BuildError(f"unsupported host architecture: {raw}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path, sha256: str | None = None) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not sha256 or sha256_file(destination) == sha256:
            return destination
        destination.unlink()
    tmp = destination.with_suffix(destination.suffix + ".part")
    log(f"downloading {url}")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "StrataOS-builder/0.2"})
        with urllib.request.urlopen(request) as response, tmp.open("wb") as output:
            shutil.copyfileobj(response, output)
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise BuildError(f"download failed: {url}: {exc}") from exc
    tmp.replace(destination)
    if sha256:
        actual = sha256_file(destination)
        if actual != sha256:
            destination.unlink(missing_ok=True)
            raise BuildError(
                f"sha256 mismatch for {destination.name}: {actual} != {sha256}"
            )
    return destination


_EXTRACTION_SCHEMA = 4


def _archive_compression(archive: Path) -> str | None:
    name = archive.name.lower()
    if name.endswith((".tar.xz", ".txz")):
        return "xz"
    if name.endswith((".tar.gz", ".tgz")):
        return "gzip"
    if name.endswith((".tar.bz2", ".tbz2", ".tbz")):
        return "bzip2"
    if name.endswith((".tar.zst", ".tar.zstd", ".tzst")):
        return "zstd"
    if name.endswith(".tar"):
        return None
    return "auto"


def _parallel_decompressor(archive: Path, parallelism: int) -> tuple[list[str] | None, bool]:
    """Return a tar decompressor command and whether it is parallel.

    GNU tar still serializes archive member creation, but the expensive
    decompression stream is delegated to a threaded implementation whenever
    one is available.  LLVM and Linux are distributed as .tar.xz, for which
    xz's own threaded decoder is always used.
    """
    count = max(1, parallelism)
    compression = _archive_compression(archive)
    if compression is None or compression == "auto":
        return None, False
    if compression == "xz":
        executable = shutil.which("xz")
        return ([executable, "-dc", f"-T{count}"] if executable else None, count > 1)
    if compression == "gzip":
        pigz = shutil.which("pigz")
        if pigz:
            return [pigz, "-dc", "-p", str(count)], count > 1
        gzip = shutil.which("gzip")
        return ([gzip, "-dc"] if gzip else None, False)
    if compression == "bzip2":
        pbzip2 = shutil.which("pbzip2")
        if pbzip2:
            return [pbzip2, "-dc", f"-p{count}"], count > 1
        lbzip2 = shutil.which("lbzip2")
        if lbzip2:
            return [lbzip2, "-dc", "-n", str(count)], count > 1
        bzip2 = shutil.which("bzip2")
        return ([bzip2, "-dc"] if bzip2 else None, False)
    if compression == "zstd":
        zstd = shutil.which("zstd")
        return ([zstd, "-dc", f"-T{count}"] if zstd else None, count > 1)
    return None, False


_FIXTURE_DIRECTORY_NAMES = frozenset({
    "test", "tests", "testing", "sample", "samples", "fixture", "fixtures",
    "testdata", "test-data",
})


def _is_fixture_path(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    return any(part.lower() in _FIXTURE_DIRECTORY_NAMES for part in relative.parts[:-1])


def _external_fixture_target_is_inert(target: Path) -> bool:
    if os.path.lexists(target):
        return False
    # Permit /nonexistent-style test fixtures, but not links below existing
    # host directories such as /tmp, /home or /usr.  The first existing parent
    # must be the filesystem root, so a later package step cannot accidentally
    # turn the link into access to a writable host location.
    current = target.parent
    while not os.path.lexists(current) and current != current.parent:
        current = current.parent
    return current == Path(target.anchor)


def _validate_extracted_tree(destination: Path) -> None:
    """Reject external links except inert broken links in test fixtures.

    Source archives occasionally carry deliberately invalid links as parser or
    validation fixtures.  AppStream, for example, includes an absolute link to
    /nonexistent under tests/samples.  Such a leaf link is inert when its target
    does not exist below any writable host directory.  Links outside fixture
    trees, or fixture links below existing host paths, remain fatal.
    """
    root = destination.resolve()
    for path in destination.rglob("*"):
        if not path.is_symlink():
            continue
        raw_target = os.readlink(path)
        target = (path.parent / raw_target).resolve()
        if target == root or root in target.parents:
            continue
        if _is_fixture_path(path, root) and _external_fixture_target_is_inert(target):
            log(f"allowing inert fixture symlink: {path.relative_to(root)} -> {raw_target}")
            continue
        raise BuildError(f"unsafe extracted symlink: {path} -> {raw_target}")


def _archive_payload_name(archive: Path) -> str:
    """Return the expected top-level directory name for a tar archive."""
    name = archive.name
    for suffix in (
        ".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst", ".tar.zstd",
        ".tgz", ".txz", ".tbz2", ".tbz", ".tzst", ".tar",
    ):
        if name.lower().endswith(suffix):
            return name[:-len(suffix)]
    return archive.stem


def _collapse_redundant_archive_root(
    staging: Path, archive: Path, strip_components: int
) -> bool:
    """Collapse a package root left behind by a leading ``./`` tar member.

    GNU tar counts the leading ``.`` in members such as
    ``./AppStream-1.0.4/meson.build`` as a component.  Consequently,
    ``--strip-components=1`` removes only ``.`` and leaves the package root in
    place.  When extraction produced exactly that archive-named directory,
    replace the staging directory with its contents without decompressing the
    archive a second time.
    """
    if strip_components <= 0:
        return False
    entries = list(staging.iterdir())
    if len(entries) != 1:
        return False
    candidate = entries[0]
    if candidate.is_symlink() or not candidate.is_dir():
        return False
    if candidate.name.casefold() != _archive_payload_name(archive).casefold():
        return False

    replacement = staging.parent / f"{staging.name}.normalized"
    if replacement.exists():
        shutil.rmtree(replacement)
    candidate.replace(replacement)
    staging.rmdir()
    replacement.replace(staging)
    log(f"collapsed redundant archive root: {candidate.name}")
    return True


def extract(
    archive: Path,
    destination: Path,
    *,
    strip_components: int = 1,
    parallelism: int | None = None,
) -> Path:
    if strip_components < 0:
        raise BuildError("strip_components must be non-negative")
    effective_jobs = max(1, parallelism if parallelism is not None else jobs(0))
    marker = destination / ".strata-extracted"
    fingerprint = (
        f"{sha256_file(archive)} strip={strip_components} "
        f"schema={_EXTRACTION_SCHEMA}\n"
    )
    if marker.exists() and marker.read_text() == fingerprint:
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.extract-", dir=destination.parent))
    decompressor, threaded = _parallel_decompressor(archive, effective_jobs)
    compression = _archive_compression(archive) or "tar"
    if threaded:
        log(f"extracting {archive.name}: {compression} decompression with {effective_jobs} threads")
    elif compression in {"gzip", "bzip2", "zstd"} and effective_jobs > 1:
        log(
            f"extracting {archive.name}: serial {compression} fallback; "
            "install pigz/pbzip2/lbzip2/zstd for threaded decompression"
        )
    else:
        log(f"extracting {archive.name}: {compression}")

    command = [
        "tar", "--extract", "--file", str(archive),
        "--directory", str(staging),
        f"--strip-components={strip_components}",
        "--no-same-owner", "--no-same-permissions",
        "--delay-directory-restore",
    ]
    if decompressor:
        command.extend(["--use-compress-program", shlex.join(decompressor)])
    try:
        run(command)
        _collapse_redundant_archive_root(staging, archive, strip_components)
        _validate_extracted_tree(staging)
        (staging / ".strata-extracted").write_text(fingerprint)
        if destination.exists():
            shutil.rmtree(destination)
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return destination


def atomic_write(path: Path, text: str, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temp = Path(handle.name)
    temp.chmod(mode)
    temp.replace(path)


def copytree_clean(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=True)


def available_cpu_count() -> int:
    """Return CPUs available to this process, respecting affinity when possible."""
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except (AttributeError, OSError):
        return max(1, os.cpu_count() or 1)


def jobs_from_makeflags(value: str | None = None) -> int | None:
    """Return the explicit GNU make -j value, when one was supplied."""
    raw = os.environ.get("MAKEFLAGS", "") if value is None else value
    try:
        tokens = shlex.split(raw)
    except ValueError:
        return None
    for index, token in enumerate(tokens):
        if token.startswith("--jobs="):
            number = token.split("=", 1)[1]
        elif token == "--jobs" and index + 1 < len(tokens):
            number = tokens[index + 1]
        elif token.startswith("-j") and token != "-j":
            number = token[2:]
        elif token == "-j":
            if index + 1 < len(tokens) and tokens[index + 1].isdigit():
                number = tokens[index + 1]
            else:
                return available_cpu_count()
        else:
            continue
        if number.isdigit() and int(number, 10) > 0:
            return int(number, 10)
    return None


def jobs(configured: int, makeflags: str | None = None) -> int:
    """Resolve compilation parallelism.

    A positive STRATA_JOBS is an explicit project override.  Otherwise inherit
    the top-level ``make -jN`` setting, falling back to the online CPU count.
    """
    if configured > 0:
        return configured
    inherited = jobs_from_makeflags(makeflags)
    if inherited is not None:
        return inherited
    return available_cpu_count()


def die(message: str) -> "None":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(2)
