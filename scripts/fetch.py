#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import urllib.error
import urllib.request
from pathlib import Path

from common import BuildError, atomic_write, download, jobs, log, sha256_file
from recipes import Source, all_source_inputs


def expand(source: Source, version: str) -> str:
    try:
        return source.url.format(version=version)
    except (KeyError, ValueError) as exc:
        raise BuildError(f"invalid source URL template {source.url!r}") from exc


def source_filename(source: Source, version: str) -> str:
    if source.filename is None:
        return expand(source, version).rsplit("/", 1)[-1]
    try:
        return source.filename.format(version=version)
    except (KeyError, ValueError) as exc:
        raise BuildError(f"invalid source filename template {source.filename!r}") from exc


def fetch_source(source: Source, version: str, dl: Path) -> Path:
    return download(
        expand(source, version), dl / source_filename(source, version), source.sha256
    )


def inventory_entries(arch: str) -> list[tuple[str, Source, str]]:
    entries: list[tuple[str, Source, str]] = []
    for item in all_source_inputs():
        source = item.source_for_arch(arch)
        entries.append((item.name, source, item.version))
    if not entries:
        raise BuildError(f"source inventory contains no entries for architecture {arch}")
    return entries


def probe_source(label: str, source: Source, version: str, dl: Path) -> str:
    url = expand(source, version)
    cached = dl / source_filename(source, version)
    if cached.exists():
        if source.sha256 and sha256_file(cached) != source.sha256:
            raise BuildError(f"cached source checksum mismatch: {label}: {cached}")
        log(f"source probe cached: {label}: {cached.name}")
        return url
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "StrataOS-builder/0.3",
            "Range": "bytes=0-0",
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read(1)
    except Exception as exc:
        raise BuildError(f"source URL unavailable: {label}: {url}: {exc}") from exc
    log(f"source probe passed: {label}: {url}")
    return url


def probe_inventory(arch: str, dl: Path, parallelism: int) -> None:
    dl.mkdir(parents=True, exist_ok=True)
    entries = inventory_entries(arch)
    failures: list[str] = []
    workers = max(1, min(parallelism, 8, len(entries)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(probe_source, label, source, version, dl): label
            for label, source, version in entries
        }
        for future in as_completed(futures):
            label = futures[future]
            try:
                future.result()
            except (BuildError, OSError) as exc:
                failures.append(f"{label}: {exc}")
    if failures:
        raise BuildError("source availability probe failed:\n" + "\n".join(sorted(failures)))
    log(f"source availability probe passed for {len(entries)} archives ({arch})")


def _lock_entries() -> list[tuple[Path, str, Source, str]]:
    entries: list[tuple[Path, str, Source, str]] = []
    for item in all_source_inputs():
        if item.source.default is not None:
            entries.append((item.path, "source", item.source.default, item.version))
        for arch, source in sorted(item.source.by_arch.items()):
            entries.append((item.path, f"source.{arch}", source, item.version))
    return entries


def _write_source_hashes(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text().splitlines()
    output: list[str] = []
    current = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        match = re.match(r"\[([^]]+)]", line.strip())
        if match:
            current = match.group(1)
        if current in updates and line.strip().startswith("sha256 ="):
            index += 1
            continue
        output.append(line)
        if current in updates and line.strip().startswith("url ="):
            output.append(f'sha256 = "{updates[current]}"')
        index += 1
    atomic_write(path, "\n".join(output) + "\n")


def update_lock() -> None:
    updates: dict[Path, dict[str, str]] = {}
    for path, section, source, version in _lock_entries():
        url = expand(source, version)
        log(f"hashing {path.relative_to(path.parents[2]) if len(path.parents) > 2 else path}:{section}: {url}")
        with urllib.request.urlopen(url) as response:
            digest = hashlib.sha256()
            for chunk in iter(lambda: response.read(1024 * 1024), b""):
                digest.update(chunk)
        updates.setdefault(path, {})[section] = digest.hexdigest()
    for path, values in updates.items():
        _write_source_hashes(path, values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-lock", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--arch")
    parser.add_argument("--dl", type=Path)
    parser.add_argument("--jobs", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.update_lock:
            update_lock()
            return
        if not args.probe or not args.arch or not args.dl:
            parser.error("choose --update-lock or --probe with --arch and --dl")
        probe_inventory(args.arch, args.dl, jobs(args.jobs))
    except (BuildError, OSError, urllib.error.URLError) as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
