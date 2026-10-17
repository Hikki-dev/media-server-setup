"""Apps the person already runs: find them, connect to them without changing them, and preview what the setup would change.

Nothing here writes to an app. `connect` only joins a container to the shared network under the app's plain name (so every app can reach
every other one) and `preview` runs the normal setup code as a dry run: reads go to the real app, writes are captured."""
import json
import os
import re
import subprocess
import traceback

import audit
import configure as C
import stack as S
from arrapi import REC, Api, ApiError, Recorder

# app -> (label, image/container pattern, port inside the container)
KNOWN = {
    "sonarr": ("Sonarr", r"sonarr", 8989),
    "radarr": ("Radarr", r"radarr", 7878),
    "prowlarr": ("Prowlarr", r"prowlarr", 9696),
    "qbittorrent": ("qBittorrent", r"qbittorrent", 8080),
    "bazarr": ("Bazarr", r"bazarr", 6767),
    "jellyfin": ("Jellyfin", r"jellyfin(?!.*seerr)", 8096),
    "seerr": ("Seerr", r"(jelly|over)?seerr", 5055),
    "flaresolverr": ("FlareSolverr / Byparr", r"(flaresolverr|byparr|trawl)", 8191),
}
# what the wizard asks for when it cannot read the key itself
NEEDS = {"sonarr": [], "radarr": [], "prowlarr": [], "bazarr": [], "seerr": [], "flaresolverr": [],
         "qbittorrent": ["user", "password"], "jellyfin": ["key"]}     # Jellyfin: an API key (Dashboard > API Keys) or a username and password


def docker(*args, timeout=30):
    p = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr if p.returncode else "")


def containers():
    """Every container on this machine with the facts needed to recognise an app."""
    rc, out = docker("ps", "-a", "--format", "{{.ID}}")
    ids = out.split()
    if rc or not ids:
        return []
    rc, raw = docker("inspect", *ids, timeout=60)
    try:
        return json.loads(raw)
    except ValueError:
        return []


def detect():
    """[{app, label, container, image, running, ours, port, networks, configMount}] for every app that is already here."""
    found = []
    for c in containers():
        name = c["Name"].lstrip("/")
        image = c["Config"].get("Image", "")
        labels = c["Config"].get("Labels") or {}
        ours = labels.get("com.docker.compose.project") == S.PROJECT
        hay = f"{image.rsplit(':', 1)[0].rsplit('/', 1)[-1]} {name}".lower()
        for app, (label, rx, port) in KNOWN.items():
            if not re.search(rx, hay):
                continue
            env = {e.split("=", 1)[0]: e.split("=", 1)[1] for e in c["Config"].get("Env") or [] if "=" in e}
            if app == "qbittorrent":
                port = int(env.get("WEBUI_PORT") or port)
            mounts = {m["Destination"]: m["Source"] for m in c.get("Mounts", [])}
            found.append({"app": app, "label": label, "container": name, "image": image, "running": c["State"].get("Running", False),
                          "ours": ours, "port": port, "networks": list((c["NetworkSettings"].get("Networks") or {}).keys()),
                          "configMount": mounts.get("/config") or mounts.get("/app/config"),
                          "health": (c["State"].get("Health") or {}).get("Status", ""),
                          "keyFound": bool(read_key(app, name)) if app in ("sonarr", "radarr", "prowlarr", "bazarr", "seerr") else None})
            break
    return found


def read_key(app, container):
    """The API key of an app, read from its own config file inside its container. None when it cannot be read."""
    files = {"sonarr": "/config/config.xml", "radarr": "/config/config.xml", "prowlarr": "/config/config.xml",
             "bazarr": "/config/config/config.yaml", "seerr": "/app/config/settings.json"}
    path = files.get(app)
    if not path:
        return None
    rc, out = docker("exec", container, "cat", path)
    if rc:
        return None
    if app in ("sonarr", "radarr", "prowlarr"):
        m = re.search(r"<ApiKey>([^<]+)</ApiKey>", out)
    elif app == "bazarr":
        m = re.search(r"apikey:\s*['\"]?([0-9a-f]{32})", out)
    else:
        m = re.search(r'"apiKey"\s*:\s*"([^"]+)"', out)
    return m.group(1) if m else None


def connect(adopt):
    """Make every app of the person's reachable under its plain name (sonarr, qbittorrent, ...) on the shared network. Adds a network to
    the container; changes nothing else about it."""
    net = f"{S.PROJECT}_default"
    # created with compose's own labels, so the stack can be started on it later without a clash
    docker("network", "create", "--label", f"com.docker.compose.project={S.PROJECT}", "--label", "com.docker.compose.network=default", net)
    me = os.environ.get("HOSTNAME", "")
    if me:
        docker("network", "connect", net, me)          # so this wizard can reach them by name too
    for app, a in adopt.items():
        alias = "solver" if app == "flaresolverr" else app
        rc, own = docker("ps", "-a", "--filter", f"label=com.docker.compose.project={S.PROJECT}",
                         "--filter", f"label=com.docker.compose.service={alias}", "--format", "{{.Names}}")
        if not rc and own.strip() and own.strip() != a["container"]:
            raise RuntimeError(f"This wizard already installed its own {KNOWN[app][0]} ({own.split()[0]}). Remove it first "
                               f"(Apps and links, Clean up) or choose to use that one instead of yours.")
        target = a["container"]
        # an app adopted earlier under the same name (another container) must not answer for this one too
        rc, members = docker("network", "inspect", net, "--format", "{{range .Containers}}{{.Name}} {{end}}")
        for other in (members.split() if not rc else []):
            if other == target or other == me or other.startswith(f"{S.PROJECT}-"):
                continue
            rc2, al = docker("inspect", other, "--format", "{{json (index .NetworkSettings.Networks \"" + net + "\").Aliases}}")
            if not rc2 and f'"{alias}"' in al:
                docker("network", "disconnect", net, other)
        rc, mode = docker("inspect", "--format", "{{.HostConfig.NetworkMode}}", target)
        if not rc and mode.strip() == "host":
            # an app on the host network cannot join another network: the others reach it on the machine's address of that network
            rc, gw = docker("network", "inspect", net, "--format", "{{(index .IPAM.Config 0).Gateway}}")
            if rc or not gw.strip():
                raise RuntimeError(f"{a['container']} runs on the host network and its address could not be worked out")
            a["host"] = gw.strip()
            continue
        if not rc and mode.strip().startswith("container:"):
            # the app shares another container's network (for example behind a VPN container): that container carries its ports
            rc, owner = docker("inspect", "--format", "{{.Name}}", mode.strip().split(":", 1)[1])
            if not rc:
                target = owner.strip().lstrip("/")
        docker("network", "disconnect", net, target)          # only so a changed alias takes effect on a re-run
        rc, out = docker("network", "connect", "--alias", alias, net, target)
        if rc and "already exists" not in out:
            raise RuntimeError(f"Could not link {target} to the other apps (a technical step on this computer): {out.strip()[:160]}")


def prepare(cfg):
    """Fill in what can be read from the person's own containers (keys), and say what is still needed."""
    found = {d["app"]: d for d in detect()}
    adopt, missing = {}, []
    for app, a in (cfg.get("adopt") or {}).items():
        d = found.get(app)
        if not d:
            missing.append(f"{KNOWN[app][0]}: we could not find it any more. Is it still running?")
            continue
        entry = {"container": a.get("container") or d["container"], "port": a.get("port") or d["port"]}
        entry["key"] = a.get("key") or read_key(app, entry["container"])
        entry.update({k: a[k] for k in ("user", "password") if a.get(k)})
        if app == "jellyfin":
            need = [] if (entry.get("key") or (entry.get("user") and entry.get("password"))) else ["an API key or an admin username and password"]
        else:
            need = [k for k in NEEDS[app] if not entry.get(k)] + (["key"] if app in ("sonarr", "radarr", "prowlarr", "bazarr", "seerr") and not entry["key"] else [])
        if need:
            missing.append(f"{KNOWN[app][0]}: please fill in " + " and ".join({"key": "its access key", "user": "the username", "password": "the password"}.get(n, n) for n in need))
        adopt[app] = entry
    return adopt, missing


def check_connection(app, a):
    """A quick, read-only test with the details the person gave."""
    try:
        base = f"http://{a['container']}:{a['port']}"
        if app in ("sonarr", "radarr"):
            return Api(base, a["key"], prefix="/api/v3").get("/system/status").get("version")
        if app == "prowlarr":
            return Api(base, a["key"], prefix="/api/v1").get("/system/status").get("version")
        if app == "bazarr":
            return Api(base, prefix="/api", headers={"X-API-KEY": a["key"]}).get("/system/status").get("data", {}).get("bazarr_version")
        if app == "jellyfin":
            api = Api(base, headers={"Authorization": C.JF_AUTH})
            if a.get("key"):
                api.headers["Authorization"] = f'{C.JF_AUTH}, Token="{a["key"]}"'
                api.get("/Users")
            else:
                api.post("/Users/AuthenticateByName", {"Username": a["user"], "Pw": a["password"]})
            return api.get("/System/Info/Public").get("Version")
        if app == "qbittorrent":
            api = Api(base, cookies=True, headers={"Referer": base})
            st, body = api.call("POST", "/api/v2/auth/login", form={"username": a["user"], "password": a["password"]}, raw=True)
            if "Fails" in body:
                raise ApiError(403, "qBittorrent did not accept that username and password")
            return api.call("GET", "/api/v2/app/version", raw=True)[1].strip()
        if app == "seerr":
            return Api(base, prefix="/api/v1").get("/status").get("version")
        return "reachable"
    except ApiError as e:
        raise RuntimeError(str(e.body)[:160] or f"HTTP {e.status}") from None


def preview(cfg, log=lambda m: None):
    """Run the setup for the person's own apps as a dry run and describe every setting it would change."""
    adopt, missing = prepare(cfg)
    cfg = {**cfg, "adopt": adopt}
    if missing:
        return {"ok": False, "missing": missing, "groups": []}
    connect(adopt)
    ctx = C.Ctx(cfg, log)
    rec = Recorder("audit")
    REC["r"] = rec
    problems = []
    try:
        steps = [("qbittorrent", C.setup_qbittorrent), ("sonarr", C.setup_sonarr), ("radarr", C.setup_radarr),
                 ("prowlarr", C.setup_prowlarr), ("jellyfin", C.setup_jellyfin), ("seerr", C.setup_seerr), ("bazarr", C.setup_bazarr)]
        for app, fn in steps:
            if app not in adopt:
                continue
            try:
                log(f"Looking at {KNOWN[app][0]}...")
                fn(ctx)
            except Exception as e:  # noqa: BLE001 - one app that cannot be read must not hide the others
                traceback.print_exc()
                detail = str(getattr(e, "body", "") or e) or type(e).__name__
                problems.append(f"{KNOWN[app][0]}: {detail[:140]}")
        if C.notify_on(cfg):
            try:
                C.setup_notifications(ctx, send_test=False)
            except Exception as e:  # noqa: BLE001
                problems.append(f"Notifications: {str(getattr(e, 'body', e))[:140]}")
    finally:
        REC["r"] = None
    groups = audit.report(rec, wanted=set(adopt) | {"notifications"})
    if "jellyfin" in adopt and C.livetv_on(cfg):         # building the channel list tests hundreds of streams, so a preview only says what it would add
        m = audit.GROUPS["livetv.setup"]
        groups.append({"id": "livetv.setup", "app": m[0], "title": m[1], "why": m[2], "default": m[3], "caution": m[4], "same": False,
                       "summary": "a tuner and program guides to add", "depends": [],
                       "changes": [{"kind": "create", "what": "Live TV tuner (M3U) and guides", "rows": [], "more": 0}]})
    return {"ok": True, "missing": [], "problems": problems, "groups": groups}


def apply_skips(groups_off):
    """The groups the person switched off, plus the groups that only make sense together with them."""
    off = set(groups_off or [])
    for gid, deps in audit.DEPENDS.items():
        if any(d in off for d in deps):
            off.add(gid)
    return off
