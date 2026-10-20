"""Tests for the generated compose file. Needs no Docker. Run: python3 tools/test_compose.py"""
import pathlib
import sys
import types

sys.modules.setdefault("yaml", types.ModuleType("yaml"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "wizard" / "app"))
import stack as S  # noqa: E402

CFG = {"ports": dict(S.DEFAULT_PORTS), "storage": {"mode": "single", "base": "/data"}, "uid": 1000, "gid": 1000, "tz": "UTC", "qbit": {},
       "login": {"username": "a", "password": "abcd"}, "services": {"jellyfin": True, "seerr": True, "bazarr": True, "homepage": True, "komga": True,
                                                                     "kapowarr": True, "kaizoku": True, "scrutiny": True, "metube": True}}
svc = S.compose(CFG)["services"]
assert len(svc) > 10, "the full stack is generated"
for name, conf in svc.items():
    assert conf["logging"]["options"] == {"max-size": "50m", "max-file": "3"}, f"{name} has no log limit"
assert svc["kaizoku"]["image"].startswith("maxpiva/kaizoku-net"), "manga uses Kaizoku.NET"
assert not any("mylar" in n for n in svc), "Mylar is gone"
assert "kaizoku-db" not in svc and "kaizoku-redis" not in svc, "Kaizoku.NET needs no database"
print("Compose tests passed.")
