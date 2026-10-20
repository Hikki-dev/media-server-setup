# Best settings

These come from a Proxmox host and an LXC that run this stack every day: an Intel laptop chip (8 threads, 24 GB memory) on the host, and a container with 5 cores, 12 GB of memory and 10 GB of swap. Everything here is optional. Use what fits your hardware.

## What the setup already does for you

1. Every app restarts by itself if it stops answering, and starts again after a reboot.
2. Each app's log is limited to three files of 50 MB, so a noisy app can never fill your drive.
3. Jellyfin uses your graphics chip for video when it finds one, after testing that it works.
4. qBittorrent stops uploading when a download is done, and finished downloads are removed.

## Proxmox container settings

| Setting | A good value | Why |
|---|---|---|
| Cores | 4 or more | Jellyfin and the search apps use them in bursts |
| Memory | 8 to 12 GB | Enough for every app and a busy Jellyfin |
| Swap | 4 to 10 GB | A short spike moves to swap instead of killing an app |
| Features | **Nesting** and **keyctl** | Docker needs them inside a container |
| Start at boot | On | The apps come back after a power cut |
| Disk for the apps | 20 GB or more, on LVM-thin or ZFS if you can | The apps and their settings live here, not your media |

**Graphics for Jellyfin.** Pass the render device to the container with one line in `/etc/pve/lxc/<id>.conf`. Find the group number of `render` on the host with `getent group render`:

```text
dev0: /dev/dri/renderD128,gid=104
```

The setup then gives Jellyfin the device and tunes it by itself.

**Be careful with "privileged" guides.** Some guides tell you to make the container privileged, switch off AppArmor and allow every device. That works, but it gives the container almost the same power as the host. Start with an unprivileged container with nesting, and only loosen what one app really needs.

## Drives on the Proxmox host

1. Mount media drives with `noatime,nodiratime`. The apps read a lot, and these two options stop every read from causing a write. Add `nofail` so the host still boots when a drive is missing:

```text
UUID=your-drive-id  /mnt/Media  ext4  defaults,noatime,nodiratime,nofail  0  2
```

2. Give the container each drive with `pct set <id> -mp0 /mnt/Media,mp=/mnt/Media`.
3. Keep the drive that holds downloads and library on ext4 or XFS. exFAT cannot link files, so every download is copied. [File sharing](File%20sharing.md) explains the formats, and the mount options for NTFS and exFAT.

## Kernel settings on the host

Containers share the host's kernel, so set these on the Proxmox host in `/etc/sysctl.d/99-media-server.conf`, then run `sysctl --system`:

```text
# fewer swap-outs, and flush written data sooner (kinder to slow drives)
vm.swappiness = 10
vm.vfs_cache_pressure = 50
vm.dirty_background_ratio = 5
vm.dirty_ratio = 10

# the apps watch many folders for changes
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 8192

# faster downloads and streams over the network
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
```

If Sonarr or Radarr say they cannot watch a folder, the inotify lines are the fix.

## Docker

1. For apps you add yourself, keep their logs small too. Put this in `/etc/docker/daemon.json` and restart Docker:

```json
{ "log-driver": "json-file", "log-opts": { "max-size": "50m", "max-file": "3" } }
```

2. **Memory caps are optional.** A cap stops one app from taking everything. Look at `docker stats` for a week first, then cap with a margin, for example 4 GB for qBittorrent and 512 MB for each of Sonarr, Radarr and Prowlarr. A cap that is too low makes an app restart over and over.
3. Remove unused images now and then with `docker image prune -af`, for example weekly from cron. Never run `docker system prune` on a shared server: it also removes stopped containers and networks that belong to other things.

## Keep it private

1. **Sign in to SSH with keys only.** Make sure your key works first, then add this in `/etc/ssh/sshd_config.d/00-hardening.conf`. The `00-` matters, because sshd uses the first value it reads:

```text
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
MaxAuthTries 3
```

2. **Reach the server through Tailscale** instead of opening ports on your router. See [Private HTTPS](Private%20HTTPS.md).
3. **Allow only your home network and Tailscale** to reach the apps. Docker publishes its ports around the usual firewall rules, so a simple `ufw` does not cover them. Use the Proxmox firewall on the container, or your router.

## Backups and health

1. Run a weekly Proxmox backup to a different drive, and check now and then that the last run really finished. A failing backup is silent.
2. Keep the `ArrStack` folder in the backup. It holds every app's settings.
3. **Test the memory once** with memtest86+ on a new or second-hand machine. Bad memory slowly damages databases, and shows up as "database disk image is malformed" in Sonarr or Radarr, or apps that crash for no reason.
4. Watch free space. At 90 percent full, a drive gets slow, and at 100 percent the apps stop.
5. After an unclean shutdown, check the filesystem before you trust it.
