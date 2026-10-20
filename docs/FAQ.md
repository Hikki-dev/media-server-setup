# Questions and answers

## About the project

### Is it free?

Yes. The setup is free and open source under the MIT licence, and so is every app it installs. Some optional extras, such as a VPN or a paid subtitle account, are your own choice and have their own prices.

### Is it legal?

The setup only installs and connects ordinary programs on your own computer, and it hosts no media. What you download and watch is your own responsibility, and the rules depend on where you live. Use it only for content you have the right to. The short notice is in the README under [Legal and responsibility](../README.md#legal-and-responsibility).

### Does it send my data anywhere?

No. There is no tracking and nothing is sent to the people who make this project. Everything runs on your own computer. It does reach the internet to download the apps, to search the sites you choose, and to fetch public lists such as channel lists and subtitles.

### Is the demo a real install?

No. The demo is the real setup page with pretend answers, so you can look around. Nothing is installed or saved.

## Getting started

### What do I need?

A computer that can run Docker, about 8 GB of memory and 20 GB of free space for the apps, and an internet connection. Your media needs its own space. See [Other hardware](Other%20hardware.md) for a Proxmox LXC, a Raspberry Pi, a Synology and Unraid.

### Why Docker?

Each app runs in its own box, so nothing is installed by hand, nothing clashes, and updating or removing an app is one command.

### Can I use it on my phone?

The setup page fits phones, so you can look at it or answer the questions from a phone. The setup itself still runs on the computer or server that has Docker. To watch, use the Jellyfin app on your phone, TV or computer.

### Can I keep the apps I already run?

Yes. The **Your apps** step finds them. For each one you choose to keep yours or install a new one beside it. Nothing is changed until you approve it on the **What changes** page.

### Which ports do the apps use?

The standard ones: Jellyfin 8096, Seerr 5055, Sonarr 8989, Radarr 7878, Prowlarr 9696, qBittorrent 8080, Bazarr 6767, Homepage 3000, Kapowarr 5656, Komga 25600 and Kaizoku 9833. If a port is already used on your computer, the setup picks a free one for you and shows it at the end.

## Using it

### Where are my settings kept?

In the `ArrStack` folder, in your home folder by default. Each app has its own folder inside `config`. The file `docker-compose.yml` lists every app. The passwords you chose are in a private file that only you can read. Back this folder up and you can rebuild everything.

### I forgot a login. Where is it?

Open the setup page again (use the same start file as before) and look under **Apps and links**. The logins the setup made are listed there.

### How do I update the apps?

Run the setup again. It is safe: it updates what it made and keeps your data. Or, from the `ArrStack` folder:

```bash
docker compose pull
docker compose up -d
```

### How do I remove everything?

From the `ArrStack` folder:

```bash
docker compose down
```

That stops and removes the apps. Delete the `ArrStack` folder to remove their settings too. Your media folders are never touched. To remove the setup page itself, run `docker rm -f arr-wizard`.

### Is running the setup again safe?

Yes. See [What it sets up](What%20it%20sets%20up.md#running-the-setup-again).

### Does it have a VPN for downloads?

Not built in yet. A VPN is only offered for Live TV channels that work in one country (NordVPN). For downloads, use a VPN on your router or computer.

### Why did the setup say it used the original Kapowarr?

The maintainer's own copy of Kapowarr is on GitHub's package list, and it cannot be downloaded on some machines, such as a Raspberry Pi (it is built for Intel and AMD only) or while its package is private. The setup then uses the original Kapowarr. Comics work the same, without the copy's extra fixes. See [Comics and manga](Comics%20and%20manga.md).

## Problems

### Something does not work. Where do I start?

[Fixing problems](Fixing%20problems.md) lists the usual causes. If your problem is not there, [open an issue](https://github.com/Hikki-dev/media-server-setup/issues/new/choose) and say what you saw and which computer you use.

### Can I help?

Yes. Fixes, ideas and reports from other hardware are welcome. Read [CONTRIBUTING.md](../CONTRIBUTING.md) first.
