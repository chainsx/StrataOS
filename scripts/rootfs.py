#!/usr/bin/env python3
from __future__ import annotations

import os
import stat
from pathlib import Path

from common import BuildError, ROOT, atomic_write
from config import load_data

ACCOUNTS = {
    "root": (0, 0),
    "daemon": (1, 1),
    "messagebus": (81, 81),
    "sshd": (74, 74),
    "componentd": (201, 201),
    "dhcpcd": (285, 285),
}

GROUPS = {
    "root": 0,
    "daemon": 1,
    "tty": 5,
    "disk": 6,
    "mail": 12,
    "wheel": 10,
    "audio": 18,
    "video": 27,
    "render": 26,
    "input": 28,
    "messagebus": 81,
    "sshd": 74,
    "docker": 281,
    "netdev": 283,
    "dhcpcd": 285,
    "uucp": 284,
    "componentd": 201,
}

ROOT_INITIAL_PASSWORD_HASH = (
    "$6$strataos$xPSdYZVFtO9zV2O62G181k39HgHKjPiPETmrUkk6DXRchClTfRJCgnlZZiAvQ42s/"
    "7ze4FCqQnWIMqFhKTQXJ."
)


def _write(path: Path, body: str, mode: int = 0o644) -> None:
    atomic_write(path, body, mode)


def install_accounts(root: Path) -> None:
    etc = root / "etc"
    etc.mkdir(parents=True, exist_ok=True)
    passwd = [
        "root:x:0:0:root:/root:/bin/zsh",
        "daemon:x:1:1:daemon:/var/empty:/sbin/nologin",
        "messagebus:x:81:81:D-Bus system user:/var/run/dbus:/sbin/nologin",
        "sshd:x:74:74:OpenSSH privilege separation:/var/empty:/sbin/nologin",
        "componentd:x:201:201:StrataOS component service:/var/empty:/sbin/nologin",
        "dhcpcd:x:285:285:DHCP client:/var/empty:/sbin/nologin",
    ]
    group_members: dict[str, str] = {}
    group = [f"{name}:x:{gid}:{group_members.get(name, '')}" for name, gid in GROUPS.items()]
    shadow = [
        f"root:{ROOT_INITIAL_PASSWORD_HASH}:1::::::",
        "daemon:!:1::::::",
        "messagebus:!:1::::::",
        "sshd:!:1::::::",
        "componentd:!:1::::::",
        "dhcpcd:!:1::::::",
    ]
    gshadow = [f"{name}:!::{group_members.get(name, '')}" for name in GROUPS]
    account_files = {
        "passwd": ("\n".join(passwd) + "\n", 0o644),
        "group": ("\n".join(group) + "\n", 0o644),
        "shadow": ("\n".join(shadow) + "\n", 0o600),
        "gshadow": ("\n".join(gshadow) + "\n", 0o600),
    }
    for name, (body, mode) in account_files.items():
        _write(etc / name, body, mode)
    _write(etc / "shells", "/bin/sh\n/bin/ash\n/bin/zsh\n")


def install_base_configuration(root: Path, config: dict[str, str]) -> None:
    for relative, mode in (
        ("root", 0o700),
        ("home", 0o755),
        ("var/empty", 0o755),
        ("var/lib/dbus", 0o755),
        ("var/log", 0o750),
        ("var/spool/mail", 0o755),
        ("run", 0o755),
        ("tmp", 0o1777),
        ("var/tmp", 0o1777),
        ("etc/runlevels/sysinit", 0o755),
        ("etc/runlevels/boot", 0o755),
        ("etc/runlevels/default", 0o755),
    ):
        path = root / relative
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(mode)
    # shadow's useradd uses /var/mail while the conventional spool lives at
    # /var/spool/mail. Keep both names available without duplicating storage.
    mail = root / "var/mail"
    mail.unlink(missing_ok=True)
    mail.symlink_to("spool/mail")
    install_accounts(root)
    zsh_share = root / "usr/share/zsh"
    if zsh_share.is_dir():
        for path in (zsh_share, *sorted(zsh_share.rglob("*"))):
            if path.is_dir() and not path.is_symlink():
                path.chmod(stat.S_IMODE(path.lstat().st_mode) & ~0o022)
    hostname = config.get("STRATA_DEFAULT_HOSTNAME", "strataos")
    _write(root / "etc/hostname", hostname + "\n")
    _write(
        root / "etc/rc.conf",
        "rc_shell=/bin/sh\n"
        "rc_logger=NO\n"
        "rc_parallel=NO\n"
        "rc_depend_strict=YES\n"
        "rc_hotplug=NO\n",
    )
    _write(
        root / "etc/fstab",
        "proc /proc proc nosuid,noexec,nodev 0 0\n"
        "sysfs /sys sysfs nosuid,noexec,nodev 0 0\n"
        "devpts /dev/pts devpts gid=5,mode=620 0 0\n"
        "tmpfs /tmp tmpfs mode=1777,nosuid,nodev 0 0\n"
        "tmpfs /var/tmp tmpfs mode=1777,nosuid,nodev 0 0\n",
    )
    _write(root / "etc/nsswitch.conf", "passwd: files\ngroup: files\nshadow: files\nhosts: files dns\nnetworks: files dns\n")
    _write(root / "etc/resolv.conf", "nameserver 1.1.1.1\n")
    _write(
        root / "etc/os-release",
        "NAME=\"StrataOS\"\n"
        f"PRETTY_NAME=\"StrataOS {config['STRATA_VERSION']}\"\n"
        "ID=strataos\n"
        f"VERSION_ID=\"{config['STRATA_VERSION']}\"\n"
        f"VERSION=\"{config['STRATA_VERSION']}\"\n",
    )
    _write(
        root / "etc/strataos-release",
        f"StrataOS {config['STRATA_VERSION']}\n"
        f"Architecture: {config['STRATA_ARCH']}\n"
        "Build system: StrataOS native package DAG with LLVM/Clang and musl\n",
    )
    init = root / "sbin/init"
    init.parent.mkdir(parents=True, exist_ok=True)
    if init.exists() or init.is_symlink():
        init.unlink()
    init.symlink_to("openrc-init")
    for name in ("halt", "poweroff", "reboot", "shutdown"):
        shutdown_alias = root / "sbin" / name
        shutdown_alias.unlink(missing_ok=True)
        shutdown_alias.symlink_to("openrc-shutdown")
    nologin = root / "sbin/nologin"
    if not nologin.exists() and not nologin.is_symlink():
        nologin.symlink_to("../bin/false")
    early_md5sum = root / "bin/md5sum"
    early_md5sum.parent.mkdir(parents=True, exist_ok=True)
    if not early_md5sum.exists() and not early_md5sum.is_symlink():
        early_md5sum.symlink_to("busybox")
def add_runlevel_link(root: Path, level: str, service: str) -> None:
    target = root / "etc/runlevels" / level / service
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    target.symlink_to(f"../../init.d/{service}")


def install_base_runlevels(root: Path) -> None:
    for service in ("devfs", "procfs", "sysfs", "mdev"):
        add_runlevel_link(root, "sysinit", service)
    for service in ("hostname", "cgroups", "localmount", "strataos-storage", "strataos-logging"):
        add_runlevel_link(root, "boot", service)
    for service in ("dbus", "getty-console", "strataos-boot-ok"):
        add_runlevel_link(root, "default", service)


def ownership_for(relative: str, mode: int) -> tuple[int, int, int]:
    uid = gid = 0
    if relative == "var/lib/dbus" or relative.startswith("var/lib/dbus/"):
        uid = gid = 81
    elif relative == "var/empty" or relative.startswith("var/empty/"):
        uid = gid = 0
    return mode, uid, gid


def configure_logging(root: Path) -> None:
    logging = load_data(ROOT / "configs/runtime/logging.conf")
    _write(
        root / "etc/conf.d/strataos-logging",
        f"LOG_MODE={logging['mode']}\n"
        f"LOG_EARLY_BOOT={logging['early_boot_log']}\n"
        f"LOG_KERNEL={logging['kernel_log']}\n"
        f"LOG_MAX_FILE_KIB={logging['max_file_kib']}\n"
        f"LOG_ROTATE_COUNT={logging['rotate_count']}\n"
        f"LOG_BOOT_COUNT={logging['boot_log_count']}\n"
        f"LOG_REMOTE={logging.get('remote', '')}\n",
    )
