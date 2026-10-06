# StrataOS

StrataOS is an immutable, modular GNU/Linux distribution compiled from
upstream source code and targeting UEFI Class 3 devices or U-Boot platforms
with extlinux support. The target
system consists of OpenRC, Zsh, musl libc, the LLVM/Clang toolchain,
Linux 6.18, and OpenSSH. Docker and CJK fonts are selectable
components.

This program is free software.  See the file LICENSE for copying
conditions.

## System Architecture

```text
STRATA_BOOTLOADER=limine-efi: UEFI -> Limine -> Linux kernel + initramfs
STRATA_BOOTLOADER=extlinux:   U-Boot -> extlinux.conf -> Linux kernel + initramfs
                                                        |
                                                        v
                        system-core + optional Docker / Graphics / CJK Fonts /
                        Firewall / Fail2ban / Diagnostics component images
                                                        |
                                                        v
                                             OverlayFS -> OpenRC
```

## Build Model

StrataOS employs a self-contained Python build orchestrator with
package recipes expressed in TOML.  The build proceeds through the
following phases:

1.  Download the official LLVM/Clang and CMake prebuilt archives.
2.  Bootstrap an isolated target sysroot from musl source.
3.  Build LLVM runtime libraries (libc++, libc++abi, libunwind).
4.  Build host tools and target packages according to the dependency
    graph declared in `packages/<name>/<name>.toml`.
5.  Install each target package into its own `output/packages/<name>/root`
    and merge development files into the isolated sysroot.
6.  Assemble read-only SquashFS component images from per-component
    `packages.list` files.
7.  Build the Linux package and initramfs through their dedicated stages.
8.  Emit a GPT disk image (ESP + ext4 data partition) using the
    project's own GPT writer.

Every package-specific configure, compile and install option is declared in
its recipe as `configure_args`, `build_args` and `install_args`. Generic and
audited special handlers only expand those declarations and supply the common
toolchain environment; package policy is not hidden in Python build scripts.

The target root filesystem does not borrow libc, shared libraries, or
distribution packages from the build host.  The host machine provides
only the execution environment (Python, make, tar, patch, bison, flex,
and similar fundamental utilities).

Only native same-architecture builds are supported at present:

```text
x86_64 host  -->  x86_64 image
arm64 host   -->  arm64 image
```

## Component System

StrataOS is organized into components: self-contained, read-only
SquashFS images that bundle a functional domain's programs, libraries,
OpenRC services, and configuration.  Each component carries its own
metadata, package provenance, and optional project-authored overlay.

### Core vs. Optional Components

`system-core` is the mandatory base component. It provides the initramfs, C
library, shell, OpenRC, logging and recovery utilities. The kernel image is
booted from the ESP, while loadable drivers are packaged separately in the
mandatory `kernel-modules` component. Network,
Python and OpenSSH are separate default components so they can be updated and
audited independently. SSH starts by default and can be stopped and disabled persistently through
OpenRC.

Additional components are selected at build time via configuration
flags in `.config`:

```text
STRATA_ENABLE_DOCKER=1     Include the Docker container runtime
STRATA_ENABLE_FIREWALL=1   Include nftables and firewall policy
STRATA_ENABLE_FAIL2BAN=1   Include SSH intrusion protection
STRATA_ENABLE_CJK_FONTS=1  Include the Noto Sans CJK font component
STRATA_ENABLE_DIAGNOSTICS=1 Include htop and lsof
STRATA_BOOTLOADER=limine-efi Select the Limine UEFI image (or `extlinux`)
```


When disabled, the corresponding packages are neither fetched nor
compiled, and the disk image excludes their SquashFS images and data
volumes.

### Adding a Custom Component

The component infrastructure is generic.  To add a component:

1.  Create the source directory `components/<name>/` containing:
    - `component.conf` -- declarative metadata (name, version,
      priority, services, storage volumes);
    - `packages.list` -- package recipe names owned by the component;
    - `rootfs/` -- optional project-authored overlay (init scripts,
      configuration, static files);
    - `hooks/` -- optional lifecycle hooks.

2.  Add a configuration flag `STRATA_ENABLE_<NAME>=1` to the defconfig
    files and to the validation list in `scripts/config.py`.

3.  Register the component in `scripts/components.py` function
    `build_components()`:

    ```python
    if enabled(config, "STRATA_ENABLE_DIAGNOSTICS"):
        selected.append("diagnostics")
    ```

4.  If the component declares data volumes, update `scripts/qemu.py`
    function `qemu_disk_mib()` to account for the additional storage.

5.  Add the necessary package recipes to `packages/<name>/<name>.toml`, with
    source metadata in their `[source]` tables.

See `docs/COMPONENTS.md` for the full component format specification
and `docs/CUSTOMIZATION.md` for detailed extension procedures.

## Disk Layout

The default partitioning scheme is GPT:

```text
Partition 1   FAT32 ESP
  EFI boot files
  Linux kernel
  initramfs
  storage.conf / logging.conf / disk.conf

Partition 2   ext4 data partition
  /strataos/components/       read-only component images
  /strataos/slots/            component slot manifests
  /strataos/volumes/          backing files for component-owned data volumes
  /strataos/state/            system writable state
  /strataos/transactions/     component update transactions
```

The current full image is assembled from independently attributed components:

- default base: `system-core`, `kernel-modules`, `network`, `python`, and `openssh`;
- security and diagnostics: `firewall`, `fail2ban`, and `diagnostics`;
- application/runtime: `docker` and `fonts-cjk`.

Optional components are included only when selected by the build configuration.
Each component carries unified metadata, a package provenance list, and a
`rootfs/` tree. Components declare their own data volumes. Published images do
not pre-seed component data images; the initramfs creates them on first
activation and only permits growth thereafter. The current persistent owners
are `system-core` (`/state`), `network` (DHCP leases), `openssh` (host identity),
`fail2ban` (ban database), and `docker`.

Data volume redundancy can be configured as:

- `none` — the default, no redundancy;
- `mirror` — two loop members assembled into MD RAID1;
- `integrity-mirror` — each member passes through dm-integrity before
  MD RAID1 assembly.

When both mirror members reside on the same physical disk, the
configuration does not protect against whole-disk or outer-filesystem
failure.  Important data should place the second member on a separate
backend and retain independent backups.  See `docs/STORAGE.md`.

## Logging

Logging spans three stages: build-time, initramfs, and OpenRC.

- `output/logs/build.log`
- `/run/strataos/early-boot.log`
- `/var/log/boot/<boot-id>-*.log`
- `/var/log/messages`

Boot logs record partition growth, component verification,
loop/RAID/dm-integrity assembly, filesystem checks, and filesystem
resize operations.  See `docs/LOGGING.md`.

## Building

### Prerequisites (Ubuntu 24.04)

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 make patch perl rsync file unzip bc bison flex gettext gperf cpio \
  gzip pigz bzip2 pbzip2 xz-utils gawk sed findutils tar which xsltproc docbook-xsl \
  zlib1g libstdc++6 g++ groff-base
```

Source extraction normalizes archive members whose paths begin with
`./package-version/`.  GNU tar counts the leading `.' toward
`--strip-components`; the builder detects a sole remaining directory
matching the archive name and atomically collapses it, ensuring that
Meson, CMake, and Autotools always start from the genuine source root.

Autotools packages prefer upstream release tarballs over auto-generated
VCS snapshots.  Release tarballs must include a pre-generated
`configure` script; for example, procps-ng uses SourceForge's
`procps-ng-<version>.tar.xz`, avoiding extra Autoconf, Automake,
Gettext, or Libtool bootstrap dependencies before the source-aware
preflight phase.

When parallelism exceeds one, the builder applies the same thread count
to source extraction.  LLVM, LLVM source, and Linux `.tar.xz` archives
are decompressed with `xz -T<N>`; CMake, musl, and other `.tar.gz`
archives with `pigz -p <N>`.  `.tar.bz2` archives are decompressed in
parallel when `pbzip2` or `lbzip2` is installed.  The toolchain build
requires the host to provide `pigz` when using `make -j$(nproc)`,
avoiding a fallback to single-threaded gzip.

### x86_64

```bash
make x86_64_defconfig
make check
make preflight
make source-lock
make -j$(nproc)
```

### arm64

```bash
make arm64_defconfig
make check
make preflight
make source-lock
make -j$(nproc)
```

An unadorned `make` runs `make preflight` before toolchain compilation,
downloading the selected sources and verifying all Autotools, CMake,
Meson, and special recipe parameters.  `make source-lock` records
SHA-256 hashes for version-pinned archives. A formal release build should
commit and review the updated recipe TOMLs. Build parameter
auditing is described in `docs/BUILD_PARAMETER_AUDIT.md`.

The BusyBox configuration does not depend on the Linux kernel's
`scripts/config`.  The builder starts from `allnoconfig`, merges
`packages/busybox/configs/busybox.fragment` directly, runs `olddefconfig`, and
then verifies every resulting Kconfig value item by item.  If an
upstream dependency forces an option off, the build fails before
BusyBox compilation begins.

Top-level stages are serialized because they share the sysroot and
output directories.  The `-jN` argument is forwarded to package
compilation, LLVM runtime build, Linux kernel build, Ninja/CMake
invocations, and SquashFS creation.  `STRATA_JOBS=0` in the default
configuration inherits the `make -jN` value; when no `-jN` is passed,
the build uses the number of online CPUs.

### Build Targets

```text
make toolchain        Bootstrap LLVM, musl, and LLVM runtime
make packages         Build the StrataOS package dependency graph
make kernel           Build the Linux kernel
make components       Assemble SquashFS components
make initramfs        Build the early-userspace initramfs
make image            Generate the GPT disk image
make qemu             Boot a copy-on-write image in QEMU
make clean            Remove output (download cache preserved)
make dist             Create a reproducible source archive
```

### Output Layout

```text
output/toolchain/                     Isolated LLVM/musl toolchain & sysroot
output/host/                          Host tools built from source
output/packages/<name>/root/          Per-package isolated install root
output/kernel/kernel                  Linux kernel image
output/components/*.squashfs          Component images
output/initramfs/initramfs.cpio.gz    Early userspace
output/images/strataos-<ver>-*.img    GPT disk image
output/logs/build.log                 Build log
output/reports/build-parameter-audit.json
output/reports/effective-build-parameters/*.json
output/reports/generated-build-plans/*.json
```

## Build Resumption

The build system implements two levels of incremental construction.

**Package-level caching** is automatic.  Before building a package,
the builder computes a fingerprint (SHA-256 over the recipe, patches,
build scripts, toolchain marker, and full dependency chain).  If the
stamp file `output/packages/<name>/.complete` exists and matches the
current fingerprint, the package is skipped entirely.  This avoids
rebuilding unchanged packages across invocations.

**Build-directory resumption** requires the `--resume` flag.
Without it, every package starts from a clean build directory.  With
`--resume`, if a previous build failed partway through, the builder
preserves the incomplete build tree so that `make` or `cmake --build`
can continue from the point of interruption.

Build progress is recorded in `output/reports/package-build-state.json`:

```json
{
  "format": 1,
  "requested": ["zlib", "openssl", "curl", "..."],
  "completed": ["zlib", "openssl"],
  "status": "building",
  "current": "curl",
  "resume": false
}
```

Usage:

```bash
# Normal build (clean directory per package; cached packages skipped)
make packages

# Resume mode (reuse incomplete build directories)
python3 scripts/build.py --config .config --output output packages --resume
```

`make clean` removes the output tree while preserving the download
cache.  The granularity is per-package, not per-file: within a single
package, incremental compilation relies on the underlying build
system's own logic (make, cmake, ninja).

## Configuration Entry Points

- `defconfigs/x86_64_defconfig` / `defconfigs/arm64_defconfig` -- target
  architecture, version, and component enable flags
  (`STRATA_ENABLE_DOCKER`,
  `STRATA_ENABLE_FIREWALL`, `STRATA_ENABLE_FAIL2BAN`,
  `STRATA_ENABLE_CJK_FONTS`, `STRATA_ENABLE_DIAGNOSTICS`)
- `configs/image/disk.conf` -- partition layout and sizing
- `configs/runtime/storage.conf` -- volume backend and redundancy policy
- `configs/runtime/logging.conf` -- log persistence and rotation
- `configs/kernel/<arch>/kernel.config` -- Linux kernel configuration
- `packages/<name>/<name>.toml` -- package recipes, including Linux
- `components/*/component.conf` -- component metadata and storage
  declarations
- `components/*/packages.list` -- package-to-component ownership
- `packages/busybox/configs/busybox.fragment` -- BusyBox applet selection

See `docs/CUSTOMIZATION.md` for procedures to add packages, components,
kernel options, and initramfs modifications.

## Security Posture

The image has no pre-created `strata` account and embeds no SSH public
keys.  Initial console or SSH access uses `root` with the temporary
password `strata`.  The first interactive login requires changing that
password and creating a named administrator account. OpenSSH is a default
standalone component; root and password login stay enabled so the administrator
can recover the system, while its boot service can be controlled through OpenRC.
Component file
names embed a full SHA-256 digest, and the slot manifest records
component paths.  The current format does not yet provide publisher
signatures, Secure Boot, dm-verity, or anti-rollback protection.

## Validation Status

The project includes tests for configuration, recipe DAG correctness, source
option preflight, build-system compile probes, ELF dependency closure, component
schema, shell syntax, kernel required symbols, the GPT writer, and storage
policies. ARM64 builds, real-device testing, storage corruption injection, and
recovery drills remain release work. See `docs/VALIDATION.md`.
