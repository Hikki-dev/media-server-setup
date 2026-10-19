# Comics and manga

This is optional. Switch on **Kapowarr** for comics and **Kaizoku** for manga on the Apps step. Each one has its own job, and both save into folders that Komga (the reader) can open.

## What each app does

| App | What it does for you | Where you open it |
|---|---|---|
| Kapowarr | Finds and downloads **comics** and keeps them tidy. It does not do manga | Port 5656 |
| Kaizoku | Follows **manga** series and downloads new chapters by itself | Port 3001 |
| FlareSolverr | Helps Kapowarr open comic websites that check for robots | Never, it works quietly |
| Komga | The reader. Open it on any device to read what was downloaded | Port 25600 |

## Kapowarr

The setup uses a personal copy of Kapowarr, [Hikki-dev/Kapowarr](https://github.com/Hikki-dev/Kapowarr), in place of Mylar. It is the original Kapowarr plus these fixes:

1. New releases found every 15 minutes from the GetComics feed and from Prowlarr.
2. A **Search All** that no longer freezes or stops when one title fails.
3. Prowlarr torrent links become magnet links, so they are no longer rejected.
4. Programs and scripts hidden in a download are blocked.
5. Older databases start without errors.

Its manga search is switched off by the setup, because Kaizoku does manga.

When the install finishes, the setup has already done this inside Kapowarr:

1. FlareSolverr is linked, so comic websites open.
2. Prowlarr is linked, so torrent search works too.
3. qBittorrent is added as a download client.
4. `/comics` is added as the root folder.
5. The admin login is the same as the other apps.

You do one thing yourself: paste a **ComicVine key**. It is free at comicvine.gamespot.com/api. Paste it on the Apps step, or later in Kapowarr under Settings. Without it Kapowarr cannot look up comics.

Then add a volume (a comic series), choose the root folder, and press **Search Monitored**.

## Kaizoku

Kaizoku follows a manga series and downloads each new chapter. It runs with its own small database and cache, both private to your stack.

1. Open Kaizoku, press **Search**, and type a manga name.
2. Pick the source and add it. Chapters download into `books/manga`.
3. Komga picks them up on its next scan.

The Kaizoku project is archived. It still works, but it will not get updates.

## Where the files go

Both apps write inside the media folder you chose, in the `books` folder:

| Folder | Used by |
|---|---|
| `books/comics` | Kapowarr |
| `books/manga` | Kaizoku |

In Komga, add the library `books` (or each folder on its own) once.

## Moving from Mylar

Mylar is gone. If you switched it on before, running the setup again turns on Kapowarr in its place and leaves your old `config/mylar3` folder alone. Your comic files stay where they are.

## If something does not work

| What you see | Reason | What to do |
|---|---|---|
| Kapowarr cannot find any comic | No ComicVine key | Paste the key in Kapowarr, Settings |
| The Kapowarr image will not download | The package is private | Make it public on GitHub, or sign in with `docker login ghcr.io` on the server |
| A comic site does not open | FlareSolverr is not running | Restart FlareSolverr, then try again |
| Kaizoku shows an error on first start | Its database was still starting | Wait a minute and refresh |
| Komga shows nothing | It has not scanned yet | Press Scan library in Komga |
