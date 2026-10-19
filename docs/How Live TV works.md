# How Live TV works

This page follows the Live TV list from the free sources to the screen. It also explains the TV guide, YouTube channels, and the safeguards that keep the server calm. The VPN side has its own page: [Live TV and VPN](Live%20TV%20and%20VPN.md).

## The daily update

Once a day, at night, the setup rebuilds your channel list. Nothing is done by hand.

[![The daily channel update in six steps: collect, check, try the VPN, match guides, write files, Jellyfin refreshes](images/livetv-daily.svg)](images/livetv-daily.svg)

1. **Collect.** It reads the free public channel lists from the iptv-org project for the countries and kinds of channel you chose.
2. **Check.** Every channel is tested. The setup asks for the playlist and then for a real piece of video, so a channel that answers but shows nothing is dropped. The check runs gently and slows down by itself when the server is busy.
3. **Try the VPN.** Channels that refuse with a "not allowed" answer are tried through the UK and US connections. See [Live TV and VPN](Live%20TV%20and%20VPN.md).
4. **Match guides.** Working channels are matched with a TV guide, explained below.
5. **Write files.** Two files are written for Jellyfin: a channel list and a guide.
6. **Jellyfin refreshes.** Jellyfin reads the two files on its own schedule.

## Channel numbers

Local channels, such as Sri Lankan channels when you pick Sri Lanka, get the numbers 1 to 99. Every other channel starts at 101.

## The TV guide

The guide tells Jellyfin what is on now and next. It comes from free public sources: the EPG Share site for many countries, and the free guides published for Pluto TV, Samsung TV Plus and Plex.

A channel is matched with a guide only inside its own country. The setup compares the channel id and its name. It ignores small differences such as HD, East or West, a country name in brackets, and the word Television against TV. A channel whose name could mean two different things is left without a guide, because a wrong guide is worse than none.

Some channels have no public guide anywhere. Local community channels are the most common case. They play fine and simply show no programme list.

Channels that publish only a news bulletin time, such as some Sri Lankan YouTube channels, get a small schedule written by the setup itself.

## YouTube channels

YouTube changes its live addresses all the time, so they cannot be saved in a list. When you open a YouTube channel, Regional asks a free tool called yt-dlp for the current address and keeps it for five minutes. It looks them up again every few minutes in the background, so the next start is quick.

YouTube sends picture and sound separately. The relay joins them into one stream without changing the quality, and it only runs while someone is watching. It stops by itself three minutes after the last viewer leaves. If a channel is not live, a short "off air" picture is shown instead of an error.

## Keeping the server calm

Live TV is built so it never takes over your server.

- The nightly work runs with a low priority, and the stream check slows down when the server is busy.
- A small watcher runs every two minutes. It stops a stuck helper program that has been running too long, and restarts a VPN connection that reports itself unhealthy. It never touches Jellyfin itself.
- The relay for broken channels, described in [Smoother channels](../extras/Smoother%20channels/Read%20me.md), only starts when someone opens the channel.

## Do you need TVHeadend or WebGrab+?

No. Both were tested, and neither makes this setup better.

- **TVHeadend** is a TV recorder and tuner server. It shines when you have a TV aerial or satellite card. A server like this one has no tuner, and the channels here are internet streams in a different format that TVHeadend cannot read directly. Making it work would need an extra helper program for every channel, and one more thing that can fail, for no new feature that you can use.
- **WebGrab+** collects guides by reading TV websites, with site files that break whenever a site changes. The free public guides listed above already cover the same ground without that upkeep.

A better guide match, described above, gave more channels a guide without adding anything new to run. If you later want a guide for a channel that no public source covers, the iptv-org project also publishes free guide grabbers, and that is the first thing to try.
