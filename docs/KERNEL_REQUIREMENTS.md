# Kernel requirements by component

`configs/kernel/required-symbols.list` is the enforced common baseline for both
x86_64 and arm64. Architecture seed files may add platform drivers, but may not
omit a symbol in that list.

## system-core

| Function or package | Required kernel options |
| --- | --- |
| initramfs and devices | `CONFIG_BLK_DEV_INITRD`, `CONFIG_DEVTMPFS`, `CONFIG_DEVTMPFS_MOUNT`, `CONFIG_TMPFS` |
| component images | `CONFIG_BLK_DEV_LOOP`, `CONFIG_SQUASHFS`, `CONFIG_SQUASHFS_ZSTD`, `CONFIG_OVERLAY_FS` |
| state filesystems | `CONFIG_EXT4_FS`, `CONFIG_BTRFS_FS`, `CONFIG_VFAT_FS` |
| LVM and cryptsetup | `CONFIG_BLK_DEV_DM`, `CONFIG_DM_INTEGRITY`, `CONFIG_DM_VERITY`, kernel crypto baseline |
| mdadm redundancy | `CONFIG_MD`, `CONFIG_BLK_DEV_MD`, `CONFIG_MD_RAID1` |
| zram and Swap | `CONFIG_ZRAM`, `CONFIG_ZSMALLOC` |
| EFI boot | `CONFIG_EFI` plus architecture EFI stub/loader support |
| networking and SSH | `CONFIG_UNIX`, `CONFIG_PACKET`, `CONFIG_INET`, `CONFIG_IPV6` and a platform NIC driver |
| PPP/PPPoE | `CONFIG_PPP`, `CONFIG_PPPOE` |
| bridge/VLAN/tunnels | `CONFIG_BRIDGE`, `CONFIG_BRIDGE_NETFILTER`, `CONFIG_VLAN_8021Q`, `CONFIG_MACVLAN`, `CONFIG_TUN`, `CONFIG_VETH` |
| nftables and Fail2ban | `CONFIG_NETFILTER`, `CONFIG_NF_TABLES`, `CONFIG_NF_TABLES_INET`, `CONFIG_NFT_CT`, `CONFIG_NFT_NAT`, `CONFIG_NFT_MASQ`, `CONFIG_NFT_REJECT`, `CONFIG_NFT_REJECT_INET`, conntrack and NAT |
| recovery logs | `CONFIG_PSTORE`, `CONFIG_PSTORE_CONSOLE`, `CONFIG_NETCONSOLE` |

## kernel-modules component

`CONFIG_MODULES=y` is required. The build runs `make modules` and
`modules_install` into `output/kernel/modules-root`, then packages that tree as
the read-only `kernel-modules` component. USB mass storage is intentionally
`CONFIG_USB_STORAGE=m`; boot-critical disk and network drivers remain built in
so modules are not needed before the component overlay is active.

## Docker component

Docker requires namespaces, PID/network/IPC/UTS/mount and user namespaces,
`CONFIG_CGROUPS`, device/BPF/CPU/PID/memory cgroup controllers,
`CONFIG_SECCOMP`, `CONFIG_SECCOMP_FILTER`, Veth, bridge netfilter, OverlayFS and
nftables NAT/connection tracking.

## firewall component

UI rules use the nftables `inet` family, making `CONFIG_NF_TABLES_INET` mandatory
on both architectures. IPv4/IPv6 masquerade requires conntrack, NAT and nftables
masquerade expressions. Fail2ban additionally uses nftables sets and reject.

## Architecture-specific storage and boot

Both seeds enable SCSI disk, SATA/AHCI, NVMe, USB mass storage and xHCI. x86_64
adds PC/ACPI, i8042 and common virtual NIC drivers. arm64 adds PL011 console,
generic PCI host, VirtIO MMIO, platform AHCI, platform USB/DWC3 and common platform
Ethernet. Real arm64 hardware may still require a board device tree and SoC
storage/NIC/clock/reset drivers.
