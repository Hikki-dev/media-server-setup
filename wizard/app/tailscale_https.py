#!/usr/bin/env python3
"""Gives every web app on this computer a private HTTPS address with Tailscale, and points Homepage at those addresses.

What it does, in plain words:
  1. Finds every Docker container that offers a web page on a port of this computer.
  2. Checks that the port really speaks plain web (HTTP), so file sharing, DNS and databases are never touched.
  3. Asks Tailscale for an address like  https://your-server.your-tailnet.ts.net:18096  for each one.
  4. Optionally rewrites the links in Homepage to use those addresses.

The addresses work only for devices signed in to your Tailscale account (or devices you shared the server with).
Nothing is opened on your router and nothing goes on the public internet.

It only ever ADDS addresses. It never resets or removes the ones you already have, so it is safe to run again and
again, for example every few minutes to pick up new containers.

Use:
  python3 tailscale_https.py                        show what it would do
  python3 tailscale_https.py --apply                add the missing addresses
  python3 tailscale_https.py --apply --homepage /path/to/services.yaml
  python3 tailscale_https.py --apply --loop 300     keep checking every 5 minutes
  python3 tailscale_https.py --skip adguard --extra qbittorrent=8080    leave one out, add a host network app by hand
"""
import argparse
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time

# Containers that should never get an address: they can be misused by anyone who reaches them.
NEVER = ("flaresolverr", "solver", "trawl", "byparr", "postgres", "redis", "gluetun", "docker-proxy", "watchtower")
# Ports that are never plain web pages (the check below would refuse them anyway).
NOT_WEB = {22, 25, 53, 67, 68, 123, 139, 445, 853, 1883, 3306, 5432, 5433, 6379, 9443, 27017}
# Known tool ports that answer like a web page but are not meant to be opened by hand.
NOT_WEB_PAIRS = {("portainer", 8000), ("portainer-ee", 8000), ("rustdesk", 21114), ("rustdesk-server", 21114)}
FUNNEL = {443, 8443, 10000}      # kept free on purpose: these are the only ports Tailscale can show on the public internet


def sh(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, "", str(e)


# ------------------------------------------------------------------ reading what exists
def parse_ports(text):
    """Published TCP ports from `docker ps --format "{{.Names}}|{{.Ports}}"` lines: {container: [host ports]}."""
    out = {}
    for line in (text or "").splitlines():
        if "|" not in line:
            continue
        name, ports = line.split("|", 1)
        found = sorted({int(m.group(1)) for m in re.finditer(r":(\d+)->\d+/tcp", ports)})
        if found:
            out[name.strip()] = found
    return out


def parse_serve(text, dns):
    """Addresses Tailscale already serves: {https port: upstream port}. Reads `tailscale serve status --json`."""
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return {}
    out = {}
    for key, web in (data.get("Web") or {}).items():
        host, _, port = key.rpartition(":")
        if not port.isdigit():
            continue
        for h in (web.get("Handlers") or {}).values():
            m = re.search(r"//(?:localhost|127\.0\.0\.1|\[::1\]):(\d+)", h.get("Proxy") or "")
            if m:
                out[int(port)] = int(m.group(1))
                break
    return out


def url_of(dns, https):
    return f"https://{dns}" if https == 443 else f"https://{dns}:{https}"


def assign(port, taken):
    """The HTTPS port for an app. Easy to remember: 8096 becomes 18096. Never one of the public internet ports."""
    want = 10000 + port if port < 10000 else 20000 + port
    if want > 65000:
        want = 12000 + (port % 40000)
    while want in taken or want in FUNNEL:
        want += 1
    return want


def is_web(port, host="127.0.0.1"):
    """True when the port answers a plain web request (any status). TLS-only ports and other protocols are refused."""
    try:
        c = http.client.HTTPConnection(host, port, timeout=3)
        c.request("GET", "/", headers={"User-Agent": "tailscale-https-check"})
        r = c.getresponse()
        body = r.read(400).decode("latin-1", "replace")
        c.close()
    except (OSError, http.client.HTTPException, ValueError):
        return False
    if r.status == 400 and "HTTPS" in body.upper() and "PLAIN HTTP" in body.upper():
        return False
    return 100 <= r.status < 600


def plan(containers, existing, dns, skip=(), extra=None, probe=is_web, remembered=None):
    """The list of addresses: each {"name", "port", "https", "url", "state"}.

    containers: {name: [ports]}. existing: {https port: upstream port}. extra: {name: port} for apps docker cannot list
    (apps on the host network). remembered: {upstream port: https port} kept from earlier runs, so an address never changes. state is "have" (already served), "add" (will be added) or "skip" (with a reason).
    """
    items, taken = [], set(existing)
    by_up = {}
    for https, up in existing.items():
        by_up.setdefault(up, https)
    wanted = [(n, p) for n, ps in sorted(containers.items()) for p in ps] + sorted((extra or {}).items())
    for name, port in [(n, p) for n, p in wanted]:
        low = name.lower()
        base = {"name": name, "port": port}
        if any(low.startswith(n) or n in low for n in NEVER) or low in {s.lower() for s in skip}:
            items.append({**base, "state": "skip", "reason": "left out on purpose"})
            continue
        if port in NOT_WEB or (low, port) in NOT_WEB_PAIRS:
            items.append({**base, "state": "skip", "reason": "not a web page"})
            continue
        if port in by_up:
            h = by_up[port]
            items.append({**base, "https": h, "url": url_of(dns, h), "state": "have"})
            continue
        if not probe(port):
            items.append({**base, "state": "skip", "reason": "does not answer as a web page"})
            continue
        h = (remembered or {}).get(port)
        if not h or h in taken:
            h = assign(port, taken)
        taken.add(h)
        by_up[port] = h
        items.append({**base, "https": h, "url": url_of(dns, h), "state": "add"})
    return items


# ------------------------------------------------------------------ homepage
def update_homepage(text, items):
    """Point the href of every Homepage tile that names a container at its HTTPS address. Comments and layout are kept.

    A tile is a block that starts with  - Name:  and has a  container: name  line. Returns (new text, how many changed).
    """
    urls = {}
    for i in items:
        if i.get("url") and i["state"] in ("have", "add", "added"):
            urls.setdefault(i["name"], i["url"])
    lines, changed, i = text.split("\n"), 0, 0
    starts = [n for n, l in enumerate(lines) if re.match(r"^\s*- [^:#]+:\s*$", l)]
    for k, s in enumerate(starts):
        e = starts[k + 1] if k + 1 < len(starts) else len(lines)
        block = range(s + 1, e)
        cont = next((re.match(r"^\s*container:\s*(\S+)", lines[n]).group(1) for n in block if re.match(r"^\s*container:\s*\S+", lines[n])), None)
        if not cont or cont not in urls:
            continue
        href = next((n for n in block if re.match(r"^\s*href:\s*", lines[n])), None)
        if href is not None:
            if urls[cont] not in lines[href]:
                lines[href] = re.sub(r"(href:\s*).*", lambda m: m.group(1) + urls[cont], lines[href])
                changed += 1
        else:
            indent = re.match(r"^(\s*)", lines[next(n for n in block if re.match(r"^\s*container:", lines[n]))]).group(1)
            lines.insert(s + 1, f"{indent}href: {urls[cont]}")
            starts = [n + (1 if n > s else 0) for n in starts]
            changed += 1
    return "\n".join(lines), changed


# ------------------------------------------------------------------ doing it
def tailscale_state():
    """(dns name, problem). The problem is a plain sentence, or None when Tailscale is ready."""
    if not shutil.which("tailscale"):
        return None, "Tailscale is not installed on this computer. Install it from tailscale.com/download and sign in."
    rc, out, err = sh(["tailscale", "status", "--json"])
    if rc != 0:
        return None, "Tailscale is not running or you are not signed in: " + (err or out).strip()[:160]
    try:
        d = json.loads(out)
    except ValueError:
        return None, "Tailscale did not answer in a way this tool understands."
    if d.get("BackendState") != "Running":
        return None, f"Tailscale is {d.get('BackendState', 'not ready')}. Sign in with: tailscale up"
    dns = (d.get("Self") or {}).get("DNSName", "").rstrip(".")
    if not dns:
        return None, "Tailscale has no address name for this computer yet. Turn on MagicDNS in the Tailscale admin page."
    return dns, None


def load_state(path):
    try:
        return {int(k): int(v) for k, v in json.load(open(path)).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def save_state(path, mapping):
    try:
        with open(path, "w") as f:
            json.dump({str(k): v for k, v in sorted(mapping.items())}, f, indent=1)
    except OSError:
        pass


def run(args):
    dns, problem = tailscale_state()
    if problem:
        return {"ok": False, "problem": problem, "items": []}
    rc, out, _ = sh(["tailscale", "serve", "status", "--json"])
    existing = parse_serve(out, dns)
    rc, out, err = sh(["docker", "ps", "--format", "{{.Names}}|{{.Ports}}"], 30)
    if rc != 0:
        return {"ok": False, "problem": "Docker did not answer: " + err.strip()[:160], "items": []}
    containers = parse_ports(out)
    if getattr(args, "only", None):
        keep = set(args.only)
        containers = {n: ps for n, ps in containers.items() if n in keep}
    extra = {}
    for e in args.extra or []:
        n, _, p = e.partition("=")
        if p.isdigit():
            extra[n] = int(p)
    host = "host.docker.internal" if args.from_container else "127.0.0.1"
    skip = [s for chunk in (args.skip or []) for s in chunk.split(",") if s]
    remembered = load_state(args.state)
    items = plan(containers, existing, dns, skip, extra, probe=lambda p: is_web(p, host), remembered=remembered)
    # addresses made on an earlier run that Tailscale has lost (after a reset) or that docker cannot list: bring them back
    covered = set(existing.values()) | {i["port"] for i in items}
    used = set(existing) | {i["https"] for i in items if i.get("https")}
    for up, https in sorted(remembered.items()):
        if up not in covered and https not in used:
            items.append({"name": f"port {up}", "port": up, "https": https, "url": url_of(dns, https), "state": "add", "reason": "remembered from before"})
            used.add(https)
    problem = None
    for i in items:
        if i["state"] != "add" or not args.apply:
            continue
        rc, _, err = sh(["tailscale", "serve", "--bg", f"--https={i['https']}", f"http://localhost:{i['port']}"], 30)
        if rc == 0:
            i["state"] = "added"
        else:
            i["state"], i["reason"] = "failed", err.strip()[:200]
            if "HTTPS" in err and ("not enabled" in err or "enable" in err.lower()):
                problem = "HTTPS is not turned on for your Tailscale account. In the Tailscale admin page open DNS and press Enable HTTPS."
    if args.apply:
        rc2, raw, _ = sh(["tailscale", "serve", "status", "--json"])
        if rc2 == 0 and raw.strip():
            try:
                open(args.state + ".snapshot", "w").write(raw)     # the full settings, kept in case something needs putting back by hand
            except OSError:
                pass
        keep = {**remembered, **{up: https for https, up in existing.items()}}
        keep.update({i["port"]: i["https"] for i in items if i["state"] in ("have", "added")})
        save_state(args.state, keep)
    if args.homepage and args.apply and os.path.exists(args.homepage):
        text = open(args.homepage).read()
        new, n = update_homepage(text, [i for i in items if i["state"] in ("have", "added")])
        if n:
            shutil.copy2(args.homepage, args.homepage + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
            open(args.homepage, "w").write(new)
        for i in items:
            i["homepage"] = n
    return {"ok": problem is None, "problem": problem, "dns": dns, "items": items}


def show(res, applied):
    if res.get("problem"):
        print("\n" + res["problem"] + "\n")
    names = {"have": "already works", "add": "would be added", "added": "added", "skip": "left out", "failed": "failed"}
    for i in res["items"]:
        line = f"  {i['name']:<22} port {i['port']:<6}"
        if i.get("url"):
            line += f" {i['url']}"
        print(f"{line:<78} {names[i['state']]}" + (f" ({i['reason']})" if i.get("reason") else ""))
    if not applied and any(i["state"] == "add" for i in res["items"]):
        print("\nNothing was changed. Add --apply to create the missing addresses.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Private HTTPS addresses for your web apps, with Tailscale.")
    ap.add_argument("--apply", action="store_true", help="create the missing addresses (without this it only shows the plan)")
    ap.add_argument("--homepage", help="path to the Homepage services.yaml whose links should use the addresses")
    ap.add_argument("--loop", type=int, metavar="SECONDS", help="keep running and check again every so many seconds")
    ap.add_argument("--skip", action="append", help="container names to leave out, separated by commas")
    ap.add_argument("--extra", action="append", metavar="NAME=PORT", help="an app docker cannot list, such as one on the host network")
    ap.add_argument("--only", action="append", help="only these container names (the setup uses this so your other containers are left alone)")
    ap.add_argument("--json", metavar="FILE", help="write the result to this file")
    ap.add_argument("--state", default=os.path.expanduser("~/.tailscale-https.json"),
                    help="file that remembers each address, so it stays the same even if Tailscale is reset")
    ap.add_argument("--from-container", action="store_true", help="this tool runs inside a container, so reach host ports through host.docker.internal")
    args = ap.parse_args(argv)
    while True:
        res = run(args)
        show(res, args.apply)
        if args.json:
            with open(args.json, "w") as f:
                json.dump(res, f, indent=1)
        if not args.loop:
            return 0 if res["ok"] else 1
        time.sleep(max(30, args.loop))


if __name__ == "__main__":
    sys.exit(main())
