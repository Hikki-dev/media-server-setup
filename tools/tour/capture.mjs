// Step 1 of the tour video: walks through the demo in a real browser and saves one picture of every state
// (before a click, with the pointer over the button, and after the click), plus where each button is.
// Step 2 (compose.py) turns these into the video: it draws the pointer, the camera moves and the captions.
//
// Needs: npm install (puppeteer-core), Google Chrome, and the demo served at http://localhost:8765/demo/
//   python3 tools/build_site.py && (cd site && python3 -m http.server 8765) &
//   node tools/tour/capture.mjs <output folder>
import puppeteer from "puppeteer-core";
import fs from "node:fs";
import path from "node:path";

const OUT = path.resolve(process.argv[2] || "tour-work");
const URL = process.env.DEMO_URL || "http://localhost:8765/demo/";
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const W = 1280, H = 720, DPR = 2;
fs.mkdirSync(OUT, { recursive: true });

const sleep = ms => new Promise(r => setTimeout(r, ms));
const browser = await puppeteer.launch({ executablePath: CHROME, headless: "new", args: ["--hide-scrollbars", "--font-render-hinting=none"] });
const page = await browser.newPage();
await page.setViewport({ width: W, height: H, deviceScaleFactor: DPR });
await page.goto(URL, { waitUntil: "networkidle0" });
await page.addStyleTag({ content: ".demo-bar{display:none!important} html{scroll-behavior:auto!important} *{caret-color:transparent}" });
await sleep(800);

const states = [];
let n = 0;
async function target(spec) {      // where an element is, in page pixels
  return page.evaluate(spec => {
    const pick = () => {
      if (spec.css) return document.querySelector(spec.css);
      const all = [...document.querySelectorAll(spec.tag || "button,a,.tile,.it,.chip,.seg button,[data-v],div")];
      const hits = all.filter(e => new RegExp(spec.text, "i").test((e.innerText || "").trim()) && (e.innerText || "").trim().length < (spec.max || 80));
      return hits.sort((a, b) => a.getBoundingClientRect().width * a.getBoundingClientRect().height - b.getBoundingClientRect().width * b.getBoundingClientRect().height)[0];
    };
    const e = pick();
    if (!e) return null;
    const r = e.getBoundingClientRect();
    return { x: r.left + scrollX, y: r.top + scrollY, w: r.width, h: r.height };
  }, spec);
}
async function shot(name, { full = true, targets = {} } = {}) {
  const found = {};
  for (const [k, spec] of Object.entries(targets)) {
    const t = await target(spec);
    if (!t) console.warn("  not found:", name, k, JSON.stringify(spec));
    found[k] = t;
  }
  const id = String(++n).padStart(3, "0") + "-" + name;
  const file = id + ".png";
  await page.screenshot({ path: path.join(OUT, file), fullPage: full });
  const dims = await page.evaluate(() => ({ w: document.documentElement.scrollWidth, h: Math.max(document.documentElement.scrollHeight, innerHeight) }));
  states.push({ id, file, full, w: dims.w, h: full ? dims.h : H, targets: found });
  console.log("captured", id);
  return found;
}
async function center(spec) { const t = await target(spec); return { x: t.x + t.w / 2 - (await page.evaluate(() => scrollX)), y: t.y + t.h / 2 - (await page.evaluate(() => scrollY)) }; }
async function hover(spec, { scroll = true } = {}) {
  if (scroll) await page.evaluate(spec2 => {}, spec);
  const el = await page.evaluateHandle(spec => {
    const all = [...document.querySelectorAll(spec.tag || "button,a,.tile,.it,.chip,.seg button,[data-v],div")];
    if (spec.css) return document.querySelector(spec.css);
    const hits = all.filter(e => new RegExp(spec.text, "i").test((e.innerText || "").trim()) && (e.innerText || "").trim().length < (spec.max || 80));
    return hits.sort((a, b) => a.getBoundingClientRect().width * a.getBoundingClientRect().height - b.getBoundingClientRect().width * b.getBoundingClientRect().height)[0];
  }, spec);
  await el.asElement().evaluate(e => e.scrollIntoView({ block: "center", behavior: "instant" }));
  await sleep(120);
  const box = await el.asElement().boundingBox();
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 4 });
  await sleep(250);
  return el.asElement();
}
async function park() { await page.mouse.move(2, 2); await page.evaluate(() => window.scrollTo(0, 0)); await sleep(250); }

/* a click through the real mouse: park, take the "before" picture, hover, take the "hover" picture, click, wait */
async function step(name, spec, { full = true, settle = 700, targets = {}, hoverFull = full, extra = {} } = {}) {
  await park();
  await shot(name, { full, targets: { target: spec, ...targets } });
  const el = await hover(spec);
  await shot(name + "-hover", { full: hoverFull, targets: { target: spec } });
  await el.click({ delay: 60 });
  await sleep(settle);
}

const CONTINUE = { css: "#next" };
await sleep(300);

/* 1. welcome */
await step("welcome", { text: "^Start setup", tag: "button" }, { settle: 3200 });

/* 2. computer check */
await step("check", CONTINUE, { settle: 3200, targets: { rows: { text: "Running, version", tag: "div,span,p", max: 60 } } });

/* 3. storage and the folder picker */
await park();
await shot("storage", { targets: { browse: { text: "^Browse", tag: "button" }, path: { text: "free of", tag: "div,span", max: 40 } } });
{
  const el = await hover({ text: "^Browse", tag: "button" });
  await shot("storage-hover-browse", { targets: {} });
  await el.click({ delay: 60 });
  await sleep(3500);
}
await park();
await page.evaluate(() => { const c = document.querySelector('[data-i="-1"]'); if (c) c.click(); });
await sleep(1200);
await shot("picker", { full: false, targets: { internal: { text: "This computer", tag: ".it" }, media: { text: "^Media", tag: ".it" }, backup: { text: "^Backup", tag: ".it" }, list: { css: ".qa" }, modal: { css: ".modal" } } });
{
  const a = await hover({ text: "This computer", tag: ".it" }, { scroll: false });
  await shot("picker-hover-internal", { full: false });
  const b = await hover({ text: "^Media", tag: ".it" }, { scroll: false });
  await shot("picker-hover-media", { full: false });
  await b.click({ delay: 60 });
  await sleep(1800);
}
await shot("picker-media", { full: false, targets: { use: { css: "#bu" }, dirs: { css: ".dirs" }, modal: { css: ".modal" } } });
{
  const el = await hover({ css: "#bu" }, { scroll: false });
  await shot("picker-hover-use", { full: false });
  await el.click({ delay: 60 });
  await sleep(1800);
}
await step("storage-chosen", CONTINUE, { targets: { path: { text: "free of", tag: "div,span", max: 40 } }, settle: 2500 });

/* 4. what you watch */
await park();
await shot("watch", { targets: { quick: { text: "English shows and anime", tag: ".chip", max: 60 } } });
{
  const el = await hover({ text: "English shows and anime", tag: ".chip", max: 60 });
  await shot("watch-hover-quick");
  await el.click({ delay: 60 });
  await sleep(900);
}
await step("watch-chosen", CONTINUE, { settle: 4500 });

/* 5. live tv, profiles, downloads: seen quickly */
await step("livetv", CONTINUE, { settle: 2500 });
await step("profiles", CONTINUE, { settle: 2200 });
/* the downloader needs its own login: typed one letter at a time, so the video can show it */
await park();
await shot("downloads", { targets: { user: { css: "#qu" }, pass: { css: "#qp" } } });
{
  const el = await hover({ css: "#qu" });
  await shot("downloads-hover-user", { targets: { user: { css: "#qu" } } });
  await el.click({ delay: 60 });
  await page.evaluate(() => document.querySelector("#qu").select());      // typing replaces the default text
  let typed = 0;
  for (const ch of "qbit") { await page.keyboard.type(ch); await shot(`downloads-user-${++typed}`, { targets: { user: { css: "#qu" } } }); }
  const el2 = await hover({ css: "#qp" });
  await shot("downloads-hover-pass", { targets: { pass: { css: "#qp" } } });
  await el2.click({ delay: 60 });
  await page.evaluate(() => document.querySelector("#qp").select());
  typed = 0;
  for (const ch of "demo-pass") { await page.keyboard.type(ch); await shot(`downloads-pass-${++typed}`, { targets: { pass: { css: "#qp" } } }); }
}
await step("downloads-continue", CONTINUE, { settle: 3000 });

/* 6. apps: switch on comics, manga and the reader */
await park();
await shot("apps", { targets: { komga: { css: '[data-s="komga"]' }, kapowarr: { css: '[data-s="kapowarr"]' }, kaizoku: { css: '[data-s="kaizoku"]' }, grid: { css: "#svc" } } });
for (const k of ["komga", "kapowarr", "kaizoku"]) {
  const el = await hover({ css: `[data-s="${k}"]` });
  await shot(`apps-hover-${k}`, { targets: { tile: { css: `[data-s="${k}"]` } } });
  await el.click({ delay: 60 });
  await sleep(500);
  console.log('  services:', JSON.stringify(await page.evaluate(() => ({ k: S.cfg.services.kapowarr, kz: S.cfg.services.kaizoku, step: S.step, cv: !!document.querySelector('#cvk') }))));
  await shot(`apps-${k}-on`, { targets: { tile: { css: `[data-s="${k}"]` }, grid: { css: "#svc" }, card: { text: "ComicVine key", tag: ".card", max: 400 } } });
}
{
  const el = await hover({ css: "#cvk" });
  await shot("apps-hover-key", { targets: { field: { css: "#cvk" }, card: { text: "ComicVine key", tag: ".card", max: 400 } } });
  await el.click({ delay: 60 });
  await page.keyboard.type("7c1e5b0a9f2d84c36e5a1b7d90f4c2a8e3d61b05", { delay: 0 });
  await sleep(400);
  await shot("apps-key-pasted", { targets: { field: { css: "#cvk" } } });
}
{
  const gen = { text: "^Generate", tag: "button" };
  const el = await hover(gen);
  await shot("apps-hover-generate", { targets: { gen, login: { text: "^Main login", tag: ".card", max: 600 } } });
  await el.click({ delay: 60 });
  await sleep(500);
  await shot("apps-generated", { targets: { login: { text: "^Main login", tag: ".card", max: 600 }, pass: { css: "#lp" } } });
}
await step("apps-continue", { text: "^Review", tag: "button" }, { settle: 3000 });

/* 7. review and install */
await park();
await shot("review", { targets: { summary: { text: "Here is what is about to be set up", tag: ".card,div", max: 900 }, install: { css: "#next" } } });
{
  const el = await hover({ css: "#next" });
  await shot("review-hover-install", { targets: { install: { css: "#next" } } });
  await el.click({ delay: 60 });
}
await page.mouse.move(2, 2);

/* 8. the install, one picture a second */
const startedAt = Date.now();
let k = 0;
while (Date.now() - startedAt < 70000) {
  const step = await page.evaluate(() => S.step);
  if (step === "done") break;
  await shot(`install-${String(k++).padStart(2, "0")}`, { full: false, targets: { tasks: { css: "#tasks" }, log: { css: "#log" }, bar: { css: ".prog" } } });
  await sleep(850);
}
await sleep(1500);

/* 9. done */
await park();
await shot("done", { targets: { links: { css: ".grid3" }, logins: { text: "Your logins", tag: ".card", max: 2000 } } });
{
  const show = { text: "^Show", tag: "button" };
  const el = await hover(show);
  await shot("done-hover-show", { targets: { show } });
  await el.click({ delay: 60 });
  await sleep(500);
  await shot("done-revealed", { targets: { logins: { text: "Your logins", tag: ".card", max: 2000 } } });
}
await park();
await shot("done-end", { full: false, targets: {} });

fs.writeFileSync(path.join(OUT, "manifest.json"), JSON.stringify({ W, H, DPR, states }, null, 1));
console.log("done:", states.length, "states in", OUT);
await browser.close();
