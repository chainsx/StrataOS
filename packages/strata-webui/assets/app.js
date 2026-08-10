/* StrataOS WebUI — i18n, theme, and full control panel */
const I18N = {
  en: {
    "nav.system": "System",
    "nav.storage": "Storage",
    "nav.settings": "Settings",
    "nav.network": "Network",
    "nav.terminal": "Terminal",
    "nav.security": "TLS & SSH",
    "nav.firewall": "Firewall",
    "nav.docker": "Docker",
    "nav.apps": "Flatpak Apps",
    "title.system": "System Configuration & Information",
    "title.storage": "Storage Management",
    "title.settings": "System Settings",
    "title.network": "Network Configuration",
    "title.terminal": "Web Terminal",
    "title.security": "TLS Certificates & SSH",
    "title.firewall": "Firewall",
    "title.docker": "Docker",
    "title.apps": "Flatpak Applications",
    "action.refresh": "Refresh",
    "action.logout": "Sign Out",
    "action.restart": "Restart",
    "action.shutdown": "Shut Down",
    "action.apply": "Apply",
    "action.save": "Save Configuration",
    "action.reconnect": "Reconnect",
    "action.confirm": "Confirm",
    "action.rollback": "Rollback Now",
    "action.add": "Add Rule",
    "action.pull": "Pull",
    "action.cancel": "Cancel",
    "action.close": "Close",
    "action.install": "Install",
    "action.refresh_apps": "Refresh Apps",
    "action.add_update": "Add or Update",
    "action.add_port": "Add port mapping",
    "action.add_volume": "Add volume",
    "action.add_env": "Add environment variable",
    "system.details": "System Details",
    "system.details_desc": "Operating system, hardware, and runtime environment",
    "system.control": "System Control",
    "system.control_desc": "Manage the hostname and power state; power actions interrupt active sessions",
    "system.hostname": "Hostname",
    "system.hostname_desc": "Change the system hostname",
    "system.power_actions": "Power Actions",
    "system.volumes": "Component Data Volumes",
    "system.components": "StrataOS Component Management",
    "system.components_desc": "Active components and their persistent data images",
    "system.no_volume": "This component has no persistent data image.",
    "system.volumes_desc": "Each component\'s data volume \u2014 size can only be increased (ext4 grow-on-boot)",
    "system.resources": "Resource Overview",
    "system.resources_desc": "Memory, swap, storage and process capacity",
    "system.temperatures": "Temperatures",
    "system.temperatures_desc": "Hardware thermal sensors",
    "system.gpu": "GPU",
    "system.gpu_desc": "Graphics devices",
    "system.block_devices": "Block Devices",
    "system.block_devices_desc": "Physical storage devices",
    "system.sysconfig": "System Configuration",
    "system.sysconfig_desc": "Docker daemon settings, logging mode, and runtime configuration",
    "sysconfig.docker_data": "Docker Data Root",
    "sysconfig.docker_log_size": "Docker Log Max Size",
    "sysconfig.docker_log_file": "Docker Log Max Files",
    "sysconfig.logging_mode": "Logging Mode",
    "sysconfig.log_persistent": "Persistent (disk)",
    "sysconfig.log_volatile": "Volatile (tmpfs)",
    "sysconfig.swap_mgmt": "Swap Management",
    "sysconfig.swappiness": "Swappiness (0-100)",
    "sysconfig.swap_state": "Swap State",
    "sysconfig.swap_size": "Create swap file",
    "sysconfig.language": "Language",
    "alert.popup_blocked": "The browser blocked the application window. Allow pop-ups for StrataOS and try again.",
    "volume.size_mib": "Volume Size (MiB)",
    "volume.growth": "Growth Policy",
    "volume.boot_only": "Boot-only",
    "volume.grow_only": "Grow-only",
    "volume.fixed": "Fixed",
    "volume.inherit": "Inherit",
    "volume.current": "Current",
    "volume.configured": "Configured",
    "volume.usage": "Usage",
    "volume.mount": "Mount",
    "volume.note_increase": "Size can only be increased. New size takes effect on next boot.",
    "network.interfaces": "Network Interfaces",
    "network.interfaces_desc": "Configure IPv4, gateway, and DNS for each interface",
    "network.dns": "DNS Servers",
    "network.dns_desc": "Comma-separated list of nameservers",
    "network.routes": "Routing Table",
    "network.routes_desc": "Active IPv4 routes",
    "network.tuning": "TCP/IP Tuning",
    "network.tuning_desc": "Kernel network stack performance settings",
    "network.tcp_congestion": "TCP Congestion Control",
    "network.qdisc": "Default Qdisc",
    "network.tfo": "TCP Fast Open",
    "network.pppoe": "PPPoE WAN",
    "network.pppoe_desc": "Connect to an ISP using PPP over Ethernet",
    "network.interface": "Interface",
    "network.protocol": "Protocol",
    "network.configure": "Configure",
    "network.username": "Username",
    "network.password": "Password",
    "network.connect": "Connect",
    "network.disconnect": "Disconnect",
    "network.nat": "Outbound NAT",
    "network.nat_desc": "Standard IPv4 and IPv6 masquerading",
    "state.enabled": "Enabled",
    "state.disabled": "Disabled",
    "option.default": "Default",
    "option.keep_current": "Keep current",
    "option.enable_swap": "Enable all swap",
    "option.disable_swap": "Disable all swap",
    "option.client_server": "Enabled (client + server)",
    "option.client_only": "Client only",
    "option.blackhole": "On black-hole detection",
    "option.always": "Always enabled",
    "option.strict": "Strict",
    "option.loose": "Loose",
    "network.mtu_probing": "TCP MTU Probing",
    "network.ipv4_forward": "IPv4 Forwarding",
    "network.rp_filter": "Reverse Path Filter",
    "terminal.title": "Web Terminal",
    "terminal.desc": "Authenticated local terminal powered by ttyd with system administration privileges",
    "security.tls": "TLS Certificate",
    "security.tls_desc": "HTTPS also protects Flatpak viewers and system or container terminals",
    "security.enable": "Enable HTTPS",
    "security.disable": "Disable HTTPS",
    "security.generate": "Generate Self-Signed Certificate",
    "security.generate_desc": "Browsers will show a warning until the certificate is explicitly trusted",
    "security.deploy": "Deploy Existing Certificate",
    "security.deploy_desc": "Upload a PEM certificate chain and its matching unencrypted PEM private key",
    "security.hostname": "Hostname or IPv4 address",
    "security.validity": "Validity in days",
    "security.generate_btn": "Generate and Enable HTTPS",
    "security.cert": "Certificate or full chain",
    "security.key": "Private key",
    "security.deploy_btn": "Validate, Deploy, and Enable",
    "security.notice": "Changing TLS mode restarts WebUI, clears login sessions, and ends browser terminal and application viewer connections. Running Docker containers continue.",
    "security.ssh_config": "SSH Server Configuration",
    "security.ssh_config_desc": "Modify the OpenSSH daemon settings",
    "security.ssh_enabled": "SSH Enabled",
    "security.ssh_port": "SSH Port",
    "security.ssh_permit_root": "Permit Root Login",
    "security.ssh_password_auth": "Password Authentication",
    "security.ssh_tcp_forward": "TCP Forwarding",
    "security.ssh_restart": "SSH configuration changes require restarting the daemon: rc-service sshd restart",
    "firewall.pending": "Change Pending Confirmation",
    "firewall.pending_desc": "Unconfirmed changes automatically roll back if not confirmed in time",
    "firewall.presets": "Presets",
    "firewall.presets_desc": "Applying a preset requires confirmation before it becomes permanent",
    "firewall.add_rule": "Add Rule",
    "firewall.add_rule_desc": "Custom rules are layered on top of the active preset",
    "firewall.rules": "Rules",
    "firewall.rules_desc": "Rules affecting management ports (SSH, WebUI, terminal, VNC) are rejected",
    "firewall.notice": "Management ports 22 (SSH), 9090 (WebUI), 7681/7690-7789 (terminal), and 6080 (VNC) can never be blocked by a rule or preset.",
    "firewall.allow": "Allow",
    "firewall.deny": "Deny",
    "state.status": "Status",
    "state.active": "Active",
    "firewall.preset.management-only.name": "Management only",
    "firewall.preset.management-only.desc": "Default deny inbound; allow management ports and established connections.",
    "firewall.preset.allow-all.name": "Allow all inbound",
    "firewall.preset.allow-all.desc": "Default accept inbound; deny only ports listed in custom rules.",
    "firewall.fail2ban": "Fail2ban Protection",
    "firewall.fail2ban_desc": "Automatically ban addresses after repeated SSH authentication failures",
    "firewall.maxretry": "Maximum failures",
    "firewall.findtime": "Detection window",
    "firewall.bantime": "Ban duration",
    "docker.pull": "Pull Image",
    "docker.pull_desc": "Pull an image from the configured registry or mirrors",
    "docker.images": "Local Images",
    "docker.images_desc": "Use a local image as the basis for a new container",
    "docker.create": "Create Container",
    "docker.create_desc": "Configure and deploy a container in one step",
    "docker.image": "Image",
    "docker.name": "Container name",
    "docker.hostname": "Hostname",
    "docker.restart": "Restart policy",
    "docker.network": "Network",
    "docker.console": "Console",
    "docker.pull_before": "Always pull the image before creating",
    "docker.start_after": "Start the container after creating",
    "docker.ports": "Port mapping",
    "docker.ports_desc": "Map container ports to the host",
    "docker.volumes": "Volumes",
    "docker.volumes_desc": "Bind-mount a host path or attach a named volume",
    "docker.env": "Environment variables",
    "docker.env_desc": "Passed to the container as KEY=value pairs",
    "docker.advanced": "Advanced: resources, security, labels, and command",
    "docker.workdir": "Working directory",
    "docker.user": "User",
    "docker.entrypoint": "Entrypoint",
    "docker.memory": "Memory limit",
    "docker.cpus": "CPU limit",
    "docker.labels": "Labels",
    "docker.dns_servers": "DNS servers",
    "docker.extra_hosts": "Extra hosts",
    "docker.devices": "Devices",
    "docker.cap_add": "Capabilities to add",
    "docker.cap_drop": "Capabilities to drop",
    "docker.extra_args": "Additional create arguments",
    "docker.command": "Command and arguments",
    "docker.privileged": "Privileged",
    "docker.readonly": "Read-only root filesystem",
    "docker.auto_remove": "Auto-remove",
    "docker.deploy": "Deploy the Container",
    "docker.containers": "Containers",
    "docker.containers_desc": "Start, stop, restart, view parameters, inspect logs, remove, or open interactive shell",
    "docker.mirrors": "Docker Registry Mirrors",
    "docker.mirrors_desc": "Adding, replacing, or deleting a mirror restarts Docker",
    "docker.daemon_config": "Docker Daemon Configuration",
    "docker.daemon_config_desc": "Change data root, log limits, and other daemon settings",
    "docker.data_root": "Data Root",
    "docker.log_max_size": "Log Max Size",
    "docker.log_max_file": "Log Max Files",
    "apps.install": "Install Flatpak Application",
    "apps.install_desc": "Choose a configured source and enter an application ID",
    "apps.title": "Flatpak Applications",
    "apps.title_desc": "Applications keep running when their viewer window is closed",
    "apps.sources": "Flatpak Sources",
    "apps.sources_desc": "Add mirrors or manage existing system-wide remotes",
    "apps.render_mode": "Renderer",
    "apps.render_gpu": "GPU acceleration",
    "apps.render_software": "Software rendering",
    "apps.configure_flathub": "Configure official Flathub",
    "apps.no_source": "No Flatpak source is configured. Configure official Flathub before installing applications.",
    "table.name": "Name",
    "table.size": "Size",
    "table.readonly": "Read-only",
    "table.destination": "Destination",
    "table.gateway": "Gateway",
    "table.device": "Device",
    "table.action": "Action",
    "table.protocol": "Protocol",
    "table.port": "Port",
    "table.actions": "Actions",
    "table.repository": "Repository",
    "table.tag": "Tag",
    "table.image_id": "Image ID",
    "table.created": "Created",
    "table.image": "Image",
    "table.container_id": "Container ID",
    "table.status": "Status",
    "login.title": "Connect to StrataOS",
    "login.desc": "Sign in with a system account, such as root or the administrator created during initial setup.",
    "login.username": "Username",
    "login.password": "Password",
    "login.signin": "Sign In",
    "setup.title": "Secure StrataOS",
    "setup.desc": "Default root credentials were used. Change the root password and create a named administrator before continuing.",
    "setup.root_password": "New root password",
    "setup.root_confirm": "Confirm root password",
    "setup.username": "Administrator username",
    "setup.user_password": "Administrator password",
    "setup.user_confirm": "Confirm administrator password",
    "setup.complete": "Complete Setup",
    "status.not_installed": "Not Installed",
    "status.not_running": "Not Running",
    "status.running": "Running",
    "status.unavailable": "Unable to connect to the Docker daemon",
    "status.no_containers": "No containers found.",
    "status.no_images": "No local images found.",
    "status.no_apps": "No Flatpak applications installed.",
    "status.no_interfaces": "No network interfaces detected.",
    "status.no_routes": "No routes.",
    "status.no_logs": "No logs are available for this container.",
    "status.no_sources": "No Flatpak sources configured.",
    "status.no_mirrors": "No Docker registry mirrors configured.",
    "status.docker_not_installed": "The Docker component is not installed.",
    "status.docker_not_available": "The Docker daemon is currently unavailable.",
    "status.start_docker_images": "Start Docker to view local images.",
    "status.install_docker": "Install the Docker component to view status.",
    "status.preparing": "Preparing installation",
    "status.preparing_pull": "Preparing image pull",
    "status.loading": "Loading...",
    "status.restarting": "Restarting",
    "status.shutting_down": "Shutting down",
    "status.active": "Active",
    "status.not_configured": "Not Configured",
    "status.none": "None",
    "status.unknown": "unknown",
    "status.opening_terminal": "Opening container terminal...",
    "alert.invalid_size": "Invalid size",
    "alert.volume_min": "Volume size can only be increased (min: ",
    "alert.address_required": "Address is required.",
    "alert.dns_updated": "DNS servers updated.",
    "alert.enter_value": "Enter at least one value to update.",
    "alert.popup_blocked": "The terminal window was blocked by the browser. Allow pop-ups for this site.",
    "alert.save_ok": " OK",
    "alert.tls_restart": "WebUI is restarting. Reconnect using ",
    "alert.disable_https": "Disable HTTPS and return all WebUI endpoints to unencrypted HTTP?",
    "alert.remove_container": "Remove this container?",
    "alert.stop_app": "Stop ",
    "alert.delete_flatpak": "Delete Flatpak source ",
    "alert.delete_mirror": "Delete this registry mirror and restart Docker? Running containers will be interrupted.",
    "alert.apply_mirror": "Apply registry mirror changes and restart Docker? Running containers will be interrupted.",
    "alert.rollback_firewall": "Immediately restore the previous firewall ruleset?",
    "table.no": "No",
    "docker.edit_container": "Edit Container",
    "docker.edit_subtitle": "Update parameters, then save to recreate this container",
    "docker.save_changes": "Save Changes (Recreates Container)",
    "docker.quick_params": "Quick update — no container restart required",
    "docker.leave_unchanged": "Leave unchanged",
    "docker.apply_without": "Apply Without Recreating",
    "docker.docker_default": "Docker default",
    "docker.params_loading": "Loading parameters...",
  },
  "zh-CN": {
    "nav.system": "\u7cfb\u7edf\u914d\u7f6e",
    "nav.network": "\u7f51\u7edc\u8bbe\u7f6e",
    "nav.terminal": "\u7ec8\u7aef",
    "nav.security": "TLS \u4e0e SSH",
    "nav.firewall": "\u9632\u706b\u5899",
    "nav.docker": "Docker",
    "nav.apps": "Flatpak \u5e94\u7528",
    "title.system": "\u7cfb\u7edf\u914d\u7f6e\u53ca\u4fe1\u606f",
    "title.network": "\u7f51\u7edc\u914d\u7f6e",
    "title.terminal": "Web \u7ec8\u7aef",
    "title.security": "TLS \u8bc1\u4e66\u4e0e SSH",
    "title.firewall": "\u9632\u706b\u5899",
    "title.docker": "Docker",
    "title.apps": "Flatpak \u5e94\u7528",
    "action.refresh": "\u5237\u65b0",
    "action.logout": "\u9000\u51fa\u767b\u5f55",
    "action.restart": "\u91cd\u542f",
    "action.shutdown": "\u5173\u673a",
    "action.apply": "\u5e94\u7528",
    "action.save": "\u4fdd\u5b58\u914d\u7f6e",
    "action.reconnect": "\u91cd\u65b0\u8fde\u63a5",
    "action.confirm": "\u786e\u8ba4",
    "action.rollback": "\u7acb\u5373\u56de\u6eda",
    "action.add": "\u6dfb\u52a0\u89c4\u5219",
    "action.pull": "\u62c9\u53d6",
    "action.cancel": "\u53d6\u6d88",
    "action.close": "\u5173\u95ed",
    "action.install": "\u5b89\u88c5",
    "action.refresh_apps": "\u5237\u65b0\u5e94\u7528",
    "action.add_update": "\u6dfb\u52a0\u6216\u66f4\u65b0",
    "action.add_port": "\u6dfb\u52a0\u7aef\u53e3\u6620\u5c04",
    "action.add_volume": "\u6dfb\u52a0\u5377",
    "action.add_env": "\u6dfb\u52a0\u73af\u5883\u53d8\u91cf",
    "system.details": "\u7cfb\u7edf\u8be6\u60c5",
    "system.details_desc": "\u64cd\u4f5c\u7cfb\u7edf、\u786c\u4ef6\u53ca\u8fd0\u884c\u73af\u5883",
    "system.control": "\u7cfb\u7edf\u63a7\u5236",
    "system.control_desc": "\u7ba1\u7406\u4e3b\u673a\u540d\u548c\u7535\u6e90\u72b6\u6001\uff1b\u7535\u6e90\u64cd\u4f5c\u4f1a\u4e2d\u65ad\u5f53\u524d\u4f1a\u8bdd",
    "system.hostname": "\u4e3b\u673a\u540d",
    "system.hostname_desc": "\u4fee\u6539\u7cfb\u7edf\u4e3b\u673a\u540d",
    "system.power_actions": "\u7535\u6e90\u64cd\u4f5c",
    "system.volumes": "\u7ec4\u4ef6\u6570\u636e\u5377",
    "system.components": "StrataOS \u7ec4\u4ef6\u7ba1\u7406",
    "system.components_desc": "\u5df2\u6fc0\u6d3b\u7684\u7ec4\u4ef6\u53ca\u5176\u6301\u4e45\u5316\u6570\u636e\u955c\u50cf",
    "system.no_volume": "\u6b64\u7ec4\u4ef6\u6ca1\u6709\u6301\u4e45\u5316\u6570\u636e\u955c\u50cf\u3002",
    "system.volumes_desc": "\u6bcf\u4e2a\u7ec4\u4ef6\u7684\u6570\u636e\u5377 \u2014 \u5927\u5c0f\u53ea\u80fd\u589e\u52a0（ext4 \u542f\u52a8\u65f6\u6269\u5bb9）",
    "system.resources": "\u8d44\u6e90\u6982\u89c8",
    "system.resources_desc": "\u5185\u5b58\u3001Swap\u3001\u5b58\u50a8\u4e0e\u8fdb\u7a0b\u5bb9\u91cf",
    "system.temperatures": "\u6e29\u5ea6\u4f20\u611f\u5668",
    "system.temperatures_desc": "\u786c\u4ef6\u6e29\u5ea6\u4f20\u611f\u5668",
    "system.gpu": "GPU",
    "system.gpu_desc": "\u56fe\u5f62\u8bbe\u5907",
    "system.block_devices": "\u5757\u8bbe\u5907",
    "system.block_devices_desc": "\u7269\u7406\u5b58\u50a8\u8bbe\u5907",
    "system.sysconfig": "\u7cfb\u7edf\u914d\u7f6e",
    "system.sysconfig_desc": "Docker \u5b88\u62a4\u8fdb\u7a0b\u8bbe\u7f6e、\u65e5\u5fd7\u6a21\u5f0f\u53ca\u8fd0\u884c\u65f6\u914d\u7f6e",
    "sysconfig.docker_data": "Docker \u6570\u636e\u6839\u76ee\u5f55",
    "sysconfig.docker_log_size": "Docker \u65e5\u5fd7\u6700\u5927\u5927\u5c0f",
    "sysconfig.docker_log_file": "Docker \u65e5\u5fd7\u6700\u5927\u6587\u4ef6\u6570",
    "sysconfig.logging_mode": "\u65e5\u5fd7\u6a21\u5f0f",
    "sysconfig.log_persistent": "\u6301\u4e45\u5316（\u78c1\u76d8）",
    "sysconfig.log_volatile": "\u6613\u5931（tmpfs）",
    "sysconfig.swap_mgmt": "Swap \u7ba1\u7406",
    "sysconfig.swappiness": "Swappiness (0-100)",
    "sysconfig.swap_state": "Swap \u72b6\u6001",
    "sysconfig.swap_size": "\u521b\u5efa Swap \u6587\u4ef6",
    "sysconfig.language": "\u8bed\u8a00",
    "alert.popup_blocked": "\u6d4f\u89c8\u5668\u62e6\u622a\u4e86\u5e94\u7528\u7a97\u53e3\u3002\u8bf7\u5141\u8bb8 StrataOS \u5f39\u51fa\u7a97\u53e3\u540e\u91cd\u8bd5\u3002",
    "volume.size_mib": "\u5377\u5927\u5c0f (MiB)",
    "volume.growth": "\u6269\u5bb9\u7b56\u7565",
    "volume.boot_only": "\u4ec5\u542f\u52a8\u65f6",
    "volume.grow_only": "\u4ec5\u6269\u5bb9",
    "volume.fixed": "\u56fa\u5b9a",
    "volume.inherit": "\u7ee7\u627f",
    "volume.current": "\u5f53\u524d",
    "volume.configured": "\u5df2\u914d\u7f6e",
    "volume.usage": "\u7528\u91cf",
    "volume.mount": "\u6302\u8f7d\u70b9",
    "volume.note_increase": "\u5927\u5c0f\u53ea\u80fd\u589e\u52a0。\u65b0\u5927\u5c0f\u5728\u4e0b\u6b21\u542f\u52a8\u65f6\u751f\u6548。",
    "network.interfaces": "\u7f51\u7edc\u63a5\u53e3",
    "network.interfaces_desc": "\u4e3a\u6bcf\u4e2a\u63a5\u53e3\u914d\u7f6e IPv4、\u7f51\u5173\u53ca DNS",
    "network.dns": "DNS \u670d\u52a1\u5668",
    "network.dns_desc": "\u9017\u53f7\u5206\u9694\u7684\u57df\u540d\u670d\u52a1\u5668\u5217\u8868",
    "network.routes": "\u8def\u7531\u8868",
    "network.routes_desc": "\u5f53\u524d\u6d3b\u8dc3\u7684 IPv4 \u8def\u7531",
    "network.tuning": "TCP/IP \u8c03\u4f18",
    "network.tuning_desc": "\u5185\u6838\u7f51\u7edc\u6808\u6027\u80fd\u8bbe\u7f6e",
    "network.tcp_congestion": "TCP \u62e5\u585e\u63a7\u5236",
    "network.qdisc": "\u9ed8\u8ba4 Qdisc",
    "network.tfo": "TCP Fast Open",
    "network.pppoe": "PPPoE \u5bbd\u5e26\u62e8\u53f7",
    "network.pppoe_desc": "\u901a\u8fc7 PPP over Ethernet \u8fde\u63a5\u8fd0\u8425\u5546",
    "network.interface": "\u7f51\u7edc\u63a5\u53e3",
    "network.protocol": "\u534f\u8bae",
    "network.configure": "\u914d\u7f6e",
    "network.username": "\u7528\u6237\u540d",
    "network.password": "\u5bc6\u7801",
    "network.connect": "\u8fde\u63a5",
    "network.disconnect": "\u65ad\u5f00",
    "network.nat": "\u51fa\u7ad9 NAT",
    "network.nat_desc": "\u6807\u51c6 IPv4/IPv6 \u5730\u5740\u4f2a\u88c5",
    "state.enabled": "\u5df2\u542f\u7528",
    "state.disabled": "\u5df2\u7981\u7528",
    "option.default": "\u9ed8\u8ba4",
    "option.keep_current": "\u4fdd\u6301\u5f53\u524d\u72b6\u6001",
    "option.enable_swap": "\u542f\u7528\u5168\u90e8 Swap",
    "option.disable_swap": "\u7981\u7528\u5168\u90e8 Swap",
    "option.client_server": "\u542f\u7528\uff08\u5ba2\u6237\u7aef + \u670d\u52a1\u7aef\uff09",
    "option.client_only": "\u4ec5\u5ba2\u6237\u7aef",
    "option.blackhole": "\u68c0\u6d4b\u5230\u9ed1\u6d1e\u65f6",
    "option.always": "\u59cb\u7ec8\u542f\u7528",
    "option.strict": "\u4e25\u683c",
    "option.loose": "\u5bbd\u677e",
    "network.mtu_probing": "TCP MTU \u63a2\u6d4b",
    "network.ipv4_forward": "IPv4 \u8f6c\u53d1",
    "network.rp_filter": "\u53cd\u5411\u8def\u5f84\u8fc7\u6ee4",
    "terminal.title": "Web \u7ec8\u7aef",
    "terminal.desc": "\u57fa\u4e8e ttyd \u7684\u5df2\u8ba4\u8bc1\u672c\u5730\u7ec8\u7aef，\u62e5\u6709\u7cfb\u7edf\u7ba1\u7406\u6743\u9650",
    "security.tls": "TLS \u8bc1\u4e66",
    "security.tls_desc": "HTTPS \u540c\u65f6\u4fdd\u62a4 Flatpak \u67e5\u770b\u5668\u548c\u7cfb\u7edf\u7ec8\u7aef",
    "security.enable": "\u542f\u7528 HTTPS",
    "security.disable": "\u7981\u7528 HTTPS",
    "security.generate": "\u751f\u6210\u81ea\u7b7e\u540d\u8bc1\u4e66",
    "security.generate_desc": "\u6d4f\u89c8\u5668\u5c06\u663e\u793a\u8b66\u544a，\u76f4\u5230\u624b\u52a8\u4fe1\u4efb\u6b64\u8bc1\u4e66",
    "security.deploy": "\u90e8\u7f72\u73b0\u6709\u8bc1\u4e66",
    "security.deploy_desc": "\u4e0a\u4f20 PEM \u8bc1\u4e66\u94fe\u548c\u5339\u914d\u7684\u672a\u52a0\u5bc6 PEM \u79c1\u94a5",
    "security.hostname": "\u4e3b\u673a\u540d\u6216 IPv4 \u5730\u5740",
    "security.validity": "\u6709\u6548\u671f（\u5929）",
    "security.generate_btn": "\u751f\u6210\u5e76\u542f\u7528 HTTPS",
    "security.cert": "\u8bc1\u4e66\u6216\u5b8c\u6574\u94fe",
    "security.key": "\u79c1\u94a5",
    "security.deploy_btn": "\u9a8c\u8bc1、\u90e8\u7f72\u5e76\u542f\u7528",
    "security.notice": "\u66f4\u6539 TLS \u6a21\u5f0f\u5c06\u91cd\u542f WebUI、\u6e05\u9664\u767b\u5f55\u4f1a\u8bdd\u5e76\u65ad\u5f00\u6d4f\u89c8\u5668\u7ec8\u7aef\u548c\u5e94\u7528\u67e5\u770b\u5668\u8fde\u63a5。Docker \u5bb9\u5668\u5c06\u7ee7\u7eed\u8fd0\u884c。",
    "security.ssh_config": "SSH \u670d\u52a1\u5668\u914d\u7f6e",
    "security.ssh_config_desc": "\u4fee\u6539 OpenSSH \u5b88\u62a4\u8fdb\u7a0b\u8bbe\u7f6e",
    "security.ssh_enabled": "\u542f\u7528 SSH",
    "security.ssh_port": "SSH \u7aef\u53e3",
    "security.ssh_permit_root": "\u5141\u8bb8 Root \u767b\u5f55",
    "security.ssh_password_auth": "\u5bc6\u7801\u8ba4\u8bc1",
    "security.ssh_tcp_forward": "TCP \u8f6c\u53d1",
    "security.ssh_restart": "SSH \u914d\u7f6e\u66f4\u6539\u540e\u9700\u91cd\u542f\u5b88\u62a4\u8fdb\u7a0b: rc-service sshd restart",
    "firewall.pending": "\u5f85\u786e\u8ba4\u66f4\u6539",
    "firewall.pending_desc": "\u672a\u786e\u8ba4\u7684\u66f4\u6539\u5c06\u81ea\u52a8\u56de\u6eda",
    "firewall.presets": "\u9884\u8bbe\u65b9\u6848",
    "firewall.presets_desc": "\u5e94\u7528\u9884\u8bbe\u65b9\u6848\u9700\u8981\u786e\u8ba4\u624d\u80fd\u6c38\u4e45\u751f\u6548",
    "firewall.add_rule": "\u6dfb\u52a0\u89c4\u5219",
    "firewall.add_rule_desc": "\u81ea\u5b9a\u4e49\u89c4\u5219\u53e0\u52a0\u5728\u6d3b\u8dc3\u9884\u8bbe\u4e4b\u4e0a",
    "firewall.rules": "\u89c4\u5219",
    "firewall.rules_desc": "\u5f71\u54cd\u7ba1\u7406\u7aef\u53e3\u7684\u89c4\u5219（SSH、WebUI、\u7ec8\u7aef、VNC）\u5c06\u88ab\u62d2\u7edd",
    "firewall.notice": "\u7ba1\u7406\u7aef\u53e3 22 (SSH)、9090 (WebUI)、7681/7690-7789 (\u7ec8\u7aef) \u548c 6080 (VNC) \u6c38\u8fdc\u4e0d\u80fd\u88ab\u89c4\u5219\u6216\u9884\u8bbe\u963b\u6b62。",
    "firewall.allow": "\u5141\u8bb8",
    "firewall.deny": "\u62d2\u7edd",
    "state.status": "\u72b6\u6001",
    "state.active": "\u5df2\u542f\u7528",
    "firewall.preset.management-only.name": "\u4ec5\u7ba1\u7406\u670d\u52a1",
    "firewall.preset.management-only.desc": "\u9ed8\u8ba4\u62d2\u7edd\u5165\u7ad9\u8fde\u63a5，\u4ec5\u5141\u8bb8\u7ba1\u7406\u7aef\u53e3\u548c\u5df2\u5efa\u7acb\u7684\u8fde\u63a5\u3002",
    "firewall.preset.allow-all.name": "\u5141\u8bb8\u6240\u6709\u5165\u7ad9\u8fde\u63a5",
    "firewall.preset.allow-all.desc": "\u9ed8\u8ba4\u5141\u8bb8\u5165\u7ad9\u8fde\u63a5，\u4ec5\u62d2\u7edd\u81ea\u5b9a\u4e49\u89c4\u5219\u4e2d\u7684\u7aef\u53e3\u3002",
    "firewall.fail2ban": "Fail2ban \u9632\u62a4",
    "firewall.fail2ban_desc": "SSH \u8ba4\u8bc1\u8fde\u7eed\u5931\u8d25\u540e\u81ea\u52a8\u5c01\u7981\u6765\u6e90\u5730\u5740",
    "firewall.maxretry": "\u6700\u5927\u5931\u8d25\u6b21\u6570",
    "firewall.findtime": "\u68c0\u6d4b\u65f6\u95f4\u7a97",
    "firewall.bantime": "\u5c01\u7981\u65f6\u957f",
    "docker.pull": "\u62c9\u53d6\u955c\u50cf",
    "docker.pull_desc": "\u4ece\u5df2\u914d\u7f6e\u7684\u4ed3\u5e93\u6216\u955c\u50cf\u7ad9\u62c9\u53d6\u955c\u50cf",
    "docker.images": "\u672c\u5730\u955c\u50cf",
    "docker.images_desc": "\u4f7f\u7528\u672c\u5730\u955c\u50cf\u521b\u5efa\u65b0\u5bb9\u5668",
    "docker.create": "\u521b\u5efa\u5bb9\u5668",
    "docker.create_desc": "\u4e00\u952e\u914d\u7f6e\u548c\u90e8\u7f72\u5bb9\u5668",
    "docker.image": "\u955c\u50cf",
    "docker.name": "\u5bb9\u5668\u540d\u79f0",
    "docker.hostname": "\u4e3b\u673a\u540d",
    "docker.restart": "\u91cd\u542f\u7b56\u7565",
    "docker.network": "\u7f51\u7edc",
    "docker.console": "\u63a7\u5236\u53f0",
    "docker.pull_before": "\u521b\u5efa\u524d\u603b\u662f\u62c9\u53d6\u955c\u50cf",
    "docker.start_after": "\u521b\u5efa\u540e\u542f\u52a8\u5bb9\u5668",
    "docker.ports": "\u7aef\u53e3\u6620\u5c04",
    "docker.ports_desc": "\u5c06\u5bb9\u5668\u7aef\u53e3\u6620\u5c04\u5230\u4e3b\u673a",
    "docker.volumes": "\u5377",
    "docker.volumes_desc": "\u7ed1\u5b9a\u6302\u8f7d\u4e3b\u673a\u8def\u5f84\u6216\u9644\u52a0\u547d\u540d\u5377",
    "docker.env": "\u73af\u5883\u53d8\u91cf",
    "docker.env_desc": "\u4ee5 KEY=value \u683c\u5f0f\u4f20\u9012\u7ed9\u5bb9\u5668",
    "docker.advanced": "\u9ad8\u7ea7\u9009\u9879：\u8d44\u6e90、\u5b89\u5168、\u6807\u7b7e\u548c\u547d\u4ee4",
    "docker.workdir": "\u5de5\u4f5c\u76ee\u5f55",
    "docker.user": "\u7528\u6237",
    "docker.entrypoint": "\u5165\u53e3\u70b9",
    "docker.memory": "\u5185\u5b58\u9650\u5236",
    "docker.cpus": "CPU \u9650\u5236",
    "docker.labels": "\u6807\u7b7e",
    "docker.dns_servers": "DNS \u670d\u52a1\u5668",
    "docker.extra_hosts": "\u989d\u5916\u4e3b\u673a",
    "docker.devices": "\u8bbe\u5907",
    "docker.cap_add": "\u6dfb\u52a0\u80fd\u529b",
    "docker.cap_drop": "\u79fb\u9664\u80fd\u529b",
    "docker.extra_args": "\u989d\u5916\u53c2\u6570",
    "docker.command": "\u547d\u4ee4\u53ca\u53c2\u6570",
    "docker.privileged": "\u7279\u6743\u6a21\u5f0f",
    "docker.readonly": "\u53ea\u8bfb\u6839\u6587\u4ef6\u7cfb\u7edf",
    "docker.auto_remove": "\u81ea\u52a8\u5220\u9664",
    "docker.deploy": "\u90e8\u7f72\u5bb9\u5668",
    "docker.containers": "\u5bb9\u5668",
    "docker.containers_desc": "\u542f\u52a8、\u505c\u6b62、\u91cd\u542f、\u67e5\u770b\u53c2\u6570、\u65e5\u5fd7、\u5220\u9664\u6216\u6253\u5f00\u4ea4\u4e92\u5f0f\u7ec8\u7aef",
    "docker.mirrors": "Docker \u955c\u50cf\u4ed3\u5e93",
    "docker.mirrors_desc": "\u6dfb\u52a0、\u66ff\u6362\u6216\u5220\u9664\u955c\u50cf\u4ed3\u5e93\u5c06\u91cd\u542f Docker",
    "docker.daemon_config": "Docker \u5b88\u62a4\u8fdb\u7a0b\u914d\u7f6e",
    "docker.daemon_config_desc": "\u66f4\u6539\u6570\u636e\u6839\u76ee\u5f55、\u65e5\u5fd7\u9650\u5236\u53ca\u5176\u4ed6\u5b88\u62a4\u8fdb\u7a0b\u8bbe\u7f6e",
    "docker.data_root": "\u6570\u636e\u6839\u76ee\u5f55",
    "docker.log_max_size": "\u65e5\u5fd7\u6700\u5927\u5927\u5c0f",
    "docker.log_max_file": "\u65e5\u5fd7\u6700\u5927\u6587\u4ef6\u6570",
    "apps.install": "\u5b89\u88c5 Flatpak \u5e94\u7528",
    "apps.install_desc": "\u9009\u62e9\u914d\u7f6e\u7684\u6e90\u5e76\u8f93\u5165\u5e94\u7528 ID",
    "apps.title": "Flatpak \u5e94\u7528",
    "apps.title_desc": "\u5173\u95ed\u67e5\u770b\u5668\u7a97\u53e3\u540e\u5e94\u7528\u7ee7\u7eed\u8fd0\u884c",
    "apps.sources": "Flatpak \u6e90",
    "apps.sources_desc": "\u6dfb\u52a0\u955c\u50cf\u6216\u7ba1\u7406\u7cfb\u7edf\u7ea7\u8fdc\u7a0b\u4ed3\u5e93",
    "apps.render_mode": "\u6e32\u67d3\u5668",
    "apps.render_gpu": "GPU \u52a0\u901f",
    "apps.render_software": "\u8f6f\u4ef6\u6e32\u67d3",
    "apps.configure_flathub": "\u914d\u7f6e\u5b98\u65b9 Flathub",
    "apps.no_source": "\u672a\u914d\u7f6e Flatpak \u8f6f\u4ef6\u6e90\u3002\u8bf7\u5148\u914d\u7f6e\u5b98\u65b9 Flathub\u3002",
    "table.name": "\u540d\u79f0",
    "table.size": "\u5927\u5c0f",
    "table.readonly": "\u53ea\u8bfb",
    "table.destination": "\u76ee\u6807",
    "table.gateway": "\u7f51\u5173",
    "table.device": "\u8bbe\u5907",
    "table.action": "\u52a8\u4f5c",
    "table.protocol": "\u534f\u8bae",
    "table.port": "\u7aef\u53e3",
    "table.actions": "\u64cd\u4f5c",
    "table.repository": "\u4ed3\u5e93",
    "table.tag": "\u6807\u7b7e",
    "table.image_id": "\u955c\u50cf ID",
    "table.created": "\u521b\u5efa\u65f6\u95f4",
    "table.image": "\u955c\u50cf",
    "table.container_id": "\u5bb9\u5668 ID",
    "table.status": "\u72b6\u6001",
    "login.title": "\u8fde\u63a5\u5230 StrataOS",
    "login.desc": "\u4f7f\u7528\u7cfb\u7edf\u8d26\u6237\u767b\u5f55，\u5982 root \u6216\u521d\u59cb\u8bbe\u7f6e\u65f6\u521b\u5efa\u7684\u7ba1\u7406\u5458\u8d26\u6237。",
    "login.username": "\u7528\u6237\u540d",
    "login.password": "\u5bc6\u7801",
    "login.signin": "\u767b\u5f55",
    "setup.title": "\u4fdd\u62a4 StrataOS",
    "setup.desc": "\u68c0\u6d4b\u5230\u4f7f\u7528\u4e86\u9ed8\u8ba4 root \u51ed\u636e\u3002\u7ee7\u7eed\u524d\u8bf7\u4fee\u6539 root \u5bc6\u7801\u5e76\u521b\u5efa\u5177\u540d\u7ba1\u7406\u5458\u3002",
    "setup.root_password": "\u65b0 root \u5bc6\u7801",
    "setup.root_confirm": "\u786e\u8ba4 root \u5bc6\u7801",
    "setup.username": "\u7ba1\u7406\u5458\u7528\u6237\u540d",
    "setup.user_password": "\u7ba1\u7406\u5458\u5bc6\u7801",
    "setup.user_confirm": "\u786e\u8ba4\u7ba1\u7406\u5458\u5bc6\u7801",
    "setup.complete": "\u5b8c\u6210\u8bbe\u7f6e",
    "status.not_installed": "\u672a\u5b89\u88c5",
    "status.not_running": "\u672a\u8fd0\u884c",
    "status.running": "\u8fd0\u884c\u4e2d",
    "status.unavailable": "\u65e0\u6cd5\u8fde\u63a5\u5230 Docker \u5b88\u62a4\u8fdb\u7a0b",
    "status.no_containers": "\u672a\u627e\u5230\u5bb9\u5668。",
    "status.no_images": "\u672a\u627e\u5230\u672c\u5730\u955c\u50cf。",
    "status.no_apps": "\u672a\u5b89\u88c5 Flatpak \u5e94\u7528。",
    "status.no_interfaces": "\u672a\u68c0\u6d4b\u5230\u7f51\u7edc\u63a5\u53e3。",
    "status.no_routes": "\u65e0\u8def\u7531。",
    "status.no_logs": "\u6b64\u5bb9\u5668\u6ca1\u6709\u53ef\u7528\u65e5\u5fd7。",
    "status.no_sources": "\u672a\u914d\u7f6e Flatpak \u6e90。",
    "status.no_mirrors": "\u672a\u914d\u7f6e Docker \u955c\u50cf\u4ed3\u5e93。",
    "status.docker_not_installed": "Docker \u7ec4\u4ef6\u672a\u5b89\u88c5。",
    "status.docker_not_available": "Docker \u5b88\u62a4\u8fdb\u7a0b\u5f53\u524d\u4e0d\u53ef\u7528。",
    "status.start_docker_images": "\u542f\u52a8 Docker \u4ee5\u67e5\u770b\u672c\u5730\u955c\u50cf。",
    "status.install_docker": "\u5b89\u88c5 Docker \u7ec4\u4ef6\u4ee5\u67e5\u770b\u72b6\u6001。",
    "status.preparing": "\u6b63\u5728\u51c6\u5907\u5b89\u88c5",
    "status.preparing_pull": "\u6b63\u5728\u51c6\u5907\u62c9\u53d6\u955c\u50cf",
    "status.loading": "\u52a0\u8f7d\u4e2d...",
    "status.restarting": "\u6b63\u5728\u91cd\u542f",
    "status.shutting_down": "\u6b63\u5728\u5173\u673a",
    "status.active": "\u6d3b\u8dc3",
    "status.not_configured": "\u672a\u914d\u7f6e",
    "status.none": "\u65e0",
    "status.unknown": "\u672a\u77e5",
    "status.opening_terminal": "\u6b63\u5728\u6253\u5f00\u5bb9\u5668\u7ec8\u7aef...",
    "alert.invalid_size": "\u65e0\u6548\u7684\u5927\u5c0f",
    "alert.volume_min": "\u5377\u5927\u5c0f\u53ea\u80fd\u589e\u52a0（\u6700\u5c0f\u503c：",
    "alert.address_required": "\u5730\u5740\u4e0d\u80fd\u4e3a\u7a7a。",
    "alert.dns_updated": "DNS \u670d\u52a1\u5668\u5df2\u66f4\u65b0。",
    "alert.enter_value": "\u8bf7\u81f3\u5c11\u8f93\u5165\u4e00\u4e2a\u503c\u4ee5\u66f4\u65b0。",
    "alert.popup_blocked": "\u7ec8\u7aef\u7a97\u53e3\u88ab\u6d4f\u89c8\u5668\u62e6\u622a。\u8bf7\u5141\u8bb8\u6b64\u7ad9\u70b9\u7684\u5f39\u51fa\u7a97\u53e3。",
    "alert.save_ok": " \u5df2\u4fdd\u5b58",
    "alert.tls_restart": "WebUI \u6b63\u5728\u91cd\u542f。\u8bf7\u4f7f\u7528 ",
    "alert.disable_https": "\u7981\u7528 HTTPS \u5e76\u5c06\u6240\u6709 WebUI \u7aef\u70b9\u6062\u590d\u4e3a\u672a\u52a0\u5bc6\u7684 HTTP？",
    "alert.remove_container": "\u79fb\u9664\u6b64\u5bb9\u5668？",
    "alert.stop_app": "\u505c\u6b62 ",
    "alert.delete_flatpak": "\u5220\u9664 Flatpak \u6e90 ",
    "alert.delete_mirror": "\u5220\u9664\u6b64\u955c\u50cf\u4ed3\u5e93\u5e76\u91cd\u542f Docker？\u8fd0\u884c\u4e2d\u7684\u5bb9\u5668\u5c06\u88ab\u4e2d\u65ad。",
    "alert.apply_mirror": "\u5e94\u7528\u955c\u50cf\u4ed3\u5e93\u66f4\u6539\u5e76\u91cd\u542f Docker？\u8fd0\u884c\u4e2d\u7684\u5bb9\u5668\u5c06\u88ab\u4e2d\u65ad。",
    "alert.rollback_firewall": "\u7acb\u5373\u6062\u590d\u4e4b\u524d\u7684\u9632\u706b\u5899\u89c4\u5219\u96c6？",
    "table.no": "\u5426",
    "docker.edit_container": "\u7f16\u8f91\u5bb9\u5668",
    "docker.edit_subtitle": "\u66f4\u65b0\u53c2\u6570\u540e\u4fdd\u5b58\u4ee5\u91cd\u65b0\u521b\u5efa\u6b64\u5bb9\u5668",
    "docker.save_changes": "\u4fdd\u5b58\u66f4\u6539（\u5c06\u91cd\u65b0\u521b\u5efa\u5bb9\u5668）",
    "docker.quick_params": "\u5feb\u901f\u66f4\u65b0 — \u65e0\u9700\u91cd\u542f\u5bb9\u5668",
    "docker.leave_unchanged": "\u4fdd\u6301\u4e0d\u53d8",
    "docker.apply_without": "\u5e94\u7528（\u65e0\u9700\u91cd\u65b0\u521b\u5efa）",
    "docker.docker_default": "Docker \u9ed8\u8ba4",
    "docker.params_loading": "\u6b63\u5728\u52a0\u8f7d\u53c2\u6570...",
  }
};

const savedLocale = localStorage.getItem('strata-locale');
let locale = savedLocale && Object.prototype.hasOwnProperty.call(I18N, savedLocale) ? savedLocale : 'en';
let theme = localStorage.getItem('strata-theme') || 'light';
let token = sessionStorage.getItem('strata-token') || '';
let username = sessionStorage.getItem('strata-username') || '';
let currentPage = 'system';
let installPoll = null;
let dockerPullPoll = null;
let features = {docker: false, webapp: false, firewall: false};
let firewallPoll = null;
let networkState = {};
const iconUrls = [];
const login = document.querySelector('#login');

function mountPanelDialog(panelId, dialogId, openId) {
  const panel = document.querySelector(panelId);
  const dialog = document.querySelector(dialogId);
  if (!panel || !dialog) return;
  dialog.appendChild(panel);
  const close = document.createElement('button');
  close.type = 'button'; close.className = 'secondary dialog-corner-close'; close.textContent = '✕';
  close.setAttribute('aria-label', t('action.close'));
  close.addEventListener('click', () => dialog.close());
  panel.prepend(close);
  document.querySelector(openId)?.addEventListener('click', () => dialog.showModal());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
}

mountPanelDialog('#docker-create-panel', '#docker-create-dialog', '#docker-create-open');
mountPanelDialog('#docker-sources-panel', '#docker-sources-dialog', '#docker-sources-open');
mountPanelDialog('#docker-config-panel', '#docker-config-dialog', '#docker-config-open');

function t(key) { return (I18N[locale] && I18N[locale][key]) || (I18N.en[key] || key); }

function applyI18n() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    if (el.tagName === 'INPUT' && (el.type === 'text' || el.type === 'url' || el.type === 'number')) {
      el.placeholder = t(key);
    } else {
      el.textContent = t(key);
    }
  });
  document.querySelector('#page-title').textContent = t('title.' + currentPage);
  document.documentElement.lang = locale;
}

function setLocale(lang) {
  locale = lang;
  localStorage.setItem('strata-locale', lang);
  applyI18n();
  const selector = document.querySelector('#language-select');
  if (selector) selector.value = lang;
}

function setTheme(mode) {
  theme = mode;
  localStorage.setItem('strata-theme', mode);
  document.documentElement.setAttribute('data-theme', mode === 'light' ? 'light' : '');
  document.querySelector('#theme-toggle').textContent = mode === 'light' ? '☀' : '◐';
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
}

async function api(path, options = {}) {
  const headers = {...(options.headers || {}), Authorization: `Bearer ${token}`};
  if (options.body) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {...options, headers, cache: 'no-store'});
  if (response.status === 401) {
    token = '';
    sessionStorage.removeItem('strata-token');
    sessionStorage.removeItem('strata-username');
    if (!login.open) login.showModal();
    throw new Error('unauthorized');
  }
  const result = await response.json();
  if (result.error) throw new Error(result.error);
  return result;
}

async function signIn(account, password) {
  const response = await fetch(`/cgi-bin/login?username=${encodeURIComponent(account)}`, {
    method: 'POST', headers: {'Content-Type': 'text/plain'},
    body: password, cache: 'no-store',
  });
  const result = await response.json();
  if (!response.ok || result.error) throw new Error(result.error || 'Unable to sign in');
  token = result.token;
  username = result.username;
  sessionStorage.setItem('strata-token', token);
  sessionStorage.setItem('strata-username', username);
  document.querySelector('#password').value = '';
  if (result.setup_required) {
    document.querySelector('#webui-setup').showModal();
    return;
  }
  await loadFeatures();
  await navigate(currentPage);
}

function formatBytes(kib) {
  const bytes = Number(kib || 0) * 1024;
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GiB`;
  if (bytes >= 1024 ** 2) return `${Math.round(bytes / 1024 ** 2)} MiB`;
  return `${Math.round(bytes / 1024)} KiB`;
}

function formatUptime(seconds) {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return [days && `${days}d`, hours && `${hours}h`, `${minutes}m`].filter(Boolean).join(' ');
}

function metric(label, value, detail = '') {
  return `<div class="metric"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong>${detail ? `<div class="subvalue">${escapeHtml(detail)}</div>` : ''}</div>`;
}

function detail(label, value) {
  return `<div><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value || '—')}</dd></div>`;
}

async function loadSystem() {
  const info = await api('/cgi-bin/system');
  document.querySelector('#connection').textContent = username ? `${username}@${info.hostname}` : info.hostname;
  const memoryUsed = Math.max(0, info.memory_total_kib - info.memory_available_kib);
  document.querySelector('#system-summary').innerHTML = [
    metric(t('system.hostname'), info.hostname, formatUptime(info.uptime_seconds)),
    metric('Memory', formatBytes(memoryUsed), `${formatBytes(info.memory_total_kib)} total`),
    metric('Root Filesystem', formatBytes(info.disk_used_kib), `${formatBytes(info.disk_total_kib)} total`),
    metric('System Load', info.load, `${info.cpu_count} logical processors`),
  ].join('');

  document.querySelector('#system-details').innerHTML = [
    detail('Operating System', info.os), detail('Hostname', info.hostname), detail('Kernel', info.kernel),
    detail('Architecture', info.architecture), detail('Processor', info.cpu_model),
    detail('Logical Processors', info.cpu_count), detail('Hardware', info.hardware),
    detail('Firmware', info.firmware), detail('Virtualization', info.virtualization),
    detail('Network Interfaces', info.network_interface_count), detail('Machine ID', info.machine_id),
  ].join('');

  document.querySelector('#system-resources').innerHTML = [
    detail('Memory available', formatBytes(info.memory_available_kib)),
    detail('Swap total', formatBytes(info.swap_total_kib)), detail('Swap free', formatBytes(info.swap_free_kib)),
    detail('Persistent data used', formatBytes(info.data_used_kib)), detail('Persistent data available', formatBytes(info.data_available_kib)),
    detail('Processes', info.process_count), detail('Boot ID', info.boot_id), detail('Local time', info.local_time),
  ].join('');

}

async function loadSettings() {
  const [info, cfg] = await Promise.all([api('/cgi-bin/system'), api('/cgi-bin/system-config?view=settings')]);
  document.querySelector('#hostname-input').value = info.hostname;
  if (cfg.logging_mode) document.querySelector('#sysconfig-form').elements.logging_mode.value = cfg.logging_mode;
  if (cfg.kernel_tuning) document.querySelector('#sysconfig-form').elements.swappiness.value = cfg.kernel_tuning.swappiness || '';
}

function storageOption(device) {
  return `<option value="${escapeHtml(device.path)}">${escapeHtml(device.path)} (${formatBytes(Number(device.size || 0) / 1024)})</option>`;
}

function flattenStorage(devices) {
  return devices.flatMap(device => [device, ...(device.children || [])]);
}

async function loadStorage() {
  const [storage, cfg] = await Promise.all([api('/cgi-bin/storage'), api('/cgi-bin/system-config?view=storage')]);
  const devices = flattenStorage(storage.blockdevices || []);
  const usable = devices.filter(device => device.type === 'part' && !device.ro);
  const mounted = devices.filter(device => (device.mountpoints || []).some(Boolean));
  const capacity = devices.reduce((total, device) => total + Number(device.size || 0), 0);
  document.querySelector('#storage-summary').innerHTML = [
    metric('Detected devices', String(devices.length), `${usable.length} writable partitions`),
    metric('Mounted filesystems', String(mounted.length)),
    metric('Raw capacity', formatBytes(capacity / 1024)),
    metric('Component volumes', String((cfg.components || []).reduce((total, item) => total + (item.volumes || []).length, 0))),
  ].join('');
  document.querySelector('#storage-devices').innerHTML = devices.map(device => {
    const points = (device.mountpoints || []).filter(Boolean).join(', ') || '—';
    const protectedDevice = (device.mountpoints || []).some(point => point === '/' || point === '/state' || point === '/boot');
    const canMount = device.type === 'part' && !device.ro && !device.fstype && !protectedDevice;
    const canUnmount = device.type === 'part' && !device.ro && !protectedDevice && points !== '—';
    return `<tr><td><strong>${escapeHtml(device.path || device.name)}</strong><br><small>${escapeHtml(device.model || device.type || '')}</small></td><td>${formatBytes(Number(device.size || 0) / 1024)}</td><td>${escapeHtml(device.fstype || 'unformatted')}${device.label ? ` (${escapeHtml(device.label)})` : ''}</td><td>${escapeHtml(points)}</td><td class="storage-actions">${canMount ? `<button class="secondary" data-storage-action="select-mount" data-device="${escapeHtml(device.path)}">Mount</button>` : ''}${canUnmount ? `<button class="secondary" data-storage-action="unmount" data-device="${escapeHtml(device.path)}">Unmount</button>` : ''}${device.type === 'part' && !device.ro && !protectedDevice && points === '—' ? `<button class="danger" data-storage-action="select-format" data-device="${escapeHtml(device.path)}">Format</button>` : ''}</td></tr>`;
  }).join('') || '<tr><td colspan="5" class="state-muted">No block devices available.</td></tr>';
  const options = usable.map(storageOption).join('');
  document.querySelector('#storage-mount-device').innerHTML = options;
  document.querySelector('#storage-format-device').innerHTML = usable.filter(device => !(device.mountpoints || []).some(Boolean)).map(storageOption).join('');
  renderComponents(cfg.components || []);
}

function renderComponents(components) {
  const target = document.querySelector('#component-list');
  target.innerHTML = components.map(component => `<article class="volume-card">
    <div class="volume-card-header"><h3>${escapeHtml(component.name)}</h3><span class="badge">${(component.volumes || []).length} volume(s)</span></div>
    ${(component.volumes || []).map(volume => `<div class="component-volume">
      <div class="volume-card-stats">
        <div class="volume-stat"><span class="vs-label">ID</span><span class="vs-value">${escapeHtml(volume.id)}</span></div>
        <div class="volume-stat"><span class="vs-label">${t('volume.mount')}</span><span class="vs-value">${escapeHtml(volume.mount)}</span></div>
        <div class="volume-stat"><span class="vs-label">${t('volume.current')}</span><span class="vs-value">${volume.current_size_mib} MiB</span></div>
        <div class="volume-stat"><span class="vs-label">${t('volume.usage')}</span><span class="vs-value">${volume.used_mib} MiB</span></div>
        <div class="volume-stat"><span class="vs-label">Redundancy</span><span class="vs-value">${escapeHtml(volume.redundancy)}</span></div>
      </div>
      <form class="volume-card-form" data-component="${escapeHtml(component.name)}" data-volume-id="${escapeHtml(volume.id)}">
        <label>${t('volume.size_mib')}<input name="size_mib" type="number" min="${volume.current_size_mib}" value="${volume.configured_size_mib}" required></label>
        <label>${t('volume.growth')}<select name="growth"><option value="boot-only">${t('volume.boot_only')}</option><option value="grow-only">${t('volume.grow_only')}</option><option value="fixed">${t('volume.fixed')}</option><option value="inherit">${t('volume.inherit')}</option></select></label>
        <button type="submit">${t('action.save')}</button>
      </form>
    </div>`).join('') || `<p class="state-muted">${t('system.no_volume')}</p>`}
  </article>`).join('');
  target.querySelectorAll('.volume-card-form').forEach(form => {
    form.elements.growth.value = components.find(item => item.name === form.dataset.component)?.volumes.find(item => item.id === form.dataset.volumeId)?.growth || 'boot-only';
  });
}

async function loadNetwork() {
  const net = await api('/cgi-bin/network');
  networkState = net;
  const interfaces = net.interfaces || [];
  document.querySelector('#network-summary').innerHTML = [
    metric(t('network.interfaces'), String(interfaces.length), `${interfaces.filter(i => i.state === 'up').length} active`),
    metric(t('network.dns'), String((net.dns || []).length), (net.dns || []).join(', ') || t('status.none')),
    metric(t('network.routes'), String((net.routes || []).length)),
    metric(t('table.gateway'), interfaces.find(i => i.gateway)?.gateway || interfaces.find(i => i.gateway6)?.gateway6 || '—'),
  ].join('');

  document.querySelector('#network-interfaces').innerHTML = interfaces.map(iface => {
    const up = iface.state === 'up';
    return `<div class="iface-card">
      <div class="iface-card-header">
        <h3>${escapeHtml(iface.name)} <span class="badge">${escapeHtml(iface.type || 'ethernet')}</span> <span class="iface-state ${up ? 'iface-up' : 'iface-down'}">${up ? 'UP' : 'DOWN'}</span></h3>
      </div>
      <div class="iface-card-body">
        <div class="iface-field"><span class="label">MAC</span><span class="value">${escapeHtml(iface.mac || '—')}</span></div>
        <div class="iface-field"><span class="label">IPv4</span><span class="value">${escapeHtml(iface.ipv4 || '—')}</span></div>
        <div class="iface-field"><span class="label">IPv6</span><span class="value">${escapeHtml(iface.ipv6 || '—')}</span></div>
        <div class="iface-field"><span class="label">Gateway</span><span class="value">${escapeHtml(iface.gateway || '—')}</span></div>
        <div class="iface-field"><span class="label">Speed</span><span class="value">${iface.speed > 0 ? iface.speed + ' Mbps' : '—'}</span></div>
        <div class="iface-field"><span class="label">RX</span><span class="value">${formatBytes(iface.rx_bytes / 1024)}</span></div>
        <div class="iface-field"><span class="label">TX</span><span class="value">${formatBytes(iface.tx_bytes / 1024)}</span></div>
      </div>
      <div class="iface-card-actions">
        <label class="protocol-picker"><span>${t('network.protocol')}</span><select data-protocol-for="${escapeHtml(iface.name)}"><option value="dhcp">DHCP client</option><option value="static">Static address</option><option value="pppoe">PPPoE</option></select></label>
        <button data-net-action="configure-protocol" data-iface="${escapeHtml(iface.name)}">${t('network.configure')}</button>
        ${(net.pppoe || {}).interface === iface.name ? `<span class="badge">PPPoE · ${(net.pppoe || {}).running ? t('status.running') : t('status.not_running')}</span>` : ''}
      </div>
    </div>`;
  }).join('') || '<div class="empty-state compact">'+t('status.no_interfaces')+'</div>';

  document.querySelector('#dns-servers').value = (net.dns || []).join(', ');

  const interfaceOptions = interfaces.map(item => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)}${item.mac ? ` · ${escapeHtml(item.mac)}` : ''}</option>`).join('');
  document.querySelectorAll('.physical-interface-select').forEach(select => { const selected = select.value; select.innerHTML = interfaceOptions; if ([...select.options].some(option => option.value === selected)) select.value = selected; });
  const nat = net.nat || {};
  const natForm = document.querySelector('#nat-form');
  natForm.elements.nat4_mode.value = nat.ipv4_mode || 'off'; natForm.elements.nat6_mode.value = nat.ipv6_mode || 'off';
  if (nat.ipv4_interface) natForm.elements.nat4_interface.value = nat.ipv4_interface;
  if (nat.ipv6_interface) natForm.elements.nat6_interface.value = nat.ipv6_interface;

  document.querySelector('#routes-body').innerHTML = (net.routes || []).map(r =>
    `<tr><td><span class="badge">IPv${r.family || 4}</span> ${escapeHtml(r.dest)}</td><td>${escapeHtml(r.gateway || '—')}</td><td>${escapeHtml(r.device)}</td></tr>`
  ).join('') || '<tr><td colspan="3" class="state-muted">'+t('status.no_routes')+'</td></tr>';

  // Pre-fill network tuning
  try {
    const scfg = await api('/cgi-bin/system-config');
    if (scfg.kernel_tuning) {
      document.querySelector('#network-tuning-form').elements.net_tcp_cc.value = scfg.kernel_tuning.tcp_congestion || '';
      document.querySelector('#network-tuning-form').elements.net_qdisc.value = scfg.kernel_tuning.default_qdisc || '';
      const tfoVal = scfg.kernel_tuning.tcp_fastopen;
      document.querySelector('#network-tuning-form').elements.net_tfo.value = tfoVal !== undefined && tfoVal !== null ? String(tfoVal) : '';
      document.querySelector('#network-tuning-form').elements.net_mtu_probing.value = String(scfg.kernel_tuning.tcp_mtu_probing ?? '');
      document.querySelector('#network-tuning-form').elements.net_ipv4_forward.value = String(scfg.kernel_tuning.ipv4_forward ?? '');
      document.querySelector('#network-tuning-form').elements.net_rp_filter.value = String(scfg.kernel_tuning.rp_filter ?? '');
    }
  } catch (e) { console.error('net tuning load error:', e); }
}

async function loadDocker() {
  const target = document.querySelector('#docker-summary');
  const body = document.querySelector('#docker-containers');
  const images = document.querySelector('#docker-images');
  const [info, sources] = await Promise.all([api('/cgi-bin/docker'), api('/cgi-bin/docker-sources')]);
  renderDockerSources(sources.mirrors || []);
  if (!info.installed) {
    target.innerHTML = metric('Docker', t('status.not_installed'), t('status.install_docker'));
    body.innerHTML = '<tr><td colspan="5" class="state-muted">'+t('status.docker_not_installed')+'</td></tr>';
    images.innerHTML = '<tr><td colspan="6" class="state-muted">'+t('status.docker_not_installed')+'</td></tr>';
    return;
  }
  if (!info.available) {
    target.innerHTML = metric('Docker', t('status.not_running'), t('status.unavailable'));
    body.innerHTML = '<tr><td colspan="5" class="state-muted">'+t('status.docker_not_available')+'</td></tr>';
    images.innerHTML = '<tr><td colspan="6" class="state-muted">'+t('status.start_docker_images')+'</td></tr>';
    target.insertAdjacentHTML('beforeend', '<button class="metric-action" data-daemon-action="daemon_start">Start Docker</button>');
    return;
  }
  target.innerHTML = [metric('Docker Engine', info.version, info.driver), metric('Running', info.running, `${info.container_count} containers total`), metric('Stopped', info.stopped), metric('Local Images', info.images)].join('');
  body.innerHTML = info.containers.length ? info.containers.map(container => {
    const paused = container.state === 'paused';
    const running = container.state === 'running' || paused;
    return `<tr><td>${escapeHtml(container.name)}</td><td>${escapeHtml(container.image)}</td><td title="${escapeHtml(container.id)}">${escapeHtml(container.id.slice(0, 12))}</td><td class="${running ? 'state-running' : 'state-muted'}">${escapeHtml(container.status)}</td><td><div class="table-actions"><button data-docker-action="start" data-id="${escapeHtml(container.id)}" ${running ? 'disabled' : ''}>Start</button><button class="secondary" data-docker-action="stop" data-id="${escapeHtml(container.id)}" ${running ? '' : 'disabled'}>Stop</button><button class="secondary" data-docker-action="${paused ? 'unpause' : 'pause'}" data-id="${escapeHtml(container.id)}" ${running ? '' : 'disabled'}>${paused ? 'Resume' : 'Pause'}</button><button class="secondary" data-docker-action="restart" data-id="${escapeHtml(container.id)}" ${running ? '' : 'disabled'}>Restart</button><button class="secondary" data-docker-action="params" data-name="${escapeHtml(container.name)}" data-id="${escapeHtml(container.id)}">Params</button><button class="secondary" data-docker-action="logs" data-name="${escapeHtml(container.name)}" data-id="${escapeHtml(container.id)}">Logs</button><button class="secondary" data-docker-action="terminal" data-id="${escapeHtml(container.id)}" ${running && !paused ? '' : 'disabled'}>Terminal</button><button class="danger" data-docker-action="remove" data-id="${escapeHtml(container.id)}" ${running ? 'disabled' : ''}>Remove</button></div></td></tr>`;
  }).join('') : '<tr><td colspan="5" class="state-muted">'+t('status.no_containers')+'</td></tr>';
  images.innerHTML = info.image_list.length ? info.image_list.map(image => {
    const ref = image.repository === '<none>' ? image.id : `${image.repository}:${image.tag}`;
    return `<tr><td>${escapeHtml(image.repository)}</td><td>${escapeHtml(image.tag)}</td><td title="${escapeHtml(image.id)}">${escapeHtml(image.id.replace('sha256:', '').slice(0, 12))}</td><td>${escapeHtml(image.size)}</td><td>${escapeHtml(image.created)}</td><td><div class="table-actions"><button class="secondary" data-use-image="${escapeHtml(ref)}">Create</button><button class="danger" data-remove-image="${escapeHtml(image.id)}">Remove</button></div></td></tr>`;
  }).join('') : '<tr><td colspan="6" class="state-muted">'+t('status.no_images')+'</td></tr>';
  document.querySelector('#docker-image-options').innerHTML = info.image_list.filter(image => image.repository !== '<none>').map(image => `<option value="${escapeHtml(`${image.repository}:${image.tag}`)}"></option>`).join('');
  const networkSelect = document.querySelector('#docker-create-form').elements.network;
  const selectedNetwork = networkSelect.value;
  networkSelect.innerHTML = '<option value="">Docker default</option><option value="host">host</option><option value="none">none</option>' +
    (info.networks || []).filter(item => !['host', 'none'].includes(item.name)).map(item => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)} (${escapeHtml(item.driver)})</option>`).join('');
  networkSelect.value = selectedNetwork;
  document.querySelector('#docker-networks').innerHTML = (info.networks || []).map(item => `<article class="remote"><div><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.driver)} · ${escapeHtml(item.scope)}</p></div>${['host', 'none', 'bridge'].includes(item.name) ? '' : `<button class="danger" data-docker-object="network_remove" data-id="${escapeHtml(item.id)}">Remove</button>`}</article>`).join('') || '<div class="empty-state compact">No networks</div>';
  document.querySelector('#docker-volume-list').innerHTML = (info.volumes || []).map(item => `<article class="remote"><div><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.driver)} · ${escapeHtml(item.scope)}</p></div><button class="danger" data-docker-object="volume_remove" data-id="${escapeHtml(item.name)}">Remove</button></article>`).join('') || '<div class="empty-state compact">No named volumes</div>';

  // Pre-fill Docker daemon config
  try {
    const scfg = await api('/cgi-bin/system-config');
    if (scfg.docker_config) {
      document.querySelector('#docker-config-form').elements.docker_data_root.value = scfg.docker_config.data_root || '';
      document.querySelector('#docker-config-form').elements.docker_log_size.value = scfg.docker_config.log_max_size || '10m';
      document.querySelector('#docker-config-form').elements.docker_log_file.value = scfg.docker_config.log_max_file || '3';
      document.querySelector('#docker-config-form').elements.docker_log_driver.value = scfg.docker_config.log_driver || 'local';
      document.querySelector('#docker-config-form').elements.docker_log_level.value = scfg.docker_config.log_level || 'info';
      document.querySelector('#docker-config-form').elements.docker_auto_start.value = String(!!scfg.docker_config.auto_start);
      document.querySelector('#docker-config-form').elements.docker_live_restore.value = String(!!scfg.docker_config.live_restore);
      document.querySelector('#docker-config-form').elements.docker_userland_proxy.value = String(!!scfg.docker_config.userland_proxy);
    }
  } catch (e) { console.error('docker config load error:', e); }
}

function renderDockerSources(mirrors) {
  document.querySelector('#docker-sources').innerHTML = mirrors.length ? mirrors.map(url =>
    `<article class="remote"><div><h3>Registry mirror</h3><p>${escapeHtml(url)}</p></div><div class="remote-actions"><button class="secondary" data-docker-source-action="edit" data-url="${escapeHtml(url)}">Edit</button><button class="danger" data-docker-source-action="delete" data-url="${escapeHtml(url)}">Delete</button></div></article>`
  ).join('') : '<div class="empty-state compact">'+t('status.no_mirrors')+'</div>';
}

async function dockerAction(action, id = '', extra = {}) {
  return api('/cgi-bin/docker', {method: 'POST', body: JSON.stringify({action, id, ...extra})});
}

function showDockerPullStatus(status) {
  const container = document.querySelector('#docker-pull-progress');
  const bar = document.querySelector('#docker-pull-progress-bar');
  const label = document.querySelector('#docker-pull-status');
  const button = document.querySelector('#docker-pull-form button');
  const active = status.state === 'starting' || status.state === 'running';
  container.hidden = status.state === 'idle';
  bar.value = Number(status.progress || 0);
  button.disabled = active;
  if (active) label.textContent = `Pulling ${status.image || ''} · ${status.operation || '0/0'} · ${bar.value}%`;
  else if (status.state === 'done') label.textContent = `${status.image} pulled · ${status.operation} · 100%`;
  else if (status.state === 'error') label.textContent = `${status.image} pull failed${status.message ? ` · ${status.message}` : ''}`;
  if (!active && dockerPullPoll) {
    clearInterval(dockerPullPoll);
    dockerPullPoll = null;
    if (status.state === 'done') loadDocker().catch(error => console.error(error));
  }
}

async function pollDockerPull() {
  const status = await api('/cgi-bin/docker-pull');
  showDockerPullStatus(status);
  const active = status.state === 'starting' || status.state === 'running';
  if (active && !dockerPullPoll) {
    dockerPullPoll = setInterval(() => pollDockerPull().catch(error => {
      clearInterval(dockerPullPoll); dockerPullPoll = null;
      document.querySelector('#docker-pull-form button').disabled = false;
      console.error(error);
    }), 500);
  }
}

async function startDockerPull(image) {
  const status = await api('/cgi-bin/docker-pull', {method: 'POST', body: JSON.stringify({image})});
  showDockerPullStatus(status);
  if (dockerPullPoll) clearInterval(dockerPullPoll);
  dockerPullPoll = setInterval(() => pollDockerPull().catch(error => {
    clearInterval(dockerPullPoll); dockerPullPoll = null;
    document.querySelector('#docker-pull-form button').disabled = false;
    alert(error.message);
  }), 500);
}

async function showDockerLogs(id, name) {
  const dialog = document.querySelector('#docker-logs-dialog');
  dialog.dataset.id = id; dialog.dataset.name = name || id.slice(0, 12);
  document.querySelector('#docker-logs-title').textContent = `${dialog.dataset.name} Logs`;
  document.querySelector('#docker-logs-output').textContent = 'Loading logs...';
  if (!dialog.open) dialog.showModal();
  const result = await api('/cgi-bin/docker-logs', {method: 'POST', body: JSON.stringify({id})});
  if (dialog.dataset.id === id) {
    const output = document.querySelector('#docker-logs-output');
    output.textContent = result.logs || t('status.no_logs');
    output.scrollTop = output.scrollHeight;
  }
}

function createDockerRowList({rowsSelector, hiddenSelector, addButtonSelector, buildRow, serializeRow, parseItem}) {
  const rowsEl = document.querySelector(rowsSelector);
  const hidden = document.querySelector(hiddenSelector);
  function sync() {
    hidden.value = [...rowsEl.querySelectorAll('[data-row]')].map(serializeRow).filter(Boolean).join(',');
  }
  function addRow(initial) {
    const row = buildRow(initial || {});
    row.dataset.row = '1';
    row.addEventListener('input', sync); row.addEventListener('change', sync);
    row.querySelector('.row-remove').addEventListener('click', () => { row.remove(); sync(); });
    rowsEl.appendChild(row); sync();
    return row;
  }
  function clear() { rowsEl.innerHTML = ''; sync(); }
  function loadFromString(value) {
    clear();
    (value || '').split(',').map(item => item.trim()).filter(Boolean).forEach(item => addRow(parseItem(item)));
  }
  document.querySelector(addButtonSelector).addEventListener('click', () => addRow());
  return {addRow, clear, loadFromString, sync};
}

function buildPortRow({host = '', container = '', protocol = 'tcp'} = {}) {
  const row = document.createElement('div');
  row.className = 'docker-row';
  row.innerHTML = `<input class="row-host" placeholder="Host port (optional)" value="${escapeHtml(host)}"><span class="row-sep">:</span><input class="row-container" placeholder="Container port" value="${escapeHtml(container)}"><select class="row-protocol"><option value="tcp">TCP</option><option value="udp">UDP</option></select><button type="button" class="secondary row-remove">Remove</button>`;
  row.querySelector('.row-protocol').value = protocol;
  return row;
}
function serializePortRow(row) {
  const host = row.querySelector('.row-host').value.trim();
  const container = row.querySelector('.row-container').value.trim();
  const protocol = row.querySelector('.row-protocol').value;
  if (!container) return '';
  return `${host ? host + ':' : ''}${container}/${protocol}`;
}
function parsePortItem(item) {
  const [hostContainer, protocol] = item.split('/');
  const parts = hostContainer.split(':');
  if (parts.length >= 2) return {host: parts[0], container: parts.slice(1).join(':'), protocol: protocol || 'tcp'};
  return {host: '', container: parts[0], protocol: protocol || 'tcp'};
}

function buildVolumeRow({source = '', target = '', readonly = false} = {}) {
  const row = document.createElement('div');
  row.className = 'docker-row';
  row.innerHTML = `<input class="row-source" placeholder="/host/path or volume-name" value="${escapeHtml(source)}"><span class="row-sep">:</span><input class="row-target" placeholder="/container/path" value="${escapeHtml(target)}"><label><input type="checkbox" class="row-readonly"> Read-only</label><button type="button" class="secondary row-remove">Remove</button>`;
  row.querySelector('.row-readonly').checked = !!readonly;
  return row;
}
function serializeVolumeRow(row) {
  const source = row.querySelector('.row-source').value.trim();
  const target = row.querySelector('.row-target').value.trim();
  const readonly = row.querySelector('.row-readonly').checked;
  if (!source || !target) return '';
  return `${source}:${target}${readonly ? ':ro' : ''}`;
}
function parseVolumeItem(item) {
  const parts = item.split(':');
  const readonly = parts[parts.length - 1] === 'ro';
  if (readonly) parts.pop();
  const target = parts.pop();
  const source = parts.join(':');
  return {source, target, readonly};
}

function buildEnvRow({key = '', value = ''} = {}) {
  const row = document.createElement('div');
  row.className = 'docker-row';
  row.innerHTML = `<input class="row-key" placeholder="KEY" value="${escapeHtml(key)}"><span class="row-sep">=</span><input class="row-value" placeholder="value" value="${escapeHtml(value)}"><button type="button" class="secondary row-remove">Remove</button>`;
  return row;
}
function serializeEnvRow(row) {
  const key = row.querySelector('.row-key').value.trim();
  const value = row.querySelector('.row-value').value;
  if (!key) return '';
  return `${key}=${value}`;
}
function parseEnvItem(item) {
  const index = item.indexOf('=');
  if (index === -1) return {key: item, value: ''};
  return {key: item.slice(0, index), value: item.slice(index + 1)};
}

const dockerPortRows = createDockerRowList({
  rowsSelector: '#docker-ports-rows', hiddenSelector: '#docker-create-form input[name="ports"]',
  addButtonSelector: '#docker-port-add', buildRow: buildPortRow, serializeRow: serializePortRow, parseItem: parsePortItem,
});
const dockerVolumeRows = createDockerRowList({
  rowsSelector: '#docker-volumes-rows', hiddenSelector: '#docker-create-form input[name="volumes"]',
  addButtonSelector: '#docker-volume-add', buildRow: buildVolumeRow, serializeRow: serializeVolumeRow, parseItem: parseVolumeItem,
});
const dockerEnvRows = createDockerRowList({
  rowsSelector: '#docker-envs-rows', hiddenSelector: '#docker-create-form input[name="envs"]',
  addButtonSelector: '#docker-env-add', buildRow: buildEnvRow, serializeRow: serializeEnvRow, parseItem: parseEnvItem,
});

const dockerParamLabels = {
  image: 'Image', name: 'Name', hostname: 'Hostname', domainname: 'Domain name', restart: 'Restart policy', network: 'Network',
  ip_address: 'Container IPv4', mac_address: 'MAC address',
  workdir: 'Working directory', user: 'User', entrypoint: 'Entrypoint', memory: 'Memory limit (bytes)',
  memory_swap: 'Memory + swap', cpus: 'CPU limit', cpuset_cpus: 'CPU set', pids_limit: 'PID limit', shm_size: 'Shared memory',
  privileged: 'Privileged', auto_remove: 'Auto-remove', init_process: 'Init process', publish_all: 'Publish all ports', stdin_open: 'Keep stdin open',
  tty: 'Allocate TTY', readonly: 'Read-only root filesystem', envs: 'Environment variables',
  ports: 'Published ports', volumes: 'Volumes / bind mounts', labels: 'Labels', dns: 'DNS servers',
  extra_hosts: 'Extra hosts', devices: 'Devices', cap_add: 'Capabilities added', cap_drop: 'Capabilities dropped', security_opt: 'Security options',
  sysctls: 'Sysctls', tmpfs: 'Tmpfs mounts', dns_search: 'DNS search', group_add: 'Additional groups', stop_signal: 'Stop signal',
  command: 'Command',
}

function formatDockerParams(params) {
  return Object.keys(dockerParamLabels).map(key => {
    let value = params[key];
    if (typeof value === 'boolean') value = value ? 'yes' : 'no';
    return `${dockerParamLabels[key]}: ${value === '' || value === undefined || value === null ? '-' : value}`;
  }).join('\n');
}

async function showDockerParams(id, name) {
  const dialog = document.querySelector('#docker-params-dialog');
  const label = name || id.slice(0, 12);
  dialog.dataset.id = id; dialog.dataset.name = label;
  document.querySelector('#docker-params-title').textContent = `${label} Parameters`;
  document.querySelector('#docker-params-output').textContent = t('docker.params_loading');
  document.querySelector('#docker-quick-update-form').reset();
  if (!dialog.open) dialog.showModal();
  const params = await api(`/cgi-bin/docker?inspect=${encodeURIComponent(id)}`);
  if (dialog.dataset.id !== id) return;
  dialog.dockerParams = params;
  document.querySelector('#docker-params-output').textContent = formatDockerParams(params);
  document.querySelector('#docker-quick-update-form').elements.restart.value = params.restart || '';
}

function consoleModeFor(params) {
  if (params.tty && params.stdin_open) return 'interactive';
  if (params.tty) return 'tty';
  return 'none';
}

function enterDockerEditMode(id, params) {
  const form = document.querySelector('#docker-create-form');
  resetDockerCreateForm();
  document.querySelector('#docker-edit-id').value = id;
  for (const name of ['image', 'name', 'hostname', 'domainname', 'restart', 'network', 'ip_address', 'mac_address', 'workdir', 'user', 'entrypoint',
    'memory', 'memory_swap', 'cpus', 'cpuset_cpus', 'pids_limit', 'shm_size', 'labels', 'dns', 'dns_search', 'extra_hosts', 'devices', 'cap_add', 'cap_drop',
    'security_opt', 'sysctls', 'tmpfs', 'group_add', 'stop_signal', 'stop_timeout', 'health_cmd', 'health_interval', 'health_timeout', 'health_start_period', 'health_retries', 'command']) {
    if (form.elements[name] && params[name] !== undefined) form.elements[name].value = params[name];
  }
  for (const name of ['privileged', 'readonly', 'auto_remove', 'init_process', 'publish_all']) {
    if (form.elements[name]) form.elements[name].checked = !!params[name];
  }
  form.elements.console_mode.value = consoleModeFor(params);
  dockerPortRows.loadFromString(params.ports);
  dockerVolumeRows.loadFromString(params.volumes);
  dockerEnvRows.loadFromString(params.envs);
  document.querySelector('#docker-create-heading').textContent = t('docker.edit_container');
  document.querySelector('#docker-create-subtitle').textContent = t('docker.edit_subtitle');
  document.querySelector('#docker-edit-name').textContent = params.name || id.slice(0, 12);
  document.querySelector('#docker-edit-notice').hidden = false;
  document.querySelector('#docker-create-submit').textContent = t('docker.save_changes');
  document.querySelector('#docker-edit-cancel').hidden = false;
  const dialog = document.querySelector('#docker-create-dialog');
  if (!dialog.open) dialog.showModal();
}

function resetDockerCreateForm() {
  document.querySelector('#docker-create-form').reset();
  dockerPortRows.clear(); dockerVolumeRows.clear(); dockerEnvRows.clear();
}

function exitDockerEditMode() {
  resetDockerCreateForm();
  document.querySelector('#docker-edit-id').value = '';
  document.querySelector('#docker-create-heading').textContent = t('docker.create');
  document.querySelector('#docker-create-subtitle').textContent = t('docker.create_desc');
  document.querySelector('#docker-edit-notice').hidden = true;
  document.querySelector('#docker-create-submit').textContent = t('docker.deploy');
  document.querySelector('#docker-edit-cancel').hidden = true;
}

async function openDockerTerminal(id, popup) {
  const result = await api('/cgi-bin/docker-terminal', {method: 'POST', body: JSON.stringify({id})});
  const host = location.hostname.includes(':') ? `[${location.hostname}]` : location.hostname;
  popup.location.href = `${location.protocol}//${host}:${result.port}/`;
}

async function loadApps() {
  const apps = await api('/cgi-bin/apps');
  for (const url of iconUrls) URL.revokeObjectURL(url);
  iconUrls.length = 0;
  document.querySelector('#apps').innerHTML = apps.length ? apps.map(app => {
    const img = app.icon_url ? `<img class="app-icon" data-icon-app="${escapeHtml(app.app_id)}" alt="" hidden>` : '';
    const running = app.session && app.session.running;
    const renderMode = running ? app.session.render_mode : 'unknown';
    let labels = '';
    if (app.sessions_count > 1) labels += `<span class="session-state">${app.sessions_count} instances</span>`;
    if (running) labels += '<span class="session-state running">Running</span>';
    return `<div class="app">
      <div class="app-card-heading">${img}<div>${img ? '<br>' : ''}${labels}</div></div>
      <h3>${escapeHtml(app.name)}</h3>
      <p>${escapeHtml(app.app_id)}</p>
      <p class="app-render-status">${escapeHtml(t('apps.render_mode'))}: ${escapeHtml(renderMode === 'gpu' ? t('apps.render_gpu') : renderMode === 'software' ? t('apps.render_software') : 'Auto (GPU preferred)')}</p>
      <div class="app-actions">
        <button data-app="${escapeHtml(app.app_id)}" data-action="start" ${running ? 'disabled' : ''}>Start</button>
        <button class="secondary" data-app="${escapeHtml(app.app_id)}" data-action="stop" ${running ? '' : 'disabled'}>Stop</button>
        <button class="secondary" data-app="${escapeHtml(app.app_id)}" data-action="view" ${running ? '' : 'disabled'}>View</button>
      </div>
    </div>`;
  }).join('') : '<div class="empty-state">'+t('status.no_apps')+'</div>';
  void loadAppIcons(apps);
}

async function loadAppIcons(apps) {
  // Keep the application list interactive while icon I/O completes. Limit
  // concurrent Flatpak export reads so a large catalogue cannot stall WebUI.
  const pending = apps.filter(app => app.icon_url);
  const workers = Array.from({length: Math.min(4, pending.length)}, async () => {
    while (pending.length) {
      const app = pending.shift();
      try {
        const response = await fetch(`/cgi-bin/icon?app_id=${encodeURIComponent(app.app_id)}`, {headers: {Authorization: `Bearer ${token}`}, cache: 'no-store'});
        const blob = await response.blob();
        if (!response.ok || !blob.type.startsWith('image/')) continue;
        const source = URL.createObjectURL(blob);
        iconUrls.push(source);
        document.querySelectorAll('[data-icon-app]').forEach(image => {
          if (image.dataset.iconApp === app.app_id) { image.src = source; image.hidden = false; }
        });
      } catch (_) { /* An icon is optional and must not block the app list. */ }
    }
  });
  await Promise.all(workers);
}

async function loadRemotes() {
  const remotes = await api('/cgi-bin/remotes');
  document.querySelector('#remotes').innerHTML = remotes.length ? remotes.map(r =>
    `<article class="remote"><div><h3>${escapeHtml(r.name)}</h3><p>${escapeHtml(r.url)}</p></div><div class="remote-actions"><button class="secondary" data-remote-action="edit" data-name="${escapeHtml(r.name)}" data-url="${escapeHtml(r.url)}">Edit</button><button class="danger" data-remote-action="delete" data-name="${escapeHtml(r.name)}">Delete</button></div></article>`
  ).join('') : '<div class="empty-state compact">'+t('status.no_sources')+'</div>';
  const sourceSelect = document.querySelector('#install-remote');
  sourceSelect.innerHTML = remotes.length ? remotes.map(r => `<option value="${escapeHtml(r.name)}">${escapeHtml(r.name)}</option>`).join('') : '<option value="" selected disabled>No source configured</option>';
  document.querySelector('#configure-flathub').hidden = remotes.length !== 0;
}

function showInstallStatus(status) {
  const container = document.querySelector('#install-progress');
  const bar = document.querySelector('#install-progress-bar');
  const label = document.querySelector('#install-status');
  const button = document.querySelector('#install-button');
  const active = status.state === 'starting' || status.state === 'running';
  container.hidden = status.state === 'idle';
  bar.value = Number(status.progress || 0);
  button.disabled = active;
  if (active) label.textContent = `Installing ${status.ref || ''} · ${status.operation || '0/0'} · ${bar.value}%`;
  else if (status.state === 'done') label.textContent = `${status.ref} installed`;
  else if (status.state === 'error') label.textContent = `Install failed: ${status.message || 'unknown error'}`;
  if (!active && installPoll) { clearInterval(installPoll); installPoll = null; if (status.state === 'done') loadApps().catch(e => console.error(e)); }
}

async function pollInstall() {
  const status = await api('/cgi-bin/install');
  showInstallStatus(status);
  const active = status.state === 'starting' || status.state === 'running';
  if (active && !installPoll) {
    installPoll = setInterval(() => pollInstall().catch(error => { clearInterval(installPoll); installPoll = null; document.querySelector('#install-button').disabled = false; alert(error.message); }), 750);
  }
}

async function installApp(ref, remote) {
  const status = await api('/cgi-bin/install', {method: 'POST', body: JSON.stringify({ref, remote})});
  showInstallStatus(status);
  if (installPoll) clearInterval(installPoll);
  installPoll = setInterval(() => pollInstall().catch(error => {
    clearInterval(installPoll); installPoll = null;
    document.querySelector('#install-button').disabled = false;
    alert(error.message);
  }), 750);
}

async function loadTerminal() {
  const result = await api('/cgi-bin/terminal-auth', {method: 'POST'});
  const frame = document.querySelector('#terminal-frame');
  const host = location.hostname.includes(':') ? `[${location.hostname}]` : location.hostname;
  frame.src = `${location.protocol}//${host}:${result.port}/`;
  frame.hidden = false;
}

async function loadTls() {
  const status = await api('/cgi-bin/tls');
  document.querySelector('#tls-summary').innerHTML = [
    metric('HTTPS', status.enabled ? 'Enabled' : 'Disabled', status.enabled ? 'TLS 1.2 or newer' : 'Web traffic is not encrypted'),
    metric('Certificate', status.configured ? (status.self_signed ? 'Self-Signed' : 'Deployed') : 'Not Configured'),
    metric('Valid From', status.not_before || '—'),
    metric('Valid Until', status.not_after || '—'),
  ].join('');
  document.querySelector('#tls-details').innerHTML = [
    detail('Subject', status.subject), detail('Issuer', status.issuer),
    detail('SHA-256 Fingerprint', status.fingerprint),
    detail('Browser URL', `${status.enabled ? 'https' : 'http'}://${location.hostname.includes(':') ? `[${location.hostname}]` : location.hostname}:9090/`),
  ].join('');
  document.querySelector('#tls-enable').hidden = status.enabled || !status.configured;
  document.querySelector('#tls-disable').hidden = !status.enabled;
  if (!document.querySelector('#tls-common-name').value) document.querySelector('#tls-common-name').value = location.hostname;

  // Load SSH config
  try {
    const sshConfig = await api('/cgi-bin/ssh');
    if (sshConfig) {
      const sshToggle = document.querySelector('#ssh-service-toggle');
      sshToggle.checked = Boolean(sshConfig.enabled);
      sshToggle.disabled = !sshConfig.available;
      document.querySelector('#ssh-config-form').elements.ssh_port.value = sshConfig.port || '';
      document.querySelector('#ssh-config-form').elements.ssh_permit_root.value = sshConfig.permit_root_login || '';
      document.querySelector('#ssh-config-form').elements.ssh_password_auth.value = sshConfig.password_auth || '';
      document.querySelector('#ssh-config-form').elements.ssh_tcp_forward.value = sshConfig.tcp_forwarding || '';
      document.querySelector('#ssh-config-form').elements.ssh_max_auth.value = sshConfig.max_auth_tries ?? '';
      document.querySelector('#ssh-config-form').elements.ssh_alive_interval.value = sshConfig.client_alive_interval ?? '';
      document.querySelector('#ssh-config-form').elements.ssh_alive_count.value = sshConfig.client_alive_count_max ?? '';
    }
  } catch (e) { console.error('ssh config load error:', e); }
}

async function fileBase64(file) {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return btoa(binary);
}

function reconnectAfterTls(enabled) {
  const direct = location.port === '9090';
  alert(t('alert.tls_restart') + (enabled ? 'HTTPS' : 'HTTP') + '.');
  if (direct) {
    const host = location.hostname.includes(':') ? `[${location.hostname}]` : location.hostname;
    setTimeout(() => location.replace(`${enabled ? 'https' : 'http'}://${host}:9090/`), 2500);
  } else {
    setTimeout(() => location.reload(), 2500);
  }
}

async function changeTls(action, values = {}) {
  const result = await api('/cgi-bin/tls', {method: 'POST', body: JSON.stringify({action, ...values})});
  reconnectAfterTls(result.enabled);
}

function renderFirewallPresets(presets, activePreset) {
  document.querySelector('#firewall-presets').innerHTML = presets.map(preset => {
    const active = preset.id === activePreset;
    return `<div class="app${active ? ' preset-active' : ''}">
      <h3>${escapeHtml(t(`firewall.preset.${preset.id}.name`))}${active ? ` <span class="session-state running">${escapeHtml(t('state.active'))}</span>` : ''}</h3>
      <p>${escapeHtml(t(`firewall.preset.${preset.id}.desc`))}</p>
      <button data-preset="${escapeHtml(preset.id)}" data-action="apply-preset" ${active ? 'disabled' : ''}>${escapeHtml(t('action.apply'))}</button>
    </div>`;
  }).join('');
}

function renderFirewallRules(rules) {
  document.querySelector('#firewall-rules').innerHTML = rules.map(rule => `
    <tr><td><span class="rule-action rule-action-${escapeHtml(rule.action)}">${escapeHtml(rule.action)}</span></td><td>${escapeHtml(rule.proto)}</td><td>${escapeHtml(rule.port)}</td>
    <td><button class="danger" data-proto="${escapeHtml(rule.proto)}" data-port="${escapeHtml(rule.port)}" data-action-type="${escapeHtml(rule.action)}" data-action="remove-rule">Remove</button></td></tr>
  `).join('');
}

function stopFirewallPoll() {
  if (firewallPoll) { clearInterval(firewallPoll); firewallPoll = null; }
}

async function loadFirewall() {
  const status = await api('/cgi-bin/firewall');
  const presets = status.presets || [];
  document.querySelector('#firewall-summary').innerHTML = [
    metric('Active Preset', presets.find(p => p.id === status.preset)?.name || status.preset),
    metric('Kernel Ruleset', status.active ? 'Active' : 'Not loaded'),
    metric('Pending Change', status.pending ? 'Awaiting confirmation' : 'None'),
  ].join('');
  renderFirewallPresets(presets, status.preset);
  renderFirewallRules(status.rules || []);
  if (status.fail2ban) {
    const form = document.querySelector('#fail2ban-form');
    const available = status.fail2ban.available !== false;
    form.elements.enabled.value = String(!!status.fail2ban.enabled);
    form.elements.maxretry.value = status.fail2ban.maxretry || 5;
    form.elements.findtime.value = String(status.fail2ban.findtime || 600);
    form.elements.bantime.value = String(status.fail2ban.bantime || 600);
    Array.from(form.elements).forEach(element => { element.disabled = !available; });
  }
  document.querySelector('#firewall-pending').hidden = !status.pending;
  if (status.pending) {
    const timeout = status.confirm_timeout || 90;
    const remaining = status.remaining != null ? status.remaining : timeout;
    document.querySelector('#firewall-countdown').max = timeout;
    document.querySelector('#firewall-countdown').value = remaining;
    document.querySelector('#firewall-countdown-label').textContent =
      remaining > 0 ? `Auto rollback in ${remaining}s` : 'Rolling back...';
    if (!firewallPoll) firewallPoll = setInterval(() => loadFirewall().catch(error => console.error(error)), 3000);
  } else {
    stopFirewallPoll();
  }
}

async function applyFirewallPreset(preset) {
  await api('/cgi-bin/firewall', {method: 'POST', body: JSON.stringify({action: 'apply_preset', preset})});
  await loadFirewall();
}

async function addFirewallRule(event) {
  event.preventDefault();
  const form = event.target;
  await api('/cgi-bin/firewall', {method: 'POST', body: JSON.stringify({
    action: 'add_rule', action_type: form.action_type.value,
    proto: form.proto.value, port: form.port.value,
  })});
  form.reset();
  await loadFirewall();
}

async function removeFirewallRule(proto, port, actionType) {
  await api('/cgi-bin/firewall', {method: 'POST', body: JSON.stringify({action: 'remove_rule', action_type: actionType, proto, port})});
  await loadFirewall();
}

async function confirmFirewall() {
  await api('/cgi-bin/firewall', {method: 'POST', body: JSON.stringify({action: 'confirm'})});
  await loadFirewall();
}

async function rollbackFirewall() {
  await api('/cgi-bin/firewall', {method: 'POST', body: JSON.stringify({action: 'rollback'})});
  await loadFirewall();
}

async function startApp(appId) {
  await api('/cgi-bin/session', {method: 'POST', body: JSON.stringify({app_id: appId})});
  await loadApps();
}

async function stopApp(appId) {
  await api('/cgi-bin/session', {method: 'POST', body: JSON.stringify({action: 'stop', app_id: appId})});
  await loadApps();
}

function viewApp(appId) {
  sessionStorage.setItem('strata-token', token);
  const name = `strata-flatpak-${appId.replace(/[^A-Za-z0-9_-]/g, '-')}`;
  const viewer = window.open(`/viewer.html?app_id=${encodeURIComponent(appId)}`, name, 'popup=yes,width=1120,height=760,resizable=yes');
  if (!viewer) throw new Error(t('alert.popup_blocked'));
  viewer.focus();
}

const titles = {
  system: 'System Configuration & Information', network: 'Network Configuration',
  terminal: 'Web Terminal', security: 'HTTPS & Certificates', firewall: 'Firewall',
  docker: 'Docker', apps: 'Application Center', storage: 'Storage Management', settings: 'System Settings'
};

async function navigate(page) {
  if ((page === 'docker' && !features.docker) || (page === 'apps' && !features.webapp) || (page === 'firewall' && !features.firewall) || (page === 'storage' && !features.storage)) page = 'system';
  currentPage = page;
  document.querySelectorAll('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.page === page));
  document.querySelectorAll('.page').forEach(item => item.classList.toggle('active', item.id === `page-${page}`));
  document.querySelector('#page-title').textContent = t('title.' + page);
  if (page === 'system') await loadSystem();
  if (page === 'storage') await loadStorage();
  if (page === 'settings') await loadSettings();
  if (page === 'network') await loadNetwork();
  if (page === 'terminal' && document.querySelector('#terminal-frame').hidden) await loadTerminal();
  if (page === 'security') await loadTls();
  if (page === 'firewall') await loadFirewall();
  if (page === 'docker') await Promise.all([loadDocker(), pollDockerPull()]);
  if (page === 'apps') await Promise.all([loadApps(), loadRemotes()]);
}

function confirmPower(action) {
  const dialog = document.querySelector('#confirm');
  document.querySelector('#confirm-title').textContent = action === 'reboot' ? 'Restart the system?' : 'Shut down the system?';
  document.querySelector('#confirm-message').textContent = 'Active terminal and application sessions will be interrupted immediately. Unsaved data may be lost.';
  dialog.dataset.action = action;
  dialog.showModal();
}

async function loadFeatures() {
  try { features = await api('/cgi-bin/features'); } catch (e) { console.error(e); }
  document.querySelectorAll('.nav-item[data-page="firewall"]').forEach(el => el.hidden = !features.firewall);
  document.querySelectorAll('.nav-item[data-page="docker"]').forEach(el => el.hidden = !features.docker);
  document.querySelectorAll('.nav-item[data-page="apps"]').forEach(el => el.hidden = !features.webapp);
  document.querySelectorAll('.nav-item[data-page="storage"]').forEach(el => el.hidden = !features.storage);
}

// ===== Event Listeners =====
login.addEventListener('close', async () => {
  if (login.returnValue !== 'login') return;
  try {
    await signIn(document.querySelector('#username').value.trim(), document.querySelector('#password').value);
  } catch (error) {
    document.querySelector('#password').value = '';
    alert(error.message);
    if (!login.open) login.showModal();
  }
});
login.addEventListener('cancel', event => event.preventDefault());
document.querySelector('#webui-setup').addEventListener('cancel', event => event.preventDefault());
document.querySelector('#webui-setup-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.target;
  if (form.elements.root_password.value !== form.elements.root_confirm.value || form.elements.user_password.value !== form.elements.user_confirm.value) { alert('Passwords do not match'); return; }
  const encode = value => btoa(String.fromCharCode(...new TextEncoder().encode(value)));
  try {
    const result = await api('/cgi-bin/setup', {method: 'POST', body: JSON.stringify({username: form.elements.username.value.trim(), root_password: encode(form.elements.root_password.value), user_password: encode(form.elements.user_password.value)})});
    token = ''; username = ''; sessionStorage.removeItem('strata-token'); sessionStorage.removeItem('strata-username');
    document.querySelector('#webui-setup').close(); form.reset(); document.querySelector('#username').value = result.username; if (!login.open) login.showModal();
  } catch (error) { alert(error.message); }
});

document.querySelectorAll('.nav-item').forEach(item => item.addEventListener('click', () => navigate(item.dataset.page).catch(error => alert(error.message))));
document.querySelector('#refresh-page').addEventListener('click', () => navigate(currentPage).catch(error => alert(error.message)));

document.querySelector('#logout').addEventListener('click', async () => {
  try { if (token) await api('/cgi-bin/logout', {method: 'POST'}); } catch (error) { console.error(error); }
  token = ''; username = '';
  sessionStorage.removeItem('strata-token'); sessionStorage.removeItem('strata-username');
  document.querySelector('#terminal-frame').src = 'about:blank';
  document.querySelector('#terminal-frame').hidden = true;
  if (!login.open) login.showModal();
});

// Theme toggle
document.querySelector('#theme-toggle').addEventListener('click', () => setTheme(theme === 'dark' ? 'light' : 'dark'));
document.querySelector('#language-select').addEventListener('change', event => setLocale(event.target.value));

// Hostname form
document.querySelector('#hostname-form').addEventListener('submit', async event => {
  event.preventDefault();
  const newName = document.querySelector('#hostname-input').value.trim();
  if (!newName) return;
  try {
    await api('/cgi-bin/hostname', {method: 'POST', body: JSON.stringify({hostname: newName})});
    await loadSettings();
  } catch (error) { alert(error.message); }
});

// System config form (Logging + Swap)
document.querySelector('#sysconfig-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  const logMode = form.elements.logging_mode.value;
  const swappiness = form.elements.swappiness.value;
  const swapState = form.elements.swap_state.value;
  const swapSize = form.elements.swap_size_mib.value;
  try {
    if (logMode) await api('/cgi-bin/system-config', {method: 'POST', body: JSON.stringify({action: 'logging_mode', mode: logMode})});
    if (swappiness || swapState) {
      const kt = {action: 'kernel_tuning'};
      if (swappiness) kt.swappiness = parseInt(swappiness, 10);
      if (swapState) kt.swap_state = swapState;
      await api('/cgi-bin/system-config', {method: 'POST', body: JSON.stringify(kt)});
    }
    if (swapSize) await api('/cgi-bin/system-config', {method: 'POST', body: JSON.stringify({action: 'create_swap', size_mib: parseInt(swapSize, 10)})});
    alert(t('alert.save_ok'));
  } catch (error) { alert(error.message); }
});

document.querySelector('#component-list').addEventListener('submit', async event => {
  const form = event.target.closest('.volume-card-form');
  if (!form) return;
  event.preventDefault();
  const common = {component: form.dataset.component, volume_id: form.dataset.volumeId};
  try {
    await api('/cgi-bin/system-config', {method: 'POST', body: JSON.stringify({action: 'set_volume_size', ...common, size_mib: Number(form.elements.size_mib.value)})});
    await api('/cgi-bin/system-config', {method: 'POST', body: JSON.stringify({action: 'set_growth', ...common, growth: form.elements.growth.value})});
    alert(t('alert.save_ok'));
    await loadStorage();
  } catch (error) { alert(error.message); }
});
document.querySelector('#refresh-storage').addEventListener('click', () => loadStorage().catch(error => alert(error.message)));
document.querySelector('#storage-devices').addEventListener('click', event => {
  const button = event.target.closest('[data-storage-action]');
  if (!button) return;
  const device = button.dataset.device;
  if (button.dataset.storageAction === 'select-mount') {
    document.querySelector('#storage-mount-device').value = device;
    document.querySelector('#storage-mount-form').elements.mount_name.focus();
    return;
  }
  if (button.dataset.storageAction === 'select-format') {
    document.querySelector('#storage-format-device').value = device;
    document.querySelector('#storage-format-form').elements.label.focus();
    return;
  }
  if (button.dataset.storageAction === 'unmount' && confirm(`Unmount ${device}?`)) {
    api('/cgi-bin/storage', {method: 'POST', body: JSON.stringify({action: 'unmount', device})}).then(loadStorage).catch(error => alert(error.message));
  }
});
document.querySelector('#storage-mount-form').addEventListener('submit', event => {
  event.preventDefault();
  const form = event.target;
  api('/cgi-bin/storage', {method: 'POST', body: JSON.stringify({action: 'mount', device: form.elements.device.value, mount_name: form.elements.mount_name.value})}).then(loadStorage).catch(error => alert(error.message));
});
document.querySelector('#storage-format-form').addEventListener('submit', event => {
  event.preventDefault();
  const form = event.target;
  const device = form.elements.device.value;
  if (!confirm(`Format ${device}? All data on this partition will be erased.`)) return;
  api('/cgi-bin/storage', {method: 'POST', body: JSON.stringify({action: 'format', device, filesystem: form.elements.filesystem.value, label: form.elements.label.value})}).then(loadStorage).catch(error => alert(error.message));
});

// Network tuning form
document.querySelector('#network-tuning-form').addEventListener('submit', async event => {
  event.preventDefault();
  const f = event.target;
  const kt = {action: 'kernel_tuning'};
  if (f.elements.net_tcp_cc.value) kt.tcp_congestion = f.elements.net_tcp_cc.value;
  if (f.elements.net_qdisc.value) kt.qdisc = f.elements.net_qdisc.value;
  if (f.elements.net_tfo.value) kt.tcp_fastopen = parseInt(f.elements.net_tfo.value, 10);
  if (f.elements.net_mtu_probing.value !== '') kt.tcp_mtu_probing = parseInt(f.elements.net_mtu_probing.value, 10);
  if (f.elements.net_ipv4_forward.value !== '') kt.ipv4_forward = parseInt(f.elements.net_ipv4_forward.value, 10);
  if (f.elements.net_rp_filter.value !== '') kt.rp_filter = parseInt(f.elements.net_rp_filter.value, 10);
  if (Object.keys(kt).length > 1) {
    try {
      await api('/cgi-bin/system-config', {method: 'POST', body: JSON.stringify(kt)});
      alert(t('alert.save_ok'));
    } catch (error) { alert(error.message); }
  }
});

// Docker daemon config form
document.querySelector('#docker-config-form').addEventListener('submit', async event => {
  event.preventDefault();
  const f = event.target;
  const dc = {action: 'docker_config'};
  if (f.elements.docker_data_root.value.trim()) dc.data_root = f.elements.docker_data_root.value.trim();
  if (f.elements.docker_log_size.value.trim()) dc.log_max_size = f.elements.docker_log_size.value.trim();
  if (f.elements.docker_log_file.value) dc.log_max_file = f.elements.docker_log_file.value;
  dc.log_driver = f.elements.docker_log_driver.value;
  dc.log_level = f.elements.docker_log_level.value;
  dc.auto_start = f.elements.docker_auto_start.value === 'true';
  dc.live_restore = f.elements.docker_live_restore.value === 'true';
  dc.userland_proxy = f.elements.docker_userland_proxy.value === 'true';
  if (Object.keys(dc).length > 1) {
    try {
      await api('/cgi-bin/system-config', {method: 'POST', body: JSON.stringify(dc)});
      alert(t('alert.save_ok'));
      document.querySelector('#docker-config-dialog').close();
      await loadDocker();
    } catch (error) { alert(error.message); }
  }
});

// SSH config form
document.querySelector('#ssh-config-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = event.target;
  const sc = {action: 'ssh_config'};
  if (form.elements.ssh_port.value.trim()) sc.port = form.elements.ssh_port.value.trim();
  if (form.elements.ssh_permit_root.value) sc.permit_root_login = form.elements.ssh_permit_root.value;
  if (form.elements.ssh_password_auth.value) sc.password_auth = form.elements.ssh_password_auth.value;
  if (form.elements.ssh_tcp_forward.value) sc.tcp_forwarding = form.elements.ssh_tcp_forward.value;
  if (form.elements.ssh_max_auth.value) sc.max_auth_tries = parseInt(form.elements.ssh_max_auth.value, 10);
  if (form.elements.ssh_alive_interval.value) sc.client_alive_interval = parseInt(form.elements.ssh_alive_interval.value, 10);
  if (form.elements.ssh_alive_count.value) sc.client_alive_count_max = parseInt(form.elements.ssh_alive_count.value, 10);
  try {
    await api('/cgi-bin/ssh', {method: 'POST', body: JSON.stringify(sc)});
    alert(t('action.save') + ' OK');
  } catch (error) { alert(error.message); }
});

document.querySelector('#ssh-service-toggle').addEventListener('change', async event => {
  const toggle = event.target;
  const enabled = toggle.checked;
  toggle.disabled = true;
  try {
    await api('/cgi-bin/ssh', {method: 'POST', body: JSON.stringify({action: 'ssh_service', enabled})});
    alert(t('alert.save_ok'));
  } catch (error) {
    toggle.checked = !enabled;
    alert(error.message);
  } finally {
    toggle.disabled = false;
  }
});

// Network actions
document.addEventListener('click', async event => {
  const btn = event.target.closest('[data-net-action]');
  if (!btn) return;
  const action = btn.dataset.netAction;
  const iface = btn.dataset.iface;
  if (!action) return;
  if (action === 'configure-protocol') {
    const protocol = document.querySelector(`[data-protocol-for="${iface}"]`).value;
    if (protocol === 'dhcp') {
      btn.disabled = true;
      try {
        await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_dhcp', interface: iface})});
        await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_ipv6_auto', interface: iface})});
        await loadNetwork();
      } catch (error) { alert(error.message); }
      btn.disabled = false; return;
    }
    const dialog = document.querySelector('#network-config-dialog');
    document.querySelector('#network-config-title').textContent = `${iface} · ${protocol === 'pppoe' ? 'PPPoE' : t('network.configure')}`;
    const pppoe = networkState.pppoe || {};
    document.querySelector('#network-config-body').innerHTML = protocol === 'pppoe' ? `<div class="iface-static-form protocol-form"><label>${t('network.username')}<input name="username" value="${pppoe.interface === iface ? escapeHtml(pppoe.username || '') : ''}" autocomplete="username"></label><label>${t('network.password')}<input name="password" type="password" autocomplete="current-password"></label><label>IPv6 / IP6CP<select name="ipv6"><option value="true">${t('state.enabled')}</option><option value="false">${t('state.disabled')}</option></select></label><button data-net-action="apply-protocol-pppoe" data-iface="${escapeHtml(iface)}">${t('network.connect')}</button><button class="secondary" data-net-action="stop-pppoe" data-iface="${escapeHtml(iface)}">${t('network.disconnect')}</button></div>` : `<div class="iface-static-form protocol-form"><label>IPv4 Address<input name="address4" placeholder="192.168.1.100/24"></label><label>IPv4 Gateway<input name="gateway4" placeholder="192.168.1.1"></label><label>IPv6 Address<input name="address6" placeholder="2001:db8::10/64"></label><label>IPv6 Gateway<input name="gateway6" placeholder="2001:db8::1"></label><button data-net-action="apply-protocol-static" data-iface="${escapeHtml(iface)}">${t('action.apply')}</button></div>`;
    dialog.showModal(); return;
  }
  if (action === 'apply-protocol-pppoe') {
    const form = document.querySelector('#network-config-body');
    try { await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_pppoe', interface: iface, username: form.querySelector('[name="username"]').value.trim(), password: form.querySelector('[name="password"]').value, ipv6: form.querySelector('[name="ipv6"]').value === 'true'})}); document.querySelector('#network-config-dialog').close(); await loadNetwork(); }
    catch (error) { alert(error.message); } return;
  }
  if (action === 'stop-pppoe') {
    try { await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'stop_pppoe'})}); document.querySelector('#network-config-dialog').close(); await loadNetwork(); }
    catch (error) { alert(error.message); } return;
  }
  if (action === 'apply-protocol-static') {
    const form = document.querySelector('#network-config-body');
    const address4 = form.querySelector('[name="address4"]').value.trim(), gateway4 = form.querySelector('[name="gateway4"]').value.trim();
    const address6 = form.querySelector('[name="address6"]').value.trim(), gateway6 = form.querySelector('[name="gateway6"]').value.trim();
    if (!address4 && !address6) { alert(t('alert.address_required')); return; }
    try {
      if (address4) await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_static', interface: iface, address: address4, gateway: gateway4})});
      if (address6) await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_ipv6_static', interface: iface, address: address6, gateway: gateway6})});
      document.querySelector('#network-config-dialog').close(); await loadNetwork();
    } catch (error) { alert(error.message); } return;
  }
  if (action === 'dhcp') {
    btn.disabled = true;
    try {
      await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_dhcp', interface: iface})});
      await loadNetwork();
    } catch (error) { alert(error.message); }
    btn.disabled = false;
  }
  if (action === 'show-static') {
    const form = document.querySelector(`[data-static-form="${iface}"]`); form.hidden = false;
    document.querySelector('#network-config-title').textContent = `${iface} · IPv4`;
    document.querySelector('#network-config-body').replaceChildren(form); document.querySelector('#network-config-dialog').showModal();
  }
  if (action === 'ipv6-auto') {
    btn.disabled = true;
    try { await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_ipv6_auto', interface: iface})}); await loadNetwork(); }
    catch (error) { alert(error.message); }
    btn.disabled = false;
  }
  if (action === 'show-ipv6') {
    const form = document.querySelector(`[data-ipv6-form="${iface}"]`); form.hidden = false;
    document.querySelector('#network-config-title').textContent = `${iface} · IPv6`;
    document.querySelector('#network-config-body').replaceChildren(form); document.querySelector('#network-config-dialog').showModal();
  }
  if (action === 'hide-ipv6') document.querySelector('#network-config-dialog').close();
  if (action === 'apply-ipv6') {
    const form = document.querySelector(`[data-ipv6-form="${iface}"]`);
    const address = form.querySelector('.static-addr6').value.trim();
    const gateway = form.querySelector('.static-gw6').value.trim();
    if (!address) { alert(t('alert.address_required')); return; }
    try { await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_ipv6_static', interface: iface, address, gateway})}); await loadNetwork(); }
    catch (error) { alert(error.message); }
  }
  if (action === 'hide-static') {
    document.querySelector('#network-config-dialog').close();
  }
  if (action === 'apply-static') {
    const form = document.querySelector(`[data-static-form="${iface}"]`);
    const addr = form.querySelector('.static-addr').value.trim();
    const gw = form.querySelector('.static-gw').value.trim();
    if (!addr) { alert(t('alert.address_required')); return; }
    try {
      await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'apply_static', interface: iface, address: addr, gateway: gw})});
      await loadNetwork();
    } catch (error) { alert(error.message); }
  }
});

// DNS form
document.querySelector('#dns-form').addEventListener('submit', async event => {
  event.preventDefault();
  const servers = document.querySelector('#dns-servers').value.trim();
  try {
    await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'set_dns', servers})});
    alert(t('alert.dns_updated'));
  } catch (error) { alert(error.message); }
});
document.querySelector('#network-config-close').addEventListener('click', () => document.querySelector('#network-config-dialog').close());
document.querySelector('#network-config-dialog').addEventListener('click', event => { if (event.target === event.currentTarget) event.currentTarget.close(); });
document.querySelector('#network-create').addEventListener('click', () => {
  const physical = (networkState.interfaces || []).filter(item => (item.type || 'ethernet') === 'ethernet');
  const options = physical.map(item => `<option value="${escapeHtml(item.name)}">${escapeHtml(item.name)} · ${escapeHtml(item.mac || '')}</option>`).join('');
  const dialog = document.querySelector('#network-config-dialog');
  document.querySelector('#network-config-title').textContent = 'Create Network';
  document.querySelector('#network-config-body').innerHTML = `<form id="network-create-form" class="iface-static-form protocol-form">
    <label>Device type<select name="type"><option value="bridge">Bridge</option><option value="vlan">VLAN (802.1Q)</option><option value="macvlan">MACVLAN</option><option value="dummy">Dummy interface</option></select></label>
    <label>Device name<input name="device" placeholder="br-lan" pattern="[A-Za-z0-9._-]+" required></label>
    <label data-network-parent>Parent interface<select name="parent">${options}</select></label>
    <label data-network-vlan>VLAN ID<input name="vlan_id" type="number" min="1" max="4094" value="10"></label>
    <label class="span-all" data-network-ports>Bridge ports<select name="ports" multiple size="${Math.min(6, Math.max(2, physical.length))}">${options}</select><small>Use Ctrl/Cmd to select multiple ports.</small></label>
    <button type="submit">Create Device</button></form>`;
  const form = document.querySelector('#network-create-form');
  const update = () => { const type = form.elements.type.value; form.querySelector('[data-network-parent]').hidden = !['vlan', 'macvlan'].includes(type); form.querySelector('[data-network-vlan]').hidden = type !== 'vlan'; form.querySelector('[data-network-ports]').hidden = type !== 'bridge'; };
  form.elements.type.addEventListener('change', update); update();
  form.addEventListener('submit', async event => {
    event.preventDefault(); const ports = [...form.elements.ports.selectedOptions].map(option => option.value).join(',');
    try { await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'create_network', type: form.elements.type.value, device: form.elements.device.value.trim(), parent: form.elements.parent.value, vlan_id: Number(form.elements.vlan_id.value), ports})}); dialog.close(); await loadNetwork(); }
    catch (error) { alert(error.message); }
  });
  dialog.showModal();
});

document.querySelector('#nat-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.target;
  try {
    await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'set_nat', family: 4, mode: form.elements.nat4_mode.value, interface: form.elements.nat4_interface.value})});
    await api('/cgi-bin/network', {method: 'POST', body: JSON.stringify({action: 'set_nat', family: 6, mode: form.elements.nat6_mode.value, interface: form.elements.nat6_interface.value})});
    alert(t('alert.save_ok')); await loadNetwork();
  } catch (error) { alert(error.message); }
});

// ===== App & Docker event listeners =====
document.querySelector('#refresh-apps').addEventListener('click', () => loadApps().catch(error => alert(error.message)));
async function configureDefaultFlathub() {
  const button = document.querySelector('#configure-flathub');
  button.disabled = true;
  try {
    await api('/cgi-bin/remotes', {method: 'POST', body: JSON.stringify({action: 'configure-default'})});
    await loadRemotes();
  } finally {
    button.disabled = false;
  }
}

document.querySelector('#configure-flathub').addEventListener('click', () => configureDefaultFlathub().catch(error => alert(error.message)));
document.querySelector('#install-form').addEventListener('submit', async event => {
  event.preventDefault();
  const remote = document.querySelector('#install-remote').value;
  if (!remote) {
    if (!confirm(t('apps.no_source'))) return;
    try { await configureDefaultFlathub(); } catch (error) { alert(error.message); }
    return;
  }
  installApp(document.querySelector('#install-ref').value.trim(), remote).catch(error => alert(error.message));
});
document.querySelector('#open-terminal').addEventListener('click', () => loadTerminal().catch(error => alert(error.message)));
document.querySelector('#tls-self-signed-form').addEventListener('submit', event => {
  event.preventDefault();
  const button = event.target.querySelector('button');
  button.disabled = true;
  changeTls('self-signed', {
    common_name: document.querySelector('#tls-common-name').value.trim(),
    days: document.querySelector('#tls-days').value,
  }).catch(error => alert(error.message)).finally(() => { button.disabled = false; });
});
document.querySelector('#tls-deploy-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.target.querySelector('button');
  button.disabled = true;
  try {
    const certificate = await fileBase64(document.querySelector('#tls-certificate').files[0]);
    const privateKey = await fileBase64(document.querySelector('#tls-private-key').files[0]);
    await changeTls('deploy', {certificate, private_key: privateKey});
  } catch (error) { alert(error.message); }
  finally { button.disabled = false; }
});
document.querySelector('#tls-enable').addEventListener('click', () => changeTls('enable').catch(error => alert(error.message)));
document.querySelector('#tls-disable').addEventListener('click', () => {
  if (confirm(t('alert.disable_https'))) changeTls('disable').catch(error => alert(error.message));
});
document.querySelector('#firewall-rule-form').addEventListener('submit', event => { addFirewallRule(event).catch(error => alert(error.message)); });
document.querySelector('#fail2ban-form').addEventListener('submit', async event => {
  event.preventDefault(); const form = event.target;
  try {
    await api('/cgi-bin/firewall', {method: 'POST', body: JSON.stringify({action: 'fail2ban_config', enabled: form.elements.enabled.value, maxretry: form.elements.maxretry.value, findtime: form.elements.findtime.value, bantime: form.elements.bantime.value})});
    alert(t('alert.save_ok')); await loadFirewall();
  } catch (error) { alert(error.message); }
});
document.querySelector('#firewall-confirm').addEventListener('click', () => confirmFirewall().catch(error => alert(error.message)));
document.querySelector('#firewall-rollback').addEventListener('click', () => {
  if (confirm(t('alert.rollback_firewall'))) rollbackFirewall().catch(error => alert(error.message));
});
document.querySelector('#firewall-presets').addEventListener('click', event => {
  const btn = event.target.closest('[data-preset]');
  if (!btn) return;
  const preset = btn.dataset.preset;
  const action = btn.dataset.action;
  if (action === 'apply-preset') applyFirewallPreset(preset).catch(error => alert(error.message));
});
document.querySelector('#firewall-rules').addEventListener('click', event => {
  const btn = event.target.closest('[data-proto]');
  if (!btn) return;
  const proto = btn.dataset.proto;
  const port = btn.dataset.port;
  const actionType = btn.dataset.actionType;
  const action = btn.dataset.action;
  if (action === 'remove-rule') removeFirewallRule(proto, port, actionType).catch(error => alert(error.message));
});
document.querySelector('#docker-pull-form').addEventListener('submit', event => {
  event.preventDefault();
  const button = event.target.querySelector('button');
  button.disabled = true;
  startDockerPull(document.querySelector('#docker-pull-image').value.trim()).catch(error => { button.disabled = false; alert(error.message); });
});
document.querySelector('#docker-create-form').addEventListener('submit', event => {
  event.preventDefault();
  const form = event.target;
  const values = Object.fromEntries(new FormData(form));
  for (const name of ['privileged', 'readonly', 'auto_remove', 'init_process', 'publish_all', 'pull_before', 'start_after']) values[name] = form.elements[name].checked;
  const consoleMode = values.console_mode;
  delete values.console_mode;
  values.tty = consoleMode === 'tty' || consoleMode === 'interactive';
  values.stdin_open = consoleMode === 'interactive';
  const editId = values.edit_id;
  delete values.edit_id;
  const button = form.querySelector('#docker-create-submit');
  button.disabled = true;
  const action = editId ? 'recreate' : 'create';
  dockerAction(action, editId || '', values).then(() => { exitDockerEditMode(); document.querySelector('#docker-create-dialog').close(); return loadDocker(); }).catch(error => alert(error.message)).finally(() => { button.disabled = false; });
});
document.querySelector('#docker-edit-cancel').addEventListener('click', () => exitDockerEditMode());
document.querySelector('#docker-images').addEventListener('click', event => {
  const imgBtn = event.target.closest('[data-use-image]');
  const removeBtn = event.target.closest('[data-remove-image]');
  if (removeBtn) {
    if (confirm('Remove this image?')) dockerAction('image_remove', removeBtn.dataset.removeImage).then(loadDocker).catch(error => alert(error.message));
    return;
  }
  if (!imgBtn) return;
  exitDockerEditMode();
  document.querySelector('#docker-create-form').elements.image.value = imgBtn.dataset.useImage;
  document.querySelector('#docker-create-dialog').showModal();
});
document.querySelector('#docker-containers').addEventListener('click', event => {
  const dcBtn = event.target.closest('[data-docker-action]');
  if (!dcBtn) return;
  const action = dcBtn.dataset.dockerAction;
  const id = dcBtn.dataset.id;
  const name = dcBtn.dataset.name;
  if (!action) return;
  if (action === 'remove' && !confirm(t('alert.remove_container'))) return;
  if (action === 'terminal') {
    const popup = window.open('about:blank', `strata-docker-${id.slice(0, 12)}`, 'popup,width=1100,height=720');
    if (!popup) { alert(t('alert.popup_blocked')); return; }
    popup.document.body.textContent = t('status.opening_terminal');
    openDockerTerminal(id, popup).catch(error => { popup.close(); alert(error.message); });
    return;
  }
  if (action === 'logs') { showDockerLogs(id, name).catch(error => alert(error.message)); return; }
  if (action === 'params') { showDockerParams(id, name).catch(error => alert(error.message)); return; }
  dcBtn.disabled = true;
  dockerAction(action, dcBtn.dataset.dockerAction === 'remove' ? dcBtn.dataset.id : (dcBtn.dataset.id || ''), {}).then(loadDocker).catch(error => alert(error.message));
});
document.querySelector('#docker-summary').addEventListener('click', event => {
  const button = event.target.closest('[data-daemon-action]');
  if (!button) return;
  button.disabled = true;
  dockerAction(button.dataset.daemonAction).then(loadDocker).catch(error => alert(error.message)).finally(() => { button.disabled = false; });
});
for (const [formId, action] of [['#docker-network-form', 'network_create'], ['#docker-volume-form', 'volume_create']]) {
  document.querySelector(formId).addEventListener('submit', event => {
    event.preventDefault();
    const name = event.target.elements.name.value.trim();
    dockerAction(action, '', {name}).then(() => { event.target.reset(); return loadDocker(); }).catch(error => alert(error.message));
  });
}
for (const listId of ['#docker-networks', '#docker-volume-list']) {
  document.querySelector(listId).addEventListener('click', event => {
    const button = event.target.closest('[data-docker-object]');
    if (!button || !confirm('Remove this unused Docker object?')) return;
    dockerAction(button.dataset.dockerObject, button.dataset.id).then(loadDocker).catch(error => alert(error.message));
  });
}
document.querySelector('#docker-logs-dialog').addEventListener('close', event => {
  if (event.target.returnValue !== 'refresh') return;
  showDockerLogs(event.target.dataset.id, event.target.dataset.name).catch(error => alert(error.message));
});
document.querySelector('#docker-quick-update-form').addEventListener('submit', event => {
  event.preventDefault();
  const dialog = document.querySelector('#docker-params-dialog');
  const id = dialog.dataset.id;
  const values = Object.fromEntries(new FormData(event.target));
  if (!values.restart && !values.memory && !values.cpus) { alert(t('alert.enter_value')); return; }
  const button = event.target.querySelector('button');
  button.disabled = true;
  dockerAction('update', id, values).then(() => showDockerParams(id, dialog.dataset.name)).catch(error => alert(error.message)).finally(() => { button.disabled = false; });
});
document.querySelector('#docker-params-edit').addEventListener('click', () => {
  const dialog = document.querySelector('#docker-params-dialog');
  if (!dialog.dockerParams) return;
  enterDockerEditMode(dialog.dataset.id, dialog.dockerParams);
  dialog.close();
});
document.querySelector('#docker-params-close').addEventListener('click', () => document.querySelector('#docker-params-dialog').close());
document.querySelector('#docker-params-close-x').addEventListener('click', () => document.querySelector('#docker-params-dialog').close());
document.querySelector('#docker-source-form').addEventListener('submit', event => {
  event.preventDefault();
  const url = document.querySelector('#docker-source-url').value.trim();
  const oldUrl = document.querySelector('#docker-source-old').value;
  if (!confirm(t('alert.apply_mirror'))) return;
  api('/cgi-bin/docker-sources', {method: 'POST', body: JSON.stringify({action: 'save', url, old_url: oldUrl})}).then(() => {
    event.target.reset(); document.querySelector('#docker-source-old').value = ''; return loadDocker();
  }).catch(error => alert(error.message));
});
document.querySelector('#docker-source-preset').addEventListener('change', event => {
  if (event.target.value) document.querySelector('#docker-source-url').value = event.target.value;
});
document.querySelector('#docker-sources').addEventListener('click', event => {
  const dsBtn = event.target.closest('[data-docker-source-action]');
  if (!dsBtn) return;
  const action = dsBtn.dataset.dockerSourceAction;
  const url = dsBtn.dataset.url;
  if (!action) return;
  if (action === 'edit') {
    document.querySelector('#docker-source-old').value = url;
    document.querySelector('#docker-source-url').value = url;
    document.querySelector('#docker-source-url').focus();
    return;
  }
  if (!confirm(t('alert.delete_mirror'))) return;
  api('/cgi-bin/docker-sources', {method: 'POST', body: JSON.stringify({action: 'delete', url})}).then(loadDocker).catch(error => alert(error.message));
});
document.querySelector('#apps').addEventListener('click', event => {
  const btn = event.target.closest('[data-app]');
  if (!btn) return;
  const app = btn.dataset.app;
  const action = btn.dataset.action;
  if (!app || !action) return;
  if (action === 'start') {
    startApp(app).catch(error => alert(error.message));
  }
  if (action === 'stop' && confirm(t('alert.stop_app') + app + '?')) stopApp(app).catch(error => alert(error.message));
  if (action === 'view') { try { viewApp(app); } catch (error) { alert(error.message); } }
});
document.querySelector('#remote-form').addEventListener('submit', event => {
  event.preventDefault();
  const name = document.querySelector('#remote-name').value.trim();
  const url = document.querySelector('#remote-url').value.trim();
  api('/cgi-bin/remotes', {method: 'POST', body: JSON.stringify({action: 'save', name, url})}).then(() => {
    event.target.reset();
    return loadRemotes();
  }).catch(error => alert(error.message));
});
document.querySelector('#flatpak-source-preset').addEventListener('change', event => {
  const option = event.target.selectedOptions[0]; if (!option || !option.value) return;
  document.querySelector('#remote-name').value = option.dataset.name || '';
  document.querySelector('#remote-url').value = option.value;
});
document.querySelector('#remotes').addEventListener('click', event => {
  const rmBtn = event.target.closest('[data-remote-action]');
  if (!rmBtn) return;
  const action = rmBtn.dataset.remoteAction;
  const name = rmBtn.dataset.name;
  const url = rmBtn.dataset.url;
  if (!action) return;
  if (action === 'edit') {
    document.querySelector('#remote-name').value = name;
    document.querySelector('#remote-url').value = url;
    document.querySelector('#remote-url').focus();
    return;
  }
  if (action === 'delete' && !confirm(t('alert.delete_flatpak') + name + '?')) return;
  api('/cgi-bin/remotes', {method: 'POST', body: JSON.stringify({action, name})}).then(loadRemotes).catch(error => alert(error.message));
});
document.querySelector('#reboot').addEventListener('click', () => confirmPower('reboot'));
document.querySelector('#poweroff').addEventListener('click', () => confirmPower('poweroff'));
document.querySelector('#confirm').addEventListener('close', async event => {
  if (event.target.returnValue !== 'confirm') return;
  const action = event.target.closest('#confirm')?.dataset?.action;
  try { await api('/cgi-bin/power', {method: 'POST', body: JSON.stringify({action})}); document.querySelector('#connection').textContent = action === 'reboot' ? t('status.restarting') : t('status.shutting_down'); } catch (error) { alert(error.message); }
});

// ===== Init =====
setTheme(theme);
setLocale(locale);
if (token) {
  loadFeatures().then(() => navigate('system')).catch(() => { if (!login.open) login.showModal(); });
  pollInstall().catch(() => {});
} else login.showModal();
