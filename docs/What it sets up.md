# What the setup does for you

## The apps

| App | What it does |
|---|---|
| Jellyfin | Where you watch your movies and shows |
| Seerr | A page where family and friends ask for something to watch |
| Sonarr | Finds and downloads TV shows and anime |
| Radarr | Finds and downloads movies |
| Prowlarr | Keeps the list of websites that Sonarr and Radarr search |
| qBittorrent | Does the downloading |
| Bazarr | Finds subtitles |
| Helper for protected websites | Opens search sites that make you prove you are not a robot |
| Homepage | One page with a button for every app |

You can also add a YouTube downloader, a comic reader, a comic downloader and a disk health checker. If a port is already used on your computer, the setup picks a free one for you.

## Where your files go

You can use one drive or many. The setup shows how much space each folder has, and it never moves or renames files you already have.

One drive: you choose one folder, and the setup makes the other folders inside it.

Several drives: you choose a downloads folder and as many Movies, TV Shows and Anime folders as you like. New titles go to the folder with the most free space.

Files on the same drive as your downloads are linked, so they use no extra space and appear at once. Files on another drive are copied, then the download is removed.

## Downloads

qBittorrent is set so nothing keeps uploading after a download. Finished downloads are removed once the file is in your library. It also finds extra sources so rare titles download faster, and it blocks program files (like .exe) so nothing harmful can come in. Downloads at the same time, speed limits and the login are chosen in the Downloads step.

## Quality choices

A quality choice tells the apps what picture quality you want, how big a file can be, and whether English subtitles are needed. You can have as many as you like. For example: anime in 1080p only, English TV in 720p only, English movies in 4K only.

The picture quality is chosen separately for TV shows and for movies. The options are 4K only, 4K or 1080p, 1080p only, 1080p or 720p, and 720p only. The word "only" means nothing else is ever downloaded, even if it is the only copy.

Size limits are per file. The starting limits are 6 GB for a 4K episode and 25 GB for a 4K movie, 800 MB and 5 GB for 1080p, and 400 MB and 2.5 GB for 720p.

Quality rules come from a well known community guide, so poor quality and fake releases are turned down. Requests for another language go to the right quality choice by themselves.

## Subtitles

Bazarr is linked to Sonarr, Radarr and Jellyfin. English is always wanted and it keeps searching until it finds one. You can add more languages. It uses free subtitle websites that need no account. Adding free accounts on OpenSubtitles, SubDL or SubSource gives better results. For anime you can also add your own free AniDB client to improve matching. Everything works without it.

## Jellyfin for every device

After your libraries are made, Jellyfin is tuned so almost any TV, phone, computer or streaming stick plays smoothly.

1. If your computer has a graphics chip that works, it is used to convert video quickly. The setup tests it first.
2. HDR video is changed so colours look right on normal screens.
3. Your home network is recognised, so nothing is limited at home.
4. Subtitles only show when the voices are not in your language. The next episode plays by itself.
5. Slow background jobs nobody notices are switched off.

## Live TV and sports

This step is optional. It adds a Live TV section to Jellyfin.

Channels come from free public lists. You choose countries, kinds of channel and languages. You can add free sports channels from anywhere, and live channels on YouTube. For Sri Lanka these are Ada Derana News, TV Derana, News 1st (Sinhala and English), News 1st Tamil, Sirasa, TV1, ITN and Swarnavahini. They only play while they are live, and the TV guide shows the usual news times.

Every channel is tested and broken ones are left out. The list is checked again every day. Channels you pick as local come first and are saved as favourites for everyone.

Paid sports like the Premier League, La Liga and the Champions League are not on free lists, so they are not included. If you pay a TV provider, paste their channel list and guide links under Your own provider.

Some channels only work in their own country. With NordVPN you can try them through the UK and the US. See the file Live TV and VPN.

## File sharing

Optional. If you switch it on, a small Samba program shares the folders and drives you pick. Everyone uses one login. See File sharing.md for how to connect and how to set up your drives.

## Private HTTPS addresses

Optional. With Tailscale on the server, each app gets a safe address that works from your own devices anywhere. See Private HTTPS.md.

## Search sites

The setup adds popular free search sites for movies, TV and anime, tests each one, and removes the ones that do not answer. Websites for Tamil and Malayalam titles change address often, so a small helper finds the current address by itself.

## Links between the apps

When the install ends, every link between the apps is tested, fixed once if it failed, and listed on the last page. You can test again any time under Apps and links. If an app stops answering, it is restarted for you.

## Logins

One main login is used for Jellyfin, Seerr, Sonarr, Radarr, Prowlarr and Bazarr. qBittorrent has its own. At the end the setup signs in to every app to prove each login works, and shows them with Show and Copy buttons.

## Already have some of these apps?

You do not have to start again. The Your apps step lists the apps already on your computer. For each one you choose to use yours, or install a new one beside it. Then the What changes step shows every setting the setup wants to change, next to how it is set today, with a switch to keep yours. Nothing is changed until you say so.

These are kept exactly as they are unless you switch them: your links between apps, logins, request rules, recycle bin, folder names, qBittorrent download folders, search sites you added, and your Jellyfin server name.

## Running the setup again

It is safe. It updates what it made and keeps your data.
