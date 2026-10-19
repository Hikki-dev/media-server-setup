"use strict";
/* Media Server Setup - wizard + dashboard. Markup and classes follow the Claude Design mockups. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const api = async (path, body) => {
  const r = await fetch(path, body !== undefined ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : { cache: "no-store" });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error((j.errors && j.errors.join(" ")) || j.error || r.statusText);
  return j;
};
const toast = (m, top) => { const t = document.createElement("div"); t.className = "toast" + (top ? " top" : ""); t.textContent = m; document.body.append(t); setTimeout(() => t.remove(), 3600); return t; };
/* light is the default; the choice is remembered in this browser */
const THEME = { get: () => (document.documentElement.dataset.theme === "dark" ? "dark" : "light"), set(t) { document.documentElement.dataset.theme = t; try { localStorage.setItem("mss-theme", t); } catch (e) { /* not saved */ } } };
const themeInner = () => (THEME.get() === "dark" ? `${ic("sun")}<span>Switch to light mode</span>` : `${ic("moon")}<span>Switch to dark mode</span>`);
const themeBtn = () => `<button class="sidelink" type="button" data-theme-toggle>${themeInner()}</button>`;
const guideLink = () => `<a class="sidelink" href="/guide" target="_blank" rel="noopener">${ic("book")}<span>Open the guide</span></a>`;
document.addEventListener("click", e => { if (!e.target.closest("[data-theme-toggle]")) return; THEME.set(THEME.get() === "dark" ? "light" : "dark"); document.querySelectorAll("[data-theme-toggle]").forEach(b => { b.innerHTML = themeInner(); }); });

const ICON = {
  film: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4M3 12h18M3 16h4M17 8h4M17 16h4"/>',
  tv: '<rect x="2" y="7" width="20" height="14" rx="2"/><path d="M17 2l-5 5-5-5"/>',
  spark: '<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z"/>',
  drive: '<path d="M22 12H2"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/><path d="M6 16h.01M10 16h.01"/>',
  folder: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  download: '<path d="M12 3v12m0 0l-4-4m4 4l4-4M4 21h16"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7"/>', play: '<path d="M8 5v14l11-7z"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
  link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>', arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
  globe: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
  sliders: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/>',
  book: '<path d="M12 6c-2-1.5-5-2-8-2v14c3 0 6 .5 8 2 2-1.5 5-2 8-2V4c-3 0-6 .5-8 2z"/><path d="M12 6v14"/>',
  moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
};
const ic = (n, c = "") => `<svg class="i ${c}" viewBox="0 0 24 24" aria-hidden="true">${ICON[n]}</svg>`;
const fmt = b => b == null ? "" : b >= 1e12 ? (b / 1e12).toFixed(1) + " TB" : b >= 1e9 ? Math.round(b / 1e9) + " GB" : Math.round(b / 1e6) + " MB";

const PACKS_DEFAULT = ["english", "anime", "tamil", "malayalam", "japanese", "korean"];
const S = {
  step: "welcome", env: null, pc: {}, mode: "wizard", tab: "find", plan: null,
  cfg: {
    kinds: ["tv", "movies"], packs: [...PACKS_DEFAULT], animeAudio: "sub", subtitleLangs: ["en"],
    storage: { mode: "single", base: "", downloads: "", libraries: [{ type: "movies", path: "" }, { type: "tv", path: "" }, { type: "anime", path: "" }] },
    quality: { episodeCapMB: 800, episodeRuntime: 45, movieCapGB: 5, allow720: true, preferX265: true },
    settings: { minSeeders: 2, concurrent: 3, dlLimitKB: 0, ulLimitKB: 400, rssMinutes: 30, retryFailed: true, upgrade: false, hardSubs: true },
    qbit: { username: "admin", password: "", vuetorrent: true },
    login: { username: "admin", password: "", email: "" },
    solver: "flaresolverr", services: { jellyfin: true, seerr: true, bazarr: true, homepage: true, metube: false, komga: false, kapowarr: false, kaizoku: false, scrutiny: false, samba: false, tailscale: false },
    subtitles: {}, ports: {}, samba: null, livetv: null, notify: null, adopt: {}, skipGroups: [],
  },
};
const WIZ = [["welcome", "Welcome"], ["check", "Computer check"], ["mine", "Your apps"], ["storage", "Storage"], ["watch", "What you watch"], ["livetv", "Live TV and sports"], ["profiles", "Profiles"], ["downloads", "Downloads"], ["apps", "Apps and accounts"], ["changes", "What changes"], ["review", "Review"]];
const ORDER = WIZ.map(x => x[0]);
// two steps only appear when they matter: "Your apps" when apps of the person's own were found, "What changes" when they are used
const shown = k => k === "mine" ? !!(S.found && S.found.some(a => !a.ours)) : k === "changes" ? Object.keys(S.cfg.adopt || {}).length > 0 : true;
const VIS = () => WIZ.filter(([k]) => shown(k));
const KIND = { movies: ["film", "Movies"], tv: ["tv", "TV Shows"], anime: ["spark", "Anime"] };
const DIRNAME = { movies: "Movies", tv: "TV Shows", anime: "Anime" };
const SVC = { jellyfin: ["film", "Jellyfin", "Watch your library on any device"], seerr: ["search", "Seerr", "Request page for family and friends"], bazarr: ["globe", "Bazarr", "Finds subtitles automatically"], homepage: ["link", "Homepage", "One dashboard for every app"], metube: ["download", "MeTube", "Download YouTube videos"], komga: ["folder", "Komga", "Comics and manga reader"], kapowarr: ["spark", "Kapowarr", "Automatic comic downloads"], kaizoku: ["folder", "Kaizoku", "Automatic manga downloads (manga only)"], scrutiny: ["drive", "Scrutiny", "Hard drive health"], samba: ["folder", "File sharing", "Open your media and drives from other computers and phones"], tailscale: ["link", "Private HTTPS addresses", "Open every app from anywhere, safely, with Tailscale"] };

/* ------------------------------------------------------------ shell */
function stepItems(active) {
  const vis = VIS(), idx = vis.findIndex(x => x[0] === active);
  return vis.map(([k, label], i) => {
    const cls = k === active ? "on" : (idx > i || active === "install" || active === "done") ? "done" : "";
    const n = cls === "done" ? ic("check", "s") : i + 1;
    return `<li class="${cls}"><span class="n">${n}</span><span class="t">${esc(label)}</span></li>`;
  }).join("");
}
function shell(active, main, foot = "") {
  $("#app").innerHTML = `<div class="app"><aside class="side"><div class="brand"><span class="mark">${ic("play")}</span>Media Server Setup</div><ol class="steps">${stepItems(active)}</ol><div class="foot"><div class="sidelinks">${guideLink()}${themeBtn()}</div>${foot ? `<p class="footnote">${esc(foot)}</p>` : ""}</div></aside><main class="main screen">${main}</main></div>`;
  window.scrollTo(0, 0);
}
const head = (n, title, lead) => `<div><span class="eyebrow">${n}</span><h2 style="font-size:36px">${esc(title)}</h2><p class="lead">${esc(lead)}</p></div>`;
const stepHead = (n, title, lead) => { const v = VIS(), i = v.findIndex(x => x[0] === S.step); return head(`Step ${i < 0 ? n : i + 1} of ${v.length}`, title, lead); };
const nav = (next = "Continue", off = false) => `<div class="actions"><button class="btn" id="back">Back</button><button class="btn primary" id="next" ${off ? "disabled" : ""}>${esc(next)} ${ic("arrow")}</button></div>`;
const go = step => { S.step = step; render(); };
const goRel = d => { let i = ORDER.indexOf(S.step); do { i = Math.max(0, Math.min(ORDER.length - 1, i + d)); } while (!shown(ORDER[i]) && i > 0 && i < ORDER.length - 1); go(ORDER[i]); };
function wire(next) { $("#back")?.addEventListener("click", () => goRel(-1)); $("#next")?.addEventListener("click", next || (() => goRel(1))); }
const toggleIn = (arr, k) => { const i = arr.indexOf(k); i >= 0 ? arr.splice(i, 1) : arr.push(k); };
const sw = (on, id, label) => `<button class="switch ${on ? "on" : ""}" id="${id}" role="switch" aria-checked="${on}" aria-label="${esc(label)}"></button>`;
function bindSwitch(id, get, set) { const b = $("#" + id); if (!b) return; b.onclick = () => { const v = !get(); set(v); b.classList.toggle("on", v); b.setAttribute("aria-checked", v); }; }
function bindSeg(sel, get, set, conv = x => x) { $$(sel + " button").forEach(b => b.onclick = () => { set(conv(b.dataset.v)); $$(sel + " button").forEach(x => x.classList.toggle("on", x === b)); }); }
const seg = (id, opts, cur) => `<div class="seg" id="${id}">${opts.map(([v, l]) => `<button data-v="${esc(v)}" class="${String(cur) === String(v) ? "on" : ""}">${esc(l)}</button>`).join("")}</div>`;
const onKey = (el, f) => { el.onclick = f; el.onkeydown = e => (e.key === " " || e.key === "Enter") && (e.preventDefault(), f()); };

const genPw = () => { const a = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"; const r = crypto.getRandomValues(new Uint32Array(14)); return [...r].map(n => a[n % a.length]).join(""); };
const pwField = (id, value, label) => `<div class="field"><label for="${id}">${label}</label><div style="display:flex;gap:8px"><input class="input" id="${id}" type="password" value="${esc(value)}" placeholder="choose one" autocomplete="new-password" style="flex:1"><button class="btn sm" type="button" data-show="${id}">Show</button><button class="btn sm" type="button" data-gen="${id}">Generate</button></div></div>`;
function bindPw() {
  $$("[data-show]").forEach(b => b.onclick = () => { const i = $("#" + b.dataset.show); const on = i.type === "password"; i.type = on ? "text" : "password"; b.textContent = on ? "Hide" : "Show"; });
  $$("[data-gen]").forEach(b => b.onclick = () => { const i = $("#" + b.dataset.gen); i.value = genPw(); i.type = "text"; const sb = $(`[data-show="${b.dataset.gen}"]`); if (sb) sb.textContent = "Hide"; });
}
const credsCard = list => `<div class="card"><div class="card-h"><h3>Your logins</h3><span class="sub">Each one was signed in to just now</span></div>${list.map((c, i) => `<div class="lib" style="grid-template-columns:130px minmax(0,1fr) auto"><div class="kind">${esc(c.app)}</div><div class="where">${c.user ? `<div class="mono">${esc(c.user)}</div><div class="mono" style="color:var(--mute)"><span data-pw="${i}">&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;</span></div>` : `<div class="hint" style="margin:0">${esc(c.note)}</div>`}${c.user ? `<div class="meta"><span>${esc(c.note)}</span></div>` : ""}</div><div style="display:flex;gap:8px;align-items:center">${c.user ? `<button class="btn sm" data-reveal="${i}">Show</button><button class="btn sm" data-copy="${i}">Copy</button>` : ""}<span class="pill ${c.ok ? "ok" : "bad"}">${c.ok ? "works" : "check"}</span>${c.url ? `<a class="btn sm" href="${esc(c.url)}" target="_blank" rel="noopener">Open</a>` : ""}</div></div>`).join("")}</div>`;
function bindCreds(list) {
  $$("[data-reveal]").forEach(b => b.onclick = () => { const i = +b.dataset.reveal, el = $(`[data-pw="${i}"]`); const shown = b.textContent === "Hide"; el.textContent = shown ? "\u2022".repeat(8) : list[i].password; b.textContent = shown ? "Show" : "Hide"; });
  $$("[data-copy]").forEach(b => b.onclick = async () => { try { await navigator.clipboard.writeText(list[+b.dataset.copy].password); toast("Password copied"); } catch (e) { toast("Copy failed: select it with Show"); } });
}

const linksCard = list => `<div class="card" id="linkscard"><div class="card-h"><h3>How the apps are linked</h3><button class="btn sm" id="recheck">Check again</button></div>${list.map(l => `<div class="setting" style="padding:11px 0"><div><div class="t">${esc(l.name)}</div><div class="d">${esc(l.detail)}${l.fixed ? " (repaired automatically)" : ""}</div></div><span class="pill ${l.ok ? "ok" : "bad"}">${l.ok ? "connected" : "needs attention"}</span></div>`).join("")}</div>`;
function bindLinks(onUpdate) { const b = $("#recheck"); if (!b) return; b.onclick = async () => { b.disabled = true; b.textContent = "Checking…"; try { const r = await api("/api/integrations/check", {}); onUpdate(r); } catch (e) { toast(e.message); b.disabled = false; b.textContent = "Check again"; } }; }

/* ------------------------------------------------------------ storage helpers */
async function checkPath(p) {
  if (!p) return null;
  try { S.pc[p] = await api("/api/pathcheck?path=" + encodeURIComponent(p)); } catch (e) { S.pc[p] = { ok: false, error: e.message }; }
  return S.pc[p];
}
const meterHtml = i => {
  if (!i || i.totalBytes == null || !i.totalBytes) return "";
  const pct = Math.round(i.usedBytes / i.totalBytes * 100);
  return `<div class="meter"><i class="${pct > 92 ? "hi" : pct > 78 ? "mid" : ""}" style="width:${pct}%"></i></div>`;
};
function pathMeta(i, extra = "") {
  if (!i) return `<div class="meta"><span>Checking…</span></div>`;
  if (i.ok === false && i.error) return `<div class="meta"><span class="errtxt">${esc(i.error)}</span></div>`;
  const bits = [];
  if (i.exists === false) bits.push(`<span class="warnc">will be made</span>`);
  else bits.push(i.writable ? `<span class="okc">writable</span>` : `<span class="errtxt">the apps are not allowed to write here</span>`);
  if (i.freeBytes != null) bits.push(`<span>${fmt(i.freeBytes)} free of ${fmt(i.totalBytes)}</span>`);
  if (i.exists !== false && i.items != null) bits.push(`<span>${i.items} item${i.items === 1 ? "" : "s"} inside</span>`);
  return `<div class="meta">${bits.join("")}${extra}</div>`;
}
async function refreshPlan() {
  const st = S.cfg.storage;
  try { S.plan = await api("/api/plan", { storage: st, hostOs: S.env.hostOs }); } catch (e) { S.plan = null; }
}

/* ------------------------------------------------------------ folder browser */
async function openBrowser(title, start, onPick) {
  const ov = document.createElement("div"); ov.className = "overlay";
  document.body.append(ov);
  let cur = null, drives = { drives: [], places: [] };
  const close = () => ov.remove();
  async function load(path) {
    try { cur = await api("/api/browse?path=" + encodeURIComponent(path)); draw(); } catch (e) { toast(e.message); }
  }
  function draw() {
    const crumbs = cur ? cur.segments.map((s, i) => `<span data-i="${i}" style="cursor:pointer">${esc(s)}</span>`).join("<span>/</span>") : "";
    ov.innerHTML = `<div class="modal" role="dialog" aria-label="${esc(title)}">
      <div class="modal-h"><div><h3>${esc(title)}</h3><div class="hint" style="margin:2px 0 0">Pick a folder you already have, or make a new one. Nothing inside it is changed.</div></div><button class="btn sm" id="bx" aria-label="Close">${ic("x", "s")}</button></div>
      <div class="crumbs">${cur ? `<span style="cursor:pointer" data-i="-1">Drives</span><span>/</span>${crumbs}` : "<span>Choose a drive</span>"}</div>
      <div class="modal-body"><div class="qa"><div class="h">Drives</div>${drives.drives.map(d => `<div class="it" data-p="${esc(d.path)}">${ic("drive")}${esc(d.name)}<small>${fmt(d.freeBytes)}</small></div>`).join("") || `<div class="hint" style="padding:6px 10px">${drives.failed ? "Could not read your drives. Close this and try again." : "No drives found"}</div>`}
        ${drives.places.length ? `<div class="h" style="margin-top:10px">Places</div>${drives.places.map(d => `<div class="it" data-p="${esc(d.path)}">${ic("folder")}${esc(d.name)}</div>`).join("")}` : ""}</div>
        <div class="dirs">${cur ? (cur.dirs.length ? cur.dirs.map(d => `<div class="dir" data-d="${esc(d.name)}">${ic("folder")}${esc(d.name)}<span class="sz">${d.items} items</span></div>`).join("") : `<div class="hint" style="padding:14px">No folders here. Press “New folder” or choose this one.</div>`) : `<div class="hint" style="padding:14px">Pick a drive on the left.</div>`}</div></div>
      <div class="modal-f"><div style="min-width:0"><div class="mono" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${cur ? esc(cur.path) : ""}</div>${cur ? `<div class="hint" style="margin:2px 0 0;color:${cur.writable ? "var(--ok)" : "var(--bad)"}">${cur.writable ? "Writable" : "The apps are not allowed to write here"} &#183; ${fmt(cur.freeBytes)} free &#183; ${cur.items} item${cur.items === 1 ? "" : "s"}</div>` : ""}</div>
        <div style="display:flex;gap:10px;flex:none"><button class="btn" id="bn" ${cur ? "" : "disabled"}>${ic("plus", "s")}New folder</button><button class="btn primary" id="bu" ${cur ? "" : "disabled"}>Use this folder</button></div></div></div>`;
    $("#bx", ov).onclick = close;
    ov.onclick = e => { if (e.target === ov) close(); };
    $$(".qa .it", ov).forEach(el => el.onclick = () => load(el.dataset.p));
    $$(".dir", ov).forEach(el => el.onclick = () => load(cur.path.replace(/\/$/, "") + "/" + el.dataset.d));
    $$(".crumbs [data-i]", ov).forEach(el => el.onclick = () => {
      const i = +el.dataset.i; if (i < 0) { cur = null; draw(); return; }
      const segs = cur.segments.slice(0, i + 1); load(/^[A-Za-z]:$/.test(segs[0]) ? segs[0] + "/" + segs.slice(1).join("/") : "/" + segs.join("/"));
    });
    $("#bn", ov)?.addEventListener("click", async () => {
      const name = prompt("New folder name"); if (!name) return;
      try { const r = await api("/api/mkdir", { parent: cur.path, name }); load(r.path); } catch (e) { toast(e.message); }
    });
    $("#bu", ov)?.addEventListener("click", () => { if (!cur.writable && !confirm("The apps are not allowed to write in this folder. Use it anyway?")) return; close(); onPick(cur.path); });
  }
  draw();
  try { drives = await api("/api/drives"); } catch (e) { drives.failed = true; }
  draw();
  let p = start || S.env.defaultMedia || "";
  for (let k = 0; p && k < 8; k++) { try { await api("/api/browse?path=" + encodeURIComponent(p)); await load(p); return; } catch (e) { const np = p.replace(/[\\/][^\\/]*$/, ""); if (np === p || np.length < 2) break; p = np; } }
}



/* ------------------------------------------------------------ notifications */
const NT = {
  discord: { label: "Discord", fields: [["webhook", "Webhook URL", "https://discord.com/api/webhooks/..."]], steps: "In Discord open the channel's settings, Integrations, Webhooks, New Webhook, then Copy Webhook URL." },
  telegram: { label: "Telegram", fields: [["botToken", "Bot token", "123456:ABC..."], ["chatId", "Chat id", "e.g. 123456789"]], steps: "Message @BotFather, send /newbot and copy the token. Send any message to your new bot, then open https://api.telegram.org/bot<token>/getUpdates and copy the number after \"chat\":{\"id\":." },
  pushover: { label: "Pushover", fields: [["userKey", "User key", "shown on pushover.net"], ["apiKey", "Application token", "create an application on pushover.net"]], steps: "On pushover.net copy your User Key, then create an Application and copy its API token." },
  ntfy: { label: "ntfy", fields: [["topic", "Topic", "a private topic name"], ["server", "Server (optional)", "https://ntfy.sh"], ["token", "Access token (optional)", ""]], steps: "Pick a long, hard-to-guess topic name and subscribe to it in the ntfy app. Leave the server empty to use ntfy.sh." },
  gotify: { label: "Gotify", fields: [["server", "Server address", "https://gotify.example.com"], ["token", "Application token", ""]], steps: "In Gotify create an application and copy its token; use your Gotify server address." },
};
function notifyEditor(box, sel, onChange = () => {}) {
  sel.values = sel.values || {};
  const draw = () => {
    const p = sel.provider && NT[sel.provider];
    box.innerHTML = `<div class="chips"><span class="chip ${!p ? "on" : ""}" data-np="" tabindex="0">${!p ? '<span class="dot"></span>' : ""}No notifications</span>${Object.entries(NT).map(([k, v]) => `<span class="chip ${sel.provider === k ? "on" : ""}" data-np="${k}" tabindex="0">${sel.provider === k ? '<span class="dot"></span>' : ""}${v.label}</span>`).join("")}</div>
      ${p ? `<p class="hint">${esc(p.steps)}</p><div class="grid2">${p.fields.map(([k, l, ph]) => `<div class="field"><label for="nt-${k}">${l}</label><input class="input" id="nt-${k}" data-nk="${k}" value="${esc(sel.values[k] || "")}" placeholder="${esc(ph)}" autocomplete="off"></div>`).join("")}</div>
      <p class="hint" style="margin:0">You get a message when something starts downloading, finishes, gets a better version, or needs your help. It also works for Prowlarr, Seerr and Bazarr.</p>` : ""}`;
    $$("[data-np]", box).forEach(el => onKey(el, () => { sel.provider = el.dataset.np || null; onChange(); draw(); }));
    $$("[data-nk]", box).forEach(el => el.oninput = () => { sel.values[el.dataset.nk] = el.value.trim(); onChange(); });
  };
  draw();
}
const ntSummary = c => c.notify && c.notify.provider ? NT[c.notify.provider].label : "Off";

/* ------------------------------------------------------------ live tv and sports */
const LT_DEFAULT = () => ({ enabled: false, countries: [], categories: [], extraCategories: ["sports"], languages: [], youtube: [], local: [], fullGuide: false, english: false, custom: { m3u: "", xmltv: "" }, checkStreams: true });
const flagOf = c => (c && c.flag ? `<span class="flag" aria-hidden="true">${c.flag}</span>` : "");      // the flag is its own item, so the chip spacing applies to it
async function ltCatalog() { return S.ltcat || (S.ltcat = await api("/api/livetv/catalog")); }
function ltEditor(box, sel, onChange = () => {}) {
  const st = S.ltui || (S.ltui = { q: "", region: "", pre: "" });
  const draw = async () => {
    let cat; try { cat = await ltCatalog(); } catch (e) { box.innerHTML = `<div class="note bad">${ic("info")}<div>Could not load the channel catalogue (${esc(e.message)}). It needs an internet connection; try again in a moment.</div></div>`; return; }
    const byCode = Object.fromEntries(cat.countries.map(c => [c.code, c]));
    const langName = Object.fromEntries(cat.languages.map(l => [l.code, l.name]));
    const chips = (items, on, attr, lab) => items.map(x => `<span class="chip ${on(x) ? "on" : ""}" ${attr}="${esc(x.id ?? x.code)}" tabindex="0">${on(x) ? '<span class="dot"></span>' : ""}${lab(x)}</span>`).join("");
    const region = cat.regions.find(r => r.code === st.region);
    const pool = cat.countries.filter(c => (!region || region.countries.includes(c.code)) && (!st.q || c.name.toLowerCase().includes(st.q.toLowerCase())));
    const shown = pool.filter(c => !sel.countries.includes(c.code)).slice(0, 18);
    const langs = [...new Set(sel.countries.flatMap(k => (byCode[k] || {}).languages || []).concat(sel.languages))].filter(l => langName[l]);
    box.innerHTML = `<div class="setting" style="padding-top:0"><div><div class="t">Add live TV and sports to Jellyfin</div><div class="d">Free channels show up under Live TV in Jellyfin, with a TV guide when one is available.</div></div>${sw(sel.enabled, "lt-on", "Live TV")}</div>
    ${sel.enabled ? `
    <div class="card" style="margin-top:14px"><div class="card-h"><h3>Which countries do you want channels from?</h3><span class="sub">${sel.countries.length} selected</span></div>
      <div class="chips">${sel.countries.map(k => `<span class="chip on" data-rm="${k}" tabindex="0"><span class="dot"></span>${flagOf(byCode[k])}${esc((byCode[k] || {}).name || k)} &times;</span>`).join("") || '<span class="hint" style="margin:0">Nothing picked yet. Search for a country or choose a region.</span>'}</div>
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:14px"><input class="input" id="lt-q" style="flex:1 1 220px;width:auto" placeholder="Search countries" value="${esc(st.q)}" aria-label="Search countries"><select class="input" id="lt-region" style="flex:1 1 200px;width:auto;max-width:100%" aria-label="Region"><option value="">Every region</option>${cat.regions.map(r => `<option value="${r.code}" ${st.region === r.code ? "selected" : ""}>${esc(r.name)}</option>`).join("")}</select></div>
      <div class="chips" style="margin-top:12px">${shown.map(c => `<span class="chip" data-add="${c.code}" tabindex="0">${flagOf(c)}${esc(c.name)}</span>`).join("")}${region && pool.length ? `<span class="chip" data-all="1" tabindex="0">Add all ${pool.length} in ${esc(region.name)}</span>` : ""}</div>
      <p class="hint">The channels come from free public lists. Only pick countries you really watch. A whole region means thousands of channels.</p></div>
    ${sel.countries.length > 1 ? `<div class="card"><div class="card-h"><h3>Local channels first</h3><span class="sub">${(sel.local || []).length ? "on" : "off"}</span></div>
      <div class="chips">${sel.countries.map(k => `<span class="chip ${(sel.local || []).includes(k) ? "on" : ""}" data-loc="${k}" tabindex="0">${(sel.local || []).includes(k) ? '<span class="dot"></span>' : ""}${flagOf(byCode[k])}${esc((byCode[k] || {}).name || k)}</span>`).join("")}</div>
      <p class="hint">If you picked several countries, tick your own here. Its channels come first, are saved as favourites for everyone, and show on the Jellyfin home page. Press Apply again after adding new users.</p></div>` : ""}
    <div class="card"><div class="card-h"><h3>What kind of channels?</h3><span class="sub">${sel.categories.length ? sel.categories.length + " chosen" : "all kinds"}</span></div>
      <div class="chips">${chips(cat.categories, x => sel.categories.includes(x.id), "data-cat", x => esc(x.name))}</div>
      <p class="hint">Leave this empty to get every channel, or tick only what you want, like Sports and News.</p>
      <div class="setting"><div><div class="t">Also add free sports channels from anywhere in the world</div><div class="d">Adds every sports channel that works, from any country.</div></div>${sw(sel.extraCategories.includes("sports"), "lt-sp", "Worldwide sports")}</div>
      ${langs.length ? `<div class="slab" style="margin-top:12px"><span>Also add channels in these languages, from any country</span></div><div class="chips" style="margin-top:8px">${langs.map(l => `<span class="chip ${sel.languages.includes(l) ? "on" : ""}" data-lang="${l}" tabindex="0">${sel.languages.includes(l) ? '<span class="dot"></span>' : ""}${esc(langName[l])}</span>`).join("")}</div>` : ""}
    </div>
    ${(cat.youtube || []).some(y => y.country === "*" || sel.countries.includes(y.country)) ? `<div class="card"><div class="card-h"><h3>Live channels on YouTube</h3><span class="sub">${(sel.youtube || []).length} chosen</span></div>
      <div class="chips">${cat.youtube.filter(y => y.country === "*" || sel.countries.includes(y.country)).map(y => `<span class="chip ${(sel.youtube || []).includes(y.id) ? "on" : ""}" data-yt="${esc(y.id)}" tabindex="0">${(sel.youtube || []).includes(y.id) ? '<span class="dot"></span>' : ""}${esc(y.name)} &middot; ${esc(y.note)}</span>`).join("")}</div>
      <p class="hint">Real TV channels that broadcast live on YouTube. Some are on all day. The others only play while they are live, and show a message the rest of the time.</p></div>` : ""}
    <div class="card"><div class="card-h"><h3>NordVPN for channels that only work in some countries</h3><span class="sub">optional</span></div>
      <div class="chips"><span class="chip ${!(sel.vpn && sel.vpn.provider) ? "on" : ""}" data-vpn="" tabindex="0">${!(sel.vpn && sel.vpn.provider) ? '<span class="dot"></span>' : ""}Off</span><span class="chip ${sel.vpn && sel.vpn.provider === "nordvpn" ? "on" : ""}" data-vpn="nordvpn" tabindex="0">${sel.vpn && sel.vpn.provider === "nordvpn" ? '<span class="dot"></span>' : ""}NordVPN</span></div>
      ${sel.vpn && sel.vpn.provider === "nordvpn" ? `<p class="hint">Some free channels refuse to play outside their own country. With NordVPN, the setup tries them from the UK and the US and keeps the ones that work. It checks again every day. Only those channels use the VPN. In your Nord Account open NordVPN, <b>Set up NordVPN yourself</b>, then <b>NordVPN service login</b> This is not your normal NordVPN login. Channels through the VPN start a few seconds slower. It works best on Linux.</p>
      <div class="grid2"><div class="field"><label for="vpn-u">Service username</label><input class="input" id="vpn-u" value="${esc(sel.vpn.user || "")}" autocomplete="off"></div><div class="field"><label for="vpn-p">Service password</label><input class="input" id="vpn-p" type="password" value="${esc(sel.vpn.password || "")}" autocomplete="new-password"></div></div>` : `<p class="hint">Leave this off if you do not use NordVPN. Everything else works without it.</p>`}</div>
    <div class="card"><div class="card-h"><h3>Your own TV provider</h3><span class="sub">optional</span></div>
      <p class="hint" style="margin-top:0">Paid sports and premium channels are not on the free lists. If you pay for a TV provider and they gave you a playlist link and a guide link, paste them here and they are added too.</p>
      <div class="field"><label for="lt-m3u">Channel list link</label><input class="input" id="lt-m3u" value="${esc(sel.custom.m3u)}" placeholder="https://..."></div>
      <div class="field"><label for="lt-xml">TV guide link</label><input class="input" id="lt-xml" value="${esc(sel.custom.xmltv)}" placeholder="https://..."></div></div>
    <div class="card"><div class="setting" style="padding-top:0"><div><div class="t">TV guide for every channel</div><div class="d">Off to start with. It adds show times for channels that have a guide, but with hundreds of channels Jellyfin becomes slow. Your local channels always get a simple guide.</div></div>${sw(!!sel.fullGuide, "lt-fg", "Full guide")}</div>
      <div class="setting"><div><div class="t">English channels only</div><div class="d">Leaves out channels in other languages, like Nickelodeon Germany. Your local channels are always kept.</div></div>${sw(!!sel.english, "lt-en", "English only")}</div>
      <div class="setting"><div><div class="t">Remove channels that do not work</div><div class="d">Every channel is tested and broken ones are left out. It checks again every day. Only the best 600 are kept, because a longer list makes Jellyfin slow.</div></div>${sw(sel.checkStreams, "lt-ck", "Remove broken channels")}</div>
      <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-top:6px"><button class="btn sm" id="lt-pv">${ic("search", "s")}Count channels</button><span class="hint" id="lt-out" style="margin:0"></span></div></div>` : ""}`;
    bindSwitch("lt-on", () => sel.enabled, v => { sel.enabled = v; if (v && !sel.countries.length) { const r = (navigator.language || "").split("-")[1]; const k = r === "GB" ? "UK" : r; if (byCode[k]) { sel.countries.push(k); sel.local = [k]; } } onChange(); draw(); });
    if (!sel.enabled) return;
    const rerender = () => { onChange(); draw(); };
    $$("[data-add]", box).forEach(el => onKey(el, () => { sel.countries.push(el.dataset.add); rerender(); }));
    $$("[data-rm]", box).forEach(el => onKey(el, () => { sel.countries = sel.countries.filter(x => x !== el.dataset.rm); rerender(); }));
    $$("[data-all]", box).forEach(el => onKey(el, () => { sel.countries = [...new Set([...sel.countries, ...pool.map(c => c.code)])]; rerender(); }));
    $$("[data-cat]", box).forEach(el => onKey(el, () => { toggleIn(sel.categories, el.dataset.cat); rerender(); }));
    $$("[data-loc]", box).forEach(el => onKey(el, () => { sel.local = sel.local || []; toggleIn(sel.local, el.dataset.loc); rerender(); }));
    $$("[data-vpn]", box).forEach(el => onKey(el, () => { sel.vpn = sel.vpn || {}; sel.vpn.provider = el.dataset.vpn || null; rerender(); }));
    const vu = $("#vpn-u"), vp = $("#vpn-p");
    if (vu) { vu.oninput = () => { sel.vpn.user = vu.value.trim(); onChange(); }; vp.oninput = () => { sel.vpn.password = vp.value; onChange(); }; }
    $$("[data-yt]", box).forEach(el => onKey(el, () => { sel.youtube = sel.youtube || []; toggleIn(sel.youtube, el.dataset.yt); rerender(); }));
    $$("[data-lang]", box).forEach(el => onKey(el, () => { toggleIn(sel.languages, el.dataset.lang); rerender(); }));
    bindSwitch("lt-sp", () => sel.extraCategories.includes("sports"), v => { sel.extraCategories = v ? ["sports"] : []; onChange(); });
    bindSwitch("lt-en", () => !!sel.english, v => { sel.english = v; onChange(); });
    bindSwitch("lt-fg", () => !!sel.fullGuide, v => { sel.fullGuide = v; onChange(); });
    bindSwitch("lt-ck", () => sel.checkStreams, v => { sel.checkStreams = v; onChange(); });
    $("#lt-q").oninput = e => { st.q = e.target.value; clearTimeout(st.t); st.t = setTimeout(() => { draw().then(() => { const i = $("#lt-q"); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }); }, 250); };
    $("#lt-region").onchange = e => { st.region = e.target.value; draw(); };
    $("#lt-m3u").oninput = e => { sel.custom.m3u = e.target.value.trim(); onChange(); };
    $("#lt-xml").oninput = e => { sel.custom.xmltv = e.target.value.trim(); onChange(); };
    $("#lt-pv").onclick = async () => {
      const out = $("#lt-out"); out.textContent = "Counting…"; $("#lt-pv").disabled = true;
      try { const r = await api("/api/livetv/preview", sel); out.textContent = r.channels ? `About ${r.channels} channels (${r.sports} sports) before testing which ones work.` : "No channels found for these choices."; }
      catch (e) { out.textContent = e.message; }
      $("#lt-pv").disabled = false;
    };
  };
  return draw();
}
const ltSummary = c => { const l = c.livetv; return l && l.enabled ? `${l.countries.length} countr${l.countries.length === 1 ? "y" : "ies"}${l.extraCategories.includes("sports") ? ", sports worldwide" : ""}${l.categories.length ? ", " + l.categories.join("/") : ""}${l.custom.m3u ? ", your provider" : ""}` : "Off"; };

/* ------------------------------------------------------------ profiles */
const WORLD_LANGS = () => Object.keys(S.env.packs).filter(k => !["english", "anime"].includes(k));
function defaultProfiles(c) {
  const q = c.quality, P = S.env.packs, base = { resTv: q.allow720 ? "1080+720" : "1080", resMv: q.allow720 ? "1080+720" : "1080", ep2160: 6000, mv2160: 25, ep1080: q.episodeCapMB, mv1080: q.movieCapGB, ep720: Math.max(150, Math.round(q.episodeCapMB / 2 / 50) * 50), mv720: Math.round(q.movieCapGB) / 2, x265: q.preferX265, strictSubs: false };
  const out = [];
  if (c.packs.includes("english")) out.push({ ...base, id: "english", name: "English", kind: "english", langs: ["english"], subs: "optional" });
  if (c.packs.includes("anime")) out.push({ ...base, id: "anime", name: "Anime", kind: "anime", langs: [], subs: "required", audio: c.animeAudio, ep1080: Math.min(q.episodeCapMB, 600), ep720: Math.min(q.episodeCapMB, 600) / 2, mv1080: Math.min(q.movieCapGB, 4), mv720: Math.min(q.movieCapGB, 4) / 2 });
  const world = c.packs.filter(k => !["english", "anime"].includes(k));
  if (world.length) out.push({ ...base, id: "world", name: world.length <= 3 ? world.map(k => P[k]).join(" + ") : "World cinema", kind: "world", langs: world, subs: "required" });
  return out.length ? out : [{ ...base, id: "english", name: "English", kind: "english", langs: ["english"], subs: "optional" }];
}
function ensureProfiles() {
  const c = S.cfg, sig = JSON.stringify([c.packs, c.animeAudio]);
  if (!c.profiles || c._psig !== sig) {
    const old = Object.fromEntries((c.profiles || []).map(p => [p.id, p]));
    const fresh = defaultProfiles(c).map(p => old[p.id] ? { ...p, ...old[p.id], langs: p.kind === "world" ? p.langs : old[p.id].langs } : p);
    const custom = (c.profiles || []).filter(p => p.custom);
    c.profiles = [...fresh, ...custom]; c._psig = sig;
  }
}
function newProfile(c) {
  const n = c.profiles.filter(p => p.custom).length + 1;
  return { id: "custom" + Date.now(), custom: true, name: "New profile " + n, kind: "world", langs: [], resTv: "1080+720", resMv: "1080+720", ep2160: 6000, mv2160: 25, ep1080: 800, mv1080: 5, ep720: 400, mv720: 2.5, x265: true, subs: "required", strictSubs: false };
}
const qlab = v => v.split("+").map(r => r === "2160" ? "4K" : r + "p").join("/") + (v.includes("+") ? "" : " only");
const mbf = v => v >= 1000 ? (v / 1000).toFixed(1) + " GB" : Math.round(v) + " MB";
function profileCards(list, P, redraw) {
  const slider = (p, key, label, min, max, step, fmtf) => `<div><div class="slab"><span>${label}</span><b data-v="${key}">${fmtf(p[key])}</b></div><input type="range" min="${min}" max="${max}" step="${step}" value="${p[key]}" data-pk="${key}" aria-label="${label}"></div>`;
  return list.map((p, i) => {
    const ic1 = p.kind === "anime" ? "spark" : p.kind === "english" ? "tv" : "globe";
    const sub = { english: "English shows and movies", anime: "Japanese voices, with careful rules about which versions to trust", world: "Original voices with English subtitles" }[p.kind];
    const rs = k => (p[k] || p.res || "1080+720").split("+"), kinds = S.cfg.kinds || [], animeOn = (S.cfg.packs || []).includes("anime");
    const showTv = kinds.includes("tv") || animeOn, showMv = kinds.includes("movies") || animeOn;
    const QO = [["2160", "4K only"], ["2160+1080", "4K, or 1080p if needed"], ["1080", "1080p only"], ["1080+720", "1080p, or 720p if needed"], ["720", "720p only"]];
    const qrow = (key, label) => `<div><div class="slab"><span>${label}</span></div><div class="seg" data-res="${key}" style="margin-top:8px;flex-wrap:wrap">${QO.map(([v, t]) => `<button data-v="${v}" class="${(p[key] || p.res || "1080+720") === v ? "on" : ""}">${t}</button>`).join("")}</div></div>`;
    const EP = { 2160: [1500, 20000, 250], 1080: [300, 2500, 50], 720: [150, 1500, 50] }, MV = { 2160: [8, 80, 1], 1080: [1.5, 15, 0.5], 720: [0.8, 8, 0.5] };
    const gb = v => (+v).toFixed(1) + " GB";
    const sl = (unit, f) => (unit === "ep" ? rs("resTv") : rs("resMv")).map(r => slider(p, unit + r, `Biggest ${r === "2160" ? "4K" : r + "p"} ${unit === "ep" ? "episode" : "movie"}`, ...(unit === "ep" ? EP : MV)[r], f)).join("");
    return `<div class="card pf" data-pi="${i}"><div class="pf-h"><div class="pf-name"><span class="icbox" style="margin:0">${ic(ic1)}</span><div>${p.kind === "world" ? `<input class="input" data-pk="name" value="${esc(p.name)}" style="font-weight:650;min-width:240px" aria-label="Profile name">` : `<h3>${esc(p.name)}</h3>`}<div class="hint" style="margin:0">${sub}</div></div></div>${p.kind === "english" ? '<span class="pill">default</span>' : p.kind === "world" ? `<button class="btn sm danger" data-rmp="${i}">Remove</button>` : ""}</div>
      ${p.kind === "world" ? `<div class="chips">${WORLD_LANGS().map(k => `<span class="chip ${p.langs.includes(k) ? "on" : ""}" data-lang="${k}" tabindex="0">${p.langs.includes(k) ? '<span class="dot"></span>' : ""}${esc(P[k])}</span>`).join("")}</div>` : ""}
      ${p.kind === "anime" ? `<div><div class="slab"><span>Audio</span></div><div class="seg" data-aud style="margin-top:8px"><button data-v="sub" class="${p.audio !== "dub" ? "on" : ""}">Japanese with English subtitles</button><button data-v="dub" class="${p.audio === "dub" ? "on" : ""}">English voices</button></div></div>` : ""}
      ${showTv ? qrow("resTv", "TV shows: quality") + `<div class="rowsl">${sl("ep", mbf)}</div>` : ""}
      ${showMv ? qrow("resMv", "Movies: quality") + `<div class="rowsl">${sl("mv", gb)}</div>` : ""}
      <div class="hint" style="margin:0">"Only" means nothing else is ever downloaded for this choice, even if it is the only copy.</div>
      ${p.kind !== "anime" ? `<div class="setting"><div><div class="t">Prefer smaller files (x265)</div><div class="d">About half the size with the same picture quality.</div></div>${sw(p.x265, "x" + i, "Prefer smaller files (x265)")}</div>` : ""}
      ${p.kind !== "english" ? `<div class="setting"><div><div class="t">English subtitles needed</div><div class="d">Downloads that already have them are preferred. If there are none, the subtitle app finds English ones and keeps trying.</div></div>${sw(p.subs !== "off", "s" + i, "English subtitles needed")}</div>
      <div class="setting"><div><div class="t">Only download versions that already have English subtitles</div><div class="d">Stricter. Fewer results.</div></div>${sw(p.strictSubs, "t" + i, "Strict subtitles")}</div>` : ""}</div>`;
  }).join("");
}
function bindProfileCards(list, redraw) {
  $$("[data-pi]").forEach(card => {
    const i = +card.dataset.pi, p = list[i];
    $$("input[type=range]", card).forEach(r => r.oninput = () => { p[r.dataset.pk] = +r.value; const b = $(`[data-v="${r.dataset.pk}"]`, card); b.textContent = r.dataset.pk.startsWith("ep") ? mbf(p[r.dataset.pk]) : (+p[r.dataset.pk]).toFixed(1) + " GB"; });
    $$("[data-res] button", card).forEach(b => b.onclick = () => { p[b.parentElement.dataset.res] = b.dataset.v; redraw(); });
    $$("[data-aud] button", card).forEach(b => b.onclick = () => { p.audio = b.dataset.v; redraw(); });
    const nm = $('[data-pk="name"]', card); if (nm) nm.oninput = () => { p.name = nm.value; };
    bindSwitch("x" + i, () => p.x265, v => p.x265 = v);
    bindSwitch("s" + i, () => p.subs !== "off", v => p.subs = v ? "required" : "off");
    bindSwitch("t" + i, () => p.strictSubs, v => p.strictSubs = v);
    $$("[data-lang]", card).forEach(ch => ch.onclick = () => { const k = ch.dataset.lang; if (p.langs.includes(k)) p.langs = p.langs.filter(x => x !== k); else { list.forEach(o => { if (o.kind === "world") o.langs = o.langs.filter(x => x !== k); }); p.langs.push(k); } redraw(); });
    const rm = $("[data-rmp]", card); if (rm) rm.onclick = () => { list.splice(i, 1); redraw(); };
  });
}
function routeRows(list, P) {
  const rows = [];
  const en = list.find(p => p.kind === "english") || list.find(p => p.kind === "world") || list[0];
  rows.push(["English titles", en.name]);
  const an = list.find(p => p.kind === "anime"); if (an) rows.push(["Anime", an.name]);
  for (const p of list.filter(p => p.kind === "world" && p.langs.length)) rows.push([p.langs.map(k => P[k]).join(", "), p.name]);
  const all = new Set(list.flatMap(p => p.langs)), loose = Object.keys(P).filter(k => !["english", "anime"].includes(k) && !all.has(k) && S.cfg.packs.includes(k));
  if (loose.length) rows.push([loose.map(k => P[k]).join(", "), en.name]);
  return rows.map(([a, b]) => `<div class="setting" style="padding:9px 0"><span class="d" style="margin:0">${esc(a)}</span><b>${esc(b)}</b></div>`).join("");
}
function drawProfiles() {
  const c = S.cfg, P = S.env.packs;
  $("#pcards").innerHTML = profileCards(c.profiles, P);
  $("#prail").innerHTML = `<div class="card"><h3 style="margin-bottom:12px">Where each request goes</h3>${routeRows(c.profiles, P)}<p class="hint">The request page picks the profile from the title's original language. Anything unassigned uses ${esc((c.profiles.find(p => p.kind === "english") || c.profiles[0]).name)}.</p></div><div class="card"><h3 style="margin-bottom:8px">How size limits work</h3><p class="hint" style="margin:0">Each limit only applies to its own choice and picture quality. Full seasons are checked one episode at a time.</p></div>`;
  bindProfileCards(c.profiles, drawProfiles);
}

/* ------------------------------------------------------------ screens */
const screens = {
  welcome() {
    shell("welcome", `<div style="max-width:760px;display:flex;flex-direction:column;gap:22px;padding-top:40px">
      <span class="eyebrow">Your own media server</span><h1>Search a title.<br>It arrives in your library.</h1>
      <p class="lead">Answer a few simple questions. The setup installs every app, connects them, and tries a real search before it says it is done.</p>
      <div class="actions" style="justify-content:flex-start;gap:16px;margin-top:10px"><button class="btn primary" id="next">Start setup ${ic("arrow")}</button><span class="hint" style="margin:0">Needs Docker. Works on Windows, Mac and Linux.</span></div></div>
      <div class="grid3" style="max-width:980px;margin-top:26px">
      <div class="card"><div class="icbox">${ic("drive")}</div><h3>Any way you store things</h3><p class="hint" style="margin-top:8px">One drive, or movies, shows, anime and downloads spread over several. Folders you already have stay where they are.</p></div>
      <div class="card"><div class="icbox">${ic("globe")}</div><h3>Your languages</h3><p class="hint" style="margin-top:8px">English, Malayalam, Tamil, Korean, Japanese and more. English subtitles are found for everything else.</p></div>
      <div class="card"><div class="icbox">${ic("download")}</div><h3>No uploading afterwards</h3><p class="hint" style="margin-top:8px">Each download is removed once it is in your library, so nothing keeps uploading and nothing takes up space.</p></div></div>`, "About 5 minutes of questions, then it does the rest.");
    wire();
  },

  async check() {
    shell("check", `${stepHead(2, "Checking this computer", "Making sure everything is ready before anything is installed.")}<div class="card" id="chk">Looking…</div>`, "Nothing is changed during the check.");
    const e = S.env, c = S.cfg;
    Object.assign(c, { hostOs: e.hostOs, uid: e.uid, gid: e.gid, tz: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC", hostAddress: location.hostname });
    const st = c.storage, root = (e.defaultMedia || "").replace(/\/$/, "");
    if (!st.base) st.base = e.defaultMedia || "";
    if (!st.downloads) st.downloads = root + "/torrents";
    st.libraries.forEach(l => { if (!l.path) l.path = root + "/" + DIRNAME[l.type]; });
    const used = new Set(Object.values(e.ports).map(v => v.port)); c.ports = {};
    for (const [k, v] of Object.entries(e.ports)) { let p = v.port; if (!v.free) { p += 1000; while (used.has(p)) p++; used.add(p); } c.ports[k] = p; }
    const moved = Object.entries(e.ports).filter(([, v]) => !v.free);
    try { const d = await api("/api/detect"); S.found = d.apps; S.needs = d.needs; } catch (e) { S.found = []; }
    const mineApps = (S.found || []).filter(a => !a.ours);
    const side = $(".steps"); if (side) side.innerHTML = stepItems("check");        // "Your apps" appears once something was found
    const sub = $(".eyebrow"); if (sub) sub.textContent = `Step 2 of ${VIS().length}`;
    const row = (ok, t, d) => `<div class="setting"><div><div class="t">${esc(t)}</div><div class="d">${esc(d)}</div></div><span class="pill ${ok ? "ok" : "bad"}">${ok ? "ready" : "needs attention"}</span></div>`;
    $("#chk").innerHTML = row(e.docker, "Docker", e.docker ? "Running, version " + e.dockerVersion : "Not reachable. Start Docker Desktop and reload.")
      + row(true, "Operating system", { win: "Windows", mac: "macOS", linux: "Linux" }[e.hostOs] || e.hostOs)
      + row(true, "Network ports", moved.length ? "Some ports were busy, so free ones were picked: " + moved.map(([k]) => k + " " + c.ports[k]).join(", ") : "All the ports it needs are free")
      + row(true, "Apps you already have", mineApps.length ? "Found " + [...new Set(mineApps.map(a => a.label))].join(", ") + ". You will choose next whether to keep using them." : "None found, everything will be installed new");
    $("#chk").insertAdjacentHTML("afterend", nav("Continue", !e.docker));
    wire();
  },

  mine() {
    const c = S.cfg, NEED = S.needs || {};
    const cands = {};                                   // app -> every container that looks like it
    (S.found || []).filter(a => !a.ours).forEach(a => (cands[a.app] = cands[a.app] || []).push(a));
    const apps = Object.keys(cands);
    S.mineState = S.mineState || {};
    apps.forEach(k => { S.mineState[k] = S.mineState[k] || { mode: "mine", container: cands[k][0].container, user: "", password: "", key: "", check: null }; });
    const pick = k => cands[k].find(a => a.container === S.mineState[k].container) || cands[k][0];
    shell("mine", `${stepHead(3, "Apps you already have", "These apps are already on this computer. You can keep using yours, or install a fresh copy beside yours. Nothing is changed on this page, and you will see every change before anything is touched.")}
      <div id="minelist"></div>${nav()}`, "Your apps are only looked at, never changed, until you say so on the next pages.");
    const need = a => {
      const f = [];
      if (a.app === "qbittorrent") f.push(["user", "Username for qBittorrent", "text"], ["password", "Password for qBittorrent", "password"]);
      else if (a.app === "jellyfin") f.push(["key", "Access key (in Jellyfin: Dashboard, then API Keys, then the + button)", "password"]);
      else if (a.keyFound === false) f.push(["key", "Access key (in the app: Settings, then General)", "password"]);
      return f;
    };
    const draw = () => {
      $("#minelist").innerHTML = apps.map(k => {
        const a = pick(k), st = S.mineState[k], fields = need(a);
        const pill = st.check ? `<span class="pill ${st.check.ok ? "ok" : "bad"}">${st.check.ok ? "works" + (st.check.version ? " (version " + esc(st.check.version) + ")" : "") : "could not connect"}</span>` : "";
        return `<div class="card" data-app="${k}"><div class="card-h"><h3>${esc(a.label)}</h3><span class="sub mono">${esc(String(a.image).split("/").pop())} · ${a.running ? "running" : "stopped"}</span></div>
          ${cands[k].length > 1 ? `<div class="field"><label>Which one</label><select class="input" data-sel="${k}">${cands[k].map(x => `<option value="${esc(x.container)}" ${x.container === a.container ? "selected" : ""}>${esc(x.container)}</option>`).join("")}</select></div>` : `<p class="hint mono" style="margin:0 0 10px">${esc(a.container)}</p>`}
          ${seg("sg-" + k, [["mine", "Use mine"], ["new", "Install a new one beside it"]], st.mode)}
          ${st.mode === "mine" ? `<div class="grid2" style="margin-top:14px">${fields.map(([f, l, t]) => `<div class="field"><label>${l}</label><input class="input" type="${t}" data-f="${k}:${f}" value="${esc(st[f] || "")}" autocomplete="off"></div>`).join("")}</div>
            <div style="display:flex;gap:10px;align-items:center;margin-top:12px"><button class="btn sm" data-chk="${k}">Test connection</button>${pill}<span class="hint" style="margin:0">${st.check && !st.check.ok ? esc(st.check.detail || "") : fields.length ? "" : "Nothing to type: it is found automatically."}</span></div>` : `<p class="hint">A new ${esc(a.label)} will be installed next to yours. Yours is not touched.</p>`}</div>`;
      }).join("") + `<div style="margin-top:8px"><button class="btn" id="chkall">Test every connection</button></div>`;
      apps.forEach(k => bindSeg("#sg-" + k, () => S.mineState[k].mode, v => { S.mineState[k].mode = v; draw(); }));
      $$("[data-sel]").forEach(sel => sel.onchange = () => { S.mineState[sel.dataset.sel].container = sel.value; S.mineState[sel.dataset.sel].check = null; draw(); });
      $$("[data-f]").forEach(i => i.oninput = () => { const [app, f] = i.dataset.f.split(":"); S.mineState[app][f] = i.value.trim(); S.mineState[app].check = null; });
      const check = async k => {
        const st = S.mineState[k], a = pick(k);
        try { st.check = await api("/api/adopt/check", { app: k, container: a.container, port: a.port, key: st.key, user: st.user, password: st.password }); }
        catch (e) { st.check = { ok: false, detail: e.message }; }
      };
      $$("[data-chk]").forEach(b => b.onclick = async () => { b.disabled = true; b.textContent = "Checking…"; await check(b.dataset.chk); draw(); });
      $("#chkall").onclick = async e => { e.target.disabled = true; e.target.textContent = "Checking…"; for (const k of apps) if (S.mineState[k].mode === "mine") await check(k); draw(); };
    };
    draw();
    wire(() => {
      const adopt = {};
      for (const k of apps) {
        const a = pick(k), st = S.mineState[k];
        if (st.mode !== "mine") continue;
        if (!(st.check && st.check.ok)) return toast("Please test the connection to " + a.label + " first, or choose to install a new one.");
        adopt[k] = { container: a.container, port: a.port, ...(st.key ? { key: st.key } : {}), ...(st.user ? { user: st.user, password: st.password } : {}) };
        if (["jellyfin", "seerr", "bazarr"].includes(k)) c.services[k] = true;
      }
      c.adopt = adopt; c.skipGroups = []; S.preview = null;
      goRel(1);
    });
  },

  async changes() {
    const c = S.cfg;
    shell("changes", `${stepHead(9, "What would change in your apps", "Here is everything this setup wants to change in the apps you already have, next to how they are set today. Nothing has been changed yet. Turn a switch off to keep that part exactly as it is.")}
      <div id="pv"><div class="card"><div class="card-h"><h3>Looking at your apps…</h3></div><p class="hint" id="pvlog">This only looks, it changes nothing. It can take a minute or two.</p><div class="prog"><i style="width:30%"></i></div></div></div>`, "Nothing has been changed yet.");
    const key = JSON.stringify([c.adopt, c.packs, c.profiles, c.settings, c.quality, c.storage, c.kinds, c.notify, c.livetv && c.livetv.enabled, c.subtitleLangs]);
    if (!S.preview || S.preview.key !== key) {
      S.preview = null;
      try { await api("/api/preview", c); } catch (e) { if (!/already running/i.test(e.message)) { $("#pv").innerHTML = `<div class="note bad">${ic("info")}<div>${esc(e.message)}</div></div>${nav()}`; return wire(); } }
      for (;;) {
        await new Promise(r => setTimeout(r, 1800));
        let st; try { st = await api("/api/preview/status"); } catch (e) { continue; }
        const el = $("#pvlog"); if (!el) return;       // the person left this page
        el.textContent = (st.log || []).slice(-1)[0] || "Looking…";
        if (st.done) { S.preview = { key, ...(st.result || {}), error: st.error }; S.offInit = false; break; }
      }
    }
    const P = S.preview;
    if (P.error || P.ok === false) {
      $("#pv").innerHTML = `<div class="note bad">${ic("info")}<div>${esc(P.error || (P.missing || []).join("; ") || "Could not read your apps.")}</div></div>${nav()}`;
      return wire();
    }
    const groups = P.groups || [];
    if (!S.offInit) { S.off = new Set(c.skipGroups.length ? c.skipGroups : groups.filter(g => !g.default).map(g => g.id)); S.offInit = true; }
    const open = new Set();
    const blocked = g => (g.depends || []).filter(d => S.off.has(d) && groups.some(x => x.id === d));
    const rowsHtml = g => g.changes.map(ch => `<div style="margin:8px 0"><b>${esc({ create: "Will add:", update: "Will change:", delete: "Will remove:" }[ch.kind] || ch.kind)}</b> <span class="mono">${esc(ch.what)}</span>${ch.rows.length ? `<table class="diff"><tr><th>What</th><th>How it is now</th><th>After setup</th></tr>${ch.rows.map(r => `<tr><td class="mono">${esc(r[0])}</td><td class="mono">${esc(r[1])}</td><td class="mono">${esc(r[2])}</td></tr>`).join("")}${ch.more ? `<tr><td colspan="3" class="hint">and ${ch.more} more</td></tr>` : ""}</table>` : ""}</div>`).join("");
    const draw = () => {
      const apps = [...new Set(groups.map(g => g.app))];
      const total = groups.filter(g => !g.same).length, kept = groups.filter(g => !g.same && S.off.has(g.id)).length;
      $("#pv").innerHTML = (P.problems || []).map(p => `<div class="note warn" style="margin-bottom:10px">${ic("info")}<div>${esc(p)}</div></div>`).join("")
        + apps.map(app => {
          const gs = groups.filter(g => g.app === app), diff = gs.filter(g => !g.same), same = gs.filter(g => g.same);
          return `<div class="card"><div class="card-h"><h3>${esc(app)} <span class="sub">your own</span></h3><div style="display:flex;gap:8px"><button class="btn sm" data-all="${esc(app)}:1">Change everything</button><button class="btn sm" data-all="${esc(app)}:0">Keep everything of mine</button></div></div>
            ${diff.length ? diff.map(g => { const b = blocked(g), on = !S.off.has(g.id) && !b.length;
              return `<div class="setting" style="align-items:flex-start"><div style="flex:1"><div class="t">${esc(g.title)} <span class="pill ${on ? "blue" : ""}">${esc(g.summary)}</span></div><div class="d">${esc(g.why)}</div>${g.caution ? `<div class="d" style="color:var(--note-warn)">${esc(g.caution)}</div>` : ""}${b.length ? `<div class="d" style="color:var(--note-warn)">Left alone because you chose to keep your own quality choices.</div>` : ""}
                <a href="#" class="linkish" data-det="${esc(g.id)}">${open.has(g.id) ? "Hide" : "Show exactly what changes"}</a><div class="det" ${open.has(g.id) ? "" : "hidden"}>${open.has(g.id) ? rowsHtml(g) : ""}</div></div>
                <div style="text-align:center;min-width:92px">${sw(on, "sw-" + g.id, g.title)}<div class="hint" style="margin:4px 0 0">${on ? "Setup will change this" : "Keep mine as it is"}</div></div></div>`; }).join("") : `<p class="hint" style="margin:0">Nothing to change here: everything is already set the way this setup would do it.</p>`}
            ${same.length && diff.length ? `<p class="hint" style="margin:12px 0 0">Already set the way this setup would do it: ${esc(same.map(g => g.title).join(", "))}.</p>` : ""}</div>`;
        }).join("")
        + `<div class="note ${kept ? "ok" : ""}">${ic("check")}<div>${total - kept} of ${total} parts of your apps will be changed${kept ? `, and ${kept} will stay exactly as you have them` : ""}. You can go back and change your mind before anything happens.</div></div>${nav("Continue")}`;
      groups.forEach(g => { const b = $("#sw-" + g.id); if (b) b.onclick = () => { if (blocked(g).length) return; S.off.has(g.id) ? S.off.delete(g.id) : S.off.add(g.id); draw(); }; });
      $$("[data-det]").forEach(a => a.onclick = e => { e.preventDefault(); const id = a.dataset.det; open.has(id) ? open.delete(id) : open.add(id); draw(); });
      $$("[data-all]").forEach(b => b.onclick = () => { const [app, v] = b.dataset.all.split(":"); groups.filter(g => g.app === app && !g.same).forEach(g => v === "1" ? S.off.delete(g.id) : S.off.add(g.id)); draw(); });
      wire(() => { c.skipGroups = [...S.off]; goRel(1); });
    };
    draw();
  },

  async storage() {
    const c = S.cfg, st = c.storage, e = S.env;
    shell("storage", `${stepHead(3, "Where is everything kept?", "Choose the folder for each kind of media. Use one drive or as many as you have. Folders you already have are used as they are.")}
      <div class="cols"><div class="grow">
        <div class="card"><div class="card-h"><h3>How are your drives arranged?</h3></div>${seg("sm", [["single", "One drive for everything"], ["multi", "Separate drives and folders"]], st.mode)}
        <p class="hint">Pick separate if movies, shows, anime or downloads are on different disks, or if you already have a library somewhere.</p></div>
        <div id="body"></div><div id="warn"></div>${nav()}
      </div><aside class="rail" id="rail"></aside></div>`, "Nothing is moved, renamed or deleted in folders you already have.");
    const allPaths = () => st.mode === "single" ? [st.base] : [st.downloads, ...st.libraries.map(l => l.path)];
    const ensureChecked = async () => { await Promise.all(allPaths().filter(p => p && !S.pc[p]).map(checkPath)); await refreshPlan(); };
    bindSeg("#sm", () => st.mode, v => { st.mode = v; (async () => { await ensureChecked(); drawBody(); })(); drawBody(); });

    function linkNote(key) {
      if (st.mode === "single" || !S.plan) return "";
      const m = /^lib(\d+)$/.exec(key); if (!m) return "";
      const l = S.plan.libs[+m[1]]; if (!l) return "";
      return l.linked ? `<span class="okc">same drive as downloads: instant, uses no extra space</span>` : `<span class="warnc">different drive: copied across, then the download is removed</span>`;
    }
    function pathRow(label, icon, key, p, removable) {
      const i = S.pc[p];
      return `<div class="lib"><div class="kind"><span class="ic">${ic(icon)}</span>${esc(label)}</div>
        <div class="where"><input class="input mono" value="${esc(p)}" data-path="${esc(key)}" spellcheck="false" aria-label="${esc(label)} folder">${meterHtml(i)}${pathMeta(i, linkNote(key))}</div>
        <div style="display:flex;gap:8px"><button class="btn sm" data-browse="${esc(key)}">${ic("folder", "s")}Browse</button>${removable ? `<button class="btn sm danger" data-rm="${esc(key)}" aria-label="Remove ${esc(label)}">${ic("x", "s")}</button>` : ""}</div></div>`;
    }
    function drawBody() {
      $("#body").innerHTML = st.mode === "single"
        ? `<div class="card"><div class="card-h"><h3>Media folder</h3><span class="pill blue">one place for downloads and your library</span></div>${pathRow("Media", "drive", "base", st.base, false)}
            <p class="hint">Inside it the setup makes <span class="mono">torrents</span>, <span class="mono">media/Movies</span>, <span class="mono">media/TV Shows</span> and <span class="mono">media/Anime</span>. Downloads and your library are on one drive, so finished files are linked, not copied.</p></div>`
        : `<div class="card"><div class="card-h"><h3>Downloads</h3><span class="pill blue">unfinished downloads</span></div>${pathRow("Downloads", "download", "dl", st.downloads, false)}</div>
           <div class="card"><div class="card-h"><h3>Libraries</h3><span class="sub">Each folder shows how finished files get there</span></div>${st.libraries.map((l, i) => pathRow(KIND[l.type][1], KIND[l.type][0], "lib" + i, l.path, true)).join("")}
           <div style="margin-top:14px;display:flex;gap:8px;flex-wrap:wrap"><span class="hint" style="margin:0 6px 0 0;align-self:center">Add another folder for</span>${["movies", "tv", "anime"].map(k => `<button class="btn sm" data-add="${k}">${ic("plus", "s")}${KIND[k][1]}</button>`).join("")}</div></div>`;
      bindRows(); drawRail(); drawWarn();
    }
    const acc = key => key === "base" ? [() => st.base, v => st.base = v] : key === "dl" ? [() => st.downloads, v => st.downloads = v] : (l => [() => l.path, v => l.path = v])(st.libraries[+key.slice(3)]);
    function bindRows() {
      $$("[data-path]").forEach(inp => {
        const [, set] = acc(inp.dataset.path);
        inp.onchange = async () => { const v = inp.value.trim().replace(/\\/g, "/"); set(v); await checkPath(v); await refreshPlan(); drawBody(); };
      });
      $$("[data-browse]").forEach(b => b.onclick = () => {
        const key = b.dataset.browse, [get, set] = acc(key);
        const label = key === "base" ? "Choose the media folder" : key === "dl" ? "Choose the downloads folder" : "Choose a folder for " + KIND[st.libraries[+key.slice(3)].type][1];
        openBrowser(label, get(), async p => { set(p); await checkPath(p); await refreshPlan(); drawBody(); });
      });
      $$("[data-rm]").forEach(b => b.onclick = async () => { st.libraries.splice(+b.dataset.rm.slice(3), 1); await refreshPlan(); drawBody(); });
      $$("[data-add]").forEach(b => b.onclick = async () => {
        const k = b.dataset.add, root = (st.downloads || e.defaultMedia || "").replace(/\/[^/]*$/, "") || e.defaultMedia;
        st.libraries.push({ type: k, path: root + "/" + DIRNAME[k] });
        await checkPath(st.libraries.at(-1).path); await refreshPlan(); drawBody();
      });
    }
    function drawRail() {
      let h;
      if (st.mode === "single" || !S.plan) h = `<div class="card"><h3 style="margin-bottom:10px">How it works</h3><div class="diagram"><span class="node">torrents</span><span class="arrow">&#8594;</span><span class="node">media</span></div><p class="hint" style="margin-top:10px">Same drive: files are linked, so they use no extra space and arrive instantly.</p></div>`;
      else h = `<div class="card"><h3 style="margin-bottom:14px">Your layout</h3><div style="display:flex;flex-direction:column;gap:12px">${S.plan.libs.map((l, i) => `${i ? '<div class="sep" style="margin:4px 0"></div>' : ""}<div><div class="mono" style="color:var(--mute)">${esc(KIND[l.type][1])}</div><div class="diagram" style="margin-top:6px"><span class="node">downloads</span><span class="arrow">&#8594;</span><span class="node">${esc(l.host.split("/").filter(Boolean).slice(-2).join("/"))}</span></div><div class="hint" style="margin-top:6px">${l.linked ? "Linked: instant, no extra space" : "Copied across, then the download is removed"}</div></div>`).join("")}</div></div>
        <div class="card"><h3 style="margin-bottom:10px">Good to know</h3><p class="hint" style="margin:0">Copying between drives needs room for the download and the finished file for a short time. Keep a few GB free on the downloads drive.</p></div>`;
      const inside = S.plan ? `<div class="card"><h3 style="margin-bottom:8px">How the apps see your folders</h3><p class="hint" style="margin:0 0 12px">Every app sees each folder at the same place, so they always agree on where files are. Bazarr is told about each library folder automatically. If you change a drive later, start the setup again and this is updated.</p>${[{ host: S.plan.downloadsHost, path: S.plan.downloads, type: "dl" }, ...S.plan.libs].map(l => `<div class="setting" style="padding:8px 0;gap:10px;flex-wrap:wrap"><span class="d mono" style="margin:0;word-break:break-all">${esc(l.host)}</span><b class="mono" style="font-size:12.5px;word-break:break-all">${esc(l.path)}</b></div>`).join("")}</div>` : "";
      $("#rail").innerHTML = h + inside;
    }
    function drawWarn() {
      const out = [];
      for (const p of allPaths()) {
        const i = S.pc[p]; if (!i) continue;
        if (i.freeBytes != null && i.totalBytes && i.freeBytes < 60e9) out.push(`<div class="note warn">${ic("info")}<div><b>${esc(p.split("/").filter(Boolean).slice(-2).join("/"))}</b> has only ${fmt(i.freeBytes)} free.</div></div>`);
        if (i.ok === false && i.error) out.push(`<div class="note bad">${ic("info")}<div>${esc(i.error)}</div></div>`);
      }
      $("#warn").innerHTML = out.join("");
    }
    drawBody();
    await ensureChecked(); drawBody();
    wire(() => {
      if (allPaths().some(p => !p)) return toast("Fill in every folder first.");
      if (allPaths().some(p => S.pc[p] && S.pc[p].ok === false)) return toast("Fix the folder that shows an error first.");
      goRel(1);
    });
  },

  watch() {
    const c = S.cfg, P = S.env.packs;
    const langKeys = Object.keys(P).filter(k => k !== "anime");
    const SUBS = [["en", "English"], ["ml", "Malayalam"], ["ta", "Tamil"], ["hi", "Hindi"], ["si", "Sinhala"], ["ko", "Korean"], ["ja", "Japanese"]];
    const presets = [
      ["English shows and movies", { kinds: ["tv", "movies"], packs: ["english"] }],
      ["English shows and anime (English subtitles)", { kinds: ["tv"], packs: ["english", "anime"], animeAudio: "sub" }],
      ["English, anime and Korean", { kinds: ["tv", "movies"], packs: ["english", "anime", "korean"], animeAudio: "sub" }],
      ["South Indian, Asian and English", { kinds: ["tv", "movies"], packs: [...PACKS_DEFAULT], animeAudio: "sub" }],
      ["Everything", { kinds: ["tv", "movies"], packs: Object.keys(P), animeAudio: "sub" }],
    ];
    const tile = (k, icon, t, d, on, attr) => `<div class="tile ${on ? "on" : ""}" ${attr}="${k}" tabindex="0" role="checkbox" aria-checked="${on}"><span class="check">${ic("check", "s")}</span><div class="ic">${ic(icon, "l")}</div><b>${t}</b><small>${d}</small></div>`;
    const draw = () => {
      $("#presets").innerHTML = presets.map(([n], i) => `<span class="chip" data-pre="${i}" tabindex="0">${esc(n)}</span>`).join("");
      $("#tiles").innerHTML = tile("tv", "tv", "TV series", "New episodes download as they come out", c.kinds.includes("tv"), "data-kind") + tile("movies", "film", "Movies", "Search for a title and it downloads", c.kinds.includes("movies"), "data-kind") + tile("anime", "spark", "Anime", "Shows and films, with careful rules for anime groups", c.packs.includes("anime"), "data-anime");
      $("#aud").classList.toggle("hidden", !c.packs.includes("anime"));
      $("#langs").innerHTML = langKeys.map(k => `<span class="chip lang ${c.packs.includes(k) ? "on" : ""}" data-k="${k}" tabindex="0">${c.packs.includes(k) ? '<span class="dot"></span>' : ""}${esc(P[k])}</span>`).join("");
      $("#nlang").textContent = c.packs.filter(k => k !== "anime").length + " selected";
      $$("[data-pre]").forEach(el => el.onclick = () => { const p = presets[+el.dataset.pre][1]; c.kinds = [...p.kinds]; c.packs = [...p.packs]; if (p.animeAudio) c.animeAudio = p.animeAudio; draw(); });
      $$("[data-kind]").forEach(el => onKey(el, () => { toggleIn(c.kinds, el.dataset.kind); draw(); }));
      $$("[data-anime]").forEach(el => onKey(el, () => { toggleIn(c.packs, "anime"); draw(); }));
      $$(".chip.lang").forEach(el => el.onclick = () => { toggleIn(c.packs, el.dataset.k); draw(); });
      $("#sublangs").innerHTML = SUBS.map(([k, n]) => `<span class="chip sub ${c.subtitleLangs.includes(k) ? "on" : ""}" data-k="${k}" tabindex="0">${c.subtitleLangs.includes(k) ? '<span class="dot"></span>' : ""}${n}</span>`).join("");
      $$(".chip.sub").forEach(el => el.onclick = () => { if (el.dataset.k === "en") return; toggleIn(c.subtitleLangs, el.dataset.k); draw(); });
      const reg = c.packs.some(p => ["tamil", "malayalam", "telugu", "kannada", "hindi"].includes(p));
      $("#built").innerHTML = [["Profiles", ["TV Shows", c.packs.includes("anime") ? "Anime" : "", "Movies", c.packs.includes("anime") ? "Anime Movies" : ""].filter(Boolean).join(", ")], ["Release rules", "Trusted quality rules, original voices, poor groups turned down"], ["Indexers", "General" + (c.packs.includes("anime") ? " + anime" : "") + (c.packs.includes("korean") ? " + Korean" : "") + (reg ? " + Tamil/Malayalam forums" : "")], ["Subtitles", c.subtitleLangs.map(k => SUBS.find(s => s[0] === k)?.[1]).join(", ")]].map(([t, d]) => `<div class="setting" style="padding:10px 0"><div><div class="t">${t}</div><div class="d">${esc(d)}</div></div></div>`).join("");
    };
    shell("watch", `${stepHead(4, "What do you watch?", "Start with a quick choice or tick things yourself. Everything is built from your answers here.")}
      <div class="cols"><div class="grow">
        <div class="card"><div class="card-h"><h3>Quick choices</h3><span class="sub">One click, then change what you like</span></div><div class="chips" id="presets"></div></div>
        <div class="grid3" id="tiles"></div>
        <div class="card" id="aud"><div class="card-h"><h3>Anime audio</h3></div>${seg("sa", [["sub", "Japanese voices with English subtitles"], ["dub", "English voices"]], c.animeAudio)}<p class="hint">Subtitles come with the download. If they are missing, the subtitle app finds them.</p></div>
        <div class="card"><div class="card-h"><h3>Languages</h3><span class="sub" id="nlang"></span></div><div class="chips" id="langs"></div><p class="hint">Shows in other languages keep their original voices. English subtitles are found automatically.</p></div>
        <div class="card"><div class="card-h"><h3>Subtitles</h3></div><div class="chips" id="sublangs"></div></div>
        ${nav()}</div>
      <aside class="rail"><div class="card"><h3 style="margin-bottom:12px">What this does</h3><div id="built"></div></div></aside></div>`, "You can change all of this later in the dashboard.");
    bindSeg("#sa", () => c.animeAudio, v => c.animeAudio = v);
    draw();
    wire(() => (c.kinds.length || c.packs.includes("anime")) ? goRel(1) : toast("Pick at least one thing to watch."));
  },

  livetv() {
    const c = S.cfg;
    if (!c.livetv) c.livetv = LT_DEFAULT();
    shell("livetv", `${stepHead(5, "Live TV and sports", "Optional. Watch live channels and sports in Jellyfin, next to your own library. Skip it if you only want movies and shows.")}
      <div class="cols"><div class="grow"><div class="card"><div id="ltbox">Loading…</div></div>${nav()}</div>
      <aside class="rail"><div class="card"><h3 style="margin-bottom:12px">How it works</h3><p class="hint" style="margin:0">The setup makes a channel list from free public lists, tests every channel, and adds it to Jellyfin with a TV guide. The list updates itself every day, so broken channels disappear and new ones appear.</p><p class="hint">Some channels only work in their own country.</p></div></aside></div>`);
    ltEditor($("#ltbox"), c.livetv);
    wire();
  },

  profiles() {
    const c = S.cfg, s = c.settings;
    ensureProfiles();
    shell("profiles", `${stepHead(6, "Profiles", "A quality choice decides how good the picture should be, how big a file may be, and whether English subtitles are needed. Requests are matched to a choice by language.")}
      <div class="cols"><div class="grow"><div id="pcards"></div>
        <div class="card" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap"><div><h3>Add a quality choice</h3><div class="hint" style="margin:2px 0 0">Give a language its own picture quality and size limit, for example Malayalam in 1080p with a bigger limit.</div></div><button class="btn" id="addp">${ic("plus", "s")}Add profile</button></div>
        <div class="card"><div class="card-h"><h3>Rules for every choice</h3></div>
          <div class="setting"><div><div class="t">Replace files when a better version appears</div><div class="d">Off keeps what you have and avoids downloading again.</div></div>${sw(s.upgrade, "sup", "Replace files with better versions")}</div>
          <div class="setting"><div><div class="t">Accept downloads with English subtitles built into the picture</div><div class="d">Common for Tamil, Malayalam and Korean downloads (they are called ESub).</div></div>${sw(s.hardSubs, "shs", "Accept subtitles built into the picture")}</div></div>
        ${nav()}</div>
      <aside class="rail" id="prail"></aside></div>`, "Each choice has its own quality, size limit and subtitle rule.");
    bindSwitch("sup", () => s.upgrade, v => s.upgrade = v); bindSwitch("shs", () => s.hardSubs, v => s.hardSubs = v);
    $("#addp").onclick = () => { c.profiles.push(newProfile(c)); drawProfiles(); };
    drawProfiles();
    wire(() => c.profiles.every(p => p.name.trim()) ? goRel(1) : toast("Every choice needs a name."));
  },

  downloads() {
    const c = S.cfg, s = c.settings, d = c.qbit;
    shell("downloads", `${stepHead(7, "How should downloads work?", "qBittorrent does the downloading. These settings decide how fast it goes, how many at once, and how picky it is.")}
      <div class="cols"><div class="grow">${downloadSettings(s)}
        <div class="card"><div class="card-h"><h3>qBittorrent login</h3><div class="chips"><span class="chip ${d.vuetorrent ? "on" : ""}" id="vt" tabindex="0">${d.vuetorrent ? '<span class="dot"></span>' : ""}VueTorrent interface</span></div></div>
          <div class="grid2"><div class="field"><label for="qu">Username</label><input class="input" id="qu" value="${esc(d.username)}" autocomplete="off"></div>${pwField("qp", d.password, "Password")}</div></div>
        ${nav()}</div>
      <aside class="rail">${noSeedCard()}<div class="card"><h3 style="margin-bottom:8px">Not finding anything?</h3><p class="hint" style="margin:0">Lower the minimum to 1. You can change any of this later without installing again.</p></div></aside></div>`, "These starting values come from a setup that has run well for months.");
    bindDownloadSettings(s); bindPw();
    $("#vt").onclick = e => { d.vuetorrent = !d.vuetorrent; e.currentTarget.classList.toggle("on", d.vuetorrent); };
    wire(() => { d.username = $("#qu").value.trim(); d.password = $("#qp").value; if (!d.username || d.password.length < 4) return toast("Please enter a username and a password of at least 4 characters."); goRel(1); });
  },

  apps() {
    const c = S.cfg, sv = c.services, l = c.login;
    if (c.autoApprove === undefined) c.autoApprove = true;
    shell("apps", `${stepHead(8, "Apps and accounts", "Choose what else to install and set the main login used by the apps.")}
      <div class="cols"><div class="grow">
        <div class="grid3" id="svc"></div>
        <div id="smbbox"></div>
        <div id="tsbox"></div>
        <div id="cvbox"></div>
        <div class="card"><div class="setting"><div><div class="t">Approve requests automatically</div><div class="d">Anyone who signs in to the request page gets their downloads straight away. Turn this off to approve each one yourself.</div></div>${sw(c.autoApprove !== false, "saa", "Approve requests automatically")}</div></div>
        <div class="card"><div class="card-h"><h3>Helper for protected websites</h3><span class="sub" id="hw"></span></div><p class="hint" style="margin:0 0 14px">Many search sites make you prove you are not a robot. This helper opens them in a hidden browser for you. We tested all three on the same sites. Which is best depends on your computer.</p><div class="grid3" id="solvers"></div><div id="solvernote"></div></div>
        <div class="card"><div class="card-h"><h3>Main login</h3><span class="sub">Jellyfin, Seerr, Sonarr, Radarr, Prowlarr</span></div><div class="grid2"><div class="field"><label for="lu">Username</label><input class="input" id="lu" value="${esc(l.username)}" autocomplete="off"></div>${pwField("lp", l.password, "Password")}</div></div>
        ${c.packs.includes("anime") ? `<div class="card"><div class="card-h"><h3>AniDB (optional)</h3><span class="sub">Finds better subtitles for anime</span></div><p class="hint" style="margin:0 0 12px">Bazarr can use a website called AniDB to match anime to the right show. You need to register yourself for free. It takes a few minutes:</p><ol class="hint" style="margin:0 0 14px;padding-left:20px;line-height:1.8"><li>Create a free account at <a href="https://anidb.net" target="_blank" rel="noopener" style="color:var(--accent-text)">anidb.net</a> and log in.</li><li>Open your profile's <b>API Client</b> page and create a project (any name).</li><li>From the project, add a client: choose <b>HTTP API</b>, enter a unique name in <b>lowercase</b>, and version <b>1</b>.</li><li>Enter that client name and version below. Leave both empty to skip; anime still works without it.</li></ol><div class="grid2"><div class="field"><label for="adn">Client name (lowercase)</label><input class="input" id="adn" value="${esc(c.subtitles.anidb_client || "")}" placeholder="my-media-server"></div><div class="field"><label for="adv">Client version</label><input class="input" id="adv" value="${esc(c.subtitles.anidb_ver || "1")}"></div></div></div>` : ""}
        <div class="card"><div class="card-h"><h3>Notifications</h3><span class="sub">Optional</span></div><p class="hint" style="margin:0 0 12px">Get a message in your chat app when something downloads, gets a better version, or needs you.</p><div id="ntbox"></div></div>
        <div class="card"><div class="card-h"><h3>Subtitle accounts</h3><span class="sub">Optional</span></div><p class="hint" style="margin:0 0 12px">Seven free websites work without an account. Adding OpenSubtitles.com, SubDL or SubSource gives better results.</p><div class="grid2"><div class="field"><label for="osu">OpenSubtitles username</label><input class="input" id="osu" value="${esc(c.subtitles.opensubtitlescom_user || "")}"></div><div class="field"><label for="osp">OpenSubtitles password</label><input class="input" id="osp" type="password" value="${esc(c.subtitles.opensubtitlescom_pass || "")}"></div><div class="field"><label for="sdk">SubDL access key (free)</label><input class="input" id="sdk" value="${esc(c.subtitles.subdl_key || "")}"></div><div class="field"><label for="ssk">SubSource access key (free)</label><input class="input" id="ssk" value="${esc(c.subtitles.subsource_key || "")}"></div></div></div>
        ${nav("Review")}</div></div>`, "Ports are chosen for you and shown at the end.");
    const smbPort = () => (c.ports && c.ports.samba) || 445;
    async function drawShare() {
      const box = $("#smbbox"); if (!box) return;
      if (!sv.samba) { box.innerHTML = ""; return; }
      if (!c.samba) c.samba = { user: "media", password: genPw(), shares: null };
      const sm = c.samba;
      if (!sm.shares) { box.innerHTML = `<div class="card"><p class="hint" style="margin:0">Looking for your folders and drives…</p></div>`; try { sm.shares = (await api("/api/samba/suggest", { storage: c.storage })).shares; } catch (e) { sm.shares = []; } }
      const fsNote = x => { const n = []; if (x.fs) n.push(x.fs); if (x.totalBytes) n.push(fmt(x.totalBytes)); if (/^(exFAT|FAT)$/.test(x.fs || "")) n.push("cannot link files, see the file sharing guide"); return n.join(", "); };
      const rows = sm.shares.map((x, i) => `<div class="setting" style="align-items:center;gap:12px;${x.on === false ? "opacity:.55" : ""}"><label class="hint" style="margin:0;white-space:nowrap"><input type="checkbox" data-so="${i}" ${x.on === false ? "" : "checked"}> Share</label><div style="flex:1;min-width:0"><input class="input" data-sn="${i}" value="${esc(x.name)}" aria-label="Share name" spellcheck="false"><div class="hint mono" style="margin:4px 0 0;overflow-wrap:anywhere">${esc(x.path)}${fsNote(x) ? ` <span style="font-family:inherit">(${esc(fsNote(x))})</span>` : ""}</div></div><label class="hint" style="margin:0;white-space:nowrap"><input type="checkbox" data-sr="${i}" ${x.readOnly ? "checked" : ""}> Read only</label><button class="btn sm danger" data-sx="${i}" aria-label="Remove ${esc(x.name)}">${ic("x", "s")}</button></div>`).join("");
      box.innerHTML = `<div class="card"><div class="card-h"><h3>File sharing</h3><span class="sub">Optional</span></div>
        <p class="hint" style="margin:0 0 14px">Your folders and drives show up on your home network, so you can open them from Windows, Mac and phones. Everyone uses the one login below. Nobody can open anything without it.</p>
        ${smbPort() !== 445 ? `<div class="note warn" style="margin-bottom:14px">${ic("info")}<div>Another file sharing program on this computer already uses the usual port, so ${smbPort()} is used instead. Windows cannot connect to it. Mac and Linux can.</div></div>` : ""}
        <div class="grid2"><div class="field"><label for="smu">User name</label><input class="input" id="smu" value="${esc(sm.user)}" autocomplete="off" spellcheck="false"></div>${pwField("smp", sm.password, "Password (8 or more characters)")}</div>
        <h4 style="margin:18px 0 6px">What to share</h4>${rows || `<p class="hint">Nothing found yet. Add a folder.</p>`}
        <div style="margin-top:12px"><button class="btn sm" id="smadd">${ic("plus", "s")}Add a folder</button></div>
        <p class="hint" style="margin:14px 0 0">Only your home network and Tailscale can connect. Never open this to the internet from your router.</p></div>`;
      bindPw();
      $("#smu").onchange = e => sm.user = e.target.value.trim().toLowerCase();
      $("#smp").onchange = e => sm.password = e.target.value;
      $$("[data-sn]").forEach(i => i.onchange = () => sm.shares[+i.dataset.sn].name = i.value.trim());
      $$("[data-sr]").forEach(i => i.onchange = () => sm.shares[+i.dataset.sr].readOnly = i.checked);
      $$("[data-so]").forEach(i => i.onchange = () => { sm.shares[+i.dataset.so].on = i.checked; drawShare(); });
      $$("[data-sx]").forEach(b => b.onclick = () => { sm.shares.splice(+b.dataset.sx, 1); drawShare(); });
      $("#smadd").onclick = () => openBrowser("Choose a folder to share", "", p => { if (!p || sm.shares.some(x => x.path === p)) return; const base = p.replace(/\/+$/, "").split("/").pop() || "Share"; let n = base, k = 2; while (sm.shares.some(x => x.name.toLowerCase() === n.toLowerCase())) n = base + " " + k++; sm.shares.push({ name: n, path: p, readOnly: false, kind: "drive" }); drawShare(); });
    }
    function drawCv() {
      const box = $("#cvbox"); if (!box) return;
      box.innerHTML = !sv.kapowarr ? "" : `<div class="card"><div class="card-h"><h3>Kapowarr: ComicVine key</h3><span class="sub">Optional</span></div>
        <p class="hint" style="margin:0 0 12px">Kapowarr finds comic details on ComicVine, which needs a personal key. Get one free at comicvine.gamespot.com/api, then paste it here. You can also add it later in Kapowarr under Settings.</p>
        <div class="field"><label for="cvk">ComicVine API key</label><input class="input" id="cvk" value="${esc((S.cfg.comics || {}).comicvine_key || "")}"></div></div>`;
      const i = $("#cvk"); if (i) i.oninput = () => { S.cfg.comics = { ...(S.cfg.comics || {}), comicvine_key: i.value.trim() }; };
    }
    function drawTs() {
      const box = $("#tsbox"); if (!box) return;
      const t = S.env.tailscale || {};
      box.innerHTML = !sv.tailscale ? "" : `<div class="card"><div class="card-h"><h3>Private HTTPS addresses</h3><span class="sub">Optional</span></div>
        <p class="hint" style="margin:0 0 12px">Every app gets an address like <span class="mono">https://${esc(t.dns || "your-server.your-network.ts.net")}:18096</span> that works from any of your devices with Tailscale, at home or away, with a proper padlock. Nothing is opened on your router.</p>
        <ol class="hint" style="margin:0;padding-left:20px;line-height:1.8"><li>In the Tailscale admin page, open DNS and press <b>Enable HTTPS</b> once. The setup cannot do this for you.</li><li>Homepage links are changed to these addresses automatically.</li><li>Run the setup again after adding apps, and the new ones get an address too.</li></ol></div>`;
    }
    const draw = () => { $("#svc").innerHTML = Object.entries(SVC).map(([k, [i, t, d]]) => `<div class="tile ${sv[k] ? "on" : ""}" data-s="${k}" tabindex="0" role="checkbox" aria-checked="${sv[k]}"><span class="check">${ic("check", "s")}</span><div class="ic">${ic(i, "l")}</div><b>${t}</b><small>${d}</small></div>`).join(""); $$("[data-s]").forEach(el => onKey(el, () => { const k = el.dataset.s; if (k === "samba" && S.env.hostOs !== "linux") return toast("File sharing is only offered when this setup runs on Linux. On Windows and Mac, use the sharing built into the system."); if (k === "tailscale" && !sv.tailscale && !(S.env.tailscale && S.env.tailscale.ready)) return toast((S.env.tailscale && S.env.tailscale.problem) || "Tailscale is not ready on this computer."); sv[k] = !sv[k]; draw(); })); drawShare(); drawTs(); drawCv(); };
    const SOLVERS = { flaresolverr: ["FlareSolverr", "Best for almost everyone", "Opened every site that any option could, including TamilBlasters. Uses about 55 MB when idle and up to 1.6 GB while working. Best when many sites are searched at once."],
      byparr: ["Byparr", "Backup option", "Opened the same sites as FlareSolverr but is heavier (2.3 GB download, about 2 GB at its busiest) and slower when several searches run together. Pick it only if FlareSolverr stops working on a site you need."],
      trawl: ["TRAWL", "Fast on easy sites", "Answers easy sites in 1 to 2 seconds instead of 6 to 15, but failed 1337x and TamilBlasters in testing and keeps about 0.5 to 0.9 GB busy plus a small Redis. For machines with 8 GB+ where you mostly use the easy indexers."] };
    const hwNote = () => { const e = S.env, m = e.memGB; const low = m && m < 4; $("#hw").textContent = m ? `Docker can use ${m} GB RAM and ${e.cpus} CPUs here` : ""; $("#solvernote").innerHTML = low ? `<div class="note warn" style="margin-top:14px">${ic("info")}<div>Docker has only ${m} GB here, so FlareSolverr is the only comfortable choice. Raise Docker's memory limit before trying the others.</div></div>` : ""; };
    const drawSolvers = () => { $("#solvers").innerHTML = Object.entries(SOLVERS).map(([k, [t, tag, d]]) => `<div class="tile ${c.solver === k ? "on" : ""}" data-sv="${k}" tabindex="0" role="radio" aria-checked="${c.solver === k}"><span class="check">${ic("check", "s")}</span><b>${t}</b><span class="pill ${k === "flaresolverr" ? "ok" : ""}" style="align-self:flex-start">${tag}</span><small>${d}</small></div>`).join(""); $$("[data-sv]").forEach(el => onKey(el, () => { c.solver = el.dataset.sv; drawSolvers(); })); };
    if (!c.notify) c.notify = { provider: null, values: {} };
    notifyEditor($("#ntbox"), c.notify);
    drawSolvers(); hwNote(); bindSwitch("saa", () => c.autoApprove !== false, v => c.autoApprove = v);
    draw(); bindPw();
    wire(() => {
      l.username = $("#lu").value.trim(); l.password = $("#lp").value;
      if (!l.username || l.password.length < 4) return toast("Pick a username and a password of at least 4 characters.");
      if (sv.seerr && !sv.jellyfin) { sv.jellyfin = true; toast("Seerr needs Jellyfin, so Jellyfin was turned on."); }
      if (sv.samba && c.samba) {
        const sm = c.samba; sm.user = ($("#smu")?.value || sm.user).trim().toLowerCase(); sm.password = $("#smp")?.value ?? sm.password;
        if (!/^[a-z_][a-z0-9_-]{0,30}$/.test(sm.user)) return toast("File sharing: the user name must be lowercase letters or numbers, and start with a letter.");
        if (sm.password.length < 8 || sm.password.includes(":")) return toast("File sharing: use a password of 8 or more characters, without a colon.");
        const live = (sm.shares || []).filter(x => x.on !== false);
        if (!live.length) return toast("File sharing: tick at least one folder to share, or switch it off.");
        const names = live.map(x => x.name.toLowerCase());
        if (live.some(x => !/^[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}$/.test(x.name))) return toast("File sharing: share names can only use letters, numbers and spaces.");
        if (new Set(names).size !== names.length) return toast("File sharing: two shares have the same name.");
      }
      c.subtitles = { opensubtitlescom_user: $("#osu").value.trim(), opensubtitlescom_pass: $("#osp").value, subdl_key: $("#sdk").value.trim(), subsource_key: $("#ssk").value.trim(), anidb_client: ($("#adn")?.value || "").trim().toLowerCase(), anidb_ver: ($("#adv")?.value || "1").trim() };
      goRel(1);
    });
  },

  review() {
    ensureProfiles();
    const c = S.cfg, q = c.quality, s = c.settings, st = c.storage, on = Object.keys(c.services).filter(k => c.services[k]);
    const P = S.env.packs, errs = [];
    if (st.mode === "multi") {
      const have = new Set(st.libraries.filter(l => l.path).map(l => l.type));
      if (c.kinds.includes("movies") && !have.has("movies") && !(c.packs.includes("anime") && have.has("anime"))) errs.push("Add a Movies folder in the Storage step.");
      if (c.kinds.includes("tv") && !have.has("tv")) errs.push("Add a TV Shows folder in the Storage step.");
      if (c.packs.includes("anime") && !have.has("anime")) errs.push("Add an Anime folder in the Storage step.");
    }
    const where = st.mode === "single" ? st.base : `${st.downloads} + ${st.libraries.length} librar${st.libraries.length === 1 ? "y" : "ies"}`;
    const row = (a, b) => `<div class="setting" style="padding:12px 0"><span class="d" style="margin:0">${a}</span><b style="text-align:right">${b}</b></div>`;
    shell("review", `${stepHead(9, "Ready when you are", "Here is what is about to be set up.")}
      <div class="cols"><div class="grow"><div class="card">
        ${row("Storage", `<span class="mono">${esc(where)}</span>`)}
        ${row("Watching", esc([c.kinds.includes("tv") ? "TV" : "", c.kinds.includes("movies") ? "Movies" : "", c.packs.includes("anime") ? "Anime (" + (c.animeAudio === "dub" ? "English voices" : "English subs") + ")" : ""].filter(Boolean).join(", ")))}
        ${row("Languages", esc(c.packs.filter(k => k !== "anime").map(k => P[k]).join(", ") || "-"))}
        ${row("Notifications", esc(ntSummary(c)))}
        ${c.services.tailscale ? row("Private HTTPS addresses", "Tailscale, for every app") : ""}
        ${c.services.samba && c.samba ? row("File sharing", esc((c.samba.shares || []).filter(x => x.on !== false).map(x => x.name).join(", ") || "none")) : ""}
        ${row("Live TV and sports", esc(ltSummary(c)))}
        ${row("Profiles", esc(c.profiles.map(p => `${p.name} (TV ${qlab(p.resTv || p.res)}, movies ${qlab(p.resMv || p.res)})`).join("; ")))}
        ${row("Minimum number of sources", s.minSeeders)}
        ${row("Seeding", "Off (download removed once it is in your library)")}
        ${Object.keys(c.adopt || {}).length ? row("Apps you already have", esc(Object.keys(c.adopt).map(k => (S.found.find(a => a.app === k) || {}).label || k).join(", "))) + row("Left exactly as you have them", c.skipGroups.length ? c.skipGroups.length + " parts" : "nothing, everything will be changed") : ""}
        ${row("Apps", esc(["qBittorrent", "Prowlarr", "Sonarr", "Radarr", { flaresolverr: "FlareSolverr", byparr: "Byparr", trawl: "TRAWL" }[c.solver || "flaresolverr"], ...on.map(k => SVC[k][1])].join(", ")))}</div>
        ${errs.map(e => `<div class="note bad">${ic("info")}<div>${esc(e)}</div></div>`).join("")}
        <p class="hint">The first time it downloads several GB, so it can take 5 to 15 minutes.</p>
        <div class="actions"><button class="btn" id="back">Change something</button><button class="btn primary" id="next" ${errs.length ? "disabled" : ""}>Install everything ${ic("arrow")}</button></div></div></div>`, "Stopping the install is always safe.");
    wire(async () => {
      try { await api("/api/install", S.cfg); S.since = 0; go("install"); }
      catch (e) { if (/already running/i.test(e.message)) { S.since = 0; go("install"); } else toast(e.message); }   // attach to the install that is already in progress
    });
  },

  install() {
    const sv = S.cfg.services;
    const base = [["Preparing folders", "Folders checked and prepared"], ["Preparing the install", null], ["Downloading and starting the apps (the first time takes a few minutes)", "Apps downloaded and started"], ["Setting up qBittorrent (no uploading afterwards)", "qBittorrent: uploading off, folders made"], ["Setting up Sonarr and Radarr", "Sonarr and Radarr: quality choices, sizes and folders"], ["Setting up Bazarr (subtitles)", "Bazarr: subtitle languages"], ["Setting up Prowlarr (finding and testing search sites)", "Prowlarr: adding and testing search sites"], ["Setting up Jellyfin", "Jellyfin: libraries and main account"], ["Setting up Live TV and sports", "Live TV and sports channels added to Jellyfin"], ["Setting up Seerr (requests)", "Seerr: request page"], ["Setting up notifications", "Notifications connected"], ["Checking every connection", "Every link between the apps tested"], ["Checking every login", "Every login checked"], ["Testing a real search", "A real test search"], ["Building your Homepage dashboard", "Homepage dashboard"], ["All done", null]];
    const list = base.filter(([n, l]) => l && !(n.includes("Bazarr") && !sv.bazarr) && !(n.includes("Jellyfin") && !sv.jellyfin) && !(n.includes("Seerr") && !(sv.seerr && sv.jellyfin)) && !(n.includes("Homepage") && !sv.homepage) && !(n.includes("Live TV") && !(sv.jellyfin && S.cfg.livetv && S.cfg.livetv.enabled)) && !(n.includes("notifications") && !(S.cfg.notify && S.cfg.notify.provider)));
    let cur = -1;
    shell("install", `${head("Installing", "Building your server", "You do not need to do anything. The first time it downloads a few gigabytes of apps.")}
      <div class="cols"><div class="grow"><div class="card"><div class="card-h"><div style="flex:1"><div class="prog"><i id="bar" style="width:3%"></i></div></div><b class="mono" id="pct">0%</b></div><div id="tasks"></div></div>
      <div class="log" id="log" aria-label="Live log"></div><div id="errbox"></div>
      <div class="actions" id="stoprow"><button class="btn danger" id="stop">${ic("stop", "s")}Stop</button><span class="hint" style="margin:0">If it stops, you can clean up and start again.</span></div></div>
      <aside class="rail"><div class="card"><h3 style="margin-bottom:12px">Your server</h3>${summaryRows()}</div></aside></div>`, "You can leave this open. Stopping never touches your media.");
    const paint = () => {
      $("#tasks").innerHTML = list.map(([, label], i) => `<div class="task ${i < cur ? "done" : i === cur ? "run" : ""}"><span class="b">${i < cur ? ic("check", "s") : i === cur ? "" : i + 1}</span>${esc(label)}</div>`).join("");
      const pct = Math.max(3, Math.min(100, Math.round(Math.max(cur, 0) / list.length * 100))); $("#bar").style.width = pct + "%"; $("#pct").textContent = pct + "%";
    };
    paint();
    $("#stop").onclick = async () => { if (!confirm("Stop the installation?")) return; $("#stop").disabled = true; try { await api("/api/stop", {}); } catch (e) { toast(e.message); } };
    const retry = async () => { try { await api("/api/install", S.cfg); S.since = 0; $("#errbox").innerHTML = ""; $("#log").textContent = ""; $("#stoprow").classList.remove("hidden"); $("#stop").disabled = false; poll(); } catch (e) { toast(e.message); } };
    const poll = async () => {
      if (S.step !== "install") return;
      try {
        const r = await api("/api/events?since=" + (S.since || 0)); S.since = r.next;
        for (const ev of r.events) {
          if (ev.kind === "step") { const i = list.findIndex(([n]) => n === ev.msg); if (i >= 0) cur = i; else if (ev.msg === "All done") cur = list.length; paint(); }
          else if (ev.kind === "stopped") {
            $("#stoprow").classList.add("hidden");
            $("#errbox").innerHTML = `<div class="card"><h3>Stopped</h3><p class="hint">Some apps already started and are still on this computer. Choose what to do:</p><div class="actions" style="justify-content:flex-start;gap:10px"><button class="btn primary" id="again">Clean up and start over</button><button class="btn" id="resume">Continue installing</button></div></div>`;
            $("#again").onclick = async () => { try { $("#again").disabled = true; await api("/api/stack", { action: "reset" }); go("review"); } catch (e) { toast(e.message); $("#again").disabled = false; } };
            $("#resume").onclick = retry; return;
          } else {
            const L = $("#log"); L.append(document.createTextNode(ev.msg + "\n")); L.scrollTop = L.scrollHeight;
            if (ev.kind === "error") { $("#stoprow").classList.add("hidden"); $("#errbox").innerHTML = `<div class="note bad">${ic("info")}<div>${esc(ev.msg)}<br><button class="btn sm" id="retry" style="margin-top:10px">Try again</button></div></div>`; $("#retry").onclick = retry; return; }
          }
        }
        if (r.done) { S.result = r.result; return setTimeout(() => go("done"), 700); }
      } catch (e) { /* server busy while images pull */ }
      setTimeout(poll, 1500);
    };
    poll();
  },

  done() {
    const r = S.result || {};
    shell("done", `<div><span class="eyebrow">Finished</span><h1 style="margin-bottom:8px">Your server is ready</h1><p class="lead">Everything is installed, connected and tested. Open the dashboard to see it all.</p></div>
      <div class="grid3">${(r.links || []).map(l => `<a class="link" href="${esc(l.url)}" target="_blank" rel="noopener"><span><b>${esc(l.name)}</b><br><small>${esc(l.url.replace("http://", ""))}</small></span>${ic("arrow", "s")}</a>`).join("")}</div>
      ${r.smoke ? `<div class="note ${r.smoke.ok ? "ok" : "warn"}">${ic(r.smoke.ok ? "check" : "info")}<div>${esc(r.smoke.msg)}</div></div>` : ""}
      ${linksCard(r.integrations || [])}
      ${credsCard(r.credentials || [])}
      ${r.indexers && r.indexers.working ? `<div class="card"><h3 style="margin-bottom:6px">${r.indexers.working.length} working indexers</h3><p class="hint" style="margin:0">${r.indexers.working.map(esc).join(", ")}${(r.indexers.not_available || []).length ? `<br><br>Not available right now: ${r.indexers.not_available.map(esc).join(", ")}` : ""}</p></div>` : ""}
      <div class="actions" style="justify-content:flex-start"><button class="btn primary" id="find">Find a movie or series ${ic("arrow")}</button></div>`, "");
    bindCreds(r.credentials || []); bindLinks(res => { r.integrations = res; $("#linkscard").outerHTML = linksCard(res); bindLinks(() => {}); });
    $("#find").onclick = () => { S.mode = "dash"; S.tab = "find"; dash(); };
  },
};

/* shared pieces for wizard + dashboard */
function downloadSettings(s) {
  return `<div class="card"><div class="card-h"><h3>Finding downloads</h3></div>
    <div class="setting"><div><div class="t">Minimum number of sources</div><div class="d">Downloads with fewer sources than this are ignored. A low number finds rare titles. A high number skips them.</div></div><div class="val" id="msv" style="min-width:70px;font-size:28px;text-align:right">${s.minSeeders}</div></div>
    <input type="range" id="ms" min="1" max="10" step="1" value="${s.minSeeders}" style="margin-top:4px" aria-label="Minimum number of sources"><div class="meta" style="justify-content:space-between"><span>1 finds everything</span><span>10 only popular ones</span></div><div class="sep"></div>
    <div class="setting"><div><div class="t">Look for new releases every</div><div class="d">How often it looks for new episodes and movies.</div></div>${seg("srss", [[15, "15 min"], [30, "30 min"], [60, "60 min"]], s.rssMinutes)}</div>
    <div class="setting"><div><div class="t">Try again when a download fails</div><div class="d">Picks the next best version if one fails or gets stuck.</div></div>${sw(s.retryFailed, "sretry", "Try again when a download fails")}</div></div>
    <div class="card"><div class="card-h"><h3>Speed and waiting line</h3></div>
    <div class="setting"><div><div class="t">Downloads at the same time</div><div class="d">1 means one at a time. A higher number is faster for many downloads.</div></div>${seg("scon", [[1, "1"], [2, "2"], [3, "3"], [5, "5"], [0, "Unlimited"]], s.concurrent)}</div>
    <div class="grid2" style="margin-top:8px"><div class="field"><label for="dl">Download speed limit (KB per second, 0 means no limit)</label><input class="input" id="dl" type="number" min="0" value="${s.dlLimitKB}"></div><div class="field"><label for="ul">Upload speed limit (KB per second)</label><input class="input" id="ul" type="number" min="0" value="${s.ulLimitKB}"></div></div>
    <p class="hint">Uploading only happens while a download is still running. Nothing uploads afterwards.</p></div>`;
}
function bindDownloadSettings(s) {
  $("#ms").oninput = e => { s.minSeeders = +e.target.value; $("#msv").textContent = s.minSeeders; };
  bindSeg("#srss", () => s.rssMinutes, v => s.rssMinutes = v, Number); bindSeg("#scon", () => s.concurrent, v => s.concurrent = v, Number);
  bindSwitch("sretry", () => s.retryFailed, v => s.retryFailed = v);
  $("#dl").onchange = e => s.dlLimitKB = Math.max(0, +e.target.value || 0); $("#ul").onchange = e => s.ulLimitKB = Math.max(0, +e.target.value || 0);
}
const noSeedCard = () => `<div class="card"><h3 style="margin-bottom:12px">No uploading afterwards</h3><div class="diagram"><span class="node">download</span><span class="arrow">&#8594;</span><span class="node">import</span><span class="arrow">&#8594;</span><span class="node">download removed</span></div><p class="hint" style="margin-top:12px">A finished download is deleted as soon as the file is in your library. Nothing is shared back. This is fine for public sites. Private sites that demand sharing back are not supported.</p><div class="note ok" style="margin-top:14px">${ic("check")}<div>qBittorrent is also told to stop sharing, as a second safety.</div></div></div>`;
function summaryRows() {
  const c = S.cfg, st = c.storage;
  return [["Storage", st.mode === "single" ? "One drive" : (S.plan ? S.plan.mounts.length : st.libraries.length) + " locations"], ["Languages", c.packs.filter(k => k !== "anime").length], ["Profiles", (c.profiles || []).length], ["Live TV", ltSummary(c)], ["Notifications", ntSummary(c)], ["Min seeders", c.settings.minSeeders]].map(([a, b]) => `<div class="setting" style="padding:9px 0"><span class="d" style="margin:0">${a}</span><span class="mono">${esc(b)}</span></div>`).join("");
}

/* ------------------------------------------------------------ dashboard */
const NAV = [["find", "search", "Find a title"], ["storage", "folder", "Storage"], ["profiles", "sliders", "Profiles"], ["livetv", "tv", "Live TV"], ["notify", "info", "Notifications"], ["dl", "download", "Downloads"], ["langs", "globe", "Languages"], ["links", "link", "Apps and links"]];
function dshell(main) {
  $("#app").innerHTML = `<div class="app"><aside class="side"><div class="brand"><span class="mark">${ic("play")}</span>Media Server</div><ol class="steps">${NAV.map(([k, i, l]) => `<li class="${S.tab === k ? "on" : ""}" data-t="${k}" style="cursor:pointer"><span class="n">${ic(i, "s")}</span><span class="t">${l}</span></li>`).join("")}</ol><div class="foot"><div class="sidelinks">${guideLink()}${themeBtn()}</div><p class="footnote"><a href="/?setup=1" style="color:var(--faint)">Start the setup again</a></p></div></aside><main class="main screen">${main}</main></div>`;
  $$("[data-t]").forEach(el => el.onclick = () => { S.tab = el.dataset.t; dash(); });
}
function dash() { tabs[S.tab](); }
async function applyPatch(patch, msg = "Applied") { const t = toast("Applying…", true); try { await api("/api/retune", patch); t.remove(); toast(msg); } catch (e) { t.remove(); toast(e.message); } }

const tabs = {
  find() {
    dshell(`<div><span class="eyebrow">Find a title</span><h2 style="font-size:36px">Search for anything. See why it will or will not download.</h2></div>
      <div class="card" style="padding:16px"><div style="display:flex;gap:12px;flex-wrap:wrap"><div class="seg" id="kind"><button data-v="movie" class="on">Movie</button><button data-v="tv">TV series</button></div><input class="input" id="term" style="flex:1 1 300px;width:auto" placeholder="e.g. Premam 2015, Breaking Bad" aria-label="Title"><button class="btn primary" id="go">${ic("search", "s")}Search</button></div></div>
      <div id="res"></div>`);
    let kind = "movie";
    bindSeg("#kind", () => kind, v => kind = v);
    const run = async () => {
      const term = $("#term").value.trim(); if (!term) return; $("#res").innerHTML = `<div class="card">Searching…</div>`;
      try {
        const list = await api(`/api/lookup?kind=${kind}&term=${encodeURIComponent(term)}`); S.last = list;
        $("#res").innerHTML = `<div class="card">${list.map((r, i) => `<div class="title-row">${r.poster ? `<img class="poster" src="${esc(r.poster)}" alt="" loading="lazy">` : `<div class="poster">${ic("film", "l")}</div>`}<div><div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap"><b style="font:600 18px var(--display)">${esc(r.title)}</b><span class="hint" style="margin:0">${esc(r.year || "")} &#183; ${esc(r.lang || "")}</span>${r.inLibrary ? '<span class="pill warn">in your library</span>' : ""}</div><p class="hint" style="max-width:70ch">${esc(r.overview)}</p></div><button class="btn primary sm" data-i="${i}">${r.inLibrary ? "Check" : "Add and check"}</button></div>`).join("") || "Nothing found. Try spelling it differently."}</div><div id="diag"></div>`;
        $$(".title-row .btn").forEach(b => b.onclick = () => addAndCheck(kind, S.last[+b.dataset.i], b));
      } catch (e) { $("#res").innerHTML = `<div class="note bad">${ic("info")}<div>${esc(e.message === "Failed to fetch" ? "Cannot reach the setup. Refresh this page in a few seconds." : e.message)}</div></div>`; }
    };
    $("#go").onclick = run; $("#term").onkeydown = e => e.key === "Enter" && run(); $("#term").focus();
  },

  async storage() {
    dshell(`<div><span class="eyebrow">Storage</span><h2 style="font-size:36px">Where your media is kept</h2></div><div class="card" id="box">Loading…</div>`);
    const st = await api("/api/storage");
    $("#box").innerHTML = `<div class="setting"><div><div class="t">Downloads</div><div class="d mono">${esc(st.downloadsHost)}</div></div></div>` + st.libs.map(l => `<div class="lib" style="margin-top:10px"><div class="kind"><span class="ic">${ic(KIND[l.type][0])}</span>${KIND[l.type][1]}</div><div class="where"><div class="path">${esc(l.host)}</div>${l.totalBytes ? `<div class="meter"><i class="${l.usedBytes / l.totalBytes > .92 ? "hi" : l.usedBytes / l.totalBytes > .78 ? "mid" : ""}" style="width:${Math.round(l.usedBytes / l.totalBytes * 100)}%"></i></div><div class="meta"><span>${fmt(l.freeBytes)} free of ${fmt(l.totalBytes)}</span><span>${l.linked ? "instant link" : "copied across drives"}</span></div>` : ""}</div><span></span></div>`).join("") + `<p class="hint" style="margin-top:16px">New titles go to the folder with the most free space. To change folders or add a drive, start the setup again. Files you already have are never moved.</p><div class="actions" style="justify-content:flex-start"><a class="btn" href="/?setup=1">Change storage</a></div>`;
  },

  async notify() {
    dshell(`<div><span class="eyebrow">Notifications</span><h2 style="font-size:36px">Know when something happens</h2><p class="lead">Messages about downloads, better versions, problems and requests, sent to your chat app.</p></div>
      <div class="card"><div id="ntbox">Loading…</div></div><div id="ntstat"></div>
      <div class="actions" style="justify-content:flex-start"><button class="btn primary" id="ntapply">Save and send a test message</button></div>`);
    const st = await api("/api/state"); const sel = (st.cfg && st.cfg.notify) || { provider: null, values: {} }; sel.values = sel.values || {};
    notifyEditor($("#ntbox"), sel);
    $("#ntapply").onclick = async () => {
      $("#ntapply").disabled = true; $("#ntstat").innerHTML = `<div class="card">Applying…</div>`;
      try { const r = await api("/api/notify/apply", { provider: sel.provider, values: sel.values });
        $("#ntstat").innerHTML = r.problems.length ? `<div class="note bad">${ic("info")}<div>${esc(r.problems.join("; "))}</div></div>` : `<div class="note ok">${ic("check")}<div>${sel.provider ? "Connected in " + esc(r.done.join(", ")) + (r.tested ? ". A test message was sent." : ".") : "Notifications turned off."}</div></div>`;
      } catch (e) { $("#ntstat").innerHTML = `<div class="note bad">${ic("info")}<div>${esc(e.message)}</div></div>`; }
      $("#ntapply").disabled = false;
    };
  },

  async livetv() {
    dshell(`<div><span class="eyebrow">Live TV</span><h2 style="font-size:36px">Live TV and sports</h2><p class="lead">Channels from free lists, plus your own provider if you have one.</p></div>
      <div class="card"><div id="ltbox">Loading…</div></div><div id="ltstat"></div>
      <div class="actions" style="justify-content:flex-start"><button class="btn primary" id="ltapply">Add to Jellyfin</button></div>`);
    const s = await api("/api/livetv/status");
    if (!s.jellyfin) { $("#ltbox").innerHTML = `<div class="note">${ic("info")}<div>Jellyfin is not part of this setup, so there is nowhere to show live TV.</div></div>`; $("#ltapply").remove(); return; }
    const sel = S.dlt = Object.assign(LT_DEFAULT(), s.selection || {});
    sel.custom = Object.assign({ m3u: "", xmltv: "" }, sel.custom);
    ltEditor($("#ltbox"), sel);
    const show = j => {
      const d = s.daily || {};
      $("#ltstat").innerHTML = j.running ? `<div class="card">${esc(j.msg || "Working…")}</div>` : j.error ? `<div class="note bad">${ic("info")}<div>${esc(j.error)}</div></div>`
        : j.stats ? `<div class="note ok">${ic("check")}<div>${j.stats.inJellyfin || j.stats.channels} channels in Jellyfin, ${j.stats.sports} sports, ${j.stats.withGuide} with a program guide. ${j.stats.dead} dead streams left out.</div></div>`
        : d.last ? `<div class="hint">List last refreshed automatically ${new Date(d.last * 1000).toLocaleString()}.</div>` : "";
    };
    show(s.job);
    $("#ltapply").onclick = async () => {
      $("#ltapply").disabled = true;
      try { await api("/api/livetv/apply", sel); } catch (e) { toast(e.message); $("#ltapply").disabled = false; return; }
      const tick = async () => { const r = await api("/api/livetv/status"); show(r.job); if (r.job.running) return setTimeout(tick, 3000); $("#ltapply").disabled = false; };
      tick();
    };
  },

  async profiles() {
    const st = await api("/api/state"), env = S.env || (S.env = await api("/api/env"));
    S.cfg = { ...S.cfg, ...st.cfg, packs: [...st.cfg.packs], settings: { ...st.cfg.settings } }; S.cfg._psig = JSON.stringify([S.cfg.packs, S.cfg.animeAudio]);
    ensureProfiles();
    dshell(`<div><span class="eyebrow">Profiles</span><h2 style="font-size:36px">Quality, size and subtitles</h2></div><div class="cols"><div class="grow"><div id="pcards"></div>
      <div class="card" style="display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap"><div><h3>Add a quality choice</h3><div class="hint" style="margin:2px 0 0">Give a language its own quality and size.</div></div><button class="btn" id="addp">${ic("plus", "s")}Add profile</button></div>
      <div class="actions" style="justify-content:flex-start"><button class="btn primary" id="save">Apply</button></div></div><aside class="rail" id="prail"></aside></div>`);
    $("#addp").onclick = () => { S.cfg.profiles.push(newProfile(S.cfg)); drawProfiles(); };
    drawProfiles();
    $("#save").onclick = () => applyPatch({ profiles: S.cfg.profiles, settings: S.cfg.settings });
  },

  async dl() {
    const st = await api("/api/state"); const s = { ...st.cfg.settings };
    dshell(`<div><span class="eyebrow">Downloads</span><h2 style="font-size:36px">How downloads work</h2></div><div class="cols"><div class="grow">${downloadSettings(s)}<div class="actions" style="justify-content:flex-start"><button class="btn primary" id="save">Apply</button></div></div><aside class="rail">${noSeedCard()}</aside></div>`);
    bindDownloadSettings(s); $("#save").onclick = () => applyPatch({ settings: s });
  },

  async langs() {
    const st = await api("/api/state"), env = S.env || (S.env = await api("/api/env")); const c = { packs: [...st.cfg.packs], animeAudio: st.cfg.animeAudio, subtitleLangs: [...st.cfg.subtitleLangs] };
    const P = env.packs, keys = Object.keys(P).filter(k => k !== "anime");
    dshell(`<div><span class="eyebrow">Languages</span><h2 style="font-size:36px">What you watch</h2></div>
      <div class="card"><div class="card-h"><h3>Anime</h3></div><div class="chips"><span class="chip ${c.packs.includes("anime") ? "on" : ""}" id="an" tabindex="0">${c.packs.includes("anime") ? '<span class="dot"></span>' : ""}Anime</span></div><div style="margin-top:12px">${seg("sa", [["sub", "Japanese voices with English subtitles"], ["dub", "English voices"]], c.animeAudio)}</div></div>
      <div class="card"><div class="card-h"><h3>Languages</h3></div><div class="chips" id="langs"></div></div>
      <div class="note">${ic("info")}<div>Adding Tamil, Malayalam, Telugu, Kannada or Hindi for the first time also adds the Tamil and Malayalam forum search site. Use “Start the setup again” after changing those.</div></div>
      <div class="actions" style="justify-content:flex-start"><button class="btn primary" id="save">Apply</button></div>`);
    const draw = () => { $("#langs").innerHTML = keys.map(k => `<span class="chip ${c.packs.includes(k) ? "on" : ""}" data-k="${k}" tabindex="0">${c.packs.includes(k) ? '<span class="dot"></span>' : ""}${esc(P[k])}</span>`).join(""); $$("#langs .chip").forEach(el => el.onclick = () => { toggleIn(c.packs, el.dataset.k); draw(); }); }; draw();
    $("#an").onclick = e => { toggleIn(c.packs, "anime"); e.currentTarget.classList.toggle("on"); };
    bindSeg("#sa", () => c.animeAudio, v => c.animeAudio = v);
    $("#save").onclick = () => applyPatch(c);
  },

  async links() {
    const st = await api("/api/state"); const r = st.summary || {};
    dshell(`<div><span class="eyebrow">Apps and links</span><h2 style="font-size:36px">Your apps</h2></div><div class="grid3">${(r.links || []).map(l => `<a class="link" href="${esc(l.url)}" target="_blank" rel="noopener"><span><b>${esc(l.name)}</b><br><small>${esc(l.url.replace("http://", ""))}</small></span>${ic("arrow", "s")}</a>`).join("")}</div>
      <div class="card"><div class="card-h"><h3>Status</h3><div style="display:flex;gap:8px"><button class="btn sm" id="stopall">${ic("stop", "s")}Stop all</button><button class="btn sm" id="startall">${ic("play", "s")}Start all</button></div></div><div class="chips">${(st.containers || []).map(c => `<span class="pill ${c.state === "running" ? "ok" : "bad"}">${esc(c.service)}: ${esc(c.state)}</span>`).join("")}</div></div>`);
    try {
      const rg = await api("/api/regional");
      if (Object.keys(rg).length) {
        $(".main").insertAdjacentHTML("beforeend", `<div class="card"><div class="card-h"><h3>Tamil, Malayalam and Indian film sources</h3><span class="sub">Their website addresses change often. This finds the current one for you.</span></div>${Object.entries(rg).map(([k, r]) => `<div class="setting"><div><div class="t">${esc(r.name)}</div><div class="d mono">${esc(r.address || r.error || "looking for an address…")}</div></div><div style="display:flex;gap:8px;align-items:center"><span class="pill ${r.online ? "ok" : "warn"}">${r.online ? "online" : "searching"}</span><button class="btn sm" data-disc="${k}">Find the address</button></div></div>`).join("")}</div>`);
        $$("[data-disc]").forEach(b => b.onclick = async () => { b.disabled = true; toast("Looking for a working address…"); try { const r = await api("/api/regional/discover", { site: b.dataset.disc }); toast(r.address ? "Found " + r.address : (r.error || "No address found yet")); } catch (e) { toast(e.message); } b.disabled = false; tabs.links(); });
      }
    } catch (e) { /* adapter not installed */ }
    try { const il = await api("/api/integrations"); if (il.length) { $(".main").insertAdjacentHTML("beforeend", linksCard(il)); const redo = res => { $("#linkscard").outerHTML = linksCard(res); bindLinks(redo); }; bindLinks(redo); } } catch (e) { /* none yet */ }
    try { const cr = await api("/api/credentials"); if (cr.length) { $(".main").insertAdjacentHTML("beforeend", credsCard(cr)); bindCreds(cr); } } catch (e) { /* none yet */ }
    for (const a of ["stop", "start"]) $("#" + a + "all").onclick = async e => { e.currentTarget.disabled = true; toast(a === "stop" ? "Stopping…" : "Starting…"); try { await api("/api/stack", { action: a }); toast("Done"); tabs.links(); } catch (er) { toast(er.message); e.currentTarget.disabled = false; } };
  },
};

async function addAndCheck(kind, item, btn) {
  const box = $("#diag"); btn.disabled = true;
  box.innerHTML = `<div class="card"><b>Adding “${esc(item.title)}” and searching every indexer…</b><div class="hint">This can take up to a minute.</div><div class="prog" style="margin-top:12px"><i style="width:55%"></i></div></div>`;
  try {
    const added = item.inLibrary ? { id: item.raw.id, kind } : await api("/api/add", { kind, raw: item.raw });
    const d = await api(`/api/diagnose?kind=${kind}&id=${added.id}`);
    const pill = { ok: ["ok", "Will download"], rejected: ["warn", "Turned down by your choices"], none: ["bad", "Nothing found"], notyet: ["warn", "Not released yet"] }[d.verdict];
    const rejected = (d.releases || []).filter(r => !r.approved), approved = (d.releases || []).filter(r => r.approved);
    const reasons = Object.entries(d.reasons || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);
    const relRow = r => `<div class="rel"><div><div class="t">${esc(r.title)}</div><div class="m"><span>${esc(r.indexer)}</span><span>${r.sizeMB >= 1000 ? (r.sizeMB / 1000).toFixed(1) + " GB" : r.sizeMB + " MB"}</span><span>${r.seeders ?? "?"} seeders</span><span class="pill ${r.approved ? "ok" : ""}">${esc(r.quality || "")}</span>${(r.languages || []).map(l => `<span class="pill blue">${esc(l)}</span>`).join("")}${r.rejections.length ? `<span class="warnc">${r.rejections.map(esc).join(" · ")}</span>` : ""}</div></div><button class="btn sm" data-g="${esc(r.guid)}" data-i="${r.indexerId}">${r.approved ? "Download again" : "Download anyway"}</button></div>`;
    box.innerHTML = `<div class="card"><span class="pill ${pill[0]}">${pill[1]}</span><p>${esc(d.message)}</p>
      <div class="stat"><div><b>${(d.releases || []).length}</b><span>releases found</span></div><div><b class="okc">${approved.length}</b><span>match your choices</span></div></div></div>
      <div class="cols" style="margin-top:18px"><div class="grow"><div class="card"><div class="card-h"><h3>Releases</h3><div class="seg" id="rt"><button data-v="a" class="${approved.length ? "on" : ""}">Matching ${approved.length}</button><button data-v="r" class="${approved.length ? "" : "on"}">Rejected ${rejected.length}</button></div></div><div id="rl"></div></div></div>
      <aside class="rail">${reasons.length ? `<div class="card"><h3 style="margin-bottom:10px">Why some downloads were turned down</h3>${reasons.map(([k, n]) => `<div class="setting" style="padding:8px 0"><span class="d" style="margin:0">${esc(k)}</span><b>${n}</b></div>`).join("")}<p class="hint">You can still download a rejected one by hand with one click.</p></div>` : ""}</aside></div>`;
    const showList = v => { $("#rl").innerHTML = (v === "a" ? approved : rejected).slice(0, 25).map(relRow).join("") || `<p class="hint">Nothing here.</p>`; $$("#rl [data-g]").forEach(b => b.onclick = async () => { try { await api("/api/grab", { kind, guid: b.dataset.g, indexerId: +b.dataset.i }); toast("Sent to qBittorrent"); } catch (e) { toast(e.message); } }); };
    bindSeg("#rt", () => "", showList); showList(approved.length ? "a" : "r");
  } catch (e) { box.innerHTML = `<div class="note bad">${ic("info")}<div>${esc(e.message)}</div></div>`; }
  btn.disabled = false;
}

/* ------------------------------------------------------------ connection watchdog + boot */
let offline = false;
setInterval(async () => {
  try { const r = await fetch("/api/state", { cache: "no-store" }); if (!r.ok) throw 0; if (offline) { offline = false; $("#offline")?.remove(); toast("Reconnected", true); setTimeout(() => location.reload(), 900); } }
  catch (e) { if (!offline) { offline = true; const t = toast("Lost the connection to the setup. Trying again…", true); t.id = "offline"; } }
}, 4000);

function render() { const f = screens[S.step]; if (f) Promise.resolve(f()); }
(async () => {
  try {
    const st = await api("/api/state");
    S.env = await api("/api/env");
    if (st.running) { if (st.jobCfg) S.cfg = st.jobCfg; S.since = 0; S.step = "install"; return render(); }
    if (st.installed && !location.search.includes("setup")) { S.mode = "dash"; return dash(); }
    if (st.installed && st.cfgFull) S.cfg = { ...S.cfg, ...st.cfgFull };
  } catch (e) { /* first run */ }
  render();
})();
