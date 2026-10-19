"""Builds the demo website into the site folder: the real setup page and guide, with the server replaced by canned answers.
Anyone can open it and click through every screen without installing anything. Run it from the top folder:
    python3 tools/build_demo.py
Cloudflare Pages runs this command for you (build command: python3 tools/build_demo.py, output folder: site)."""
import ast
import json
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "site"
STATIC = ROOT / "wizard" / "app" / "static"
DOCS = ROOT / "docs"

if OUT.exists():
    shutil.rmtree(OUT)
shutil.copytree(STATIC, OUT)
shutil.copytree(DOCS, OUT / "docs")
(OUT / "demo-data").mkdir()
for f in (ROOT / "demo" / "fixtures").glob("*.json"):
    shutil.copy(f, OUT / "demo-data" / f.name)
shutil.copy(ROOT / "demo" / "demo.js", OUT / "demo.js")

# the guide's page list, in the same order the real setup shows it
src = (ROOT / "wizard" / "app" / "server.py").read_text(encoding="utf8")
order = ast.literal_eval(re.search(r"GUIDE_ORDER = (\[.*?\])", src, re.S).group(1))
names = sorted(p.stem for p in DOCS.glob("*.md"))
pages = [n for n in order if n in names] + [n for n in names if n not in order]
(OUT / "demo-data" / "docs.json").write_text(json.dumps([{"name": n, "file": n + ".md"} for n in pages]), encoding="utf8")

# load the demo layer before the page script
for page, script in (("index.html", "app.js"), ("guide.html", "guide.js")):
    f = OUT / page
    html = f.read_text(encoding="utf8")
    tag = f'<script src="{script}"></script>'
    assert tag in html, f"{page} has no {script}"
    f.write_text(html.replace(tag, f'<script src="demo.js"></script>\n{tag}', 1), encoding="utf8")

(OUT / "_headers").write_text("/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: no-referrer\n/demo-data/*\n  Cache-Control: public, max-age=300\n", encoding="utf8")
print(f"Demo site built in {OUT.relative_to(ROOT)}: {sum(1 for _ in OUT.rglob('*') if _.is_file())} files, {len(pages)} guide pages.")
