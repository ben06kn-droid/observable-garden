// The arriving half of a carry between the chain's pages (src/chain.ts is the leaving half). A classic,
// render-blocking script in <head>, so it runs before the page's first frame: it reads what the page
// being left wrote to sessionStorage and marks <html> with the direction (data-carry), and with
// data-carry-cover on the fallback path, where no cross-document view transition plays. A carry upward
// lands at the page's end. Anything else (a typed URL, a link, Back) is left alone.
//
// A page the leaving page prerendered (Chrome) runs this script long before it is shown, when there is no
// carry to read yet: it then reads the carry when the page is activated (prerenderingchange).
//
// window.__carry.done resolves once the arrival is over (the view transition finished, the fallback's
// cover lifted, or at once without either); src/chain.ts waits for it before the page starts its heavy
// work (WebGL, Pyodide) and before a new carry can arm.
(function () {
  var h = document.documentElement;
  function arrive() {
    var raw = null, c = null;
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
    var finish, done = new Promise(function (r) { finish = r; });
    window.__carry = { dir: c.dir, cover: !!c.cover, viewTransition: false, done: done };   // read by chain.ts and the browser check

    // The rest of the gesture that made the carry (a trackpad's momentum) arrives here: it must not scroll
    // the page it landed on. Only that gesture is swallowed. The leaving page recorded when its last wheel
    // event came and how strong it was (c.w, c.a); events here continue that gesture while they keep
    // coming (no pause over 100 ms) and keep falling. A new swipe (a pause, a reversal, or the wheel
    // speeding up again) is the visitor's own and scrolls at once. A wheel listener that is not passive
    // makes every scroll wait for the main thread, so this one removes itself as soon as the gesture ends.
    var last = c.w ? performance.now() - (Date.now() - c.w) : -1e9, low = c.a || 0, peak = c.a || 0, rise = 0, sign = c.dir === "up" ? -1 : 1, on = true;
    var stop = function () { if (!on) return; on = false; removeEventListener("wheel", swallow, { passive: false }); };
    var swallow = function (e) {
      // as src/chain.ts reads a gesture: strength as px per 60 Hz frame (merged events are not a new swipe), and a
      // new swipe is a pause, a reversal, or the strength rising again after it had begun to fall, two events running
      var now = e.timeStamp || performance.now(), unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? innerHeight : 1, dy = e.deltaY * unit;
      var r = Math.abs(dy) * 16.7 / Math.max(8, Math.min(60, now - last));
      rise = low < peak * 0.8 && r > Math.max(low * 1.6, low + 4) && r >= 6 ? rise + 1 : 0;
      var fresh = now - last > 100 || (dy !== 0 && (dy > 0 ? 1 : -1) !== sign) || rise >= 2;
      if (fresh) { stop(); mark(); return; }
      last = now; low = Math.min(low, r); peak = Math.max(peak, r);
      e.preventDefault();
    };
    addEventListener("wheel", swallow, { passive: false });
    setTimeout(stop, 2500);   // a backstop: no momentum lasts this long
    addEventListener("touchstart", mark, { passive: true, once: true });
    addEventListener("keydown", mark, { once: true });

    var revealed = false;
    var onReveal = function (e) {
      if (revealed) return; revealed = true;
      window.__carry.viewTransition = !!e.viewTransition;
      // the frames this page draws while the carry plays (1.1 s), for the browser check
      var gaps = [], lt = 0, t0 = performance.now();
      var f = function (t) { if (lt) gaps.push(t - lt); lt = t; if (t - t0 < 1100) requestAnimationFrame(f);
        else window.__carry.frames = { count: gaps.length, longest_ms: Math.round(Math.max.apply(null, gaps.concat([0]))), over_20ms: gaps.filter(function (g) { return g > 20; }).length }; };
      requestAnimationFrame(f);
      end();
      var over = function () { h.removeAttribute("data-carry"); finish(); };
      if (e.viewTransition) e.viewTransition.finished.then(over, over);
      else if (c.cover) setTimeout(over, 650);   // the fallback's cover lifts over 600 ms (chain.css)
      else over();
    };
    addEventListener("pagereveal", onReveal);
    setTimeout(function () { if (!revealed) { revealed = true; h.removeAttribute("data-carry"); finish(); } }, 2500);   // no pagereveal (an older browser)
    addEventListener("DOMContentLoaded", end);
    // late layout (fonts, the page's own script) can lengthen the page: stay at the end unless the visitor moved
    var settle = function () { if (!userMoved) end(); setTimeout(function () { if (!userMoved) end(); h.removeAttribute("data-carry-cover"); }, 700); };
    if (document.readyState === "complete") settle(); else addEventListener("load", settle);
  }
  if (document.prerendering) document.addEventListener("prerenderingchange", arrive, { once: true });
  else arrive();
})();
