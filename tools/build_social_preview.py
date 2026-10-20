"""Makes landing/img/social-preview.png (1280 x 640) from tools/social-preview.html with headless Chrome.
Upload it under the repository's Settings, Social preview. It is also the picture other sites show for the website link.
Run it from the top folder: python3 tools/build_social_preview.py   (needs Google Chrome)"""
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
chrome = next((c for c in ("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", shutil.which("google-chrome"), shutil.which("chromium")) if c and pathlib.Path(c).exists()), None)
if not chrome:
    sys.exit("Google Chrome was not found.")
out = ROOT / "landing" / "img" / "social-preview.png"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=6000", "--window-size=1280,640",
                f"--screenshot={out}", (ROOT / "tools" / "social-preview.html").as_uri()], check=True, capture_output=True)
print(f"Wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB)")
