// The site's menu (src/menu.html; DESIGN.md 4): one control fixed at the top left, the wordmark with a small
// "Menu" label, that opens a panel of links directly beneath it. A disclosure: the button says whether the panel
// is open (aria-expanded) and which it controls; the panel is a nav of plain links, so a reader's own link
// handling applies (on the one page, src/onepage/boot.ts scrolls to a section and marks the current one).
//
// - Opens on a click, Enter or Space (focus moves to the current item, or the first), or Down (the first) and
//   Up (the last). Inside it, Up and Down move between the items, Home and End to the ends.
// - Closes on choosing an item, on Escape (focus back on the button), on a click outside, and when focus leaves
//   it (Tab past its last item).
// - The current page or section is the link marked aria-current="page": on the one page boot.ts keeps it, on a
//   separate page it is marked here from the address (the Eucalyptus page; none on the demo or the viewer).
const ctl = document.querySelector<HTMLElement>(".top");   // the control and its panel
const btn = ctl?.querySelector<HTMLButtonElement>(".menu-btn");
const panel = ctl?.querySelector<HTMLElement>(".menu-panel");

if (ctl && btn && panel) {
  const items = () => [...panel.querySelectorAll<HTMLAnchorElement>("a")];
  const isOpen = () => btn.getAttribute("aria-expanded") === "true";
  const open = (focus: "current" | "first" | "last" | null) => {
    panel.hidden = false; btn.setAttribute("aria-expanded", "true"); ctl.classList.add("open");
    const all = items();
    const to = focus === "current" ? all.find((a) => a.getAttribute("aria-current")) ?? all[0] : focus === "first" ? all[0] : focus === "last" ? all.at(-1) : null;
    to?.focus();
  };
  const close = (refocus: boolean) => {
    if (!isOpen()) return;
    panel.hidden = true; btn.setAttribute("aria-expanded", "false"); ctl.classList.remove("open");
    if (refocus) btn.focus();
  };
  // a click by pointer opens it without moving focus into it; by keyboard (no pointer: detail 0), focus moves in
  btn.addEventListener("click", (e) => { if (isOpen()) close(false); else open(e.detail === 0 ? "current" : null); });
  btn.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); open("first"); }
    else if (e.key === "ArrowUp") { e.preventDefault(); open("last"); }
  });
  panel.addEventListener("keydown", (e) => {
    const all = items(), i = all.indexOf(document.activeElement as HTMLAnchorElement);
    const go = (j: number) => { e.preventDefault(); all[(j + all.length) % all.length]?.focus(); };
    if (e.key === "ArrowDown") go(i + 1);
    else if (e.key === "ArrowUp") go(i - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(all.length - 1);
  });
  // choosing an item closes it (the link itself does the rest: a section scroll, the paper, a page)
  panel.addEventListener("click", (e) => { if ((e.target as Element).closest("a")) close(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && isOpen()) { e.preventDefault(); close(ctl.contains(document.activeElement)); } });
  document.addEventListener("pointerdown", (e) => { if (isOpen() && !ctl.contains(e.target as Node)) close(false); }, { passive: true });
  ctl.addEventListener("focusout", (e) => { if (isOpen() && e.relatedTarget && !ctl.contains(e.relatedTarget as Node)) close(false); });

  // a separate page marks its own entry (the one page's boot.ts marks the section on screen)
  if (!document.documentElement.dataset.start) {
    const here = location.pathname === "/index.html" ? "/" : location.pathname;
    for (const a of items()) if (new URL(a.href).origin === location.origin && new URL(a.href).pathname === here) a.setAttribute("aria-current", "page");
  }
}

export {};
