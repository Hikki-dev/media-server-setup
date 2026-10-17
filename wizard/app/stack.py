"""Builds the docker-compose stack, plans drive mounts, pre-seeds config files and drives docker."""
import base64
import hashlib
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import yaml

from arrapi import CANCEL, Fatal

STACK = "/stack"                      # host stack folder, mounted into this container
HOST_STACK = os.environ.get("HOST_STACK_DIR", "/stack").replace("\\", "/")
PROJECT = os.environ.get("STACK_PROJECT", "arrstack")
HELPER_IMAGE = "alpine:3"

DEFAULT_PORTS = {
    "qbittorrent": 8080, "sonarr": 8989, "radarr": 7878, "prowlarr": 9696, "bazarr": 6767,
    "jellyfin": 8096, "seerr": 5055, "flaresolverr": 8191, "homepage": 3000,
    "metube": 8081, "komga": 25600, "mylar3": 8090, "scrutiny": 8087,
}
INTERNAL = {  # port each app listens on inside its container
    "qbittorrent": 8080, "sonarr": 8989, "radarr": 7878, "prowlarr": 9696, "bazarr": 6767,
    "jellyfin": 8096, "seerr": 5055, "flaresolverr": 8191, "homepage": 3000,
    "metube": 8081, "komga": 25600, "mylar3": 8090, "scrutiny": 8080, "regional": 9120,
}

RUNNING = {"proc": None}


def sh(cmd, timeout=900, check=True):
    """Run a command; the Stop button can terminate it mid-flight."""
    if CANCEL.is_set():
        raise Fatal("Stopped")
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    RUNNING["proc"] = p
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        raise RuntimeError("command timed out: " + " ".join(cmd[:4]))
    finally:
        RUNNING["proc"] = None
    if CANCEL.is_set():
        raise Fatal("Stopped")
    if check and p.returncode != 0:
        raise RuntimeError((err or out).strip()[-1500:])
    return subprocess.CompletedProcess(cmd, p.returncode, out, err)


def kill_running():
    p = RUNNING["proc"]
    if p and p.poll() is None:
        p.terminate()


def hostpath(sub=""):
    return f"{HOST_STACK}/{sub}".rstrip("/")


def qbit_pbkdf2(password):
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100000, dklen=64)
    return "@ByteArray(%s:%s)" % (base64.b64encode(salt).decode(), base64.b64encode(dk).decode())


# ---------------------------------------------------------------- storage planning
def posix(p):
    p = (p or "").replace("\\", "/").strip()
    return (p.rstrip("/") or "/") if not re.match(r"^[A-Za-z]:/?$", p) else p[:2] + "/"


def drive_key(path, host_os):
    """Best guess of which physical drive a path is on, from its location alone."""
    p = posix(path)
    if host_os == "win":
        m = re.match(r"^([A-Za-z]:)", p)
        return m.group(1).upper() if m else "win"
    if host_os == "mac":
        m = re.match(r"^(/Volumes/[^/]+)", p)
        return m.group(1) if m else "/"
    m = re.match(r"^(/mnt/[^/]+|/media/[^/]+/[^/]+|/run/media/[^/]+/[^/]+|/srv/[^/]+)", p)
    return m.group(1) if m else "/"


def _segments(p):
    p = posix(p)
    m = re.match(r"^([A-Za-z]:)(/.*)?$", p)
    if m:
        return [m.group(1)] + [s for s in (m.group(2) or "").split("/") if s]
    return [s for s in p.split("/") if s]


def _join(segs, win):
    if win:
        return segs[0] + "/" + "/".join(segs[1:]) if len(segs) > 1 else segs[0] + "/"
    return "/" + "/".join(segs)


def common_dir(paths):
    segs = [_segments(p) for p in paths]
    out = []
    for parts in zip(*segs):
        if len(set(parts)) != 1:
            break
        out.append(parts[0])
    return out


BROAD = re.compile(r"^(/|/Users|/home|/Volumes|/mnt|/media|/run/media|/srv|/Users/[^/]+|/home/[^/]+|[Cc]:/?)$")


def plan_storage(cfg):
    """Turn the storage answers into container mounts and container-side paths.

    Paths on the same drive share one mount so Sonarr/Radarr can hard-link finished downloads into the library;
    paths on different drives get their own mounts and files are copied across.
    """
    st = cfg["storage"]
    win = cfg.get("hostOs") == "win"
    if st.get("mode") == "single":
        base = posix(st["base"])
        libs = [{"type": "movies", "host": f"{base}/media/Movies", "path": "/data/media/Movies", "linked": True},
                {"type": "tv", "host": f"{base}/media/TV Shows", "path": "/data/media/TV Shows", "linked": True},
                {"type": "anime", "host": f"{base}/media/Anime", "path": "/data/media/Anime", "linked": True}]
        return {"mounts": [{"host": base, "container": "/data"}], "downloads": "/data/torrents",
                "downloadsHost": f"{base}/torrents", "libs": libs, "mode": "single"}

    dl = posix(st["downloads"])
    libs_in = [{"type": l["type"], "host": posix(l["path"])} for l in st["libraries"] if l.get("path")]
    allp = list(dict.fromkeys([dl] + [l["host"] for l in libs_in]))
    # cluster paths that can share one mount (same drive, and a dedicated common parent folder)
    clusters = []
    for p in allp:
        key = drive_key(p, cfg.get("hostOs"))
        for c in clusters:
            if c["key"] == key:
                anc = common_dir(c["paths"] + [p])
                if anc and not BROAD.match(_join(anc, win)):
                    c["paths"].append(p)
                    break
        else:
            clusters.append({"key": key, "paths": [p]})
    mounts, where = [], {}
    for c in clusters:
        idx = len(mounts)
        if len(c["paths"]) > 1:
            anc = common_dir(c["paths"])
            anc_path = _join(anc, win)
            mounts.append({"host": anc_path, "container": f"/mnt/g{idx}"})
            for p in c["paths"]:
                rel = "/".join(_segments(p)[len(anc):])
                where[p] = (idx, f"/mnt/g{idx}" + (f"/{rel}" if rel else ""))
        else:
            mounts.append({"host": c["paths"][0], "container": f"/mnt/g{idx}"})
            where[c["paths"][0]] = (idx, f"/mnt/g{idx}")
    dl_idx, dl_c = where[dl]
    libs = [{**l, "path": where[l["host"]][1], "linked": where[l["host"]][0] == dl_idx} for l in libs_in]
    return {"mounts": mounts, "downloads": dl_c, "downloadsHost": dl, "libs": libs, "mode": "multi"}


def libs_of(plan, kind):
    return [l for l in plan["libs"] if l["type"] == kind]


# ---------------------------------------------------------------- compose
def compose(cfg):
    p = cfg["ports"]
    s = cfg["services"]
    plan = plan_storage(cfg)
    uid, gid = str(cfg.get("uid", 1000)), str(cfg.get("gid", 1000))
    tz = cfg.get("tz", "UTC")
    mounts = [f"{m['host']}:{m['container']}" for m in plan["mounts"]]
    base_env = [f"PUID={uid}", f"PGID={gid}", f"TZ={tz}"]
    cfgdir = lambda n: f"{hostpath('config/' + n)}:/config"  # noqa: E731
    svc = {}

    def hc(cmd, start=60):
        return {"test": ["CMD-SHELL", cmd], "interval": "60s", "timeout": "15s", "retries": 3, "start_period": f"{start}s"}
    heal = {"deunhealth.restart.on.unhealthy": "true"}

    def lsio(name, image, env=(), media=True, **kw):
        d = {"image": image, "restart": "unless-stopped", "environment": base_env + list(env),
             "volumes": [cfgdir(name)] + (mounts if media else []),
             "ports": [f"{p[name]}:{INTERNAL[name]}"]}
        d.update(kw)
        svc[name] = d

    qenv = [f"WEBUI_PORT={INTERNAL['qbittorrent']}", "TORRENTING_PORT=6881"]
    if cfg["qbit"].get("vuetorrent", True):
        qenv.append("DOCKER_MODS=ghcr.io/vuetorrent/vuetorrent-lsio-mod:latest")
    lsio("qbittorrent", "lscr.io/linuxserver/qbittorrent:latest", env=qenv)
    svc["qbittorrent"]["ports"] += ["6881:6881", "6881:6881/udp"]
    lsio("prowlarr", "lscr.io/linuxserver/prowlarr:latest", media=False)
    lsio("sonarr", "lscr.io/linuxserver/sonarr:latest")
    lsio("radarr", "lscr.io/linuxserver/radarr:latest")
    solver = cfg.get("solver", "flaresolverr")
    sp = [f"{p['flaresolverr']}:8191"]
    if solver == "byparr":
        svc["solver"] = {"image": "ghcr.io/thephaseless/byparr:latest", "restart": "unless-stopped",
                         "environment": [f"TZ={tz}"], "shm_size": "1gb", "ports": sp}
    elif solver == "trawl":
        svc["solver-redis"] = {"image": "redis:7-alpine", "restart": "unless-stopped"}
        svc["solver"] = {"image": "ghcr.io/germondai/trawl:latest", "restart": "unless-stopped", "shm_size": "1gb",
                         "environment": [f"TZ={tz}", "REDIS_URL=redis://solver-redis:6379/1",
                                         f"BROWSER_POOL_SIZE={cfg.get('solverPool', 2)}"],
                         "depends_on": ["solver-redis"], "ports": sp}
    else:
        svc["solver"] = {"image": "ghcr.io/flaresolverr/flaresolverr:latest", "restart": "unless-stopped",
                         "environment": [f"TZ={tz}", "LOG_LEVEL=info", "CAPTCHA_SOLVER=none"], "shm_size": "1gb", "ports": sp}
    if True:   # the adapter also serves BT4G for everyone
        svc["regional"] = {"image": "arr-wizard:latest", "restart": "unless-stopped", "pull_policy": "never",
                           "command": ["python", "-u", "bridge.py"],
                           "environment": [f"TZ={tz}", "DATA_DIR=/data", "SOLVER_URL=http://solver:8191/v1"],
                           "volumes": [f"{hostpath('config/regional')}:/data"]
                           + ([f"{hostpath('config/jellyfin/livetv')}:/livetv"] if s.get("jellyfin") else [])}
    vpn = (cfg.get("livetv") or {}).get("vpn") or {}
    if vpn.get("provider") == "nordvpn" and vpn.get("user") and vpn.get("password") and s.get("jellyfin"):
        # optional: two VPN exits (UK and US) the regional service relays region-locked live channels through
        for key, country in (("uk", "United Kingdom"), ("us", "United States")):
            svc[f"gluetun-{key}"] = {"image": "qmcgaw/gluetun:latest", "restart": "unless-stopped", "cap_add": ["NET_ADMIN"],
                                     "devices": ["/dev/net/tun:/dev/net/tun"], "env_file": ["config/vpn/nord.env"], "mem_limit": "192m", "labels": heal,
                                     "environment": ["VPN_SERVICE_PROVIDER=nordvpn", "VPN_TYPE=openvpn", f"SERVER_COUNTRIES={country}",
                                                     "HTTPPROXY=on", "HTTPPROXY_LISTENING_ADDRESS=:8888", "FIREWALL_INPUT_PORTS=8888"]}
        svc["regional"]["environment"].append("VPN_PROXIES=uk=http://gluetun-uk:8888,us=http://gluetun-us:8888")
    if s.get("bazarr"):
        lsio("bazarr", "lscr.io/linuxserver/bazarr:latest")
    if s.get("jellyfin"):
        lsio("jellyfin", "lscr.io/linuxserver/jellyfin:latest", **({"devices": ["/dev/dri:/dev/dri"]} if cfg.get("gpu") else {}))
    if s.get("seerr"):
        svc["seerr"] = {"image": "ghcr.io/seerr-team/seerr:latest", "init": True, "restart": "unless-stopped",
                        "environment": [f"TZ={tz}"], "user": f"{uid}:{gid}",
                        "volumes": [f"{hostpath('config/seerr')}:/app/config"],
                        "ports": [f"{p['seerr']}:5055"]}
    if s.get("homepage"):
        svc["homepage"] = {"image": "ghcr.io/gethomepage/homepage:latest", "restart": "unless-stopped",
                           "environment": base_env + ["HOMEPAGE_ALLOWED_HOSTS=*"],
                           "volumes": [f"{hostpath('config/homepage')}:/app/config"],
                           "ports": [f"{p['homepage']}:3000"]}
    extra = plan["mounts"][0]["host"] if plan["mounts"] else HOST_STACK
    if s.get("metube"):
        svc["metube"] = {"image": "ghcr.io/alexta69/metube:latest", "restart": "unless-stopped",
                         "environment": [f"UID={uid}", f"GID={gid}", "DOWNLOAD_DIR=/downloads",
                                         "CREATE_SUBDIR_FOR_PLAYLISTS=true"],
                         "volumes": [f"{extra}/downloads-youtube:/downloads"],
                         "ports": [f"{p['metube']}:8081"]}
    if s.get("komga"):
        svc["komga"] = {"image": "gotson/komga:latest", "restart": "unless-stopped", "user": f"{uid}:{gid}",
                        "volumes": [f"{hostpath('config/komga')}:/config", f"{extra}/books:/books"],
                        "ports": [f"{p['komga']}:25600"]}
    if s.get("mylar3"):
        lsio("mylar3", "lscr.io/linuxserver/mylar3:latest", media=False)
        svc["mylar3"]["volumes"] += [f"{extra}/books/comics:/comics"]
    if s.get("scrutiny"):
        svc["scrutiny"] = {"image": "ghcr.io/analogj/scrutiny:master-omnibus", "restart": "unless-stopped",
                           "cap_add": ["SYS_RAWIO"],
                           "volumes": [f"{hostpath('config/scrutiny')}:/opt/scrutiny/config"],
                           "ports": [f"{p['scrutiny']}:8080"]}
    # healthchecks + automatic restart of anything that hangs (the pattern a long-running home server uses)
    checks = {"sonarr": hc("curl -sf http://localhost:8989/ping >/dev/null || exit 1"),
              "radarr": hc("curl -sf http://localhost:7878/ping >/dev/null || exit 1"),
              "prowlarr": hc("curl -sf http://localhost:9696/ping >/dev/null || exit 1"),
              "qbittorrent": hc("curl -s -o /dev/null http://127.0.0.1:8080/ || exit 1", 90),
              "bazarr": hc("curl -s -o /dev/null http://localhost:6767/ || exit 1", 90),
              "jellyfin": hc("curl -sf http://localhost:8096/health >/dev/null || exit 1", 90),
              "seerr": hc("wget --no-verbose --tries=1 --spider http://localhost:5055/api/v1/status || exit 1"),
              "solver": hc("python3 -c \"import urllib.request;urllib.request.urlopen('http://localhost:8191/',timeout=10)\" 2>/dev/null"
                           " || curl -sf http://localhost:8191/ >/dev/null || curl -sf http://localhost:8191/health >/dev/null || exit 1", 90)}
    if "regional" in svc:
        checks["regional"] = hc("python3 -c \"import urllib.request;urllib.request.urlopen('http://localhost:9120/health',timeout=8)\" || exit 1", 20)
    for name, test in checks.items():
        if name in svc:
            svc[name]["healthcheck"] = test
            svc[name]["labels"] = {**svc[name].get("labels", {}), **heal}
    svc["deunhealth"] = {"image": "qmcgaw/deunhealth", "restart": "always", "network_mode": "none",
                         "environment": ["LOG_LEVEL=info", f"TZ={tz}"],
                         "volumes": ["/var/run/docker.sock:/var/run/docker.sock"]}
    # apps the person already runs are used as they are: they are not part of the generated stack
    for app in (cfg.get("adopt") or {}):
        svc.pop("solver" if app == "flaresolverr" else app, None)
        if app == "flaresolverr":
            svc.pop("solver-redis", None)
    mine = (cfg.get("adopt") or {}).get("jellyfin")
    if mine and "regional" in svc and mine.get("configMount"):       # the Live TV files must land in THEIR Jellyfin's config folder
        svc["regional"]["volumes"] = [v for v in svc["regional"]["volumes"] if not v.endswith(":/livetv")] + [f"{mine['configMount']}/livetv:/livetv"]
    return {"name": PROJECT, "services": svc}


def write_vpn_env(cfg):
    """The VPN service credentials live in their own owner-only file next to the compose file; they never appear in the compose file."""
    vpn = (cfg.get("livetv") or {}).get("vpn") or {}
    if vpn.get("provider") != "nordvpn" or not (vpn.get("user") and vpn.get("password")):
        return
    d = f"{STACK}/config/vpn"
    os.makedirs(d, exist_ok=True)
    p = f"{d}/nord.env"
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"OPENVPN_USER='{vpn['user']}'\nOPENVPN_PASSWORD='{vpn['password']}'\n")


def write_compose(cfg):
    write_vpn_env(cfg)
    path = f"{STACK}/docker-compose.yml"
    header = "# Generated by the Media Server Setup wizard. Re-run the wizard to change it.\n"
    with open(path, "w") as f:
        f.write(header + yaml.safe_dump(compose(cfg), sort_keys=False, default_flow_style=False))
    return path


# ---------------------------------------------------------------- host folders (through a throw-away helper container)
def helper(host_path, script, rw=False, uid=None, timeout=60):
    """Run a short shell script with host_path mounted at /m."""
    cmd = ["docker", "run", "--rm", "-v", f"{host_path}:/m" + ("" if rw else ":ro")]
    if uid is not None:
        cmd += ["-u", uid]
    cmd += [HELPER_IMAGE, "sh", "-c", script]
    return sh(cmd, timeout=timeout, check=False)


def inspect_path(path, cfg_ids=("1000", "1000")):
    """Existence, writability (as the app user), free space and contents of a host folder."""
    path = posix(path)
    uid = f"{cfg_ids[0]}:{cfg_ids[1]}"
    script = ('p=/m; echo "ITEMS=$(ls -A $p 2>/dev/null | wc -l)"; df -Pk $p | tail -1 | awk \'{print "DF="$2" "$3" "$4}\'; '
              'for d in $p/*/; do [ -d "$d" ] && echo "DIR=$(basename "$d")|$(ls -A "$d" 2>/dev/null | wc -l)"; done; true')
    r = helper(path, script)
    if r.returncode != 0:
        return {"ok": False, "path": path, "error": "Docker cannot open this folder. Check the path and that the drive is shared with Docker."}
    w = helper(path, "touch /m/.arr-w 2>/dev/null && rm -f /m/.arr-w && echo W", rw=True, uid=uid)
    out = {"ok": True, "path": path, "writable": "W" in (w.stdout or ""), "items": 0, "dirs": []}
    for line in r.stdout.splitlines():
        if line.startswith("ITEMS="):
            out["items"] = int(line[6:] or 0)
        elif line.startswith("DF="):
            tot, used, avail = (int(x) * 1024 for x in line[3:].split())
            out.update(totalBytes=tot, usedBytes=used, freeBytes=avail)
        elif line.startswith("DIR="):
            name, n = line[4:].rsplit("|", 1)
            out["dirs"].append({"name": name, "items": int(n or 0)})
    out["dirs"].sort(key=lambda d: d["name"].lower())
    return out


def folder_exists(path, host_os):
    par = parent_of(path, host_os)
    if par is None:
        return True
    name = _segments(path)[-1]
    r = helper(par, f"[ -d '/m/{name}' ] && echo Y")
    return "Y" in (r.stdout or "")


def check_path(path, host_os, ids=("1000", "1000")):
    """Everything the storage page shows about one folder."""
    if not path:
        return {"ok": False, "error": "Enter a folder."}
    if folder_exists(path, host_os):
        out = inspect_path(path, ids)
        out["exists"] = True
        out["drive"] = drive_key(path, host_os)
        return out
    par = parent_of(path, host_os)
    pi = inspect_path(par, ids) if par else {"ok": False}
    return {"ok": bool(pi.get("ok") and pi.get("writable")), "exists": False, "path": posix(path), "items": 0, "dirs": [],
            "freeBytes": pi.get("freeBytes"), "totalBytes": pi.get("totalBytes"), "drive": drive_key(path, host_os),
            "error": None if pi.get("writable") else "This folder does not exist and its parent is not writable."}


def parent_of(path, host_os):
    segs = _segments(path)
    if len(segs) <= 1:
        return None
    return _join(segs[:-1], host_os == "win") if segs[:-1] else "/"


def list_drives(host_os, home):
    """Top-level places to start browsing."""
    cands = []
    if host_os == "mac":
        r = helper("/Volumes", "ls -1 /m", timeout=30)
        cands = [{"name": n, "path": f"/Volumes/{n}"} for n in (r.stdout or "").split("\n") if n]
    elif host_os == "win":
        for letter in "CDEFGHIJ":
            r = helper(f"{letter}:/", "ls -1 /m | head -1", timeout=20)
            if r.returncode == 0:
                cands.append({"name": f"{letter}:", "path": f"{letter}:/"})
    else:
        for base in ("/mnt", "/media", "/srv"):
            r = helper(base, "ls -1 /m", timeout=20)
            if r.returncode == 0:
                cands += [{"name": n, "path": f"{base}/{n}"} for n in r.stdout.split("\n") if n]
    places = [{"name": "Home", "path": home}] if home else []
    if host_os == "mac":   # system/recovery volumes are not places to keep media
        cands = [d for d in cands if d["name"] not in ("Recovery", "Macintosh HD", "Preboot", "VM", "Update")]

    def info(d):
        i = inspect_path(d["path"])
        d["freeBytes"] = i.get("freeBytes")
        d["totalBytes"] = i.get("totalBytes")
        return d
    with ThreadPoolExecutor(max_workers=4) as ex:
        drives = list(ex.map(info, cands))
        places = list(ex.map(info, places))
    return {"drives": [d for d in drives if (d.get("totalBytes") or 0) > 2e9], "places": places}


def make_folder(parent, name, uid):
    name = re.sub(r'[\\/:*?"<>|]', "", name).strip()
    if not name:
        raise RuntimeError("Enter a folder name.")
    r = helper(parent, f"mkdir -p '/m/{name}' && echo OK", rw=True, uid=uid)
    if "OK" not in (r.stdout or ""):
        raise RuntimeError("Could not create the folder (is the drive writable?).")
    return posix(parent) + "/" + name


def has_gpu(host_os):
    """True when this Linux machine exposes a render device, so Jellyfin can use it for hardware transcoding."""
    if host_os != "linux":
        return False
    r = sh(["docker", "run", "--rm", "-v", "/dev:/h:ro", "alpine:3", "ls", "/h/dri"], timeout=120, check=False)
    return "renderD128" in (getattr(r, "stdout", "") or "")


def prepare_dirs(cfg):
    """Create the folders the plan needs, owned by the app user; existing folders are left alone."""
    plan = plan_storage(cfg)
    uid, gid = cfg.get("uid", 1000), cfg.get("gid", 1000)
    wanted = []   # (container path, is_downloads_subtree)
    wanted += [(f"{plan['downloads']}/{d}", True) for d in ("incomplete", "tv", "movies")] + [(plan["downloads"], True)]
    wanted += [(l["path"], False) for l in plan["libs"]]
    if cfg["services"].get("metube"):
        wanted.append((plan["mounts"][0]["container"] + "/downloads-youtube", False))
    if cfg["services"].get("komga") or cfg["services"].get("mylar3"):
        wanted.append((plan["mounts"][0]["container"] + "/books/comics", False))
    for m in plan["mounts"]:
        cmds = []
        for c, _ in wanted:
            if c == m["container"] or c.startswith(m["container"] + "/"):
                rel = c[len(m["container"]):].lstrip("/")
                tgt = f"/m/{rel}" if rel else "/m"
                cmds.append(f"[ -d '{tgt}' ] || {{ mkdir -p '{tgt}' && chown {uid}:{gid} '{tgt}'; }}")
        if cmds:
            r = helper(m["host"], "; ".join(cmds) + "; true", rw=True, timeout=120)
            if r.returncode != 0:
                raise RuntimeError(f"Cannot create folders in {m['host']}: {(r.stderr or '').strip()[-200:]}")
    for n in ["qbittorrent", "prowlarr", "sonarr", "radarr", "bazarr", "jellyfin", "seerr", "homepage",
              "komga", "mylar3", "scrutiny", "regional", "jellyfin/livetv"]:
        os.makedirs(f"{STACK}/config/{n}", exist_ok=True)
    sh(["chown", "-R", f"{uid}:{gid}", f"{STACK}/config"], check=False)
    return plan


# ---------------------------------------------------------------- seeded config files
def seed_qbittorrent(cfg, plan):
    q = cfg["qbit"]
    dl = plan["downloads"]
    d = f"{STACK}/config/qbittorrent/qBittorrent"
    os.makedirs(d, exist_ok=True)
    conf = f"""[BitTorrent]
Session\\DefaultSavePath={dl}
Session\\TempPath={dl}/incomplete
Session\\TempPathEnabled=true
Session\\Port=6881
Session\\QueueingSystemEnabled=false
Session\\GlobalMaxRatio=0
Session\\GlobalMaxSeedingMinutes=0
Session\\GlobalMaxInactiveSeedingMinutes=2
Session\\ShareLimitAction=Stop

[Core]
AutoDeleteAddedTorrentFile=Never

[LegalNotice]
Accepted=true

[Preferences]
WebUI\\Address=*
WebUI\\Port={INTERNAL['qbittorrent']}
WebUI\\Username={q['username']}
WebUI\\Password_PBKDF2="{qbit_pbkdf2(q['password'])}"
WebUI\\HostHeaderValidation=false
WebUI\\CSRFProtection=false
WebUI\\LocalHostAuth=false
WebUI\\ServerDomains=*
"""
    if q.get("vuetorrent", True):
        conf += "WebUI\\AlternativeUIEnabled=true\nWebUI\\RootFolder=/vuetorrent\n"
    cats = {"tv": {"save_path": f"{dl}/tv"}, "movies": {"save_path": f"{dl}/movies"}}
    cf = f"{d}/qBittorrent.conf"
    if not os.path.exists(cf):  # never clobber a configured install
        open(cf, "w").write(conf)
        json.dump(cats, open(f"{d}/categories.json", "w"), indent=2)


# ---------------------------------------------------------------- docker compose control
def compose_cmd(*args, timeout=1800):
    return sh(["docker", "compose", "-p", PROJECT, "-f", f"{STACK}/docker-compose.yml",
               "--project-directory", STACK, *args], timeout=timeout)


def connect_network():
    """Join this wizard container to the stack network so it can reach services by name."""
    me = os.environ.get("HOSTNAME", "")
    net = f"{PROJECT}_default"
    if me:
        sh(["docker", "network", "connect", net, me], check=False)


def container_state():
    p = sh(["docker", "compose", "-p", PROJECT, "ps", "-a", "--format", "json"], check=False)
    out = []
    for line in (p.stdout or "").splitlines():
        try:
            j = json.loads(line)
            items = j if isinstance(j, list) else [j]
            out += [{"service": i.get("Service"), "state": i.get("State"), "health": i.get("Health", "")} for i in items]
        except ValueError:
            pass
    return out


def reset_fresh():
    """Remove a half-finished install: containers + generated config. Never touches the media folders."""
    sh(["docker", "compose", "-p", PROJECT, "down", "--remove-orphans"], check=False)
    import shutil
    shutil.rmtree(f"{STACK}/config", ignore_errors=True)
    try:
        os.remove(f"{STACK}/docker-compose.yml")
    except OSError:
        pass
