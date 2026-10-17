#!/usr/bin/env python3
"""On-demand re-encoder for the channels listed in data/reencode.json (written by livetv_sync.py).

Some streams cannot be decoded cleanly when Jellyfin only copies them (for example no parameter sets at the start). Jellyfin's own
ffmpeg re-encodes them into a clean HLS stream. To spare the server, the encoder only runs while someone is watching: the channel
list points at this small web server, which starts the encoder on the first request, waits for the first chunks, serves them, and
stops the encoder three minutes after the last request. Run from cron every minute; it only makes sure this server is running."""
import json, os, shlex, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = "data/reencode.json"
HOST_DIR = "livetv/relay"
PORT, IDLE, START_WAIT, GRACE = 9130, 180, 45, 90
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
last, lock = {}, threading.Lock()


def items():
    try:
        return {i["slug"]: i["src"] for i in json.load(open(STATE))}
    except (OSError, ValueError):
        return {}


def pid_of(slug):
    out = subprocess.run(["pgrep", "-f", f"[r]elay/{slug}/s%d"], capture_output=True, text=True).stdout.split()
    return out[0] if out else ""


def playlist_age(slug):
    try:
        return time.time() - os.stat(f"{HOST_DIR}/{slug}/index.m3u8").st_mtime
    except OSError:
        return 9999


def stop(slug):
    subprocess.run(["docker", "exec", "jellyfin", "pkill", "-f", f"[r]elay/{slug}/s%d"], capture_output=True, timeout=60)


def start(slug, src):
    d, pl = f"/config/livetv/relay/{slug}", f"/config/livetv/relay/{slug}/index.m3u8"
    gpu = os.path.exists("/dev/dri/renderD128")      # Intel QSV: far less CPU than a software encode
    enc = "-init_hw_device vaapi=va:/dev/dri/renderD128 -init_hw_device qsv=hw@va -filter_hw_device hw " if gpu else ""
    vid = ("-vf hwupload=extra_hw_frames=32,vpp_qsv=deinterlace=2:format=nv12 -c:v h264_qsv -preset veryfast -b:v 2500k -maxrate 3500k " if gpu
           else "-vf yadif=0:-1:0 -c:v libx264 -preset veryfast -crf 23 -maxrate 3500k -bufsize 7000k -sc_threshold 0 -pix_fmt yuv420p -profile:v main -level 4.0 ")
    cmd = (f"mkdir -p {d} && rm -f {d}/*.ts {d}/*.m3u8; exec nice -n 10 /usr/lib/jellyfin-ffmpeg/ffmpeg -nostdin -loglevel warning {enc}"
           f"-user_agent {shlex.quote(UA)} -rw_timeout 15000000 -fflags +genpts+discardcorrupt -i {shlex.quote(src)} "
           f"-map 0:v:0 -map 0:a:0? {vid}-g 100 -keyint_min 100 -c:a aac -b:a 128k -ar 48000 -ac 2 "
           f"-f hls -hls_time 2 -hls_list_size 10 -hls_flags delete_segments+independent_segments -hls_segment_filename {d}/s%d.ts {pl}")
    subprocess.run(["docker", "exec", "-d", "jellyfin", "sh", "-c", f"{cmd} > {d}.log 2>&1"], timeout=60)
    print(time.strftime("%F %T"), "started re-encoder for", slug, flush=True)


def segments_ready(slug, n=3):
    try:
        return open(f"{HOST_DIR}/{slug}/index.m3u8").read().count("#EXTINF") >= n and playlist_age(slug) < 10
    except OSError:
        return False


def ensure(slug):
    """Make sure one fresh encoder is running for this channel; wait until its playlist has a few chunks.
    Players ask for the playlist several times at once, so a freshly started encoder gets a grace period (its process is not visible
    for the first moments) and is never started twice."""
    src = items().get(slug)
    if not src:
        return False
    with lock:
        now = time.time()
        last[slug] = now
        began = last.get(slug + "#started", 0)
        if now - began > GRACE and (not pid_of(slug) or playlist_age(slug) > 30):
            if pid_of(slug):
                stop(slug)
                time.sleep(1)
            start(slug, src)
            last[slug + "#started"] = time.time()
    for _ in range(START_WAIT * 2):
        if segments_ready(slug):
            return True
        time.sleep(0.5)
    return False


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        parts = self.path.split("?")[0].strip("/").split("/")
        if len(parts) != 2 or ".." in parts[1] or parts[1].rsplit(".", 1)[-1] not in ("m3u8", "ts"):
            return self.send_error(404)
        slug, name = parts
        if name.endswith(".m3u8") and not ensure(slug):
            return self.send_error(503, "encoder not ready")
        last[slug] = time.time()
        try:
            data = open(f"{HOST_DIR}/{slug}/{name}", "rb").read()
        except OSError:
            return self.send_error(404)
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.apple.mpegurl" if name.endswith(".m3u8") else "video/mp2t")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def reaper():
    """Every few seconds: restart an encoder that died while someone is watching (some sources end a session after a few minutes),
    and stop the ones nobody has asked for during the last IDLE seconds."""
    tick = 0
    while True:
        time.sleep(5)
        tick += 1
        wanted = items()
        for slug, src in wanted.items():
            idle = time.time() - last.get(slug, 0)
            running = pid_of(slug)
            if not running and idle < IDLE:
                with lock:
                    began = last.get(slug + "#started", 0)
                    wait = last.get(slug + "#wait", 8)
                    if time.time() - began > wait and not pid_of(slug):
                        # a source that is off the air makes the encoder die at once: back off so it is not hammered (8 s up to 2 min)
                        short = time.time() - began < wait + 25
                        last[slug + "#wait"] = min(wait * 2, 120) if short else 8
                        start(slug, src)
                        last[slug + "#started"] = time.time()
            elif running and idle > IDLE:
                stop(slug)
                print(time.strftime("%F %T"), "stopped idle re-encoder for", slug, flush=True)
        if tick % 6 == 0:
            for line in subprocess.run(["pgrep", "-fa", "[r]elay/.*/s%d"], capture_output=True, text=True).stdout.splitlines():
                slug = line.split("relay/")[-1].split("/")[0]
                if slug and slug not in wanted:
                    stop(slug)


def serve():
    gw = subprocess.run(["docker", "inspect", "jellyfin", "--format", "{{range .NetworkSettings.Networks}}{{.Gateway}} {{end}}"],
                        capture_output=True, text=True).stdout.split()
    threading.Thread(target=reaper, daemon=True).start()
    ThreadingHTTPServer((gw[0], PORT), H).serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        serve()
    elif items() and subprocess.run(["pgrep", "-f", "[l]ivetv_sidecar.py serve"], capture_output=True).returncode:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "serve"], stdout=open("sidecar.log", "a"),
                         stderr=subprocess.STDOUT, start_new_session=True)
