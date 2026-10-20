"""Setup wizard web server (stdlib only). Serves the GUI and a small JSON API."""
import json
import os
import socket
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import adopt as A
import configure as C
import sharing
import stack as S
import tailscale_https as TS
from arrapi import CANCEL, REC, Api, ApiError, Fatal, Recorder

STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
GUIDE_ORDER = ["Installing", "Other hardware", "Best settings", "Getting started", "How everything fits", "What it sets up", "File sharing", "Private HTTPS", "Portainer", "Comics and manga", "Live TV and VPN", "How Live TV works", "Fixing problems", "FAQ", "How it works", "Demo website"]


def docs_list():
    """The guide pages shown on the website, in reading order: [{"name", "file"}]."""
    try:
        files = [f[:-3] for f in os.listdir(DOCS) if f.endswith(".md")]
    except OSError:
        return []
    files.sort(key=lambda n: (GUIDE_ORDER.index(n) if n in GUIDE_ORDER else 99, n))
    return [{"name": n, "file": n + ".md"} for n in files]
STATE_FILE = f"{S.STACK}/arr-wizard-state.json"
LOCK = threading.Lock()
JOB = {"running": False, "events": [], "done": False, "error": None, "result": None}
PREVIEW = {"running": False, "done": False, "result": None, "error": None, "log": []}


# ------------------------------------------------------------------ state
def load_state():
    try:
        return json.load(open(STATE_FILE))
    except (OSError, ValueError):
        return None


def save_state(st):
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, indent=2)
    os.chmod(STATE_FILE, 0o600)


def log(msg, kind="info"):
    with LOCK:
        JOB["events"].append({"t": time.time(), "kind": kind, "msg": msg})
    print(msg, flush=True)


def step(name):
    if CANCEL.is_set():
        raise Fatal("Stopped")
    log(name, "step")


# ------------------------------------------------------------------ install
REGIONAL_PACKS = {"tamil", "malayalam", "telugu", "kannada", "hindi"}


def normalize(cfg):
    cfg.setdefault("kinds", ["tv", "movies"])
    cfg.setdefault("packs", ["english"])
    cfg["settings"] = {**C.DEFAULT_SETTINGS, **(cfg.get("settings") or {})}
    cfg["regional"] = bool(REGIONAL_PACKS & set(cfg["packs"]))
    sv = cfg.setdefault("services", {})
    if sv.pop("mylar3", None):      # Mylar3 was replaced by Kapowarr
        sv["kapowarr"] = True
    if "mylar3" in cfg.get("ports", {}):
        cfg["ports"].setdefault("kapowarr", S.DEFAULT_PORTS["kapowarr"])
        cfg["ports"].pop("mylar3")
    for k in ("kapowarr", "kaizoku"):
        cfg.setdefault("ports", {}).setdefault(k, S.DEFAULT_PORTS[k])
    cfg.setdefault("livetv", None)
    cfg.setdefault("notify", None)
    cfg["profiles"] = C.profiles_of(cfg)
    return cfg


def validate(cfg):
    errs = []
    st = cfg.get("storage") or {}
    if st.get("mode") == "single":
        if not st.get("base"):
            errs.append("Choose a media folder.")
    else:
        if not st.get("downloads"):
            errs.append("Choose a downloads folder.")
        have = {l["type"] for l in st.get("libraries", []) if l.get("path")}
        pf = C.prefs(cfg)
        for kind, label, need in (("movies", "Movies", "movies" in cfg.get("kinds", [])),
                                  ("tv", "TV Shows", "tv" in cfg.get("kinds", [])), ("anime", "Anime", pf["anime"])):
            if need and kind not in have and not (kind == "movies" and "anime" in have and pf["anime"]):
                errs.append(f"Add a {label} folder.")
    if "qbittorrent" not in (cfg.get("adopt") or {}) and not (cfg.get("qbit", {}).get("username") and cfg["qbit"].get("password")):
        errs.append("Choose a qBittorrent username and password.")
    for p in cfg.get("profiles") or []:
        if not p.get("name"):
            errs.append("Every profile needs a name.")
    if len(cfg.get("login", {}).get("password", "")) < 4:
        errs.append("Choose an admin password (4+ characters).")
    ports = list(cfg["ports"].values())
    if len(set(ports)) != len(ports):
        errs.append("Two services share the same port.")
    if cfg.get("services", {}).get("samba"):
        errs += sharing.check(cfg)
    return errs


def private_addresses(cfg):
    """Create a Tailscale HTTPS address for every app of this stack. Returns {app port on this computer: address}."""
    import argparse
    names = [n for n in S.sh(["docker", "ps", "--filter", f"label=com.docker.compose.project={S.PROJECT}", "--format", "{{.Names}}"],
                             check=False).stdout.split() if n]
    args = argparse.Namespace(apply=True, homepage=None, loop=None, skip=["regional"], extra=None, json=None, only=names,
                              from_container=True, state=f"{S.STACK}/tailscale-https.json")
    res = TS.run(args)
    if res.get("problem"):
        log("Private HTTPS addresses: " + res["problem"], "warn")
    made = {i["port"]: i["url"] for i in res.get("items", []) if i.get("url") and i["state"] in ("have", "added")}
    log(f"Private HTTPS addresses ready for {len(made)} apps")
    return made


def install(cfg):
    ctx = C.Ctx(cfg, log)
    CANCEL.clear()
    try:
        step("Preparing folders")
        normalize(cfg)
        plan = S.prepare_dirs(cfg)
        if "qbittorrent" not in (cfg.get("adopt") or {}):
            S.seed_qbittorrent(cfg, plan)
        cfg["gpu"] = cfg["services"].get("jellyfin") and S.has_gpu(cfg.get("hostOs"))
        mine = {}
        if cfg.get("adopt"):
            step("Reading the apps you already run")
            mine, missing = A.prepare(cfg)
            if missing:
                raise RuntimeError("Cannot use your own apps yet: " + "; ".join(missing))
            cfg["adopt"] = mine
            ctx.adopt = mine
            if "jellyfin" in mine:
                cfg["services"]["jellyfin"] = True
                ctx.cfg["services"]["jellyfin"] = True
        step("Writing your docker-compose file")
        if cfg["services"].get("kapowarr"):
            cfg["kapowarrImage"], fallback = S.pick_kapowarr_image()
            if fallback:
                log(f"  Kapowarr: Hikki-dev's copy cannot be downloaded right now, so the original Kapowarr ({cfg['kapowarrImage']}) is used. Everything else works the same.")
        S.write_compose(cfg)
        step("Downloading and starting the apps (first time takes a few minutes)")
        S.compose_cmd("up", "-d", "--remove-orphans")
        S.connect_network()
        if mine:
            A.connect(mine)
            REC["r"] = Recorder("apply", skip=A.apply_skips(cfg.get("skipGroups")))      # settings the person kept are left alone
        if cfg["services"].get("tailscale"):
            step("Making private HTTPS addresses with Tailscale")
            cfg["tailscaleUrls"] = private_addresses(cfg)
            ctx.cfg["tailscaleUrls"] = cfg["tailscaleUrls"]
        step("Configuring qBittorrent (no seeding)")
        C.setup_qbittorrent(ctx)
        step("Configuring Sonarr and Radarr")
        C.setup_sonarr(ctx)
        C.setup_radarr(ctx)
        if cfg["services"].get("bazarr"):
            step("Configuring Bazarr (subtitles)")
            C.setup_bazarr(ctx)
        if cfg["services"].get("kapowarr"):
            step("Configuring Kapowarr (comics)")
            try:
                C.setup_kapowarr(ctx)
            except Exception as e:  # noqa: BLE001 - optional extra: report, never fail the whole install
                log(f"  Kapowarr could not be finished: {str(getattr(e, 'body', e))[:160]}")
        step("Configuring Prowlarr (finding and testing indexers)")
        C.setup_prowlarr(ctx)
        if cfg["services"].get("jellyfin"):
            step("Configuring Jellyfin")
            C.setup_jellyfin(ctx)
            if C.livetv_on(cfg):
                step("Setting up Live TV and sports")
                try:
                    C.setup_livetv(ctx)
                except Exception as e:  # noqa: BLE001 - optional extra: report, never fail the whole install
                    log(f"  Live TV could not be finished: {str(getattr(e, 'body', e))[:160]}. You can retry it from the Live TV tab.")
            if cfg["services"].get("seerr"):
                step("Configuring Seerr (requests)")
                C.setup_seerr(ctx)
        if C.notify_on(cfg):
            step("Setting up notifications")
            rep = C.setup_notifications(ctx)
            if rep["problems"]:
                log("  Notifications: " + "; ".join(rep["problems"])[:300])
        step("Checking every connection")
        links = C.verify_integrations(ctx)
        badl = [x["name"] for x in links if not x["ok"]]
        fixed = [x["name"] for x in links if x["fixed"]]
        log(("Every connection verified" if not badl else "Needs attention: " + ", ".join(badl))
            + (f" (repaired automatically: {', '.join(fixed)})" if fixed else ""))
        step("Checking every login")
        creds = C.verify_logins(ctx)
        bad = [x["app"] for x in creds if not x["ok"]]
        log("Every login verified" if not bad else "Could not verify a login for: " + ", ".join(bad))
        step("Testing a real search")
        smoke = smoke_test(ctx)
        log(smoke["msg"])
        if cfg["services"].get("homepage"):
            step("Building your Homepage dashboard")
            C.setup_homepage(ctx)
            S.compose_cmd("restart", "homepage")
        st = {"cfg": cfg, "keys": ctx.keys, "installedAt": time.time(), "plan": plan, "credentials": creds, "integrations": links,
              "profiles": {"sonarr": ctx.profiles_sonarr, "radarr": ctx.profiles_radarr},
              "routes": C.routes_of(ctx),
              "indexers": getattr(ctx, "indexers", {})}
        save_state(st)
        JOB["result"] = {**summary(st), "smoke": smoke, "credentials": creds, "integrations": links}
        step("All done")
        JOB["done"] = True
    except Fatal as e:
        JOB["error"] = "stopped"
        log("Stopped. Nothing is lost. You can start again any time." if str(e) == "Stopped" else str(e), "stopped")
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        JOB["error"] = str(e)[-900:]
        log(f"Something went wrong: {str(e)[-300:]}", "error")
    finally:
        REC["r"] = None
        JOB["running"] = False


def smoke_test(ctx):
    """Search real indexers for an open-licensed film (Sintel) without downloading it, then remove it again."""
    if ctx.adopt and (C.group_off("radarr.profiles") or C.group_off("radarr.roots") or C.group_off("prowlarr.indexers")):
        return {"ok": True, "msg": "Test search skipped: you kept your own Radarr profiles, folders or indexers, so the sample film is not added to your Radarr."}
    try:
        r = ctx.apis["radarr"]
        movies = libs_movie_root(ctx)
        lookup = r.get("/movie/lookup", params={"term": "Sintel 2010"}, timeout=180)
        item = next((m for m in lookup if m.get("year") == 2010 and "sintel" in m["title"].lower()), None)
        if not item or not movies:
            return {"ok": False, "msg": "Test search skipped: test title not found."}
        pid = ctx.profiles_radarr[C.routes_of(ctx)["default"]]
        body = {**item, "qualityProfileId": pid, "monitored": False, "rootFolderPath": movies,
                "minimumAvailability": "released", "addOptions": {"searchForMovie": False}}
        added = r.post("/movie", body)
        try:
            rel = r.get("/release", params={"movieId": added["id"]}, timeout=240)
        finally:
            r.delete(f"/movie/{added['id']}", params={"deleteFiles": "false"})
        ok = [x for x in rel if x.get("approved")]
        if rel:
            tail = "" if ok else " None fit the default profile's quality or size rules (normal when a profile is strict, such as 4K only), so nothing would download for this sample."
            return {"ok": True, "msg": f"Test search found {len(rel)} releases for a sample film; {len(ok)} match your rules. Indexers are working.{tail}"}
        return {"ok": False, "msg": "Test search returned nothing. Indexers may still be warming up; use Find a title to retry."}
    except Exception as e:  # noqa: BLE001 - never fail the install because of the self-test
        return {"ok": False, "msg": f"Test search could not run ({str(e)[:100]})."}


def libs_movie_root(ctx):
    libs = S.libs_of(ctx.plan, "movies") or S.libs_of(ctx.plan, "anime")
    return libs[0]["path"] if libs else None


def summary(st):
    cfg = st["cfg"]
    host = cfg.get("hostAddress") or "localhost"
    ts = {int(k): v for k, v in (cfg.get("tailscaleUrls") or {}).items()}
    links = [{"name": n, "url": ts.get(p) or f"http://{host}:{p}"} for n, p in cfg["ports"].items()
             if n in ("homepage", "jellyfin", "seerr", "sonarr", "radarr", "prowlarr", "bazarr", "qbittorrent")
             and (n in ("sonarr", "radarr", "prowlarr", "qbittorrent") or cfg["services"].get(n))]
    out = {"links": links, "indexers": st.get("indexers", {}),
           "login": cfg["login"]["username"], "qbit": cfg["qbit"]["username"]}
    if cfg.get("services", {}).get("samba"):
        out["sharing"] = {"user": cfg["samba"]["user"], "port": cfg["ports"].get("samba", 445),
                          "shares": sharing.addresses(host, sharing.shares_of(cfg))}
    return out


# ------------------------------------------------------------------ re-tune (after install)
class respecting_choices:
    """While active, the person's own apps are written to only where they allowed it (the groups they switched off are left alone)."""

    def __init__(self, cfg):
        self.cfg = cfg

    def __enter__(self):
        if self.cfg.get("adopt"):
            A.connect(self.cfg["adopt"])
            REC["r"] = Recorder("apply", skip=A.apply_skips(self.cfg.get("skipGroups")))
        return self

    def __exit__(self, *a):
        REC["r"] = None


def retune(patch):
    st = load_state()
    if not st:
        raise RuntimeError("Nothing installed yet.")
    cfg = st["cfg"]
    for k in ("quality", "packs", "animeAudio", "subtitleLangs", "profiles"):
        if k in patch:
            cfg[k] = patch[k]
    if "settings" in patch:
        cfg["settings"] = {**cfg.get("settings", {}), **patch["settings"]}
    normalize(cfg)
    ctx = C.Ctx(cfg, log)
    ctx.keys = st["keys"]
    S.connect_network()
    with respecting_choices(cfg):
        return _retune(ctx, cfg, st)


def _retune(ctx, cfg, st):
    for app, port, ver in (("sonarr", 8989, "v3"), ("radarr", 7878, "v3"), ("prowlarr", 9696, "v1")):
        ctx.apis[app] = Api(ctx.host_url(app), st["keys"][app], prefix=f"/api/{ver}")
    log("Applying size limits and download rules")
    profs = C.profiles_of(cfg)
    for app in ("sonarr", "radarr"):
        with C.grp(f"{app}.sizes"):
            C.apply_sizes(ctx.apis[app], app, profs)
        C.common_settings(ctx.apis[app], app, cfg["quality"], ctx)
    C.apply_qbit_prefs(ctx, C.qbit_api(ctx))
    with C.grp("prowlarr.indexers"):
        C.apply_min_seeders(ctx)
    log("Rebuilding quality profiles")
    ctx.profiles_sonarr = C.build_all_profiles(ctx, ctx.apis["sonarr"], "sonarr")
    ctx.profiles_radarr = C.build_all_profiles(ctx, ctx.apis["radarr"], "radarr")
    st["profiles"] = {"sonarr": ctx.profiles_sonarr, "radarr": ctx.profiles_radarr}
    st["routes"] = C.routes_of(ctx)
    try:
        ctx.apis["sonarr"].get("/system/status")
        seerr_ok = "seerr" in [x["service"] for x in S.container_state()]
        if seerr_ok:
            C.setup_seerr(ctx)
    except Exception as e:  # noqa: BLE001 - profile routing in Seerr is best effort on a live system
        log(f"Could not update Seerr routing ({str(e)[:80]})")
    save_state(st)
    return {"ok": True}


# ------------------------------------------------------------------ notifications
def apply_notify(sel):
    st = load_state()
    if not st:
        raise RuntimeError("Nothing installed yet.")
    cfg = st["cfg"]
    prev = cfg.get("notify") or {}
    cfg["notify"] = {**sel, "seerrAgent": prev.get("seerrAgent"), "bazarrProvider": prev.get("bazarrProvider")}
    ctx = C.Ctx(cfg, log)
    ctx.keys = st["keys"]
    S.connect_network()
    for app, port, ver in (("sonarr", 8989, "v3"), ("radarr", 7878, "v3"), ("prowlarr", 9696, "v1")):
        ctx.apis[app] = Api(ctx.host_url(app), st["keys"][app], prefix=f"/api/{ver}")
    with respecting_choices(cfg):
        rep = C.setup_notifications(ctx)
    save_state(st)
    return rep


# ------------------------------------------------------------------ live TV and sports
LT = {"running": False, "msg": "", "error": None, "stats": None}


def apply_livetv(sel):
    st = load_state()
    if not st or not st["cfg"]["services"].get("jellyfin"):
        raise RuntimeError("Jellyfin is not installed.")
    cfg = st["cfg"]
    cfg["livetv"] = sel
    ctx = C.Ctx(cfg, lambda m, kind="info": LT.update(msg=m.strip()))
    ctx.keys = st["keys"]
    os.makedirs(f"{S.STACK}/config/jellyfin/livetv", exist_ok=True)
    S.write_compose(cfg)
    S.compose_cmd("up", "-d", "--remove-orphans")
    S.connect_network()
    if sel.get("enabled"):
        stats = C.setup_livetv(ctx)
    else:
        C.disable_livetv(ctx)
        stats = None
    save_state(st)
    return stats


def livetv_job(sel):
    LT.update(running=True, msg="Starting...", error=None, stats=None)
    try:
        LT["stats"] = apply_livetv(sel)
        LT["msg"] = "Done"
    except Exception as e:  # noqa: BLE001
        LT["error"] = str(getattr(e, "body", e))[:300]
    finally:
        LT["running"] = False


# ------------------------------------------------------------------ request doctor
def apis():
    st = load_state()
    if not st:
        raise RuntimeError("Run the setup first.")
    S.connect_network()
    return st, {a: Api(f"http://{a}:{S.INTERNAL[a]}", st["keys"][a], prefix="/api/v3") for a in ("sonarr", "radarr")}


def lookup(kind, term):
    st, a = apis()
    if kind == "tv":
        res = a["sonarr"].get("/series/lookup", params={"term": term}, timeout=60)
        return [{"id": r.get("tvdbId"), "title": r["title"], "year": r.get("year"), "overview": (r.get("overview") or "")[:240],
                 "poster": next((i["remoteUrl"] for i in r.get("images", []) if i["coverType"] == "poster"), None),
                 "lang": (r.get("originalLanguage") or {}).get("name"), "inLibrary": bool(r.get("id")),
                 "raw": r} for r in res[:12]]
    res = a["radarr"].get("/movie/lookup", params={"term": term}, timeout=60)
    return [{"id": r.get("tmdbId"), "title": r["title"], "year": r.get("year"), "overview": (r.get("overview") or "")[:240],
             "poster": next((i["remoteUrl"] for i in r.get("images", []) if i["coverType"] == "poster"), None),
             "lang": (r.get("originalLanguage") or {}).get("name"), "inLibrary": bool(r.get("id")),
             "raw": r} for r in res[:12]]


def root_for(st, api, kind):
    """The library folder of this kind with the most free space."""
    plan = st["plan"]
    mine = {l["path"] for l in S.libs_of(plan, kind)} or {l["path"] for l in S.libs_of(plan, "anime")} \
        or {l["path"] for l in S.libs_of(plan, "tv")}
    roots = [r for r in api.get("/rootfolder") if r["path"] in mine]
    return max(roots, key=lambda r: r.get("freeSpace") or 0)["path"] if roots else next(iter(mine))


def pick_profile(st, app, raw, anime):
    """Profile id for a title: anime first, then by original language, else the default profile."""
    rt, ids = st["routes"], st["profiles"][app]
    lang = ((raw.get("originalLanguage") or {}).get("name") or "").lower()
    pid = (rt["anime"] if anime and rt["anime"] else None) or rt["langs"].get(lang) or rt["default"]
    return ids[pid]


def add_title(kind, raw):
    st, a = apis()
    jp_anim = "Animation" in raw.get("genres", []) and (raw.get("originalLanguage") or {}).get("name") == "Japanese"
    if kind == "tv":
        anime = (raw.get("seriesType") == "anime") or jp_anim
        body = {**raw, "qualityProfileId": pick_profile(st, "sonarr", raw, anime), "monitored": True,
                "seasonFolder": True, "seriesType": "anime" if anime else raw.get("seriesType", "standard"),
                "rootFolderPath": root_for(st, a["sonarr"], "anime" if anime else "tv"),
                "addOptions": {"monitor": "all", "searchForMissingEpisodes": True, "searchForCutoffUnmetEpisodes": False}}
        r = a["sonarr"].post("/series", body)
        return {"id": r["id"], "kind": kind, "title": r["title"]}
    body = {**raw, "qualityProfileId": pick_profile(st, "radarr", raw, jp_anim), "monitored": True,
            "rootFolderPath": root_for(st, a["radarr"], "movies"), "minimumAvailability": "released",
            "addOptions": {"searchForMovie": True}}
    r = a["radarr"].post("/movie", body)
    return {"id": r["id"], "kind": kind, "title": r["title"]}


def diagnose(kind, item_id):
    """Run an interactive search and explain, in plain words, what was found and why releases were rejected."""
    st, a = apis()
    if kind == "tv":
        api = a["sonarr"]
        eps = api.get("/episode", params={"seriesId": item_id})
        aired = [e for e in eps if e.get("airDateUtc") and e["airDateUtc"] < time.strftime("%Y-%m-%dT%H:%M:%SZ")
                 and e["seasonNumber"] > 0]
        if not aired:
            return {"verdict": "notyet", "message": "No episodes have aired yet - nothing to download until they do.", "releases": []}
        target = sorted(aired, key=lambda e: (e["seasonNumber"], e["episodeNumber"]))[0]
        rel = api.get("/release", params={"episodeId": target["id"]}, timeout=180)
        label = f"S{target['seasonNumber']:02d}E{target['episodeNumber']:02d}"
        cap = st["cfg"]["quality"]["episodeCapMB"]
    else:
        api = a["radarr"]
        mv = api.get(f"/movie/{item_id}")
        if not mv.get("isAvailable"):
            return {"verdict": "notyet", "message": "This movie is not released yet - it will download once it is out.", "releases": []}
        rel = api.get("/release", params={"movieId": item_id}, timeout=180)
        label = mv["title"]
        cap = st["cfg"]["quality"]["movieCapGB"] * 1024
    out = []
    for r in rel:
        out.append({"title": r["title"], "indexer": r.get("indexer"), "sizeMB": round(r["size"] / 1048576),
                    "seeders": r.get("seeders"), "quality": (r.get("quality") or {}).get("quality", {}).get("name"),
                    "approved": r.get("approved", False), "rejections": r.get("rejections", []),
                    "guid": r["guid"], "indexerId": r["indexerId"],
                    "languages": [l["name"] for l in r.get("languages", [])]})
    out.sort(key=lambda x: (not x["approved"], -(x["seeders"] or 0)))
    approved = [r for r in out if r["approved"]]
    reasons = {}
    for r in out:
        for rj in r["rejections"]:
            key = "too big" if ("larger than" in rj.lower() or "maximum size" in rj.lower()) else \
                  "too small" if "smaller than" in rj.lower() else \
                  "quality not allowed" if "quality" in rj.lower() and "not wanted" in rj.lower() else \
                  "language" if "language" in rj.lower() else \
                  "no seeders" if "seeder" in rj.lower() else rj[:70]
            reasons[key] = reasons.get(key, 0) + 1
    if not out:
        verdict, msg = "none", ("No indexer returned anything for this title. Try an alternative name, or add more "
                                "indexers in Prowlarr. (Brand-new or very obscure titles may not be shared yet.)")
    elif approved:
        verdict, msg = "ok", f"Found {len(out)} releases for {label}; {len(approved)} match your rules. The best one is being downloaded automatically."
    else:
        top = max(reasons, key=reasons.get)
        msg = (f"Found {len(out)} releases for {label} but none matched your rules. Most common reason: {top}. "
               "You can download the best one anyway, or loosen the rule below.")
        verdict = "rejected"
    return {"verdict": verdict, "message": msg, "releases": out[:25], "reasons": reasons, "capMB": cap, "label": label}


def grab(kind, guid, indexer_id):
    st, a = apis()
    api = a["sonarr" if kind == "tv" else "radarr"]
    api.post("/release", {"guid": guid, "indexerId": indexer_id}, timeout=60)
    return {"ok": True}


# ------------------------------------------------------------------ http
def run_preview(cfg):
    """Read the person's own apps and describe what the setup would change, in the background (it can take a minute)."""
    PREVIEW.update(running=True, done=False, result=None, error=None, log=[])
    try:
        normalize(cfg)
        S.connect_network()
        res = A.preview(cfg, log=lambda m: PREVIEW["log"].append(m))
        PREVIEW["result"] = res
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        PREVIEW["error"] = str(getattr(e, "body", e))[:300]
    finally:
        REC["r"] = None
        PREVIEW.update(running=False, done=True)


def port_free(port):
    s = socket.socket()
    s.settimeout(0.4)
    try:
        return s.connect_ex(("host.docker.internal", port)) != 0
    except OSError:
        return True
    finally:
        s.close()


def tailscale_info():
    """Whether private HTTPS addresses can be made: Tailscale must be reachable from here and signed in."""
    if os.environ.get("HOST_TAILSCALE") != "1":
        return {"ready": False, "problem": "The setup was not started with access to Tailscale. Install Tailscale on this computer, then start the setup again."}
    dns, problem = TS.tailscale_state()
    return {"ready": not problem, "dns": dns, "problem": problem}


def env_info():
    docker_ok = True
    try:
        v = S.sh(["docker", "version", "--format", "{{.Server.Version}}"], check=False).stdout.strip()
        docker_ok = bool(v)
    except Exception:  # noqa: BLE001
        v, docker_ok = "", False
    ports = {k: (S.DEFAULT_PORTS[k], port_free(S.DEFAULT_PORTS[k])) for k in S.DEFAULT_PORTS}
    try:   # what the Docker engine can actually use (matters on a laptop, where Docker has its own memory limit)
        mem, cpus = S.sh(["docker", "info", "--format", "{{.MemTotal}} {{.NCPU}}"], check=False).stdout.split()
        mem_gb, ncpu = round(int(mem) / 1073741824, 1), int(cpus)
    except Exception:  # noqa: BLE001
        mem_gb, ncpu = None, None
    return {"docker": docker_ok, "dockerVersion": v, "memGB": mem_gb, "cpus": ncpu, "hostOs": os.environ.get("HOST_OS", "linux"),
            "hostHome": os.environ.get("HOST_HOME", ""), "uid": int(os.environ.get("HOST_UID", 1000)),
            "gid": int(os.environ.get("HOST_GID", 1000)), "stackPath": S.HOST_STACK,
            "defaultMedia": os.environ.get("HOST_DEFAULT_MEDIA", ""),
            "ports": {k: {"port": p, "free": f} for k, (p, f) in ports.items()},
            "packs": C.PACKS,
            "hostAddress": os.environ.get("HOST_ADDRESS", ""), "tailscale": tailscale_info()}


MIME = {".html": "text/html", ".css": "text/css", ".js": "application/javascript", ".svg": "image/svg+xml",
        ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".md": "text/markdown; charset=utf-8"}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        try:
            if u.path == "/api/env":
                return self.send(200, env_info())
            if u.path == "/api/state":
                st = load_state()
                return self.send(200, {"installed": bool(st), "running": JOB["running"], "jobCfg": JOB.get("cfg") if JOB["running"] else None,
                                       "summary": summary(st) if st else None, "cfgFull": ({k: st["cfg"][k] for k in ("kinds", "packs", "animeAudio", "subtitleLangs", "storage", "quality", "settings", "services", "qbit", "ports", "profiles")} if st else None),
                                       "cfg": ({k: st["cfg"][k] for k in ("quality", "packs", "animeAudio", "subtitleLangs", "settings", "profiles")} if st else None),
                                       "containers": S.container_state() if st else []})
            if u.path == "/api/events":
                since = int(q.get("since", ["0"])[0])
                with LOCK:
                    ev = JOB["events"][since:]
                return self.send(200, {"events": ev, "next": since + len(ev), "running": JOB["running"],
                                       "done": JOB["done"], "error": JOB["error"], "result": JOB["result"]})
            ids = (str(os.environ.get("HOST_UID", 1000)), str(os.environ.get("HOST_GID", 1000)))
            hos = os.environ.get("HOST_OS", "linux")
            if u.path == "/api/drives":
                return self.send(200, S.list_drives(hos, os.environ.get("HOST_HOME", "")))
            if u.path == "/api/browse":
                p = q["path"][0]
                if not S.folder_exists(p, hos):
                    return self.send(404, {"error": "That folder does not exist."})
                info = S.inspect_path(p, ids)
                info["parent"] = S.parent_of(p, hos)
                info["segments"] = S._segments(p)
                return self.send(200, info)
            if u.path == "/api/pathcheck":
                return self.send(200, S.check_path(q["path"][0], hos, ids))
            if u.path == "/api/livetv/catalog":
                import livetv
                return self.send(200, livetv.catalog(f"{S.STACK}/config/regional"))
            if u.path == "/api/livetv/status":
                import urllib.request as ur
                st = load_state() or {}
                bridge = {}
                try:
                    S.connect_network()
                    bridge = json.loads(ur.urlopen("http://regional:9120/livetv/status", timeout=6).read())
                except Exception:  # noqa: BLE001 - adapter not running
                    pass
                return self.send(200, {"job": LT, "selection": st.get("cfg", {}).get("livetv"), "daily": bridge,
                                       "installed": bool(st), "jellyfin": bool(st.get("cfg", {}).get("services", {}).get("jellyfin"))})
            if u.path == "/api/regional":
                S.connect_network()
                import urllib.request as ur
                try:
                    return self.send(200, json.loads(ur.urlopen("http://regional:9120/status", timeout=8).read()))
                except Exception:  # noqa: BLE001 - adapter not installed or still starting
                    return self.send(200, {})
            if u.path == "/api/detect":
                found = A.detect()
                return self.send(200, {"apps": found, "known": {k: v[0] for k, v in A.KNOWN.items()}, "needs": A.NEEDS,
                                       "groups": {k: {"app": v[0], "title": v[1]} for k, v in __import__("audit").GROUPS.items()}})
            if u.path == "/api/preview/status":
                return self.send(200, {k: PREVIEW[k] for k in ("running", "done", "result", "error", "log")})
            if u.path == "/api/integrations":
                return self.send(200, (load_state() or {}).get("integrations", []))
            if u.path == "/api/credentials":
                st = load_state()
                return self.send(200, (st or {}).get("credentials", []))
            if u.path == "/api/storage":
                st = load_state()
                if not st:
                    return self.send(404, {"error": "Not installed."})
                plan = st["plan"]
                libs = []
                for l in plan["libs"]:
                    i = S.inspect_path(l["host"], ids)
                    libs.append({**l, **{k: i.get(k) for k in ("totalBytes", "usedBytes", "freeBytes")}})
                return self.send(200, {"downloadsHost": plan["downloadsHost"], "libs": libs})
            if u.path == "/api/lookup":
                r = lookup(q["kind"][0], q["term"][0])
                return self.send(200, r)
            if u.path == "/api/diagnose":
                return self.send(200, diagnose(q["kind"][0], int(q["id"][0])))
            if u.path == "/guide":
                u = urllib.parse.urlparse("/guide.html")
            if u.path == "/api/docs":
                return self.send(200, docs_list())
            if u.path.startswith("/docs/"):
                rel = urllib.parse.unquote(u.path[len("/docs/"):])
                fp = os.path.normpath(os.path.join(DOCS, rel))
                if not fp.startswith(DOCS + os.sep) or not os.path.isfile(fp):
                    return self.send(404, {"error": "No such page."})
                return self.send(200, open(fp, "rb").read(), MIME.get(os.path.splitext(fp)[1].lower(), "application/octet-stream"))
            path = "/index.html" if u.path == "/" else u.path
            fp = os.path.normpath(os.path.join(STATIC, path.lstrip("/")))
            if not fp.startswith(STATIC) or not os.path.isfile(fp):
                return self.send(404, {"error": "not found"})
            return self.send(200, open(fp, "rb").read(), MIME.get(os.path.splitext(fp)[1], "application/octet-stream"))
        except ApiError as e:
            self.send(502, {"error": f"{e.status}: {str(e.body)[:300]}"})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.send(500, {"error": str(e)[:300]})

    def do_POST(self):
        try:
            b = self.body()
            if self.path == "/api/install":
                errs = validate(b)
                if errs:
                    return self.send(400, {"errors": errs})
                with LOCK:
                    if JOB["running"]:
                        return self.send(409, {"errors": ["Install already running."]})
                    JOB.update(running=True, events=[], done=False, error=None, result=None, cfg=b)
                threading.Thread(target=install, args=(b,), daemon=True).start()
                return self.send(200, {"started": True})
            if self.path == "/api/adopt/check":
                try:
                    app = b["app"]
                    entry, miss = A.prepare({"adopt": {app: b}})
                    if miss:
                        return self.send(200, {"ok": False, "detail": miss[0]})
                    S.connect_network()
                    A.connect(entry)
                    return self.send(200, {"ok": True, "version": A.check_connection(app, entry[app]), "key": bool(entry[app].get("key"))})
                except Exception as e:  # noqa: BLE001
                    return self.send(200, {"ok": False, "detail": str(e)[:200]})
            if self.path == "/api/preview":
                with LOCK:
                    if PREVIEW["running"]:
                        return self.send(409, {"errors": ["A preview is already running."]})
                    PREVIEW.update(running=True, done=False, result=None, error=None, log=[])
                threading.Thread(target=run_preview, args=(b,), daemon=True).start()
                return self.send(200, {"started": True})
            if self.path == "/api/integrations/check":
                st = load_state()
                if not st:
                    return self.send(400, {"errors": ["Not installed."]})
                S.connect_network()
                ctx = C.Ctx(st["cfg"], log)
                ctx.keys = st["keys"]
                for app, ver in (("sonarr", "v3"), ("radarr", "v3"), ("prowlarr", "v1")):
                    ctx.apis[app] = Api(ctx.host_url(app), st["keys"][app], prefix=f"/api/{ver}")
                ctx.profiles_sonarr, ctx.profiles_radarr = st["profiles"]["sonarr"], st["profiles"]["radarr"]
                res = C.verify_integrations(ctx)
                st["integrations"] = res
                save_state(st)
                return self.send(200, res)
            if self.path == "/api/regional/discover":
                import urllib.request as ur
                S.connect_network()
                res = json.loads(ur.urlopen(f"http://regional:9120/discover/{b['site']}", timeout=120).read())
                st = load_state()
                if res.get("address") and st:
                    try:
                        api = Api("http://prowlarr:9696", st["keys"]["prowlarr"], prefix="/api/v1")
                        C.ensure_adapter_indexers(api, st["cfg"], api.get("/indexer/schema"), {i["name"].lower() for i in api.get("/indexer")}, log)
                    except Exception:  # noqa: BLE001
                        pass
                return self.send(200, res)
            if self.path == "/api/mkdir":
                ids = f"{os.environ.get('HOST_UID', 1000)}:{os.environ.get('HOST_GID', 1000)}"
                return self.send(200, {"path": S.make_folder(b["parent"], b["name"], ids)})
            if self.path == "/api/samba/suggest":
                hos = os.environ.get("HOST_OS", "linux")
                try:
                    mounts = S.plan_storage({"storage": b.get("storage") or {}, "hostOs": hos})["mounts"]
                except (KeyError, TypeError, IndexError):
                    mounts = []         # the storage answers are not complete yet: offer the drives only
                drives = S.list_drives(hos, os.environ.get("HOST_HOME", "")).get("drives", [])
                try:       # the real drives of this computer, so ordinary folders and links are not offered as drives
                    table = sharing.parse_mounts(S.sh(["docker", "run", "--rm", "--pid=host", S.HELPER_IMAGE, "cat", "/proc/1/mounts"], timeout=60, check=False).stdout)
                except Exception:  # noqa: BLE001 - without the list, every folder found is offered
                    table = None
                return self.send(200, {"shares": sharing.suggest(mounts, drives, table or None), "supported": hos == "linux"})
            if self.path == "/api/plan":
                return self.send(200, S.plan_storage({**b, "hostOs": os.environ.get("HOST_OS", "linux")}))
            if self.path == "/api/stop":
                CANCEL.set()
                S.kill_running()
                log("Stopping...", "info")
                return self.send(200, {"ok": True})
            if self.path == "/api/stack":
                act = b.get("action")
                CANCEL.clear()  # a finished Stop must not block later commands
                if JOB["running"]:
                    return self.send(409, {"errors": ["Stop the install first."]})
                if act == "reset":
                    if load_state():
                        return self.send(400, {"errors": ["Already installed - nothing to reset."]})
                    S.reset_fresh()
                elif act in ("stop", "start"):
                    S.compose_cmd(act)
                else:
                    return self.send(400, {"errors": ["Unknown action."]})
                return self.send(200, {"ok": True})
            if self.path == "/api/notify/apply":
                return self.send(200, apply_notify(b))
            if self.path == "/api/livetv/preview":
                import livetv
                return self.send(200, livetv.build(b, None, check=False, guides=False))
            if self.path == "/api/livetv/apply":
                if LT["running"]:
                    return self.send(409, {"error": "Already working on it."})
                threading.Thread(target=livetv_job, args=(b,), daemon=True).start()
                return self.send(200, {"started": True})
            if self.path == "/api/retune":
                return self.send(200, retune(b))
            if self.path == "/api/add":
                return self.send(200, add_title(b["kind"], b["raw"]))
            if self.path == "/api/grab":
                return self.send(200, grab(b["kind"], b["guid"], b["indexerId"]))
            self.send(404, {"error": "not found"})
        except ApiError as e:
            self.send(502, {"error": f"{e.status}: {str(e.body)[:300]}"})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self.send(500, {"error": str(e)[:300]})


def regional_watch():
    """Keep the adapter-backed Prowlarr sources in step with reality: add a source once its address has been found."""
    import urllib.request as ur
    while True:
        time.sleep(600)
        try:
            st = load_state()
            if not st or JOB["running"]:
                continue
            S.connect_network()
            api = Api("http://prowlarr:9696", st["keys"]["prowlarr"], prefix="/api/v1")
            status = json.loads(ur.urlopen("http://regional:9120/status", timeout=8).read())
            have = {i["name"].lower() for i in api.get("/indexer")}
            if any(x.get("online") for x in status.values()):
                C.ensure_adapter_indexers(api, st["cfg"], api.get("/indexer/schema"), have, log)
        except Exception as e:  # noqa: BLE001 - best effort, retried next cycle
            print("regional watch:", str(e)[:120], flush=True)


if __name__ == "__main__":
    threading.Thread(target=regional_watch, daemon=True).start()
    print("Arr Stack Setup wizard on :7979", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 7979), H).serve_forever()
