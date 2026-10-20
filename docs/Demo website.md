# Demo website

The website has two parts, both plain static files hosted for free on Cloudflare:

1. **The home page** (`/`). It shows the install command with a copy button, what the setup installs, pictures, and how it goes. It works on phones, tablets and computers.
2. **The demo** (`/demo/`). It is the real setup page and guide, with the server replaced by pretend answers, so it looks and works the same. The guide is at `/demo/guide`.

Nothing in the demo installs or saves anything. A bar at the top says so, and links to this project on GitHub.

The live site is at https://media-server-setup.makkoacknowledgesstress.workers.dev.

## The tour video

The home page has a 90 second video of the setup page: a pointer that moves like a hand, zooms only where there is something to look at, and short captions. It is made from the demo, so it can be made again whenever the setup page changes:

```bash
python3 tools/build_site.py && (cd site && python3 -m http.server 8765) &
cd tools/tour && npm install && cd ../..
node tools/tour/capture.mjs tour-work
python3 tools/tour/compose.py tour-work landing/media/tour.mp4
```

The steps are in `tools/tour/README.md`. The README picture is a shorter highlight cut from the same video.

## What you can do in the demo

1. Go through every setup screen, including the folder picker with pretend drives.
2. Press **Install everything** and watch a pretend install of about 40 seconds.
3. See the finished page with logins and links, and search for a title under **Find a title**.
4. Read the whole guide.

## Build it on your computer

```bash
python3 tools/build_site.py
```

This makes the folder `site`. To look at it, run `python3 -m http.server 8000 --directory site` and open `http://localhost:8000`.

The home page files are in `landing`. Change the install command in `landing/index.html` (and in the README) if the project moves.

The pretend answers are in `demo/demo.js`. The pretend computer details (Docker version, apps found, live TV channels) are in `demo/fixtures`.

## Put it on Cloudflare (free)

The easy way: let Cloudflare build it from GitHub every time you push.

1. Sign in at dash.cloudflare.com and open **Workers & Pages**.
2. Press **Create**, choose **Import a repository**, and pick `media-server-setup`.
3. Set the build command to `python3 tools/build_site.py`.
4. Set the deploy command to `npx wrangler deploy`. The file `wrangler.jsonc` already says which folder to serve.
5. Press **Save and deploy**. Cloudflare gives you an address like `media-server-setup.your-name.workers.dev`.

Every push to the main branch updates the demo by itself.

The other way, from your computer, once:

```bash
npx wrangler login
python3 tools/build_site.py
npx wrangler deploy
```

For your own web address, open the project in Cloudflare, then **Settings**, **Domains and routes**.

## Keeping it up to date

The demo uses the real files in `wizard/app/static` and the pages in `docs`, so it changes when they change. The pretend install steps in `demo/demo.js` must match the real ones. If you add a step to the setup, add it there too.
