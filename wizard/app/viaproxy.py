"""Relays live streams through a VPN exit so channels that refuse this country still play.

Each exit is a small HTTP proxy (the gluetun container, connected to the VPN). Jellyfin asks the regional service for
/via/<exit>/<encoded address>; the service fetches the stream through that exit and hands it back. Playlists are rewritten
so every segment is fetched through the same exit. Exits are configured with VPN_PROXIES="uk=http://gluetun-uk:8888,us=...".
"""
import base64
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def exits():
    """Configured exits: VPN_PROXIES="uk=http://gluetun-uk:8888,..." or a vpn-exits.json file next to the service's data."""
    out = {}
    for part in (os.environ.get("VPN_PROXIES") or "").split(","):
        if "=" in part:
            k, val = part.split("=", 1)
            out[k.strip()] = val.strip()
    try:
        out.update(json.load(open(os.path.join(os.environ.get("DATA_DIR", "/data"), "vpn-exits.json"))))
    except (OSError, ValueError):
        pass
    return out


def enc(url):
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


def dec(token):
    token = token.split(".", 1)[0]
    return base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode()


def check_target(url):
    """Only public web addresses: this service must never become a way to reach other machines on the home network."""
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise PermissionError("bad address")
    for info in socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80)):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise PermissionError("private address")


def opener(region):
    if region == "direct":
        return urllib.request.build_opener()
    proxy = exits().get(region)
    if not proxy:
        raise LookupError("unknown exit")
    return urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))


def fetch(region, url, headers=None, timeout=25):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    for attempt in range(3):         # a VPN exit drops a TLS connection now and then
        try:
            return opener(region).open(req, timeout=timeout)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, OSError, ssl.SSLError):
            if attempt == 2:
                raise
            time.sleep(0.4)


# Chunks are fetched ahead of the player: every playlist the relay hands out triggers a background download of its newest chunks, so
# when Jellyfin asks for them they are already here instead of waiting on the VPN round trip.
_chunks, _lock = {}, threading.Lock()
MAX_CHUNK_BYTES, MAX_CACHE_BYTES = 12_000_000, 90_000_000


def _prefetch(region, url):
    with _lock:
        if url in _chunks:
            return
        _chunks[url] = None       # claimed
    try:
        with fetch(region, url, timeout=30) as r:
            data = r.read(MAX_CHUNK_BYTES + 1)
        if len(data) > MAX_CHUNK_BYTES:
            raise ValueError("too big")
        ctype = r.headers.get("Content-Type", "video/mp2t")
        with _lock:
            _chunks[url] = (time.time(), data, ctype)
            while sum(len(c[1]) for c in _chunks.values() if c) > MAX_CACHE_BYTES or len(_chunks) > 80:
                old = min((k for k, c in _chunks.items() if c), key=lambda k: _chunks[k][0], default=None)
                if old is None:
                    break
                _chunks.pop(old)
    except Exception:  # noqa: BLE001 - the normal request path will try again and report the error
        with _lock:
            _chunks.pop(url, None)


def _warm(region, urls):
    """Download the newest chunks in order, one after another (together they would split the VPN's speed and all arrive late)."""
    wanted = urls[-3:]

    def run():
        for u in wanted:
            _prefetch(region, u)
    threading.Thread(target=run, daemon=True).start()


def _ext(url, default="bin"):
    m = re.search(r"\.(m3u8|ts|m4s|mp4|m4a|m4v|aac|ac3|vtt|webvtt|key)(?:$|\?)", urllib.parse.urlparse(url).path + "?")
    return m.group(1) if m else default


def trim_master(text, max_height=720):
    """A master playlist with several qualities makes Jellyfin probe every one (slow, and sometimes it ends up with no usable
    stream at all). Keep one: the best up to 720p (or the one closest to ~3 Mbit/s when sizes are not listed)."""
    lines = text.splitlines()
    variants = [(i, ln) for i, ln in enumerate(lines) if ln.startswith("#EXT-X-STREAM-INF") and i + 1 < len(lines)]
    if len(variants) < 2:
        return text

    def score(item):
        ln = item[1]
        h = re.search(r"RESOLUTION=\d+x(\d+)", ln)
        bw = re.search(r"BANDWIDTH=(\d+)", ln)
        if h:
            return (0, -int(h.group(1))) if int(h.group(1)) <= max_height else (1, int(h.group(1)))
        return (2, abs(int(bw.group(1)) - 3_000_000) if bw else 0)
    i, ln = min(variants, key=score)
    aud = re.search(r'AUDIO="([^"]+)"', ln)
    keep = [x for x in lines if x.startswith("#EXT-X-MEDIA") and aud and "TYPE=AUDIO" in x and f'GROUP-ID="{aud.group(1)}"' in x]
    ln = re.sub(r',?(SUBTITLES|CLOSED-CAPTIONS)="[^"]*"', "", ln)
    return "\n".join(["#EXTM3U"] + keep + [ln, lines[i + 1]]) + "\n"


def rewrite(text, base, region):
    """Point every playlist, chunk and key at the relay. The player only accepts chunks whose name ends in a known extension, so
    chunks without one (common on ad-supported streams) are labelled .ts, playlists .m3u8, init segments .mp4."""
    def to_via(ref, default):
        absu = urllib.parse.urljoin(base, ref)
        return f"/via/{region}/{enc(absu)}.{_ext(absu, default)}"
    out, nxt = [], "ts"
    for line in text.splitlines():
        if line.startswith("#"):
            if line.startswith("#EXT-X-STREAM-INF") or line.startswith("#EXT-X-I-FRAME-STREAM-INF"):
                nxt = "m3u8"
            elif line.startswith("#EXTINF"):
                nxt = "ts"

            def attr(m, line=line):
                d = "mp4" if line.startswith("#EXT-X-MAP") else "key" if "KEY" in line else "m3u8" if line.startswith("#EXT-X-MEDIA") else "ts"
                return f'URI="{to_via(m.group(1), d)}"'
            line = re.sub(r'URI="([^"]+)"', attr, line)
        elif line.strip():
            line = to_via(line.strip(), nxt)
        out.append(line)
    return "\n".join(out) + "\n"


def _segment_urls(text, base):
    if "#EXTINF" not in text:
        return []
    return [urllib.parse.urljoin(base, x.strip()) for x in text.splitlines() if x.strip() and not x.startswith("#")]


def _cached(url):
    """A prefetched chunk, waiting briefly if it is still arriving."""
    for _ in range(400):
        with _lock:
            hit = _chunks.get(url, False)
        if hit is False:
            return None
        if hit:
            return hit
        time.sleep(0.05)
    return None


def serve(handler, region, token):
    """Write the relayed response to an http.server handler."""
    try:
        url = dec(token)
        check_target(url)
        hit = _cached(url)
        if hit:
            handler.send_response(200)
            handler.send_header("Content-Type", hit[2])
            handler.send_header("Content-Length", str(len(hit[1])))
            handler.end_headers()
            try:
                handler.wfile.write(hit[1])
            except (BrokenPipeError, ConnectionResetError):
                pass
            return
        headers = {"Range": handler.headers["Range"]} if handler.headers.get("Range") else None
        r = fetch(region, url, headers)
    except PermissionError as e:
        return handler.reply(403, str(e), "text/plain")
    except LookupError as e:
        return handler.reply(404, str(e), "text/plain")
    except urllib.error.HTTPError as e:
        return handler.reply(e.code if e.code < 600 else 502, f"origin said {e.code}", "text/plain")
    except Exception as e:  # noqa: BLE001 - exit not connected, origin down
        return handler.reply(502, str(e)[:160], "text/plain")
    ctype = r.headers.get("Content-Type", "application/octet-stream")
    if ".m3u8" in urllib.parse.urlparse(url).path.lower() or "mpegurl" in ctype.lower():
        body = r.read(3_000_000)
        if body.lstrip()[:7] == b"#EXTM3U":
            text = trim_master(body.decode("utf8", "ignore"))
            _warm(region, _segment_urls(text, r.geturl()))
            return handler.reply(200, rewrite(text, r.geturl(), region), "application/vnd.apple.mpegurl")
        return handler.reply(200, body, ctype)
    handler.send_response(r.status)
    handler.send_header("Content-Type", ctype)
    for h in ("Content-Length", "Content-Range", "Accept-Ranges"):
        if r.headers.get(h):
            handler.send_header(h, r.headers[h])
    handler.end_headers()
    try:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            handler.wfile.write(chunk)
    except (BrokenPipeError, ConnectionResetError):
        pass


def probe(region, url):
    """True if the stream really starts through this exit: playlist, then the newest video chunk."""
    try:
        check_target(url)
        t0 = time.time()
        with fetch(region, url, timeout=15) as r:
            head = r.read(200_000)
        if head.lstrip()[:7] != b"#EXTM3U":
            return len(head) > 0 and ".m3u8" not in url.lower()
        text, base = head.decode("utf8", "ignore"), url
        for _ in range(2):
            refs = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
            if not refs:
                return False
            nxt = urllib.parse.urljoin(base, refs[0])
            if "EXT-X-STREAM-INF" in text and ".m3u8" in nxt.split("?")[0].lower():
                base = nxt
                with fetch(region, nxt, timeout=15) as r:
                    text = r.read(200_000).decode("utf8", "ignore")
                continue
            break
        refs = [x.strip() for x in text.splitlines() if x.strip() and not x.startswith("#")]
        if not refs:
            return False
        with fetch(region, urllib.parse.urljoin(base, refs[-1]), timeout=15) as r:
            ok = len(r.read(65_536)) >= 1024
        return ok and time.time() - t0 < 9          # through a VPN every step adds delay: keep only channels that start comfortably
    except Exception:  # noqa: BLE001
        return False


def exit_info(region):
    """Which country the exit really appears in (to prove the VPN is connected)."""
    try:
        with fetch(region, "https://ipinfo.io/json", timeout=20) as r:
            d = json.loads(r.read())
        return {"ip": d.get("ip"), "country": d.get("country"), "city": d.get("city")}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)[:100]}
