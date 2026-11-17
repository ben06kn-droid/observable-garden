// The arriving half of a carry between the chain's pages (src/chain.ts is the leaving half). A classic,
// render-blocking script in <head>, so it runs before the page's first frame: it reads what the page
// being left wrote to sessionStorage and marks <html> with the direction (data-carry), and with
// data-carry-cover on the fallback path, where no cross-document view transition plays. A carry upward
// lands at the page's end. Anything else (a typed URL, a link, Back) is left alone.
(function () {
  var raw = null, c = null, h = document.documentElement;
  try { raw = sessionStorage.getItem("qx-carry"); sessionStorage.removeItem("qx-carry"); } catch (e) { return; }
  if (!raw) return;
  try { c = JSON.parse(raw); } catch (e) { return; }
  var here = location.pathname === "/index.html" ? "/" : location.pathname;
  if (!c || c.to !== here || Date.now() - c.t > 5000 || (c.dir !== "down" && c.dir !== "up")) return;
  h.setAttribute("data-carry", c.dir);
  if (c.cover) h.setAttribute("data-carry-cover", c.dir);
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  var end = function () { if (c.dir === "up") window.scrollTo(0, h.scrollHeight); };
  var userMoved = false;
  var mark = function () { userMoved = true; };
  // the rest of the gesture that made the carry (a trackpad's momentum, the last wheel notches) arrives
  // here: it must not scroll the page it landed on. Swallow wheel events while they keep coming, for at
  // most 1.2 s; the first pause of 220 ms ends it, and the visitor's next scroll is their own.
  // Once it has ended, the listener removes itself: a wheel listener that is not passive makes every
  // scroll wait for the main thread, so it must not outlive those 1.2 s.
  var settleUntil = performance.now() + 1200, lastWheel = 0;
  var swallow = function (e) {
    var now = performance.now();
    if (settleUntil && now < settleUntil && (!lastWheel || now - lastWheel < 220)) { lastWheel = now; e.preventDefault(); return; }
    settleUntil = 0; mark(); removeEventListener("wheel", swallow, { passive: false });
  };
  addEventListener("wheel", swallow, { passive: false });
  setTimeout(function () { if (settleUntil) { settleUntil = 0; removeEventListener("wheel", swallow, { passive: false }); } }, 1300);
  addEventListener("touchstart", mark, { passive: true, once: true });
  addEventListener("keydown", mark, { once: true });
  window.__carry = { dir: c.dir, cover: !!c.cover, viewTransition: false };   // read by the browser check
  addEventListener("pagereveal", function (e) {
    window.__carry.viewTransition = !!e.viewTransition;
    // the frames this page draws while the carry plays (1.1 s), for the browser check
    var gaps = [], last = 0, t0 = performance.now();
    var f = function (t) { if (last) gaps.push(t - last); last = t; if (t - t0 < 1100) requestAnimationFrame(f);
      else window.__carry.frames = { count: gaps.length, longest_ms: Math.round(Math.max.apply(null, gaps.concat([0]))), over_20ms: gaps.filter(function (g) { return g > 20; }).length }; };
    requestAnimationFrame(f);
    end();
    if (e.viewTransition) e.viewTransition.finished.then(function () { h.removeAttribute("data-carry"); }, function () { h.removeAttribute("data-carry"); });
  });
  addEventListener("DOMContentLoaded", end);
  // late layout (fonts, the page's own script) can lengthen the page: stay at the end unless the visitor moved
  addEventListener("load", function () { if (!userMoved) end(); setTimeout(function () { if (!userMoved) end(); h.removeAttribute("data-carry-cover"); }, 700); });
})();
