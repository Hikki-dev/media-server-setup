"""Tests for the drive list in the folder picker. Needs no Docker. Run: python3 tools/test_drives.py
On Windows, Mac and Linux the computer's own (internal) drive must always be offered first, even with no other drive."""
import pathlib
import subprocess
import sys
import types

sys.modules.setdefault("yaml", types.ModuleType("yaml"))      # stack.py imports it, but the drive list does not use it
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "wizard" / "app"))
import stack as S  # noqa: E402

GB = 10 ** 9
FREE = {"freeBytes": 200 * GB, "totalBytes": 500 * GB}


def fake(listing):
    """Stand in for the Docker helper: `listing` maps a host folder to the names inside it."""
    def helper(path, script, **kw):
        names = listing.get(path)
        return subprocess.CompletedProcess([], 0 if names is not None else 1, "\n".join(names or []) + "\n", "")
    S.helper = helper
    S.inspect_path = lambda p, *a: dict(FREE, ok=True, path=p)


def names(r):
    return [d["name"] for d in r["drives"]]


# Mac with no external drive: only the internal one
fake({"/Volumes": ["Macintosh HD"]})
r = S.list_drives("mac", "/Users/someone")
assert names(r) == ["This computer"], names(r)
assert r["drives"][0]["path"] == "/Users/someone" and r["drives"][0]["internal"]

# Mac with an external drive: internal first, then the external
fake({"/Volumes": ["Macintosh HD", "Media"]})
assert names(S.list_drives("mac", "/Users/someone")) == ["This computer", "Media"]

# Linux with nothing mounted: only the internal one. With a data disk: internal first
fake({})
assert names(S.list_drives("linux", "/home/someone")) == ["This computer"]
fake({"/mnt": ["media"], "/media": []})
r = S.list_drives("linux", "/home/someone")
assert names(r) == ["This computer", "media"], names(r)

# Windows: C: is the internal drive and is listed first, even when D: is found first
fake({"C:/": ["Users"], "D:/": ["x"]})
r = S.list_drives("win", "C:/Users/someone")
assert names(r)[0] == "C: (this computer)" and "D:" in names(r), names(r)
assert r["drives"][0]["path"] == "C:/"

# Windows where only D: answers: still offers the home folder as the internal drive
fake({"D:/": ["x"]})
r = S.list_drives("win", "C:/Users/someone")
assert names(r)[0] == "This computer" and r["drives"][0]["path"] == "C:/Users/someone", names(r)

# small volumes (system partitions) are never offered as drives
S.inspect_path = lambda p, *a: {"ok": True, "freeBytes": GB, "totalBytes": GB}
S.helper = lambda path, script, **kw: subprocess.CompletedProcess([], 0, "tiny\n", "")
assert names(S.list_drives("linux", "")) == [], "no home and no drive: nothing to offer"
print("Drive list tests passed.")
