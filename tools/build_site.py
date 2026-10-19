"""Builds the website into the site folder. Run it from the top folder:
    python3 tools/build_site.py
The home page (landing) shows the install command. The folder demo holds the real setup page and guide with the server
replaced by canned answers, so anyone can click through every screen without installing anything.
Cloudflare runs this for you (build command: python3 tools/build_site.py, output folder: site)."""
import ast
import json
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site"
DEMO = OUT / "demo"
STATIC = ROOT / "wizard" / "app" / "static"
DOCS = ROOT / "docs"

if OUT.exists():
    shutil.rmtree(OUT)

# the home page
shutil.copytree(ROOT / "landing", OUT)
shutil.copytree(DOCS / "images" / "icons", OUT / "img" / "icons")

# the demo: the real page and guide, plus the pretend server
shutil.copytree(STATIC, DEMO)
shutil.copytree(DOCS, DEMO / "docs")
(DEMO / "demo-data").mkdir()
for f in (ROOT / "demo" / "fixtures").glob("*.json"):
    shutil.copy(f, DEMO / "demo-data" / f.name)
shutil.copy(ROOT / "demo" / "demo.js", DEMO / "demo.js")

# the guide's page list, in the same order the real setup shows it
src = (ROOT / "wizard" / "app" / "server.py").read_text(encoding="utf8")
order = ast.literal_eval(re.search(r"GUIDE_ORDER = (\[.*?\])", src, re.S).group(1))
names = sorted(p.stem for p in DOCS.glob("*.md"))
pages = [n for n in order if n in names] + [n for n in names if n not in order]
(DEMO / "demo-data" / "docs.json").write_text(json.dumps([{"name": n, "file": n + ".md"} for n in pages]), encoding="utf8")


def patch(path, old, new):
    text = path.read_text(encoding="utf8")
    assert old in text, f"{path.name}: {old!r} not found"
    path.write_text(text.replace(old, new), encoding="utf8")


# the demo lives in /demo/, so its links must be relative instead of starting at the top of the site
patch(DEMO / "app.js", 'href="/guide"', 'href="guide"')
patch(DEMO / "guide.js", '"/docs/"', '"docs/"')
patch(DEMO / "guide.js", '<a class="back" href="/">Back to the setup</a>', '<a class="back" href="./">Back to the demo</a>')

# load the demo layer before the page script
for page, script in (("index.html", "app.js"), ("guide.html", "guide.js")):
    patch(DEMO / page, f'<script src="{script}"></script>', f'<script src="demo.js"></script>\n<script src="{script}"></script>')

(OUT / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n/img/*\n  Cache-Control: public, max-age=86400\n/demo/demo-data/*\n  Cache-Control: public, max-age=300\n", encoding="utf8")
print(f"Site built in {OUT.relative_to(ROOT)}: {sum(1 for p in OUT.rglob('*') if p.is_file())} files, {len(pages)} guide pages.")
