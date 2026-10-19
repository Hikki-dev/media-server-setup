# Media Server Setup

One page in your browser that installs a complete home media server and connects every part of it.

<p align="center"><img src="docs/images/step-9-apps.png" alt="The Apps and accounts screen of the setup page, with a tile for every app" width="100%"></p>

You answer a few simple questions. The setup does the rest: it installs the apps, links them together, and tries a real search to prove it works before it says it is done.

## What you get

<table>
<tr><td width="64"><img src="docs/images/icons/jellyfin.png" alt="Jellyfin logo" width="48"></td><td width="150"><b>Jellyfin</b></td><td>Where you watch your movies, shows, anime and live TV</td></tr>
<tr><td><img src="docs/images/icons/seerr.png" alt="Seerr logo" width="48"></td><td><b>Seerr</b></td><td>A page where family and friends ask for something to watch</td></tr>
<tr><td><img src="docs/images/icons/sonarr.png" alt="Sonarr logo" width="48"></td><td><b>Sonarr</b></td><td>Finds and downloads TV shows and anime</td></tr>
<tr><td><img src="docs/images/icons/radarr.png" alt="Radarr logo" width="48"></td><td><b>Radarr</b></td><td>Finds and downloads movies</td></tr>
<tr><td><img src="docs/images/icons/prowlarr.png" alt="Prowlarr logo" width="48"></td><td><b>Prowlarr</b></td><td>Keeps the list of websites that Sonarr and Radarr search</td></tr>
<tr><td><img src="docs/images/icons/qbittorrent.png" alt="qBittorrent logo" width="48"></td><td><b>qBittorrent</b></td><td>Does the downloading, and stops uploading when it is done</td></tr>
<tr><td><img src="docs/images/icons/bazarr.png" alt="Bazarr logo" width="48"></td><td><b>Bazarr</b></td><td>Finds subtitles, English first</td></tr>
<tr><td><img src="docs/images/icons/flaresolverr.png" alt="FlareSolverr logo" width="48"></td><td><b>FlareSolverr</b></td><td>Helps the searches get past robot checks on search websites</td></tr>
<tr><td><img src="docs/images/icons/homepage.png" alt="Homepage logo" width="48"></td><td><b>Homepage</b></td><td>One page with a button for every app</td></tr>
<tr><td><img src="docs/images/icons/tailscale.png" alt="Tailscale logo" width="48"></td><td><b>Tailscale</b> (optional)</td><td>A private way to reach everything from anywhere, with safe HTTPS addresses</td></tr>
</table>

It also sets up quality choices for each language you watch, size limits, notifications to your chat app, and optional live TV and sports channels.

## How everything fits together

Ask once in Seerr, and the rest happens by itself. The small numbers on the arrows are the standard ports of each app. Click the picture to see it full size.

<p align="center"><a href="docs/images/how-it-fits.svg"><img src="docs/images/how-it-fits.svg" alt="Diagram: you ask in Seerr, Radarr and Sonarr search through Prowlarr, qBittorrent downloads into your library, Bazarr adds subtitles and Jellyfin plays it" width="100%"></a></p>

## See it, one step at a time

Every screen explains itself in plain words. These are the main ones. Click a picture to see it full size. The full walk through is in [docs/Getting started.md](docs/Getting%20started.md).

### Where is everything kept

<a href="docs/images/step-4-storage.png"><img src="docs/images/step-4-storage.png" alt="Storage screen: choose where downloads and each library are kept, and see which folders share a drive" width="100%"></a>

It shows which folders are on the same drive, so finished downloads are linked instantly instead of copied.

### Pick folders you already have

<a href="docs/images/step-4-folder-picker.png"><img src="docs/images/step-4-folder-picker.png" alt="Folder picker: browse your drives and choose a folder" width="100%"></a>

Browse your drives and choose a folder. Nothing inside it is moved, renamed or deleted.

### What you watch

<a href="docs/images/step-5-what-you-watch.png"><img src="docs/images/step-5-what-you-watch.png" alt="What do you watch screen with quick choices for languages and kinds of media" width="100%"></a>

One click chooses the quality rules, the search sites and the subtitle languages.

### Live TV and sports

<a href="docs/images/step-6-live-tv.png"><img src="docs/images/step-6-live-tv.png" alt="Live TV and sports screen with countries, kinds of channel and a search box" width="100%"></a>

Optional. Free channels with a TV guide, tested every day.

### Profiles

<a href="docs/images/step-7-profiles.png"><img src="docs/images/step-7-profiles.png" alt="Profiles screen with quality and size limits for each language" width="100%"></a>

Each language gets its own picture quality and size limits.

### Downloads

<a href="docs/images/step-8-downloads.png"><img src="docs/images/step-8-downloads.png" alt="Downloads screen with the minimum number of sources and speed limits" width="100%"></a>

Sensible defaults. A finished download is removed, so nothing keeps uploading.

### Apps and accounts

<a href="docs/images/step-9-apps.png"><img src="docs/images/step-9-apps.png" alt="Apps and accounts screen with a tile for every app" width="100%"></a>

Choose what else to install, and the main login.

### File sharing

<a href="docs/images/step-9-file-sharing.png"><img src="docs/images/step-9-file-sharing.png" alt="File sharing card: a login, and a tick box and read only option for each folder and drive" width="100%"></a>

Optional. Shows your media and drives on your network, with one login.

### Private HTTPS addresses

<a href="docs/images/step-9-private-https.png"><img src="docs/images/step-9-private-https.png" alt="Private HTTPS addresses card explaining how every app gets a safe address with Tailscale" width="100%"></a>

Optional. Safe addresses for every app, with Tailscale.

### Review

<a href="docs/images/step-10-review.png"><img src="docs/images/step-10-review.png" alt="Review screen listing everything that is about to be set up" width="100%"></a>

One last look at everything before anything is installed.

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

## Light and dark mode

The setup page and the guide start in a soft light theme that is easy on the eyes. A button at the bottom of the left side switches to dark mode, and the choice is remembered.

<a href="docs/images/step-1-welcome.png"><img src="docs/images/step-1-welcome.png" alt="The welcome screen in light mode, the default" width="100%"></a>

Light mode, the default.

<a href="docs/images/dark-mode-apps.png"><img src="docs/images/dark-mode-apps.png" alt="The apps screen in dark mode" width="100%"></a>

Dark mode, one button away.

## A guide with pictures

The setup page has a guide at the bottom of the left side: Open the guide. It is the same set of pages as the docs folder, with screenshots and a picture of how the apps work together. Start with docs/Getting started.md.

![The guide inside the setup page](docs/images/guide-page.png)

## Private HTTPS addresses

This part is optional. With Tailscale on the server, every app gets a safe HTTPS address that works from any of your own devices, at home or away, and Homepage links are changed to match. Nothing is opened on your router. It can also be used on its own, for any Docker containers. See docs/Private HTTPS.md.

## Share your folders and drives

This part is optional. It makes your media folder and your other drives show up on your home network, so you can open them from Windows, Mac, Linux and phones, and reach them from anywhere with Tailscale. It uses one login, no guest access, and settings chosen for speed and safety. It works on Linux. You can switch it on in the setup page, or use the script in extras/File sharing on a computer that does not run the setup. The guide also explains how to prepare your drives properly. See docs/File sharing.md.

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
4. docs/File sharing.md covers sharing your folders and drives, setting up drives, and using them away from home.
5. docs/Private HTTPS.md covers safe addresses for every app with Tailscale.
   docs/Portainer.md covers keeping the apps in Portainer stacks, and the mistakes that leave apps stopped.
6. docs/Getting started.md and docs/How everything fits.md are the guide with pictures.
7. docs/How it works.md is for people who want to change the code.

## Contributing

Fixes and ideas are welcome. Read CONTRIBUTING.md first. It explains how to run the checks and what we ask of every change.

## Credits

The app logos in the pictures are from the Dashboard Icons collection and belong to their projects. The quality rules come from the TRaSH Guides. Channel lists come from the iptv org project, and TV guides from EPG Share. Thank you to everyone who keeps these free.

## Licence

MIT. You can use, change and share this freely. See LICENSE.
