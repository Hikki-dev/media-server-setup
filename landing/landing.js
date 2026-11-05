/* The light and dark switch, the Windows and Linux tabs, and a copy button for the install command.
   Nothing else is needed: the page reads fine without any of it. */
(() => {
  /* theme: light is the default, and the visitor's own choice is remembered */
  const root = document.documentElement, toggle = document.getElementById("theme");
  const paint = () => {
    const dark = root.dataset.theme === "dark";
    const label = dark ? "Switch to light mode" : "Switch to dark mode";
    toggle.setAttribute("aria-label", label);
    toggle.title = label;
  };
  toggle.addEventListener("click", () => {
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try { localStorage.setItem("theme", root.dataset.theme); } catch (e) { /* private window: fine, it just is not remembered */ }
    paint();
  });
  paint();

  /* tabs */
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  const show = tab => {
    tabs.forEach(t => {
      const on = t === tab;
      t.setAttribute("aria-selected", on);
      t.tabIndex = on ? 0 : -1;
      document.getElementById(t.getAttribute("aria-controls")).hidden = !on;
    });
  };
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => show(t));
    t.addEventListener("keydown", e => {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      const next = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length];
      show(next); next.focus();
    });
  });

  /* copy */
  const btn = document.getElementById("copy"), msg = document.getElementById("copied");
  const text = () => document.getElementById("cmd").textContent.trim();
  const done = ok => {
    msg.textContent = ok ? "Copied. Paste it into your terminal." : "Select the command and copy it.";
    setTimeout(() => { msg.textContent = ""; }, 4000);
  };
  btn.addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(text()); done(true); }
    catch (e) {
      const r = document.createRange(); r.selectNodeContents(document.getElementById("cmd"));
      const s = getSelection(); s.removeAllRanges(); s.addRange(r);
      try { done(document.execCommand("copy")); } catch (err) { done(false); }
    }
  });
})();
