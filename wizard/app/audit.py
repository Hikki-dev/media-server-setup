"""The "what would change" preview: names every settings group the setup touches and turns the writes that a dry run captured into
rows a person can read (what their app holds now, and what the setup would set)."""
import json

# id -> (app, title, plain explanation, on by default when the app is already yours, caution shown in red or "")
GROUPS = {
    "sonarr.sizes": ("Sonarr", "How big a TV episode can be", "Sets a size range for each video quality so huge files are not downloaded.", True, ""),
    "sonarr.media": ("Sonarr", "How finished downloads are filed", "Saves disk space by linking files instead of copying them, tidies empty folders and keeps subtitle files.", True, ""),
    "sonarr.downloads": ("Sonarr", "What happens when a download finishes", "Files it automatically, and tries another copy if a download fails.", True, ""),
    "sonarr.delay": ("Sonarr", "Prefer torrents, start right away", "Looks at torrents first and does not wait before starting a download.", True, "Replaces your current wait times. Skip this if you also use Usenet."),
    "sonarr.indexer": ("Sonarr", "How often it looks for new episodes", "How many minutes between checks for new releases.", True, ""),
    "sonarr.naming": ("Sonarr", "How episode files and folders are named", "Gives every episode and season folder a clean, matching name.", True, "Only new files get the new names. Your existing files are not renamed unless you ask Sonarr to."),
    "sonarr.profiles": ("Sonarr", "Quality choices (what Sonarr is allowed to download)", "Ready-made quality choices built from your answers: picture quality, language, subtitles and size.", True, ""),
    "sonarr.dropstock": ("Sonarr", "Delete the quality choices Sonarr came with", "Removes the standard choices nobody uses.", False, "This deletes things. Anything currently in use is kept."),
    "sonarr.roots": ("Sonarr", "Add the TV and anime folders from this setup", "Tells Sonarr where to keep your shows.", False, "These folder names only make sense for the NEW apps. Leave this off for your own Sonarr unless it can see the same folders."),
    "sonarr.qbit": ("Sonarr", "Remove a torrent after it is filed", "Your connection to your download app stays the same. Finished torrents are removed so nothing keeps uploading.", True, ""),
    "sonarr.auth": ("Sonarr", "Password for the Sonarr web page", "Asks for the username and password you chose here.", False, "Changes who can open Sonarr."),
    "radarr.sizes": ("Radarr", "How big a movie can be", "Sets a size range for each video quality so huge files are not downloaded.", True, ""),
    "radarr.media": ("Radarr", "How finished downloads are filed", "Saves disk space by linking files instead of copying them, tidies empty folders and keeps subtitle files.", True, ""),
    "radarr.downloads": ("Radarr", "What happens when a download finishes", "Files it within a minute, and tries another copy if a download fails.", True, ""),
    "radarr.delay": ("Radarr", "Prefer torrents, start right away", "Looks at torrents first and does not wait before starting a download.", True, "Replaces your current wait times. Skip this if you also use Usenet."),
    "radarr.indexer": ("Radarr", "Release checks, biggest movie, subtitles in the video", "How often it looks for new releases, the biggest movie file it accepts, and whether it accepts releases with English subtitles built into the picture.", True, ""),
    "radarr.naming": ("Radarr", "How movie files and folders are named", "Gives every movie and its folder a clean, matching name.", True, "Only new files get the new names."),
    "radarr.profiles": ("Radarr", "Quality choices (what Radarr is allowed to download)", "Ready-made quality choices built from your answers: picture quality, language, subtitles and size.", True, ""),
    "radarr.dropstock": ("Radarr", "Delete the quality choices Radarr came with", "Removes the standard choices nobody uses.", False, "This deletes things. Anything currently in use is kept."),
    "radarr.roots": ("Radarr", "Add the movie folders from this setup", "Tells Radarr where to keep your movies.", False, "These folder names only make sense for the NEW apps. Leave this off for your own Radarr unless it can see the same folders."),
    "radarr.qbit": ("Radarr", "Remove a torrent after it is filed", "Your connection to your download app stays the same. Finished torrents are removed so nothing keeps uploading.", True, ""),
    "radarr.auth": ("Radarr", "Password for the Radarr web page", "Asks for the username and password you chose here.", False, "Changes who can open Radarr."),
    "qbittorrent.prefs": ("qBittorrent", "Uploading, speed limits and safety", "Stops uploading after a download, sets speed and queue limits, finds more sources, and blocks program files (like .exe) from ever being downloaded.", True, ""),
    "qbittorrent.categories": ("qBittorrent", "Folders for TV and movies", "Creates a TV folder and a Movies folder inside your download app.", False, "These folder names only make sense for the NEW apps. Leave this off for your own qBittorrent."),
    "prowlarr.solver": ("Prowlarr", "Helper for protected websites", "Lets Prowlarr open search sites that make you prove you are not a robot.", True, ""),
    "prowlarr.apps": ("Prowlarr", "Share search sites with Sonarr and Radarr", "Prowlarr hands its list of search sites to Sonarr and Radarr automatically.", True, ""),
    "prowlarr.indexers": ("Prowlarr", "Search sites to find downloads", "Adds popular free search sites that suit your choices, tests each one, and removes the ones that do not answer.", True, "Only sites this setup adds can be removed. Sites you added yourself are never removed."),
    "prowlarr.auth": ("Prowlarr", "Password for the Prowlarr web page", "Asks for the username and password you chose here.", False, "Changes who can open Prowlarr."),
    "jellyfin.libraries": ("Jellyfin", "Add Movies, TV and Anime libraries", "Creates the libraries for the folders chosen in this setup.", False, "These folder names only make sense for the NEW apps. Leave this off for your own Jellyfin unless it can see the same folders."),
    "jellyfin.links": ("Jellyfin", "Update Jellyfin when something is added", "Sonarr and Radarr tell Jellyfin to look for new files. A link you already have is left as it is.", True, ""),
    "jellyfin.encoding": ("Jellyfin", "Use the graphics chip for smoother playback", "Uses your graphics chip (after testing it works) to convert video quickly, and fixes washed-out colours from HDR video.", True, "Replaces your current playback conversion settings."),
    "jellyfin.tasks": ("Jellyfin", "Switch off slow background jobs", "Stops jobs most people never notice (chapter pictures, scrub previews) that slow the computer down, and keeps the database tidy.", True, ""),
    "jellyfin.network": ("Jellyfin", "Network settings", "Tells Jellyfin which devices at home count as local, turns off automatic router changes, and trusts the other apps here.", False, "Changes how devices connect to Jellyfin."),
    "jellyfin.server": ("Jellyfin", "General server settings", "Language for movie details, shows extras inside seasons, allows Quick Connect sign-in.", True, ""),
    "jellyfin.library": ("Jellyfin", "How libraries are scanned", "Notices new files at once, skips slow picture extraction, and sets the language for movie details.", True, "Applies to every library."),
    "jellyfin.user": ("Jellyfin", "Subtitle and playback habits for your account", "Shows subtitles only when the spoken language is not yours, plays the next episode automatically, and allows video conversion.", True, "Changes the settings of the account used for this setup."),
    "livetv.setup": ("Jellyfin", "Live TV and sports channels", "Adds the channel list and TV guide, pins your local channels, and puts Live TV on everyone's home page.", True, "Adds to your Jellyfin. Any Live TV you already set up is left alone."),
    "seerr.defaults": ("Seerr", "Connect Seerr to Sonarr and Radarr", "Only added when Seerr has no connection yet. A connection you already have is left as it is.", True, ""),
    "seerr.routes": ("Seerr", "Send requests to the right quality choice by language", "A request for a Tamil or Korean title goes to the matching quality choice, and anime goes to the anime one.", True, "Needs the quality choices above. Your own request rules are kept."),
    "seerr.perms": ("Seerr", "What new people may do", "New users can make requests, and their requests start downloading without waiting for approval.", False, "Changes what new users are allowed to do."),
    "bazarr.links": ("Bazarr", "Connect Bazarr to your other apps", "Links Bazarr to Sonarr, Radarr and Jellyfin. A link you already have is left as it is.", True, ""),
    "bazarr.paths": ("Bazarr", "Where Bazarr looks for your files", "Tells Bazarr the folders chosen in this setup.", False, "These folder names only make sense for the NEW apps. Leave this off for your own Bazarr."),
    "bazarr.languages": ("Bazarr", "Subtitle languages", "English is always wanted, plus any other languages you picked.", True, ""),
    "bazarr.providers": ("Bazarr", "Where subtitles come from", "Free subtitle websites that work without an account, plus any you gave a login for.", True, ""),
    "bazarr.tuning": ("Bazarr", "How Bazarr searches for subtitles", "How often it searches, how good a match must be, replacing poor subtitles with better ones, weekly backups.", True, ""),
    "notify.setup": ("Notifications", "Messages to your phone or chat app", "Sends you a message when something is added or goes wrong.", True, ""),
    "other": ("Other", "Other small settings", "A few settings that do not belong to any group above.", True, ""),
}
# a group that depends on another one: when the other is kept as the person has it, this one is left alone too
DEPENDS = {"seerr.routes": ["sonarr.profiles", "radarr.profiles"]}
IGNORE = {"tags", "id", "resource", "infoLink", "presets", "implementationName", "message", "link", "helpText", "helpLink", "hidden", "advanced",
          "order", "type", "selectOptionsProviderAction", "isFloat", "privacy", "unit", "label"}

FIELD = {"host": "Address", "port": "Port", "username": "Username", "password": "Password", "apiKey": "Access key", "ip": "Address",
         "tvCategory": "TV folder name", "movieCategory": "Movies folder name", "renameEpisodes": "Rename episodes",
         "renameMovies": "Rename movies", "standardEpisodeFormat": "Episode file name", "dailyEpisodeFormat": "Daily show file name",
         "animeEpisodeFormat": "Anime episode file name", "standardMovieFormat": "Movie file name", "seriesFolderFormat": "Show folder name",
         "seasonFolderFormat": "Season folder name", "movieFolderFormat": "Movie folder name", "copyUsingHardlinks": "Link files instead of copying",
         "recycleBin": "Recycle bin folder", "extraFileExtensions": "Extra file types kept (like subtitles)", "rssSyncInterval": "Minutes between checks",
         "maximumSize": "Biggest file allowed (MB)", "authenticationRequired": "Ask for a login", "minSize": "Smallest size", "maxSize": "Largest size",
         "preferredSize": "Preferred size", "max_ratio_enabled": "Stop uploading at a ratio", "max_ratio": "Upload ratio limit",
         "max_seeding_time_enabled": "Stop uploading after a time", "queueing_enabled": "Limit how many download at once",
         "max_active_downloads": "Downloads at once", "max_active_torrents": "Active torrents at once", "dl_limit": "Download speed limit",
         "up_limit": "Upload speed limit", "save_path": "Download folder", "temp_path": "Unfinished downloads folder",
         "add_trackers_enabled": "Add extra sources automatically", "excluded_file_names_enabled": "Block unwanted file types",
         "excluded_file_names": "Blocked file types", "autorun_enabled": "Run a program when a download finishes", "enableCompletedDownloadHandling": "File finished downloads automatically",
         "autoRedownloadFailed": "Try another copy when a download fails", "preferredProtocol": "Preferred way to download", "torrentDelay": "Wait before torrents (minutes)",
         "usenetDelay": "Wait before Usenet (minutes)", "removeCompletedDownloads": "Remove torrent once filed", "removeFailedDownloads": "Remove failed torrents",
         "enable": "Switched on", "requestTimeout": "Give up after (seconds)", "ServerName": "Server name", "HardwareAccelerationType": "Graphics chip type",
         "EnableHardwareEncoding": "Use graphics chip to convert video", "EnableTonemapping": "Fix washed-out HDR colours", "EnableThrottling": "Pause conversion when ahead",
         "SubtitleMode": "When to show subtitles", "SubtitleLanguagePreference": "Subtitle language", "PreferredMetadataLanguage": "Language for details",
         "enabled_providers": "Subtitle websites", "analytics-enabled": "Send usage statistics", "use_subsync": "Re-time subtitles with the audio",
         "concurrent_jobs": "Jobs at once", "upgrade_subs": "Replace poor subtitles with better ones", "minimum_score": "Smallest match score (TV)",
         "minimum_score_movie": "Smallest match score (movies)", "defaultPermissions": "What new users may do", "activeProfileId": "Quality choice used",
         "activeDirectory": "Folder used", "profileId": "Quality choice"}


def friendly(label):
    import re
    pre = ""
    if ": " in label:
        pre, label = label.split(": ", 1)
        pre += ": "
    label = re.sub(r"^fields\.", "", label)
    label = re.sub(r"\.value$", "", label)
    out = []
    for p in re.split(r"[.]|(?<=[a-z])-(?=[a-z])", label):
        if p in FIELD:
            out.append(FIELD[p])
        else:
            out.append(re.sub(r"(?<=[a-z0-9])(?=[A-Z])|[_]", " ", p).strip().capitalize())
    return pre + " › ".join(out)


def plain_value(v):
    return {"true": "on", "false": "off", "None": "nothing", "null": "nothing", "(not set)": "not set", "(not there)": "not there yet"}.get(v, v)


def short(v, n=70):
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def diff_obj(before, after, path=""):
    """[(setting, what the app holds, what the setup sets)] for one object."""
    rows = []
    if not isinstance(after, dict):
        return [(path or "value", short(before), short(after))] if before != after else []
    before = before if isinstance(before, dict) else {}
    for k, v in after.items():
        if k in IGNORE:
            continue
        bv = before.get(k)
        if isinstance(v, dict) and isinstance(bv, dict):
            rows += diff_obj(bv, v, f"{path}{k}.")
        elif isinstance(v, list) and v and all(isinstance(x, dict) and "name" in x for x in v) and isinstance(bv, list):
            named = {x["name"]: x for x in bv if isinstance(x, dict) and "name" in x}
            for x in v:
                y = named.get(x["name"])
                label = f"{path}{k}.{x['name']}"
                if y is None:
                    rows.append((label, "(not there)", short(x.get("value", x.get("score", x.get("allowed", "added"))))))
                else:
                    rows += diff_obj(y, x, label + ".")
        elif v != bv and not (v in (None, "", []) and bv in (None, "", [])):
            rows.append((f"{path}{k}", short(bv) if bv is not None else "(not set)", short(v)))
    return rows


PATH_NAMES = {"/config/naming": "File and folder naming", "/config/mediamanagement": "Importing and folders",
              "/config/downloadclient": "Download handling", "/config/indexer": "RSS sync and limits", "/config/host": "Login for the web page",
              "/delayprofile": "Delay profile", "/System/Configuration/encoding": "Transcoding", "/System/Configuration/network": "Network",
              "/System/Configuration": "Server", "/settings/main": "Seerr main settings", "/qualitydefinition": "Quality sizes"}


def name_of(obj, path):
    if isinstance(obj, dict):
        for k in ("name", "label", "title", "path"):
            if obj.get(k):
                return str(obj[k])
    base = "/" + "/".join(p for p in path.split("?")[0].strip("/").split("/") if not p.isdigit())
    return PATH_NAMES.get(base, path)


RESOURCE = {"customformat": "ranking rules", "qualityprofile": "quality choices", "indexer": "search sites", "rootfolder": "folders",
            "downloadclient": "download apps", "notification": "connections", "applications": "app links", "indexerProxy": "helpers",
            "VirtualFolders": "libraries", "overrideRule": "request rules", "category": "folders"}


def resource(path):
    for part in path.strip("/").split("/"):
        if part in RESOURCE:
            return RESOURCE[part]
    return ""


def describe(ch):
    d = _describe(ch)
    d["rows"] = [(friendly(a), plain_value(b), plain_value(c)) for a, b, c in d["rows"]]
    return d


def _describe(ch):
    """One captured write -> {kind, what, rows}. kind is create, update, delete or same (nothing would change)."""
    method, path, before, after = ch["method"], ch["path"], ch.get("before"), ch.get("after")
    if path.split("?")[0].rstrip("/") == "/tag" or "/Running/" in path:
        return {"kind": "same", "what": "plumbing", "rows": []}
    if method == "DELETE":
        return {"kind": "delete", "what": name_of(before, path), "rows": []}
    if isinstance(after, dict) and path.endswith("/system/settings") and any(str(k).startswith("settings-") for k in after):
        flat = {}
        for sec, vals in (before or {}).items():
            for k, v in (vals.items() if isinstance(vals, dict) else []):
                flat[f"settings-{sec}-{k}"] = v
        rows = []
        for k, v in after.items():
            if not str(k).startswith("settings-") or "password" in k or "apikey" in k or "api_key" in k:
                continue
            cur = flat.get(k)
            norm = lambda x: ("true" if x else "false") if isinstance(x, bool) else (",".join(map(str, x)) if isinstance(x, list) else str(x))   # noqa: E731
            if cur is None or norm(cur).lower() != norm(v).lower():
                rows.append((k[len("settings-"):], short(cur) if cur is not None else "(not set)", short(v)))
        return {"kind": "update" if rows else "same", "what": "Bazarr settings", "rows": rows}
    if isinstance(after, dict) and "json" in after and path.endswith("setPreferences"):     # qBittorrent preferences
        try:
            after = json.loads(after["json"])
        except ValueError:
            pass
        rows = diff_obj(before if isinstance(before, dict) else {}, after)
        return {"kind": "update" if rows else "same", "what": "qBittorrent preferences", "rows": rows}
    if method == "POST" and isinstance(after, dict) and isinstance(after.get("LibraryOptions"), dict) and isinstance(before, dict):
        rows = diff_obj(before.get("LibraryOptions") or {}, after["LibraryOptions"])
        return {"kind": "update" if rows else "same", "what": "library options", "rows": rows}
    if method == "POST" and isinstance(before, dict) and isinstance(after, dict):       # Jellyfin saves settings with POST
        rows = diff_obj(before, after)
        return {"kind": "update" if rows else "same", "what": name_of(after, path), "rows": rows}
    if method == "POST":
        what = name_of(after, path)
        if isinstance(after, dict) and after.get("category"):
            what = f"category {after['category']}"
        return {"kind": "create", "what": what, "rows": []}
    if isinstance(before, list) and isinstance(after, list):          # a whole list written at once (quality sizes)
        byid = {x.get("id"): x for x in before if isinstance(x, dict)}
        rows, count = [], 0
        for x in after:
            y = byid.get(x.get("id")) or {}
            d = diff_obj(y, x)
            if d:
                count += 1
                rows += [(f"{name_of(x, '')}: {a}", b, c) for a, b, c in d]
        return {"kind": "update" if count else "same", "what": f"{count} of {len(after)} entries", "rows": rows}
    rows = diff_obj(before, after) if before is not None else []
    if before is None:
        return {"kind": "update", "what": name_of(after, path), "rows": []}
    return {"kind": "update" if rows else "same", "what": name_of(after, path), "rows": rows}


def report(rec, wanted=None):
    """The groups a dry run touched, readable. `wanted` limits it to the groups of apps that are the person's own."""
    out = []
    for gid, changes in rec.changes.items():
        meta = GROUPS.get(gid) or GROUPS["other"]
        if wanted is not None and meta[0].lower() not in wanted and gid != "other":
            continue
        items = [describe(c) for c in changes]
        items = [i for i in items if i["kind"] != "same"]
        rows = sum(len(i["rows"]) for i in items)
        creates = [i["what"] for i in items if i["kind"] == "create"]
        deletes = [i["what"] for i in items if i["kind"] == "delete"]
        updates = [i for i in items if i["kind"] == "update"]
        parts = []
        if updates:
            parts.append(f"{rows or len(updates)} thing{'s' if (rows or len(updates)) != 1 else ''} different")
        for word, kind in (("will be added", "create"), ("will be removed", "delete")):
            counts = {}
            for i, ch in zip(items, [c for c in changes if describe(c)["kind"] != "same"]):
                if i["kind"] == kind:
                    counts[resource(ch["path"])] = counts.get(resource(ch["path"]), 0) + 1
            for res, n in counts.items():
                parts.append(f"{n} {res} {word}".replace("  ", " "))
        out.append({"id": gid, "app": meta[0], "title": meta[1], "why": meta[2], "default": meta[3], "caution": meta[4],
                    "same": not items, "summary": ", ".join(parts) if parts else "already set the way this setup would do it",
                    "changes": [{"kind": i["kind"], "what": i["what"], "rows": i["rows"][:14], "more": max(0, len(i["rows"]) - 14)}
                                for i in items[:40]],
                    "depends": DEPENDS.get(gid, [])})
    out.sort(key=lambda g: (list(GROUPS).index(g["id"]) if g["id"] in GROUPS else 999))
    return out
