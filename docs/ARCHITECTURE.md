# StrataOS Architecture

This document describes the architecture of the StrataOS system,
covering the build pipeline, package isolation, target compilation
environment, boot sequence, and immutability boundaries.

## Design Constraints

The core constraints of StrataOS are:

1.  The target system's runtime libraries are isolated from the Ubuntu
    build host.  No host libc, shared library, or distribution binary
    enters the target image.
2.  All target software originates from fixed upstream source archives
    or official prebuilt toolchain releases. Each package and toolchain input
    owns its source metadata and SHA-256 lock.
3.  Components are read-only and carry their own data volumes.  The
    outer data partition is writable, but component root filesystems
    are immutable SquashFS images.
4.  The build entry point is simple, automated, and requires no
    external distribution build tree or package database.
5.  The base image is headless. It includes no display server, desktop,
    remote framebuffer service, or GPU userspace; system administration uses
    the serial console or OpenSSH.

## Build Pipeline

```text
                    STRATAOS  BUILD  PIPELINE

                package and toolchain TOML sources
                               |
                               v
                +--------------+--------------+
                |         fetch.py           |
                |  download, cache, SHA-256  |
                |  lock for all sources      |
                +--------------+--------------+
                               |
                               v
                +--------------+--------------+
                |   bootstrap_toolchain.py    |
                |  LLVM/Clang + musl libc     |
                |  LLVM runtime libraries     |
                +--------------+--------------+
                               |
                  +------------+------------+
                  |                         |
                  v                         v
        +---------+---------+    +----------+---------+
        |  package_builder   |    |    package_builder  |
        |  (host recipes)    |    |  (target recipes)   |
        +---------+---------+    +----------+---------+
                  |                         |
                  v                         v
        +---------+---------+    +----------+---------+
        |   output/host/     |    | output/packages/   |
        |  ninja, pkgconf,   |    | <name>/root/       |
        |  mksquashfs,       |    | merged to sysroot  |
        |  e2fsprogs, etc.   |    |                     |
        +---------+---------+    +----------+---------+
                                             |
                                             v
                                  +----------+---------+
                                  |    kernel.py        |
                                  |  Linux 6.18 build   |
                                  +----------+---------+
                                             |
                                  +----------+---------+
                                  |   components.py     |
                                  |  SquashFS assembly  |
                                  +----------+---------+
                                             |
                                  +----------+---------+
                                  |   initramfs.py      |
                                  |  newc cpio archive  |
                                  +----------+---------+
                                             |
                                  +----------+---------+
                                  |     image.py        |
                                  |  native GPT writer  |
                                  |  ESP + ext4 image   |
                                  +----------+---------+
                                             |
                                             v
                                  output/images/
                                  strataos-<ver>-<arch>.img
```

### Build Scripts

The builder is composed of the following project-internal scripts:

- `scripts/fetch.py` — download, caching, and source locking;
- `scripts/bootstrap_toolchain.py` — LLVM, musl, and LLVM runtime
  bootstrap;
- `scripts/package_builder.py` — recipe parsing, topological sort,
  build execution, and sysroot merging;
- `scripts/kernel.py` — Linux kernel build and final configuration
  verification;
- `scripts/components.py` — component attribution, metadata, and
  SquashFS image creation;
- `scripts/initramfs.py` — early userspace construction and newc
  archive generation;
- `scripts/image.py` — ESP, ext4, and GPT disk image assembly;
- `scripts/build.py` — top-level stage orchestration and build logging.

### Build Resumption

The builder supports incremental construction at the package level.
Before building a package, it computes a cryptographic fingerprint
from the recipe, patches, build scripts, toolchain marker, and
dependency chain.  If the stamp file matches, the package is skipped.

The `--resume` flag additionally preserves incomplete build directories
so that a failed `make` or `cmake --build` invocation can continue from
the point of interruption rather than restarting from scratch.

Build progress is recorded in `output/reports/package-build-state.json`
for external monitoring.

## Package Isolation

Each target package uses a private directory:

```text
output/package-work/<name>/          build directory
output/packages/<name>/root/         install root (DESTDIR)
output/packages/<name>/package.env   effective build parameters
```

Installation steps must use `DESTDIR` or an equivalent mechanism.  No
package may write directly to the host `/usr`.  After installation,
development and runtime files are merged into
`output/toolchain/sysroot` for subsequent packages to link against.
Component assembly reads only from isolated package install roots, not
from the host root.

Recipes support `autotools`, `cmake`, `meson`, and project-internal
audited special handlers.  The dependency graph uses deterministic
topological ordering and rejects missing dependencies and cycles.

## Target Compilation Environment

The target C and C++ compiler wrappers set explicitly:

- the target triple (e.g., `x86_64-linux-musl`);
- the musl sysroot;
- LLD as the linker;
- libc++, libc++abi, and libunwind as the C++ runtime;
- compilation flags consistent with the target architecture.

The host prebuilt LLVM serves only as a bootstrap compiler; it does
not leak host libc into the target system.  A formal release build
must confirm via ELF dynamic dependency audit that every target
program refers only to the permitted interpreters and libraries within
the target sysroot.

## Boot Architecture

`STRATA_BOOTLOADER` selects exactly one boot path while the image is built:

- `limine-efi` (the default) has UEFI firmware load Limine from the ESP, then
  Limine loads the Linux kernel and initramfs.
- `extlinux` provides `/extlinux/extlinux.conf` for U-Boot `bootstd` or
  `sysboot` to load the same kernel and initramfs. This image has no EFI
  executable or Limine configuration.

After either loader starts the kernel, the initramfs performs the following
sequence:

1.  Locate the ESP and data partitions by filesystem label;
2.  If necessary, grow the trailing data partition and its outer ext4
    filesystem;
3.  Read the active component slot;
4.  Verify component integrity (full SHA-256) and target architecture;
5.  Mount SquashFS component images read-only, ordered by priority;
6.  Create or assemble data volumes according to component declarations;
7.  Construct a writable root filesystem using OverlayFS. The initramfs uses
    compact internal aliases for its `lowerdir` list so BusyBox's mount-option
    buffer is not exhausted as the number of components grows;
8.  Mount component data volumes at their declared paths;
9.  `switch_root` to OpenRC.

## Immutability Boundaries

Immutability applies to component SquashFS images.  The outer data
partition must remain writable because it hosts component slots,
transactions, OverlayFS state, and loop-backed data volumes.
Component hashes detect accidental modification but are not a
substitute for origin authentication.  Production deployments require
component signing and a trusted boot chain.
