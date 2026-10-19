"""Draws docs/images/how-it-fits.svg from the app icons in docs/images/icons. Run it from the top folder:
    python3 tools/build_diagram.py
The icons are embedded in the picture, so it also shows correctly on GitHub. The logos belong to their projects."""
import base64
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICONS = ROOT / "docs" / "images" / "icons"
W, H = 1240, 810

# name: (x, y, icon file or None, title, small text, icon size)
NODES = {
    "you": (95, 350, None, "You", "phone, TV, computer", 0),
    "jellyfin": (350, 130, "jellyfin", "Jellyfin", "watch your library", 96),
    "seerr": (350, 350, "seerr", "Seerr", "ask for a show or film", 96),
    "homepage": (350, 570, "homepage", "Homepage", "a link to every app", 96),
    "radarr": (500, 130, "radarr", "Radarr", "films", 96),
    "sonarr": (770, 340, "sonarr", "Sonarr", "shows and anime", 96),
    "qbit": (630, 570, "qbittorrent", "qBittorrent", "does the downloading", 96),
    "prowlarr": (950, 130, "prowlarr", "Prowlarr", "the search sites", 96),
    "flare": (1120, 130, "flaresolverr", "FlareSolverr", "gets past robot checks", 96),
    "bazarr": (1060, 360, "bazarr", "Bazarr", "finds subtitles", 96),
    "library": (950, 570, None, "Your library", "folders on your drives", 0),
}
NODES = {k: (v[0], v[1] + 50) + v[2:] for k, v in NODES.items()}      # room for the title
NODES["you"] = (130, NODES["you"][1]) + NODES["you"][2:]
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
    w = 9.4 * len(text) + 20
    return (f'<rect x="{x - w / 2:.0f}" y="{y - 13:.0f}" width="{w:.0f}" height="26" rx="13" fill="#f8fafc" stroke="#cbd5e1"/>'
            f'<text x="{x:.0f}" y="{y + 5:.0f}" class="l">{text}</text>')


out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Arial, Helvetica, sans-serif" role="img" aria-labelledby="t d">',
       '<title id="t">How the apps work together</title>',
       '<desc id="d">You ask for something in Seerr. Radarr and Sonarr search through Prowlarr, qBittorrent downloads it into your library, Bazarr adds subtitles, and Jellyfin plays it. The numbers are the standard ports.</desc>',
       "<defs>"]
for c in COLOURS:
    out.append(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="{c}"/></marker>')
out.append("""<style>.t{font-size:19px;font-weight:700;fill:#0f172a;text-anchor:middle}.s{font-size:14.5px;fill:#475569;text-anchor:middle}
.l{font-size:14px;font-weight:700;fill:#334155;text-anchor:middle}.h{font-size:28px;font-weight:700;fill:#0f172a;text-anchor:middle}</style></defs>""")
out.append(f'<rect width="{W}" height="{H}" fill="#f8fafc"/>')
out.append(f'<text x="{W / 2:.0f}" y="40" class="h">How everything fits together</text>')

pos = {k: (v[0], v[1]) for k, v in NODES.items()}
for a, b, colour, text, *_ in ARROWS:
    dx, dy = pos[b][0] - pos[a][0], pos[b][1] - pos[a][1]
    down, up = dy > 0.6 * abs(dx), -dy > 0.6 * abs(dx)           # leave under the text of a node, arrive under the text of the next one
    p, q = edge(pos[a], pos[b], 100 if down else 66), edge(pos[b], pos[a], 100 if up else 84)
    out.append(f'<line x1="{p[0]:.0f}" y1="{p[1]:.0f}" x2="{q[0]:.0f}" y2="{q[1]:.0f}" stroke="{colour}" stroke-width="2.4" marker-end="url(#a{colour[1:]})"/>')
# Jellyfin plays what is in the library: a long dashed line round the outside
out.append('<path d="M950 712 L950 752 L24 752 L24 180 L248 180" fill="none" stroke="#94a3b8" stroke-width="2.2" stroke-dasharray="7 6" marker-end="url(#a94a3b8)"/>')
out.append(label(560, 752, "Jellyfin plays what is in your library"))
# Tailscale: the private way in
tx, ty = 130, 620
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
    out.append(f'<text x="{x}" y="{y + 36}" class="t">{title}</text><text x="{x}" y="{y + 58}" class="s">{small}</text>')

# Tailscale node
out.append(f'<image href="{data_uri("tailscale")}" x="{tx - 32}" y="{ty - 62}" width="64" height="64"/>')
out.append(f'<text x="{tx}" y="{ty + 36}" class="t">Tailscale</text><text x="{tx}" y="{ty + 58}" class="s">private access</text>')

# port labels on top of the lines
for a, b, colour, text, *rest in ARROWS:
    p, q = pos[a], pos[b]
    t = rest[0] if rest else 0.5
    out.append(label(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t + (rest[1] if len(rest) > 1 else 0), text))
out.append(f'<text x="{W / 2:.0f}" y="{H - 14}" class="s" style="font-size:14px">The numbers are the standard ports. If one is busy, the setup picks a free one. Logos belong to their projects.</text>')
out.append("</svg>")
svg = "\n".join(out)
(ROOT / "docs" / "images" / "how-it-fits.svg").write_text(svg)
print(f"wrote docs/images/how-it-fits.svg ({len(svg) // 1024} KB)")
