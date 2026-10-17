# How it works

This page is for people who want to read or change the code.

## The big picture

The start files build a small Docker image from the wizard folder and run it. That image runs a tiny web server on port 7979 and serves the page you see. The server talks to Docker on your computer and to each app through its own web address.

The server never changes the apps by itself. Every change goes through one install flow, and every change to an app you already have goes through a preview first.

## The folders

1. wizard/app: the program.
2. wizard/app/static: the page in the browser (app.js and style.css).
3. wizard/presets: the quality rules from the TRaSH Guides, made by tools/build_trash_presets.py.
4. docs: the written help.
5. extras: optional tools for people who run their own server.
6. tools: the start script, the checks and the quality rule builder.

## The program, file by file

1. server.py: the web server and the install flow. It runs the steps in order and keeps the log.
2. configure.py: one function per app. Each reads what is there, changes what is needed, and can safely run again.
3. stack.py: makes the Docker compose file, plans the drives and prepares folders.
4. arrapi.py: a small web client used for every app. It also holds the Recorder (see below).
5. adopt.py: finds apps you already run, reads their keys, links them to the shared network and runs the preview.
6. audit.py: the list of settings groups and the plain English text for each one, and the code that turns captured changes into rows a person can read.
7. livetv.py: builds the channel list, TV guides and favourites.
8. bridge.py: the helper service. It finds working addresses for Tamil and Malayalam sources, finds live YouTube streams, shows a message when a channel is off air, and updates the channel list every day.
9. jellyfin_tune.py: the Jellyfin settings for smooth playback on every device.
10. viaproxy.py: sends a channel through a VPN connection when it only works in some countries.

## How apps you already have are kept safe

Every setup step is written as a small block that reads an app, changes a copy and saves it. Each block is wrapped in a settings group, like sonarr.naming. Two modes use the same code:

1. Preview: the Recorder lets every read through and captures every write instead of sending it. Nothing is changed. The captured writes are turned into rows (how it is now, how it would be) for the What changes page.
2. Apply: the Recorder lets writes through, except for groups the person switched off.

Because both modes run the same code, the preview can never promise something the setup would not do.

Rules we keep: a connection that already exists is left alone, folders from the setup are never added to a person's own app by default, and logins are never changed by default.

## Live TV

livetv.py builds the list from free public lists and tests every channel. The result is a channel list file and TV guide files that Jellyfin reads. bridge.py runs every day to update them. Some channels need help. The tools in extras handle two cases: a channel whose picture is broken, and a YouTube channel whose sound is kept apart from its picture.

## Adding a new group of settings

1. Wrap the code in with grp("app.name").
2. Add the group to audit.py with a plain title, a plain reason, whether it starts on, and a warning if it is risky.
3. Run the preview against a throwaway app and read the page. If a sentence needs a technical word, rewrite it.
