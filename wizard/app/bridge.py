"""Torznab adapter for the Tamil/Malayalam forums (TamilMV, TamilBlasters) and MovieRulz.

Prowlarr's indexer definitions turn one search row into one release, but these sites put several qualities
(each its own magnet) inside a single page. This adapter searches the site, opens the matching pages and returns
every magnet as its own Torznab item, so Radarr/Sonarr parse real release names, sizes and languages. It runs inside
the stack as the `regional` service and is added to Prowlarr as an ordinary Torznab indexer.

These sites change domain constantly, so the address is never hard-wired. Each site goes through, in order:
  1. a manual override (/data/override.json)            4. a TLD sweep of look-alike names, validated by page structure
  2. the last address that worked (/data/domains.json)  5. DNS-over-HTTPS when the local resolver is blocked
  3. built-in seeds + MediaFusion's community registry  6. a Cloudflare solver (FlareSolverr/TRAWL API) when challenged
A candidate is only accepted if the page really looks like the site (and, for MovieRulz, really yields magnets).

  GET /<site>/api?t=search&q=premam 2015        GET /status        GET /health
"""
import concurrent.futures as cf
import html
import http.client
import json
import os
import re
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import formatdate
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xml.sax.saxutils import escape

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
SOLVER = os.environ.get("SOLVER_URL", "http://solver:8191/v1")
DATA = os.environ.get("DATA_DIR", "/data")
REGISTRY = "https://raw.githubusercontent.com/mhdzumair/MediaFusion/main/resources/json/scraper_config.json"
REGISTRY_KEYS = {"tamilmv": "tamilmv", "tamilblasters": "tamil_blasters", "movierulz": "movierulz"}

SITES = {
    # DHT search engine with an RSS API; it also indexes the regional sites' uploads, so it works when their domains are blocked
    "bt4g": {"name": "BT4G", "kind": "rss", "marker": r"bt4g", "names": ["bt4g", "bt4gprx"],
             "seeds": ["https://bt4gprx.com", "https://bt4g.org", "https://bt4g.com"]},
    "tamilmv": {"name": "TamilMV", "kind": "ips", "marker": r"tamilmv", "names": ["1tamilmv", "tamilmv"],
                "seeds": ["https://www.1tamilmv.solar", "https://www.1tamilmv.pizza", "https://1tamilmv.meme"]},
    "tamilblasters": {"name": "TamilBlasters", "kind": "ips", "marker": r"tamilblasters", "names": ["1tamilblasters", "tamilblasters"],
                      "seeds": ["https://1tamilblasters.garden", "https://1tamilblasters.wtf", "https://1tamilblasters.im"]},
    "movierulz": {"name": "MovieRulz", "kind": "wp", "marker": r"movierulz", "names": ["5movierulz", "movierulz", "4movierulz"],
                  "seeds": ["https://www.5movierulz.day", "https://5movierulz.site", "https://www.movierulz.co.in"]},
}
TLDS = ("com net org in co.in to tv me cc vc ws xyz info site online live life fun cloud club top vip lol pro app one "
        "run bz ac pm ag nz lk day cam ink wtf garden pink moda im yt tel solar pizza meme rsvp cards fi rest mov sbs "
        "cfd icu fyi plus link tube pics zip directory institute").split()
MAX_TOPICS = 8            # pages opened per search
SEEDERS = 5               # these sites publish no seeder counts; a small fixed value passes a low minimum-seeders rule
TTL = {"search": 900, "topic": 1800, "domain_fail": 3600}
_cache, _lock = {}, threading.Lock()
_state = {s: {"base": None, "ok": None, "error": None, "cookies": "", "ua": UA, "via": ""} for s in SITES}


# ---------------------------------------------------------------- tiny persistence
def _path(name):
    return os.path.join(DATA, name)


def load_json(name, default):
    try:
        with open(_path(name)) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(name, obj):
    try:
        os.makedirs(DATA, exist_ok=True)
        with open(_path(name), "w") as f:
            json.dump(obj, f)
    except OSError:
        pass


def cached(key, ttl, fn):
    with _lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    with _lock:
        _cache[key] = (time.time(), val)
    return val


# ---------------------------------------------------------------- network: plain, DoH, solver
class _PinnedHTTPS(http.client.HTTPSConnection):
    """Connect to a given IP but keep the real hostname for SNI and certificate checks."""

    def __init__(self, host, ip, **kw):
        super().__init__(host, **kw)
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port or 443), self.timeout)
        self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=self.host)


def doh_resolve(host):
    """Resolve through DNS-over-HTTPS when the local resolver refuses (common ISP blocking)."""
    def run():
        for url in (f"https://cloudflare-dns.com/dns-query?name={host}&type=A", f"https://dns.google/resolve?name={host}&type=A"):
            try:
                req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
                with urllib.request.urlopen(req, timeout=6) as r:
                    ans = json.loads(r.read()).get("Answer", [])
                ips = [a["data"] for a in ans if a.get("type") == 1]
                if ips:
                    return ips
            except Exception:  # noqa: BLE001 - try the next resolver
                continue
        return []
    return cached(("doh", host), 3600, run)


def fetch_doh(url, headers, timeout):
    u = urllib.parse.urlparse(url)
    if u.scheme != "https":
        raise OSError("DoH fetch needs https")
    ips = doh_resolve(u.hostname)
    if not ips:
        raise OSError(f"cannot resolve {u.hostname}")
    conn = _PinnedHTTPS(u.hostname, ips[0], timeout=timeout)
    conn.request("GET", (u.path or "/") + (("?" + u.query) if u.query else ""), headers={**headers, "Host": u.netloc})
    r = conn.getresponse()
    data = r.read()
    if r.status in (301, 302, 303, 307, 308) and r.getheader("Location"):
        return fetch_doh(urllib.parse.urljoin(url, r.getheader("Location")), headers, timeout)
    if r.status >= 400:
        raise urllib.error.HTTPError(url, r.status, r.reason, r.headers, None)
    return data, url


def via_solver(url, site, timeout=60):
    body = json.dumps({"cmd": "request.get", "url": url, "maxTimeout": 45000}).encode()
    req = urllib.request.Request(SOLVER, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read())
    sol = j.get("solution") or {}
    if j.get("status") != "ok":
        raise RuntimeError("blocked by a Cloudflare challenge and the solver could not pass it")
    st = _state.setdefault(site, {})
    st["ua"] = sol.get("userAgent", UA)
    st["cookies"] = "; ".join(f"{c['name']}={c['value']}" for c in sol.get("cookies", []))
    st["via"] = "solver"
    return sol.get("response", ""), sol.get("url", url)


def http_get(url, site, timeout=20):
    st = _state.setdefault(site, {})
    headers = {"User-Agent": st.get("ua", UA), "Accept": "text/html,*/*", "Accept-Encoding": "identity"}
    if st.get("cookies"):
        headers["Cookie"] = st["cookies"]

    def decode(data):
        return data.decode("utf-8", "replace")

    def challenged(text):
        return "Just a moment" in text[:4000] or "cf-challenge" in text[:4000] or "challenge-platform" in text[:6000]
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text, final = decode(r.read()), r.geturl()
        if challenged(text):
            return via_solver(url, site)
        return text, final
    except urllib.error.HTTPError as e:
        if e.code in (403, 429, 503):
            return via_solver(url, site)
        raise
    except ssl.SSLError:
        raise                         # wrong certificate: a parked or look-alike domain, never accept it
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        reason = str(getattr(e, "reason", e))
        if "certificate" in reason.lower():
            raise
        if any(k in reason for k in ("Name or service", "nodename", "resolve", "getaddrinfo")):
            data, final = fetch_doh(url, headers, timeout)           # resolver blocked: ask DNS-over-HTTPS instead
            st["via"] = "doh"
            return decode(data), final
        try:
            return via_solver(url, site)                            # silent hang is how Cloudflare challenges often look
        except Exception:  # noqa: BLE001
            raise e


# ---------------------------------------------------------------- domain discovery
IPS_RE = re.compile(r"(ipsLayout|ipsApp|index\.php\?/forums|data-ipsHover)")
WP_RE = re.compile(r"(entry-title|wp-content|wp-json)")


def looks_right(site, page):
    cfg = SITES[site]
    if not re.search(cfg["marker"], page, re.I):
        return False
    return bool({"ips": IPS_RE, "wp": WP_RE, "rss": re.compile(r"<rss")}[cfg["kind"]].search(page))


def registry():
    """Community-maintained homepage list (MediaFusion's config) used as extra seeds; cached for a day."""
    def run():
        try:
            with urllib.request.urlopen(urllib.request.Request(REGISTRY, headers={"User-Agent": UA}), timeout=10) as r:
                cfg = json.loads(r.read())
            return {s: (cfg.get(k) or {}).get("homepage") for s, k in REGISTRY_KEYS.items()}
        except Exception:  # noqa: BLE001
            return {}
    return cached("registry", 86400, run)


def validate(site, base):
    """The address serving the real site (right structure, and for WordPress sources actual magnets), else None."""
    try:
        page, final = http_get(base + ("/search?q=test&page=rss" if SITES[site]["kind"] == "rss" else "/"), site, timeout=10)
    except Exception:  # noqa: BLE001
        return None
    if not looks_right(site, page):
        return None
    p = urllib.parse.urlparse(final)
    root = f"{p.scheme}://{p.netloc}"
    if SITES[site]["kind"] == "wp" and not wp_has_magnets(site, root):
        return None
    return root


def wp_has_magnets(site, base):
    """Canary: the search must lead to a page that really contains magnets, otherwise it is just a streaming clone."""
    try:
        page, _ = http_get(f"{base}/?s=rrr", site, timeout=15)
        for link in wp_links(page)[:3]:
            p, _ = http_get(link, site, timeout=15)
            if MAGNET_RE.search(p):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def candidates(site):
    cfg, out = SITES[site], []
    st = load_json("domains.json", {}).get(site)
    ov = load_json("override.json", {}).get(site)
    for b in [ov, st, *cfg["seeds"], registry().get(site)]:
        if b and b.rstrip("/") not in out:
            out.append(b.rstrip("/"))
    return out


def tld_sweep(site):
    """Last resort: probe look-alike names across common TLDs and keep the first that passes validation."""
    names = SITES[site]["names"]
    hosts = [f"{n}.{t}" for n in names for t in TLDS] + [f"www.{n}.{t}" for n in names for t in TLDS[:24]]

    def one(h):
        try:
            return validate(site, f"https://{h}")
        except Exception:  # noqa: BLE001
            return None
    with cf.ThreadPoolExecutor(24) as ex:
        for res in ex.map(one, hosts):
            if res:
                return [res]
    return []


_sweeping = set()


def _sweep_job(site):
    try:
        found = tld_sweep(site)
        if found:
            remember(site, found[0])
    finally:
        _sweeping.discard(site)


def base_url(site, force=False):
    st = _state[site]
    if st["base"] and not force:
        return st["base"]
    cands = candidates(site)
    last = cands[-1] if cands else None
    with cf.ThreadPoolExecutor(max_workers=max(1, len(cands))) as ex:     # probe all known addresses at once
        for root in ex.map(lambda c: validate(site, c), cands):
            if root:
                return remember(site, root)
    # nothing known works: sweep look-alike domains in the background so searches never block on it
    if site not in _sweeping and time.time() - st.get("swept", 0) > TTL["domain_fail"]:
        st["swept"] = time.time()
        _sweeping.add(site)
        threading.Thread(target=_sweep_job, args=(site,), daemon=True).start()
    st["error"] = f"{SITES[site]['name']} has no reachable address right now (last tried {last}); still looking"
    raise RuntimeError(st["error"])


def remember(site, root):
    st = _state[site]
    st.update(base=root, ok=time.time(), error=None)
    d = load_json("domains.json", {})
    if d.get(site) != root:
        d[site] = root
        save_json("domains.json", d)
    return root


def get_page(site, path_or_url):
    """Fetch a page; if the known domain died, rediscover once and retry on the new one."""
    for attempt in (0, 1):
        try:
            base = base_url(site, force=attempt == 1)
            url = path_or_url if path_or_url.startswith("http") else base + path_or_url
            return http_get(url, site)
        except RuntimeError:
            raise
        except Exception:  # noqa: BLE001
            if attempt == 1:
                raise
            _state[site]["base"] = None
    raise RuntimeError("unreachable")


# ---------------------------------------------------------------- parsing
TOPIC_RE = re.compile(r"ipsStreamItem_title.*?<a href='([^']+)'[^>]*>\s*([^<]+)</a>", re.S)
WP_ROW = re.compile(r"""<h2[^>]*class=["'][^"']*entry-title[^"']*["'][^>]*>\s*<a[^>]+href=["']([^"']+)["'][^>]*>([^<]*)""")
MAGNET_RE = re.compile(r"""href=['"](magnet:\?[^'"]+)""")
SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(TB|GB|MB)", re.I)
PREFIX_RE = re.compile(r"^(?:www\.)?\w*(?:tamilmv|tamilblasters|tamilrockers|movierulz)\w*\.[a-z.]{2,12}\s*-\s*", re.I)


def norm(text):
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower())


def title_words(q):
    q = re.sub(r"\b(19|20)\d{2}\b", " ", norm(q))
    return [w for w in q.split() if len(w) > 1 and w not in ("the", "and", "of", "a")]


def matches(q, title):
    words, t = title_words(q), norm(title)
    if not all(w in t for w in words):
        return False
    years = re.findall(r"\b(?:19|20)\d{2}\b", q)
    return not years or any(y in title for y in years)


def wp_links(page):
    return list(dict.fromkeys(html.unescape(m.group(1)) for m in WP_ROW.finditer(page)))


def search_topics(site, q):
    kind = SITES[site]["kind"]
    words = title_words(q)

    def run(term):
        if kind == "ips":
            page, _ = get_page(site, f"/index.php?/search/&q={urllib.parse.quote_plus(term)}&type=forums_topic&search_and_or=and&sortby=relevancy")
            out = []
            for href, title in TOPIC_RE.findall(page):
                href = html.unescape(href).split("&do=")[0]
                if href not in [o[0] for o in out]:
                    out.append((href, html.unescape(title).strip()))
            return out
        page, _ = get_page(site, f"/?s={urllib.parse.quote_plus(term)}")
        return [(html.unescape(m.group(1)), html.unescape(m.group(2)).strip()) for m in WP_ROW.finditer(page)]
    # the forum search returns nothing for some multi-word phrases, so fall back to the most distinctive word
    for term in [" ".join(words), max(words, key=len) if words else ""]:
        if term:
            topics = cached(("s", site, term), TTL["search"], lambda t=term: run(t))
            if topics:
                return topics[:MAX_TOPICS * 2]
    return []


def topic_releases(site, url):
    def run():
        page, _ = get_page(site, url)
        posted = re.search(r"<time datetime=['\"]([^'\"]+)", page)
        heading = re.search(r"<h1[^>]*>\s*(?:<[^>]+>)*([^<]{4,200})", page)
        items = []
        for mag in MAGNET_RE.findall(page):
            mag = html.unescape(mag)
            q = urllib.parse.parse_qs(urllib.parse.urlparse(mag).query)
            ih = (q.get("xt", [""])[0].rsplit(":", 1) or [""])[-1].lower()
            name = urllib.parse.unquote_plus(q.get("dn", [""])[0]) or (html.unescape(heading.group(1)).strip() if heading else "")
            if not ih or not name:
                continue
            name = re.sub(r"\.torrent$", "", PREFIX_RE.sub("", name), flags=re.I).strip()
            items.append({"title": name, "magnet": mag, "hash": ih, "date": posted.group(1) if posted else None, "topic": url})
        return items
    return cached(("t", site, url), TTL["topic"], run)


def size_of(title):
    sizes = [float(n) * {"TB": 1 << 40, "GB": 1 << 30, "MB": 1 << 20}[u.upper()] for n, u in SIZE_RE.findall(title)]
    return int(sizes[-1]) if sizes else int(1.4 * (1 << 30))


def category(title, topic_url):
    tv = bool(re.search(r"\b(S\d{1,2}\b|S\d{1,2}E\d|EP?\s?\(?\d|season|web[- ]series|tv[- ]show)", title, re.I)) \
        or "web-series" in topic_url or "tv-show" in topic_url
    return 5000 if tv else 2000


# ---------------------------------------------------------------- torznab
def caps(site):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<caps><server title="{SITES[site]['name']} (adaptive adapter)"/><limits max="100" default="50"/>
<searching><search available="yes" supportedParams="q"/><tv-search available="yes" supportedParams="q,season,ep"/>
<movie-search available="yes" supportedParams="q"/></searching>
<categories><category id="2000" name="Movies"/><category id="5000" name="TV"/></categories></caps>"""


# Never hand Sonarr/Radarr anything that looks like software, a cracked installer or a script instead of a film or episode.
UNSAFE_TITLE = re.compile(r"\.(exe|msi|scr|bat|cmd|com|apk|dmg|pkg|jar|vbs|ps1|lnk|dll|iso\.exe)\b|"
                          r"\b(keygen|patcher|activator)\b|\bcrack(ed)?[ ._-]?(by|only|fix)\b", re.I)
VIDEO_CATEGORY = re.compile(r"movie|tv|video|series|show|anime", re.I)   # BT4G also files archives and software, which never get through


def is_safe(row):
    cat = row["topic"].split(":", 1)[1] if row["topic"].startswith("bt4g:") else ""
    return not UNSAFE_TITLE.search(row["title"]) and (not row["topic"].startswith("bt4g:") or bool(VIDEO_CATEGORY.search(cat)))


def feed(site, rows, want_cat):
    items = []
    for r in filter(is_safe, rows):
        cat = 5000 if r["topic"].startswith("bt4g:") and "tv" in r["topic"].lower() else category(r["title"], r["topic"])
        if want_cat and cat != want_cat:
            continue
        size = r.get("size") or size_of(r["title"])
        try:
            pub = formatdate(time.mktime(time.strptime(r["date"][:19], "%Y-%m-%dT%H:%M:%S"))) if r["date"] else formatdate()
        except ValueError:
            pub = formatdate()
        link = escape(r["magnet"])
        items.append(f"""<item><title>{escape(r['title'])}</title><guid>{r['hash']}</guid><link>{link}</link>
<comments>{escape(r['topic'])}</comments><pubDate>{pub}</pubDate><size>{size}</size>
<enclosure url="{link}" length="{size}" type="application/x-bittorrent"/>
<torznab:attr name="category" value="{cat}"/><torznab:attr name="seeders" value="{SEEDERS}"/>
<torznab:attr name="peers" value="{SEEDERS}"/><torznab:attr name="infohash" value="{r['hash']}"/>
<torznab:attr name="magneturl" value="{link}"/><torznab:attr name="size" value="{size}"/></item>""")
    return ('<?xml version="1.0" encoding="UTF-8"?><rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" '
            'xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel>'
            f'<title>{SITES[site]["name"]}</title>' + "".join(items) + "</channel></rss>")


def error_xml(code, msg):
    return f'<?xml version="1.0" encoding="UTF-8"?><error code="{code}" description="{escape(msg)}"/>'


def recent(site):
    def run():
        page, _ = get_page(site, "/")
        if SITES[site]["kind"] == "ips":
            links = []
            for href in re.findall(r"href=['\"]([^'\"]*?/forums/topic/\d+-[^'\"]+)['\"]", page):
                href = html.unescape(href).split("&do=")[0]
                if href not in links:
                    links.append(href)
        else:
            links = wp_links(page)
        return [(h, "") for h in links[:12]]
    return cached(("r", site), 900, run)


RSS_ITEM = re.compile(r"<item>(.*?)</item>", re.S)


def collect_rss(site, q):
    """BT4G: one RSS item per torrent, with size in the description."""
    def run(q):
        page, _ = get_page(site, f"/search?q={urllib.parse.quote_plus(q)}&page=rss")
        rows = []
        for it in RSS_ITEM.findall(page):
            title = re.search(r"<title>(.*?)</title>", it, re.S)
            link = re.search(r"<link>(magnet:[^<]+)</link>", it)
            desc = re.search(r"<description><!\[CDATA\[(.*?)\]\]>", it, re.S)
            when = re.search(r"<pubDate>(.*?)</pubDate>", it)
            if not (title and link):
                continue
            mag = html.unescape(link.group(1))
            ih = (urllib.parse.parse_qs(urllib.parse.urlparse(mag).query).get("xt", [""])[0].rsplit(":", 1) or [""])[-1].lower()
            name = re.sub(r"\.torrent$", "", PREFIX_RE.sub("", html.unescape(title.group(1))), flags=re.I).strip()
            size, cat = None, None
            if desc:
                parts = desc.group(1).split("<br>")
                m = SIZE_RE.search(parts[1]) if len(parts) > 1 else None
                if m:
                    size = int(float(m.group(1)) * {"TB": 1 << 40, "GB": 1 << 30, "MB": 1 << 20}[m.group(2).upper()])
                cat = parts[2].strip() if len(parts) > 2 else None
            date = None
            if when:
                try:
                    date = time.strftime("%Y-%m-%dT%H:%M:%S", time.strptime(re.sub(r",(\d)", r", \1", when.group(1)).replace(" -0000", "").replace(" +0000", "").strip(), "%a, %d %b %Y %H:%M:%S"))
                except ValueError:
                    date = None
            rows.append({"title": name, "magnet": mag, "hash": ih, "date": date, "topic": f"bt4g:{cat or ''}", "size": size})
        return rows
    term = q or "1080p"          # RSS-style polls (no query) get the newest 1080p uploads
    rows = cached(("rss", site, term), TTL["search"], lambda: run(term))
    return [r for r in rows if r["hash"] and (not q or matches(q, r["title"]))]


def collect(site, q):
    if SITES[site]["kind"] == "rss":
        return collect_rss(site, q)
    topics = search_topics(site, q) if q else recent(site)
    if q:
        topics = [t for t in topics if matches(q, t[1])][:MAX_TOPICS]

    def safe(t):
        try:
            return topic_releases(site, t[0])
        except Exception:  # noqa: BLE001 - one broken page must not fail the whole search
            return []
    rows = []
    with cf.ThreadPoolExecutor(max_workers=3) as ex:
        for res in ex.map(safe, topics):
            rows.extend(res)
    return [r for r in rows if matches(q, r["title"])] if q else rows


def status():
    return {s: {"name": SITES[s]["name"], "address": st["base"], "online": bool(st["base"] and not st["error"]),
                "lastOk": st["ok"], "error": st["error"], "via": st["via"]} for s, st in _state.items()}


class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        print("req", fmt % a, flush=True)

    def reply(self, code, body, ctype="application/xml"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        parts = [p for p in u.path.split("/") if p]
        params = urllib.parse.parse_qs(u.query)
        if len(parts) == 2 and parts[0] == "slate" and slate_bytes():
            try:
                return self.reply(200, slate_segment(int(parts[1].split(".")[0])), "video/mp2t")
            except ValueError:
                return self.reply(404, "bad chunk", "text/plain")
        if len(parts) == 3 and parts[0] == "via":
            import viaproxy
            return viaproxy.serve(self, parts[1], parts[2])
        if parts == ["vpn", "status"]:
            import viaproxy
            ex = {k: viaproxy.exit_info(k) for k in viaproxy.exits()}
            return self.reply(200, json.dumps({"exits": ex}), "application/json")
        if parts == ["vpn", "probe"]:
            import viaproxy
            target = (params.get("url") or [""])[0]
            found = next((k for k in viaproxy.exits() if viaproxy.probe(k, target)), None)
            return self.reply(200, json.dumps({"exit": found}), "application/json")
        if parts == ["health"]:
            return self.reply(200, "ok", "text/plain")
        if parts == ["status"]:
            return self.reply(200, json.dumps(status()), "application/json")
        if len(parts) == 2 and parts[0] == "yt":
            ref = urllib.parse.unquote(parts[1])
            if not YT_REF.match(ref):
                return self.reply(400, "bad channel", "text/plain")
            try:
                playlist = yt_resolve(ref)
            except LookupError:
                if slate_bytes():
                    return self.reply(200, slate_playlist(), "application/vnd.apple.mpegurl")
                return self.reply(404, "not live right now", "text/plain")
            except Exception as e:  # noqa: BLE001 - YouTube blocked us or yt-dlp is missing
                return self.reply(502, str(e)[:160], "text/plain")
            return self.reply(200, playlist, "application/vnd.apple.mpegurl")
        if parts == ["livetv", "status"]:
            return self.reply(200, json.dumps(_livetv), "application/json")
        if parts == ["livetv", "refresh"]:
            threading.Thread(target=livetv_refresh, daemon=True).start()
            return self.reply(200, json.dumps({"started": True}), "application/json")
        if len(parts) == 2 and parts[0] == "discover" and parts[1] in SITES:     # force a fresh address search
            try:
                _state[parts[1]]["base"] = None
                return self.reply(200, json.dumps({"address": base_url(parts[1], force=True)}), "application/json")
            except Exception as e:  # noqa: BLE001
                return self.reply(200, json.dumps({"error": str(e)}), "application/json")
        if len(parts) != 2 or parts[0] not in SITES or parts[1] != "api":
            return self.reply(404, error_xml(300, "unknown path"))
        site, t = parts[0], (params.get("t") or ["search"])[0]
        try:
            if t == "caps":
                return self.reply(200, caps(site))
            want = {"movie": 2000, "tvsearch": 5000}.get(t)
            cat = (params.get("cat") or [""])[0]
            if cat and not want:
                ids = {c for c in cat.split(",") if c.isdigit()}
                if ids and all(i.startswith("5") for i in ids):
                    want = 5000
                elif ids and all(i.startswith("2") for i in ids):
                    want = 2000
            q = re.sub(r"\s+", " ", (params.get("q") or [""])[0].strip())
            return self.reply(200, feed(site, collect(site, q), want))
        except RuntimeError as e:      # site down or address unknown: an empty result keeps the indexer healthy in Prowlarr
            print("unavailable:", e, flush=True)
            return self.reply(200, feed(site, [], None))
        except Exception as e:  # noqa: BLE001
            return self.reply(200, error_xml(900, str(e)[:200]))


_livetv = {"last": None, "stats": None, "error": None}
_yt = {}
YT_REF = re.compile(r"^(UC[\w-]{22}|@[\w.-]{2,40})$")      # only a channel id or handle, never an arbitrary address


def yt_resolve(ref):
    """Current HLS address of a YouTube channel's live stream (they expire after a few hours, so it is looked up on demand)."""
    hit = _yt.get(ref)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    import sys
    for p in (os.path.join(os.environ.get("DATA_DIR", "/data"), "ytlib"),):
        if os.path.isdir(p) and p not in sys.path:
            sys.path.insert(0, p)
    import yt_dlp
    url = f"https://www.youtube.com/{'channel/' if ref.startswith('UC') else ''}{ref}/live"
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True,
                               "ignore_no_formats_error": True}) as y:
            info = y.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as e:
        if "not currently live" in str(e) or "not live" in str(e):
            raise LookupError("not live right now") from None
        raise
    if not info.get("is_live"):
        raise LookupError("not live right now")
    fm = [f for f in info.get("formats") or [] if f.get("manifest_url")]
    m3u8 = info.get("manifest_url") or (fm[0]["manifest_url"] if fm else None)
    if not m3u8:
        raise RuntimeError("no stream address found")
    text = urllib.request.urlopen(urllib.request.Request(m3u8, headers={"User-Agent": "Mozilla/5.0"}), timeout=20).read().decode("utf8", "ignore")
    trimmed = yt_trim(text)
    _yt[ref] = (time.time(), trimmed)
    return trimmed


SLATE = None


def slate_bytes():
    global SLATE
    if SLATE is None:
        for d in (os.environ.get("DATA_DIR", "/data"), os.path.dirname(os.path.abspath(__file__))):
            try:
                SLATE = open(os.path.join(d, "slate.ts"), "rb").read()
                break
            except OSError:
                continue
        else:
            SLATE = b""
    return SLATE


def _ts_time(pkt, pos):
    return (((pkt[pos] >> 1) & 7) << 30) | (pkt[pos + 1] << 22) | ((pkt[pos + 2] >> 1) << 15) | (pkt[pos + 3] << 7) | (pkt[pos + 4] >> 1)


def _ts_set(pkt, pos, v):
    pre = pkt[pos] & 0xF0
    pkt[pos] = pre | (((v >> 30) & 7) << 1) | 1
    pkt[pos + 1] = (v >> 22) & 0xFF
    pkt[pos + 2] = ((v >> 14) & 0xFE) | 1
    pkt[pos + 3] = (v >> 7) & 0xFF
    pkt[pos + 4] = ((v << 1) & 0xFE) | 1


def slate_segment(k):
    """The slate chunk number k with its timestamps and continuity counters moved forward, so a repeating picture looks like one
    unbroken live stream (the player rejects chunks whose timestamps jump back)."""
    data, out = slate_bytes(), bytearray()
    shift = (k * 4 * 90000) % (1 << 33)
    counts = {}
    for i in range(0, len(data) - 187, 188):
        pid = ((data[i + 1] & 0x1F) << 8) | data[i + 2]
        if (data[i + 3] >> 4) & 1:
            counts[pid] = counts.get(pid, 0) + 1
    for i in range(0, len(data) - 187, 188):
        pkt = bytearray(data[i:i + 188])
        if pkt[0] != 0x47:
            out += pkt
            continue
        pid = ((pkt[1] & 0x1F) << 8) | pkt[2]
        afc, pos = (pkt[3] >> 4) & 3, 4
        if afc in (2, 3):
            alen = pkt[4]
            if alen >= 7 and pkt[5] & 0x10:                      # PCR
                base = (pkt[6] << 25) | (pkt[7] << 17) | (pkt[8] << 9) | (pkt[9] << 1) | (pkt[10] >> 7)
                base = (base + shift) % (1 << 33)
                pkt[6], pkt[7], pkt[8], pkt[9] = (base >> 25) & 0xFF, (base >> 17) & 0xFF, (base >> 9) & 0xFF, (base >> 1) & 0xFF
                pkt[10] = ((base & 1) << 7) | (pkt[10] & 0x7F)
            pos = 5 + alen
        if afc in (1, 3):
            if (pkt[1] & 0x40) and pkt[pos:pos + 3] == b"\x00\x00\x01" and 0xC0 <= pkt[pos + 3] <= 0xEF:
                flags = pkt[pos + 7] >> 6
                if flags & 2:
                    _ts_set(pkt, pos + 9, (_ts_time(pkt, pos + 9) + shift) % (1 << 33))
                if flags == 3:
                    _ts_set(pkt, pos + 14, (_ts_time(pkt, pos + 14) + shift) % (1 << 33))
            pkt[3] = (pkt[3] & 0xF0) | (((pkt[3] & 0x0F) + k * counts.get(pid, 0)) & 0x0F)
        out += pkt
    return bytes(out)


def slate_playlist():
    """A never-ending "not live right now" picture, so an off-air channel plays a clear message instead of failing."""
    n = int(time.time() // 4)
    segs = range(n - 5, n + 1)
    lines = ["#EXTM3U", "#EXT-X-VERSION:3", "#EXT-X-TARGETDURATION:4", f"#EXT-X-MEDIA-SEQUENCE:{n - 5}"]
    for k in segs:
        lines += ["#EXTINF:4.000,", f"/slate/{k}.ts"]
    return "\n".join(lines) + "\n"


def yt_trim(master, max_height=720):
    """YouTube lists every quality; Jellyfin then probes all of them and takes over a minute to start. Keep one (best up to 720p)."""
    lines, best = master.splitlines(), None
    for i, ln in enumerate(lines):
        m = re.search(r"RESOLUTION=\d+x(\d+)", ln)
        if ln.startswith("#EXT-X-STREAM-INF") and m and i + 1 < len(lines):
            h = int(m.group(1))
            if h <= max_height and (best is None or h > best[0]):
                best = (h, ln, lines[i + 1])
    if not best:
        return master
    aud = re.search(r'AUDIO="([^"]+)"', best[1])
    keep = [ln for ln in lines if ln.startswith("#EXT-X-MEDIA") and aud and f'GROUP-ID="{aud.group(1)}"' in ln]
    return "\n".join(["#EXTM3U", "#EXT-X-INDEPENDENT-SEGMENTS"] + keep + [best[1], best[2]]) + "\n"

LIVETV_SEL, LIVETV_OUT = os.path.join(os.environ.get("DATA_DIR", "/data"), "livetv.json"), "/livetv/channels.m3u"


def livetv_refresh():
    """Rebuild the Live TV channel list (dead streams out, new ones in). Jellyfin re-reads the file with its daily guide refresh."""
    if not os.path.exists(LIVETV_SEL) or not os.path.isdir(os.path.dirname(LIVETV_OUT)):
        return
    try:
        import livetv
        import viaproxy
        ex = viaproxy.exits()
        probe = (lambda url: next((k for k in ex if viaproxy.probe(k, url)), None)) if ex else None   # region-locked channels through a VPN exit
        stats = livetv.build(json.load(open(LIVETV_SEL)), LIVETV_OUT, check=True, vpn_probe=probe)
        _livetv.update(last=time.time(), stats=stats, error=None)
        print("live tv list refreshed:", stats["channels"], "channels", flush=True)
    except Exception as e:  # noqa: BLE001 - keep the old list, try again tomorrow
        _livetv["error"] = str(e)[:200]


def yt_prewarm_loop():
    """Keep every wanted YouTube channel's stream address fresh so pressing play does not wait for the lookup."""
    time.sleep(20)
    while True:
        try:
            refs = json.load(open(LIVETV_SEL)).get("youtube") or []
        except (OSError, ValueError):
            refs = []
        for ref in refs:
            if YT_REF.match(ref):
                _yt.pop(ref, None)
                try:
                    yt_resolve(ref)
                except Exception:  # noqa: BLE001 - not live right now, or YouTube busy: retried next round
                    pass
        time.sleep(240)


def livetv_loop():
    time.sleep(600)
    while True:
        livetv_refresh()
        time.sleep(86400)


sys.path.append(os.environ.get("DATA_DIR", "/data"))     # lets a standalone install drop extra modules next to its data


if __name__ == "__main__":
    threading.Thread(target=livetv_loop, daemon=True).start()
    threading.Thread(target=yt_prewarm_loop, daemon=True).start()
    print("regional indexer adapter on :9120", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 9120), H).serve_forever()
