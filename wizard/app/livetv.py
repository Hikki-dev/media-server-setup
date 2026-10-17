"""Live TV and sports channel lists for Jellyfin.

Channels come from the community iptv-org lists (free, publicly available streams) and, optionally, the person's own
provider. Dead streams are filtered out, guide ids are matched to the public EPG Share guides, and the result is one
M3U file Jellyfin reads as an M3U tuner. Shared by the wizard (first build) and the regional service (daily refresh).
"""
import collections
import concurrent.futures as cf
import gzip
import http.client
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request as ur

API = "https://iptv-org.github.io/api/"
LISTS = "https://iptv-org.github.io/iptv/"
GUIDES = "https://epgshare01.online/epgshare01/"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
NO_VERIFY = ssl.create_default_context()
NO_VERIFY.check_hostname, NO_VERIFY.verify_mode = False, ssl.CERT_NONE   # many stream hosts have bad certificates; players ignore that too
HIDDEN_CATEGORIES = {"xxx"}
SHORTENER = re.compile(r"(^|\.)(tinyurl\.com|2x2\.me|bit\.ly|t\.co|goo\.gl|is\.gd|cutt\.ly|rebrand\.ly|shorturl\.at)$", re.I)
ENGLISH_COUNTRIES = ["us", "uk", "ca", "au", "nz", "ie", "in", "sg", "lk", "za", "ph", "my", "pk", "hk"]
ENGLISH_EXCLUDE = (r"german|germany|deutsch|ital(y|ia|iano)|poland|polska|polski|russia|czech|slovak|hungar|magyar|turk|romania|bulgar|"
                   r"serbia|croatia|greece|greek|arab|latin ?america|latam|espa[nñ]ol|en espa|france|fran[cç]ais|spain|portug|brasil|brazil|"
                   r"scandinavia|nordic|danish|swedish|norwegian|finnish|dutch|netherlands|korea|japan|china|chinese|thai|indonesia|vietnam|"
                   r"hindi|tamil|telugu|malayalam|kannada|bangla|bengali|marathi|punjabi|gujarati|urdu|nepal|\bcee\b|balkan|israel|iran|africa(?! ?n? ?english)|strongman")
# Official, verified YouTube channels of broadcasters that go live there. None streams round the clock: each programme (bulletin,
# show, event) is its own live video, so the channels play while the broadcaster is live and show as unavailable between programmes.
YOUTUBE_LIVE = [
    # "bulletins": the usual daily slots (Sri Lanka time, minutes long, title). The channels go live for each bulletin; the guide shows them.
    {"logoId": "AdaDerana24x7.lk", "id": "UCCK3OZi788Ok44K97WAhLKQ", "name": "Ada Derana News", "country": "LK", "note": "bulletins and programmes",
     "bulletins": [("12:00", 45, "Midday News Bulletin"), ("18:55", 60, "Prime Time News Bulletin"), ("22:00", 45, "Late Night News Bulletin")]},
    {"logoId": "TVDerana.lk", "id": "@TVDeranaOfficial", "name": "TV Derana", "country": "LK", "note": "when live"},
    {"logoId": "News1st.lk", "id": "UCgnFSj7jQffD5V5m05j4dPw", "name": "News 1st", "country": "LK", "note": "Sinhala 7 PM, English 9 PM",
     "bulletins": [("12:00", 45, "Lunch Time Sinhala News"), ("19:00", 45, "Prime Time Sinhala News (7 PM)"),
                   ("21:00", 60, "Prime Time English News (9 PM)"), ("22:00", 45, "Prime Time Sinhala News (10 PM)")]},
    {"logoId": "News1st.lk", "id": "UCJpM66ypgqDMT-buL1ALuLA", "name": "News 1st Tamil", "country": "LK", "note": "Tamil bulletins",
     "bulletins": [("07:00", 45, "Breakfast News (Tamil)"), ("13:00", 45, "Lunch Time News (Tamil)"),
                   ("20:00", 45, "Prime Time News (Tamil, 8 PM)"), ("22:00", 45, "Prime Time News (Tamil, 10 PM)")]},
    {"logoId": "SirasaTV.lk", "id": "UCLNz9bgiJfM3ImTtYDOt8Ew", "name": "Sirasa TV", "country": "LK", "note": "when live"},
    {"logoId": "TV1.lk", "id": "@TV1SriLanka", "name": "TV1", "country": "LK", "note": "when live"},
    {"logoId": "ITN.lk", "id": "@ITNSriLanka", "name": "ITN", "country": "LK", "note": "when live"},
    {"logoId": "Swarnavahini.lk", "id": "@SwarnavahiniTV", "name": "Swarnavahini", "country": "LK", "note": "when live"},
]
YT_BASE = "http://regional:9120/yt/"      # the regional service looks up the current stream address on demand
MAX_GUIDE_COUNTRIES = 14      # each guide is a few MB of XML; beyond this Jellyfin matches names on its own


NET_ERRORS = (OSError, ValueError, http.client.HTTPException, urllib.error.URLError, EOFError)


def fetch(url, timeout=45):
    for attempt in range(3):      # public mirrors drop connections now and then
        try:
            with ur.urlopen(ur.Request(url, headers=UA), timeout=timeout) as r:
                data = r.read()
            return gzip.decompress(data) if data[:2] == b"\x1f\x8b" else data
        except NET_ERRORS:
            if attempt == 2:
                raise
            time.sleep(2)


def catalog(cache_dir=None, max_age=86400):
    """Countries, regions, categories, languages and which countries have a ready-made guide."""
    cache = os.path.join(cache_dir, "livetv-catalog.json") if cache_dir else None
    if cache and os.path.exists(cache) and time.time() - os.path.getmtime(cache) < max_age:
        try:
            return json.load(open(cache))
        except ValueError:
            pass
    get = lambda n: json.loads(fetch(API + n + ".json"))
    countries = [{"code": c["code"], "name": c["name"], "flag": c.get("flag", ""), "languages": c.get("languages", [])}
                 for c in get("countries")]
    langs = {l["code"]: l["name"] for l in get("languages")}
    used = sorted({l for c in countries for l in c["languages"]})
    cats = [{"id": c["id"], "name": c["name"]} for c in get("categories") if c["id"] not in HIDDEN_CATEGORIES]
    regions = [{"code": r["code"], "name": r["name"], "countries": r["countries"]} for r in get("regions")
               if r["code"] not in ("INT", "WW") and r["countries"]]
    try:
        index = fetch(GUIDES, 30).decode("utf8", "ignore")
        guides = sorted(set(re.findall(r"epg_ripper_([A-Z]{2})\d", index)))
    except NET_ERRORS:
        guides = []
    out = {"youtube": YOUTUBE_LIVE, "countries": countries, "regions": regions, "categories": cats, "guides": guides,
           "languages": [{"code": l, "name": langs.get(l, l)} for l in used]}
    if cache:
        os.makedirs(cache_dir, exist_ok=True)
        json.dump(out, open(cache, "w"))
    return out


def parse_m3u(text):
    out, info = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            attr = dict(re.findall(r'([\w-]+)="([^"]*)"', line))
            name = line.rsplit(",", 1)[-1].strip()
            info = {"id": attr.get("tvg-id", ""), "logo": attr.get("tvg-logo", ""), "group": attr.get("group-title", ""),
                    "name": name, "tvgName": attr.get("tvg-name", "")}
        elif line and not line.startswith("#") and info:
            info["url"] = line
            out.append(info)
            info = None
    return out


def _get(url, limit, timeout):
    with ur.urlopen(ur.Request(url, headers=UA), timeout=timeout, context=NO_VERIFY) as r:
        return r.read(limit)


def _first_ref(text):
    """First media or variant address in an HLS playlist (None if it lists none)."""
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line
    return None


def alive(url, detail=False, strict=True):
    """True only if the stream really starts: an HLS channel must hand over its playlist AND a real video chunk quickly.
    (Checking just the playlist lets through channels that refuse their chunks, which then never start in Jellyfin.)
    With detail=True a refusal (HTTP 401/403/451, often a region block) is reported as "blocked"."""
    refused = False
    for attempt in range(2):
        try:
            t0 = time.time()
            head = _get(url, 200_000, 12)
            if head.lstrip()[:7] == b"#EXTM3U":
                text, base = head.decode("utf8", "ignore"), url
                for _ in range(2):                      # master playlist -> media playlist -> first chunk
                    ref = _first_ref(text)
                    if not ref:
                        return False
                    nxt = urllib.parse.urljoin(base, ref)
                    if ".m3u8" in nxt.split("?")[0].lower() and "EXT-X-STREAM-INF" in text:
                        base, text = nxt, _get(nxt, 200_000, 12).decode("utf8", "ignore")
                        continue
                    break
                refs = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
                if not refs:
                    return False
                seg = urllib.parse.urljoin(base, refs[-1])     # the newest chunk: what a player asks for first on a live stream
                t1 = time.time()
                got = len(_get(seg, 400_000 if strict else 65_536, 10 if strict else 20))
                if got < 1024:
                    return False
                if strict and (time.time() - t0 > 9 or (got >= 200_000 and got / max(time.time() - t1, 0.05) < 250_000)):
                    return False                        # too slow to start comfortably or to keep up (under ~2 Mbit/s)
                return True
            if ".m3u8" not in url.split("?")[0].lower() and len(head) > 0:
                return True
        except urllib.error.HTTPError as e:
            refused = e.code in (401, 403, 451)
        except NET_ERRORS:
            pass
        time.sleep(1.5)
    return "blocked" if (detail and refused) else False


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _probe_safe(probe):
    """The relay can restart under load: a failed probe means 'not proven', never a crash. DASH (.mpd) is not relayed."""
    def run(e):
        if ".mpd" in e["url"].split("?")[0].lower():
            return None
        try:
            return probe(e["url"])
        except Exception:  # noqa: BLE001
            return None
    return run


def build(sel, out_path=None, check=True, deadline=None, cat=None, guides=True, log=lambda m: None, vpn_probe=None, vpn_base="http://regional:9120"):
    """Fetch, merge, filter and (optionally) write the playlist. Returns stats and the guide URLs for Jellyfin."""
    cat = cat or catalog()
    names = {c["id"]: c["name"].lower() for c in cat["categories"]}
    wanted = {names.get(c, c).lower() for c in sel.get("categories") or []}
    entries, errors = [], []

    def add(url, filt=None, tag=None, custom=False, rx=None, both=False):
        try:
            for e in parse_m3u(fetch(url).decode("utf8", "ignore")):
                groups = {g.strip().lower() for g in e["group"].split(";")}
                if groups & HIDDEN_CATEGORIES:
                    continue
                if both and filt and rx:                       # category AND name pattern
                    if not (groups & filt and rx.search(e["name"])):
                        continue
                elif (filt or rx) and not ((filt and groups & filt) or (rx and rx.search(e["name"]))):
                    continue
                e["custom"], e["cc"] = custom, tag
                entries.append(e)
        except NET_ERRORS as ex:
            errors.append(f"{url.rsplit('/', 1)[-1]}: {ex}")

    if sel.get("rules"):
        # rules: each one picks channels; the result is their union. A rule is a country, a language (optionally narrowed by
        # categories and/or a name pattern) or a category narrowed by a name pattern.
        for r in sel["rules"]:
            rx = re.compile(r["nameRegex"], re.I) if r.get("nameRegex") else None
            cats_ = {names.get(c, c).lower() for c in r.get("categories") or []} or None
            if r.get("country"):
                add(f"{LISTS}countries/{r['country'].lower()}.m3u", None, r["country"])
            elif r.get("language"):
                add(f"{LISTS}languages/{r['language']}.m3u", cats_, None, rx=rx, both=bool(r.get("both"))) if (cats_ or rx) else add(f"{LISTS}languages/{r['language']}.m3u")
            elif r.get("category"):
                add(f"{LISTS}categories/{r['category']}.m3u", None, None, rx=rx)
    else:
        for cc in sel.get("countries") or []:
            add(f"{LISTS}countries/{cc.lower()}.m3u", wanted or None, cc)
        for c in sel.get("extraCategories") or []:
            add(f"{LISTS}categories/{c}.m3u")
        for lang in sel.get("languages") or []:
            add(f"{LISTS}languages/{lang}.m3u")
    if sel.get("channelIds"):
        wanted_ids = set(sel["channelIds"])
        try:
            idlogos = {}
            for x in json.loads(fetch(API + "logos.json")):
                idlogos.setdefault(x["channel"], x["url"])
            for s in json.loads(fetch(API + "streams.json")):
                if s.get("channel") in wanted_ids:
                    cid = s["channel"]
                    grp = "Kids" if re.search(r"cartoon|toonami|boomerang|adultswim|disney|nick|pogo|smurf", cid, re.I) else \
                        "News" if re.search(r"news", cid, re.I) else "Sports" if re.search(r"sport|ten|cricket|barca|f1", cid, re.I) else "Entertainment"
                    entries.append({"id": cid, "logo": idlogos.get(cid, ""), "group": grp, "name": s.get("title") or cid,
                                    "tvgName": "", "url": s["url"], "custom": False, "cc": cid.rsplit(".", 1)[-1].upper()})
        except NET_ERRORS as ex:
            errors.append(f"streams: {ex}")
    names = {y["id"]: y for y in YOUTUBE_LIVE}
    logos = {}
    if sel.get("youtube"):
        try:
            for x in json.loads(fetch(API + "logos.json")):
                logos.setdefault(x["channel"], x["url"])
        except NET_ERRORS:
            pass
    for ref in sel.get("youtube") or []:
        y = names.get(ref)
        if y:
            entries.append({"id": "", "logo": logos.get(y.get("logoId"), ""), "group": "News" if "news" in y["name"].lower() else "Entertainment",
                            "name": f"{y['name']} (YouTube)", "tvgName": "", "url": YT_BASE + ref, "custom": True, "cc": y["country"],
                            "bulletins": y.get("bulletins")})
    custom = (sel.get("custom") or {}).get("m3u", "").strip()
    if custom:
        add(custom, custom=True)
    seen, uniq = set(), []
    for e in entries:
        if e["url"] not in seen:
            seen.add(e["url"])
            uniq.append(e)
    uniq = [e for e in uniq[:2500] if not SHORTENER.search(urllib.parse.urlparse(e["url"]).netloc)]    # link shorteners redirect unpredictably
    if sel.get("english"):
        # "English" language lists also carry foreign feeds of English-language brands (Nickelodeon Germany, Disney Poland...): drop those
        bad = re.compile((sel.get("excludeRegex") or ENGLISH_EXCLUDE) + (("|" + sel["excludeExtra"]) if sel.get("excludeExtra") else ""), re.I)
        ok_cc = {c.lower() for c in sel.get("allowedCountries") or ENGLISH_COUNTRIES}
        local_ = set(sel.get("local") or [])

        def english(e):
            if e.get("custom") or e.get("cc") in local_:
                return True
            m = re.search(r"\.([a-z]{2})(?:@|$)", e["id"] or "")
            return not bad.search(e["name"]) and (not m or m.group(1) in ok_cc)
        uniq = [e for e in uniq if english(e)]
    dead = 0
    # A busy server makes good streams time out. While the server is busy, remember what passed in the last 30 hours and keep it when a check merely fails.
    cache_file = os.path.join(os.path.dirname(out_path), "alive.json") if out_path else None
    try:
        seen = json.load(open(cache_file)) if cache_file else {}
    except (OSError, ValueError):
        seen = {}
    now_ = time.time()
    busy = os.getloadavg()[0] > 2 * (os.cpu_count() or 2)      # only a busy server makes good streams time out: otherwise a failure is real
    fresh = lambda u: busy and now_ - (seen.get(u) or {}).get("t", 0) < 30 * 3600    # noqa: E731
    if check and uniq:
        todo = [e for e in uniq if not e["custom"]]
        with cf.ThreadPoolExecutor(16) as pool:      # gentle on a small server
            futs = {pool.submit(alive, e["url"], bool(vpn_probe), False): e for e in todo}
            try:
                for f in cf.as_completed(futs, timeout=deadline):
                    futs[f]["ok"] = f.result()
            except cf.TimeoutError:
                for f in futs:
                    f.cancel()
        for e in todo:      # failed or timed out now, but passed recently: trust the earlier result
            if e.get("ok") in (False, None) and fresh(e["url"]):
                e["ok"], e["sticky"] = ("blocked" if seen[e["url"]].get("via") else True), True
        blocked = [e for e in uniq if e.get("ok") == "blocked"]
        if vpn_probe and blocked:      # channels that refuse this country: keep the ones that play through a VPN exit
            import viaproxy
            with cf.ThreadPoolExecutor(4) as pool:      # gentle: the relay is a small service
                for e, exit_ in zip(blocked, pool.map(_probe_safe(vpn_probe), blocked)):
                    if not exit_ and fresh(e["url"]):
                        exit_, e["sticky"] = (seen.get(e["url"]) or {}).get("via"), True
                    if exit_:
                        e["raw"] = e["url"]
                        e["url"], e["ok"], e["via"] = f"{vpn_base}/via/{exit_}/{viaproxy.enc(e['url'])}.m3u8", True, exit_
        keep = [e for e in uniq if e["custom"] or e.get("ok", True) is True or e.get("ok") is None]    # not checked in time: keep, the daily refresh checks again
        # second pass, a few at a time so the measurement is not limited by our own downloads: drop channels too slow to start well
        local_cc = set(sel.get("local") or [])
        wanted = [k.lower() for k in sel.get("keep") or []]
        fast = [e for e in keep if not e["custom"] and not e.get("via") and e.get("ok") is True and e.get("cc") not in local_cc
                and not any(k in e["name"].lower() for k in wanted)]
        with cf.ThreadPoolExecutor(4) as pool:
            for e, ok2 in zip(fast, pool.map(lambda x: alive(x["url"], False, True), fast)):
                if not ok2:
                    if fresh(e["url"]):
                        e["sticky"] = True
                    else:
                        e["ok"] = False
        keep = [e for e in keep if e.get("ok", True) is not False]
        if cache_file:
            for e in keep:
                if not e["custom"] and e.get("ok") is True and not e.get("sticky"):
                    seen[e.get("raw") or e["url"]] = {"t": now_, "via": e.get("via")}
            seen = {u: v for u, v in seen.items() if now_ - v["t"] < 14 * 86400}
            try:
                os.makedirs(os.path.dirname(cache_file), exist_ok=True)
                json.dump(seen, open(cache_file, "w"))
            except OSError:
                pass
        dead = len(uniq) - len(keep)
        uniq = keep
    # a huge channel list makes Jellyfin's Live TV pages slow, so keep the best: local, wanted brands, your countries, then the rest
    keep = [k.lower() for k in sel.get("keep") or []]
    countries_sel, local_sel = set(sel.get("countries") or []), set(sel.get("local") or [])

    def rank(e):
        if e.get("cc") in local_sel or e.get("custom"):
            return 0
        if any(k in e["name"].lower() for k in keep):
            return 1
        return 2 if e.get("cc") in countries_sel else 3
    prefer = set(sel.get("preferUrls") or [])       # a better feed of a channel that has several: listed first, so it is the one kept
    uniq.sort(key=lambda e: (rank(e), 0 if e["url"] in prefer else 1))
    seen_ch, one = set(), []
    for e in uniq:     # the same channel offered by several streams is listed once (the first that passed, which ranks best)
        key = ("id", e["id"].split("@")[0]) if e["id"] else ("name", _norm(_clean(e["name"])))
        if e.get("custom") or e.get("cc") in local_sel or key not in seen_ch:
            seen_ch.add(key)
            one.append(e)
    uniq = one[:int(sel.get("maxChannels") or 600)]
    # program guide: each channel is matched, exactly, only inside the guide of its own country (by guide id, else by identical name);
    # nothing is guessed across countries, because a name like "Cartoon Network" exists in every country with a different schedule
    guide_urls = []
    if guides and sel.get("fullGuide"):
        _match_guides(uniq, cat, errors)
        _match_fast(uniq, errors)
    xml = (sel.get("custom") or {}).get("xmltv", "").strip()
    if xml:
        guide_urls.append(xml)
    # local channels first: numbers 1-99 (Ada Derana 24 and the other 24-hour ones lead), everything else from 101
    local = set(sel.get("local") or [])
    skip = [s.lower() for s in sel.get("localExclude") or ["national geographic", "nickelodeon"]]   # international brands some lists file under a country
    loc = [e for e in uniq if e.get("cc") in local and not any(s in e["name"].lower() for s in skip)]
    loc.sort(key=lambda e: (0 if e["url"].startswith(YT_BASE) and e["name"].startswith("Ada Derana 24") else 1 if not e["url"].startswith(YT_BASE) else 2, e["name"].lower()))
    for i, e in enumerate(loc[:99], 1):
        e["chno"] = i
    rest = [e for e in uniq if "chno" not in e]
    for i, e in enumerate(rest, 101):
        e["chno"] = i
    for e in loc[:99]:
        e["guide"] = f"local{e['chno']}"
    uniq = loc[:99] + rest
    # channels a player cannot play when Jellyfin only copies them: "reencode" makes a clean copy of the picture, "remux" joins a separate
    # audio track to the picture (YouTube channels keep them apart, and Jellyfin then plays no sound)
    redo = []
    for e in uniq:
        low = e["name"].lower()
        mode = None
        if e["url"] not in prefer and any(k.lower() in low for k in sel.get("reencode") or []):
            mode = "encode"
        elif any(k.lower() in low for k in sel.get("remux") or []) or (e["url"].startswith(YT_BASE) and sel.get("remuxYoutube", True)):
            mode = "copy"
        if mode:
            slug = re.sub(r"[^a-z0-9]+", "", low)[:24]
            redo.append({"name": e["name"], "slug": slug, "src": e["url"], "mode": mode})
            e["url"] = f"{sel.get('reencodeBase') or 'http://172.17.0.1:9130'}/{slug}/index.m3u8"   # served by the sidecar (Jellyfin ignores plain file paths)
    matched = sum(1 for e in uniq if e.get("_g"))
    for e in uniq:
        if e.get("_g"):
            e["guide"] = f"g{e['chno']}"
    local_guide = bool(loc)
    stats = {"viaVpn": sum(1 for e in uniq if e.get("via")), "channels": len(uniq), "allNames": [e["name"] for e in uniq], "localGuide": local_guide, "local": min(len(loc), 99), "localNames": [e["name"] for e in loc[:99]],
             "localEntries": [{"chno": e["chno"], "name": e["name"], "logo": e["logo"], "url": e["url"], "bulletins": e.get("bulletins")} for e in loc[:99]], "dead": dead, "withGuide": matched, "guides": guide_urls, "mergedGuide": False, "reencode": redo, "errors": errors[:5],
             "sports": sum(1 for e in uniq if "sport" in e["group"].lower())}
    if out_path:
        lines = ["#EXTM3U"]
        for e in uniq:
            gid = e.get("guide") or e["id"]
            group = (e["group"].split(";")[0] or "Other").strip()
            lines.append(f'#EXTINF:-1 tvg-id="{gid}" tvg-chno="{e["chno"]}" tvg-logo="{e["logo"]}" group-title="{group}",{e["name"]}')
            lines.append(e["url"])
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        tmp = out_path + ".tmp"
        open(tmp, "w", encoding="utf8").write("\n".join(lines) + "\n")
        os.replace(tmp, out_path)
        if local_guide:
            write_local_guide(os.path.join(os.path.dirname(out_path), "local.xml"), stats["localEntries"])
        merged = os.path.join(os.path.dirname(out_path), "guide.xml")
        stats["mergedGuide"] = bool(matched) and _write_merged_guide(merged, uniq) > 0
        if not stats["mergedGuide"] and os.path.exists(merged):
            os.remove(merged)
    return stats


def _guide_channels(xml):
    return {m.group(1): re.findall(r"<display-name[^>]*>([^<]*)<", m.group(2)) for m in re.finditer(r'<channel id="([^"]*)">(.*?)</channel>', xml, re.S)}


def _gnorm(gid):
    return _norm(re.sub(r"\.[a-z]{2}\d?$", "", gid.split("@")[0]))


def _xmltv_time(s):
    import datetime as dt
    m = re.match(r"\s*(\d{14})\s*([+-]\d{4})?", s)
    t = dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
    if m.group(2):
        off = m.group(2)
        t -= (1 if off[0] == "+" else -1) * dt.timedelta(hours=int(off[1:3]), minutes=int(off[3:5]))
    return t.replace(tzinfo=dt.timezone.utc)


def _match_guides(uniq, cat, errors):
    """Mark entries with e["_g"] = (guide file, guide channel id) and keep their programmes in e["_progs"]."""
    import datetime as dt
    have = set(cat.get("guides") or [])
    by_cc = collections.defaultdict(list)
    for e in uniq:
        m = re.search(r"\.([a-z]{2})(?:@|$)", e["id"] or "")
        if m and m.group(1).upper() in have:
            by_cc[m.group(1).upper()].append(e)
    try:
        idx = fetch(GUIDES, 30).decode("utf8", "ignore")
    except NET_ERRORS:
        return
    now = dt.datetime.now(dt.timezone.utc)
    lo, hi = now - dt.timedelta(hours=6), now + dt.timedelta(hours=72)
    for cc, items in sorted(by_cc.items(), key=lambda kv: -len(kv[1]))[:MAX_GUIDE_COUNTRIES]:
        for fn in sorted(set(re.findall(rf"epg_ripper_{cc}\d+\.xml\.gz", idx)))[:3]:
            try:
                xml = fetch(GUIDES + fn, 120).decode("utf8", "ignore")
            except NET_ERRORS as ex:
                errors.append(f"guide {fn}: {ex}")
                continue
            chans = _guide_channels(xml)
            idmap = {_gnorm(g): g for g in chans}
            namemap = {}
            for g, names in chans.items():
                for n in names:
                    namemap.setdefault(_norm(n), g)
            counts = collections.Counter(re.findall(r'<programme [^>]*channel="([^"]+)"', xml))
            alias = lambda k: k.replace("sportsten", "ten")     # noqa: E731 - Sony Sports Ten N is the rebranded Sony Ten N
            want = {}
            for e in items:
                if e.get("_progs"):
                    continue
                base = _norm(re.sub(r"\.[a-z]{2}$", "", e["id"].split("@")[0]))
                nm = _norm(re.sub(r"\([^)]*\)|\[[^\]]*\]", "", e["name"]))
                keys = [base, nm, re.sub(r"hd$", "", nm), alias(base), alias(nm), alias(re.sub(r"hd$", "", nm))]
                # a guide file often lists a channel twice (one entry empty): take the candidate that really has programmes,
                # and leave the channel for the next guide file when this one has none
                cands = {idmap.get(k) or namemap.get(k) for k in keys} - {None}
                best = max(cands, key=lambda g: counts.get(g, 0), default=None)
                if best and counts.get(best, 0) > 0:
                    e["_g"] = (fn, best)
                    want.setdefault(best, []).append(e)
            if not want:
                continue
            for pm in re.finditer(r"<programme ([^>]*)>(.*?)</programme>", xml, re.S):
                attrs = dict(re.findall(r'(\w+)="([^"]*)"', pm.group(1)))
                g = attrs.get("channel")
                if g not in want:
                    continue
                try:
                    st, sp = _xmltv_time(attrs["start"]), _xmltv_time(attrs["stop"])
                except (KeyError, ValueError, AttributeError):
                    continue
                if sp > lo and st < hi:
                    for e in want[g]:
                        e.setdefault("_progs", []).append((st, sp, pm.group(2)))


FAST_GUIDES = {"PlutoTV": {"ar", "br", "ca", "cl", "de", "dk", "es", "fr", "gb", "it", "mx", "no", "se", "us"},
               "SamsungTVPlus": {"at", "ca", "ch", "de", "es", "fr", "gb", "in", "it", "kr", "us"},
               "Plex": {"au", "ca", "es", "fr", "gb", "mx", "nz", "us"}}


def _match_fast(uniq, errors):
    """Free ad-supported channels (Pluto, Samsung TV Plus, Plex) publish their own guides per country. Match by identical name inside
    the channel's own country only; a name that is ambiguous in that guide is left unmatched rather than guessed."""
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    lo, hi = now - dt.timedelta(hours=6), now + dt.timedelta(hours=72)
    by_cc = collections.defaultdict(list)
    for e in uniq:
        m = re.search(r"\.([a-z]{2})(?:@|$)", e["id"] or "")
        if m and not e.get("_g"):
            by_cc[{"uk": "gb"}.get(m.group(1), m.group(1))].append(e)
    for prov, regions in FAST_GUIDES.items():
        for cc in sorted(regions & set(by_cc)):
            items = [e for e in by_cc[cc] if not e.get("_g")]
            if not items:
                continue
            try:
                xml = fetch(f"https://i.mjh.nz/{prov}/{cc}.xml.gz", 120).decode("utf8", "ignore")
            except NET_ERRORS as ex:
                errors.append(f"guide {prov}/{cc}: {ex}")
                continue
            chans = _guide_channels(xml)
            names = collections.defaultdict(set)
            for g, ns in chans.items():
                for n in ns:
                    names[_norm(n)].add(g)
            want = {}
            for e in items:
                nm = _norm(re.sub(r"\([^)]*\)|\[[^\]]*\]", "", e["name"]))
                gs = names.get(nm) or names.get(nm + "tv") or set()
                if len(nm) >= 5 and len(gs) == 1:
                    g = next(iter(gs))
                    e["_g"] = (f"{prov}/{cc}", g)
                    want.setdefault(g, []).append(e)
            for pm in re.finditer(r"<programme ([^>]*)>(.*?)</programme>", xml, re.S) if want else []:
                attrs = dict(re.findall(r'(\w+)="([^"]*)"', pm.group(1)))
                g = attrs.get("channel")
                if g not in want:
                    continue
                try:
                    st, sp = _xmltv_time(attrs["start"]), _xmltv_time(attrs["stop"])
                except (KeyError, ValueError, AttributeError):
                    continue
                if sp > lo and st < hi:
                    for e in want[g]:
                        e.setdefault("_progs", []).append((st, sp, pm.group(2)))


def _write_merged_guide(path, entries):
    """One clean guide file: only the programmes matched above, under this list's own channel ids (g<number>)."""
    n = 0
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")     # noqa: E731
    for e in entries:
        if e.get("_g") and e.get("_progs"):
            out.append(f'<channel id="g{e["chno"]}"><display-name>{esc(_clean(e["name"]))}</display-name></channel>')
    fmt = lambda t: t.strftime("%Y%m%d%H%M%S +0000")     # noqa: E731
    for e in entries:
        if e.get("_g") and e.get("_progs"):
            n += 1
            for st, sp, inner in sorted(e["_progs"], key=lambda p: p[0]):
                # programme pictures make Jellyfin download one image per programme (thousands, many refused): leave them out
                inner = re.sub(r"<icon\b[^>]*?/>|<icon\b[^>]*>.*?</icon>", "", inner, flags=re.S)
                out.append(f'<programme start="{fmt(st)}" stop="{fmt(sp)}" channel="g{e["chno"]}">{inner}</programme>')
    out.append("</tv>")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf8") as fh:
        fh.write("\n".join(out))
    os.replace(tmp, path)
    return n


def purge_duplicate_programs(call):
    """Jellyfin keeps programme records from earlier guide imports, so a slot can appear twice. Keep the newest record of each."""
    items = call("POST", "/LiveTv/Programs", {"Limit": 20000, "EnableTotalRecordCount": False, "ImageTypeLimit": 0,
                                               "Fields": ["DateCreated"]})["Items"]
    newest = {}
    for p in items:
        k = (p["ChannelId"], p["StartDate"])
        if k not in newest or p.get("DateCreated", "") > newest[k].get("DateCreated", ""):
            newest[k] = p
    gone = 0
    for p in items:
        if newest[(p["ChannelId"], p["StartDate"])]["Id"] != p["Id"]:
            call("DELETE", f"/Items/{p['Id']}")
            gone += 1
    return gone


def pin_favorites(call, names):
    """Mark the local channels as favourites for every Jellyfin user, so nobody has to search for them (matched by channel name)."""
    names = set(names)
    users = call("GET", "/Users")
    mine = [c["Id"] for c in call("GET", "/LiveTv/Channels?limit=5000")["Items"] if c["Name"] in names]
    for u in users:
        for cid in mine:
            call("POST", f"/Users/{u['Id']}/FavoriteItems/{cid}")
    return {"users": len(users), "channels": len(mine)}


# ---------------------------------------------------------------- local channels first on Jellyfin's own Live TV row
def _clean(name):
    return re.sub(r"\s+", " ", re.sub(r"\s*\(\d{3,4}p\)|\s*\[[^\]]*\]", "", name)).strip()


def write_local_guide(path, entries, hours=96):
    """A small program guide for the local channels, in 3-hour blocks: their broadcasters publish no schedule, so each shows a simple
    "Live" programme."""
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    start0 = now - dt.timedelta(hours=now.hour % 3 + 3)
    fmt = lambda t: t.strftime("%Y%m%d%H%M%S +0000")     # noqa: E731
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")     # noqa: E731
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<tv>"]
    for e in entries:
        out.append(f'<channel id="local{e["chno"]}"><display-name>{esc(_clean(e["name"]))}</display-name>' +
                   (f'<icon src="{esc(e["logo"])}"/>' if e.get("logo") else "") + "</channel>")
    lk = dt.timezone(dt.timedelta(hours=5, minutes=30))
    for e in entries:
        name = esc(_clean(e["name"]))
        cid = f'local{e["chno"]}'
        if e.get("bulletins"):
            # real bulletin slots (usual daily times), with a plain "between bulletins" block in every gap
            slots = []
            for day in range(-1, hours // 24 + 2):
                d0 = (now.astimezone(lk) + dt.timedelta(days=day)).replace(hour=0, minute=0, second=0, microsecond=0)
                for hhmm, mins, title in e["bulletins"]:
                    h, m = map(int, hhmm.split(":"))
                    st = d0.replace(hour=h, minute=m).astimezone(dt.timezone.utc)
                    slots.append((st, st + dt.timedelta(minutes=mins), title))
            slots.sort()
            cur = slots[0][0] - dt.timedelta(hours=1)
            for st, en, title in slots:
                if st > cur:
                    out.append(f'<programme start="{fmt(cur)}" stop="{fmt(st)}" channel="{cid}"><title lang="en">{name}</title>'
                               f'<desc lang="en">Programmes and news bulletins air live on {name} at their usual times.</desc>'
                               f'<category lang="en">News</category></programme>')
                out.append(f'<programme start="{fmt(st)}" stop="{fmt(en)}" channel="{cid}"><title lang="en">{esc(title)}</title>'
                           f'<sub-title lang="en">{name}</sub-title>'
                           f'<desc lang="en">{esc(title)} on {name}. Usual daily slot (Sri Lanka time); the channel goes live for the bulletin.</desc>'
                           f'<category lang="en">News</category></programme>')
                cur = en
            continue
        for k in range(hours // 3 + 2):
            s0 = start0 + dt.timedelta(hours=3 * k)
            out.append(f'<programme start="{fmt(s0)}" stop="{fmt(s0 + dt.timedelta(hours=3))}" channel="{cid}">'
                       f'<title lang="en">{name} Live</title><desc lang="en">Live broadcast on {name}.</desc></programme>')
    out.append("</tv>")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf8") as fh:
        fh.write("\n".join(out))
    os.replace(tmp, path)
    return len(entries)


def set_home_for_everyone(call):
    """Jellyfin's Live TV row (buttons, On Now, Next Up) right under the top of everyone's home page."""
    order = ["smalllibrarytiles", "livetv", "resume", "nextup", "latestmedia", "none", "none"]
    for u in call("GET", "/Users"):
        uid = u["Id"]
        dp = call("GET", f"/DisplayPreferences/usersettings?userId={uid}&client=emby")
        for i, s in enumerate(order):
            dp.setdefault("CustomPrefs", {})[f"homesection{i}"] = s
        call("POST", f"/DisplayPreferences/usersettings?userId={uid}&client=emby", dp)


def purge_stale(call, names):
    """Jellyfin keeps channels from earlier lists forever: remove the ones no longer wanted, and older copies of a channel that was
    re-imported (a channel whose address changed shows up twice)."""
    names, gone, newest = set(names), 0, {}
    items = call("GET", "/LiveTv/Channels?limit=10000&Fields=DateCreated")["Items"]
    for c in items:
        if c["Name"] in names and (c["Name"] not in newest or c.get("DateCreated", "") > newest[c["Name"]].get("DateCreated", "")):
            newest[c["Name"]] = c
    for c in items:
        if c["Name"] not in names or newest.get(c["Name"], c)["Id"] != c["Id"]:
            call("DELETE", f"/Items/{c['Id']}")
            gone += 1
    return gone
