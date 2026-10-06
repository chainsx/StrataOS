# Component System

## Purpose

A component is a read-only SquashFS image containing the programs,
libraries, OpenRC services, and configuration for one functional
domain.  Component upgrades do not overwrite the active root
filesystem directly; instead, they write into a new slot and activate
on the next boot.

## Component Sources

Each component declares ownership of target packages through its
`packages.list` file.  For example:

```text
components/docker/packages.list
  docker-static
```

The package builder installs each package into an isolated DESTDIR.
The component assembler copies only the package roots listed in the
component's `packages.list`, together with the component's own
`rootfs/` overlay.  If two packages or an overlay provide the same
path with different content, the first writer wins.

A rootfs-only adapter may have no package payload; its `packages.list` keeps a
comment explaining that ownership and its files come entirely from `rootfs/`.

## On-Disk Format

```text
meta/strataos/component.conf
meta/strataos/files.sha256
meta/strataos/manifest.json
meta/strataos/packages.json
meta/strataos/hooks/
rootfs/
```

The file name follows the pattern:

```text
<name>-<version>-<full-SHA-256>.squashfs
```

During component generation, the architecture field is rewritten to
the single target architecture.  The manifest records package names,
versions, file modes, UID/GID pairs, sizes, and file hashes.

## Version Catalog

Every build also publishes `output/components/component-versions.json` and
`component-versions.json.sha256`. The catalog is deterministic and is the
release-side description used to select component updates. It records the
target release and architecture, the hash of the slot component list, and for
each component its name, version, dependencies, priority, persistent-storage
schemas, image path, SHA-256 and size. The initial catalog is copied to
`/strataos/component-versions.json` in the Data partition with its checksum.

An update client must verify the catalog using the release trust policy before
using it, then verify the selected artifact hash before giving that artifact to
`componentctl install`. The catalog checksum is an integrity sidecar for
publication and transport; it is not a replacement for a release signature.

## UID/GID and Permissions

Target ownership is generated explicitly by StrataOS's account policy
and path rules, then written through SquashFS pseudo definitions.  The
assembler does not force the entire component to root, nor does it
inherit host file ownership.  Trusted files requiring setuid must be
explicitly listed in the ownership policy and pass automated checks.

## Dependencies and Priority

Components declare `requires`, `after`, and `priority` fields.  The
initramfs and the component installation tool both reject:

- architecture mismatch;
- hash suffix mismatch;
- missing required components;
- illegal paths;
- priority collisions;
- duplicate component names.

## Data Volumes

Components declare their own data volumes with a logical identifier,
mount point, initial size, growth policy, and redundancy policy.
Published images do not contain pre-created empty ext4 volumes.  On
first activation, the trusted initramfs manager creates or assembles
the declared volume according to the component manifest and
`storage.conf`.

The stable identity of a volume is:

```text
<component-name> + <component-local-volume-id>
```

This allows third-party components to use the same local identifiers
without MD or dm-integrity name collisions.

Persistent state is assigned to the narrowest component that owns its
lifecycle:

| Component | Persistent state |
|---|---|
| `system-core` | `/state`, including writable `/etc`, homes and logs |
| `kernel-modules` | none; `/lib/modules` is read-only component payload |
| `network` | `/var/lib/dhcpcd` leases |
| `openssh` | generated host identity |
| `fail2ban` | `/var/lib/fail2ban` database |
| `docker` | `/var/lib/docker` |

Stateless components declare `storage.count=0`.

## Update Boundaries

Format v1 includes hooks in the component digest but does not
automatically execute data migration hooks.  Upgrades that involve
persistent schema changes require an offline backup, compatibility
check, and administratively validated migration before activation.

## Extensibility

The component format is generic.  Any directory under `components/`
that follows the required structure can be built into a SquashFS
component.  New components must be:

1.  Registered in `scripts/components.py` function `build_components()`;
2.  Gated by a `STRATA_ENABLE_<NAME>` flag in `.config`;
3.  Accounted for in `scripts/qemu.py` if they declare data volumes;
4.  Accompanied by corresponding package recipes and source entries.

The `system-core`, `kernel-modules`, `network`, `python`, and `openssh` components form the
default operating-system set. `network` owns iproute2, dhcpcd, iputils, PPP and
the OpenRC network service. Python is isolated so its interpreter can be
updated and audited independently. OpenSSH owns only `sshd`, SSH configuration
and its persistent host-identity volume; SSH is enabled by default and can be
controlled through OpenRC. Fail2ban is a separate optional security component
that depends explicitly on Python, OpenSSH and Firewall.

Docker, CJK Fonts, Diagnostics, Firewall and Fail2ban are reference
implementations of feature components. `fonts-cjk` owns the shared Noto CJK
font. `diagnostics` contains htop and lsof. `firewall` depends on `system-core`
and `network`, owns `nftables` and `libnftnl`, and declares no data volume. The
shared `libmnl` stays in `system-core` because both iproute2 and nftables link
against it. Its persisted ruleset lives under `/etc/strataos/firewall` in the
writable `/etc` overlay. It manages nftables presets and user-defined rules,
applying changes immediately but requiring an explicit confirmation before they
persist; unconfirmed changes automatically roll back after a configurable
timeout so a mistaken rule can never lock out SSH access. Its
`strataos-firewall` OpenRC service declares `before docker` so rules are always
in place before the Docker daemon starts; note that a component's
`after`/`priority` fields only order squashfs assembly and are not the runtime
boot-order mechanism, which OpenRC's `depend()` block provides instead.

No graphical component is shipped. The standard image has no display server,
desktop environment, remote framebuffer service, or GPU userspace; the serial
console and OpenSSH are the supported management interfaces.

The default full image therefore contains 10 components. Component root paths
are exposed to OverlayFS through short initramfs-only aliases; this is an
implementation detail that prevents a long colon-separated `lowerdir` option
from exceeding BusyBox's mount argument buffer after further component splits.

`system-core` keeps `/etc` writable changes in a persistent OverlayFS upper
directory. Account tools therefore update normal `/etc/passwd` and
`/etc/shadow` files atomically, while unchanged configuration continues to
come from the currently active read-only component instead of being frozen by
a whole-directory copy.
