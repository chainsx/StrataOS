# Build Instructions

See [Kernel requirements by component](KERNEL_REQUIREMENTS.md) and the
[package/build-parameter audit](PACKAGE_AUDIT.md) when adding packages or an
arm64 board target.

## Principles

The StrataOS builder maintains its own source inventory, package
recipes, dependency graph, sysroot, component generator, and disk
image generator.  It does not consume binary packages or build outputs
from other distributions.

The host machine's installed software serves only to execute the
build.  Target files may only originate from:

- upstream archives pinned in the corresponding package or toolchain TOML;
- project-internal configuration, patches, and runtime files;
- target artifacts produced during the build process.

## Host Preparation

On an Ubuntu 24.04 system, install the prerequisite packages:

```bash
sudo apt-get update
sudo apt-get install -y \
  python3 make patch perl rsync file unzip bc bison flex gettext gperf cpio \
  gzip pigz bzip2 pbzip2 xz-utils gawk sed findutils tar which xsltproc docbook-xsl \
  zlib1g libstdc++6 g++ groff-base
```

The builder requires Python 3.11 or later.  Verify with
`python3 --version`.

The `pigz` package enables parallel decompression of `.tar.gz`
archives when building with `make -j$(nproc)`.  The `pbzip2` package
provides the same for `.tar.bz2` archives.  Without these, extraction
falls back to single-threaded operation.

## Source Preparation

Before building, the project must be configured for the target
architecture.

### x86_64

```bash
make x86_64_defconfig
```

### arm64

```bash
make arm64_defconfig
```

The defconfig target writes `STRATA_ARCH` and related variables to
`.config`.  This file is read by every subsequent build step.

## Preflight Checks

Run the static validation suite before downloading sources or
compiling:

```bash
make check
```

This executes configuration validation, recipe audit, and unit tests.
It does not require network access or previously downloaded sources.

To download the selected sources and verify their availability:

```bash
make preflight
```

This fetches every package and toolchain source selected for the configured
architecture and caches them in `output/dl/`.

To record SHA-256 hashes of the downloaded archives for reproducible
builds:

```bash
make source-lock
```

This updates `[source]` / `[source.<arch>]` `sha256` fields in the owning
recipe TOMLs. A formal release build should commit the reviewed updates.

## Compilation

The default target builds everything and produces a bootable disk
image:

```bash
make -j$(nproc)
```

Individual stages can be built separately:

```text
make toolchain        Bootstrap LLVM, musl, and LLVM runtime
make packages         Build the StrataOS package dependency graph
make kernel           Build the Linux kernel
make components       Assemble SquashFS components
make initramfs        Build the early-userspace initramfs
make image            Generate the GPT disk image
```

Package recipes are the single source of package-specific build policy and
source metadata. Each `[source]` table records the HTTPS download URL and
optional SHA-256 lock; `[source.x86_64]` and `[source.arm64]` select an
architecture-specific archive when necessary. Build phases are declared in
`packages/<name>/<name>.toml`:

```toml
configure_args = ["--disable-static"]
build_args = ["-j{jobs}"]
test_args = ["make check"]
install_args = ["DESTDIR={destdir}", "install"]
```

The exact values depend on the upstream build system. Generic and special
handlers expand the recipe placeholders and add only common cross-toolchain
state. Adding a compile target, feature switch, install target, prefix or
linker option directly to a Python handler is rejected by project review and
the recipe checks for option-bearing special packages.

## Target Optimization Policy

`configs/build/x86_64.conf` and `configs/build/arm64.conf` own the target
compiler policy independently. The default is `-O2`, ThinLTO,
function/data section splitting with linker garbage collection, PIC, stack
protection and FORTIFY. ThinLTO must be present at both compile and link time;
the builder applies it to Autotools, CMake and Meson target builds.

The images deliberately leave `cpu_flags` empty. Do not set native tuning flags
such as `-march=native`, `-mtune=native` or `-mcpu=native`: an image must boot
on every supported CPU in its architecture class. Board-specific optimization
belongs in a separately maintained target policy after its CPU baseline has
been defined and tested.

Some upstream projects cannot link with LTO because of assembler symbol-version
semantics. A target recipe may set `lto = "none"`, `"thin"` or `"full"` as a
reviewed exception. This keeps the exception declarative rather than adding
package-name branches to the builder.

Project-local packages use `build_system = "local"` and declare all three
commands in their TOML recipe. The generic builder exports `STRATA_BUILD_DIR`
and `STRATA_DESTDIR`; package-local scripts implement the declared operations.

The `-jN` flag controls parallelism for package compilation, LLVM
runtime build, Linux kernel build, Ninja/CMake invocations, and
SquashFS creation.  The default configuration (`STRATA_JOBS=0`)
inherits the value from `make -jN`; when no `-jN` is supplied, the
build uses the number of online CPUs.

## QEMU Testing

To boot the built image in QEMU with a copy-on-write overlay:

```bash
make qemu
```

This requires `qemu-system-x86_64` (or `qemu-system-aarch64` for arm64)
and OVMF UEFI firmware. `make qemu` supports only
`STRATA_BOOTLOADER=limine-efi`; use a U-Boot-capable board or emulator for an
extlinux image. The default QEMU invocation uses an EGL-headless
VirGL device and keeps the serial monitor on stdio, providing the guest with a
DRM render node without opening a display window. It therefore requires a QEMU
build with OpenGL/VirGL support. Set `STRATA_QEMU_GPU=none` to fall back to
`-nographic` for boot-only diagnostics without a graphical session.
It forwards port 2222 to the guest's SSH port.

The launcher gives the virtio system disk a higher UEFI `bootindex` than the
network adapter and refreshes writable OVMF VARS state when the raw image or GPU
topology changes. This prevents a stale PCI device path from falling through to
`Start PXE over IPv4` after switching between VirGL and serial-only launches.

## Bootloader Selection

`STRATA_BOOTLOADER` selects one boot payload for each image:

- `limine-efi` (the default) installs Limine's UEFI executable under
  `/EFI/BOOT/` and its `/limine.conf` entry on the ESP.
- `extlinux` installs only `/extlinux/extlinux.conf` on the ESP. It uses the
  same `/strataos/kernel`, `/strataos/initramfs.cpio.gz`, and kernel command
  line, and is intended for U-Boot distributions with extlinux or `bootstd`
  support.

Select the image ESP as a U-Boot boot target, or load
`/extlinux/extlinux.conf` through U-Boot's `sysboot` command. An extlinux image
does not include an EFI executable or Limine configuration.

The QEMU disk size is controlled by `STRATA_QEMU_DISK_MIB` in
`.config`.  The default is 32768 MiB (32 GiB).  The builder computes a
minimum based on the ESP size and declared component volumes, and
rejects values below that threshold.

## Cleaning

```bash
make clean              Remove output directory; preserve downloads
make distclean           Remove output and configuration
```

`make clean` deletes everything under `output/` except the download
cache (`output/dl/`).  This allows subsequent builds to skip
re-downloading source archives.

## Reproducible Source Archive

```bash
make dist
```

This creates a compressed tar archive of the project source tree,
suitable for distribution.  It runs `make check` first to ensure the
tree passes static validation.

## Build Resumption

If a build is interrupted, two mechanisms help avoid redundant work:

1.  **Package caching** (automatic): packages whose fingerprint has not
    changed are skipped on the next invocation.
2.  **Build-directory resumption** (opt-in): run the builder with
    `--resume` to keep incomplete build directories and allow
    `make`/`cmake` to continue from the interruption point.

```bash
python3 scripts/build.py --config .config --output output packages --resume
```

Build progress is recorded in `output/reports/package-build-state.json`.

## Output Layout

```text
output/toolchain/                     Isolated LLVM/musl toolchain & sysroot
output/host/                          Host tools built from source
output/packages/<name>/root/          Per-package isolated install root
output/kernel/kernel                  Linux kernel image
output/components/*.squashfs          Component images
output/components/component-versions.json  Component update version catalog
output/initramfs/initramfs.cpio.gz    Early userspace
output/images/strataos-<ver>-*.img    GPT disk image
output/logs/build.log                 Build log
output/reports/                       Audit reports and build plans
```

## Troubleshooting

If the build fails with a "configure option is not advertised by source"
error, the recipe's `configure_args` lists an option that the upstream
`configure` script does not recognize. If compile or installation fails,
inspect `build_args` or `install_args` in the same TOML recipe. Remove or fix
the declaration there rather than patching the build handler.

If a BusyBox Kconfig fragment fails to apply, the requested option
depends on another symbol that is not enabled.  Check the BusyBox
Kconfig hierarchy and add the prerequisite symbol to
`packages/busybox/configs/busybox.fragment`.

If a package build fails partway through, the build directory at
`output/package-work/<name>/build/` may contain useful diagnostic
output.  Use `--resume` to avoid restarting from scratch after fixing
the issue.
