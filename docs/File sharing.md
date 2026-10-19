# File sharing

This part is optional. It makes your media folder and your drives show up on your home network, so you can open them from a Windows PC, a Mac, a Linux computer, an iPhone or an Android phone. You can copy files in and out, play videos straight from the drive, and fix or tidy your library from any device.

It works on Linux only. On Windows and Mac, use the sharing that is already built into the system.

## Two ways to turn it on

| Way | Best for | How |
|---|---|---|
| In the setup page | Most people | On the Apps and accounts step, switch on File sharing. The page lists your media folders and the other drives it found. Untick or remove any you do not want, set a login, and install. |
| With the script | A Linux computer you manage yourself, or one that does not run the setup page | Run the script in extras/File sharing. It installs Samba on the computer itself. |

Both give the same result: one login for every share, no guest access, and settings chosen for speed and safety.

The script is used like this:

```
sudo bash "extras/File sharing/Share folders on this computer.sh" /mnt/Media /mnt/Backup
```

Each folder you list becomes one share, named after the folder.

Add the word `--read-only` before the folders to stop anyone changing them.

You can run it again with a new list at any time. It only replaces the part it wrote, and it saves a copy of your old settings first.

If you already share things yourself, your own settings are kept and only the new shares are added.

## Set up your drives properly

How a drive is prepared decides how well everything works. Spend ten minutes here and you will not have trouble later.

### Choose the right drive format

| Format | Good for | What to know |
|---|---|---|
| ext4 | The best choice for a Linux server | Fast, safe if the power goes out, supports every feature the apps use |
| XFS | Large media drives on Linux | Also very good |
| NTFS | A drive you also plug into Windows | Works well. Slightly slower. Needs the ntfs-3g program on Linux |
| exFAT | A drive you move between Windows, Mac and Linux | Works, but has two real problems, see below |

The two problems with exFAT:

1. It cannot link files. When Sonarr and Radarr finish a download, they normally link the file into your library, which is instant and uses no extra space. On exFAT they must copy it, so every download is written twice.
2. It has no protection against sudden power loss. After a power cut or a pulled cable the drive can be damaged. Linux then prints "Volume was not properly unmounted". Run `sudo fsck.exfat -p /dev/sdX1` with the drive unmounted to repair it.

If you can, keep your media on ext4 or XFS. If a drive has to stay exFAT, shut the computer down properly and leave about 15 percent of the drive free.

### Keep downloads and your library on the same drive

This is what lets finished downloads be linked instead of copied. The setup page shows "same drive as downloads: instant, uses no extra space" next to each folder when this is true.

### Make the drive mount by itself, the same way every time

Drives that are mounted by hand disappear after a restart, and the apps then write into an empty folder on the wrong disk. Add each drive to `/etc/fstab` by its ID, not by a name like sdb, because those names change.

1. Find the ID: `sudo blkid`
2. Make the folder: `sudo mkdir -p /mnt/Media`
3. Add one line to `/etc/fstab`. Pick the line for your format, and replace the ID and your user and group numbers (run `id` to see them).

```
# ext4 or XFS
UUID=your-drive-id  /mnt/Media  ext4  defaults,nofail  0  2

# NTFS
UUID=your-drive-id  /mnt/Media  ntfs-3g  uid=1000,gid=1000,umask=002,nofail  0  0

# exFAT
UUID=your-drive-id  /mnt/Media  exfat  uid=1000,gid=1000,umask=002,nofail  0  0
```

4. Test it without restarting: `sudo mount -a`. If there is no message, it worked.

`nofail` means the computer still starts if the drive is unplugged. For ext4 and XFS, make the folders belong to you once with `sudo chown -R 1000:1000 /mnt/Media`.

### Do not put the apps on the same small drive as your media

Keep the setup folder (the apps and their settings) on your main drive, and your movies and shows on the big drives. The setup page keeps them apart for you.

## Connect from your devices

Use the address of the computer that runs the setup. It is shown on the final page. The login is the one you chose for file sharing.

| Device | How |
|---|---|
| Windows | Open File Explorer, click the address bar, type `\\your-server\Media` and press Enter. To keep it, right click the share and choose Map network drive. |
| Mac | In Finder press Command and K, type `smb://your-server/Media` and click Connect. Tick Remember this password. |
| Linux | In your file manager choose Other locations and type `smb://your-server/Media`. |
| iPhone and iPad | Open the Files app, tap the three dots, choose Connect to Server and type `smb://your-server/Media`. |
| Android | Use a file app that can open network shares, such as the free CX File Explorer or Solid Explorer. Add an SMB connection. |

The computer does not appear by itself under Network. That is on purpose, so no other programs have to run. Type the address once and save it.

If the name does not work, use the number address instead, for example `smb://192.168.X.X/Media`.

## Use it away from home

Never open port 445 on your router. Programs on the internet scan for it all day, and it is one of the most attacked ports there is. The safe way is Tailscale. It makes a private, encrypted link between your own devices, with nothing opened on your router.

1. Install Tailscale on the server and on the device you carry (tailscale.com/download). Sign in to the same account on both.
2. On the device you carry, use the Tailscale address of the server instead of the home address. It starts with 100 and is shown in the Tailscale app, for example `smb://100.x.y.z/Media`.
3. To check the link is direct, run `tailscale status` on your device. It should say `direct` next to the server. If it says `relay`, the connection is going through a slower detour. Restarting Tailscale on both ends usually fixes that.

### Let family or friends in without giving them everything

1. Open the Tailscale admin page, then Machines, find the server, and choose Share. Send them the link.
2. Then limit what they can reach. Sharing a machine lets them try every port on it, including your other apps. In the Access controls page, add a rule that only allows the file sharing port and the apps you want them to use:

```
{"action": "accept", "src": ["autogroup:shared"], "dst": ["tag-or-address-of-your-server:445,8096"]}
```

Use the Preview rules box to test it before you save. Port 445 is file sharing and 8096 is Jellyfin. If Tailscale does not accept the group name, look up the current name for shared users in the Tailscale access control help.

### How fast will it be away from home?

Away from home, the slowest part is almost always your home internet upload speed, not the server. Many home lines upload at only 2 to 20 MB per second, and Tailscale adds very little on top. You can test it: on the server run a speed test and look at the upload number.

What that means in practice:

1. Copying files works well at any speed, it just takes longer for big ones.
2. For watching films away from home, use Jellyfin, not the file share. Jellyfin adjusts the picture quality to your connection, so it keeps playing smoothly. A raw video file over a slow upload will stutter.
3. On the home network, with the server on a cable, expect the full speed of your network, usually 100 MB per second or more on a gigabit cable.

## What the setup changes for speed and safety

You do not need to do anything, this is only so you know.

1. SMB version 2.1 or newer only. Older versions are slow and unsafe.
2. `use sendfile`, asynchronous reads and writes, and fast network settings for large files.
3. Idle connections are closed after 30 seconds so they do not pile up.
4. Only your home network, other private ranges and Tailscale may connect. Anyone else is refused before they can even try a password.
5. No guest access. Every share needs the login.
6. No Apple extras. Mac features like resource forks need a drive that stores extra file information, and exFAT and NTFS drives cannot. Mixing them breaks writing from a Mac. Plain sharing works the same on every drive and every device.
7. Files made over the network belong to the same user as your other apps, so Sonarr, Radarr and Jellyfin can always read and change them.

## Problems and fixes

| What happens | What to do |
|---|---|
| The share asks for a login again and again | Use the full address with your login, and check the password. On Windows, if it still fails, open Credential Manager and remove saved entries for the server. |
| It connects, but you cannot write | The share may be set to read only. Check the page, or the `read only` line for that share. Also check that the drive is mounted and not full. |
| From a Mac, copying fails on a big folder | Make sure the setup was run with this version. Older settings used Apple extras that exFAT and NTFS cannot store. |
| It works over Tailscale but not on your home network | Something on your home network is cutting file sharing connections. See the next section. |
| Port 445 is already in use | The computer already shares files with its own Samba. Keep using that one, or run the script, which adds to it safely. |
| After a restart the share is empty | The drive did not mount. Check `/etc/fstab` and run `sudo mount -a`. |
| It cannot be found by name | Type the number address. Names are not announced on purpose. |

### It works with Tailscale but not at home

This was found while building this feature.

A Mac could open the share through Tailscale. At home, the connection was cut a few thousandths of a second after it began, while websites on the same computer loaded fine.

Recording the traffic showed a reset packet that arrived with a different travel count than the Mac's own packets. So it was sent by a device in between, not by the Mac or the server.

Likely causes are a router or access point with intrusion protection, a security filter for older file sharing, or a mesh Wi-Fi setting. Things to try:

1. Look in your router for a setting with a name like SMB protection, Windows file sharing block, intrusion prevention or parental security, and turn it off or allow your server.
2. Connect the computer to the router with a cable once, to see if Wi-Fi is the cause.
3. Use the Tailscale address from your computer even at home. It works the same, and it is encrypted.

## Setting it up by hand

If you want to write the settings yourself, this is the complete file the setup writes. Put it in `/etc/samba/smb.conf`, add one share block per folder, create the login with `sudo smbpasswd -a yourlogin`, and restart with `sudo systemctl restart smbd`.

```
[global]
   workgroup = WORKGROUP
   server role = standalone server
   map to guest = never
   restrict anonymous = 2
   server min protocol = SMB2_10
   hosts allow = 127.0.0.1 ::1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 fe80::/10 fd00::/8
   hosts deny = 0.0.0.0/0
   ea support = no
   store dos attributes = no
   mangled names = no
   unix extensions = no
   use sendfile = yes
   aio read size = 16384
   aio write size = 16384
   socket options = TCP_NODELAY IPTOS_LOWDELAY
   deadtime = 30
   smb ports = 445
   disable netbios = yes
   load printers = no
   printing = bsd
   printcap name = /dev/null
   disable spoolss = yes

[Media]
   path = /mnt/Media
   browseable = yes
   read only = no
   guest ok = no
   valid users = yourlogin
   force user = the-user-who-owns-your-files
   create mask = 0664
   directory mask = 0775
   force create mode = 0664
   force directory mode = 0775
```

Check it with `testparm -s` before you restart. It prints nothing but "Loaded services file OK" when the file is correct.
