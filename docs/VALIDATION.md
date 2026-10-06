# Validation scope

## Automated checks

```bash
make check
```

Covers:

- x86_64 and arm64 config parsing;
- upstream source versions, HTTPS URLs and hash formats;
- offline audit of every package recipe's parameters, dependency topology,
  cycle detection and unique component ownership;
- LLVM runtime Clang driver and CMake real link-command checks;
- rejection of the host `ld`, GCC crt objects, libgcc, libatomic and host
  search-path leakage;
- independent target-package DESTDIRs, effective-parameter reporting and
  sysroot merge paths;
- minimal C/C++ compile probes via direct Clang, CMake and Meson;
- target ELF architecture, musl interpreter, RPATH/RUNPATH and NEEDED
  dependency closure;
- component schema, dependencies, priority, architecture and data-volume
  ownership;
- the short initramfs OverlayFS lowerdir scheme used by multi-component images;
- required symbols, duplicates and module policy for both kernel
  configurations;
- Bash, POSIX sh, BusyBox ash and Python syntax;
- Network, OpenSSH, Fail2ban and Firewall component ownership and dependency
  ordering, root password login, persistent `/etc`
  overlay and first-boot account setup;
- standalone Firewall component wiring, including protected SSH port rejection
  and rollback behavior;
- default no-redundancy, CRC32C integrity images and first-boot growth;
- MD RAID1, dm-integrity, fsck, resize and logging critical paths;
- unit tests for the native GPT writer's primary/backup GPT, partition
  boundaries and protective MBR;
- rejection of prebuilt component data `.ext4` files or disk `.img` files in
  the release tree;
- SHA-256 of release archives.

Networked release builds must also run, after `make check`:

```bash
make preflight
```

This step checks every package's actually supported configure parameters
against the upstream source.

## Additional checks required after a full build

Static checks cannot prove that every upstream version builds successfully
under the musl/Clang combination. Every release must at minimum perform:

1. native x86_64 and arm64 networked builds;
2. checking interpreter, NEEDED, RPATH/RUNPATH and architecture for every
   target ELF;
3. UEFI/QEMU serial-console cold boot, repeated boot and rollback, confirming
   the `-nographic` launch has no display or GPU device;
4. first-boot growth of the data partition and capacity boundaries;
5. creation, degradation, re-assembly, growth and scrub for `none`,
   `mirror` and `integrity-mirror`;
6. Docker container startup, networking, cgroup v2 and persistence;
7. nftables preset application, rejection of rules targeting SSH, confirm persistence,
   and automatic rollback of an unconfirmed change after its timeout;
10. OpenSSH host key first generation, root login with the temporary
    password `strata`, first password change and administrator creation;
11. component replacement, missing dependencies, wrong architecture,
    corrupted hashes and slot rollback;
12. power loss, injected corruption, outer ext4 recovery and backup
    restore drills;
13. real hardware boot on NVMe, SATA, virtio and target ARM64 devices.

## Current delivery status

The x86_64 engineering track has completed project-level static checks, unit
tests, a real musl/Clang build, component image assembly, and UEFI/QEMU cold
boot. A full default-runlevel audit found no stopped or crashed services. An
interactive `poweroff` stopped Fail2ban, SSH, Docker, networking, D-Bus and
logging in order, flushed component volumes, remounted the outer data filesystem
read-only and reached ACPI S5 without an OpenRC failure.

Native ARM64 builds, real-hardware boot, HTTPS/PAM, storage corruption injection,
and recovery drills are not yet complete, so this still cannot be described as
having passed full release certification.

### LLVM runtime pre-link validation

Before compiling libc++ sources, validation checks:

- the target musl locale configuration macro;
- target-libc availability of `__cxa_thread_atexit_impl`;
- the matching libc++abi CMake cache value and compile definition;
- absence of link-only flags in compile commands;
- LLD/compiler-rt selection in the generated shared-library link command;
- absence of ignored manually specified CMake variables.

After installation, C and C++ smoke programs exercise complex arithmetic,
locales, threads and runtime-library dependency closure.
- LLVM runtime CMake cache policy is checked only through variables accepted by the selected LLVM source; obsolete variables are rejected before configure, and pthread/realtime/atomic fallbacks are verified before the long libc++ build starts.
