"""Tests for the file sharing settings. Needs no Docker. Run: python3 tools/test_sharing.py"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "wizard" / "app"))
import sharing  # noqa: E402

CFG = {"hostOs": "linux", "uid": 1000, "gid": 1000, "tz": "UTC",
       "samba": {"user": "media", "password": "correct horse 42", "shares": [
           {"name": "Media", "path": "/mnt/Media", "readOnly": False},
           {"name": "Backup Drive", "path": "/mnt/Backup", "readOnly": True}]}}

# a good setup has no problems
assert sharing.check(CFG) == [], sharing.check(CFG)

# each mistake is reported in plain words
bad = lambda **kw: sharing.check({**CFG, "samba": {**CFG["samba"], **kw}})  # noqa: E731
assert bad(user="Media User"), "user name with a space and capitals must be refused"
assert bad(password="short"), "short password must be refused"
assert bad(password="has:colon-in-it"), "a colon would break the password file"
assert bad(shares=[]), "no shares must be refused"
assert bad(shares=[{"name": "A", "path": "/a"}, {"name": "a", "path": "/b"}]), "same name twice must be refused"
assert bad(shares=[{"name": "global", "path": "/a"}]), "reserved names must be refused"
assert bad(shares=[{"name": "A", "path": "relative"}]), "paths must be full paths"
assert sharing.check({**CFG, "hostOs": "win"}), "Windows hosts are not supported"

# the settings file
conf = sharing.smb_conf(CFG)
assert "[Media]" in conf and "[Backup Drive]" in conf
assert "path = /shares/Backup Drive" in conf
assert "guest ok = no" in conf and "map to guest = never" in conf
assert conf.count("read only = yes") == 1 and conf.count("read only = no") == 1
assert "fruit" not in conf and "streams_xattr" not in conf, "Apple extras must stay off"
assert "hosts deny = 0.0.0.0/0" in conf

# the password file: one line, ids match the other apps
assert sharing.users_conf(CFG) == "media:1000:smb:1000:correct horse 42\n"

# the compose service mounts every share
svc = sharing.service(CFG, 445, "/stack")
assert svc["ports"] == ["445:445"]
assert "/mnt/Media:/shares/Media" in svc["volumes"] and "/mnt/Backup:/shares/Backup Drive" in svc["volumes"]

# suggestions: media folders first, other drives next, nothing twice
got = sharing.suggest([{"host": "/mnt/Media"}], [{"name": "Media", "path": "/mnt/Media"}, {"name": "Photos", "path": "/mnt/Photos"},
                                                {"name": "Inside", "path": "/mnt/Media/Inside"}])
assert [g["path"] for g in got] == ["/mnt/Media", "/mnt/Photos"], got
two = sharing.suggest([{"host": "/a/Data"}, {"host": "/b/Data"}], [])
assert [g["name"] for g in two] == ["Data", "Data 2"], two
assert sharing.clean_name("Movies: 4K / Best?") == "Movies 4K Best"

# only real drives are offered, and a share that is switched off is left out
table = sharing.parse_mounts("/dev/sda1 /mnt/Media ext4 rw 0 0\n/dev/sdb1 /mnt/Photos exfat rw 0 0\ntmpfs /run tmpfs rw 0 0\n")
assert [m["mp"] for m in table] == ["/mnt/Media", "/mnt/Photos"], table
real = sharing.suggest([{"host": "/mnt/Media/data"}], [{"name": "Photos", "path": "/mnt/Photos"}, {"name": "docker", "path": "/srv/docker"},
                                                      {"name": "Link", "path": "/mnt/Link"}], table)
assert [r["path"] for r in real] == ["/mnt/Media/data", "/mnt/Photos"], real
assert real[0]["fs"] == "ext4" and real[1]["fs"] == "exFAT", real
off = {**CFG, "samba": {**CFG["samba"], "shares": [{**CFG["samba"]["shares"][0], "on": False}, CFG["samba"]["shares"][1]]}}
assert [s["name"] for s in sharing.shares_of(off)] == ["Backup Drive"]

# how to open each share
a = sharing.addresses("server", [{"name": "Backup Drive", "path": "/x"}])[0]
assert a["windows"] == "\\\\server\\Backup Drive" and a["mac"] == "smb://server/Backup%20Drive"
print("File sharing tests passed.")
