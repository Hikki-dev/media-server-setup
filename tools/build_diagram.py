"""Draws docs/images/how-it-fits.svg from the app icons in docs/images/icons. Run it from the top folder:
    python3 tools/build_diagram.py
The icons are embedded in the picture, so it also shows correctly on GitHub. The logos belong to their projects."""
import base64
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICONS = ROOT / "docs" / "images" / "icons"

# name: (x, y, icon file or None, title, small text, icon size)
NODES = {
    "you": (95, 350, None, "You", "phone, TV, computer", 0),
    "jellyfin": (350, 130, "jellyfin", "Jellyfin", "watch your library", 104),
    "seerr": (350, 350, "seerr", "Seerr", "ask for a show or film", 104),
    "homepage": (350, 570, "homepage", "Homepage", "a link to every app", 104),
    "radarr": (500, 130, "radarr", "Radarr", "films", 104),
    "sonarr": (770, 340, "sonarr", "Sonarr", "shows and anime", 104),
    "qbit": (630, 570, "qbittorrent", "qBittorrent", "does the downloading", 104),
    "prowlarr": (890, 130, "prowlarr", "Prowlarr", "the search sites", 104),
    "flare": (1150, 130, "flaresolverr", "FlareSolverr", "gets past robot checks", 104),
    "bazarr": (1060, 360, "bazarr", "Bazarr", "finds subtitles", 104),
    "library": (950, 570, None, "Your library", "folders on your drives", 0),
}
SX, SY = 1.3, 1.2        # spread the apps out so every arrow has room for its port number
NODES = {k: (round(v[0] * SX), round(v[1] * SY) + 50) + v[2:] for k, v in NODES.items()}      # room for the title
NODES["you"] = (130, NODES["you"][1]) + NODES["you"][2:]
W = max(v[0] for v in NODES.values()) + 110
H = max(v[1] for v in NODES.values()) + 190
TX, TY = 130, NODES["homepage"][1]                                                           # Tailscale sits under "You"
# from, to, colour, port label
ARROWS = [
    ("you", "jellyfin", "#64748b", "8096"), ("you", "seerr", "#64748b", "5055", 0.5, -24), ("you", "homepage", "#64748b", "3000"),
    ("seerr", "radarr", "#7c5cc4", "7878"), ("seerr", "sonarr", "#7c5cc4", "8989", 0.3),
    ("radarr", "prowlarr", "#d99a1f", "9696"), ("sonarr", "prowlarr", "#2f86d6", "9696"),
    ("prowlarr", "flare", "#e4682a", "8191"),
    ("radarr", "qbit", "#d99a1f", "8080", 0.62), ("sonarr", "qbit", "#2f86d6", "8080"),
    ("qbit", "library", "#5a7fb0", "files"),
    ("bazarr", "sonarr", "#14a39a", "8989"), ("bazarr", "library", "#14a39a", "subtitles"),
]
COLOURS = sorted({a[2] for a in ARROWS} | {"#94a3b8"})


def data_uri(name):
    return "data:image/png;base64," + base64.b64encode((ICONS / f"{name}.png").read_bytes()).decode()


def png_size(name):
    b = (ICONS / f"{name}.png").read_bytes()
    return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")


def edge(p, q, r):
    """A point on the line from p towards q, r away from p."""
    dx, dy = q[0] - p[0], q[1] - p[1]
    d = math.hypot(dx, dy) or 1
    return p[0] + dx / d * r, p[1] + dy / d * r


def label(x, y, text):
    w = 10.8 * len(text) + 26
    return (f'<rect x="{x - w / 2:.0f}" y="{y - 15:.0f}" width="{w:.0f}" height="30" rx="15" fill="#f8fafc" stroke="#cbd5e1"/>'
            f'<text x="{x:.0f}" y="{y + 6:.0f}" class="l">{text}</text>')


def build():
    """Returns (the picture as text, the places of every port label). Labels are placed so none covers another label or an app."""
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, Helvetica, sans-serif" role="img" aria-labelledby="t d">',
           '<title id="t">How the apps work together</title>',
           '<desc id="d">You ask for something in Seerr. Radarr and Sonarr search through Prowlarr, qBittorrent downloads it into your library, Bazarr adds subtitles, and Jellyfin plays it. The numbers are the standard ports.</desc>',
           "<defs>"]
    for c in COLOURS:
        out.append(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="{c}"/></marker>')
    out.append("""<style>.t{font-size:23px;font-weight:700;fill:#0f172a;text-anchor:middle}.s{font-size:17px;fill:#475569;text-anchor:middle}
.l{font-size:17px;font-weight:700;fill:#334155;text-anchor:middle}.h{font-size:34px;font-weight:700;fill:#0f172a;text-anchor:middle}</style></defs>""")
    out.append(f'<rect width="{W}" height="{H}" fill="#f8fafc"/>')
    out.append(f'<text x="{W / 2:.0f}" y="40" class="h">How everything fits together</text>')

    pos = {k: (v[0], v[1]) for k, v in NODES.items()}
    tx, ty = TX, TY
    segs = []
    for a, b, colour, text, *_ in ARROWS:
        dx, dy = pos[b][0] - pos[a][0], pos[b][1] - pos[a][1]
        down, up = dy > 0.6 * abs(dx), -dy > 0.6 * abs(dx)           # leave under the text of a node, arrive under the text of the next one
        p, q = edge(pos[a], pos[b], 112 if down else 72), edge(pos[b], pos[a], 112 if up else 92)
        segs.append((p, q))
        out.append(f'<line x1="{p[0]:.0f}" y1="{p[1]:.0f}" x2="{q[0]:.0f}" y2="{q[1]:.0f}" stroke="{colour}" stroke-width="2.4" marker-end="url(#a{colour[1:]})"/>')
    # Jellyfin plays what is in the library: a long dashed line round the outside
    lx, ly = pos["library"]
    jx, jy = pos["jellyfin"]
    bottom = ly + 132
    out.append(f'<path d="M{lx} {ly + 92} L{lx} {bottom} L24 {bottom} L24 {jy + 50} L{jx - 102} {jy + 50}" fill="none" stroke="#94a3b8" stroke-width="2.2" stroke-dasharray="7 6" marker-end="url(#a94a3b8)"/>')
    # Tailscale: the private way in
    out.append(f'<line x1="{tx}" y1="{ty - 44}" x2="{tx}" y2="{pos["you"][1] + 76}" stroke="#6aa0e0" stroke-width="2" stroke-dasharray="5 5"/>')

    for name, (x, y, icon, title, small, size) in NODES.items():
        if icon:
            w, h = png_size(icon)
            sc = size / max(w, h)
            iw, ih = w * sc, h * sc
            out.append(f'<image href="{data_uri(icon)}" x="{x - iw / 2:.0f}" y="{y - 34 - ih / 2:.0f}" width="{iw:.0f}" height="{ih:.0f}"/>')
        elif name == "you":
            out.append(f'<circle cx="{x}" cy="{y - 48}" r="19" fill="#64748b"/><path d="M{x - 38} {y - 6} Q{x - 38} {y - 28} {x} {y - 28} Q{x + 38} {y - 28} {x + 38} {y - 6} Z" fill="#64748b"/>')
        elif name == "library":
            out.append(f'<path d="M{x - 40} {y - 64} h28 l10 12 h42 a6 6 0 0 1 6 6 v44 a6 6 0 0 1 -6 6 h-80 a6 6 0 0 1 -6 -6 v-56 a6 6 0 0 1 6 -6z" fill="#7cb7f2" stroke="#4a8fd8" stroke-width="2"/>')
        out.append(f'<text x="{x}" y="{y + 40}" class="t">{title}</text><text x="{x}" y="{y + 64}" class="s">{small}</text>')
    out.append(f'<image href="{data_uri("tailscale")}" x="{tx - 32}" y="{ty - 62}" width="64" height="64"/>')
    out.append(f'<text x="{tx}" y="{ty + 40}" class="t">Tailscale</text><text x="{tx}" y="{ty + 64}" class="s">private access</text>')

    # port labels: try places along each arrow and keep the one that covers nothing
    boxes = [(x - 96, y - 96, x + 96, y + 78) for (x, y, *_r) in NODES.values()] + [(tx - 96, ty - 70, tx + 96, ty + 78)]
    placed = []
    spots = [0.5, 0.42, 0.58, 0.34, 0.66, 0.27, 0.73, 0.2, 0.8, 0.46, 0.54, 0.38, 0.62, 0.3, 0.7, 0.24, 0.76]
    for i, (a, b, colour, text, *rest) in enumerate(ARROWS):
        (x1, y1), (x2, y2) = segs[i]
        want = rest[0] if rest else 0.5
        order = [want] + [t for t in spots if t != want]
        best = None
        for rank, t in enumerate(order):
            x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t + (rest[1] if len(rest) > 1 else 0)
            r = label_box(x, y, text)
            bad = sum(1000 for n in boxes if overlap(r, n, 0)) + sum(1000 for o in placed if overlap(r, o, 8))
            bad += sum(12 for j, (p, q) in enumerate(segs) if j != i and crosses(r, p, q))      # sitting on another arrow is a small fault
            tip = [(x2 + (x1 - x2) * k / (math.hypot(x2 - x1, y2 - y1) or 1), y2 + (y1 - y2) * k / (math.hypot(x2 - x1, y2 - y1) or 1)) for k in (0, 6, 12, 18, 24, 30)]
            bad += sum(1000 for (tx_, ty_) in tip if r[0] <= tx_ <= r[2] and r[1] <= ty_ <= r[3])      # never hide an arrowhead
            bad += rank * 0.5
            if best is None or bad < best[0]:
                best = (bad, x, y, r)
            if bad < 1:
                break
        placed.append(best[3])
        out.append(label(best[1], best[2], text))
    out.append(label(W / 2, bottom, "Jellyfin plays what is in your library"))
    out.append(f'<text x="{W / 2:.0f}" y="{H - 16}" class="s" style="font-size:16px">The numbers are the standard ports. If one is busy, the setup picks a free one. Logos belong to their projects.</text>')
    out.append("</svg>")
    return "\n".join(out), placed, boxes


def label_box(x, y, text):
    w = 10.8 * len(text) + 26
    return (x - w / 2, y - 15, x + w / 2, y + 15)


def overlap(a, b, margin):
    return not (a[2] + margin < b[0] or b[2] + margin < a[0] or a[3] + margin < b[1] or b[3] + margin < a[1])


def crosses(r, p, q):
    """True when the line from p to q passes through the box r."""
    for k in range(0, 41):
        x, y = p[0] + (q[0] - p[0]) * k / 40, p[1] + (q[1] - p[1]) * k / 40
        if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
            return True
    return False


if __name__ == "__main__":
    svg, placed, boxes = build()
    clash = [(i, j) for i in range(len(placed)) for j in range(i + 1, len(placed)) if overlap(placed[i], placed[j], 0)]
    if clash:
        raise SystemExit(f"Port labels cover each other: {clash}")
    (ROOT / "docs" / "images" / "how-it-fits.svg").write_text(svg)
    print(f"wrote docs/images/how-it-fits.svg ({len(svg) // 1024} KB), {len(placed)} labels, none covering another")
