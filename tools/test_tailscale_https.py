"""Tests for the private HTTPS addresses tool. Needs no Docker and no Tailscale. Run: python3 tools/test_tailscale_https.py"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "wizard" / "app"))
import tailscale_https as t  # noqa: E402

DNS = "myserver.tail1234.ts.net"

# docker's list of published ports
ps = """jellyfin|0.0.0.0:8096->8096/tcp, [::]:8096->8096/tcp, 0.0.0.0:1900->1900/udp
sonarr|0.0.0.0:8989->8989/tcp, [::]:8989->8989/tcp
komga|0.0.0.0:25600->25600/tcp
samba|0.0.0.0:445->445/tcp
flaresolverr|0.0.0.0:8191->8191/tcp, 8192/tcp
regional|
jellystat-db|5432/tcp
"""
c = t.parse_ports(ps)
assert c == {"jellyfin": [8096], "sonarr": [8989], "komga": [25600], "samba": [445], "flaresolverr": [8191]}, c

# what Tailscale already serves
serve = json.dumps({"TCP": {"18096": {"HTTPS": True}}, "Web": {f"{DNS}:18096": {"Handlers": {"/": {"Proxy": "http://localhost:8096"}}}}})
assert t.parse_serve(serve, DNS) == {18096: 8096}
assert t.parse_serve("", DNS) == {} and t.parse_serve("not json", DNS) == {}

assert t.url_of(DNS, 443) == f"https://{DNS}" and t.url_of(DNS, 18096) == f"https://{DNS}:18096"

# port numbers: easy to remember, never a public internet port, never twice
assert t.assign(8096, set()) == 18096
assert t.assign(80, set()) == 10080
assert t.assign(25600, set()) == 45600
assert t.assign(8096, {18096}) == 18097
assert t.assign(0, set()) not in t.FUNNEL and t.assign(433, set()) == 10433 and 10000 not in {t.assign(p, set()) for p in range(1, 9000)}

# the plan: keep what exists, add the rest, refuse what is not a web page or is dangerous
web = {8096, 8989, 25600}
items = {i["name"]: i for i in t.plan(c, {18096: 8096}, DNS, probe=lambda p: p in web)}
assert items["jellyfin"]["state"] == "have" and items["jellyfin"]["url"] == f"https://{DNS}:18096"
assert items["sonarr"]["state"] == "add" and items["sonarr"]["https"] == 18989
assert items["komga"]["state"] == "add" and items["komga"]["https"] == 45600
assert items["samba"]["state"] == "skip", "file sharing must never get a web address"
assert items["flaresolverr"]["state"] == "skip", "the browser helper must never be shared"
skipped = {i["name"]: i for i in t.plan(c, {}, DNS, skip=["sonarr"], probe=lambda p: True)}
assert skipped["sonarr"]["state"] == "skip"
extra = {i["name"]: i for i in t.plan({}, {}, DNS, extra={"qbittorrent": 8080}, probe=lambda p: True)}
assert extra["qbittorrent"]["https"] == 18080
nothing = t.plan(c, {}, DNS, probe=lambda p: False)
assert all(i["state"] == "skip" for i in nothing), "a port that is not a web page must never be served"

# after a Tailscale reset, remembered addresses come back exactly as they were
back = {i["name"]: i for i in t.plan(c, {}, DNS, probe=lambda p: p in web, remembered={25600: 12560, 8096: 18096})}
assert back["komga"]["https"] == 12560 and back["jellyfin"]["https"] == 18096 and back["sonarr"]["https"] == 18989

# an address you chose yourself, even on the standard HTTPS port, is kept as it was
mine = {i["name"]: i for i in t.plan({"erp": [3001]}, {}, DNS, probe=lambda p: True, remembered={3001: 443})}
assert mine["erp"]["https"] == 443 and mine["erp"]["url"] == f"https://{DNS}"

# homepage: links change, comments and layout stay
yaml_text = """# my dashboard
- Media:
    - Jellyfin:
        icon: jellyfin
        href: http://192.168.X.X:8096
        container: jellyfin
    - Sonarr:
        icon: sonarr
        container: sonarr
    - Other:
        href: http://example.org
        container: unknown
"""
new, n = t.update_homepage(yaml_text, t.plan(c, {18096: 8096}, DNS, probe=lambda p: p in web))
assert n == 2, n
assert f"href: https://{DNS}:18096" in new and f"href: https://{DNS}:18989" in new
added = [{**i, "state": "added"} if i["state"] == "add" else i for i in t.plan(c, {18096: 8096}, DNS, probe=lambda p: p in web)]
assert t.update_homepage(yaml_text, added)[1] == 2, "links of addresses that were just added must change too"
assert "# my dashboard" in new and "href: http://example.org" in new
again, n2 = t.update_homepage(new, t.plan(c, {18096: 8096, 18989: 8989}, DNS, probe=lambda p: p in web))
assert n2 == 0 and again == new, "running twice must change nothing"
print("Private HTTPS tests passed.")
