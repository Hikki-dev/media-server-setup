---
name: media-server-setup
description: Sets up a complete home media server with a simple page in the browser, on Windows, Mac or Linux. It installs and links Sonarr, Radarr, Prowlarr, qBittorrent, Bazarr, Jellyfin, Seerr and Homepage, and can add live TV and sports. It also works with apps the person already runs. Use it when someone wants to set up, change, fix or check automatic downloads of movies, shows and anime, subtitles, quality choices for different languages, Jellyfin playback, or live TV.
---

# Media server setup

A page in the browser (run inside Docker) installs the whole server and links every app. The person only answers questions. Claude gets Docker ready, starts the page, stays with them, and checks the result.

## Files

| Where | What it is |
|---|---|
| Start on Windows.bat, Start on Mac.command, Start on Linux.sh | Start the setup, then open http://localhost:7979 |
| tools/start.sh | The shared start script for Mac and Linux |
| wizard/app | The program: server.py (the install flow), configure.py (talks to each app), adopt.py and audit.py (apps the person already has, and the list of changes), stack.py (Docker and drives), sharing.py (optional file sharing settings), tailscale_https.py (private HTTPS addresses), livetv.py (channel lists), bridge.py (Tamil and Malayalam sources and the daily channel update) |
| wizard/presets/trash.json | The community quality rules |
| tools/build_trash_presets.py | Rebuilds those rules |
| docs | Getting started, How everything fits, What it sets up, File sharing, Private HTTPS, Live TV and VPN, Fixing problems. The setup page shows them as a guide |
| extras | NordVPN, Smoother channels and File sharing, for people who run their own server |

## Steps

1. Check Docker. The command docker info must work. On Windows and Mac the person needs Docker Desktop running (Windows with WSL2). On Linux they need Docker Engine with the compose plugin. Offer to open the download page.
2. Start the setup from this folder, never from inside wizard:
   Mac: bash ./tools/start.sh mac
   Linux: bash ./tools/start.sh linux
   Windows: Start on Windows.bat
   Two settings can be changed first: ARR_STACK_DIR (where settings are kept, default ArrStack in the home folder) and ARR_MEDIA_DIR (suggested media folder, default ArrMedia).
3. The person answers at http://localhost:7979. Do not fill the form for them unless they ask. Never start an install through the API while they have the page open, because it takes over their session.
4. Watch progress with the events address: curl localhost:7979/api/events?since=0 (put the address in quotes). The first run takes 5 to 15 minutes because apps download. The page has a Stop button.
5. Check the result (below), then point them to the list of logins on the last page and the Find a title tab.

## What the person chooses

1. Storage: one drive, or separate drives with a downloads folder and any number of Movies, TV Shows and Anime folders. Folders they already have are used as they are.
2. What they watch: TV, movies, anime and languages. Quick choices cover common cases.
3. Quality choices: the picture quality for TV and for movies (4K only, 4K or 1080p, 1080p only, 1080p or 720p, 720p only), size limits, and whether English subtitles are needed.
4. Live TV and sports (optional): countries, kinds of channel, languages, worldwide sports, live channels on YouTube, and their own provider links. Free lists only hold free channels.
5. Downloads: minimum number of sources (default 2), how often to look, downloads at once, speed limits, and the qBittorrent login.
6. Logins: one main login for the apps, and one for qBittorrent. The password boxes have Show and Generate.

## File sharing (optional)

Offer it on Linux when the person wants to open their media or drives from other computers or phones. In the wizard it is the File sharing tile on the Apps and accounts step. It needs port 445 free on the computer. If the computer already runs Samba, use extras/File sharing/Share folders on this computer.sh instead, which adds to it safely. Never suggest opening port 445 on the router. For use away from home, follow docs/File sharing.md and use Tailscale. If a Mac can connect over Tailscale but not at home, read the last section of that guide before changing anything.

## Private HTTPS addresses (optional)

Offer it on Linux when Tailscale is installed. It is the Private HTTPS addresses tile on the Apps and accounts step, and tools/start.sh passes Tailscale in when it finds it. The person must press Enable HTTPS once in the Tailscale admin page under DNS. The tool in wizard/app/tailscale_https.py also works alone. It only adds addresses. Never run tailscale serve reset, because that removes entries by hand that cannot be rebuilt. See docs/Private HTTPS.md.

## Portainer

If the person uses Portainer, read docs/Portainer.md before changing a stack. Updating a stack removes and recreates every container in it. After any update run docker ps -a and start anything left in Created. A loose container with the same name as a stack service is the usual reason an update fails.

## Apps the person already has

The page looks for Sonarr, Radarr, Prowlarr, qBittorrent, Bazarr, Jellyfin, Seerr and a helper for protected websites that already run in Docker. In the step Your apps they choose, for each one, to use theirs or install a new one. Any mix works.

1. Connecting: the access key is read from the app itself. qBittorrent needs its web username and password. Jellyfin needs an access key (Dashboard, then API Keys) or an admin login. Test connection only looks. Ask the person to type these themselves and never read them back.
2. What it touches: the app is added to a shared Docker network under its plain name. An app on the host network, or behind a VPN container, is reached through that network. Nothing else about the app changes.
3. What changes (the second to last step): the setup runs as a trial against their apps. It looks at everything and writes nothing. Every group of settings is listed, with how the app is now next to what the setup would set, and a switch: setup will change this, or keep mine as it is. Change everything and Keep everything of mine work per app. Groups that already match are listed as such. Risky groups start on keep mine: logins, deleting standard quality choices, library folders, qBittorrent folders, Jellyfin network and the default rights of new Seerr users.
4. Never replaced when the app is theirs: links they already have (qBittorrent client, Jellyfin link in Sonarr and Radarr, Seerr servers, Bazarr links), request rules, the recycle bin, subtitle file types (ours are added), the Jellyfin server name, qBittorrent folders, and search sites they added.
5. Applying: only the groups left on are written. The choice is saved, so later changes from the dashboard keep respecting it.
6. From the shell: POST /api/preview with the same body as /api/install, then GET /api/preview/status. GET /api/detect lists what was found.

## Things that matter

1. No uploading afterwards. qBittorrent stops sharing and Sonarr and Radarr remove each download once it is filed. Files are linked when downloads and library are on the same drive, and copied otherwise.
2. Size limits are per file and per quality choice.
3. English subtitles are preferred in downloads, and Bazarr fills the gaps. A strict option refuses downloads that do not mention English subtitles.
4. Tamil and Malayalam sources (BT4G, TamilMV, TamilBlasters, MovieRulz) go through a small helper that finds their current address by itself. If one says searching, use Apps and links, then Find the address.
5. Bazarr is linked to Sonarr, Radarr and Jellyfin. Its folder list is made from the drives they chose.
6. AniDB is optional. If they want better anime subtitles, walk them through registering their own free AniDB client. Never register one for them.
7. NordVPN is optional, on the Live TV step. With a service login, channels that only work in some countries are tested through a UK and a US connection. Never ask for or print the login.
8. Jellyfin is tuned for any device. The graphics chip is only used when a test proves it works. On Windows, Mac and Docker Desktop there is no graphics chip inside Docker. Say so if they ask.
9. Live TV is built from free public lists with broken channels removed every day. Guides come from public guide files and cover only some channels. Never add illegal streams.
10. Download safety is always on. qBittorrent blocks program files and runs nothing, quality choices turn down downloads that mention programs or cracks, and the helper only returns video. Never weaken this.
11. Notifications are optional (Discord, Telegram, Pushover, ntfy, Gotify). A test message is sent when saved.
12. Every login is tested by signing in at the end. Report any that fail.

## Checking

Run these and look at the answers:

1. docker compose ps for the stack, with the project name arrstack
2. curl localhost:7979/api/state (installed must be true)
3. curl localhost:7979/api/credentials (every login must say ok true)
4. curl localhost:7979/api/regional (the Tamil and Malayalam sources and their addresses)

For a title: open Find a title and press Add and check. It does a real search, shows how many downloads were found and accepted, why others were turned down, and offers Download anyway. The docs file Fixing problems explains each reason.

## Changing things later

1. Quality, sizes, subtitles, downloads, languages: the dashboard tabs. They apply at once and are safe to repeat. Or POST /api/retune with the new choices.
2. Storage or new drives: start the setup again with /?setup=1. Files are never moved.
3. Stop or start all apps: Apps and links, or POST /api/stack with the action stop or start.
4. A half finished install: press Stop, then Clean up and start over. It removes only apps and settings made by the setup, never media. It is refused once the install is complete.

## Keeping the quality rules fresh

Now and then, get the latest community guide and rebuild the rules:

1. git clone the TRaSH Guides repository (depth 1)
2. python3 tools/build_trash_presets.py Guides/docs/json

Then start the setup again so it uses the new rules.

## Rules for Claude

1. Never print or store the passwords the person chooses. The setup keeps them in a private file in the stack folder.
2. Only use Docker commands for the arrstack project. Never remove volumes or images everywhere.
3. Do not delete anything inside the media folders.
4. If a step fails, read the logs of the setup and of the app that failed before trying again. The install is safe to repeat.
