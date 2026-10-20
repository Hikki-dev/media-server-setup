"""Step 2 of the tour video: turns the pictures from capture.mjs into a 1080p video.

It adds a pointer that moves the way a hand does (a curve, a slight overshoot, a pause before the click),
a camera that zooms in only where there is something to look at, and short captions.

    python3 tools/tour/compose.py <folder from capture.mjs> <output.mp4>

Needs: Pillow and ffmpeg. The end card is made by endcard.html with Google Chrome.
"""
import json
import math
import random
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WORK = Path(sys.argv[1])
OUT = Path(sys.argv[2])
FPS, OW, OH = 30, 1920, 1080
M = json.loads((WORK / "manifest.json").read_text())
CW, CH, DPR = M["W"], M["H"], M["DPR"]            # the page was captured at 1280 x 720 css pixels, twice as sharp
STATES = {s["id"].split("-", 1)[1]: s for s in M["states"]}
rnd = random.Random(7)


def S(name):
    return STATES[name]


def rect(name, key="target"):
    r = STATES[name]["targets"].get(key)
    if r is None:
        raise KeyError(f"{name}.{key}")
    return r


def center(name, key="target"):
    r = rect(name, key)
    return (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2)


# ----------------------------------------------------------------------------- pictures
_cache = OrderedDict()


def image(name):
    if name in _cache:
        _cache.move_to_end(name)
        return _cache[name]
    im = Image.open(WORK / STATES[name]["file"]).convert("RGB")
    _cache[name] = im
    if len(_cache) > 8:
        _cache.popitem(last=False)
    return im


# ----------------------------------------------------------------------------- motion helpers
W_C = (CW / 2, CH / 2)


def smoother(u):
    u = min(1.0, max(0.0, u))
    return u * u * u * (u * (u * 6 - 15) + 10)


def bezier(p0, p1, p2, p3, s):
    a, b, c, d = (1 - s) ** 3, 3 * (1 - s) ** 2 * s, 3 * (1 - s) * s * s, s ** 3
    return (a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1])


class Cam:
    """The camera: a centre and a zoom. A new move starts from wherever the camera is at that moment, so moves never fight."""

    def __init__(self, c, z):
        self.start = (c[0], c[1], z)
        self.events = []           # (t0, duration, from, to)

    def go(self, t, dur, c, z):
        self.events.append((t, dur, self.at(t), (c[0], c[1], z)))

    def at(self, t):
        cur = self.start
        for (t0, d, frm, to) in self.events:
            if t < t0:
                break
            u = smoother((t - t0) / d)
            cur = tuple(frm[i] + (to[i] - frm[i]) * u for i in range(3))
        return cur

    def target(self):
        return self.events[-1][3] if self.events else self.start

    def end_time(self):
        return max((t0 + d for (t0, d, _f, _t) in self.events), default=0.0)


def fit(r, pad=0.22, zmax=1.7, zmin=1.0):
    """The zoom that frames a rectangle with some air around it."""
    z = min(CW / (r["w"] * (1 + pad)), CH / (r["h"] * (1 + pad)))
    return (r["x"] + r["w"] / 2, r["y"] + r["h"] / 2), max(zmin, min(zmax, z))


# ----------------------------------------------------------------------------- the timeline
frames = []        # one dict per output frame: state, cursor position, press, caption, camera
cap_events = []    # (start, end, text)
cam = Cam((CW / 2, CH / 2), 1.0)
cursor = {"p": (1160.0, 640.0)}
clicks = []        # (time, point) for the ripples
now = 0.0


def emit(dur, state, pos_fn, press=0.0):
    """Adds frames for dur seconds. pos_fn(u) gives the pointer for u in 0..1."""
    global now
    n = max(1, round(dur * FPS))
    for i in range(n):
        u = (i + 0.5) / n
        t = now + i / FPS
        frames.append({"t": t, "state": state, "pos": pos_fn(u), "press": press})
    now += n / FPS
    cursor["p"] = pos_fn(1.0)


def tremor(t, amp=0.55):
    return (amp * (math.sin(6.4 * t + 0.7) * 0.6 + math.sin(11.9 * t + 2.1) * 0.4),
            amp * (math.sin(5.3 * t + 1.9) * 0.6 + math.sin(13.1 * t + 0.4) * 0.4))


def ensure_visible(pt, dur=0.95):
    """If the target is out of the camera's view, scroll to it, the way a person would."""
    cx, cy, z = cam.target()
    hh, hw = CH / 2 / z, CW / 2 / z
    if abs(pt[1] - cy) > hh * 0.78 or abs(pt[0] - cx) > hw * 0.85:
        cam.go(now, dur, (min(max(cx, hw), CW - hw), max(hh, pt[1] - hh * 0.3)), z)


def move(to, state, dur=None, arc=None):
    """A hand-like move: a gentle curve, quick in the middle, a small overshoot that settles back."""
    ensure_visible(to)
    p0, p3 = cursor["p"], to
    dx, dy = p3[0] - p0[0], p3[1] - p0[1]
    dist = math.hypot(dx, dy)
    if dist < 2:
        return
    dur = dur or max(0.45, min(1.35, 0.32 + dist / 900)) * rnd.uniform(0.94, 1.08)
    nx, ny = -dy / dist, dx / dist
    side = arc if arc is not None else rnd.choice([-1, 1]) * rnd.uniform(0.04, 0.09)
    p1 = (p0[0] + dx * 0.28 + nx * dist * side, p0[1] + dy * 0.28 + ny * dist * side)
    p2 = (p0[0] + dx * 0.78 + nx * dist * side * 0.55, p0[1] + dy * 0.78 + ny * dist * side * 0.55)
    over = min(7.0, dist * 0.012)
    end = (p3[0] + dx / dist * over, p3[1] + dy / dist * over)
    t0 = now

    def f(u):
        s = smoother(u)
        x, y = bezier(p0, p1, p2, end, s)
        tx, ty = tremor(t0 + u * dur, 0.25 * (1 - s) + 0.15)
        return (x + tx, y + ty)
    emit(dur, state, f)
    if over > 1.5:               # the hand settles back onto the target
        q0, q1, d2 = end, p3, 0.14
        emit(d2, state, lambda u: (q0[0] + (q1[0] - q0[0]) * smoother(u), q0[1] + (q1[1] - q0[1]) * smoother(u)))


def rest(dur, state, amp=0.5):
    cx, cy, z = cam.target()
    hw, hh = CW / 2 / z, CH / 2 / z
    px, py = cursor["p"]
    if not (cx - hw * 0.92 < px < cx + hw * 0.92 and cy - hh * 0.92 < py < cy + hh * 0.92):
        move((cx + hw * 0.4, cy + hh * 0.35), state, 0.9)       # the hand follows the camera instead of staying behind
    p = cursor["p"]
    t0 = now

    def f(u):
        tx, ty = tremor(t0 + u * dur, amp)
        return (p[0] + tx, p[1] + ty)
    emit(dur, state, f)


def click(state_before, state_after, hold=1.0):
    """Press and release. The page changes a moment after the press, the way it does when you click."""
    global now
    p = cursor["p"]
    emit(0.10, state_before, lambda u: p, press=1.0)
    clicks.append((now, p))
    emit(0.07, state_after, lambda u: p, press=0.0)
    emit(hold, state_after, lambda u: (p[0] + tremor(now + u * hold, 0.4)[0], p[1] + tremor(now + u * hold, 0.4)[1]))


def caption(text, dur=2.6, delay=0.2):
    cap_events.append((now + delay, now + delay + dur, text))


def camera(c, z, dur=1.1, lead=0.0):
    cam.go(max(0.0, now - lead), dur, c, z)


def target_center(name, key="target"):
    return center(name, key)


def press_target(base, hover, after, *, key="target", pre=0.26, hold=1.0, travel=None, cut=False):
    """Move to a button, hold the pointer over it, click, and land on the next page.
    With cut=True the click opens a new page: the camera goes back to the top and the pointer stays where it is on the screen."""
    to = center(hover, key) if STATES[hover]["targets"].get(key) else center(base, key)
    move(to, base, travel)
    emit(pre * rnd.uniform(0.85, 1.25), hover, lambda u: (to[0] + tremor(now + u, 0.35)[0], to[1] + tremor(now + u, 0.35)[1]))
    cursor["p"] = to
    settle = cam.end_time() - now
    if settle > 0:                                  # let the camera finish before the click, so it never moves under the pointer
        rest(settle + 0.04, hover, 0.3)
    if cut:
        cx, cy, z = cam.at(now)
        sx, sy = (to[0] - (cx - CW / 2 / z)) * z, (to[1] - (cy - CH / 2 / z)) * z      # where the pointer is on the screen
        global_click_then_cut(hover, after, hold, (sx, sy))
    else:
        click(hover, after, hold)


def global_click_then_cut(state_before, state_after, hold, screen_pt):
    p = cursor["p"]
    emit(0.10, state_before, lambda u: p, press=1.0)
    clicks.append((now, p))
    cam.go(now - 0.03, 0.01, W_C, 1.0)             # a new page opens at the top
    cursor["p"] = screen_pt
    clicks[-1] = (clicks[-1][0], p)
    q = screen_pt
    emit(0.07, state_after, lambda u: q, press=0.0)
    emit(hold, state_after, lambda u: (q[0] + tremor(now + u * hold, 0.4)[0], q[1] + tremor(now + u * hold, 0.4)[1]))


# ----------------------------------------------------------------------------- the story

# 1. Welcome: orientation, the whole screen
camera(W_C, 1.0, 0.01)
caption("Start with one page in your browser", 3.2, 0.4)
rest(1.5, "welcome")
press_target("welcome", "welcome-hover", "check", hold=0.9, cut=True)

# 2. The check: zoom in on the list, because the result is what matters here
c, z = fit({"x": 324, "y": 150, "w": 904, "h": 330}, 0.12, 1.45)
camera(c, z, 1.2)
caption("It checks your computer first", 2.8, 0.3)
rest(2.4, "check", 0.3)
camera(W_C, 1.0, 1.0)
rest(0.5, "check")
press_target("check", "check-hover", "storage", hold=0.8, cut=True)

# 3. Storage and the folder picker
camera((640, 470), 1.0, 0.8)
move(center("storage", "browse"), "storage", 1.1)
camera(*fit(rect("storage", "browse"), 3.2, 1.4), dur=1.0)
caption("Choose where everything is kept", 2.6, 0.1)
emit(0.3, "storage-hover-browse", lambda u: cursor["p"])
click("storage-hover-browse", "picker", hold=0.5)
# the picker: the drive list is the reason for the zoom, it is new
c, z = fit({"x": 290, "y": 96, "w": 700, "h": 528}, 0.08, 1.35)
camera(c, z, 1.0)
caption("Your own drive is always on the list", 3.0, 0.5)
rest(1.0, "picker")
move(center("picker", "internal"), "picker", 0.9)
emit(0.9, "picker-hover-internal", lambda u: cursor["p"])
move(center("picker", "media"), "picker-hover-internal", 0.55)
emit(0.45, "picker-hover-media", lambda u: cursor["p"])
click("picker-hover-media", "picker-media", hold=1.1)
move(center("picker-media", "use"), "picker-media", 0.9)
emit(0.4, "picker-hover-use", lambda u: cursor["p"])
click("picker-hover-use", "storage-chosen", hold=0.6)
# the space that is left, because people ask about it
c, z = fit({"x": 520, "y": 505, "w": 420, "h": 80}, 1.4, 1.5)
camera(c, z, 1.1)
caption("Any drive works, internal or external", 2.6, 0.3)
rest(1.9, "storage-chosen", 0.35)
camera(W_C, 1.0, 0.9)
press_target("storage-chosen", "storage-chosen-hover", "watch", hold=0.7, cut=True)

# 4. What you watch: one click picks a whole set of rules
c, z = fit({"x": 324, "y": 120, "w": 520, "h": 330}, 0.12, 1.3)
camera(c, z, 1.0)
caption("Pick what you watch in one click", 2.8, 0.2)
press_target("watch", "watch-hover-quick", "watch-chosen", key="quick", hold=1.5, travel=1.2)
camera(W_C, 1.0, 0.9)
press_target("watch-chosen", "watch-chosen-hover", "livetv", hold=0.35, cut=True)

# 5. Live TV and profiles are skipped fast: optional
press_target("livetv", "livetv-hover", "profiles", hold=0.3, pre=0.12, cut=True)
press_target("profiles", "profiles-hover", "downloads", hold=0.3, pre=0.12, cut=True)

# 6. The downloader login: typed by hand, one letter at a time
ur, pr = rect("downloads", "user"), rect("downloads", "pass")
c, z = fit({"x": ur["x"] - 60, "y": ur["y"] - 70, "w": pr["x"] + pr["w"] - ur["x"] + 120, "h": ur["h"] + 150}, 0.1, 1.5)
camera(c, z, 1.2)
caption("Give the downloader its own login", 2.6, 0.2)
rest(0.5, "downloads")
fld = center("downloads", "user")
move(fld, "downloads", 1.1)
emit(0.28, "downloads-hover-user", lambda u: cursor["p"])
click("downloads-hover-user", "downloads-hover-user", hold=0.35)


def type_run(prefix, letters, first_state):
    for i in range(1, letters + 1):
        gap = rnd.uniform(0.11, 0.2) + (0.12 if rnd.random() < 0.12 else 0)
        emit(gap, f"{prefix}-{i}" if i > 0 else first_state, lambda u: cursor["p"])


type_run("downloads-user", 4, "downloads-hover-user")
emit(0.5, "downloads-user-4", lambda u: cursor["p"])
move(center("downloads-hover-pass", "pass"), "downloads-user-4", 0.7)
emit(0.25, "downloads-hover-pass", lambda u: cursor["p"])
click("downloads-hover-pass", "downloads-hover-pass", hold=0.3)
type_run("downloads-pass", 9, "downloads-hover-pass")
emit(0.7, "downloads-pass-9", lambda u: cursor["p"])
camera(W_C, 1.0, 0.9)
press_target("downloads-continue", "downloads-continue-hover", "apps", hold=0.9, cut=True)

# 7. Apps: the grid, then the three that are new
camera((640, 440), 1.0, 0.7)
caption("Choose your apps", 2.0, 0.1)
rest(1.0, "apps")
c, z = fit(rect("apps", "grid"), 0.05, 1.3)
camera(c, z, 1.1)
caption("Comics and manga now have their own apps", 3.4, 0.6)
press_target("apps", "apps-hover-komga", "apps-komga-on", key="tile", hold=0.5, travel=0.9)
press_target("apps-komga-on", "apps-hover-kapowarr", "apps-kapowarr-on", key="tile", hold=0.6, travel=0.9)
press_target("apps-kapowarr-on", "apps-hover-kaizoku", "apps-kaizoku-on", key="tile", hold=0.9, travel=0.7)
# a card appeared below: pan down to it, because comics need a free key
c, z = fit(rect("apps-kaizoku-on", "card"), 0.18, 1.5)
camera(c, z, 1.3)
caption("Comics need a free ComicVine key. Paste it once", 3.2, 0.5)
rest(0.9, "apps-kaizoku-on")
fld = center("apps-hover-key", "field")
move(fld, "apps-kaizoku-on", 1.0)
emit(0.3, "apps-hover-key", lambda u: cursor["p"])
click("apps-hover-key", "apps-hover-key", hold=0.25)
emit(0.28, "apps-key-pasted", lambda u: cursor["p"])      # a paste arrives all at once
rest(1.3, "apps-key-pasted")
# the main login
c, z = fit({"x": 324, "y": 1569, "w": 904, "h": 155}, 0.3, 1.45)
camera(c, z, 1.3)
caption("One login for the apps. Generate a strong one", 2.9, 0.4)
rest(0.7, "apps-key-pasted")
gen = center("apps-hover-generate", "gen")
move(gen, "apps-key-pasted", 1.15)
emit(0.3, "apps-hover-generate", lambda u: cursor["p"])
click("apps-hover-generate", "apps-generated", hold=1.4)
camera(W_C, 1.0, 1.0)
# on to the review
camera(W_C, 1.0, 0.01) if False else None
press_target("apps-generated", "apps-continue-hover", "review", hold=0.5, cut=True)

# 8. Review
c, z = fit({"x": 324, "y": 20, "w": 904, "h": 760}, 0.05, 1.18)
camera(c, z, 1.1)
caption("One last look before anything is installed", 3.0, 0.3)
rest(2.3, "review", 0.3)
press_target("review", "review-hover-install", "install-00", key="install", hold=0.2, cut=True)

# 9. Install: sped up, the camera stays on the list of tasks
c, z = fit({"x": 324, "y": 150, "w": 604, "h": 700}, 0.06, 1.25)
camera(c, z, 1.2)
caption("It installs, links and tests every app", 3.4, 0.4)
inst_names = sorted(k for k in STATES if k.startswith("install-"))
park = cursor["p"]          # the pointer stays where the click left it while the install runs
for k in inst_names:
    emit(0.31, k, lambda u: (park[0] + tremor(now + u, 0.5)[0], park[1] + tremor(now + u, 0.5)[1]))
rest(0.6, inst_names[-1])

# 10. Done: a new page opens at the top; the pointer stays where it is on the screen
cx, cy, z = cam.at(now)
px, py = cursor["p"]
cursor["p"] = ((px - (cx - CW / 2 / z)) * z, (py - (cy - CH / 2 / z)) * z)
cam.go(now - 0.03, 0.01, W_C, 1.0)
rest(0.5, "done")
c, z = fit(rect("done", "links"), 0.18, 1.3)
camera(c, z, 1.2)
caption("Every app is linked. Open any of them from here", 3.0, 0.3)
rest(2.6, "done", 0.4)
c, z = fit({"x": 324, "y": 1186, "w": 904, "h": 520}, 0.1, 1.2)
camera(c, z, 1.5)
caption("Every login is listed, and checked", 2.8, 0.7)
rest(2.4, "done")
show = center("done-hover-show", "show")
move(show, "done", 1.2)
emit(0.3, "done-hover-show", lambda u: cursor["p"])
click("done-hover-show", "done-revealed", hold=1.8)
camera((640, show[1] + 60), 1.0, 1.3)
rest(1.2, "done-revealed")
jumps = sorted(((math.hypot(b["pos"][0] - a["pos"][0], b["pos"][1] - a["pos"][1]), a["t"]) for a, b in zip(frames, frames[1:])), reverse=True)[:4]
print("biggest pointer steps (page px per frame, time):", [(round(d, 1), round(t, 1)) for d, t in jumps])
TOTAL = now
print(f"timeline: {TOTAL:.1f} s, {len(frames)} frames")


# ----------------------------------------------------------------------------- drawing
def font(size, bold=True):
    for path, idx in (("/System/Library/Fonts/Avenir Next.ttc", 2 if bold else 7), ("/System/Library/Fonts/Helvetica.ttc", 1 if bold else 0)):
        try:
            return ImageFont.truetype(path, size, index=idx)
        except Exception:        # noqa: BLE001 - try the next font
            continue
    return ImageFont.load_default()


def make_cursor(scale=4):
    """A pointer drawn big and shrunk, so its edges are smooth."""
    s = 64 * scale
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    pts = [(6, 3), (6, 44), (16, 35), (23, 50), (31, 46.5), (24, 32), (38, 32)]
    pts = [(x * scale, y * scale) for x, y in pts]
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + 2.5 * scale, y + 3.5 * scale) for x, y in pts], fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(2.2 * scale))
    im.alpha_composite(shadow)
    d = ImageDraw.Draw(im)
    d.polygon(pts, fill=(255, 255, 255, 255), outline=(20, 23, 28, 255), width=int(2.4 * scale))
    return im


CURSOR = make_cursor()
CAP_FONT = font(29)
ring_cache = {}


def ripple(frame_img, p_screen, age):
    """A soft ring where the click landed."""
    if age < 0 or age > 0.45:
        return
    u = age / 0.45
    r = 12 + 44 * (1 - (1 - u) ** 3)
    a = int(190 * (1 - u) ** 1.4)
    size = int(r * 2 + 12)
    sc = 3
    patch = Image.new("RGBA", (size * sc, size * sc), (0, 0, 0, 0))
    d = ImageDraw.Draw(patch)
    c = size * sc / 2
    d.ellipse([c - r * sc, c - r * sc, c + r * sc, c + r * sc], outline=(242, 169, 59, a), width=int(3.2 * sc))
    patch = patch.resize((size, size), Image.LANCZOS)
    frame_img.alpha_composite(patch, (int(p_screen[0] - size / 2), int(p_screen[1] - size / 2)))


def caption_alpha(t):
    for (a, b, text) in cap_events:
        if a <= t <= b:
            fade = min(1.0, (t - a) / 0.3, (b - t) / 0.3)
            return text, max(0.0, fade)
    return None, 0.0


def draw_caption(img, text, alpha):
    d = ImageDraw.Draw(img)
    w = d.textlength(text, font=CAP_FONT)
    pad_x, pad_y, h = 26, 14, 29
    x0, y1 = 56, OH - 40
    box = (x0, y1 - h - pad_y * 2, x0 + w + pad_x * 2 + 18, y1)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rounded_rectangle(box, radius=20, fill=(13, 27, 42, int(214 * alpha)))
    ld.ellipse([box[0] + 18, (box[1] + box[3]) / 2 - 5, box[0] + 28, (box[1] + box[3]) / 2 + 5], fill=(242, 169, 59, int(255 * alpha)))
    ld.text((box[0] + 38, box[1] + pad_y - 3), text, font=CAP_FONT, fill=(255, 255, 255, int(255 * alpha)))
    img.alpha_composite(layer)


def render(i, f):
    t = f["t"]
    cx, cy, z = cam.at(t)
    z = max(1.0, z)
    st = STATES[f["state"]]
    src = image(f["state"])
    sw, sh = CW * DPR / z, CH * DPR / z                       # the part of the picture the camera sees, in picture pixels
    x0 = max(0.0, min(cx * DPR - sw / 2, src.width - sw))
    y0 = max(0.0, min(cy * DPR - sh / 2, src.height - sh))
    frame = src.resize((OW, OH), Image.LANCZOS, box=(x0, y0, x0 + sw, y0 + sh)).convert("RGBA")
    sx = lambda px: (px * DPR - x0) / sw * OW
    sy = lambda py: (py * DPR - y0) / sh * OH
    p = (sx(f["pos"][0]), sy(f["pos"][1]))
    for (ct, cp) in clicks:
        ripple(frame, (sx(cp[0]), sy(cp[1])), t - ct)
    k = (1 + 0.32 * (z - 1)) * (0.9 if f["press"] else 1.0)
    cur = CURSOR.resize((int(64 * 0.74 * k), int(64 * 0.74 * k)), Image.LANCZOS)
    frame.alpha_composite(cur, (int(p[0] - 6 * 0.74 * k), int(p[1] - 3 * 0.74 * k)))
    text, a = caption_alpha(t)
    if text:
        draw_caption(frame, text, a)
    return frame.convert("RGB")


# ----------------------------------------------------------------------------- encode
end_png = WORK / "endcard.png"
if not end_png.exists():
    sys.exit("endcard.png is missing: render tools/tour/endcard.html first (see tools/tour/README)")
END = Image.open(end_png).convert("RGB").resize((OW, OH), Image.LANCZOS)
END_SECONDS, FADE = 4.2, 0.9

ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OW}x{OH}", "-r", str(FPS), "-i", "-",
                       "-c:v", "libx264", "-preset", "slow", "-crf", "21", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", str(FPS), str(OUT)],
                      stdin=subprocess.PIPE)
last = None
for i, f in enumerate(frames):
    last = render(i, f)
    ff.stdin.write(last.tobytes())
    if i % 200 == 0:
        print(f"  frame {i}/{len(frames)}", flush=True)
for j in range(int(END_SECONDS * FPS)):             # the end card fades in over the last picture
    u = min(1.0, j / (FADE * FPS))
    ff.stdin.write(Image.blend(last, END, smoother(u)).tobytes())
ff.stdin.close()
ff.wait()
print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.1f} MB")
