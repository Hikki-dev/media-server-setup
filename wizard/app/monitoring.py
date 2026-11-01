"""Beszel: health monitoring (CPU, memory, drives, temperatures, containers) sized to the machine it runs on.

Nothing here is fixed. How much memory the monitor may use, which drives it watches and the temperature that
counts as "very bad" all come from the hardware that is found. Pure functions, so tools/test_monitoring.py needs no Docker.
"""
import hashlib
import json
import os
import re
import time
import urllib.request

HUB_PORT = 8090            # inside the container
SOCKET_DIR = "config/beszel/socket"
DATA_DIR = "config/beszel/hub_data"
ADMIN_EMAIL = "admin@beszel.local"

# Read the CPU temperature limits from the machine itself. Runs in a throw-away helper container with /sys mounted.
PROBE = (
    "for f in /h/class/hwmon/hwmon*/name; do d=$(dirname $f); n=$(cat $f); "
    "case $n in coretemp|k10temp|cpu_thermal|zenpower|soc_thermal) "
    "echo \"temp $n $(cat $d/temp1_input 2>/dev/null) $(cat $d/temp1_crit 2>/dev/null) $(cat $d/temp1_max 2>/dev/null)\";; esac; done; "
    "[ -d /h/class/powercap/intel-rapl:0 ] && echo rapl; true"
)


def parse_probe(out):
    """{"temps": bool, "crit": degrees C or None, "rapl": bool} from the probe's output."""
    hw = {"temps": False, "crit": None, "rapl": False}
    for line in (out or "").splitlines():
        parts = line.split()
        if line.strip() == "rapl":
            hw["rapl"] = True
        elif parts[:1] == ["temp"] and len(parts) >= 3:
            hw["temps"] = True
            limits = [int(x) // 1000 for x in parts[3:] if x.isdigit() and int(x) > 1000]
            if limits:
                hw["crit"] = max(limits)
    return hw


def detect(sh, host_os):
    """What this machine has: cores, memory, whether it reports temperatures, and its temperature limit."""
    hw = {"cpus": 2, "ram_mb": 4096, "temps": False, "crit": None, "rapl": False}
    r = sh(["docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}"], timeout=30, check=False)
    m = re.match(r"\s*(\d+)\s+(\d+)", getattr(r, "stdout", "") or "")
    if m:
        hw["cpus"], hw["ram_mb"] = int(m.group(1)), int(m.group(2)) // (1024 * 1024)
    if host_os == "linux":     # on Windows and Mac Docker runs in a hidden VM, which has no temperature sensors of the real chip
        p = sh(["docker", "run", "--rm", "-v", "/sys:/h:ro", "alpine:3", "sh", "-c", PROBE], timeout=120, check=False)
        hw.update(parse_probe(getattr(p, "stdout", "")))
    return hw


def sizing(hw):
    """Memory and CPU the two containers may use: small machines get small caps, big ones room to breathe."""
    ram = hw.get("ram_mb", 4096)
    hub = 256 if ram <= 4096 else 384 if ram <= 16384 else 512
    agent = 96 if ram <= 4096 else 128 if ram <= 16384 else 192
    cpus = hw.get("cpus", 2)
    return {"hub_mem": f"{hub}m", "agent_mem": f"{agent}m",
            "hub_cpus": 0.25 if cpus <= 2 else 0.5, "agent_cpus": 0.25}


def alert_rules(hw):
    """When to be pinged: only when something is really wrong. [(name, value, minutes)].

    The temperature line sits 8 degrees under the chip's own limit, so a chip that idles warm does not ping all day
    but one close to its limit does. A chip that reports no limit gets 90.
    """
    crit = hw.get("crit")
    temp = max(75, min(95, crit - 8)) if crit else 90
    rules = [("Status", 1, 5), ("CPU", 90, 10), ("Memory", 90, 10), ("Disk", 90, 10)]
    if hw.get("temps"):
        rules.append(("Temperature", temp, 10))
    return rules


def watched_drives(plan_mounts, host_os):
    """Each media drive, as (label, host path): the monitor shows how full every one is."""
    if host_os != "linux":
        return []
    seen, out = set(), []
    for m in plan_mounts:
        host = m["host"]
        label = re.sub(r"[^A-Za-z0-9._-]+", "-", os.path.basename(host.rstrip("/")) or "drive").strip("-") or "drive"
        if host not in seen:
            seen.add(host)
            out.append((label, host))
    return out


def password_for(cfg):
    """The hub's admin password: the setup login when it is long enough, otherwise one made from it."""
    pw = (cfg.get("login") or {}).get("password") or ""
    return pw if len(pw) >= 8 else hashlib.sha256((pw + ":beszel").encode()).hexdigest()[:20]


HEAL = {"deunhealth.restart.on.unhealthy": "true"}


def _health(cmd):
    # these images have no shell, so the check is the program's own "health" command
    return {"test": ["CMD"] + cmd, "interval": "60s", "timeout": "15s", "retries": 3, "start_period": "20s"}


def services(cfg, plan_mounts, hw, hostpath, port, tz, public_key):
    """The two compose services. hostpath(sub) gives a folder inside the stack folder on the host."""
    size = sizing(hw)
    drives = watched_drives(plan_mounts, cfg.get("hostOs"))
    agent_vols = [f"{hostpath(SOCKET_DIR)}:/beszel_socket", "/var/run/docker.sock:/var/run/docker.sock:ro"]
    agent_vols += [f"{host}:/extra-filesystems/{label}:ro" for label, host in drives]
    hub = {"image": "henrygd/beszel:latest", "restart": "unless-stopped",
           "environment": [f"TZ={tz}", f"USER_EMAIL={ADMIN_EMAIL}", f"USER_PASSWORD={password_for(cfg)}"],
           "volumes": [f"{hostpath(DATA_DIR)}:/beszel_data", f"{hostpath(SOCKET_DIR)}:/beszel_socket"],
           "mem_limit": size["hub_mem"], "cpus": size["hub_cpus"], "ports": [f"{port}:{HUB_PORT}"],
           "healthcheck": _health(["/beszel", "health", "--url", f"http://localhost:{HUB_PORT}"]), "labels": HEAL}
    agent = {"image": "henrygd/beszel-agent:latest", "restart": "unless-stopped", "network_mode": "host",
             "environment": ["LISTEN=/beszel_socket/beszel.sock", f"KEY={public_key}"],
             "volumes": agent_vols, "mem_limit": size["agent_mem"], "cpus": size["agent_cpus"],
             "healthcheck": _health(["/agent", "health"]), "labels": HEAL}
    return {"beszel": hub, "beszel-agent": agent}


def ensure_key(stack_dir, run):
    """The hub signs in to the agent with a key pair. Make it once (the hub reads id_ed25519 from its data folder) and return the public half."""
    d = f"{stack_dir}/{DATA_DIR}"
    os.makedirs(d, exist_ok=True)
    key = f"{d}/id_ed25519"
    if not os.path.exists(key):
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "beszel", "-f", key])
    return run(["ssh-keygen", "-y", "-f", key]).stdout.strip()


def _call(method, url, body=None, token=None):
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", token)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or b"{}")


def configure(base, cfg, hw, log, wait=120):
    """Sign in to the hub, add this machine as a system and create the alert rules. Safe to run again."""
    deadline = time.time() + wait
    token = None
    while time.time() < deadline and not token:
        try:
            token = _call("POST", f"{base}/api/collections/users/auth-with-password",
                          {"identity": ADMIN_EMAIL, "password": password_for(cfg)}).get("token")
        except Exception:  # noqa: BLE001 - the hub is still starting
            time.sleep(3)
    if not token:
        raise RuntimeError("the monitor did not start in time")
    api = f"{base}/api/collections"
    user = _call("GET", f"{api}/users/records?perPage=1", token=token)["items"][0]["id"]
    systems = _call("GET", f"{api}/systems/records?perPage=50", token=token)["items"]
    mine = next((s for s in systems if s.get("host", "").endswith("beszel.sock")), None)
    if not mine:
        mine = _call("POST", f"{api}/systems/records", {"name": "This server", "host": "/beszel_socket/beszel.sock", "port": "",
                                                       "users": [user]}, token=token)
    have = {a["name"] for a in _call("GET", f"{api}/alerts/records?perPage=100&filter=system%3D%22{mine['id']}%22", token=token)["items"]}
    for name, value, minutes in alert_rules(hw):
        if name not in have:
            _call("POST", f"{api}/alerts/records", {"name": name, "system": mine["id"], "user": user, "value": value, "min": minutes}, token=token)
    log("Monitoring ready: alerts only for real trouble"
        + (f" (temperature above {dict((n, v) for n, v, _ in alert_rules(hw))['Temperature']} C)" if hw.get("temps") else ""))
    return mine["id"]
