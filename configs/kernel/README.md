# StrataOS Linux 6.18 kernel configurations

StrataOS stores its maintained kernel seeds in this directory. They are not
fetched from another distribution during a build and contain no external
vendor branding.

- `x86_64/kernel.config` targets UEFI PCs, common server NICs, NVMe/AHCI/USB
  storage and QEMU/KVM guests.
- `arm64/kernel.config` targets UEFI/ACPI or device-tree server-class arm64,
  QEMU `virt`, common PCIe storage and a small set of common Ethernet drivers.

Both configurations build early-boot storage, SquashFS, OverlayFS, ext4,
Btrfs, MD RAID1, dm-integrity, dm-verity, cgroup v2, namespaces, seccomp,
container networking, pstore, netconsole, the DRM core and the VirtIO GPU driver
into the kernel. Loadable modules are enabled and installed into the separate
`kernel-modules` component; USB mass storage is the common modular driver.
Physical-device-specific GPU drivers, sound, media, Bluetooth, Wi-Fi, suspend,
profiling and broad consumer-device driver families remain disabled by default.

The build copies the selected seed into the Linux output directory, runs
`olddefconfig` with LLVM/Clang and validates the resolved configuration against
`required-symbols.list`. When a Linux 6.18 stable update changes Kconfig, review
and commit the resolved differences rather than replacing the file from an
external distribution.
