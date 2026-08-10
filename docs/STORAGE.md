# Storage, ext4 sharding and redundancy

## Two-layer storage

StrataOS uses a two-layer filesystem model:

1. an outer Linux data partition, currently always ext4;
2. component-owned ext4 backing files, mounted after loop, optional
   dm-integrity and MD RAID1.

The outer partition must be writable. The read-only guarantee applies to
component SquashFS images, not to the outer partition that hosts the data
volumes.

## WebUI external disks

When the `webui-storage` component is active, the Storage page exposes a
bounded external-disk workflow modelled after LuCI DiskMan: inspect detected
devices and partitions, create an ext4 or FAT32 filesystem on an unmounted
partition, and mount it persistently at `/mnt/<name>`. The mount declaration
is stored in `/etc/strataos/storage-mounts.conf` and restored by the
`strataos-storage-mounts` OpenRC service.

The UI only accepts partitions returned by `lsblk`; it rejects mounted system,
state, boot, Docker and Flatpak paths. It does not edit partition tables,
RAID members, loop devices or component backing files. Use the console and a
verified backup procedure for those advanced operations.

## Default layout

```text
/strataos/
├── components/
├── slots/
├── active-slot
├── volumes/<component>/
├── state/
└── transactions/
```

Without redundancy:

```text
volumes/docker/docker.ext4
```

The full default image currently declares volumes for `system-core`, `network`,
`openssh`, `fail2ban`, `docker`, `flatpak`, and `webui-flatpak`. DHCP leases and
the Fail2ban database no longer share generic system state. Other components
and WebUI adapters remain read-only/stateless.

In mirrored mode:

```text
volumes/docker/docker.a.ext4
volumes/docker/docker.b.ext4
```

These two files are RAID members, not independently mountable ext4
filesystems; the real ext4 filesystem lives on the assembled
`/dev/md/strata-<derived-id>`. The derived ID is generated from the
component name and the component's internal volume ID, avoiding device-name
collisions between third-party components.

## Redundancy policies

### none

```text
backing file → loop → ext4
```

The default. Lowest capacity overhead; failure recovery relies on the
outer filesystem and backups.

### mirror

```text
file A → loop A ┐
                 ├→ MD RAID1 → ext4
file B → loop B ┘
```

MD uses metadata 1.2 and an internal write-intent bitmap. It can read from
the other member when one member has an explicit read error or becomes
unavailable, but it adds no end-to-end checksum for data blocks.

### integrity-mirror

```text
file A → loop A → dm-integrity CRC32C ┐
                                      ├→ MD RAID1 → ext4
file B → loop B → dm-integrity CRC32C ┘
```

This mode turns silent corruption into a detectable I/O error, which RAID1
can then try to satisfy from the other member. The cost is roughly double
the capacity, more writes, integrity-tag overhead and more complex boot-time
assembly.

## Does this fix ext4 sharding corruption

It can help, but the effect depends on the failure layer:

- ext4's `metadata_csum` mainly protects filesystem-metadata consistency,
  not redundancy for all user data;
- `mirror` helps against single-member loss, partial unreadability and
  partial backing-file corruption;
- `integrity-mirror` additionally detects silent bit flips on a member;
- if both members sit on the same physical disk and the same outer ext4
  filesystem, neither protects against whole-disk failure, controller
  errors, corruption of the outer filesystem itself, or accidental deletion
  of the entire directory;
- redundancy is not a backup: accidental deletion, application-level
  corruption and ransomware encryption are replicated to both members.

Recommendation: keep `none` as the default; for important data, configure
an independent `secondary` device with `integrity-mirror`, combined with
offline or remote backups.

## Configuration examples

A test mirror on the same backend:

```ini
override.docker.docker.redundancy=mirror
```

An integrity mirror on an independent device:

```ini
backend.secondary.type=filesystem
backend.secondary.source=PARTUUID=<second-device-partition-uuid>
backend.secondary.filesystem=ext4
backend.secondary.path=/strataos

override.docker.docker.redundancy=integrity-mirror
override.docker.docker.mirror_backend=secondary
```

The global default can also be changed:

```ini
volume.default.redundancy=integrity-mirror
volume.default.mirror_backend=secondary
volume.default.integrity=crc32c
```

## Growth

Only growing is supported, not automatic shrinking. At boot the following
order is used:

1. grow the backing files;
2. refresh the loop device capacity;
3. run dm-integrity resize on integrity members;
4. run `mdadm --grow --size=max` on RAID1;
5. `e2fsck`;
6. `resize2fs`.

Capacity can be overridden per component:

```ini
override.docker.docker.size_mib=16384
```

An override value must not be smaller than the component's declared
initial capacity.

## ESP runtime configuration

The ESP contains the boot-time configuration under
`/strataos/config/`. It is mounted read-only by the initramfs, so an offline
edit takes effect on the next boot and cannot be silently changed by a running
component.

- `components.conf` enables or disables each published component. `system-core`
  must remain enabled, and every enabled component must retain its manifest
  dependencies.
- `storage.conf` controls Data-image backend, growth, redundancy and defaults.
  `override.<component>.<volume>.*` sets capacity or backend policy for an
  individual component volume.
- `disk.conf` defines ESP/Data partition labels, initial sizes and safe
  first-boot growth policy.
- `logging.conf` controls early-boot and persistent log policy.

`components.conf` does not duplicate storage settings: component activation
and Data-image policy are separate, so disabling a component does not discard
its retained Data image.

## Component split migration

A volume declaration may set `legacy_component=<old-owner>`. Before attaching
the volume, initramfs adopts the old owner's simple backing file or both mirror
members and honors its backend, size, growth and redundancy overrides. For the
WebUI split, `webui-flatpak.webui` adopts `webui.webui`; this preserves existing
Application Center data while moving ownership to the adapter that uses it.

## Online consistency checking

For an assembled mirrored volume, run:

```bash
strataos-storage-scrub --wait
```

This writes `check` to every active MD RAID1's `sync_action`, waits for
completion, reads `mismatch_cnt`, and logs the result to the system log. It
does not run `repair` automatically: for a plain `mirror`, if the two
copies disagree there is no end-to-end checksum to determine which copy is
correct; back up and investigate first. `integrity-mirror` can use
dm-integrity to surface bad blocks as I/O errors, but a consistency check
still cannot replace offline backups and periodic restore drills.

## First-boot disk growth

When `partition.data.auto_grow=yes`, the initramfs only calls `sfdisk` to
grow the data partition to the end of the disk if it is the disk's last
partition, then checks and grows the outer filesystem. If other partitions
exist after it, the system refuses to modify the partition table
automatically and logs this to the early-boot log.

The outer data filesystem only stores component images and logical volume
files, so it uses `partition.data.usage_type=largefile4`, avoiding a long
background initialization of inodes for millions of small files that will
never be used after auto-growth.
