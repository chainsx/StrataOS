# Customizing StrataOS

This document describes how to extend StrataOS with additional target
packages, components, kernel modifications, and disk layout changes.

## Adding a Target Package

1.  Create a recipe at `packages/<name>/<name>.toml`, including a `[source]`
    table with its pinned HTTPS URL and version-derived archive name.
3.  Declare direct dependencies.
4.  Select `autotools`, `cmake`, `meson`, or an audited special
    handler.
5.  Put all package-specific option vectors in the recipe:
    `configure_args`, `build_args`, and `install_args`. Placeholders such as
    `{jobs}`, `{destdir}`, `{sysroot}`, `{cc}`, and `{install_prefix}` are
    expanded by the builder. Do not add package policy to
    `scripts/package_builder.py`.
6.  Add the package name to one component's `packages.list`.
7.  Run `make source-lock` and `make check`.
8.  Perform a full build and audit the ELF dependency closure.

A package must belong to exactly one published component to avoid
duplicate files and ambiguous update boundaries.

## Adding a Component

Create the following structure:

```text
components/<name>/component.conf
components/<name>/packages.list
components/<name>/rootfs/
components/<name>/hooks/
```

The component name, priority, dependencies, services, and volume
declarations must pass schema validation.

Register the component in `scripts/components.py` function
`build_components()`:

```python
if enabled(config, "STRATA_ENABLE_DIAGNOSTICS"):
    selected.append("diagnostics")
```

Add the corresponding flag to `defconfigs/x86_64_defconfig` and
`defconfigs/arm64_defconfig`.  Also add it to the validation list in
`scripts/config.py`:

```python
for key in ("STRATA_ENABLE_FLATPAK", "STRATA_ENABLE_DOCKER",
            "STRATA_ENABLE_DIAGNOSTICS"):
    ...
```

If the component declares data volumes, update `scripts/qemu.py`
function `qemu_disk_mib()` to account for the additional storage
requirements.  The function must include the new component in its
`enabled` set:

```python
if config.get("STRATA_ENABLE_DIAGNOSTICS") == "1":
    enabled.add("diagnostics")
```

The built-in WebUI core requires system-core, network and web-console for
system information and the terminal. Network, OpenSSH, Firewall, Docker and
Flatpak CGI/helpers belong to their `webui-*` adapter components. The Flatpak
adapter is selected only when the active build includes WebUI, Graphics and
Flatpak. Keep hard dependencies only for components which cannot provide useful
standalone functionality.

## Modifying the Kernel

Architecture-specific kernel configurations are located at:

```text
configs/kernel/x86_64/kernel.config
configs/kernel/arm64/kernel.config
```

These are StrataOS's own configurations.  When adding new mandatory
symbols, synchronize `configs/kernel/required-symbols.list`.  The kernel
version and source are owned by `packages/linux/linux.toml`. Modules
are disabled by default; drivers needed for boot and storage must be
built-in.  The post-build script verifies the final Linux `.config`;
do not rely solely on the seed files.

## Modifying the Disk Layout

`configs/image/disk.conf` controls:

- published image initial size;
- ESP partition size;
- Linux data partition minimum size;
- GPT partition GUIDs;
- first-boot automatic partition growth.

The native image generator currently supports FAT32 for the ESP and
ext4 for the data partition.  Other filesystems are not yet supported
in the image builder (the initramfs can mount Btrfs data volumes at
runtime).

## Runtime Component Policy

`configs/runtime/components.conf` is copied to the ESP as
`/strataos/config/components.conf`. It controls whether each published
component is mounted at boot. Set `component.<name>.enabled=no` only after
also disabling all components which require it. Data-image allocation,
capacity and redundancy stay in `configs/runtime/storage.conf`; use its
`override.<component>.<volume>.*` keys for per-component storage policy.

## Modifying the Initramfs

The initramfs init script is located at `initramfs/init`.  It is a
shell script executed as PID 1.  The component orchestration logic
resides in `initramfs/bin/strata-componentd`.

The initramfs package set is defined by `components/system-core/packages.list`.
Packages added to this list are included in both the initramfs and the
system-core SquashFS component.  Keep the initramfs minimal; large
additions increase boot time and memory pressure.

Network, Python and OpenSSH are default standalone components. `python` owns
only the target interpreter, `network` owns the normal network userspace and
service, while `openssh` owns only the SSH server and persistent host identity.
Fail2ban is independently selected by `STRATA_ENABLE_FAIL2BAN`. SSH runtime
startup remains optional and is controlled through OpenRC or the WebUI switch.

## Modifying BusyBox

BusyBox applets are controlled by
`packages/busybox/configs/busybox.fragment`.
The builder starts from `allnoconfig`, merges this fragment, runs
`olddefconfig`, and verifies that every requested option took effect.
If an option is rejected (e.g., due to unmet Kconfig dependencies),
the build fails before compilation.  Add prerequisite symbols as
needed.
