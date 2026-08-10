# StrataOS package recipes

Each `packages/<name>/<name>.toml` file is a project-owned build recipe.
Package-local inputs live beside it under `configs/` and `patches/` when
needed. A recipe declares:

- package name and fixed version;
- a `[source]` table with URL, optional SHA-256, archive type and extraction
  policy; architecture-specific sources use `[source.x86_64]` and
  `[source.arm64]`;
- host or target kind;
- direct dependencies;
- build system and configure arguments;
- optional reviewed `NAME=value` environment overrides, with build-context expansion;
- optional reviewed source patches from the package's `patches/`, applied
  after extraction;
- optional reviewed special handler.

The package builder validates the complete dependency graph, rejects cycles,
builds in topological order, installs each target package into an isolated
DESTDIR and merges it into the musl sysroot only after successful completion.

Recipes are deliberately declarative. Package-specific shell logic belongs in a
small named handler in `scripts/package_builder.py`, where it can be tested and
audited. No external distribution package definition or root filesystem output
is consumed.

Linux follows the same ownership model in `packages/linux/`; its recipe owns
the kernel version and source selection, while architecture seed configs live
in `configs/kernel/`.
