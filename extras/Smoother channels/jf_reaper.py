#!/usr/bin/env python3
"""Stops Jellyfin helper processes that were left running: a stream probe that never finishes, or a live-TV stream that no player is
using any more (a TV switched off or a browser tab closed never tells Jellyfin to stop). Run from cron every 2 minutes on the Docker host.
A live stream is kept while a Jellyfin session is playing that channel, and for 5 minutes after it started (players take a few seconds
to report). Re-encoder processes (relay/) belong to livetv_sidecar.py and are left alone."""
import json, os, subprocess, urllib.parse, urllib.request

KEY = "data/.jellyfin_arr_key"
LIST = "livetv/channels.m3u"


def api(path):
    tok = open(KEY).read().strip()
    r = urllib.request.Request("http://localhost:8096" + path, headers={"Authorization": f'MediaBrowser Token="{tok}"'})
    return json.loads(urllib.request.urlopen(r, timeout=20).read())


def watched_addresses():
    """Stream addresses of the channels that sessions are playing right now, or None if that cannot be told (then nothing is killed)."""
    try:
        names = {s["NowPlayingItem"]["Name"] for s in api("/Sessions") if s.get("NowPlayingItem")}
    except Exception:  # noqa: BLE001
        return None
    urls, cur = set(), None
    for line in open(LIST, encoding="utf8"):
        line = line.strip()
        if line.startswith("#EXTINF"):
            cur = line.rsplit(",", 1)[-1].strip()
        elif line and not line.startswith("#"):
            if cur in names:
                urls.add(line)
                urls.add(line.rsplit("/", 1)[-1])
            cur = None
    return urls


def restart_unhealthy_vpn():
    """A VPN exit stuck on a server that refuses the login stays unhealthy for ever; restarting it makes gluetun pick another server."""
    out = subprocess.run(["docker", "ps", "--filter", "name=gluetun", "--filter", "health=unhealthy", "--format", "{{.Names}}"],
                         capture_output=True, text=True).stdout.split()
    for name in out:
        subprocess.run(["docker", "restart", name], capture_output=True, timeout=120)
        print("restarted unhealthy VPN exit", name, flush=True)


def main():
    restart_unhealthy_vpn()
    keep = None
    for line in subprocess.run(["ps", "-eo", "pid,etimes,args"], capture_output=True, text=True).stdout.splitlines()[1:]:
        pid, age, args = line.split(None, 2)
        exe = os.path.basename(args.split()[0])      # the server itself has "jellyfin-ffmpeg" in its arguments: only touch the tools
        if exe not in ("ffmpeg", "ffprobe") or "relay/" in args:
            continue
        age = int(age)
        if exe == "ffprobe" and age > 180:
            os.kill(int(pid), 9)
            print("killed stuck probe", pid, age, args[-100:], flush=True)
        elif exe == "ffmpeg" and age > 300 and " -i " in args:
            keep = watched_addresses() if keep is None else keep
            if keep is not None and not any(u in args for u in keep if u):
                os.kill(int(pid), 9)
                print("killed stream nobody is using", pid, age, args.split(" -i ")[1][:90], flush=True)


if __name__ == "__main__":
    main()
