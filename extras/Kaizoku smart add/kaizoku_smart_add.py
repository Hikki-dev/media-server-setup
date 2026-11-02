#!/usr/bin/env python3
"""Add a manga to Kaizoku the careful way.

Kaizoku, when you add a series, lists every chapter of every source and may fetch them all from chapter 1.
This looks at what is already on your disk first, checks every source, and adds the series so that only the
NEXT chapters are downloaded, from the one source that is best, with the others kept as back-ups.

  python3 kaizoku_smart_add.py "Chainsaw Man"                 shows the plan, changes nothing
  python3 kaizoku_smart_add.py "Chainsaw Man" --apply         adds it
  options: --url http://localhost:9833  --library /mnt/Manga  --pick 2  --from 120

Needs only Python 3. Run it on the machine that has Kaizoku and the manga folder (or pass --library)."""
import argparse, json, os, re, sys, urllib.parse, urllib.request

# Chapter number from a file name: "Ch.230", "Chapter 230", "c230", "- 230.cbz", "[Group] Title 230.cbz" -- never "Vol.23", years or "(2020)"
_CH = [re.compile(r"(?<![a-z])(?:ch(?:apter)?|c)[\s._-]*(\d+(?:\.\d+)?)", re.I), re.compile(r"[\s_-](\d{1,4}(?:\.\d+)?)(?:\s*v\d)?\.(?:cbz|cbr|zip|pdf|epub)$", re.I)]


def chapter_of(name):
    base = re.sub(r"\(\d{4}\)|\bvol(?:ume)?[\s._-]*\d+(?:\.\d+)?", " ", name, flags=re.I)       # drop volume numbers and years
    for rx in _CH:
        m = rx.search(base)
        if m:
            return float(m.group(1))
    return None


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def disk_chapters(library, title):
    """Chapter numbers already on disk for this title, from any folder under the library whose name matches."""
    found, folder = set(), None
    for root, dirs, files in os.walk(library):
        if root[len(library):].count(os.sep) > 2:
            dirs[:] = []
            continue
        if norm(os.path.basename(root)) == norm(title):
            folder = folder or root
            for f in files:
                n = chapter_of(f)
                if n is not None:
                    found.add(n)
    return found, folder


def analyse(group, disk_max):
    """What one source (one scanlator group of it) can offer."""
    nums = sorted({c["Number"] for c in group["chapters"] if c.get("Number") is not None})
    dates = [c["ProviderUploadDate"] for c in group["chapters"] if c.get("ProviderUploadDate") and not c["ProviderUploadDate"].startswith("0")]
    top = nums[-1] if nums else 0
    whole = len({int(n) for n in nums if n >= 1})                   # fractions and re-numbered parts must not make a source look bigger
    return {"group": group, "nums": nums, "top": top, "count": whole, "newest": max(dates) if dates else "",
            "new": [n for n in nums if n > disk_max], "dups": len(group["chapters"]) - len(nums)}


def plan(augmented, disk, from_chapter=None):
    """Pick the best group of each source; the best of all becomes permanent, the rest are back-ups."""
    disk_max = max(disk) if disk else 0
    if disk and len(disk) >= 1:                                       # one stray year-like number must not skip a whole series
        biggest = max((max(g["chapters"], key=lambda c: c.get("Number") or 0)["Number"] or 0) for g in augmented["series"] if g["chapters"])
        if disk_max > biggest + 10:
            disk_max = max(n for n in disk if n <= biggest + 10)
    start = from_chapter if from_chapter is not None else disk_max
    cands = [analyse(g, start) for g in augmented["series"] if g["chapters"]]
    best_per_source = {}
    for c in cands:                                                   # many tiny scanlator groups: keep only each source's biggest
        k = c["group"]["mihonProviderId"]
        key = (c["top"], c["count"], c["newest"])
        if k not in best_per_source or key > (best_per_source[k]["top"], best_per_source[k]["count"], best_per_source[k]["newest"]):
            best_per_source[k] = c
    ranked = sorted(best_per_source.values(), key=lambda c: (c["top"], c["count"], c["newest"]), reverse=True)
    usable = [c for c in ranked if c["top"] >= start - 1 or c["new"]]  # a source that stops far below what you own cannot continue it
    if usable:                                                       # a back-up that has almost nothing is only noise
        usable = [c for c in usable if c is usable[0] or c["count"] >= usable[0]["count"] / 2]
    return start, ranked, usable


def call(url, path, body=None, timeout=600):
    req = urllib.request.Request(url + path, data=None if body is None else json.dumps(body).encode(), headers={"content-type": "application/json"}, method="GET" if body is None else "POST")
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def main():
    a = argparse.ArgumentParser(); a.add_argument("title"); a.add_argument("--url", default="http://localhost:9833"); a.add_argument("--library", default="/mnt/Manga")
    a.add_argument("--pick", type=int, default=0, help="if the search finds several different series, which one (0 = first)"); a.add_argument("--from", dest="start", type=float, help="download after this chapter number")
    a.add_argument("--apply", action="store_true"); o = a.parse_args()
    found = call(o.url, "/api/search?keyword=" + urllib.parse.quote(o.title))
    groups = [x for x in found if x.get("linkedIds")]
    if not groups:
        sys.exit("Nothing found. Every source answered with no match, or all of them are down.")
    top = groups[o.pick] if o.pick < len(groups) else groups[0]
    ids = {top["mihonId"], *top["linkedIds"]}
    cluster = [x for x in found if x["mihonId"] in ids]
    print(f"Matched {top['title']!r} on: {', '.join(x['provider'] for x in cluster)}")
    aug = call(o.url, "/api/search/augment", cluster)
    for e in aug.get("sourceErrors", []):
        print("  source problem:", e.get("reason") or e)
    disk, folder = disk_chapters(o.library, top["title"])
    print(f"On disk: {len(disk)} chapters" + (f" in {folder}, highest {max(disk):g}" if disk else " (nothing yet, so everything is wanted)"))
    start, ranked, usable = plan(aug, disk, o.start)
    if not usable:
        sys.exit("No source can continue this series (all stop far below what you already have). Nothing added.")
    for i, c in enumerate(ranked):
        g = c["group"]
        print(f"  {'PERMANENT' if c is usable[0] else 'back-up  ' if c in usable else 'skipped  '} {g['provider']:<12} up to {c['top']:g}, {c['count']} chapters, {len(c['new'])} new, newest {c['newest'][:10] or '?'}")
    miss = sorted(set(range(1, int(start) + 1)) - {int(n) for n in disk}) if disk else []
    sparse = o.start is None and disk and len(miss) > start / 2
    if miss:
        print(f"  note: {len(miss)} chapter numbers below {start:g} are not on disk (first: {miss[:8]}).")
    if sparse:
        print("  WARNING: the folder holds only a few chapters, so 'continue after the highest' would leave most of the series out.\n"
              "           Use --from 0 to download everything, or --from N to continue after chapter N.")
        if o.apply:
            sys.exit("Not added. Choose --from first.")
    chosen = {id(c["group"]): c for c in usable}
    for g in aug["series"]:
        c = chosen.get(id(g))
        g["isSelected"] = c is not None
        if c:
            g["isStorage"] = c is usable[0]
            g["fromChapter"] = start if start > 0 else None
    aug["startChapter"] = start + 1 if start > 0 else None
    root = aug.get("storageFolderPath") or "/series"             # where Kaizoku sees the library; the series goes in the folder you already have, or Manga/<title>
    rel = os.path.relpath(folder, o.library).replace(os.sep, "/") if folder else ("Manga/" + re.sub(r'[\\/:*?"<>|]', "", top["title"]))
    aug["storageFolderPath"] = root.rstrip("/") + "/" + rel
    aug["series"] = [g for g in aug["series"] if g["isSelected"]]       # Kaizoku adds everything it is given: only the chosen groups go in
    for g in aug["series"]:
        g["type"] = g.get("type") or "Manga"
    if not o.apply:
        print("Plan only. Run again with --apply to add it.")
        return
    print("Added:", call(o.url, "/api/serie", aug))


def _selftest():
    assert chapter_of("Chainsaw Man - Vol.23 Ch.229.cbz") == 229 and chapter_of("One Piece - Ch.10.cbz") == 10
    assert chapter_of("Disc 2.cbz") == 2 and chapter_of("Title Disc Chapter 9.cbz") == 9
    assert chapter_of("[MangaKatana][en] Chainsaw Man 231.cbz") == 231 and chapter_of("Title Ch.12.5.cbz") == 12.5 and chapter_of("cover.jpg") is None
    ch = lambda ns: [{"Number": n, "ProviderUploadDate": "2024-01-01T00:00:00"} for n in ns]
    aug = {"series": [{"mihonProviderId": "A", "chapters": ch(range(1, 101))}, {"mihonProviderId": "A", "chapters": ch([1, 2])},
                      {"mihonProviderId": "B", "chapters": ch(range(1, 90))}, {"mihonProviderId": "C", "chapters": ch([1, 2, 3])}]}
    s, ranked, usable = plan(aug, {float(n) for n in range(1, 80)})
    assert s == 79 and usable[0]["group"]["mihonProviderId"] == "A" and [c["group"]["mihonProviderId"] for c in usable] == ["A", "B"]
    assert plan(aug, {2023.0, 5.0})[0] == 5                          # a year-like stray number is ignored
    assert len(plan(aug, {5.0})[2]) == 2                               # B has 89 of A's 100 chapters, C has 3: C is dropped
    assert plan(aug, set())[0] == 0 and plan(aug, {5.0}, 0)[0] == 0   # empty disk, or --from 0: everything
    print("self-test ok")


if __name__ == "__main__":
    _selftest() if len(sys.argv) > 1 and sys.argv[1] == "--selftest" else main()
