# Other hardware

The setup runs on any computer that can run Docker. These pages cover the places people ask about most. The first two are the best tested. The rest are written from how the pieces work, and have not been tried on that hardware yet.

## Known good setups

| Setup | Status | Notes |
|---|---|---|
| Proxmox LXC, Ubuntu 26.04, Docker 29, 5 cores, 11 GB memory | In daily use | The same apps run on the maintainer's own server this way |
| Mac with Docker Desktop (Apple chip) | The setup page, demo and start window tested | A full install has not been run on a Mac |
| Windows with Docker Desktop | Not tested yet | The start file and drive list are written for it |
| Linux with a screen | Not tested yet | The start file and drive list are written for it |
| Raspberry Pi 4 or 5 | Not tested yet | See below |
| Synology NAS | Not tested yet | See below |
| Unraid | Not tested yet | See below |

If you try one, please [tell us how it went](https://github.com/Hikki-dev/media-server-setup/issues/new/choose), good or bad. Every report makes this table better.

## Proxmox LXC

An LXC is a good home for this: it is light, and it can use the drives of the Proxmox host.

1. Make a Debian 12 or Ubuntu 24.04 (or newer) container. Give it at least 4 cores, 8 GB of memory and 20 GB of disk for the apps. Your media needs its own space.
2. Under **Options**, **Features**, tick **Nesting** and **keyctl**. Docker needs both inside an LXC.
3. Give it a fixed address, so the links never change.
4. Inside the container, install Docker from [docs.docker.com/engine/install](https://docs.docker.com/engine/install/), and `curl`.
5. Run the one-line installer from [Installing](Installing.md). The container has no screen, so the start window prints an address. Open it from another computer.

**Your media drives.** Mount the folders from the Proxmox host into the container, for example `pct set 102 -mp0 /mnt/media,mp=/mnt/media`. In an unprivileged container, user numbers are shifted by 100000 on the host, so files owned by user 1000 on the host look like they belong to nobody inside. Either map the user (see the Proxmox page on unprivileged containers) or set the owner on the host to match. If the apps say a folder is not writable, this is the cause.

**Tailscale inside the container** needs the network device. On the host, add these two lines to `/etc/pve/lxc/<id>.conf`, then restart the container:

```text
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
```

**Good habits**
1. Take regular Proxmox backups of the container, and keep the `ArrStack` folder in them. It holds every app's settings.
2. Watch the free space on the drive that holds the container. A full drive stops the apps.
3. Do not open port 7979 on your router. The setup page can install apps on the computer, so keep it on your home network or behind Tailscale.

## Raspberry Pi

1. Use a Pi 4 or Pi 5 with a **64-bit** operating system (Raspberry Pi OS 64-bit or Ubuntu). 4 GB of memory is the least; 8 GB is comfortable.
2. Keep the apps and their settings on an **SSD or a good USB drive**, not on the SD card. The apps write their databases all the time, and SD cards wear out.
3. Install Docker with `curl -fsSL https://get.docker.com | sh`, then add yourself to the docker group with `sudo usermod -aG docker $USER` and sign in again.
4. Run the one-line installer from [Installing](Installing.md).

What to expect:
1. Every app the setup installs has a 64-bit ARM version. The original Kapowarr is used automatically on ARM, because the maintainer's copy is built for Intel and AMD only.
2. A Pi cannot convert video well. Choose clients that play your files as they are (most TVs, phones and streaming sticks do), and Jellyfin will not need to convert anything.
3. The helper for protected websites runs a hidden browser, which is heavy for 4 GB. Keep it to FlareSolverr, and switch off apps you do not need on the Apps step.

## Synology NAS

1. Use DSM 7.2 or newer with **Container Manager** installed, and switch on SSH under **Control Panel**, **Terminal**.
2. Sign in over SSH and become root with `sudo -i`, because the default user cannot talk to Docker.
3. Put the settings and media on a volume, and make sure the files belong to the user you want:

```bash
curl -fsSL https://raw.githubusercontent.com/Hikki-dev/media-server-setup/main/install.sh \
  | ARR_STACK_DIR=/volume1/docker/arrstack ARR_MEDIA_DIR=/volume1/media ARR_UID=1026 ARR_GID=100 bash
```

The settings go in front of `bash`, not in front of `curl`. Use `id your-user` to find your own numbers instead of 1026 and 100.

4. **Leave File sharing off** on the Apps step. DSM already shares your folders and uses the same file sharing port.
5. Open the address the start window prints from another computer.

## Unraid

1. Open the Unraid **Terminal**. Docker is built in. If `docker compose version` says it is missing, install the **Compose Manager** plugin.
2. Put the settings in your `appdata` share and the media in a media share. Unraid's usual owner is user 99, group 100:

```bash
curl -fsSL https://raw.githubusercontent.com/Hikki-dev/media-server-setup/main/install.sh \
  | ARR_STACK_DIR=/mnt/user/appdata/arrstack ARR_MEDIA_DIR=/mnt/user/media ARR_UID=99 ARR_GID=100 bash
```

3. If you already run some of these apps from Community Apps, the setup finds them on the **Your apps** step, and you choose to keep yours or install a new one beside it.
4. **Leave File sharing off.** Unraid shares folders by itself.

## Any other Linux server

Install Docker, then use the one-line installer. If the files end up owned by the wrong user, set `ARR_UID` and `ARR_GID` in front of the command, as in the Synology example. All the settings you can put in front of the start file are listed at the top of `tools/start.sh`.
