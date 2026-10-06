# Package and build-parameter audit

This audit applies to StrataOS 0.3.22 and is checked by `make audit`,
`make preflight`, `make verify-packages`, and `make check`.

## Package selection

No package is currently an unowned duplicate. Each target package belongs to
exactly one component and every transitive dependency is declared by its recipe.
The apparently overlapping packages are intentional:

- BusyBox supplies the recovery baseline, while coreutils, util-linux, procps-ng,
  iproute2 and iputils provide complete administration semantics used by scripts.
- nftables and libnftnl are owned by `firewall`. `libmnl` remains in
  `system-core` because it is a shared dependency of both nftables and the
  `network` component's iproute2 tools.
- htop and lsof are isolated in the optional `diagnostics` component.
- Python is included only once in its own component and is required by Fail2ban.
  SQLite is a common library in `system-core`, shared by Python and its
  supporting system utilities rather than being duplicated across components. `host-python` is a build-only,
  same-version interpreter needed for CPython cross configuration.
- Docker, CJK fonts, diagnostics, firewall and Fail2ban packages are
  selected only when their corresponding component feature switch is enabled.

## Dependency coordination

The graph is acyclic. Host recipes never depend on target artifacts. Target
recipes use the musl sysroot and may use explicit host tools only for build-time
code generation. Fail2ban depends on target Python and nftables; Python declares
zlib, bzip2, OpenSSL, libffi, SQLite and ncurses. Docker remains an independent
optional branch.

Component/runtime ordering is also explicit: Network precedes OpenSSH and
Firewall; Fail2ban requires Python, OpenSSH and Firewall and loads after all
three.

## Build parameters

All target builds use the architecture-specific musl triple, sysroot, Clang,
LLD, compiler-rt and libc++ policy. Native CPU tuning flags (`-march=native`,
`-mcpu=native`, `-mtune=native`) are rejected. Configure/Meson/CMake options are
validated against downloaded upstream source by `make preflight`; generated
compile and link plans and final ELF machine types are audited during a build.
Package-specific configure, compile, test and install argument vectors live in
the package TOML (`configure_args`, `build_args`, `test_args`, `install_args`).
Each upstream recipe owns a HTTPS-only `[source]` table, which records the
download URL and release checksum. Architecture-specific sources use
`[source.x86_64]` and `[source.arm64]`. This keeps package metadata and
package-local build steps together while the common cross-toolchain
orchestration remains generic. Local project packages
use the generic `local` builder and declare their build, test, and install
commands in the recipe; their implementation is kept within that package
directory rather than in `scripts/package_builder.py`.

The project supports native builds on x86_64 and arm64. It intentionally rejects
building an arm64 configuration on an x86_64 host (and the inverse); use matching
hardware or a matching-architecture build VM.
