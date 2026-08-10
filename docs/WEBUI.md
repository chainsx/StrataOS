# WebUI and Application Center

## Architecture

The WebUI uses a pure Wayland headless display chain:

```text
Flatpak GUI -> Cage/wlroots(headless + Mesa GLES2/GBM) -> wayvnc(127.0.0.1:5900-5999)
            -> strata-wsproxy(loopback when TLS is enabled)
            -> strata-tlsproxy(:6080) -> noVNC -> browser window

Browser -> system account password check -> 12-hour random session under /run
Browser -> strata-tlsproxy(:9090) -> httpd(127.0.0.1:9091)
Browser -> strata-tlsproxy(:7681) -> strata-authproxy(HttpOnly session cookie)
       -> ttyd(127.0.0.1:7682, trusted header) -> root zsh
```

When TLS is not enabled, `strata-tlsproxy` is not started and the original HTTP
services still listen directly on the same public ports.

The `graphics` component provides Wayland, wlroots, Cage and wayvnc;
`web-console` provides ttyd, noVNC and their libraries; the `webui` core
provides static pages, common authentication/TLS proxies, system information,
power control and certificate management. Capability-specific CGI and helpers
are rootfs-only adapters: `webui-network`, `webui-openssh`, `webui-storage`,
`webui-firewall`, `webui-docker`, and `webui-flatpak`. Each adapter depends on both `webui` and
the backend component it controls. The Application Center adapter is selected
only when Graphics and Flatpak are present. The default defconfig enables the
full combination.

The separate `fonts-cjk` component installs the Noto Sans CJK SC font for use by CJK
interfaces running inside the Flatpak sandbox. libxkbcommon's keyboard data
root is fixed to the target system's `/usr/share/X11/xkb` and never
references the build host's sysroot. The Application Center's `webui-flatpak`
volume starts at an initial capacity of 4 GiB; the storage layer adopts volumes
from the former `webui` owner and grows older, smaller volumes (never shrinks
them) on the next boot.

The sidebar separates **System** overview, **Storage** and **Settings** so that
device identity, power controls and persistent-volume configuration do not
duplicate runtime information. The System page shows the OS, kernel, CPU,
memory, root filesystem, load, uptime and Machine ID. The Storage page follows
the operational shape of LuCI DiskMan: it inventories block devices and
partitions, shows filesystem and mount state, formats only unmounted detected
partitions, and persists explicit mounts below `/mnt`. It deliberately does not
expose destructive partition-table editing or component backing files as normal
disks. Settings owns hostname, logging, swap and confirmed reboot/power-off
actions. The Security page
contains the OpenSSH boot/runtime switch (enabled by default) and SSH daemon
settings. The Docker page can pull and list images
in the background; the pull panel shows completed/total layer counts and a
combined percentage covering the download, checksum and extraction phases.
The page can create containers using commonly used runtime, health-check,
resource, network and security parameters, start/stop/pause/restart/remove containers, view the last 500
timestamped lines of container logs, and open an independent ttyd shell for
a running container. Advanced create parameters can supplement the Docker
CLI's long options. Named volumes and user-defined networks can be created
and removed, and unused images can be deleted. Docker Registry API mirror sources can be added,
replaced and removed; changing a source rewrites the managed daemon
configuration and restarts Docker. Daemon settings (boot enablement, data
root, log driver and rotation, log level, live restore and userland proxy)
are persisted under `/etc/strataos/docker.conf` and validated before use.

The WebUI's default interface language is English.

The Application Center lets you pick an enabled software source and enter
an application ID to perform a system-level installation, and lets you add
or modify Flatpak remote URLs, and enable, disable or remove remotes.
The built-in source presets are official Flathub and the SJTUG mirror. The
obsolete BFSU preset was removed because its descriptor endpoint returned
HTTP 404; administrators may still enter another valid `.flatpakrepo` URL.
Installation tasks run in the background; the page reads the current
transfer percentage and the current operation index (e.g. `1/4`) from
Flatpak's terminal progress events and shows them next to the progress bar.
`--system` is used here because the install request is executed by the root
WebUI service, while GUI applications run under the isolated `webapp`
account; a user-level install would only be visible to the account that
performed it, which cannot satisfy the requirement that both accounts share
the deployment.

Every installed application has independent start, stop and "view UI"
actions. Multiple applications can run at the same time, each with its own
Cage, wayvnc and process group. The viewer opens in a modal application
window inside the control center; closing it only disconnects the VNC client
without stopping the application, and viewing again reconnects to the session.
The shared Flatpak display/proxy helpers start before the first application is
launched. They remain available while at least one application is alive and
stop after the last explicit stop, natural exit, or failed launch, reducing
idle memory use.

For interactive sessions, a GPU-backed application uses a 60 FPS WayVNC rate
limit while retaining the standard screencopy capture path. Applications and
Cage still use GPU rendering, but avoiding DMABUF capture prevents black frames
on headless or virtio renderers that cannot export compatible buffers. A
software-rendered fallback stays at 30 FPS to preserve CPU time for the
application itself. noVNC uses continuous updates
and sends remote-size requests only when the target pixel dimensions actually
change; repeated layout requests previously added avoidable resize work while
the browser window was being dragged.

The application viewer supports adaptive, 16:9, 16:10, 4:3, 3:2 and 21:9
aspect ratios, adaptive/720p/900p/1080p output resolution, and balanced,
high or best image-quality profiles. The old implementation relied solely on an animated CSS
aspect-ratio box; the DesktopSize requests that noVNC issues during the
animation were subject to the "one pending request at a time" throttling,
so the final CSS size could fail to reach the remote end, leaving the
application still drawn at the old output size and cropped. The frontend
now computes an explicit even-pixel width/height from the viewer area up
front, sends that exact size through an extended noVNC API, and retries the
latest size after 300 ms and 900 ms. When wayvnc receives the RFB
DesktopSize request it changes the headless Wayland output resolution;
Cage explicitly re-maximizes the already-mapped application window on the
headless output-mode commit, so the application surface adapts to the new
width/height in sync instead of only changing the VNC framebuffer. The
mouse uses noVNC's absolute coordinate mode, mapping the browser position
directly to the remote position. When the aspect ratio changes, the
frontend retries the DesktopSize request once the CSS layout has settled,
and noVNC also retains the last explicit target size, avoiding requests
landing on a hidden page or a window whose previous resize has not yet been
acknowledged.

The system terminal and container terminals are authenticated by the auth
proxy, which validates the HttpOnly session cookie. ttyd itself does not
enable cross-port Origin rejection: the WebUI listens on 9090 while the
terminals use 7681 or 7690-7789, which are inherently different origins; an
earlier misconfiguration that enabled ttyd's `-O` flag incorrectly rejected
legitimate WebSocket connections. The authentication boundary is still
provided by `strata-authproxy`, the only component exposed externally; the
ttyd backend only listens on loopback. The dynamic terminal endpoint only
returns the port to the browser once the public listening port has actually
entered the LISTEN state, avoiding a startup race that would otherwise
surface as "connection refused".

Each Flatpak application can be started with GPU acceleration (the default) or
software rendering. The GPU path uses Mesa EGL/GLES2 and GBM through an
accessible DRM render node. The software path sets the host Mesa's non-LLVM
`softpipe` Gallium driver for wlroots/Cage and requests software rendering in
the Flatpak process, whose runtime selects its available software driver. It
therefore remains usable when a device driver is unavailable or incompatible,
at the cost of higher CPU usage. wlroots retains its headless output backend in both modes so
several independent Cage sessions can run without competing for DRM master or
physical displays. The generic kernel enables VirtIO GPU; a physical device
target must enable its own kernel DRM/GPU driver before the corresponding
render node is available.

The WebUI core depends on `system-core`, `network`, and `web-console`. The
Docker navigation entry is shown only when `webui-docker` is active; the
Application Center navigation entry is shown only when `webui-flatpak` is
active. Storage is shown only when `webui-storage` is active. Those adapters
prove that their backend components are also active.
Application icons are resolved from the exported desktop file's `Icon` entry,
with the application ID as a fallback, then read from Flatpak's system export
icon directory. The browser fetches the image with its WebUI Bearer token and
displays the authenticated response through a temporary object URL.

Applications run under the locked-down `webapp` system account, with Cage
using a headless output and either Mesa GPU rendering through the `render`
group or Mesa software rendering. Each wayvnc
instance is allocated a port from a pool that only listens on loopback,
all routed by application ID through the session-authenticated proxy on
port 6080; the browser cannot bypass the proxy to connect to VNC directly.
The stop action only terminates the target application's session process
group, without affecting other applications. The Flatpak viewer WebSocket and
optional TLS proxies are started before the first application and stopped after
the last application exits, including natural exits and failed starts, instead
of consuming memory for the whole WebUI uptime.

## Usage

Visit `http://<device-address>:9090/` and log in with the username and
password of root or a system administrator account belonging to the
`wheel` group. The administrator created during first-boot terminal
initialization is a member of `wheel` by default, so it can be used with
the WebUI directly. Passwords are verified against `/etc/shadow` using the
system `crypt()` implementation and are never stored by the WebUI; on
successful login a random 12-hour session is issued and kept only under
`/run`. Rebooting or stopping the WebUI clears all sessions.

### HTTPS and certificates

After logging in, open the **Security** page in the sidebar, where you can:

1. Enter the device's hostname or IPv4 address and a validity period to
   generate a self-signed RSA 3072, SHA-256 certificate with a matching
   Subject Alternative Name;
2. Upload an existing PEM certificate or full chain, along with its
   matching unencrypted PEM private key;
3. Temporarily disable or re-enable an already deployed certificate.

Before deployment the certificate and private key are parsed, expired
certificates are rejected, and the public key digests are compared to
confirm they match. The certificate is stored at
`/etc/strataos/webui/tls.crt` (`0644`), the private key at
`/etc/strataos/webui/tls.key` (`0600`, root-readable only), and the enabled
state at `/etc/strataos/webui/tls.conf`. `/etc` lives on the system's
persistent overlay, so the certificate survives reboots and component
updates. Private keys should only be uploaded over a trusted management
network; if an encrypted HTTPS entry point already exists, prefer rotating
the certificate over HTTPS.

Applying a certificate restarts the WebUI, clears login sessions, and
disconnects the current terminal and Flatpak viewer connections. Running
Docker containers are not stopped by this. Once enabled, use
`https://<device-address>:9090/`; VNC uses `wss://<device-address>:6080/`,
and the system terminal and dynamic Docker terminals also switch to
HTTPS/WSS on their existing ports. Self-signed certificates are not
automatically trusted by browsers, so on first access you must verify the
SHA-256 fingerprint shown on the page and trust it manually; production
deployments should use a certificate issued by an internal or trusted CA
whose SAN matches the access address.

The web terminal is provided by ttyd, which only listens on
`127.0.0.1:7682`; the browser first obtains an HttpOnly cookie through an
authenticated API, then connects to the public auth proxy on `7681`. This
terminal is a root administration terminal, so WebUI login only accepts
root and `wheel` administrators. Installed Flatpak applications are listed
in the Application Center; clicking "Start" establishes a Wayland session,
and clicking "View UI" connects to noVNC in a separate window. "Stop" only
ends that application's session process group.

The QEMU launch script forwards host ports `9090`, `6080`, `7681`,
`7690-7789` and `2222` to the guest's WebUI, Flatpak WebSocket, system
terminal auth proxy, dynamic Docker terminals and SSH respectively, so
`http://127.0.0.1:9090/` is reachable from the host; once a certificate is
enabled, switch to `https://127.0.0.1:9090/`.

Applications must already be installed and support a Wayland socket. The
Flatpak page configures the system-wide Flathub remote on demand. When an
installation is requested with no configured source, the WebUI prompts the
administrator to configure official Flathub first. The image does not ship any
third-party applications or runtimes preinstalled.

## Interface

- `GET /cgi-bin/system`: system, CPU, memory, disk and load information.
- `GET/POST /cgi-bin/network`: lists IPv4/IPv6 interfaces, DNS, routes,
  PPPoE and NAT state. POST supports DHCP/static IPv4, automatic/static
  IPv6, PPPoE (including IP6CP), DNS, and independently configured standard
  IPv4 or IPv6 masquerade.
- `GET/POST /cgi-bin/system-config`: includes persistent swap-file creation
  on the system state volume. The `strataos-swap` OpenRC service restores it
  on later boots. `?view=settings` and `?view=storage` return only the data
  needed by their corresponding WebUI pages, avoiding expensive storage and
  hardware probes during an overview refresh.
- `GET /cgi-bin/storage`: returns `lsblk` JSON for detected block devices.
  `POST` supports `mount`, `unmount` and `format` for detected writable
  partitions only. Persistent mounts are constrained to `/mnt/<name>` and are
  restored by `strataos-storage-mounts`; mounted system and component volumes
  are never accepted as formatting targets.
- `POST /cgi-bin/login?username=...`: the request body is the password;
  verifies the system administrator account and returns a time-limited
  session token. A successful login using the factory root credential sets
  `setup_required`; the WebUI then requires password replacement and creation
  of a named administrator.
- `POST /cgi-bin/setup`: available only to an authenticated root session while
  the factory password hash is still active. It changes the root password,
  creates a wheel administrator, marks initial setup complete and invalidates
  every existing WebUI session.
- `POST /cgi-bin/logout`: logs out the current session and clears the
  terminal cookie.
- `GET /cgi-bin/tls`: returns the HTTPS enabled state and the certificate's
  subject, issuer, validity period and SHA-256 fingerprint; `POST` supports
  `self-signed`, `deploy`, `enable` and `disable`. `deploy` uses
  Base64-encoded PEM certificate chain and private key fields; the private
  key is never returned by the query interface.
- `POST /cgi-bin/power`, body `{"action":"reboot"}` or
  `{"action":"poweroff"}`: reboots or shuts down the system.
- `GET /cgi-bin/docker`: Docker daemon, image, container and current
  registry mirror status; `POST` supports `create`, `start`, `stop`,
  `restart` and `remove`.
- `GET/POST /cgi-bin/docker-pull`: starts a single background image pull
  task or reads its status, returning a `progress` percentage and an
  `operation` layer fraction (e.g. `3/8`).
- `POST /cgi-bin/docker-logs`: reads the last 500 lines (up to 256 KiB) of
  timestamped logs for the given container.
- `GET/POST /cgi-bin/docker-sources`: lists, adds, replaces or removes
  Registry API mirror sources.
- `POST /cgi-bin/docker-terminal`: allocates a session-cookie-protected
  ttyd shell endpoint for a running container.
- `GET /cgi-bin/firewall`: returns the current firewall status — active
  preset, whether a change is pending confirmation, seconds remaining before
  automatic rollback (`remaining`), whether nftables has a loaded ruleset,
  the current `confirm_timeout`, an inline `presets` array, and the custom
  `rules` list; `POST` supports `status` (same as GET), `apply_preset`
  (body: `{"action":"apply_preset","preset":"management-only|allow-all"}`),
  `add_rule` (body: `{"action":"add_rule","action_type":"allow|deny",
  "proto":"tcp|udp","port":"N or N-M"}`), `remove_rule` (body: `{"action":
  "remove_rule","action_type":"allow|deny","proto":"tcp|udp","port":"N or
  N-M"}`), `confirm` (persists the pending change to disk) and `rollback`
  (immediately restores the previous ruleset and cancels the timer).  Rules
  that would block management ports (SSH 22, WebUI 9090, noVNC 6080,
  ttyd 7681, VNC range 7690–7789) are rejected.  Every applied change
  starts an auto-rollback timer (`confirm_timeout` seconds, default 90)
  that restores the previous ruleset unless `confirm` is called first.
- `POST /cgi-bin/terminal-auth`: sets the short-lived-route terminal
  authentication cookie.
- `GET /cgi-bin/apps`: installed Flatpak applications. It obtains the complete
  session snapshot once per list request; application icons load lazily with a
  bounded browser request queue so icon I/O cannot delay Start, Stop or View.
- `GET /cgi-bin/remotes`: lists system-wide Flatpak remotes; `POST` can
  add, modify, enable, disable or remove a remote.
- `POST /cgi-bin/install`, body `{"ref":"org.example.App","remote":"flathub"}`:
  starts a system-wide background install from the given remote; `GET`
  returns the status and current transfer percentage.
- `POST /cgi-bin/session`, body `{"app_id":"org.example.App","render_mode":
  "gpu|software"}`: starts the application (`gpu` is the default). Rendering
  mode can only be changed after stopping the existing session. The viewer
  opens in a resizable browser popup; resizing the
  popup requests a matching remote desktop size, while choosing a fixed
  aspect ratio also resizes the browser popup to that ratio.
- `POST /cgi-bin/session`, body
  `{"action":"stop","app_id":"org.example.App"}`: stops the given
  application.
- `GET /cgi-bin/session`: lists running application sessions; use the
  `app_id` query parameter to read a specific session.
- `ws://<device-address>:6080/?token=...&session=...` or
  `wss://<device-address>:6080/?token=...&session=...`: the login-session-
  protected VNC WebSocket routed by application, following the WebUI's TLS
  mode.
- `http://<device-address>:7681/` or `https://<device-address>:7681/`: the
  cookie-protected ttyd HTTP/WebSocket entry point; the ttyd backend
  `7682` does not listen externally.
- `http://<device-address>:7690-7789/` or
  `https://<device-address>:7690-7789/`: on-demand, similarly
  cookie-protected container ttyd shells; the backend ports only listen on
  loopback.

Except for the login endpoint, all HTTP API calls must carry
`Authorization: Bearer <session-token>`. Application IDs may only contain
ASCII letters, digits, dots, underscores and hyphens, and are confirmed as
installed via `flatpak info` before being started; the interface does not
accept arbitrary commands.

## Current security boundary

TLS remains disabled by default so that first-boot login and certificate
deployment can be completed over HTTP; before a certificate is enabled, the
username, password and session token are still transmitted in cleartext
over HTTP/WebSocket, so initial configuration must only be performed over a
trusted management network or QEMU host port forwarding. Once enabled, the
built-in TLS proxy requires TLS 1.2 or newer and protects the 9090, 6080,
7681 and dynamic container terminal endpoints. When deploying an existing
certificate, the WebUI only accepts an unencrypted private key so that boot
can proceed unattended, so the device's persistent storage and root access
must be properly protected.

There is currently no audio forwarding, clipboard integration, multi-user
isolation, PAM, CSRF tokens or strict Origin validation.
Production hardening should add login rate limiting/lockout, CSRF and
Origin protection, per-user Flatpak data directories and resource limits,
before considering PipeWire audio and multi-session support. An external
HTTPS reverse proxy can also be used; in that case it must proxy 9090,
6080, 7681 and any dynamic terminal ports in use.

## HTTP server choice

The WebUI currently uses BusyBox `httpd` for static assets and CGI, with
StrataOS's small authentication, WebSocket and TLS proxies handling the
specialized endpoints. This is intentional: the workload does not need
nginx routing, caching, FastCGI or virtual-host features, while BusyBox is
already part of the base system and has a much smaller operational surface.
An nginx migration is therefore not justified at present. Reconsider it if
the UI moves to a long-running application server, needs HTTP/2 termination,
or requires complex reverse-proxy policy.
