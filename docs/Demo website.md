# Demo website

A demo lets anyone click through the setup page and the guide without installing anything. It is the real page, with the server replaced by pretend answers, so it looks and works the same. It is hosted for free on Cloudflare.

Nothing in the demo installs or saves anything. A bar at the top says so, and links to this project on GitHub.

## What you can do in the demo

1. Go through every setup screen, including the folder picker with pretend drives.
2. Press **Install everything** and watch a pretend install of about 40 seconds.
3. See the finished page with logins and links, and search for a title under **Find a title**.
4. Read the whole guide.

## Build it on your computer

```bash
python3 tools/build_demo.py
```

This makes the folder `site`. To look at it, run `python3 -m http.server 8000 --directory site` and open `http://localhost:8000`.

The pretend answers are in `demo/demo.js`. The pretend computer details (Docker version, apps found, live TV channels) are in `demo/fixtures`.

## Put it on Cloudflare (free)

The easy way: let Cloudflare build it from GitHub every time you push.

1. Sign in at dash.cloudflare.com and open **Workers & Pages**.
2. Press **Create**, choose **Import a repository**, and pick `media-server-setup`.
3. Set the build command to `python3 tools/build_demo.py`.
4. Set the deploy command to `npx wrangler deploy`. The file `wrangler.jsonc` already says which folder to serve.
5. Press **Save and deploy**. Cloudflare gives you an address like `media-server-setup-demo.your-name.workers.dev`.

Every push to the main branch updates the demo by itself.

The other way, from your computer, once:

```bash
npx wrangler login
python3 tools/build_demo.py
npx wrangler deploy
```

For your own web address, open the project in Cloudflare, then **Settings**, **Domains and routes**.

## Keeping it up to date

The demo uses the real files in `wizard/app/static` and the pages in `docs`, so it changes when they change. The pretend install steps in `demo/demo.js` must match the real ones. If you add a step to the setup, add it there too.
