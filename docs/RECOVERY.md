# Recovery procedures

## initramfs recovery shell

If a critical boot step fails, the system writes the error to both the
console and `/run/strataos/early-boot.log`, then drops into an initramfs
shell. Check first:

```sh
cat /run/strataos/early-boot.log
cat /run/strataos/*-fsck.log 2>/dev/null
cat /run/strataos/*-md-*.log 2>/dev/null
cat /run/strataos/*-integrity-*.log 2>/dev/null
cat /proc/mdstat
blkid
lsblk
```

## Component corruption

1. Mount `STRATA_DATA`;
2. check `strataos/active-slot`;
3. check the corresponding `slots/<slot>/components.list`;
4. recompute SHA-256 for the components listed in the manifest;
5. select a known-good slot, or restore the component files from a
   trusted build artifact.

On a running system, run:

```bash
componentctl verify
componentctl rollback
reboot
```

## RAID1 degradation

If a `mirror` or `integrity-mirror` volume loses a single member, preserve
the data first — do not immediately rebuild onto the same suspect device:

```sh
cat /proc/mdstat
mdadm --detail /dev/md/strata-docker
```

If the second backend is missing, automatic assembly will currently fail
and drop into the recovery shell, avoiding building a new array while the
topology is unclear. Once the administrator has confirmed the correct
member, they can manually assemble read-only, copy the data, or replace
the backend.

## ext4 checking

Normal boot uses `e2fsck -pf`. If the return code is greater than 1, the
automatic boot process stops. Copy the backing files before attempting
recovery; mirror members cannot be mounted directly as a plain ext4
filesystem — the loop/dm-integrity/MD layers must be restored first, and
the check must be run against the resulting logical device.

## Outer data partition

If the outer ext4/Btrfs filesystem itself is corrupted, both mirror
members on that same partition may become inaccessible at the same time.
In that case, restore from a block-level image or backup. Data-volume
redundancy is not a substitute for backing up the outer filesystem and the
whole disk.
