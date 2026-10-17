# Media Server Setup

One page in your browser that installs a complete home media server and connects every part of it.

You answer a few simple questions. The setup does the rest: it installs the apps, links them together, and tries a real search to prove it works before it says it is done.

## What you get

| App | What it does for you |
|---|---|
| Jellyfin | Where you watch your movies, shows, anime and live TV |
| Seerr | A page where family and friends ask for something to watch |
| Sonarr | Finds and downloads TV shows and anime |
| Radarr | Finds and downloads movies |
| Prowlarr | Keeps the list of websites that Sonarr and Radarr search |
| qBittorrent | Does the downloading, and stops uploading when it is done |
| Bazarr | Finds subtitles, English first |
| Homepage | One page with a button for every app |

It also sets up quality choices for each language you watch, size limits, notifications to your chat app, and optional live TV and sports channels.

## Before you start

1. A computer that can run Docker. Windows and Mac need Docker Desktop. Linux needs Docker Engine.
2. About 8 GB of memory and 20 GB of free space for the apps. Your media needs its own space.
3. An internet connection. The first install downloads several GB.

## Install

1. Download this project and unzip it, or use the green Code button on GitHub.
2. Start the file for your computer:
   * Windows: double click "Start on Windows.bat"
   * Mac: double click "Start on Mac.command". The first time, right click it and choose Open.
   * Linux: open a terminal in this folder and run: bash "Start on Linux.sh"
3. Your browser opens at http://localhost:7979. Answer the questions and press Install.

The first install takes 5 to 15 minutes. You can stop it at any time. Stopping never touches your media.

## Use it with Claude Code

Copy this folder into your Claude skills folder and name it media-server-setup. Then say "set up my media server". Claude starts the setup, stays with you, and checks that everything works. See SKILL.md for what Claude does.

## Already have some of these apps

You do not have to start again. The setup finds the apps already on your computer. For each one you choose to keep using yours or install a new one beside it. Any mix works.

Before anything is touched, the What changes page lists every setting the setup wants to change, next to how it is set today. Each part has a switch to keep yours. Nothing is changed until you say so. Connections you already have, logins, request rules, folder names and search sites you added are kept unless you switch them.

## Live TV and sports

This part is optional. It adds a Live TV section to Jellyfin from free public channel lists, tests every channel, and removes broken ones every day. You can pick countries, kinds of channel and languages. It can also add live news channels on YouTube. NordVPN can be added so channels that only work in some countries are tried through the UK and the US.

Paid sports are not on free lists, so they are not included. If you pay a TV provider, you can paste their channel list and guide links. See docs/Live TV and VPN.md.

## Your privacy and safety

1. Everything runs on your own computer. Nothing is sent to us, and there is no tracking.
2. Passwords you choose are kept in a private file on your computer. They are never shown in logs or sent anywhere except to your own apps.
3. Downloads are made safe. Program files (like .exe) are blocked, nothing is run when a download finishes, and quality choices turn down downloads that mention programs or cracks.
4. Your own apps are only read until you approve the changes.

To report a security problem, read SECURITY.md.

## Help and more reading

1. docs/What it sets up.md explains everything the setup does.
2. docs/Fixing problems.md covers the common problems.
3. docs/Live TV and VPN.md covers channels and NordVPN.
4. docs/How it works.md is for people who want to change the code.

## Contributing

Fixes and ideas are welcome. Read CONTRIBUTING.md first. It explains how to run the checks and what we ask of every change.

## Credits

The quality rules come from the TRaSH Guides. Channel lists come from the iptv org project, and TV guides from EPG Share. Thank you to everyone who keeps these free.

## Licence

MIT. You can use, change and share this freely. See LICENSE.
