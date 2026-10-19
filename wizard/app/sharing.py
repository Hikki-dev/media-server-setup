"""Optional file sharing: shows your media folder and drives on your home network (Windows, Mac, Linux, phones).

The shares are served by a small Samba container. This file builds its settings. It does not need Docker, so it can be
tested on its own (see tools/test_sharing.py).

Choices made here, and why:
  * One login for every share, and no guest access, so nobody on the network can open your files without it.
  * Only private network addresses and Tailscale addresses are allowed in. Never open port 445 on your router.
  * No Apple extras (fruit and streams). Many drives (exFAT, NTFS) cannot store them, and mixing them breaks writes
    from a Mac. Plain sharing works the same on every kind of drive.
  * The share user has the same user and group number as the other apps, so every app can read and write the same files.
"""
import os
import re

SHARE_ROOT = "/shares"
CONFIG_DIR = "config/samba"
NAME_OK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,62}$")
USER_OK = re.compile(r"^[a-z_][a-z0-9_\-]{0,30}$")
RESERVED = {"global", "homes", "printers", "print$", "ipc$", "admin$"}
# addresses allowed to connect: this computer, home networks and Tailscale (100.64.0.0/10)
ALLOWED = "127.0.0.1 ::1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 100.64.0.0/10 fe80::/10 fd00::/8"


def clean_name(text):
    """A share name that every system accepts, made from a folder name."""
    n = re.sub(r"[^A-Za-z0-9 _.\-]", "", (text or "").strip())
    n = re.sub(r"\s+", " ", n).strip(" .-")
    return n[:63] or "Share"


def unique(names):
    seen, out = {}, []
    for n in names:
        base, k = n, 2
        while n.lower() in seen:
            n = f"{base} {k}"
            k += 1
        seen[n.lower()] = 1
        out.append(n)
    return out


PSEUDO = {"proc", "sysfs", "tmpfs", "devtmpfs", "devpts", "cgroup", "cgroup2", "overlay", "squashfs", "mqueue", "debugfs", "tracefs", "securityfs",
          "pstore", "bpf", "autofs", "configfs", "fusectl", "hugetlbfs", "binfmt_misc", "ramfs", "nsfs", "efivarfs", "fuse.lxcfs"}
FS_NAMES = {"exfat": "exFAT", "vfat": "FAT", "ntfs": "NTFS", "ntfs3": "NTFS", "fuseblk": "NTFS or exFAT", "ext4": "ext4", "ext3": "ext3",
            "xfs": "XFS", "btrfs": "Btrfs", "zfs": "ZFS", "nfs": "network folder", "nfs4": "network folder", "cifs": "network folder"}


def parse_mounts(text):
    """Real drives from the text of /proc/mounts: [{"mp": "/mnt/Media", "fs": "ext4"}]."""
    out = []
    for line in (text or "").splitlines():
        f = line.split()
        if len(f) >= 3 and f[2] not in PSEUDO:
            out.append({"mp": f[1].replace("\\040", " "), "fs": f[2]})
    return out


def fs_of(path, table):
    """The kind of drive a folder is on: the longest mount point that contains it."""
    best = None
    for m in table or []:
        mp = m["mp"].rstrip("/") or "/"
        if path == mp or path.startswith(mp.rstrip("/") + "/"):
            if best is None or len(mp) > len(best["mp"].rstrip("/") or "/"):
                best = m
    return FS_NAMES.get(best["fs"], best["fs"]) if best else ""


def suggest(mounts, drives, table=None):
    """Starting list of shares: every folder the setup already uses, then the other drives found on this computer.

    mounts: [{"host": "/data"}] from the storage plan. drives: [{"name": "Backup", "path": "/mnt/Backup"}].
    table: the real drives from parse_mounts. When given, only folders that really are drives are offered as extra drives.
    """
    items, have = [], []
    for m in mounts or []:
        p = (m.get("host") or "").rstrip("/") or "/"
        items.append({"name": clean_name(os.path.basename(p) or "Media"), "path": p, "readOnly": False, "kind": "media", "on": True, "fs": fs_of(p, table)})
        have.append(p)
    mps = {(m["mp"].rstrip("/") or "/") for m in (table or [])}
    for d in drives or []:
        p = (d.get("path") or "").rstrip("/")
        if not p or (table is not None and p not in mps):
            continue            # not a drive of its own (an ordinary folder, or a link to another drive)
        if not any(p == h or p.startswith(h + "/") or h.startswith(p + "/") for h in have):
            items.append({"name": clean_name(d.get("name") or os.path.basename(p)), "path": p, "readOnly": False, "kind": "drive", "on": True,
                          "fs": fs_of(p, table), "totalBytes": d.get("totalBytes")})
    names = unique([i["name"] for i in items])
    for i, n in zip(items, names):
        i["name"] = n
    return items


def shares_of(cfg):
    sm = cfg.get("samba") or {}
    return [s for s in (sm.get("shares") or []) if s.get("name") and s.get("path") and s.get("on", True)]


def check(cfg):
    """Plain sentences about anything that would stop the sharing from working. Empty list means fine."""
    errs = []
    sm = cfg.get("samba") or {}
    if cfg.get("hostOs") not in (None, "linux"):
        errs.append("File sharing only works when the setup runs on Linux. On Windows and Mac, use the built in sharing of the system.")
    if not USER_OK.match(sm.get("user") or ""):
        errs.append("File sharing: the user name must be lowercase letters, numbers, dashes or underscores, and start with a letter.")
    pw = sm.get("password") or ""
    if len(pw) < 8 or ":" in pw or "\n" in pw or "\r" in pw:
        errs.append("File sharing: the password needs 8 or more characters and cannot contain a colon.")
    shares = shares_of(cfg)
    if not shares:
        errs.append("File sharing: choose at least one folder to share.")
    names = [s["name"].lower() for s in shares]
    for s in shares:
        if not NAME_OK.match(s["name"]) or s["name"].lower() in RESERVED:
            errs.append(f"File sharing: \"{s['name']}\" is not a usable share name. Use letters, numbers and spaces.")
        if not s["path"].startswith("/"):
            errs.append(f"File sharing: \"{s['path']}\" is not a full folder path.")
    if len(set(names)) != len(names):
        errs.append("File sharing: two shares have the same name.")
    return errs


def smb_conf(cfg):
    sm = cfg["samba"]
    shares = shares_of(cfg)
    user = sm["user"]
    out = f"""# Written by the Media Server Setup wizard. Run the wizard again to change it.
[global]
   server string = Media Server
   workgroup = WORKGROUP
   server role = standalone server
   security = user
   map to guest = never
   restrict anonymous = 2
   idmap config * : range = 3000-7999
   server min protocol = SMB2_10
   hosts allow = {sm.get('allow') or ALLOWED}
   hosts deny = 0.0.0.0/0
   # plain sharing, the same on every kind of drive (no Apple extras, see sharing.py)
   ea support = no
   store dos attributes = no
   mangled names = no
   unix charset = UTF-8
   unix extensions = no
   wide links = yes
   follow symlinks = yes
   acl allow execute always = yes
   host msdfs = no
   # speed
   use sendfile = yes
   aio read size = 16384
   aio write size = 16384
   socket options = TCP_NODELAY IPTOS_LOWDELAY
   deadtime = 30
   smb ports = 445
   disable netbios = yes
   # no printers
   load printers = no
   printing = bsd
   printcap name = /dev/null
   disable spoolss = yes
   log level = 1
   max log size = 1000
"""
    for s in shares:
        ro = bool(s.get("readOnly"))
        out += f"""
[{s['name']}]
   path = {SHARE_ROOT}/{s['name']}
   browseable = yes
   read only = {'yes' if ro else 'no'}
   guest ok = no
   valid users = {user}
   force user = {user}
   force group = smb
   create mask = 0664
   directory mask = 0775
   force create mode = 0664
   force directory mode = 0775
"""
    return out


def users_conf(cfg):
    """One line for the share user: name:user number:group:group number:password."""
    sm = cfg["samba"]
    return f"{sm['user']}:{int(cfg.get('uid', 1000))}:smb:{int(cfg.get('gid', 1000))}:{sm['password']}\n"


def write_files(cfg, stack_dir):
    """Write smb.conf and users.conf. The password file can only be read by its owner."""
    d = os.path.join(stack_dir, CONFIG_DIR)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "smb.conf"), "w") as f:
        f.write(smb_conf(cfg))
    p = os.path.join(d, "users.conf")
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(users_conf(cfg))


def service(cfg, port, config_host):
    """The compose service. config_host is the host path of the stack folder (for the two settings files)."""
    vols = [f"{config_host}/{CONFIG_DIR}/smb.conf:/etc/samba/smb.conf:ro", f"{config_host}/{CONFIG_DIR}/users.conf:/etc/samba/users.conf:ro"]
    for s in shares_of(cfg):
        vols.append(f"{s['path']}:{SHARE_ROOT}/{s['name']}")
    return {"image": "dockurr/samba:latest", "restart": "unless-stopped", "environment": [f"TZ={cfg.get('tz', 'UTC')}"],
            "ports": [f"{port}:445"], "volumes": vols}


def addresses(host_address, shares):
    """How to open each share, written out for people."""
    h = host_address or "your-server"
    return [{"name": s["name"], "windows": f"\\\\{h}\\{s['name']}", "mac": f"smb://{h}/{s['name'].replace(' ', '%20')}"} for s in shares]
