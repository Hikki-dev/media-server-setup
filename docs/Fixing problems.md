# Fixing problems

## Find a title says nothing matched

Open the title in Find a title and press Add and check. It tells you why.

| What it says | What it means | What to do |
|---|---|---|
| Found some, some match | It works, and the best one downloads by itself | Nothing |
| Too big | Every version is bigger than your size limit | Raise the limit in Quality choices, or press Download anyway on one |
| Quality not allowed | Only a lower or higher quality exists | Allow 720p for that choice, or press Download anyway |
| Language | The versions are in a different language | Press Download anyway if one looks right |
| No English subtitles mentioned | Your choice only accepts downloads that already have English subtitles | Turn off the strict subtitle option. Bazarr still finds subtitles |
| No sources | Nobody is sharing it | Lower the minimum number of sources, or wait |
| Nothing at all | No search site has it, or it is very new | Try another name, and check the search sites are green in Prowlarr |
| Not released yet | It will download after release | Nothing |

## Tamil and Malayalam sites say searching

Those websites change address often. Open Apps and links and press Find the address next to the site. If it still cannot be reached, BT4G finds most of the same downloads.

## Subtitles are not found

Open Bazarr and check that your library folders are listed. If you added or moved a folder after the setup, start the setup again so they are updated.

## Live TV: channels missing or not playing

1. Open the Live TV tab and press Add to Jellyfin. This rebuilds the list and refreshes the guide.
2. Some channels only play in their own country. Broken ones are removed at the next daily check.
3. A channel without a guide still plays.
4. Paid sports are not on free lists. Add your provider under Your own provider.
5. Right after setup, Jellyfin can take a few minutes to show the channels.
6. YouTube channels only play while the TV station is live. At other times you see a message that it is not live right now.

## A title only comes in the wrong quality

Each quality choice has a setting for TV shows and one for movies. Choices that say "only" never use another quality. If a title only exists in another quality, pick the "or" option, for example "4K, or 1080p if needed", or press Download anyway.

## No message arrives

Open the Notifications tab and press Save and send a test message. If it fails, it shows the reason. Usually the link, token or chat is wrong. Telegram needs you to send your bot one message first.

## Jellyfin stutters on one device

In Jellyfin, open Dashboard, then Playback, to see if it converted the video. Windows and Mac cannot use the graphics chip inside Docker, so the processor does the work. Choose files the device can play directly, like H.264.

## Docker

1. Docker is not reachable: start Docker Desktop and wait until it says it is running. Windows needs WSL2.
2. A drive is not shared on Windows: in Docker Desktop open Settings, then Resources, then File sharing, and add the drive.
3. A port is already used: the setup picks a free one. The last page shows the real ones.
4. Slow first start: the first time it downloads several GB. If Docker has less than 4 GB of memory it is slow. Give Docker more memory.

## Search sites are red in Prowlarr

Free websites go down or change address. In Prowlarr, test them and delete the dead ones, then start the setup again to add working ones. Sites that need the helper for protected websites only work while that helper is running.

## A login does not work

The last page lists every login, and each one was tested. Press Show to read the password exactly. qBittorrent has its own login. If qBittorrent says banned after too many wrong tries, restart qBittorrent in Docker Desktop.

## Disk space doubled

Downloads and your library need to be on the same drive to be linked. On different drives, files are copied and then the download is removed. The Storage page shows which folders link and which copy.

## Start again

Press Stop in the setup, then Clean up and start over. Your media folders are never touched. Delete the setup folder in your home folder only if you want to throw away all settings.

## Where to look when something breaks

Open Docker Desktop, find the app in the list, and open its Logs tab. Ask Claude to read it with you.

## Using apps you already have

1. Could not connect. For qBittorrent, check the username and password. A few wrong tries make qBittorrent block this computer for an hour. Wait, or restart qBittorrent. For Jellyfin, make an access key in Dashboard, then API Keys. For the other apps the key is found by itself. If it cannot be found, copy it from the app under Settings, then General.
2. My app runs on the host network or behind a VPN container. That works. The setup reaches it through the shared network. Make sure the app listens on every address, and that a firewall lets the apps reach its port.
3. The last page says needs attention for my own apps. The final checks only report on your own apps. They never change a setting you chose to keep. A link you kept may simply be different from what the setup would have made.
4. I want to undo a change. The setup never deletes your data. Start it again and switch that part to Keep mine, or set it back in the app. The What changes list shows what was there before.
