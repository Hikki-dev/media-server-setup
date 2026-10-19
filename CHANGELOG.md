# Changes

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
