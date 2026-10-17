# Smoother channels

For people who run their own server and are comfortable with a terminal. Most people do not need this.

## Fixing a channel that shows a broken picture

Some channels play sound but show a broken or empty picture in Jellyfin. This is because the channel does not send what Jellyfin needs at the start. The file livetv_sidecar.py fixes it by making a clean copy of the channel, only while someone is watching.

How to use it:

1. In your Live TV choices, add the channel name under reencode.
2. Run livetv_sidecar.py once a minute on your server.
3. Open the channel in Jellyfin. The first time takes about ten seconds longer, because the clean copy has to start. Three minutes after the last person stops watching, it stops by itself.

If your computer has an Intel graphics chip, it is used, so the processor stays calm. Otherwise the processor does the work.

## Fixing a channel that has no sound

YouTube keeps the sound and the picture of a live channel apart. Jellyfin then plays the picture with no sound. The same file joins them into one stream without changing the quality, only while someone is watching. The setup turns this on for every YouTube channel by itself. Set remuxYoutube to false in the Live TV choices to turn it off.

## Keeping the server calm

The file jf_reaper.py stops things that were left running by mistake, like a channel check that never finished or a live channel nobody is watching. Run it every 2 minutes. It also restarts a NordVPN connection that gets stuck.

Tips for a small server:

1. Run the nightly channel list update at the lowest priority.
2. Limit heavy apps, for example the helper for protected websites, so they cannot use the whole processor.
3. The channel list builder remembers channels that worked in the last 30 hours, so a busy server does not make it throw good channels away.
