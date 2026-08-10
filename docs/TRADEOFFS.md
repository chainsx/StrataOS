# Design trade-offs

## Owning our own package recipes

StrataOS maintains its own package recipes and dependency graph, gaining a
clear supply-chain boundary, component ownership and build-behavior
control. The cost is ongoing maintenance of a large set of upstream build
options, musl compatibility patches and version-upgrade testing.

The current recipe system is deliberately kept small: it supports common
build systems and a handful of special handlers, and does not try to
become a general-purpose distro package manager. Any new implicit behavior
expands the audit surface.

## Official prebuilt bootstrap tools

Using official prebuilt LLVM and CMake archives significantly lowers the
cost of the first build, but these tools still depend on the host's base
ABI at runtime. The target sysroot and target artifacts must never link
against host libraries; official releases must run ELF interpreter,
RPATH, RUNPATH and NEEDED audits.

## Component splitting

Splitting functionality into components makes independent upgrades and
rollback easier, but ownership of shared libraries must stay stable.
Shared runtime libraries are currently centralized in `system-core`, with
functional components depending on it. Adding more component layers
increases the number of boot-time mounts and the complexity of conflict
management.

## loop-backed ext4

Component-owned ext4 backing files are easy to grow, migrate and manage
per component, but introduce a two-layer filesystem, fragmentation and more
complex failure diagnosis. `mirror` and `integrity-mirror` can mitigate
partial member corruption; they do not replace independent disks and
backups.

## Separate kernel modules

Early-boot storage and network drivers remain built into the kernel, while
optional drivers such as USB mass storage are loadable modules. They live in
the independent `kernel-modules` component rather than `system-core`, so the
driver payload has an explicit update and audit boundary. This increases the
kernel attack surface slightly, but restores practical hot-plug compatibility
without making the base component own `/lib/modules`.

## Current trusted-boot boundary

A full SHA-256 can only detect content changes; it cannot prove publisher
identity. Secure Boot, component signing, dm-verity, key rotation and
anti-rollback protection belong to a later production-hardening phase.
