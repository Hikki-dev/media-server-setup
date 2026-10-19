"""Tests for choosing the Kapowarr image. Needs no Docker. Run: python3 tools/test_kapowarr_image.py"""
import pathlib
import subprocess
import sys
import types

sys.modules.setdefault("yaml", types.ModuleType("yaml"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "wizard" / "app"))
import stack as S  # noqa: E402


def docker_can_reach(*reachable):
    S.sh = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0 if cmd[-1] in reachable else 1, "", "")


docker_can_reach(*S.KAPOWARR_IMAGES)
assert S.pick_kapowarr_image() == (S.KAPOWARR_IMAGES[0], False), "the copy is used when it can be downloaded"
docker_can_reach(S.KAPOWARR_IMAGES[1])
assert S.pick_kapowarr_image() == (S.KAPOWARR_IMAGES[1], True), "the original is used when the copy is private"
docker_can_reach()
assert S.pick_kapowarr_image() == (S.KAPOWARR_IMAGES[0], False), "offline: keep the first choice"
print("Kapowarr image tests passed.")
