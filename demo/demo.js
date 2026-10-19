/* Demo mode: the real setup page, with the server replaced by canned answers.
   It lets anyone click through every screen without installing anything. Nothing is sent anywhere, nothing is saved.
   Built into the static site by tools/build_demo.py. */
(() => {
  const real = window.fetch.bind(window);
  const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json" } });
  const GB = 1e9;
  const HOME = "/home/you";
  const FOLDERS = {                       // a small pretend computer
    "/home/you": ["Documents", "Downloads", "Music", "Pictures", "Videos"],
    "/mnt/Media": ["Movies", "TV Shows", "Anime", "Comics"],
    "/mnt/Backup": ["Photos", "Documents"],
  };
  const DRIVES = [
    { name: "This computer", path: HOME, internal: true, freeBytes: 620 * GB, totalBytes: 1000 * GB },
    { name: "Media", path: "/mnt/Media", freeBytes: 3400 * GB, totalBytes: 8000 * GB },
    { name: "Backup", path: "/mnt/Backup", freeBytes: 900 * GB, totalBytes: 2000 * GB },
  ];
  const created = new Set();
  const driveOf = p => DRIVES.find(d => p === d.path || p.startsWith(d.path + "/")) || DRIVES[0];
  const segs = p => p.split("/").filter(Boolean);
  const norm = p => ("/" + segs(p || HOME).join("/"));
  const parentOf = p => { const s = segs(p); return s.length > 1 ? "/" + s.slice(0, -1).join("/") : null; };
  const kids = p => [...(FOLDERS[p] || []), ...[...created].filter(c => parentOf(c) === p).map(c => segs(c).pop())];
  const info = p => {
    const d = driveOf(p), dirs = kids(p);
    return { ok: true, path: p, writable: true, items: dirs.length, dirs: dirs.map(name => ({ name, items: (FOLDERS[p + "/" + name] || []).length })),
             totalBytes: d.totalBytes, usedBytes: d.totalBytes - d.freeBytes, freeBytes: d.freeBytes, parent: parentOf(p), segments: segs(p) };
  };

  /* what the apps would see: the same rule the real setup uses, simplified */
  function plan(cfg) {
    const st = (cfg && cfg.storage) || {};
    const label = { movies: "Movies", tv: "TV Shows", anime: "Anime" };
    if (st.mode !== "multi") {
      const base = norm(st.base || HOME + "/ArrMedia");
      return { mounts: [{ host: base, container: "/data" }], downloads: "/data/torrents", downloadsHost: base + "/torrents", mode: "single",
               libs: ["movies", "tv", "anime"].map(t => ({ type: t, host: `${base}/media/${label[t]}`, path: `/data/media/${label[t]}`, linked: true })) };
    }
    const mounts = [], where = {};
    const mount = h => { if (!where[h]) { where[h] = "/mnt/g" + mounts.length; mounts.push({ host: h, container: where[h] }); } return where[h]; };
    const dl = norm(st.downloads || "/mnt/Media/torrents");
    const dlc = mount(dl);
    return { mounts, downloads: dlc, downloadsHost: dl, mode: "multi",
             libs: (st.libraries || []).filter(l => l.path).map(l => { const h = norm(l.path); const c = mount(h); return { type: l.type, host: h, path: c, linked: h === dl || driveOf(h) === driveOf(dl) }; }) };
  }

  /* a pretend install that plays out in about 40 seconds */
  const JOB = { start: 0, cfg: null };
  const STEPS = [
    ["Preparing folders", "Folders ready in /home/you/ArrMedia"],
    ["Writing your docker-compose file", "docker-compose.yml written"],
    ["Downloading and starting the apps (first time takes a few minutes)", "Pulling images... (demo: nothing is downloaded)"],
    ["Configuring qBittorrent (no seeding)", "qBittorrent: uploading off"],
    ["Configuring Sonarr and Radarr", "Quality choices, sizes and folders set"],
    ["Configuring Bazarr (subtitles)", "Subtitle languages set"],
    ["Configuring Kapowarr (comics)", "Kapowarr ready: comics in /comics, FlareSolverr, Prowlarr and qBittorrent linked"],
    ["Configuring Prowlarr (finding and testing indexers)", "Search sites added and tested"],
    ["Configuring Jellyfin", "Libraries and main account created"],
    ["Setting up Live TV and sports", "Channels tested and added"],
    ["Configuring Seerr (requests)", "Request page connected to Jellyfin"],
    ["Setting up notifications", "Notifications connected"],
    ["Checking every connection", "Every connection verified"],
    ["Checking every login", "Every login verified"],
    ["Testing a real search", "Test search found 41 releases for a sample film; 12 match your rules. Indexers are working."],
    ["Building your Homepage dashboard", "Homepage dashboard built"],
    ["All done", null],
  ];
  const STEP_MS = 2400;
  function result(cfg) {
    const sv = cfg.services || {}, p = cfg.ports || {};
    const link = (name, key) => ({ name, url: `http://media-server.local:${p[key] || DEFAULT_PORTS[key]}` });
    const links = [sv.homepage && link("homepage", "homepage"), sv.jellyfin && link("jellyfin", "jellyfin"), sv.seerr && link("seerr", "seerr"), link("sonarr", "sonarr"), link("radarr", "radarr"),
                   link("prowlarr", "prowlarr"), sv.bazarr && link("bazarr", "bazarr"), link("qbittorrent", "qbittorrent")].filter(Boolean);
    const user = (cfg.login && cfg.login.username) || "admin", pw = "demo-password";
    const cred = (app, key, note) => ({ app, url: `http://media-server.local:${p[key] || DEFAULT_PORTS[key]}`, user, password: pw, ok: true, note });
    const credentials = [cred("Sonarr", "sonarr", "Sign in with the admin login"), cred("Radarr", "radarr", "Sign in with the admin login"), cred("Prowlarr", "prowlarr", "Sign in with the admin login"),
      { app: "qBittorrent", url: `http://media-server.local:${p.qbittorrent || 8080}`, user: (cfg.qbit && cfg.qbit.username) || "qbit", password: pw, ok: true, note: "Its own login, set on the Downloads step" }];
    if (sv.jellyfin) credentials.push(cred("Jellyfin", "jellyfin", "Admin account"));
    if (sv.seerr) credentials.push(cred("Seerr", "seerr", "Sign in with your Jellyfin account"));
    if (sv.bazarr) credentials.push(cred("Bazarr", "bazarr", "Same admin login"));
    if (sv.kapowarr) credentials.push(cred("Kapowarr", "kapowarr", "Same admin login"));
    if (sv.komga) credentials.push({ app: "Komga", url: `http://media-server.local:${p.komga || 25600}`, user: "", password: "", ok: true, note: "Create the owner account on first visit" });
    if (sv.kaizoku) credentials.push({ app: "Kaizoku", url: `http://media-server.local:${p.kaizoku || 9833}`, user: "", password: "", ok: true, note: "Add your manga sources on first visit" });
    const integrations = [["Sonarr to qBittorrent", "Download client connected"], ["Radarr to qBittorrent", "Download client connected"], ["Prowlarr to Sonarr and Radarr", "Both apps are fed by Prowlarr"],
      ["Prowlarr to FlareSolverr", "Protected search sites open"], sv.bazarr && ["Bazarr to Sonarr and Radarr", "Subtitles follow new downloads"],
      sv.jellyfin && ["Jellyfin libraries", "Movies, TV Shows and Anime found"], sv.kapowarr && ["Kapowarr to FlareSolverr, Prowlarr and qBittorrent", "All three connected"]]
      .filter(Boolean).map(([name, detail]) => ({ name, ok: true, detail, fixed: false }));
    return { links, indexers: { working: ["1337x", "Nyaa", "EZTV", "YTS", "The Pirate Bay"], not_available: [] }, login: user, qbit: "qbit",
             smoke: { ok: true, msg: STEPS[14][1] }, credentials, integrations };
  }
  const DEFAULT_PORTS = { qbittorrent: 8080, sonarr: 8989, radarr: 7878, prowlarr: 9696, bazarr: 6767, jellyfin: 8096, seerr: 5055, flaresolverr: 8191, homepage: 3000, metube: 8081, komga: 25600, kapowarr: 5656, kaizoku: 9833, scrutiny: 8087 };
  function events(since) {
    const age = Date.now() - JOB.start;
    const all = [];
    STEPS.forEach(([name, line], i) => {
      if (age >= i * STEP_MS) all.push({ kind: "step", msg: name });
      if (line && age >= i * STEP_MS + 900) all.push({ kind: "info", msg: "  " + line });
    });
    const done = age >= (STEPS.length - 1) * STEP_MS + 600;
    return { events: all.slice(since), next: all.length, running: !done, done, error: null, result: done ? result(JOB.cfg || {}) : null };
  }

  const fixtures = {};
  const fixture = async name => fixtures[name] || (fixtures[name] = await (await real(`demo-data/${name}.json`)).json());

  async function api(path, query, method, body) {
    switch (path) {
      case "/api/env": return json(await fixture("env"));
      case "/api/state": return json({ installed: false, running: false, jobCfg: null, summary: null, cfgFull: null, cfg: null, containers: [] });
      case "/api/detect": return json(await fixture("detect"));
      case "/api/livetv/catalog": return json(await fixture("livetv-catalog"));
      case "/api/docs": return json(await fixture("docs"));
      case "/api/drives": return json({ drives: DRIVES.map(d => ({ ...d })), places: [{ name: "Home", path: HOME, freeBytes: 620 * GB, totalBytes: 1000 * GB }] });
      case "/api/browse": return json(info(norm(query.get("path"))));
      case "/api/pathcheck": { const p = norm(query.get("path")), d = driveOf(p); return json({ ok: true, exists: created.has(p) || !!FOLDERS[p], path: p, items: kids(p).length, dirs: [], writable: true, freeBytes: d.freeBytes, totalBytes: d.totalBytes, drive: d.path, error: null }); }
      case "/api/mkdir": { const p = norm(body.parent) + "/" + String(body.name || "New folder").replace(/[\\/:*?"<>|]/g, ""); created.add(p); return json({ ok: true, path: p }); }
      case "/api/plan": return json(plan(body));
      case "/api/install": JOB.start = Date.now(); JOB.cfg = body; return json({ ok: true });
      case "/api/events": return json(events(+query.get("since") || 0));
      case "/api/stop": JOB.start = 0; return json({ ok: true });
      case "/api/samba/suggest": return json({ shares: [{ name: "Media", path: "/mnt/Media", readOnly: false, kind: "drive", on: true }, { name: "Backup", path: "/mnt/Backup", readOnly: true, kind: "drive", on: false }], supported: true });
      case "/api/integrations/check": return json(result(JOB.cfg || {}).integrations);
      case "/api/lookup": {      // the free Blender open movies, so the search has something real to show
        const films = [["Sintel", 2010, "A girl searches for the baby dragon she befriended."], ["Big Buck Bunny", 2008, "A giant rabbit takes revenge on three bullying rodents."],
                       ["Tears of Steel", 2012, "Fighters try to save the world from destructive robots."]];
        const term = (query.get("term") || "").toLowerCase();
        return json(films.filter(f => !term || f[0].toLowerCase().includes(term.split(" ")[0]) || term.length < 3).concat(films).slice(0, 3)
          .map(([title, year, overview], i) => ({ id: 100 + i, title, year, overview, poster: null, lang: "English", inLibrary: false, raw: { title, year } })));
      }
      case "/api/add": return json({ id: 1, kind: body.kind });
      case "/api/diagnose": {
        const rel = (title, indexer, sizeMB, seeders, quality, approved, rejections) => ({ title, indexer, sizeMB, seeders, quality, approved, rejections, guid: title, indexerId: 1, languages: ["English"] });
        const releases = [rel("Sintel.2010.1080p.BluRay.x264", "YTS", 1480, 214, "Bluray-1080p", true, []), rel("Sintel.2010.720p.WEB-DL", "1337x", 780, 96, "WEBDL-720p", true, []),
                          rel("Sintel.2010.2160p.UHD.HDR", "The Pirate Bay", 14800, 41, "Bluray-2160p", false, ["Quality not wanted in profile", "Larger than maximum size"])];
        return json({ verdict: "ok", message: "A release matches your choices. It would download automatically (demo: nothing is downloaded).", releases,
                      reasons: { "quality not allowed": 1, "too big": 1 } });
      }
      case "/api/grab": return json({ ok: true });
      default: return json({});
    }
  }

  window.fetch = (input, init) => {
    const url = new URL(typeof input === "string" ? input : input.url, location.href);
    if (!url.pathname.startsWith("/api/")) return real(input, init);
    const method = (init && init.method) || "GET";
    let body; try { body = init && init.body ? JSON.parse(init.body) : undefined; } catch (e) { body = undefined; }
    return api(url.pathname, url.searchParams, method, body);
  };

  /* the pretend apps are not really there: say so instead of opening a dead address */
  document.addEventListener("click", e => {
    const a = e.target.closest && e.target.closest("a[href*='media-server.local']");
    if (!a) return;
    e.preventDefault();
    const t = document.createElement("div");
    t.className = "toast"; t.textContent = "Demo: on a real install this opens the app.";
    document.body.append(t); setTimeout(() => t.remove(), 3000);
  });

  /* a bar on top, so nobody mistakes this for a real install */
  document.addEventListener("DOMContentLoaded", () => {
    const bar = document.createElement("div");
    bar.className = "demo-bar";
    bar.append("This is a demo. Click through every screen: nothing is installed or saved. ");
    const a = document.createElement("a");
    a.href = "https://github.com/Hikki-dev/media-server-setup"; a.target = "_blank"; a.rel = "noopener"; a.textContent = "Get the real thing on GitHub";
    bar.append(a);
    const home = document.createElement("a");
    home.href = "../"; home.textContent = "Back to the overview";
    bar.append(home);
    document.body.prepend(bar);
    const st = document.createElement("style");
    st.textContent = ".demo-bar{position:sticky;top:0;z-index:50;background:#2a1a02;color:#fde7bd;text-align:center;font:600 14px/1.4 system-ui,sans-serif;padding:9px 14px}.demo-bar a{color:#ffc266;margin-left:12px;white-space:nowrap}";
    document.head.append(st);
  });
})();
