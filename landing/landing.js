/* Tabs, and a copy button for the install command. Nothing else is needed: the page works without it. */
(() => {
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

  const btn = document.getElementById("copy"), msg = document.getElementById("copied"), slate = document.querySelector(".slate");
  const text = () => document.getElementById("cmd").textContent.trim();
  const done = ok => {
    msg.textContent = ok ? "Copied. Paste it into your terminal." : "Select the command and copy it.";
    slate.classList.add("clap");
    setTimeout(() => slate.classList.remove("clap"), 350);
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
