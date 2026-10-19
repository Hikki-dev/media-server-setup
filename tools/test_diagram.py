"""Checks the diagram of how the apps fit together. Needs nothing installed. Run: python3 tools/test_diagram.py"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_diagram", ROOT / "tools" / "build_diagram.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

svg, labels, boxes = mod.build()
assert len(labels) == len(mod.ARROWS), "every arrow needs a port label"
for i, a in enumerate(labels):
    assert 0 <= a[0] and a[2] <= mod.W and 0 <= a[1] and a[3] <= mod.H, f"label {i} is outside the picture"
    for j in range(i + 1, len(labels)):
        assert not mod.overlap(a, labels[j], 6), f"port labels {i} and {j} cover each other"
    for n in boxes:
        assert not mod.overlap(a, n, 0), f"label {i} covers an app"
saved = (ROOT / "docs" / "images" / "how-it-fits.svg").read_text()
assert saved == svg, "docs/images/how-it-fits.svg is out of date: run python3 tools/build_diagram.py"
print("Diagram tests passed.")
