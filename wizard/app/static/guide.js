/* The guide: shows the pages in the docs folder, the same files people read on GitHub. No outside libraries. */
const $ = s => document.querySelector(s);
const esc = t => String(t).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

/* A small Markdown reader: headings, paragraphs, lists, tables, code blocks, quotes, images, links, bold, italic, inline code. */
function inline(t, base) {
  const codes = [];
  t = t.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return `\u0000${codes.length - 1}\u0000`; });
  t = esc(t);
  t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => `<a class="pic" href="${imgSrc(src, base)}" target="_blank" rel="noopener" title="Open the picture full size"><img alt="${alt}" src="${imgSrc(src, base)}" loading="lazy"></a>`);
  t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
    let h = href.replace(/&amp;/g, "&");
    if (!/^(https?:|mailto:|#|\/|[A-Za-z0-9_.% -]+(\.md)?(#.*)?$)/i.test(h)) h = "#";      // only normal links: never a script address
    if (/\.md(#.*)?$/.test(h)) return `<a href="#${encodeURIComponent(decodeURIComponent(h.replace(/\.md.*$/, "").split("/").pop()))}">${label}</a>`;
    return `<a href="${h}" ${/^https?:/.test(h) ? 'target="_blank" rel="noopener"' : ""}>${label}</a>`;
  });
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/(^|[\s(])\*([^*\s][^*]*)\*(?=[\s).,]|$)/g, "$1<em>$2</em>");
  return t.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${esc(codes[+i])}</code>`);
}
const imgSrc = (src, base) => /^https?:/i.test(src) ? src : "/docs/" + src.replace(/^\.?\/*/, "").replace(/[^A-Za-z0-9_.\/% -]/g, "");

function markdown(md, base) {
  const lines = md.replace(/\r/g, "").split("\n"), out = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (/^```/.test(l)) {
      const buf = []; i++;
      while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
      i++; out.push(`<pre><code>${esc(buf.join("\n"))}</code></pre>`); continue;
    }
    const h = /^(#{1,4})\s+(.*)$/.exec(l);
    if (h) { out.push(`<h${h[1].length} id="${h[2].toLowerCase().replace(/[^a-z0-9]+/g, "-")}">${inline(h[2], base)}</h${h[1].length}>`); i++; continue; }
    if (/^\s*(---|\*\*\*)\s*$/.test(l)) { out.push("<hr>"); i++; continue; }
    if (/^\|.*\|\s*$/.test(l) && /^\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
      const cells = r => r.trim().replace(/^\||\|$/g, "").split("|").map(c => c.trim());
      const head = cells(l); i += 2; const rows = [];
      while (i < lines.length && /^\|.*\|\s*$/.test(lines[i])) rows.push(cells(lines[i++]));
      out.push(`<table><thead><tr>${head.map(c => `<th>${inline(c, base)}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${inline(c, base)}</td>`).join("")}</tr>`).join("")}</tbody></table>`); continue;
    }
    if (/^\s*([*-]|\d+\.)\s+/.test(l)) {
      const ordered = /^\s*\d+\./.test(l), items = [];
      while (i < lines.length && /^\s*([*-]|\d+\.)\s+/.test(lines[i])) {
        let item = lines[i++].replace(/^\s*([*-]|\d+\.)\s+/, "");
        while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !/^\s*([*-]|\d+\.)\s+/.test(lines[i])) item += " " + lines[i++].trim();
        items.push(item);
      }
      out.push(`<${ordered ? "ol" : "ul"}>${items.map(x => `<li>${inline(x, base)}</li>`).join("")}</${ordered ? "ol" : "ul"}>`); continue;
    }
    if (/^>\s?/.test(l)) {
      const buf = []; while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ""));
      out.push(`<blockquote>${inline(buf.join(" "), base)}</blockquote>`); continue;
    }
    if (!l.trim()) { i++; continue; }
    const buf = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|\||>|\s*([*-]|\d+\.)\s+)/.test(lines[i])) buf.push(lines[i++]);
    const only = buf.length === 1 && /^!\[[^\]]*\]\([^)]+\)$/.test(buf[0].trim());      // a picture on its own line gets the full width
    out.push(only ? `<div class="fig">${inline(buf[0].trim(), base)}</div>` : `<p>${inline(buf.join(" "), base)}</p>`);
  }
  return out.join("\n");
}

async function main() {
  let list = [];
  try { list = await (await fetch("/api/docs")).json(); } catch (e) { /* shown below */ }
  if (!list.length) { $("#doc").innerHTML = "<h1>Guide</h1><p>The guide pages could not be found. They are in the docs folder of the project.</p>"; return; }
  $("#nav").innerHTML = `<div class="brand" style="margin-bottom:18px"><span class="mark" style="margin-right:10px">?</span>Guide</div>` +
    list.map(d => `<a href="#${encodeURIComponent(d.name)}" data-n="${esc(d.name)}">${esc(d.name)}</a>`).join("") + `<a class="back" href="/">Back to the setup</a><button class="sidelink" type="button" data-theme-toggle></button>`;
  const dark = () => document.documentElement.dataset.theme === "dark";
  const svg = p => `<svg class="i" viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`;
  const SUN = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>', MOON = '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>';
  const label = () => { document.querySelector("[data-theme-toggle]").innerHTML = dark() ? svg(SUN) + "<span>Switch to light mode</span>" : svg(MOON) + "<span>Switch to dark mode</span>"; };
  document.querySelector(".back").innerHTML = svg('<path d="M19 12H5M11 6l-6 6 6 6"/>') + "<span>Back to the setup</span>";
  label();
  document.querySelector("[data-theme-toggle]").onclick = () => { const t = dark() ? "light" : "dark"; document.documentElement.dataset.theme = t; try { localStorage.setItem("mss-theme", t); } catch (e) { /* not saved */ } label(); };
  const show = async () => {
    const name = decodeURIComponent(location.hash.slice(1)) || list[0].name;
    const d = list.find(x => x.name === name) || list[0];
    document.querySelectorAll("#nav a[data-n]").forEach(a => a.classList.toggle("on", a.dataset.n === d.name));
    try {
      const r = await fetch("/docs/" + encodeURIComponent(d.file));
      $("#doc").innerHTML = markdown(await r.text(), "");
      document.title = d.name + " - Guide";
    } catch (e) { $("#doc").innerHTML = "<p>This page could not be loaded.</p>"; }
    window.scrollTo(0, 0);
  };
  window.addEventListener("hashchange", show);
  show();
}
main();
