"""Draws the two Live TV pictures in docs/images: livetv-routing.svg (how a channel reaches Jellyfin) and livetv-daily.svg (the daily update).
Run from the top folder:  python3 tools/build_livetv_diagrams.py
It stops with an error when two boxes overlap or a label covers a box. The logos belong to their projects."""
import base64
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ICONS = ROOT / "docs" / "images" / "icons"
OUT = ROOT / "docs" / "images"
STYLE = ("<style>.t{font-size:21px;font-weight:700;fill:#0f172a;text-anchor:middle}.s{font-size:15.5px;fill:#475569;text-anchor:middle}"
         ".l{font-size:16px;font-weight:700;fill:#334155;text-anchor:middle}.h{font-size:32px;font-weight:700;fill:#0f172a;text-anchor:middle}"
         ".n{font-size:19px;font-weight:700;fill:#fff;text-anchor:middle}</style>")


def icon(name):
    return "data:image/png;base64," + base64.b64encode((ICONS / f"{name}.png").read_bytes()).decode()


class Pic:
    def __init__(self, w, h, title, desc):
        self.w, self.h, self.boxes, self.parts, self.cols = w, h, [], [], set()
        self.parts.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="Arial, Helvetica, sans-serif" '
                          f'role="img" aria-labelledby="t d"><title id="t">{title}</title><desc id="d">{desc}</desc><defs>@@MARKERS@@{STYLE}</defs>'
                          f'<rect width="{w}" height="{h}" fill="#f8fafc"/><text x="{w / 2:.0f}" y="46" class="h">{title}</text>')

    def box(self, x, y, w, h, title, small="", fill="#ffffff", stroke="#cbd5e1", logo=None):
        """A card with its centre at x, y."""
        self.boxes.append((x - w / 2, y - h / 2, x + w / 2, y + h / 2, title))
        self.parts.append(f'<rect x="{x - w / 2:.0f}" y="{y - h / 2:.0f}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        ty = y + (6 if not small else -4)
        if logo:
            self.parts.append(f'<image href="{icon(logo)}" x="{x - w / 2 + 14:.0f}" y="{y - 28:.0f}" width="56" height="56"/>')
            x += 28
        self.parts.append(f'<text x="{x:.0f}" y="{ty:.0f}" class="t">{title}</text>')
        if small:
            self.parts.append(f'<text x="{x:.0f}" y="{y + 22:.0f}" class="s">{small}</text>')

    def arrow(self, x1, y1, x2, y2, colour="#64748b", label=None, lx=None, ly=None, dash=False):
        self.cols.add(colour)
        dashes = ' stroke-dasharray="7 6"' if dash else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{colour}" stroke-width="2.6" marker-end="url(#a{colour[1:]})"{dashes}/>')
        if label:
            lx = (x1 + x2) / 2 if lx is None else lx
            ly = (y1 + y2) / 2 if ly is None else ly
            w = 10.8 * len(label) + 26
            self.boxes.append((lx - w / 2, ly - 15, lx + w / 2, ly + 15, "label " + label))
            self.parts.append(f'<rect x="{lx - w / 2:.0f}" y="{ly - 15:.0f}" width="{w:.0f}" height="30" rx="15" fill="#f8fafc" stroke="#cbd5e1"/>'
                              f'<text x="{lx:.0f}" y="{ly + 6:.0f}" class="l">{label}</text>')

    def note(self, x, y, text):
        self.parts.append(f'<text x="{x}" y="{y}" class="s">{text}</text>')

    def svg(self):
        for i, a in enumerate(self.boxes):
            for b in self.boxes[i + 1:]:
                if not (a[2] + 6 < b[0] or b[2] + 6 < a[0] or a[3] + 6 < b[1] or b[3] + 6 < a[1]):
                    raise SystemExit(f"These overlap: {a[4]} and {b[4]}")
            if a[0] < 0 or a[1] < 0 or a[2] > self.w or a[3] > self.h:
                raise SystemExit(f"Outside the picture: {a[4]}")
        marks = "".join(f'<marker id="a{c[1:]}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="{c}"/></marker>'
                        for c in sorted(self.cols))
        return "\n".join(self.parts).replace("@@MARKERS@@", marks) + "\n</svg>"


def routing():
    p = Pic(1400, 760, "How a channel reaches Jellyfin", "Jellyfin asks the Regional service for a channel. Regional plays it directly, or through the UK or US VPN connection, "
            "or resolves a YouTube channel and passes it through the relay.")
    p.box(150, 380, 220, 120, "Jellyfin", "plays the channel", logo="jellyfin", fill="#eef6ff", stroke="#7cb7f2")
    p.box(560, 380, 250, 130, "Regional", "the traffic director", fill="#fff7e6", stroke="#e8b34a")
    p.arrow(262, 380, 433, 380, "#64748b", "9120")
    p.box(1050, 150, 270, 100, "Open channels", "no VPN needed")
    p.box(1050, 300, 270, 100, "UK connection", "gluetun-uk, NordVPN", fill="#eef7f0", stroke="#6bbf8a")
    p.box(1050, 450, 270, 100, "US connection", "gluetun-us, NordVPN", fill="#eef7f0", stroke="#6bbf8a")
    p.box(1050, 600, 270, 100, "YouTube channels", "found by yt-dlp", fill="#fdeeee", stroke="#e08a8a")
    p.arrow(685, 340, 913, 160, "#64748b", "direct", 800, 232)
    p.arrow(685, 366, 913, 300, "#2f9e5a", "8888", 780, 325)
    p.arrow(685, 394, 913, 450, "#2f9e5a", "8888", 780, 438)
    p.arrow(685, 420, 913, 590, "#c75050", "yt-dlp", 770, 520)
    p.box(560, 640, 250, 100, "Relay", "joins audio and video", fill="#f3eefc", stroke="#a58be0")
    p.arrow(915, 615, 688, 640, "#c75050", "9130", 800, 658)
    p.arrow(435, 600, 262, 420, "#a58be0", "9130", 349, 510, dash=True)
    p.note(700, 725, "Only blocked channels use a VPN connection. Everything else plays directly. Logos belong to their projects.")
    return p.svg()


def daily():
    p = Pic(1500, 520, "The daily channel update", "Every night the setup collects channel lists, checks each stream, tries blocked channels through the VPN, matches TV guides "
            "and writes two files that Jellyfin reads.")
    steps = [("Collect", "free channel lists"), ("Check", "does each stream play"), ("Try the VPN", "for blocked ones"),
             ("Match guides", "what is on now"), ("Write files", "channels and guide"), ("Jellyfin", "refreshes itself")]
    x = 130
    for i, (a, b) in enumerate(steps):
        fill, stroke = ("#eef6ff", "#7cb7f2") if i == 5 else ("#ffffff", "#cbd5e1")
        p.box(x, 250, 200, 130, a, b, fill=fill, stroke=stroke, logo=None)
        p.parts.append(f'<circle cx="{x - 100}" cy="{250 - 65}" r="17" fill="#e4682a"/><text x="{x - 100}" y="{250 - 59}" class="n">{i + 1}</text>')
        if i < len(steps) - 1:
            p.arrow(x + 102, 250, x + 148, 250, "#64748b")
        x += 250
    p.note(750, 380, "Runs at night so it never slows down your evening. It runs gently, so playback is not affected.")
    p.note(750, 410, "Guides come from free public sources. Channels with no public guide simply show no programme list.")
    p.note(750, 490, "Logos belong to their projects.")
    return p.svg()


if __name__ == "__main__":
    for name, fn in (("livetv-routing.svg", routing), ("livetv-daily.svg", daily)):
        s = fn()
        (OUT / name).write_text(s)
        print(f"wrote docs/images/{name} ({len(s) // 1024} KB), no overlaps")
