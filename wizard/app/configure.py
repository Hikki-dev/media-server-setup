"""Configures every app through its API. Every function is idempotent (find-by-name, then create or update)."""
import json
import time
import os
import re

from arrapi import Api, ApiError, Fatal, CANCEL, wait_for, REC
from stack import STACK, INTERNAL, PROJECT, plan_storage, libs_of
import livetv
import jellyfin_tune

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(HERE, "presets")

# What a person can tick. "anime" is its own pack; every other pack is an audio language.
PACKS = {
    "english": "English", "anime": "Anime", "korean": "Korean", "japanese": "Japanese", "tamil": "Tamil",
    "malayalam": "Malayalam", "hindi": "Hindi", "telugu": "Telugu", "kannada": "Kannada", "bengali": "Bengali",
    "marathi": "Marathi", "punjabi": "Punjabi", "sinhala": "Sinhala", "chinese": "Chinese", "spanish": "Spanish",
    "french": "French",
}
SUB_CODES = {"english": "en", "korean": "ko", "japanese": "ja", "tamil": "ta", "malayalam": "ml", "hindi": "hi",
             "telugu": "te", "kannada": "kn", "bengali": "bn", "marathi": "mr", "punjabi": "pa", "sinhala": "si",
             "chinese": "zh", "spanish": "es", "french": "fr"}

# Public indexers, best first. Only entries present in the running Prowlarr's schema are used, each one is tested,
# and unreachable ones are removed so searches never stall.
GENERAL_INDEXERS = ["1337x", "The Pirate Bay", "Knaben", "YTS", "EZTV", "TorrentsCSV", "LimeTorrents", "Uindex",
                    "kickasstorrents.ws", "kickasstorrents.to", "ExtraTorrent.st", "Torrent Downloads",
                    "TorrentDownload", "TorrentProject2", "showRSS", "Magnet Cat", "MagnetDownload", "DaMagNet"]
ANIME_INDEXERS = ["Nyaa.si", "Anime Tosho", "SubsPlease", "Anidex", "Tokyo Toshokan", "Shana Project",
                  "Bangumi Moe", "nekoBT", "AniSource"]
KOREAN_INDEXERS = ["Torrentsome", "Torrenttip"]
BEHIND_CLOUDFLARE = {"1337x", "eztv", "limetorrents", "uindex", "kickasstorrents.ws", "kickasstorrents.to",
                     "extratorrent.st", "torrent downloads", "torrentdownload", "torrentproject2", "magnet cat",
                     "magnetdownload", "damagnet", "torrentsome", "torrenttip", "anidex", "shana project"}

SOFT_PENALTY = {"LQ", "LQ (Release Title)", "No-RlsGroup", "Retags", "Bad Dual Groups", "Scene", "Asian LQ"}
TR = json.load(open(os.path.join(PRESETS, "trash.json")))


DEFAULT_SETTINGS = {"minSeeders": 2, "concurrent": 3, "dlLimitKB": 0, "ulLimitKB": 400, "rssMinutes": 30,
                    "retryFailed": True, "upgrade": False, "hardSubs": True}


def settings(cfg):
    return {**DEFAULT_SETTINGS, **(cfg.get("settings") or {})}


def prefs(cfg):
    """Normalised view of the person's choices."""
    packs = list(cfg.get("packs") or [])
    return {"tv": "tv" in cfg.get("kinds", ["tv", "movies"]), "movies": "movies" in cfg.get("kinds", ["tv", "movies"]),
            "anime": "anime" in packs, "packs": packs, "animeAudio": cfg.get("animeAudio", "sub"),
            "langs": [p for p in packs if p not in ("anime",)]}


class Ctx:
    def __init__(self, cfg, log):
        self.cfg, self.log = cfg, log
        self.plan = plan_storage(cfg)
        self.keys, self.apis = {}, {}
        self.adopt = cfg.get("adopt") or {}    # apps the person already runs: {app: {container, port, key, user, password}}

    def mine(self, name):
        return name in self.adopt

    def patience(self, name):
        """How long to wait for an app to answer: a freshly installed one is slow to start, the person's own is already running."""
        return 30 if name in self.adopt else 600

    def port(self, name):
        return int((self.adopt.get(name) or {}).get("port") or INTERNAL[name])

    def hostname(self, name):
        """How the other apps reach this one: its plain name on the shared network, or the machine's address for an app on the host network."""
        return (self.adopt.get(name) or {}).get("host") or ("solver" if name == "flaresolverr" else name)

    def host_url(self, name):
        # every app, new or the person's own, is reachable on the shared network under its plain name
        return f"http://{self.hostname(name)}:{self.port(name)}"

    def container(self, name):
        return (self.adopt.get(name) or {}).get("container") or f"{PROJECT}-{name}-1"

    def jf_login(self):
        """The Jellyfin admin to sign in as: the person's own when Jellyfin is theirs."""
        a = self.adopt.get("jellyfin") or {}
        if a.get("user"):
            return {"username": a["user"], "password": a.get("password", "")}
        return self.cfg["login"]


class _Group:
    """Marks a stretch of setup code as one settings group, so a preview can show it and the person can switch it off."""

    def __init__(self, gid):
        self.gid = gid

    def __enter__(self):
        r = REC["r"]
        if r:
            self.prev, r.group = r.group, self.gid
        return self

    def __exit__(self, *a):
        r = REC["r"]
        if r:
            r.group = self.prev


def grp(gid):
    return _Group(gid)


def group_off(gid):
    """True while this group is switched off (its writes are dropped); code with side effects outside the APIs checks it."""
    r = REC["r"]
    return bool(r and (r.mode == "audit" or gid in r.skip))


def read_key(app):
    path = f"{STACK}/config/{app}/config.xml"
    return wait_for(lambda: re.search(r"<ApiKey>([^<]+)</ApiKey>", open(path).read()).group(1), 600, 4, f"{app} config.xml")


def servarr(ctx, app, ver):
    key = (ctx.adopt.get(app) or {}).get("key") or read_key(app)
    api = Api(ctx.host_url(app), key, prefix=f"/api/{ver}")
    wait_for(lambda: api.get("/system/status"), ctx.patience(app), 4, app)
    ctx.keys[app], ctx.apis[app] = key, api
    return api


def upsert(api, path, items, name, body):
    for it in items:
        if it.get("name") == name or it.get("label") == name:
            body = {**body, "id": it["id"]}
            return api.put(f"{path}/{it['id']}", body)
    return api.post(path, body)


# ---------------------------------------------------------------- quality / size
QUALITY_GROUPS = {"2160": ["WEB 2160p", "Bluray-2160p", "HDTV-2160p"],
                  "1080": ["WEB 1080p", "Bluray-1080p", "HDTV-1080p"],
                  "720": ["WEB 720p", "Bluray-720p", "HDTV-720p"]}
RES_ORDER = ("2160", "1080", "720")      # best first; the first one a profile allows is its cutoff
ISO = {"english": "en", "korean": "ko", "japanese": "ja", "tamil": "ta", "malayalam": "ml", "hindi": "hi", "telugu": "te",
       "kannada": "kn", "bengali": "bn", "marathi": "mr", "punjabi": "pa", "sinhala": "si", "chinese": "zh",
       "spanish": "es", "french": "fr"}
# Release names that tell us English subtitles are included. Fansub groups ship them by default.
SUBS_RX = (r"(\be-?subs?\b|\beng(lish)?[ ._-]?(subs?|subtitles?|sub)\b|\bsubs?[ ._-]?eng(lish)?\b|\bmulti[ ._-]?subs?\b|"
           r"\bsubbed\b|\bhard[ ._-]?subs?\b|\bsoft[ ._-]?subs?\b|\bsubtitles?\b|\bsrt\b|subsplease|erai-raws|\bjudas\b|\bember\b|"
           r"\bvarg\b|\bsubsplus\b|\banime[ ._-]?time\b|\bcommie\b|\bhorriblesubs\b|\bnekomoe\b)")


# Files that are never video. qBittorrent skips them inside any torrent; releases that advertise them are refused in every profile.
UNSAFE_FILES = ["*.exe", "*.msi", "*.scr", "*.bat", "*.cmd", "*.com", "*.pif", "*.lnk", "*.url", "*.vbs", "*.vbe", "*.js", "*.jse",
                "*.wsf", "*.hta", "*.cpl", "*.reg", "*.ps1", "*.jar", "*.apk", "*.dmg", "*.pkg", "*.dll", "*.sys", "*.msp",
                "*.zipx", "*.7z.exe", "*readme*.txt.lnk", "*.torrent"]
SUSPICIOUS_RX = (r"\.(exe|msi|scr|bat|cmd|com|apk|dmg|pkg|jar|vbs|ps1|lnk|dll)\b|\b(keygen|patcher|activator)\b|"
                 r"\bcrack(ed)?[ ._-]?(by|only|fix)\b")
SAFETY_CF = "Suspicious release (executable or crack)"


def ensure_safety_cf(api):
    """A custom format that matches releases advertising executables or cracks; profiles score it as a hard reject."""
    return ensure_custom_format(api, SAFETY_CF, [
        {"name": "Executable or crack", "implementation": "ReleaseTitleSpecification", "negate": False, "required": True,
         "fields": [{"name": "value", "value": SUSPICIOUS_RX}]}])


def default_profiles(cfg):
    """Profiles derived from the language choices when the person did not edit them."""
    q, packs = cfg.get("quality", {}), list(cfg.get("packs") or [])
    ep, mv = q.get("episodeCapMB", 800), q.get("movieCapGB", 5)
    res = "1080+720" if q.get("allow720", True) else "1080"
    base = {"resTv": res, "resMv": res, "ep1080": ep, "mv1080": mv, "ep720": max(150, ep // 2), "mv720": round(mv / 2, 1),
            "ep2160": 6000, "mv2160": 25, "x265": q.get("preferX265", True), "strictSubs": False}
    out = []
    if "english" in packs or not packs:
        out.append({**base, "id": "english", "name": "English", "kind": "english", "langs": ["english"], "subs": "optional"})
    if "anime" in packs:
        out.append({**base, "id": "anime", "name": "Anime", "kind": "anime", "langs": [], "subs": "required",
                    "audio": cfg.get("animeAudio", "sub"), "ep1080": min(ep, 600), "ep720": min(ep, 600) // 2})
    world = [p for p in packs if p not in ("english", "anime")]
    if world:
        name = " + ".join(PACKS[p] for p in world) if len(world) <= 3 else "World cinema"
        out.append({**base, "id": "world", "name": name, "kind": "world", "langs": world, "subs": "required"})
    return out or [{**base, "id": "english", "name": "English", "kind": "english", "langs": ["english"], "subs": "optional"}]


def profiles_of(cfg):
    ps = cfg.get("profiles") or default_profiles(cfg)
    seen = set()
    for p in ps:   # names must be unique inside Sonarr/Radarr
        n, i = p["name"], 2
        while p["name"].lower() in seen:
            p["name"], i = f"{n} {i}", i + 1
        seen.add(p["name"].lower())
    return ps


def routes_of(ctx):
    """Which profile serves which original language (used by the request page and by Find a title)."""
    ps = profiles_of(ctx.cfg)
    default = next((p for p in ps if p["kind"] == "english"), next((p for p in ps if p["kind"] == "world"), ps[0]))
    anime = next((p for p in ps if p["kind"] == "anime"), None)
    langs = {}
    for p in ps:
        for l in p.get("langs", []):
            langs.setdefault(l, p["id"])
    return {"default": default["id"], "anime": anime["id"] if anime else None, "langs": langs}


def res_of(p, app):
    """Resolutions this profile accepts for series (Sonarr) or movies (Radarr), e.g. "2160", "1080+720"."""
    return p.get("resTv" if app == "sonarr" else "resMv") or p.get("res") or "1080+720"


def uses(p, r, app):
    return r in res_of(p, app).split("+")


DEFAULT_CAPS = {"ep2160": 6000, "mv2160": 25, "ep1080": 800, "mv1080": 5, "ep720": 400, "mv720": 2.5}


def global_caps(profiles, app):
    """Largest limit across profiles per resolution; the apps' own per-minute limits sit at this outer bound."""
    unit = "ep" if app == "sonarr" else "mv"
    out = {}
    for r in RES_ORDER:
        vals = [p.get(f"{unit}{r}", DEFAULT_CAPS[f"{unit}{r}"]) for p in profiles if uses(p, r, app)]
        out[r] = max(vals) if vals else DEFAULT_CAPS[f"{unit}{r}"]
    return out


def apply_sizes(api, app, profiles):
    """Quality definitions (MB per minute) at the outer bound; each profile's own limit is a Size custom format."""
    g = global_caps(profiles, app)
    defs = api.get("/qualitydefinition")
    for d in defs:
        t = d["title"]
        if "2160p" in t:
            res = "2160"
        elif "1080p" in t:
            res = "1080"
        elif "720p" in t:
            res = "720"
        elif any(k in t for k in ("480p", "576p", "SDTV", "DVD")):
            res = "sd"
        else:
            continue
        cap = g.get(res, g["720"] / 2)
        mx = cap / 45 if app == "sonarr" else cap * 1024 / 120      # MB per minute
        if "Remux" in t:
            mx *= 2.5
        mx = round(mx, 1)
        d["maxSize"] = mx
        d["preferredSize"] = round(mx * 0.75, 1)
        d["minSize"] = 0 if res == "sd" else round(mx * (0.04 if res == "720" else 0.06), 1)
    api.put("/qualitydefinition/update", defs)


# ---------------------------------------------------------------- TRaSH custom formats and profiles
def ensure_cfs(ctx, api, app, names):
    """Create/update the named TRaSH custom formats; returns {name: id}."""
    existing = {c["name"]: c["id"] for c in api.get("/customformat")}
    made = {}
    for name in names:
        spec = TR[app]["cfs"].get(name)
        if not spec:
            continue
        body = {"name": name, "includeCustomFormatWhenRenaming": spec["includeCustomFormatWhenRenaming"],
                "specifications": spec["specifications"]}
        try:
            if name in existing:
                body["id"] = existing[name]
                api.put(f"/customformat/{body['id']}", body)
                made[name] = body["id"]
            else:
                made[name] = api.post("/customformat", body)["id"]
        except ApiError as e:
            ctx.log(f"  skipped custom format {name} ({str(e.body)[:70]})")
    return made


def ensure_x265_cf(api):
    name = "x265 (smaller files)"
    body = {"name": name, "includeCustomFormatWhenRenaming": False, "specifications": [
        {"name": "x265/HEVC", "implementation": "ReleaseTitleSpecification", "negate": False, "required": True,
         "fields": [{"name": "value", "value": r"\b(x265|hevc|h\.?265)\b"}]},
        {"name": "No HDR/DV", "implementation": "ReleaseTitleSpecification", "negate": True, "required": True,
         "fields": [{"name": "value", "value": r"\b(hdr|hdr10|dv|dovi|dolby[ ._-]?vision)\b"}]}]}
    for c in api.get("/customformat"):
        if c["name"] == name:
            body["id"] = c["id"]
            api.put(f"/customformat/{c['id']}", body)
            return name
    api.post("/customformat", body)
    return name


def make_profile(api, name, allowed, cutoff_name, scores, language=None, min_score=-999, upgrade=False):
    p = api.get("/qualityprofile/schema")
    cutoff = None
    for it in p["items"]:
        nm = it.get("name") or it["quality"]["name"]
        it["allowed"] = nm in allowed
        if nm == cutoff_name:
            cutoff = it.get("id") if it.get("items") else it["quality"]["id"]
    if cutoff is None:
        raise RuntimeError(f"cutoff {cutoff_name} not in profile schema for {name}")
    fmt = [{**f, "score": scores.get(f["name"], 0)} for f in p["formatItems"]]
    body = {**p, "name": name, "upgradeAllowed": upgrade, "cutoff": cutoff, "formatItems": fmt,
            "minFormatScore": min_score, "cutoffFormatScore": 10000}
    body.pop("id", None)
    if language is not None and "language" in body:
        body["language"] = language
    return upsert(api, "/qualityprofile", api.get("/qualityprofile"), name, body)


def radarr_language(api, name):
    for l in api.get("/language"):
        if l["name"].lower() == name.lower():
            return {"id": l["id"], "name": l["name"]}
    return None


def select_value(spec_schema, field, *needles):
    for f in spec_schema["fields"]:
        if f["name"] == field:
            for o in f.get("selectOptions", []):
                nm = o["name"].lower().replace(" ", "")
                if all(n in nm for n in needles):
                    return o["value"]
    return None


def ensure_custom_format(api, name, specs):
    body = {"name": name, "includeCustomFormatWhenRenaming": False, "specifications": specs}
    for c in api.get("/customformat"):
        if c["name"] == name:
            body["id"] = c["id"]
            api.put(f"/customformat/{c['id']}", body)
            return name
    api.post("/customformat", body)
    return name


def size_cap_cf(api, app, label, res, cap_gb):
    """Matches releases of this resolution that are bigger than the cap (single episodes only on Sonarr)."""
    schema = {x["implementation"]: x for x in api.get("/customformat/schema")}
    rv = select_value(schema["ResolutionSpecification"], "value", res)
    specs = [{"name": f"{res}p", "implementation": "ResolutionSpecification", "negate": False, "required": True,
              "fields": [{"name": "value", "value": rv}]},
             {"name": "Over the limit", "implementation": "SizeSpecification", "negate": False, "required": True,
              "fields": [{"name": "min", "value": round(cap_gb, 2)}, {"name": "max", "value": 1000}]}]
    if app == "sonarr" and "ReleaseTypeSpecification" in schema:
        tv = select_value(schema["ReleaseTypeSpecification"], "value", "single")
        if tv is not None:
            specs.append({"name": "Single episode", "implementation": "ReleaseTypeSpecification", "negate": False,
                          "required": True, "fields": [{"name": "value", "value": tv}]})
    return ensure_custom_format(api, f"Over {label}", specs)


def subs_cfs(api):
    have = ensure_custom_format(api, "English subs included", [
        {"name": "English subs", "implementation": "ReleaseTitleSpecification", "negate": False, "required": False,
         "fields": [{"name": "value", "value": SUBS_RX}]}])
    none = ensure_custom_format(api, "No English subs mentioned", [
        {"name": "No subs", "implementation": "ReleaseTitleSpecification", "negate": True, "required": True,
         "fields": [{"name": "value", "value": SUBS_RX}]}])
    return have, none


def build_profile(ctx, api, app, spec):
    """One profile: TRaSH scoring for its kind, plus its own quality, size limits and subtitle rule."""
    anime = spec["kind"] == "anime"
    kind = "anime" if anime else ("series" if app == "sonarr" else "movie")
    t = TR[app]["profiles"][kind]
    scores = dict(t["scores"])
    for n in SOFT_PENALTY:          # deprioritise instead of reject: a rare title may only exist as a LQ-tagged copy
        if scores.get(n, 0) <= -10000:
            scores[n] = -500
    if anime and spec.get("audio", "sub") == "dub":
        scores.update({"Language: Not Original": 0, "Language: Not English": -10000, "Dubs Only": 100})
    else:   # original audio; subtitles come from the release or Bazarr
        scores.update({"Language: Not Original": -10000, "Language: Not English": 0})
    if spec.get("x265", True) and not anime and res_of(spec, app) != "2160":
        scores[ensure_x265_cf(api)] = 30
    scores.pop("x265 (HD)", None)
    scores[ensure_safety_cf(api)] = -10000
    ensure_cfs(ctx, api, app, [n for n in scores if n in TR[app]["cfs"]])
    # per-profile size limits
    unit = "ep" if app == "sonarr" else "mv"
    for res in RES_ORDER:
        if not uses(spec, res, app):
            continue
        cap = spec.get(f"{unit}{res}", DEFAULT_CAPS[f"{unit}{res}"])      # absolute limit for this profile; the apps' own per-minute limit is only the outer bound
        label = f"{spec['name']} {res}p {'episode' if app == 'sonarr' else 'film'} limit"
        scores[size_cap_cf(api, app, label, res, cap / 1024 if app == "sonarr" else cap)] = -10000
    # English subtitles: prefer releases that include them; optionally refuse the ones that do not
    if spec["kind"] != "english" and spec.get("subs", "required") != "off":
        have, none = subs_cfs(api)
        scores[have] = 60
        if spec.get("strictSubs"):
            scores[none] = -10000
    allowed = [n for r in RES_ORDER if uses(spec, r, app) for n in QUALITY_GROUPS[r]]
    cutoff = allowed[0]
    lang = radarr_language(api, "Any") if app == "radarr" else None
    return make_profile(api, spec["name"], allowed, cutoff, scores, language=lang, upgrade=settings(ctx.cfg)["upgrade"])


def build_all_profiles(ctx, api, app):
    ids = {}
    with grp(f"{app}.profiles"):
        for spec in profiles_of(ctx.cfg):
            ids[spec["id"]] = build_profile(ctx, api, app, spec)["id"]
    with grp(f"{app}.dropstock"):
        drop_stock_profiles(api, {k: {"id": v} for k, v in ids.items()})
    return ids


# ---------------------------------------------------------------- per-app setup
def drop_stock_profiles(api, ours):
    """Leave only the profiles built for this person; stock ones that are in use are kept."""
    keep = {p["id"] for p in ours.values()}
    for p in api.get("/qualityprofile"):
        if p["id"] not in keep:
            try:
                api.delete(f"/qualityprofile/{p['id']}")
            except ApiError:
                pass


def setup_auth(api, ctx):
    login = ctx.cfg.get("login") or {}
    if not login.get("username"):
        return
    host = api.get("/config/host")
    host.update({"authenticationMethod": "forms", "authenticationRequired": "enabled",
                 "username": login["username"], "password": login["password"],
                 "passwordConfirmation": login["password"]})
    api.put(f"/config/host/{host['id']}", host)


def common_settings(api, app, q, ctx):
    mine = ctx.mine(app)

    def extras(cur):          # the person's own subtitle/extra file types stay; ours are added
        want = {"srt", "sub", "ass"} | ({x.strip() for x in (cur or "").split(",") if x.strip()} if mine else set())
        return ",".join(sorted(want))
    with grp(f"{app}.media"):
        mm = api.get("/config/mediamanagement")
        mm.update({"copyUsingHardlinks": True, "deleteEmptyFolders": True, "importExtraFiles": True,
                   "enableMediaInfo": True, "downloadPropersAndRepacks": "doNotPrefer"})
        if not mine:
            mm["recycleBin"] = ""        # the person's own recycle bin is never switched off
        mm["extraFileExtensions"] = extras(mm.get("extraFileExtensions"))
        if app == "sonarr":
            mm.update({"autoUnmonitorPreviouslyDownloadedEpisodes": True, "episodeTitleRequired": "always"})
        else:
            mm.update({"autoUnmonitorPreviouslyDownloadedMovies": True})
        api.put(f"/config/mediamanagement/{mm['id']}", mm)
    with grp(f"{app}.downloads"):
        dl = api.get("/config/downloadclient")
        retry = settings(ctx.cfg)["retryFailed"]
        dl.update({"enableCompletedDownloadHandling": True, "autoRedownloadFailed": retry,
                   "autoRedownloadFailedFromInteractiveSearch": retry})
        if app == "radarr":
            dl["checkForFinishedDownloadInterval"] = 1      # import within a minute of a download finishing
        api.put(f"/config/downloadclient/{dl['id']}", dl)
    with grp(f"{app}.delay"):
        dp = api.get("/delayprofile")[0]
        dp.update({"preferredProtocol": "torrent", "torrentDelay": 0, "usenetDelay": 0})
        api.put(f"/delayprofile/{dp['id']}", dp)
    with grp(f"{app}.indexer"):
        ix = api.get("/config/indexer")
        ix["rssSyncInterval"] = settings(ctx.cfg)["rssMinutes"]
        if app == "radarr":
            ix["maximumSize"] = int(q["movieCapGB"] * 1024 * 1.1)   # hard ceiling just above the per-minute cap
            if settings(ctx.cfg).get("hardSubs", True):
                # regional releases very often carry burned-in English subtitles; accept them
                ix.update({"allowHardcodedSubs": True, "whitelistedHardcodedSubs": "ESub,ESubs,Eng,English,EngSub,EngSubs"})
            else:
                ix.update({"allowHardcodedSubs": False})
        api.put(f"/config/indexer/{ix['id']}", ix)


def setup_sonarr(ctx):
    cfg, q, log = ctx.cfg, ctx.cfg["quality"], ctx.log
    api = servarr(ctx, "sonarr", "v3")
    log("Sonarr is running. Setting size limits and quality choices.")
    with grp("sonarr.sizes"):
        apply_sizes(api, "sonarr", profiles_of(cfg))
    common_settings(api, "sonarr", q, ctx)
    with grp("sonarr.naming"):
        nm = api.get("/config/naming")
        nm.update({"renameEpisodes": True, "replaceIllegalCharacters": True, "multiEpisodeStyle": 5,
                   "standardEpisodeFormat": "{Series TitleYear} - S{season:00}E{episode:00} - {Episode CleanTitle} {Quality Full}",
                   "dailyEpisodeFormat": "{Series TitleYear} - {season:0}x{episode:00} - {Episode CleanTitle} {Quality Full}",
                   "animeEpisodeFormat": "{Series TitleYear} - {season:0}x{episode:00} - {absolute:000} - {Episode CleanTitle} {Quality Full}",
                   "seriesFolderFormat": "{Series Title}", "seasonFolderFormat": "Season {season}"})
        api.put(f"/config/naming/{nm['id']}", nm)
    ctx.profiles_sonarr = build_all_profiles(ctx, api, "sonarr")
    with grp("sonarr.roots"):
        roots = {r["path"] for r in api.get("/rootfolder")}
        wanted_roots = [l["path"] for l in libs_of(ctx.plan, "tv")] + [l["path"] for l in libs_of(ctx.plan, "anime")]
        for path in wanted_roots:
            if path not in roots:
                api.post("/rootfolder", {"path": path})
    with grp("sonarr.qbit"):
        add_qbit(ctx, api, "sonarr", {"tvCategory": "tv", "recentTvPriority": 0, "olderTvPriority": 0})
    with grp("sonarr.auth"):
        setup_auth(api, ctx)
    log("Sonarr ready")


def setup_radarr(ctx):
    cfg, q, log = ctx.cfg, ctx.cfg["quality"], ctx.log
    api = servarr(ctx, "radarr", "v3")
    log("Radarr is running. Setting size limits and quality choices.")
    with grp("radarr.sizes"):
        apply_sizes(api, "radarr", profiles_of(cfg))
    common_settings(api, "radarr", q, ctx)
    with grp("radarr.naming"):
        nm = api.get("/config/naming")
        nm.update({"renameMovies": True, "replaceIllegalCharacters": True,
                   "standardMovieFormat": "{Movie Title} ({Release Year})",
                   "movieFolderFormat": "{Movie Title} ({Release Year})"})
        api.put(f"/config/naming/{nm['id']}", nm)
    ctx.profiles_radarr = build_all_profiles(ctx, api, "radarr")
    with grp("radarr.roots"):
        roots = {r["path"] for r in api.get("/rootfolder")}
        movie_libs = libs_of(ctx.plan, "movies") or libs_of(ctx.plan, "anime")
        for path in [l["path"] for l in movie_libs]:
            if path not in roots:
                api.post("/rootfolder", {"path": path})
    with grp("radarr.qbit"):
        add_qbit(ctx, api, "radarr", {"movieCategory": "movies", "recentMoviePriority": 0, "olderMoviePriority": 0})
    with grp("radarr.auth"):
        setup_auth(api, ctx)
    log("Radarr ready")


def add_qbit(ctx, api, app, extra):
    qb = qbit_creds(ctx)
    schema = api.get("/downloadclient/schema")
    t = next(s for s in schema if s["implementation"] == "QBittorrent")
    vals = {"host": ctx.hostname("qbittorrent"), "port": ctx.port("qbittorrent"), "useSsl": False,
            "username": qb["username"], "password": qb["password"], "initialState": 0,
            "sequentialOrder": True, "firstAndLast": True, **extra}
    existing = api.get("/downloadclient")
    mine = next((e for e in existing if e.get("implementation") == "QBittorrent"), None) if ctx.mine(app) else None
    if mine:
        # the person's own client keeps its address, login and category; only the "no seeding" behaviour is added to it
        mine = {**mine, "enable": True, "removeCompletedDownloads": True, "removeFailedDownloads": True}
        wait_for(lambda: api.post("/downloadclient/test", {**mine}) is None or True, 20, 4, "qBittorrent")
        api.put(f"/downloadclient/{mine['id']}", mine)
        return
    for f in t["fields"]:
        if f["name"] in vals:
            f["value"] = vals[f["name"]]
    # removeCompletedDownloads = delete the torrent from qBittorrent once it is imported => no seeding
    t.update({"name": "qBittorrent", "enable": True, "priority": 1,
              "removeCompletedDownloads": True, "removeFailedDownloads": True})
    t.pop("id", None)
    for e in existing:
        if e["name"] == "qBittorrent":
            t["id"] = e["id"]      # re-runs update the existing client instead of failing on a duplicate name
    wait_for(lambda: api.post("/downloadclient/test", {**t}) is None or True, 90, 4, "qBittorrent")
    upsert(api, "/downloadclient", existing, "qBittorrent", t)


def qbit_creds(ctx):
    mine = ctx.adopt.get("qbittorrent") or {}
    if mine.get("user"):
        return {"username": mine["user"], "password": mine.get("password", "")}
    return ctx.cfg["qbit"]


def qbit_api(ctx):
    qb = qbit_creds(ctx)
    api = Api(ctx.host_url("qbittorrent"), cookies=True, headers={"Referer": ctx.host_url("qbittorrent")})
    api.bypass = True       # signing in is not a change to preview

    def login():
        st, body = api.call("POST", "/api/v2/auth/login", form={"username": qb["username"], "password": qb["password"]}, raw=True)
        if "Fails" in body:  # wrong password: stop immediately, repeated tries get the IP banned
            raise Fatal("qBittorrent rejected the password (login failed)")
        return st in (200, 204)
    wait_for(login, ctx.patience("qbittorrent"), 5, "qBittorrent login")
    api.bypass = False
    return api


def apply_qbit_prefs(ctx, api):
    st, dl = settings(ctx.cfg), ctx.plan["downloads"]
    n = st["concurrent"]
    prefs = {"max_ratio_enabled": True, "max_ratio": 0, "max_ratio_act": 0,
             "max_seeding_time_enabled": False, "queueing_enabled": n > 0,
             "max_active_downloads": n if n > 0 else 50, "max_active_torrents": n if n > 0 else 50,
             "dl_limit": st["dlLimitKB"] * 1024, "up_limit": st["ulLimitKB"] * 1024,
             "save_path": dl, "temp_path_enabled": True, "temp_path": f"{dl}/incomplete",
             "auto_tmm_enabled": False,
             # more peers for public torrents: extra trackers appended from a maintained list, announce to every tracker
             "add_trackers_enabled": True, "add_trackers_from_url_enabled": True,
             "add_trackers_url": "https://cdn.jsdelivr.net/gh/ngosang/trackerslist@master/trackers_best.txt",
             "announce_to_all_trackers": True, "max_connec": 500, "max_connec_per_torrent": 100,
             "max_uploads": 50, "max_uploads_per_torrent": 10,
             # safety: never download anything that is not media, and never run programs when a torrent finishes
             "excluded_file_names_enabled": True, "excluded_file_names": "\n".join(UNSAFE_FILES), "autorun_enabled": False,
             "autorun_on_torrent_added_enabled": False}
    if ctx.mine("qbittorrent"):
        # folders are as the NEW apps see them: the person's own qBittorrent keeps its own
        for k in ("save_path", "temp_path_enabled", "temp_path", "auto_tmm_enabled"):
            prefs.pop(k, None)
    if REC["r"]:
        api.call("GET", "/api/v2/app/preferences", raw=True)       # so the preview can compare
    with grp("qbittorrent.prefs"):
        api.call("POST", "/api/v2/app/setPreferences", form={"json": json.dumps(prefs)}, raw=True)
    with grp("qbittorrent.categories"):
        try:
            have = json.loads(api.call("GET", "/api/v2/torrents/categories", raw=True)[1] or "{}")
        except (ApiError, ValueError):
            have = {}
        for cat, path in (("tv", f"{dl}/tv"), ("movies", f"{dl}/movies")):
            if cat in have and have[cat].get("savePath") == path:
                continue
            try:
                api.call("POST", "/api/v2/torrents/editCategory" if cat in have else "/api/v2/torrents/createCategory",
                         form={"category": cat, "savePath": path}, raw=True)
            except ApiError:
                api.call("POST", "/api/v2/torrents/createCategory", form={"category": cat, "savePath": path}, raw=True)
    return json.loads(api.call("GET", "/api/v2/app/preferences", raw=True)[1])


def setup_qbittorrent(ctx):
    got = apply_qbit_prefs(ctx, qbit_api(ctx))
    ok = got.get("max_ratio_enabled") and got.get("max_ratio") == 0 and not group_off("qbittorrent.prefs")
    ctx.log("qBittorrent is ready. Nothing uploads afterwards, because finished downloads are removed."
            if ok else "qBittorrent is ready, but we could not confirm the upload limit. Check it in qBittorrent under Options.")


def apply_min_seeders(ctx):
    """Set the minimum-seeders rule everywhere: on each Prowlarr indexer and on the copies synced into the apps."""
    n = settings(ctx.cfg)["minSeeders"]
    for app, port, ver in (("prowlarr", 9696, "v1"), ("sonarr", 8989, "v3"), ("radarr", 7878, "v3")):
        api = ctx.apis.get(app)
        if not api:
            continue
        for ix in api.get("/indexer"):
            changed = False
            adapter = any("regional:9120" in str(f.get("value", "")) for f in ix.get("fields", []))
            want = min(n, 5) if adapter else n      # adapter sources report a fixed 5 seeders
            for f in ix.get("fields", []):
                if f["name"].lower().endswith("minimumseeders") and f.get("value") != want:
                    f["value"], changed = want, True
            if changed:
                try:
                    api.put(f"/indexer/{ix['id']}", ix, params={"forceSave": "true"})
                except ApiError:
                    pass


def set_min_seeders(body, n):
    for f in body.get("fields", []):
        if f["name"].lower().endswith("minimumseeders"):
            f["value"] = n


def ensure_adapter_indexers(api, cfg, schema, have, log):
    """Add the adapter-backed sources (BT4G, Tamil/Malayalam forums, MovieRulz) that are missing from Prowlarr.

    Prowlarr refuses a source whose test search returns nothing, so a source that is offline right now is simply skipped
    here; the background watcher calls this again once the adapter reports it has found a working address.
    """
    tsch = next((x for x in schema if x["implementation"] == "Torznab"), None)
    adapters = [("bt4g", "BT4G (DHT search)")]
    if cfg.get("regional"):
        adapters += [("tamilmv", "TamilMV (Tamil/Malayalam forum)"), ("tamilblasters", "TamilBlasters (Tamil/Malayalam forum)"),
                     ("movierulz", "MovieRulz (Indian cinema)")]
    added, failed = [], []
    for site, name in adapters:
        if name.lower() in have:
            added.append(name)
            continue
        if not tsch:
            continue
        body = {**tsch, "name": name, "enable": True, "appProfileId": 1, "priority": 25, "tags": []}
        body.pop("id", None)
        vals = {"baseUrl": f"http://regional:9120/{site}", "apiPath": "/api", "apiKey": "arr"}
        for f in body["fields"]:
            if f["name"] in vals:
                f["value"] = vals[f["name"]]
        set_min_seeders(body, min(settings(cfg)["minSeeders"], 5))   # these sources publish no seeder counts (a fixed 5 is reported)
        try:
            api.post("/indexer", body, params={"forceSave": "true"}, timeout=120)
            added.append(name)
        except ApiError as e:
            failed.append(name)
            log(f"  {name} is not available yet ({str(e.body)[:60]})")
    return added, failed


def setup_prowlarr(ctx):
    cfg, log = ctx.cfg, ctx.log
    api = servarr(ctx, "prowlarr", "v1")
    log("Prowlarr is running. Connecting the helper and your apps.")
    solver_url = f"http://{ctx.hostname('flaresolverr')}:{ctx.port('flaresolverr')}/"
    tags = {t["label"]: t["id"] for t in api.get("/tag")}
    with grp("prowlarr.solver"):
        _prowlarr_solver(api, tags, solver_url)
    with grp("prowlarr.apps"):
        _prowlarr_apps(ctx, api)
    with grp("prowlarr.indexers"):
        _prowlarr_indexers(ctx, api, tags)
    with grp("prowlarr.auth"):
        setup_auth(api, ctx)
    try:
        api.post("/command", {"name": "ApplicationIndexerSync"})
    except ApiError:
        pass


def _prowlarr_solver(api, tags, solver_url):
    if "flaresolverr" not in tags:
        tags["flaresolverr"] = api.post("/tag", {"label": "flaresolverr"})["id"]
    proxies = api.get("/indexerProxy")
    existing = next((p for p in proxies if p["implementation"] == "FlareSolverr"), None)
    if existing:   # re-runs (or a changed solver) update the address in place
        for f in existing["fields"]:
            if f["name"] == "host":
                f["value"] = solver_url
            if f["name"] == "requestTimeout":
                f["value"] = 120
        existing["tags"] = [tags["flaresolverr"]]
        api.put(f"/indexerProxy/{existing['id']}", existing, params={"forceSave": "true"}, timeout=120)
    else:
        sch = next(s for s in api.get("/indexerProxy/schema") if s["implementation"] == "FlareSolverr")
        for f in sch["fields"]:
            if f["name"] == "host":
                f["value"] = solver_url
            if f["name"] == "requestTimeout":
                f["value"] = 120          # small machines can take over a minute to solve a page
        sch.update({"name": "Cloudflare solver", "tags": [tags["flaresolverr"]]})
        sch.pop("id", None)
        api.post("/indexerProxy", sch)


def _prowlarr_apps(ctx, api):
    apps = api.get("/applications")
    for app in ("Sonarr", "Radarr"):
        port = ctx.port(app.lower())
        if any(a["name"] == app for a in apps):
            continue
        sch = next(s for s in api.get("/applications/schema") if s["implementation"] == app)
        vals = {"prowlarrUrl": ctx.host_url("prowlarr"), "baseUrl": ctx.host_url(app.lower()),
                "apiKey": ctx.keys[app.lower()]}
        for f in sch["fields"]:
            if f["name"] in vals:
                f["value"] = vals[f["name"]]
        sch.update({"name": app, "syncLevel": "fullSync", "tags": []})
        sch.pop("id", None)
        api.post("/applications", sch)


def _prowlarr_indexers(ctx, api, tags):
    cfg, log = ctx.cfg, ctx.log
    schema = api.get("/indexer/schema", timeout=300)
    by_name = {}
    for sc in schema:
        if sc.get("privacy") == "public" and sc.get("protocol") == "torrent":
            by_name.setdefault(sc["name"].lower(), sc)
    pf = prefs(cfg)
    wanted = list(GENERAL_INDEXERS)
    if pf["anime"]:
        wanted += ANIME_INDEXERS
    if "korean" in pf["packs"]:
        wanted += KOREAN_INDEXERS
    have = {i["name"].lower() for i in api.get("/indexer")}
    added, failed, missing, seen = [], [], [], set()
    keep_always = set()   # adapter-backed sources heal themselves (domain discovery), so never prune them
    for name in wanted:
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        sch = by_name.get(name.lower())
        if not sch:
            missing.append(name)
            continue
        if name.lower() in have:
            added.append(name)
            continue
        body = {**sch, "enable": True, "appProfileId": 1, "priority": 25,
                "tags": [tags["flaresolverr"]] if name.lower() in BEHIND_CLOUDFLARE else []}
        body.pop("id", None)
        set_min_seeders(body, settings(cfg)["minSeeders"])
        try:
            api.post("/indexer", body, params={"forceSave": "true"}, timeout=90)
            added.append(name)
        except ApiError as e:
            failed.append(name)
            log(f"  Skipped the search site {name} ({str(e.body)[:80]})")
    # second chance for anything that failed on the first pass: the solver is warm now and the first request often just timed out
    for name in list(failed):
        sch = by_name.get(name.lower())
        if not sch:
            continue
        body = {**sch, "enable": True, "appProfileId": 1, "priority": 25,
                "tags": [tags["flaresolverr"]] if name.lower() in BEHIND_CLOUDFLARE else []}
        body.pop("id", None)
        set_min_seeders(body, settings(cfg)["minSeeders"])
        try:
            api.post("/indexer", body, params={"forceSave": "true"}, timeout=120)
            added.append(name)
            failed.remove(name)
        except ApiError:
            pass
    a_added, a_failed = ensure_adapter_indexers(api, cfg, schema, {i["name"].lower() for i in api.get("/indexer")}, log)
    added += a_added
    failed += a_failed
    keep_always.update(a_added)
    # test everything; keep only the ones that really answer so searches never stall on dead sites
    dead = []
    ours = {n.lower() for n in added}
    for ix in api.get("/indexer"):
        if ix["name"] in keep_always:
            continue
        if ctx.mine("prowlarr") and ix["name"].lower() not in ours:
            continue            # a source the person added themselves is never tested away
        try:
            api.post("/indexer/test", ix, timeout=90)
        except ApiError:
            dead.append(ix["name"])
            try:
                api.delete(f"/indexer/{ix['id']}")
            except ApiError:
                pass
    ok = [n for n in added if n not in dead]
    ctx.indexers = {"working": ok, "removed_dead": dead, "not_available": missing + failed}
    log("Your Prowlarr search sites were left as they are" if group_off("prowlarr.indexers") else
        f"Prowlarr ready: {len(ok)} working indexers" + (f" ({len(dead)} unreachable ones removed)" if dead else ""))


# ---------------------------------------------------------------- jellyfin / seerr / bazarr / homepage
JF_AUTH = 'MediaBrowser Client="ArrSetup", Device="wizard", DeviceId="arr-setup", Version="1.0"'


def setup_jellyfin(ctx):
    cfg, log = ctx.cfg, ctx.log
    login = ctx.jf_login()
    base = ctx.host_url("jellyfin")
    api = Api(base, headers={"Authorization": JF_AUTH})
    wait_for(lambda: api.get("/System/Info/Public"), ctx.patience("jellyfin"), 4, "Jellyfin")
    info = api.get("/System/Info/Public")
    if not info.get("StartupWizardCompleted") and not ctx.mine("jellyfin"):
        api.post("/Startup/Configuration", {"UICulture": "en-US", "MetadataCountryCode": "US",
                                            "PreferredMetadataLanguage": "en"})
        try:
            api.get("/Startup/User")
        except ApiError:
            pass
        api.post("/Startup/User", {"Name": login["username"], "Password": login["password"]})
        api.post("/Startup/RemoteAccess", {"EnableRemoteAccess": True, "EnableAutomaticPortMapping": False})
        api.post("/Startup/Complete")
    key = (ctx.adopt.get("jellyfin") or {}).get("key")
    if key:
        token = key
    else:
        api.bypass = True       # signing in is not a change to preview
        auth = api.post("/Users/AuthenticateByName", {"Username": login["username"], "Pw": login["password"]})
        api.bypass = False
        token = auth["AccessToken"]
    api.headers["Authorization"] = f'{JF_AUTH}, Token="{token}"'
    have = {v["Name"] for v in api.get("/Library/VirtualFolders")}
    libs = []
    for name, ctype, kind in (("Movies", "movies", "movies"), ("TV Shows", "tvshows", "tv"), ("Anime", "tvshows", "anime")):
        paths = [l["path"] for l in libs_of(ctx.plan, kind)]
        if paths and (kind != "anime" or prefs(cfg)["anime"]):
            libs.append((name, ctype, paths))
    with grp("jellyfin.libraries"):
        for name, ctype, paths in libs:
            if name not in have:
                api.post("/Library/VirtualFolders", {"LibraryOptions": {"PathInfos": [{"Path": p} for p in paths]}},
                         params={"name": name, "collectionType": ctype, "refreshLibrary": "false"})
    ctx.jellyfin_key = jellyfin_key(ctx, api)
    ctx.jellyfin_token = token
    ctx.jellyfin_libs = [(n, c) for n, c, _ in libs]
    with grp("jellyfin.links"):
        for app in ("sonarr", "radarr"):     # tell Sonarr/Radarr to refresh Jellyfin automatically after every import
            if app not in ctx.apis:
                continue
            try:
                ensure_jellyfin_link(ctx, app)
            except ApiError as e:
                log(f"  could not add Jellyfin notification to {app}: {str(e.body)[:100]}")
    try:
        tune_jellyfin(ctx, api)
    except Exception as e:  # noqa: BLE001 - tuning is an upgrade, never a reason to fail the install
        log(f"  Jellyfin settings could not be tuned: {str(getattr(e, 'body', e))[:120]}")
    log(f"Jellyfin ready: admin '{login['username']}' signed in, libraries added ({', '.join(n for n, _ in ctx.jellyfin_libs)})")


LIVETV_FILE = "channels.m3u"
LIVETV_NAME = "Arr Live TV"


def livetv_on(cfg):
    return bool((cfg.get("livetv") or {}).get("enabled")) and cfg["services"].get("jellyfin")


def jellyfin_admin(ctx):
    api = Api(ctx.host_url("jellyfin"), headers={"Authorization": JF_AUTH})
    key = (ctx.adopt.get("jellyfin") or {}).get("key")
    if key:           # an API key signs in as an admin without a password
        api.headers["Authorization"] = f'{JF_AUTH}, Token="{key}"'
        return api
    login = ctx.jf_login()
    api.bypass = True
    tok = api.post("/Users/AuthenticateByName", {"Username": login["username"], "Pw": login["password"]})["AccessToken"]
    api.bypass = False
    api.headers["Authorization"] = f'{JF_AUTH}, Token="{tok}"'
    return api


def tune_jellyfin(ctx, api=None, log_it=True):
    """Best playback settings for any device: GPU transcoding when there is one, tone-mapping, subtitle and network defaults."""
    import subprocess
    cfg = ctx.cfg
    api = api or jellyfin_admin(ctx)
    users = api.get("/Users")
    want = (ctx.jf_login() or {}).get("username", "").lower() if not (ctx.adopt.get("jellyfin") or {}).get("key") else ""
    me = next((u for u in users if u["Name"].lower() == want), None) or next(
        (u for u in users if (u.get("Policy") or {}).get("IsAdministrator")), users[0])
    host = str(cfg.get("hostAddress") or "")
    lan = ".".join(host.split(".")[:3]) + ".0/24" if re.match(r"^(192\.168|10|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+(\.\d+)?$", host) else None
    if lan and lan.startswith("10."):
        lan = "10.0.0.0/8"
    elif lan and lan.startswith("172."):
        lan = "172.16.0.0/12"
    first = next((p for p in cfg.get("packs", []) if p not in ("anime",)), "english")
    opts = {"lan": lan, "metaLang": ISO.get(first, "en"), "subtitleLang": "eng", "serverName": None if ctx.mine("jellyfin") else "Media Server",
            "trickplay": False}

    def run(cmd):
        r = subprocess.run(["docker", "exec", ctx.container("jellyfin"), "sh", "-c", cmd], capture_output=True, text=True, timeout=120)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    res = jellyfin_tune.tune_all(lambda m, p, b=None: api.call(m, p, body=b), run, me["Id"], opts, group=grp)
    ctx.jellyfin_tune = res
    bad = [s["name"] for s in res["steps"] if not s["ok"]]
    if log_it:
        ctx.log("Jellyfin tuned for every device: " + res["summary"] + (f". Could not apply: {', '.join(bad)}" if bad else ""))
    return res


def livetv_channels(api):
    r = api.get("/LiveTv/Channels", params={"limit": 1})
    return (r or {}).get("TotalRecordCount", 0)


def refresh_guide(api):
    task = next((t for t in api.get("/ScheduledTasks") if t.get("Key") == "RefreshGuide"), None)
    if task:
        try:
            api.post(f"/ScheduledTasks/Running/{task['Id']}")
        except ApiError:
            pass    # already running


def vpn_probe_for(ctx):
    """A function that asks the regional service which VPN exit plays a stream, once the exits are connected; None without a VPN."""
    vpn = (ctx.cfg.get("livetv") or {}).get("vpn") or {}
    if vpn.get("provider") != "nordvpn" or not vpn.get("password"):
        return None
    import urllib.parse
    import urllib.request as ur
    base = "http://regional:9120"

    def ready():
        ex = json.loads(ur.urlopen(base + "/vpn/status", timeout=60).read())["exits"]
        return ex if ex and all(v.get("country") for v in ex.values()) else None
    try:
        wait_for(ready, 180, 6, "the VPN exits")
    except TimeoutError:
        ctx.log("  The VPN did not connect. Check the NordVPN service login. Channels that only work in some countries are skipped for now.")
        return None
    ctx.log("  The VPN is connected. Channels that only work in some countries will be tested through it.")
    return lambda url: json.loads(ur.urlopen(base + "/vpn/probe?url=" + urllib.parse.quote(url, safe=""), timeout=180).read()).get("exit")


def setup_livetv(ctx, rebuild=True):
    with grp("livetv.setup"):
        return _setup_livetv(ctx, rebuild)


def _setup_livetv(ctx, rebuild=True):
    """Live TV and sports in Jellyfin: build the channel list, add it as an M3U tuner and connect the program guides."""
    cfg, log = ctx.cfg, ctx.log
    sel = cfg.get("livetv") or {}
    folder = f"{STACK}/config/jellyfin/livetv"
    path = f"{folder}/{LIVETV_FILE}"
    stats = getattr(ctx, "livetv_stats", None)
    if rebuild or not os.path.exists(path):
        log("Building your channel list (checking which streams work)...")
        stats = livetv.build(sel, path, check=bool(sel.get("checkStreams", True)), deadline=None if (sel.get("vpn") or {}).get("password") else 150,
                             log=log, vpn_probe=vpn_probe_for(ctx))
        ctx.livetv_stats = stats
        os.makedirs(f"{STACK}/config/regional", exist_ok=True)
        json.dump(sel, open(f"{STACK}/config/regional/livetv.json", "w"))
        for p in (folder, path, f"{STACK}/config/regional/livetv.json"):
            try:
                os.chown(p, cfg.get("uid", 1000), cfg.get("gid", 1000))
            except OSError:
                pass
    if not stats or not stats["channels"]:
        raise RuntimeError("no working channels were found for these choices" + (f" ({stats['errors'][0]})" if stats and stats["errors"] else ""))
    if ctx.mine("jellyfin") and not group_off("livetv.setup"):
        # the person's own Jellyfin keeps its files in a folder this wizard cannot see: copy the channel list and guides into it
        import subprocess
        c = ctx.container("jellyfin")
        subprocess.run(["docker", "exec", c, "mkdir", "-p", "/config/livetv"], capture_output=True, timeout=60)
        r = subprocess.run(["docker", "cp", f"{folder}/.", f"{c}:/config/livetv/"], capture_output=True, text=True, timeout=300)
        if r.returncode:
            raise RuntimeError("could not copy the channel list into your Jellyfin: " + (r.stderr or "")[:160])
    api = jellyfin_admin(ctx)
    conf = api.get("/System/Configuration/livetv") or {}
    for t in conf.get("TunerHosts", []):
        if t.get("FriendlyName") == LIVETV_NAME:
            api.delete("/LiveTv/TunerHosts", params={"id": t["Id"]})
    mine = set(stats["guides"]) | {"/config/livetv/local.xml", "/config/livetv/guide.xml"}
    for p in conf.get("ListingProviders", []):
        if p.get("Type") == "xmltv" and ((p.get("Path") or "").startswith(livetv.GUIDES) or p.get("Path") in mine):
            api.delete("/LiveTv/ListingProviders", params={"id": p["Id"]})
    api.post("/LiveTv/TunerHosts", {"Type": "m3u", "Url": f"/config/livetv/{LIVETV_FILE}", "FriendlyName": LIVETV_NAME,
                                    "TunerCount": 0, "ImportFavoritesOnly": False, "AllowHWTranscoding": True,
                                    "AllowStreamSharing": True, "FallbackMaxStreamingBitrate": 30000000, "IgnoreDts": True,
                                    "ReadAtNativeFramerate": True, "EnableStreamLooping": False})
    for g in stats["guides"] + (["/config/livetv/local.xml"] if stats.get("localGuide") else []) + (["/config/livetv/guide.xml"] if stats.get("mergedGuide") else []):
        api.post("/LiveTv/ListingProviders", {"Type": "xmltv", "Path": g, "EnableAllTuners": True, "EnabledTuners": [],
                                              "NewsCategories": ["news"], "SportsCategories": ["sports"],
                                              "KidsCategories": ["kids"], "MovieCategories": ["movies"]},
                 params={"validateListings": "false", "validateLogin": "false"})
    try:     # Jellyfin keeps a copy of each guide file for a while; clear it so the new guide is read now, not later
        import subprocess
        subprocess.run(["docker", "exec", ctx.container("jellyfin"), "sh", "-c", "rm -f /config/cache/xmltv/*.xml"], capture_output=True, timeout=60)
    except Exception:  # noqa: BLE001 - only a speed-up
        pass
    refresh_guide(api)
    n, end = 0, time.time() + 150
    while time.time() < end and not CANCEL.is_set():       # Jellyfin loads channels in batches; wait until most are in
        time.sleep(6)
        try:
            n = livetv_channels(api)
        except ApiError:
            continue
        if n >= stats["channels"] * 0.9:
            break
    pinned = None
    if sel.get("local"):
        try:
            pinned = livetv.pin_favorites(lambda m, p, b=None: api.call(m, p, body=b), stats.get("localNames", []))
        except ApiError as e:
            log(f"  could not pin the local channels: {str(e.body)[:100]}")
    try:
        gone = livetv.purge_stale(lambda m, p, b=None: api.call(m, p, body=b), stats["allNames"])
        if gone:
            log(f"  removed {gone} channels left over from an earlier list")
    except ApiError:
        pass
    try:
        gone = livetv.purge_duplicate_programs(lambda m, p, b=None: api.call(m, p, body=b))
        if gone:
            log(f"  removed {gone} repeated guide entries")
    except ApiError:
        pass
    shown = bool(sel.get("local") and stats.get("localEntries"))
    if shown:
        try:
            livetv.set_home_for_everyone(lambda m, p, b=None: api.call(m, p, body=b))
        except ApiError as e:
            log(f"  could not set the home page layout: {str(e.body)[:100]}")
    ctx.livetv_stats = {**stats, "inJellyfin": n, "pinned": pinned, "homeRow": shown}
    log(f"Live TV ready: {n or stats['channels']} channels ({stats['sports']} sports), {stats['withGuide']} with a program guide; "
        f"{stats['dead']} dead streams left out." + (f" {pinned['channels']} local channels pinned for {pinned['users']} users." if pinned else "") + (" Jellyfin's Live TV row on every home page now shows the local channels." if ctx.livetv_stats.get("homeRow") else "") + " Open Jellyfin, Live TV.")
    return ctx.livetv_stats


def disable_livetv(ctx):
    """Remove the tuner and guides Arr added; the person's own Jellyfin Live TV setup is left alone."""
    api = jellyfin_admin(ctx)
    conf = api.get("/System/Configuration/livetv") or {}
    for t in conf.get("TunerHosts", []):
        if t.get("FriendlyName") == LIVETV_NAME:
            api.delete("/LiveTv/TunerHosts", params={"id": t["Id"]})
    for p in conf.get("ListingProviders", []):
        if p.get("Type") == "xmltv" and ((p.get("Path") or "").startswith(livetv.GUIDES) or p.get("Path") in ("/config/livetv/local.xml", "/config/livetv/guide.xml")):
            api.delete("/LiveTv/ListingProviders", params={"id": p["Id"]})
    for f in (f"{STACK}/config/regional/livetv.json",):
        if os.path.exists(f):
            os.remove(f)


# ---------------------------------------------------------------- notifications (optional)
NOTIFY_NAME = "Arr Notifications"
NOTIFY_EVENTS = ["onGrab", "onDownload", "onUpgrade", "onHealthIssue", "onApplicationUpdate", "onManualInteractionRequired"]
NOTIFY = {   # provider -> (Servarr implementation, {schema field: key in the person's values}, required keys)
    "discord": ("Discord", {"webHookUrl": "webhook"}, ["webhook"]),
    "telegram": ("Telegram", {"botToken": "botToken", "chatId": "chatId"}, ["botToken", "chatId"]),
    "pushover": ("Pushover", {"userKey": "userKey", "apiKey": "apiKey"}, ["userKey", "apiKey"]),
    "ntfy": ("Ntfy", {"serverUrl": "server", "accessToken": "token", "topics": "topic"}, ["topic"]),
    "gotify": ("Gotify", {"server": "server", "appToken": "token"}, ["server", "token"]),
}


def notify_on(cfg):
    n = cfg.get("notify") or {}
    p = NOTIFY.get(n.get("provider"))
    return bool(p and all((n.get("values") or {}).get(k) for k in p[2]))


def apprise_url(provider, v):
    """The same destination written the way Bazarr's notification library expects it."""
    import urllib.parse as up
    if provider == "discord":
        m = re.search(r"/webhooks/(\d+)/([\w-]+)", v["webhook"])
        return f"discord://{m.group(1)}/{m.group(2)}" if m else None
    if provider == "telegram":
        return f"tgram://{v['botToken']}/{v['chatId']}"
    if provider == "pushover":
        return f"pover://{v['userKey']}@{v['apiKey']}"
    if provider == "ntfy":
        host = (v.get("server") or "").replace("https://", "").replace("http://", "").strip("/")
        scheme = "ntfys" if not (v.get("server") or "").startswith("http://") else "ntfy"
        return f"{scheme}://{host + '/' if host else ''}{up.quote(v['topic'])}"
    if provider == "gotify":
        host = v["server"].replace("https://", "").replace("http://", "").strip("/")
        return f"{'gotifys' if not v['server'].startswith('http://') else 'gotify'}://{host}/{v['token']}"
    return None


def ensure_notification(api, app, provider, v):
    """One notification connection in Sonarr, Radarr or Prowlarr, created or updated in place."""
    impl, mapping, _ = NOTIFY[provider]
    sch = next((s for s in api.get("/notification/schema") if s["implementation"] == impl), None)
    if not sch:
        raise RuntimeError(f"{app} has no {impl} notification type")
    for f in sch["fields"]:
        key = next((k for sk, k in mapping.items() if sk == f["name"]), None)
        if key and v.get(key):
            f["value"] = [v[key]] if f["name"] == "topics" else v[key]
        elif f["name"] == "username":
            f["value"] = app.title()
    flags = {e: True for e in NOTIFY_EVENTS}
    if app == "prowlarr":
        flags = {"onHealthIssue": True, "onApplicationUpdate": True}
    for e in NOTIFY_EVENTS:
        if e in sch:
            sch[e] = flags.get(e, False)
    sch["name"] = NOTIFY_NAME
    sch.pop("id", None)
    existing = next((n for n in api.get("/notification") if n["name"] == NOTIFY_NAME), None)
    if existing:
        sch["id"] = existing["id"]
        return api.put(f"/notification/{existing['id']}", sch, params={"forceSave": "true"})
    return api.post("/notification", sch, params={"forceSave": "true"})


def setup_notifications(ctx, send_test=True):
    with grp("notify.setup"):
        return _setup_notifications(ctx, send_test)


def _setup_notifications(ctx, send_test=True):
    """Send the same events to the person's chat app from every app that can notify. Returns a short report."""
    cfg, log = ctx.cfg, ctx.log
    n = cfg.get("notify") or {}
    provider, v = n.get("provider"), n.get("values") or {}
    done, problems = [], []
    for app in ("sonarr", "radarr", "prowlarr"):
        api = ctx.apis.get(app)
        if not api:
            continue
        try:
            if notify_on(cfg):
                ensure_notification(api, app, provider, v)
            else:
                for x in api.get("/notification"):
                    if x["name"] == NOTIFY_NAME:
                        api.delete(f"/notification/{x['id']}")
            done.append(app.title())
        except (ApiError, RuntimeError) as e:
            problems.append(f"{app.title()}: {str(getattr(e, 'body', e))[:100]}")
    if cfg["services"].get("seerr"):
        try:
            seerr_notifications(ctx, provider if notify_on(cfg) else None, v)
            done.append("Seerr")
        except Exception as e:  # noqa: BLE001 - optional extra
            problems.append(f"Seerr: {str(getattr(e, 'body', e))[:100]}")
    if cfg["services"].get("bazarr"):
        try:
            bz = bazarr_api(ctx)
            url = apprise_url(provider, v) if notify_on(cfg) else None
            names = {"discord": "Discord", "telegram": "Telegram", "pushover": "Pushover", "ntfy": "ntfy", "gotify": "Gotify"}
            old = n.get("bazarrProvider")       # Bazarr ships a fixed list of providers; only the one this wizard enabled is switched off
            items = []
            if old and old != (provider if url else None):
                items.append({"name": names[old], "enabled": False, "url": None})
            if url:
                items.append({"name": names[provider], "enabled": True, "url": url})
            if items:
                bz.post("/system/settings", form={"notifications-providers": [json.dumps(i) for i in items]})
            n["bazarrProvider"] = provider if url else None
            done.append("Bazarr")
        except Exception as e:  # noqa: BLE001
            problems.append(f"Bazarr: {str(getattr(e, 'body', e))[:100]}")
    tested = None
    if send_test and notify_on(cfg) and ctx.apis.get("sonarr"):
        try:
            nt = next(x for x in ctx.apis["sonarr"].get("/notification") if x["name"] == NOTIFY_NAME)
            ctx.apis["sonarr"].post("/notification/test", nt)
            tested = True
        except Exception as e:  # noqa: BLE001
            tested = False
            problems.append(f"test message failed: {str(getattr(e, 'body', e))[:120]}")
    if notify_on(cfg):
        log(f"Notifications ready ({provider.title()}): {', '.join(done)}" + (". A test message was sent." if tested else ""))
    return {"done": done, "problems": problems, "tested": tested}


SEERR_AGENT = {"discord": ("discord", lambda v: {"webhookUrl": v["webhook"]}),
               "telegram": ("telegram", lambda v: {"botAPI": v["botToken"], "chatId": v["chatId"], "sendSilently": False}),
               "pushover": ("pushover", lambda v: {"accessToken": v["apiKey"], "userToken": v["userKey"]}),
               "ntfy": ("ntfy", lambda v: {"url": v.get("server") or "https://ntfy.sh", "topic": v["topic"], "token": v.get("token", "")}),
               "gotify": ("gotify", lambda v: {"url": v["server"], "token": v["token"], "priority": 0})}


def seerr_notifications(ctx, provider, v):
    """Seerr request events to the same chat app. Only the agent this wizard enabled is ever switched off again."""
    n = ctx.cfg.setdefault("notify", {})
    se = Api(ctx.host_url("seerr"), prefix="/api/v1", cookies=True)
    seerr_login(ctx, se)
    old = n.get("seerrAgent")
    new = SEERR_AGENT[provider][0] if provider else None
    if old and old != new:
        try:
            se.post(f"/settings/notifications/{old}", {**se.get(f"/settings/notifications/{old}"), "enabled": False})
        except ApiError:
            pass
    if provider:
        agent, opts = SEERR_AGENT[provider]
        # request, approval, availability, failure, decline, auto-approve
        se.post(f"/settings/notifications/{agent}", {"enabled": True, "types": 2 + 4 + 8 + 16 + 64 + 128, "options": opts(v)})
    n["seerrAgent"] = new


def jellyfin_key(ctx, a=None):
    """The API key the Arr apps use to reach Jellyfin (created once, found again on later runs)."""
    if getattr(ctx, "jellyfin_key", None):
        return ctx.jellyfin_key
    mine = (ctx.adopt.get("jellyfin") or {}).get("key")
    if mine:
        ctx.jellyfin_key = mine
        return mine
    a = a or jellyfin_admin(ctx)
    keys = a.get("/Auth/Keys").get("Items", [])
    if not any(k.get("AppName") == "Arr" for k in keys):
        if group_off("jellyfin.links"):
            return "(a key created for Sonarr and Radarr)"          # a preview does not create one
        a.post("/Auth/Keys", params={"app": "Arr"})
        keys = a.get("/Auth/Keys").get("Items", [])
    ctx.jellyfin_key = next(k["AccessToken"] for k in keys if k.get("AppName") == "Arr")
    return ctx.jellyfin_key


def ensure_jellyfin_link(ctx, app):
    """Sonarr/Radarr -> Jellyfin: refresh the library after every import. Updates an existing link in place."""
    a = ctx.apis[app]
    sch = next(s for s in a.get("/notification/schema") if s["implementation"] == "MediaBrowser")
    vals = {"host": ctx.hostname("jellyfin"), "port": ctx.port("jellyfin"), "useSsl": False, "apiKey": jellyfin_key(ctx), "updateLibrary": True, "notify": False}
    for f in sch["fields"]:
        if f["name"] in vals:
            f["value"] = vals[f["name"]]
    sch.update({"name": "Jellyfin", "onDownload": True, "onUpgrade": True, "onRename": True,
                "onSeriesDelete": True, "onEpisodeFileDelete": True, "onMovieDelete": True, "onMovieFileDelete": True})
    sch.pop("id", None)
    existing = next((n for n in a.get("/notification") if n["implementation"] == "MediaBrowser"), None)
    if existing and ctx.mine(app):
        return              # a connection to Jellyfin the person already has is left exactly as it is
    if existing:
        sch["id"] = existing["id"]
        a.put(f"/notification/{existing['id']}", sch)
    else:
        a.post("/notification", sch)


def best_root(ctx, kind):
    """Root folder of this kind with the most free space (Sonarr/Radarr report it)."""
    app = "radarr" if kind == "movies" else "sonarr"
    mine = {l["path"] for l in libs_of(ctx.plan, kind)}
    try:
        roots = [r for r in ctx.apis[app].get("/rootfolder") if r["path"] in mine]
        return max(roots, key=lambda r: r.get("freeSpace") or 0)["path"] if roots else None
    except (ApiError, KeyError):
        return next(iter(mine), None)


def seerr_login(ctx, api):
    """Sign in to Seerr through Jellyfin (a sign-in is not a change to preview). The person's own Seerr is used with its API key."""
    key = (ctx.adopt.get("seerr") or {}).get("key")
    if key:
        api.headers["X-Api-Key"] = key
        return
    login = ctx.jf_login()
    api.bypass = True
    try:
        api.post("/auth/jellyfin", {"username": login["username"], "password": login["password"]})
    finally:
        api.bypass = False


def setup_seerr(ctx):
    cfg, log = ctx.cfg, ctx.log
    login = ctx.jf_login()
    api = Api(ctx.host_url("seerr"), prefix="/api/v1", cookies=True)
    wait_for(lambda: api.get("/status"), ctx.patience("seerr"), 4, "Seerr")
    pub = api.get("/settings/public")
    if not pub.get("initialized") and not ctx.mine("seerr"):
        try:
            api.post("/auth/jellyfin", {"username": login["username"], "password": login["password"],
                                        "hostname": ctx.hostname("jellyfin"), "port": ctx.port("jellyfin"), "useSsl": False, "urlBase": "",
                                        "email": cfg["login"].get("email") or "admin@example.com", "serverType": 2})
        except ApiError as e:
            if "already configured" not in str(e.body):   # re-run: the server is saved, just sign in
                raise
            seerr_login(ctx, api)
        libs = api.post("/settings/jellyfin/library/sync") or []
        for lib in libs:
            api.put(f"/settings/jellyfin/library/{lib['id']}", {"enabled": True})
        try:
            api.post("/settings/jellyfin/sync", {"start": True})
        except ApiError:
            pass
    else:
        seerr_login(ctx, api)
    rt = routes_of(ctx)
    prof_s, prof_r = ctx.profiles_sonarr, ctx.profiles_radarr
    s_def, r_def = prof_s[rt["default"]], prof_r[rt["default"]]
    s_ani = prof_s[rt["anime"]] if rt["anime"] else s_def
    s_api, r_api = ctx.apis["sonarr"], ctx.apis["radarr"]
    sp = {p["id"]: p["name"] for p in s_api.get("/qualityprofile")}
    rp = {p["id"]: p["name"] for p in r_api.get("/qualityprofile")}
    existing_s = api.get("/settings/sonarr")
    existing_r = api.get("/settings/radarr")

    def save(kind, existing, body):   # create on first run, update in place on re-runs (profile ids may change)
        if existing:
            merged = {k: v for k, v in {**existing[0], **body}.items() if k != "id"}
            api.put(f"/settings/{kind}/{existing[0]['id']}", merged)
        else:
            api.post(f"/settings/{kind}", body)
    keep = ctx.mine("seerr")        # the person's own Seerr keeps the Sonarr/Radarr connections it already has
    with grp("seerr.defaults"):
        if not (keep and existing_s):
            save("sonarr", existing_s, {
                "name": "Sonarr", "hostname": ctx.hostname("sonarr"), "port": ctx.port("sonarr"), "apiKey": ctx.keys["sonarr"], "useSsl": False,
                "baseUrl": "", "activeProfileId": s_def, "activeProfileName": sp.get(s_def, ""),
                "activeDirectory": best_root(ctx, "tv"), "activeAnimeProfileId": s_ani,
                "activeAnimeProfileName": sp.get(s_ani, ""), "activeAnimeDirectory": best_root(ctx, "anime") or best_root(ctx, "tv"),
                "is4k": False, "isDefault": True, "enableSeasonFolders": True, "syncEnabled": True,
                "preventSearch": False, "tags": [], "animeTags": []})
        if not (keep and existing_r):
            save("radarr", existing_r, {
                "name": "Radarr", "hostname": ctx.hostname("radarr"), "port": ctx.port("radarr"), "apiKey": ctx.keys["radarr"], "useSsl": False,
                "baseUrl": "", "activeProfileId": r_def, "activeProfileName": rp.get(r_def, ""),
                "activeDirectory": best_root(ctx, "movies") or best_root(ctx, "anime"), "is4k": False, "minimumAvailability": "released",
                "isDefault": True, "syncEnabled": True, "preventSearch": False, "tags": []})
        if not keep:
            api.post("/settings/initialize")
    api.get("/settings/main")           # what it holds now, for the preview
    with grp("seerr.perms"):
        try:   # new users can request, and (optionally) their requests start downloading without waiting for an admin
            perms = 32 | (128 if cfg.get("autoApprove", True) else 0)       # REQUEST | AUTO_APPROVE
            api.post("/settings/main", {"defaultPermissions": perms, "partialRequestsEnabled": True})
        except ApiError as e:
            log(f"  could not set default request permissions ({str(e.body)[:80]})")
    with grp("seerr.routes"):
        # route requests by the title's original language to the matching profile
        rules = api.get("/overrideRule") or []
        if not keep:
            for rule in rules:
                api.delete(f"/overrideRule/{rule['id']}")
            rules = []

        def add_rule(rule):          # the person's own rules stay; ours are added unless an identical one is already there
            if not any(all(r.get(k) == v for k, v in rule.items()) for r in rules):
                api.post("/overrideRule", rule)
        sid = (api.get("/settings/sonarr") or [{}])[0].get("id", 0)
        rid = (api.get("/settings/radarr") or [{}])[0].get("id", 0)
        for p in profiles_of(cfg):
            codes = "|".join(ISO[l] for l in p.get("langs", []) if l in ISO and l != "english")
            if p["kind"] == "world" and codes:
                add_rule({"sonarrServiceId": sid, "language": codes, "profileId": prof_s[p["id"]]})
                add_rule({"radarrServiceId": rid, "language": codes, "profileId": prof_r[p["id"]]})
        if rt["anime"]:
            add_rule({"radarrServiceId": rid, "genre": "16", "language": "ja", "profileId": prof_r[rt["anime"]]})
    ctx.seerr_key = api.get("/settings/main").get("apiKey")
    log("Seerr ready: sign in with your Jellyfin account; requests flow to Sonarr/Radarr automatically")


BAZARR_PROVIDERS = ["embeddedsubtitles", "yifysubtitles", "gestdown", "animetosho", "subf2m", "podnapisi", "subtitlecat"]


def bazarr_api(ctx):
    path = f"{STACK}/config/bazarr/config/config.yaml"
    key = (ctx.adopt.get("bazarr") or {}).get("key") or wait_for(
        lambda: re.search(r"apikey:\s*['\"]?([0-9a-f]{32})", open(path).read()).group(1), ctx.patience("bazarr"), 4, "Bazarr api key")
    api = Api(ctx.host_url("bazarr"), prefix="/api", headers={"X-API-KEY": key})
    wait_for(lambda: api.get("/system/status"), ctx.patience("bazarr"), 4, "Bazarr")
    return api


def setup_bazarr(ctx):
    """Everything Bazarr needs, through its settings API (it ignores a pre-written config file).

    Values follow a Bazarr that has run for months, adjusted for low-spec machines: English required, upgrades on,
    OCR/common subtitle fixes, scene-name matching, both syncs at sensible intervals, Jellyfin refresh after every
    subtitle, weekly backups, analytics off.
    """
    cfg, log = ctx.cfg, ctx.log
    api = bazarr_api(ctx)
    langs = list(dict.fromkeys(["en"] + (cfg.get("subtitleLangs") or [])))
    providers = list(BAZARR_PROVIDERS)
    sub = cfg.get("subtitles") or {}
    if sub.get("opensubtitlescom_user"):
        providers.append("opensubtitlescom")
    if sub.get("subdl_key"):
        providers.append("subdl")
    if sub.get("subsource_key"):
        providers.append("subsource")
    profile = [{"profileId": 1, "name": "Default", "cutoff": 1, "items": [
        {"id": i + 1, "language": l, "audio_exclude": "False", "hi": "False", "forced": "False"} for i, l in enumerate(langs)],
        "mustContain": [], "mustNotContain": [], "originalFormat": 0, "tag": None}]
    login = cfg.get("login") or {}
    g = lambda k, v: {f"settings-general-{k}": str(v).lower() if isinstance(v, bool) else v}  # noqa: E731
    form = {
        "settings-general-use_sonarr": "true", "settings-general-use_radarr": "true",
        "settings-sonarr-ip": ctx.hostname("sonarr"), "settings-sonarr-port": str(ctx.port("sonarr")), "settings-sonarr-base_url": "", "settings-sonarr-ssl": "false",
        "settings-sonarr-apikey": ctx.keys["sonarr"], "settings-sonarr-only_monitored": "true",
        "settings-sonarr-sync_only_monitored_series": "true", "settings-sonarr-sync_only_monitored_episodes": "true",
        "settings-sonarr-exclude_season_zero": "true", "settings-sonarr-series_sync": "60", "settings-sonarr-series_sync_on_live": "true",
        "settings-sonarr-full_update": "Daily", "settings-sonarr-full_update_hour": "4", "settings-sonarr-use_ffprobe_cache": "true",
        "settings-radarr-ip": ctx.hostname("radarr"), "settings-radarr-port": str(ctx.port("radarr")), "settings-radarr-base_url": "", "settings-radarr-ssl": "false",
        "settings-radarr-apikey": ctx.keys["radarr"], "settings-radarr-only_monitored": "false",
        "settings-radarr-sync_only_monitored_movies": "true", "settings-radarr-movies_sync": "360", "settings-radarr-movies_sync_on_live": "true",
        "settings-radarr-full_update": "Daily", "settings-radarr-full_update_hour": "4", "settings-radarr-use_ffprobe_cache": "true",
        "settings-general-enabled_providers": providers,
        "languages-enabled": langs, "languages-profiles": json.dumps(profile),
        "settings-analytics-enabled": "false",
        "settings-backup-frequency": "Weekly", "settings-backup-day": "6", "settings-backup-hour": "3", "settings-backup-retention": "31",
        "settings-subsync-use_subsync": "false",       # audio-based re-timing is CPU heavy; off by default
    }
    for k, v in {"adaptive_searching": False, "minimum_score": 80, "minimum_score_movie": 70, "upgrade_subs": True,
                 "days_to_upgrade_subs": 7, "upgrade_frequency": 12, "upgrade_manual": True, "wanted_search_frequency": 6,
                 "wanted_search_frequency_movie": 6, "use_scenename": True, "utf8_encode": True, "subfolder": "current",
                 "use_embedded_subs": True, "embedded_subtitles_parser": "ffprobe", "parse_embedded_audio_track": True,
                 "serie_default_enabled": True, "serie_default_profile": 1, "movie_default_enabled": True,
                 "movie_default_profile": 1, "serie_tag_enabled": True, "movie_tag_enabled": True, "multithreading": True,
                 "concurrent_jobs": 3, "default_und_audio_lang": "en", "default_und_embedded_subtitles_lang": "en"}.items():
        form.update(g(k, v))
    if "opensubtitlescom" in providers:
        form["settings-opensubtitlescom-username"] = sub["opensubtitlescom_user"]
        form["settings-opensubtitlescom-password"] = sub.get("opensubtitlescom_pass", "")
        form["settings-opensubtitlescom-use_hash"] = "true"
    if "subdl" in providers:
        form["settings-subdl-api_key"] = sub["subdl_key"]
    if "subsource" in providers:
        form["settings-subsource-apikey"] = sub["subsource_key"]
    if login.get("username") and not ctx.mine("bazarr"):      # the person's own Bazarr keeps its own login
        form.update({"settings-auth-type": "form", "settings-auth-username": login["username"],
                     "settings-auth-password": login["password"]})
    # One mapping per library folder, built from the drives the person chose. Every app mounts each folder at the same
    # path, so these are identity mappings, but being explicit keeps Bazarr correct if a folder is ever mounted differently.
    series_roots = [l["path"] for l in libs_of(ctx.plan, "tv") + libs_of(ctx.plan, "anime")]
    movie_roots = [l["path"] for l in (libs_of(ctx.plan, "movies") or libs_of(ctx.plan, "anime"))]
    slash = lambda p: p.rstrip("/") + "/"  # noqa: E731
    form["settings-general-path_mappings"] = [f"{slash(p)},{slash(p)}" for p in dict.fromkeys(series_roots)]
    form["settings-general-path_mappings_movie"] = [f"{slash(p)},{slash(p)}" for p in dict.fromkeys(movie_roots)]
    if sub.get("anidb_client"):     # optional AniDB integration (anime title matching); needs the person's own registered client
        ver = str(sub.get("anidb_ver") or "1")
        form.update({"settings-general-enabled_integrations": ["anidb"], "settings-anidb-api_client": sub["anidb_client"].strip().lower(),
                     "settings-anidb-api_client_ver": ver, "settings-animetosho-anidb_api_client": sub["anidb_client"].strip().lower(),
                     "settings-animetosho-anidb_api_client_ver": ver})
    jf_note = ""
    if cfg["services"].get("jellyfin"):
        try:
            key = jellyfin_key(ctx)
            jf_url = ctx.host_url("jellyfin")
            libs = (api.get("/jellyfin/libraries", params={"url": jf_url, "apikey": key}) or {}).get("data", [])
            mov = [x for x in libs if x["type"] == "movies"]
            ser = [x for x in libs if x["type"] == "tvshows"]
            form.update({"settings-general-use_jellyfin": "true", "settings-jellyfin-url": jf_url,
                         "settings-jellyfin-apikey": key, "settings-jellyfin-refresh_method": "immediate",
                         "settings-jellyfin-update_movie_library": "true", "settings-jellyfin-update_series_library": "true",
                         "settings-jellyfin-movie_library": [x["name"] for x in mov], "settings-jellyfin-movie_library_ids": [x["id"] for x in mov],
                         "settings-jellyfin-series_library": [x["name"] for x in ser], "settings-jellyfin-series_library_ids": [x["id"] for x in ser]})
            jf_note = "; refreshes Jellyfin after every subtitle"
        except (ApiError, StopIteration) as e:
            log(f"  Bazarr could not be linked to Jellyfin yet ({str(getattr(e, 'body', e))[:80]})")
    cur = api.get("/system/settings") or {}        # what it holds now (also what the preview compares with)
    if ctx.mine("bazarr"):
        # connections the person's own Bazarr already has are left exactly as they are
        for sec in ("sonarr", "radarr"):
            if (cur.get(sec) or {}).get("ip"):
                for k in [k for k in form if k.startswith(f"settings-{sec}-") or k == f"settings-general-use_{sec}"]:
                    form.pop(k)
        if (cur.get("jellyfin") or {}).get("url"):
            for k in [k for k in form if k.startswith("settings-jellyfin-") or k == "settings-general-use_jellyfin"]:
                form.pop(k)

    def bazarr_group(k):
        if k.startswith(("settings-sonarr-", "settings-radarr-", "settings-jellyfin-")) or k in (
                "settings-general-use_sonarr", "settings-general-use_radarr", "settings-general-use_jellyfin"):
            return "bazarr.links"
        if "path_mappings" in k:
            return "bazarr.paths"
        if k.startswith("languages-") or any(x in k for x in ("serie_default", "movie_default", "default_und")):
            return "bazarr.languages"
        if "providers" in k or k.startswith(("settings-opensubtitlescom", "settings-subdl", "settings-subsource", "settings-anidb",
                                             "settings-animetosho")) or k == "settings-general-enabled_integrations":
            return "bazarr.providers"
        return "bazarr.tuning"
    parts = {}
    for k, v in form.items():
        parts.setdefault(bazarr_group(k), {})[k] = v
    for gid in ("bazarr.links", "bazarr.paths", "bazarr.languages", "bazarr.providers", "bazarr.tuning"):
        if parts.get(gid):
            with grp(gid):
                api.post("/system/settings", form=parts[gid])
    got = api.get("/system/settings")
    ok = got["general"].get("use_sonarr") and got["general"].get("use_radarr") and got["sonarr"].get("ip") == ctx.hostname("sonarr") or group_off("bazarr.links")
    status = api.get("/system/status").get("data", {})
    for t in ("update_series", "update_movies", "wanted_search_missing_subtitles_series", "wanted_search_missing_subtitles_movies"):
        if group_off("bazarr.tuning"):
            break
        try:
            api.post("/system/tasks", params={"taskid": t})      # start the first sync and subtitle search right away
        except ApiError:
            pass
    time.sleep(3)
    live = [p["name"] for p in (api.get("/providers") or {}).get("data", []) if p.get("status") == "Good"]
    log(("Bazarr connected to Sonarr " + str(status.get("sonarr_version", "")) + " and Radarr " + str(status.get("radarr_version", ""))
         + f"; subtitles in {', '.join(langs)}; {len(live)} subtitle providers working{jf_note}") if ok
        else "Bazarr is running but the Sonarr/Radarr link could not be confirmed")


def setup_homepage(ctx):
    cfg = ctx.cfg
    p = cfg["ports"]
    d = f"{STACK}/config/homepage"
    os.makedirs(d, exist_ok=True)
    host = cfg.get("hostAddress") or "localhost"

    def entry(name, icon, port, desc, widget=None):
        e = {"icon": icon, "href": (cfg.get("tailscaleUrls") or {}).get(port) or (cfg.get("tailscaleUrls") or {}).get(str(port)) or f"http://{host}:{port}", "description": desc}
        if widget:
            e["widget"] = widget
        return {name: e}
    q = cfg["qbit"]
    media, arrs, dl = [], [], []
    if cfg["services"].get("jellyfin"):
        media.append(entry("Jellyfin", "jellyfin", p["jellyfin"], "Watch your library",
                           {"type": "jellyfin", "url": "http://jellyfin:8096", "key": getattr(ctx, "jellyfin_key", ""),
                            "enableBlocks": True, "enableNowPlaying": True}))
    if cfg["services"].get("seerr"):
        media.append(entry("Seerr", "jellyseerr", p["seerr"], "Request movies & shows",
                           {"type": "jellyseerr", "url": "http://seerr:5055", "key": getattr(ctx, "seerr_key", "")}))
    arrs += [
        entry("Sonarr", "sonarr", p["sonarr"], "TV shows", {"type": "sonarr", "url": "http://sonarr:8989", "key": ctx.keys["sonarr"]}),
        entry("Radarr", "radarr", p["radarr"], "Movies", {"type": "radarr", "url": "http://radarr:7878", "key": ctx.keys["radarr"]}),
        entry("Prowlarr", "prowlarr", p["prowlarr"], "Indexers", {"type": "prowlarr", "url": "http://prowlarr:9696", "key": ctx.keys["prowlarr"]}),
    ]
    if cfg["services"].get("bazarr"):
        arrs.append(entry("Bazarr", "bazarr", p["bazarr"], "Subtitles"))
    arrs.append(entry({"byparr": "Byparr", "trawl": "TRAWL"}.get(cfg.get("solver"), "FlareSolverr"), "flaresolverr", p["flaresolverr"], "Cloudflare solver for indexers"))
    dl.append(entry("qBittorrent", "qbittorrent", p["qbittorrent"], "Downloads (no seeding)",
                    {"type": "qbittorrent", "url": "http://qbittorrent:8080", "username": q["username"], "password": q["password"]}))
    for k, icon, desc in (("metube", "metube", "YouTube downloader"), ("komga", "komga", "Comics & manga reader"),
                          ("mylar3", "mylar", "Comic downloads"), ("scrutiny", "scrutiny", "Disk health")):
        if cfg["services"].get(k):
            dl.append(entry(k.capitalize(), icon, p[k], desc))
    groups = []
    if media: groups.append({"Watch & request": media})
    groups += [{"Automation": arrs}, {"Downloads": dl}]
    import yaml
    yaml.safe_dump(groups, open(f"{d}/services.yaml", "w"), sort_keys=False)
    yaml.safe_dump({"title": "My Media Server", "theme": "dark", "color": "slate", "headerStyle": "boxed",
                    "layout": {"Watch & request": {"style": "row", "columns": 2}, "Automation": {"style": "row", "columns": 4},
                               "Downloads": {"style": "row", "columns": 3}}}, open(f"{d}/settings.yaml", "w"), sort_keys=False)
    yaml.safe_dump([{"resources": {"cpu": True, "memory": True, "disk": "/"}}], open(f"{d}/widgets.yaml", "w"))
    for f in ("bookmarks.yaml", "docker.yaml"):
        if not os.path.exists(f"{d}/{f}"):
            open(f"{d}/{f}", "w").write("---\n" if f == "bookmarks.yaml" else "")
    ctx.log("Homepage dashboard built with live widgets for every app")


def verify_logins(ctx):
    """Sign in to every app with the credentials the person chose, so the final screen only lists logins that work."""
    cfg, p = ctx.cfg, ctx.cfg["ports"]
    login, qb = cfg["login"], cfg["qbit"]
    host = cfg.get("hostAddress") or "localhost"
    out = []

    def add(app, key, user, pw, note, check, shown=True):
        if ctx.mine(key):
            return          # the person's own apps keep their own logins; they are not ours to list
        ok = False
        for attempt in range(3):          # a freshly started app on a small machine can be slow to answer
            try:
                ok = bool(check())
            except Exception:  # noqa: BLE001
                ok = False
            if ok:
                break
            time.sleep(6)
        out.append({"app": app, "url": f"http://{host}:{p[key]}" if key in p else "", "user": user, "password": pw,
                    "ok": ok, "note": note})

    def servarr_login(app, ver):
        """Forms login: a good password sets a session cookie that lets the web UI load; a bad one bounces to /login."""
        import http.client
        import urllib.parse as up
        conn = http.client.HTTPConnection(app, ctx.port(app), timeout=20)
        body = up.urlencode({"username": login["username"], "password": login["password"], "rememberMe": "on"})
        conn.request("POST", "/login", body, {"Content-Type": "application/x-www-form-urlencoded"})
        r = conn.getresponse(); r.read()
        cookie = "; ".join(h.split(";")[0] for k, h in r.getheaders() if k.lower() == "set-cookie")
        if "loginFailed" in (r.getheader("Location") or "") or not cookie:
            return False
        conn.request("GET", "/", headers={"Cookie": cookie})
        page = conn.getresponse(); page.read()
        return page.status == 200

    for app, key, ver in (("Sonarr", "sonarr", "v3"), ("Radarr", "radarr", "v3"), ("Prowlarr", "prowlarr", "v1")):
        add(app, key, login["username"], login["password"], "Sign in with the admin login", lambda a=app.lower(), v=ver: servarr_login(a, v))

    def qbit():
        a = Api(ctx.host_url("qbittorrent"), cookies=True, headers={"Referer": ctx.host_url("qbittorrent")})
        st, body = a.call("POST", "/api/v2/auth/login", form={"username": qb["username"], "password": qb["password"]}, raw=True)
        return st in (200, 204) and "Fails" not in body
    add("qBittorrent", "qbittorrent", qb["username"], qb["password"], "Its own login, set on the Downloads step", qbit)

    if cfg["services"].get("jellyfin"):
        def jf():
            a = Api(ctx.host_url("jellyfin"), headers={"Authorization": JF_AUTH})
            return a.post("/Users/AuthenticateByName", {"Username": login["username"], "Pw": login["password"]}).get("AccessToken")
        add("Jellyfin", "jellyfin", login["username"], login["password"], "Admin account", jf)
        if cfg["services"].get("seerr"):
            def sr():
                a = Api(ctx.host_url("seerr"), prefix="/api/v1", cookies=True)
                return a.post("/auth/jellyfin", {"username": login["username"], "password": login["password"]}).get("id")
            add("Seerr", "seerr", login["username"], login["password"], "Sign in with your Jellyfin account", sr)
    if cfg["services"].get("bazarr"):
        def bz():
            a = Api(ctx.host_url("bazarr"), prefix="/api", cookies=True)
            st, _ = a.call("POST", "/system/account", form={"username": login["username"], "password": login["password"]}, params={"action": "login"}, raw=True)
            return st in (200, 204)
        add("Bazarr", "bazarr", login["username"], login["password"], "Same admin login", bz)
    if cfg["services"].get("samba") and (cfg.get("samba") or {}).get("shares"):
        import socket
        sm, port = cfg["samba"], p.get("samba", 445)
        s = socket.socket()
        s.settimeout(3)
        try:
            up = s.connect_ex(("host.docker.internal", port)) == 0
        except OSError:
            up = False
        finally:
            s.close()
        first = sm["shares"][0]["name"].replace(" ", "%20")
        out.append({"app": "File sharing", "url": f"smb://{host}{'' if port == 445 else ':' + str(port)}/{first}", "user": sm["user"], "password": sm["password"],
                    "ok": up, "note": "Open from Windows, Mac or a phone. See the file sharing guide for each device"})
    for key, name in (("homepage", "Homepage"), ("metube", "MeTube"), ("komga", "Komga"), ("mylar3", "Mylar3"), ("scrutiny", "Scrutiny")):
        if cfg["services"].get(key):
            out.append({"app": name, "url": f"http://{host}:{p[key]}", "user": "", "password": "", "ok": True,
                        "note": "No login needed" if key != "komga" else "Create the owner account on first visit"})
    return out


def verify_integrations(ctx, repair=True):
    """Test every link between the apps with the apps' own test endpoints; repair a failed link once, then report.

    Returns [{"name", "ok", "detail", "fixed"}]. Nothing here changes a working setup.
    """
    cfg = ctx.cfg
    out = []
    if ctx.adopt:
        repair = False      # with the person's own apps this only reports; it never writes a setting they chose to keep
    solver = {"byparr": "Byparr", "trawl": "TRAWL"}.get(cfg.get("solver"), "FlareSolverr")

    def run(name, check, fix=None):
        detail, fixed, ok = "", False, False
        for attempt in range(2 if (fix and repair) else 1):
            try:
                detail = check() or ""
                ok = True
            except Exception as e:  # noqa: BLE001 - any failure means the link is not healthy
                detail = (str(e.body) if isinstance(e, ApiError) else str(e))[:160].replace("\n", " ")
                ok = False
            if ok or attempt == 1 or not (fix and repair):
                break
            try:
                fix()
                time.sleep(6)
                fixed = True
            except Exception as e:  # noqa: BLE001
                detail = "repair failed: " + str(getattr(e, "body", e))[:120]
                break
        out.append({"name": name, "ok": ok, "detail": detail, "fixed": fixed and ok})

    sonarr, radarr, prowlarr = ctx.apis.get("sonarr"), ctx.apis.get("radarr"), ctx.apis.get("prowlarr")
    extra = {"sonarr": {"tvCategory": "tv", "recentTvPriority": 0, "olderTvPriority": 0},
             "radarr": {"movieCategory": "movies", "recentMoviePriority": 0, "olderMoviePriority": 0}}

    # Sonarr / Radarr -> qBittorrent
    for app, api in (("Sonarr", sonarr), ("Radarr", radarr)):
        def chk(api=api):
            cl = next(x for x in api.get("/downloadclient") if x["implementation"] == "QBittorrent")
            api.post("/downloadclient/test", cl)
            if not cl.get("enable") or not cl.get("removeCompletedDownloads"):
                raise RuntimeError("client disabled or not set to remove finished torrents")
            return "connected; each torrent is removed after import (no seeding)"
        run(f"{app} to qBittorrent", chk, lambda api=api, app=app: add_qbit(ctx, api, app.lower(), extra[app.lower()]))

    # Prowlarr -> Sonarr / Radarr (and the indexers actually arrived)
    for app, api in (("Sonarr", sonarr), ("Radarr", radarr)):
        def chk(app=app, api=api):
            ap = next(x for x in prowlarr.get("/applications") if x["name"] == app)
            prowlarr.post("/applications/test", ap)
            n = len(api.get("/indexer"))
            if n == 0:
                raise RuntimeError("connected, but no indexers have synced yet")
            return f"connected; {n} indexers synced"
        run(f"Prowlarr to {app}", chk, lambda: prowlarr.post("/command", {"name": "ApplicationIndexerSync"}))

    # Download safety: executables never downloaded, never run
    def chk_safe():
        p = json.loads(qbit_api(ctx).call("GET", "/api/v2/app/preferences", raw=True)[1])
        if not p.get("excluded_file_names_enabled") or "*.exe" not in (p.get("excluded_file_names") or ""):
            raise RuntimeError("qBittorrent is not skipping executable files")
        if p.get("autorun_enabled"):
            raise RuntimeError("qBittorrent is set to run a program when a download finishes")
        for app, api in (("Sonarr", sonarr), ("Radarr", radarr)):
            if SAFETY_CF not in [c["name"] for c in api.get("/customformat")]:
                raise RuntimeError(f"{app} has no executable/crack rule")
        return "qBittorrent skips .exe/.msi/.scr/.bat and other non-media files and runs nothing; releases that advertise them are refused"
    run("Download safety", chk_safe, lambda: apply_qbit_prefs(ctx, qbit_api(ctx)))

    # Prowlarr -> Cloudflare solver (Sonarr/Radarr reach it through the indexers they search via Prowlarr)
    def chk_solver():
        px = next(x for x in prowlarr.get("/indexerProxy") if x["implementation"] == "FlareSolverr")
        import urllib.request as ur
        ur.urlopen("http://solver:8191/", timeout=15).read()           # the container itself must answer
        slow = ""
        try:
            prowlarr.post("/indexerProxy/test", px, timeout=180)      # opens a real page through the solver
        except ApiError as e:
            if "timed out" not in str(e.body).lower():
                raise
            slow = "; slow to answer on this machine"                  # reachable, but the test page took too long
        tag = px["tags"][0] if px.get("tags") else None
        n = sum(1 for i in prowlarr.get("/indexer") if tag in i.get("tags", []))
        return f"{solver} reachable; {n} indexers are routed through it for Sonarr and Radarr searches{slow}"

    def fix_solver():
        px = next(x for x in prowlarr.get("/indexerProxy") if x["implementation"] == "FlareSolverr")
        for f in px["fields"]:
            if f["name"] == "host":
                f["value"] = "http://solver:8191/"
        prowlarr.put(f"/indexerProxy/{px['id']}", px, params={"forceSave": "true"}, timeout=120)
    run(f"Prowlarr to {solver}", chk_solver, fix_solver)

    # Bazarr -> Sonarr / Radarr
    if cfg["services"].get("bazarr"):
        def chk_bazarr(which):
            bz = bazarr_api(ctx)
            st = bz.get("/system/status").get("data", {})
            s = bz.get("/system/settings")
            if not s["general"].get(f"use_{which}") or not st.get(f"{which}_version"):
                raise RuntimeError(f"{which.title()} is not connected")
            issues = [h.get("issue", "") for h in (bz.get("/system/health").get("data") or [])]
            if issues:
                raise RuntimeError("; ".join(issues)[:150])
            live = [p["name"] for p in (bz.get("/providers") or {}).get("data", []) if p.get("status") == "Good"]
            if len(live) < 2:
                raise RuntimeError(f"only {len(live)} subtitle providers are working")
            return f"connected to {which.title()} {st.get(which + '_version')}; English required; {len(live)} subtitle providers working"
        for which in ("sonarr", "radarr"):
            run(f"Bazarr to {which.title()}", lambda w=which: chk_bazarr(w), lambda: setup_bazarr(ctx))

    if cfg["services"].get("bazarr") and cfg["services"].get("jellyfin"):
        def chk_bz_jf():
            bz = bazarr_api(ctx)
            if not bz.get("/system/settings")["general"].get("use_jellyfin"):
                raise RuntimeError("Jellyfin link is off")
            r = bz.post("/jellyfin/test-connection", params={"url": "http://jellyfin:8096", "apikey": jellyfin_key(ctx)})
            if not r.get("success"):
                raise RuntimeError("Jellyfin did not accept the connection")
            return f"connected to Jellyfin {r.get('version', '')}; refreshes after every subtitle"
        run("Bazarr to Jellyfin", chk_bz_jf, lambda: setup_bazarr(ctx))

    # Sonarr / Radarr -> Jellyfin (library refresh after every import)
    if cfg["services"].get("jellyfin"):
        for app, api in (("Sonarr", sonarr), ("Radarr", radarr)):
            def chk(api=api):
                n = next(x for x in api.get("/notification") if x["implementation"] == "MediaBrowser")
                api.post("/notification/test", n)
                return "connected; the library refreshes after every import"
            run(f"{app} to Jellyfin", chk, lambda app=app: ensure_jellyfin_link(ctx, app.lower()))

        # Seerr -> Sonarr / Radarr / Jellyfin
        if cfg["services"].get("seerr"):
            def chk_seerr():
                login = cfg["login"]
                se = Api(ctx.host_url("seerr"), prefix="/api/v1", cookies=True)
                se.post("/auth/jellyfin", {"username": login["username"], "password": login["password"]})
                for kind, port in (("sonarr", 8989), ("radarr", 7878)):
                    conf = (se.get(f"/settings/{kind}") or [None])[0]
                    if not conf:
                        raise RuntimeError(f"{kind.title()} is not set up in Seerr")
                    se.post(f"/settings/{kind}/test", {"hostname": conf["hostname"], "port": conf["port"], "apiKey": conf["apiKey"],
                                                        "useSsl": False, "baseUrl": ""})
                libs = [x for x in se.get("/settings/jellyfin/library") if x.get("enabled")]
                if not libs:
                    raise RuntimeError("no Jellyfin libraries enabled")
                return f"connected to Sonarr, Radarr and {len(libs)} Jellyfin libraries; requests route by language"
            run("Seerr to Sonarr, Radarr and Jellyfin", chk_seerr, (lambda: setup_seerr(ctx)) if hasattr(ctx, "profiles_sonarr") else None)

    if livetv_on(cfg):
        def chk_livetv():
            api = jellyfin_admin(ctx)
            conf = api.get("/System/Configuration/livetv") or {}
            if not any(t.get("FriendlyName") == LIVETV_NAME for t in conf.get("TunerHosts", [])):
                raise RuntimeError("the channel list is not added to Jellyfin")
            n = livetv_channels(api)
            if not n:
                refresh_guide(api)
                raise RuntimeError("Jellyfin has not loaded any channels yet")
            return f"{n} channels available in Jellyfin, Live TV; program guides: {len(conf.get('ListingProviders', []))}"
        run("Jellyfin Live TV and sports", chk_livetv, lambda: setup_livetv(ctx, rebuild=False))

    # Health and folders as the apps themselves report them
    for app, api in (("Sonarr", sonarr), ("Radarr", radarr)):
        def chk_health(api=api):
            try:
                api.post("/command", {"name": "CheckHealth"})
                time.sleep(4)
            except ApiError:
                pass
            h = api.get("/health")
            errs = [x["message"] for x in h if x.get("type") == "error"]
            if errs:
                raise RuntimeError("; ".join(errs)[:160])
            roots = api.get("/rootfolder")
            bad = [r["path"] for r in roots if not r.get("accessible")]
            if bad:
                raise RuntimeError("folder not reachable: " + ", ".join(bad))
            warn = [x["message"] for x in h if x.get("type") == "warning"]
            return f"no errors; {len(roots)} folders reachable" + (f"; note: {warn[0][:90]}" if warn else "")
        run(f"{app} health and folders", chk_health)
    return out
