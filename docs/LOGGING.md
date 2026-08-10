# Logging

## Build log

The build orchestrator writes every external command, stdout and stderr
both to the terminal and to:

```text
output/logs/build.log
```

This file is appended within the same output directory; `make clean`
removes build output but keeps the download cache.

## initramfs log

`/init` and `strata-componentd` record:

- ESP/data partition discovery;
- first-boot GPT growth;
- outer fsck and resize;
- component SHA-256 verification and SquashFS mounting;
- loop, dm-integrity and MD RAID1 creation/assembly/growth;
- inner ext4 mkfs, fsck and resize;
- OverlayFS and component data mounting.

Working logs are first written to `/run/strataos/early-boot.log`. Once the
root filesystem is successfully assembled, they are copied according to
`logging.conf` to:

```text
/var/log/boot/<boot-id>-early.log
/var/log/boot/<boot-id>-dmesg.log
/var/log/boot/<boot-id>-operations.log
/var/log/boot/<boot-id>-pstore-*
```

Individual tool output is also kept in files such as
`/run/strataos/*-fsck.log`, `*-md-*.log` and `*-integrity-*.log`, and is
summarized per boot ID into `operations.log`. This keeps details of
storage-assembly failures available across reboots.

## OpenRC logging

`strataos-logging` starts BusyBox `syslogd` and, optionally, `klogd`:

```text
/var/log/messages
/var/log/messages.0 ...
```

Configuration lives at `configs/runtime/logging.conf`:

```ini
mode=persistent
early_boot_log=yes
kernel_log=yes
operation_log=yes
max_file_kib=2048
rotate_count=8
boot_log_count=16
remote=
```

`operation_log=no` disables persisting the detailed boot-time storage
operation log. `mode=persistent` preserves `/var/log` via the `state`
volume's bind rules; `mode=volatile` mounts `/var/log` as tmpfs.
`boot_log_count` keeps only the most recent files by time when the logging
service starts. `remote=host:port` enables remote syslog while still
keeping a local copy.

## Kernel crash information

The kernel seed enables the pstore console. When firmware or the platform
provides a pstore backend, the initramfs imports the previous crash record
into `/var/log/boot`. The kernel also enables netconsole, which must be
configured with a target address via the kernel command line or at
runtime before use.

## Inspecting logs

```bash
strataos-log-status
rc-service strataos-logging status
ls -l /var/log/boot
cat /run/strataos/early-boot.log
cat /proc/mdstat
componentctl storage-status
strataos-storage-scrub --wait
```

On the first boot of an image copied or attached to a larger device, the
kernel may report that the backup GPT header is not at the end of the disk.
This precedes initramfs execution; `strataos-init` then relocates the backup
header and expands the data partition. OverlayFS may likewise report that a
SquashFS lower layer has no UUID or file-handle support and disable xino/index
features. These messages are expected compatibility fallbacks, not failed
services. Containerd also logs skipped optional snapshotter/tracing plugins at
info level when AUFS, ZFS, devmapper, CDI or OTLP are not configured.
