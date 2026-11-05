# Changes

## Kapowarr: a clearer interface

1. Kapowarr has a new look in the style of Sonarr and Radarr, made easier to read for beginners and quicker for daily use. A sidebar with sections, a title and a plain sentence on every page, one icon set, one typeface, and the same spacing everywhere.
2. Every comic on the shelf shows how complete it is (`14 / 15` and "1 missing", or "Complete"). A series page opens with how many issues you have and how many are missing. When something is still needed to start (root folder, ComicVine key, download client), a short setup card says so.
3. On a phone there is a tab bar at the bottom. Dark is the default, light is under Settings, General.
4. The menu names are plainer: Volumes is now Series, Add Volume is Add Series, and Extras is New This Week. Nothing moved or stopped working.
5. The Kapowarr guide has screenshots of all of it ([Comics and manga](docs/Comics%20and%20manga.md)).

## Kapowarr: the Extras page

1. A new page in Kapowarr (now called **New This Week**, it was Extras) with four tabs. **Calendar** shows what comes out this week and the new series starting, and can follow the ones that match your watch list (a publisher or a word in the title) by itself. **Requests** lets anyone ask for a series and see how far it got. **Upgrades** lists issues in a less wanted format than your format preference. **Reading** shows your progress from Komga and searches caught-up series first.
2. Metron can be used as a second source for the calendar when ComicVine fails (needs a free metron.cloud account; not tried against the real service).
3. Removing the old file after an upgrade is off unless you set `KAPOWARR_UPGRADE_REMOVE_OLD=1`.

## A new home page

1. The website's home page now tells one story in order: why this exists, how it works, what you get, why people pick it, how easy it is, a demo, and the questions people ask first. A bar at the top jumps between the parts.
2. It is light by default, with a button in the top bar to switch to dark. The choice is remembered on that device. Each theme has its own screenshots of the setup page, so no dark screens show up in light mode.
3. It uses the same fonts as the setup page.

## Kapowarr: better results, hardlinks, messages

1. Torrent results are ordered better: a torrent nobody shares goes last, and more seeders wins between equal results. If a search finds nothing, a looser one (without year, volume and issue number) is tried. The same search within ten minutes is answered from memory: on a real library the second search of the same series took 6 seconds instead of 132.
2. A finished torrent is hard linked into the comics folder (instant, no second copy, keeps seeding), or copied when the folders are on different drives.
3. Optional: a message (ntfy, Discord or a webhook) when a comic is imported or a download fails, and a Komga scan after each import. Set `KAPOWARR_NOTIFY_URL` and `KAPOWARR_KOMGA_URL` on the container. See the fork's guide "Notifications, Komga and metrics".
4. `/api/system/metrics` gives plain-text numbers (queue, library size, Prowlarr speed) for Homepage, Beszel or Prometheus.

## Kapowarr is now a real fork

1. The Kapowarr copy is now a proper GitHub fork of the original (Casvt/Kapowarr), with the original's history. It merges the original every week, nothing is pushed back to it, and every change is listed in its FORK-NOTES.md.
2. Its image is now `ghcr.io/hikki-dev/kapowarr-fork`, public and linked to the fork. The setup uses that name. Older installs keep working; change the image name when you next update.
3. Both forks (Kapowarr and Rensaiō) now have the same set of guides: a flow diagram, FORK-NOTES, Upgrading and Troubleshooting. Kapowarr also has Prowlarr and torrents.
4. The old standalone Kapowarr repository was made private and archived (Kapowarr-pre-fork), not deleted.

## Staying current with the originals

1. Both copies (Kapowarr and Rensaiō) now check the original projects every week and bring in new work by themselves: a pull request when it merges cleanly and the checks pass, an issue when it needs a hand. Rensaiō has just been brought level with the original's newest work, and Kapowarr already is.
2. Upgrading from the original Kapowarr was tested on databases from versions 1.0.0 to 1.3.2. Version 1.0.0 and 1.1.0 used to stop part-way and now upgrade cleanly.
3. A torrent from Prowlarr was followed through to a real download in qBittorrent. Links that redirect to a magnet or point at a `.torrent` file now work too.

## Kapowarr, new base

1. The Kapowarr copy now follows the original's newest work and has Prowlarr and the Internet Archive as sources of their own. The setup adds the Prowlarr source and qBittorrent for you. Databases of the older copy are upgraded by themselves.

## Kapowarr copy

1. The Kapowarr copy is now a smaller image (170 MB) built for Intel/AMD and ARM, with a health check, so a Raspberry Pi uses it too. It is tested on every change, and the Tasks page shows "15 minutes" instead of "0 hours".

## Kaizoku, now Rensaiō

1. The manga app is now [Hikki-dev's copy of Rensaiō](https://github.com/Hikki-dev/Rensaio), the maintained successor of the archived Kaizoku. It reads your folder before adding a series, downloads each chapter from one site, moves to the next working site when one fails, and skips a site that is down. If the copy cannot be downloaded, the original Rensaiō is used.
2. Older Kaizoku 2.0 installs are upgraded on the same folders.

## Beszel login

1. Beszel's admin now uses the same name and password as the rest of the setup (an email if that is what you typed, otherwise your name at beszel.local), not a separate odd one.

## Manga

1. New extras/Kaizoku smart add: adds a manga from the best source and only for chapters you do not have, with the other sources as back-ups, and refuses to guess when the folder is nearly empty.

## Monitoring

1. New optional app, Beszel: processor, memory, drives and temperature, with a tile on Homepage. The setup adds this server to it and creates the alerts, so nothing is connected by hand.
2. It follows the hardware: memory and core caps by machine size, one watch per media drive on Linux, and a temperature alert 8 degrees under the chip's own limit, only if the machine reports a temperature.
3. Alerts only ring for real trouble: a number must stay bad for 10 minutes.
4. New extras/Monitoring/thermal-guard.sh: lowers CPU power and speed when it runs hot, with its levels worked out from the chip's own limit. Includes an installer.
5. New guide, docs/Monitoring and temperatures.md, with a cooling checklist. tools/test_monitoring.py covers it.

## Dashboard and subtitles

1. The Homepage dashboard is much richer: a glass look on a dark gradient, server CPU, memory, uptime and disk at the top, a search box and a clock, and live CPU and memory on every app tile (read-only Docker access).
2. docs/Best settings.md explains how to make subtitles show up and stay in time, what to expect from Jellyfin on a TV, and why Nginx Proxy Manager is not needed at home.

## Tour video

1. New 90 second tour video on the home page, in 1080p: a real pointer that moves like a hand, camera zooms that only happen where there is something to see, and short captions. A highlight of it is the picture at the top of the README.
2. The video is made from the demo by two scripts in tools/tour, so it can be made again whenever the setup page changes.

## Best settings

1. Every app's log is now limited to three files of 50 MB, so a noisy app cannot fill a drive.
2. New guide, docs/Best settings.md: container, drive, kernel, Docker, SSH and backup settings taken from a Proxmox host and LXC in daily use.
3. docs/Other hardware.md and docs/FAQ.md, a demo GIF and a social preview picture, badges, and the original Kapowarr on ARM machines.

## Demo website

1. New website, built by tools/build_site.py into the folder site and ready for Cloudflare (wrangler.jsonc). The home page shows the install command with a copy button, what gets installed, and pictures. The demo at /demo/ is the real setup page and guide with pretend answers, so anyone can click through every screen without installing anything. See docs/Demo website.md.
2. The setup page now fits phones: no sideways scrolling, a step bar that scrolls and shows the current step, and controls that wrap.
3. Fixed: the install progress list now uses the same step names as the server, so the bar moves as each app is set up. A step for Kapowarr was added to it.

## Drives and comics

1. The folder picker now always lists this computer's own (internal) drive first, on Windows, Mac and Linux, so the media can live on it. Before, a Mac with no external drive showed "No drives found". More Linux places are searched too. If the list cannot be read, the picker now says so. A new test, tools/test_drives.py, covers all three systems.
2. Every screenshot in the guide was taken again at 3200 pixels wide, with the new Kapowarr and Kaizoku tiles and the drive list.
3. start.sh can show another address or home folder with ARR_ADDRESS and ARR_HOME, which is how clean screenshots are made.
4. Kapowarr is comics only. The manga code was removed from Hikki-dev's copy and it no longer gets a manga folder; Kaizoku does manga.

## Easier install

1. New one-line installer, install.sh, for Linux, Mac, a Proxmox LXC or any server. It downloads the project and starts the setup.
2. The start windows are tidier: five numbered steps with a spinner and a tick, clear messages if something fails, and the address to open at the end.
3. Headless mode: on a machine with no screen (or with --headless) no browser is opened, and the address to use from another computer is shown.
4. New guide, docs/Installing.md, with a picture of every start window.

## Comics and manga

1. Mylar3 is replaced by Kapowarr, using Hikki-dev's own copy. It is for comics only; manga is Kaizoku's job, so the manga code was removed from the copy. The setup links it to FlareSolverr, Prowlarr and qBittorrent, adds the comics folder, and uses the main login. Only a free ComicVine key is left for you.
2. New optional app: Kaizoku (Kaizoku.NET), for following manga and downloading new chapters. One container, no database, on port 9833.
3. Running the setup again turns Kapowarr on for anyone who had Mylar3.
4. New guide, docs/Comics and manga.md, and new Homepage tiles.

## Light mode

1. The setup page and the guide now start in a soft light theme with warm paper colours, and a link switches to the original dark theme. The choice is remembered in the browser.
2. All screenshots in the docs were taken again at 1600 pixels wide, so small text can be read. The diagram has bigger text and logos.

## Portainer and the diagram

1. New guide page, docs/Portainer.md: keeping the apps in stacks, what an update really does, and the mistakes that leave apps stopped.
2. The picture of how the apps fit together now uses the real app logos and the standard ports. It is drawn by tools/build_diagram.py.
3. Private HTTPS: how to keep your own list of ports.

## Guide and private HTTPS addresses

1. New guide on the website, shown from the setup page. It reads the pages in the docs folder, so the website and GitHub show the same text. It has screenshots of every step and a picture of how the apps work together.
2. New optional tile: private HTTPS addresses with Tailscale for every app, and Homepage links changed to match. The tool also works on its own for any Docker containers, never removes an address, and remembers each one.
3. The setup image is now built from the top folder, so the guide travels inside it.
4. File sharing, the standalone script, and tests for both.

## File sharing

1. New optional step: share your media folder and your other drives on your home network (Samba). One login, no guest access, only home networks and Tailscale may connect.
2. Works from the setup page on Linux, or with the script in extras/File sharing for a computer that does not run the setup.
3. New guide, docs/File sharing.md: how to prepare drives (formats, mounting, hard links), how to connect from every device, how to use it away from home with Tailscale, and how to fix common problems.
4. New test, tools/test_sharing.py, that runs with the other checks.
5. Fixed: sound missing on some YouTube live channels.

## First release

1. One page in the browser that installs and links Jellyfin, Seerr, Sonarr, Radarr, Prowlarr, qBittorrent, Bazarr and Homepage.
2. Quality choices per language, size limits, English subtitles, and no uploading after a download.
3. Apps you already have: the setup finds them, lets you keep using them, and shows every change before it happens, with a switch to keep yours.
4. Optional live TV and sports channels for Jellyfin, with daily checks, TV guides, live YouTube news channels and NordVPN support.
5. Jellyfin tuned for every device, notifications to your chat app, and tests of every link at the end.
