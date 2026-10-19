"""Checks every change before it is accepted. Run it from the top folder: python3 tools/check.py"""
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKIP = {".git", "__pycache__", "node_modules"}
problems = []


def files(*suffixes):
    for p in ROOT.rglob("*"):
        if p.is_file() and not (set(p.parts) & SKIP) and p.suffix in suffixes:
            yield p


# 1. Python files must be valid
for p in files(".py"):
    try:
        compile(p.read_text(encoding="utf8"), str(p), "exec")
    except SyntaxError as e:
        problems.append(f"Python error in {p.relative_to(ROOT)} line {e.lineno}: {e.msg}")

# 2. The page script must be valid
node = shutil.which("node")
for p in files(".js"):
    if node:
        r = subprocess.run([node, "--check", str(p)], capture_output=True, text=True)
        if r.returncode:
            problems.append(f"Script error in {p.relative_to(ROOT)}: {r.stderr.strip()[:200]}")

# 3. Shell scripts must be valid
bash = shutil.which("bash")
for p in list(files(".sh")) + list(files(".command")):
    if bash:
        r = subprocess.run([bash, "-n", str(p)], capture_output=True, text=True)
        if r.returncode:
            problems.append(f"Shell error in {p.relative_to(ROOT)}: {r.stderr.strip()[:200]}")

# 4. Nothing private may be committed
PATTERNS = [
    (r"\b(?:192\.168|10\.\d{1,3})\.\d{1,3}\.(?!0/)\d{1,3}\b(?!/)", "a private network address"),
    (r"\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b(?!/)", "a Tailscale address"),
    (r"/Users/[A-Za-z0-9_.]+/", "a personal folder path"),
    (r"[A-Za-z0-9._%+]+@(?:gmail|yahoo|outlook|hotmail|icloud)\.com", "an email address"),
    (r"\bghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}", "an access token"),
    (r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----", "a private key"),
    (r"hooks\.slack\.com/services/\w+|discord(?:app)?\.com/api/webhooks/\d{10,}", "a webhook link"),
    (r"\b[0-9a-f]{32}\b", "a long key"),
]
SKIP_FILES = {"trash.json", "check.py"}
for p in ROOT.rglob("*"):
    if not p.is_file() or (set(p.parts) & SKIP) or p.name in SKIP_FILES or p.suffix in {".ts", ".png", ".jpg", ".ico", ".zip"}:
        continue
    try:
        text = p.read_text(encoding="utf8")
    except (UnicodeDecodeError, OSError):
        continue
    for rx, what in PATTERNS:
        m = re.search(rx, text)
        if m:
            problems.append(f"{p.relative_to(ROOT)} contains {what}: {m.group(0)[:40]}")

# 5. The demo website must build
r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_demo.py")], capture_output=True, text=True)
if r.returncode:
    problems.append("build_demo.py failed: " + (r.stderr.strip().splitlines() or ["see the file"])[-1][:200])

# 6. The tests must pass
for test in ("test_sharing.py", "test_tailscale_https.py", "test_drives.py"):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / test)], capture_output=True, text=True)
    if r.returncode:
        problems.append(f"{test} failed: " + (r.stderr.strip().splitlines() or ["see the file"])[-1][:200])

if problems:
    print("Problems found:\n")
    print("\n".join(problems))
    sys.exit(1)
print("All checks passed.")
