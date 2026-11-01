"""Tests for the monitoring (Beszel) setup and the thermal guard. Needs no Docker and no sensors. Run: python3 tools/test_monitoring.py"""
import os
import pathlib
import subprocess
import sys
import tempfile
import types

sys.modules.setdefault("yaml", types.ModuleType("yaml"))
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wizard" / "app"))
import monitoring as M  # noqa: E402
import stack as S  # noqa: E402

# 1. sizes follow the machine
small, big = M.sizing({"ram_mb": 2048, "cpus": 2}), M.sizing({"ram_mb": 32768, "cpus": 16})
assert small["hub_mem"] == "256m" and big["hub_mem"] == "512m" and small["hub_cpus"] < big["hub_cpus"]

# 2. the temperature alert follows the chip's own limit, and only exists when the machine reports temperatures
rules = lambda hw: {n: (v, m) for n, v, m in M.alert_rules(hw)}  # noqa: E731
assert rules({"temps": True, "crit": 100})["Temperature"] == (92, 10)
assert rules({"temps": True, "crit": 105})["Temperature"][0] == 95
assert rules({"temps": True, "crit": 85})["Temperature"][0] == 77
assert rules({"temps": True})["Temperature"][0] == 90
assert "Temperature" not in rules({"temps": False})

# 3. the probe output is understood
hw = M.parse_probe("temp coretemp 51000 100000 100000\nrapl\n")
assert hw == {"temps": True, "crit": 100, "rapl": True}, hw
assert M.parse_probe("") == {"temps": False, "crit": None, "rapl": False}

# 4. every media drive is watched on Linux, none elsewhere
mounts = [{"host": "/mnt/Media", "container": "/data"}, {"host": "/mnt/Movies 2", "container": "/movies"}]
assert [l for l, _ in M.watched_drives(mounts, "linux")] == ["Media", "Movies-2"]
assert M.watched_drives(mounts, "mac") == []

# 5. the compose services
cfg = {"login": {"password": "abcd"}, "hostOs": "linux"}
assert len(M.password_for(cfg)) == 20 and M.password_for({"login": {"password": "longenough1"}}) == "longenough1"
svc = M.services(cfg, mounts, {"ram_mb": 8192, "cpus": 4}, lambda p: f"/stack/{p}", 8091, "UTC", "ssh-ed25519 AAAA")
assert svc["beszel-agent"]["network_mode"] == "host" and "KEY=ssh-ed25519 AAAA" in svc["beszel-agent"]["environment"]
assert "/mnt/Media:/extra-filesystems/Media:ro" in svc["beszel-agent"]["volumes"]
assert svc["beszel"]["ports"] == ["8091:8090"] and svc["beszel"]["mem_limit"] == "384m"
assert "/stack/config/beszel/socket:/beszel_socket" in svc["beszel"]["volumes"]
full = S.compose({"ports": dict(S.DEFAULT_PORTS), "storage": {"mode": "single", "base": "/data"}, "uid": 1000, "gid": 1000, "tz": "UTC", "qbit": {},
                  "login": {"username": "a", "password": "abcd"}, "beszelKey": "k", "hardware": {"ram_mb": 8192, "cpus": 4},
                  "services": {"beszel": True}})["services"]
assert {"beszel", "beszel-agent"} <= set(full) and full["beszel"]["logging"]["options"]["max-size"] == "50m"

# 6. the thermal guard steps down and back up from a fake sensor and a fake power limit, whatever the chip
GUARD = ROOT / "extras" / "Monitoring" / "thermal-guard.sh"


def run(temp_c, level_dir, limit=100):
    # every run is a fresh start of the guard, so put the machine's normal settings back first
    (level_dir / "rapl" / "constraint_0_power_limit_uw").write_text("14000000")
    (level_dir / "rapl" / "constraint_1_power_limit_uw").write_text("18000000")
    (level_dir / "f0").write_text("1400000")
    (level_dir / "temp").write_text(str(temp_c * 1000))
    env = {**os.environ, "TEMP_FILE": str(level_dir / "temp"), "LIMIT_C": str(limit), "RAPL": str(level_dir / "rapl"),
           "CPUFREQ": str(level_dir / "f*"), "ONCE": "1"}
    return subprocess.run(["bash", str(GUARD)], env=env, capture_output=True, text=True)


with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    (d / "rapl").mkdir()
    (d / "rapl" / "constraint_0_power_limit_uw").write_text("14000000")
    (d / "rapl" / "constraint_1_power_limit_uw").write_text("18000000")
    (d / "f0").write_text("1400000")
    pl1 = lambda: int((d / "rapl" / "constraint_0_power_limit_uw").read_text())  # noqa: E731
    assert run(60, d).stdout == "" and pl1() == 14000000, "cool: nothing changes"
    r = run(86, d)
    assert "level 1" in r.stdout and pl1() == 9100000, r.stdout + r.stderr          # 65% of 14 W, from 100 - 15 = 85 C
    assert run(96, d).stdout.startswith("level 3") and pl1() == 4200000
    assert (d / "f0").read_text().strip() == str(1400000 * 30 // 100)
    assert run(70, d, limit=100).returncode == 0
    # a chip with a lower limit is guarded earlier
    assert "level 1" in run(72, d, limit=85).stdout, "85 C limit: level 1 starts at 70 C"
    assert run(50, d).returncode == 0
    # no sensor at all: say so and stop
    r = subprocess.run(["bash", str(GUARD)], env={**os.environ, "TEMP_FILE": "/nonexistent"}, capture_output=True, text=True)
    assert r.returncode == 1 and "no CPU temperature sensor" in r.stderr
print("Monitoring tests passed.")
