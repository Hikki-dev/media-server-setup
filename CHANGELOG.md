# Changes

## Demo website

1. New demo website: the real setup page and guide with pretend answers, so anyone can click through every screen without installing anything. Built by tools/build_demo.py into the folder site, ready for Cloudflare (wrangler.jsonc). See docs/Demo website.md.
2. Fixed: the install progress list now uses the same step names as the server, so the bar moves as each app is set up. A step for Kapowarr was added to it.

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
2. New optional app: Kaizoku, for following manga and downloading new chapters. It comes with its own private database and cache.
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
