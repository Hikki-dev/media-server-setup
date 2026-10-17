#!/usr/bin/env python3
"""Regenerates wizard/presets/trash.json from the TRaSH-Guides repository.

  git clone --depth 1 https://github.com/TRaSH-Guides/Guides.git
  python3 tools/build_trash_presets.py Guides/docs/json

Run this occasionally to pick up new release-group tiers and score changes.
"""
import json
import os
import sys

ROOT = sys.argv[1]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wizard", "presets", "trash.json")

PROFILES = {
    "sonarr": {"series": "web-1080p", "anime": "anime-remux-1080p"},
    "radarr": {"movie": "hd-bluray-web", "anime": "anime-remux-1080p"},
}
EXTRA_GROUPS = {  # cf-groups merged on top of each profile's own formatItems
    ("sonarr", "series"): ["unwanted-formats", "streaming-services-general", "streaming-services-hd-uhd-boost",
                           "streaming-services-asian", "release-groups-asian", "required-repack-proper"],
    ("radarr", "movie"): ["unwanted-formats", "streaming-services-general", "streaming-services-asian",
                          "release-groups-asian", "required-repack-proper"],
    ("sonarr", "anime"): ["required-anime-versions"],
    ("radarr", "anime"): ["required-anime-versions"],
}
ALWAYS = ["Language: Not Original", "Language: Not English"]
LANG_FIELD_NAMES = {"value"}


def load(path):
    with open(path) as f:
        return json.load(f)


def clean_specs(specs):
    out = []
    for s in specs:
        out.append({"name": s["name"], "implementation": s["implementation"], "negate": s.get("negate", False),
                    "required": s.get("required", False),
                    "fields": [{"name": k, "value": v} for k, v in s.get("fields", {}).items()]})
    return out


def main():
    result = {}
    for app, kinds in PROFILES.items():
        cf_files = {}
        for fn in os.listdir(f"{ROOT}/{app}/cf"):
            d = load(f"{ROOT}/{app}/cf/{fn}")
            cf_files[d["name"]] = d
        groups = {}
        for fn in os.listdir(f"{ROOT}/{app}/cf-groups"):
            g = load(f"{ROOT}/{app}/cf-groups/{fn}")
            groups[fn[:-5]] = [c["name"] for c in g["custom_formats"]]
        out = {"profiles": {}, "cfs": {}}
        for kind, pname in kinds.items():
            p = load(f"{ROOT}/{app}/quality-profiles/{pname}.json")
            score_set = p.get("trash_score_set", "default")
            names = list(p["formatItems"].keys())
            for g in EXTRA_GROUPS.get((app, kind), []):
                names += groups.get(g, [])
            names += [n for n in ALWAYS if n in cf_files]
            names = list(dict.fromkeys(names))
            scores = {}
            for n in names:
                cf = cf_files.get(n)
                if not cf:
                    continue
                ts = cf.get("trash_scores", {})
                scores[n] = ts.get(score_set, ts.get("default", 0))
                out["cfs"][n] = {"includeCustomFormatWhenRenaming": cf.get("includeCustomFormatWhenRenaming", False),
                                 "specifications": clean_specs(cf["specifications"])}
            out["profiles"][kind] = {
                "name": p["name"], "cutoff": p["cutoff"], "scoreSet": score_set,
                "items": [{"name": i["name"], "allowed": i.get("allowed", False), "items": i.get("items")} for i in p["items"]],
                "scores": scores,
            }
        result[app] = out
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(result, f, separators=(",", ":"))
    for a, o in result.items():
        print(a, {k: len(v["scores"]) for k, v in o["profiles"].items()}, "cfs", len(o["cfs"]))


main()
