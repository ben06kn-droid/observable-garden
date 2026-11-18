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
    if (c.col) h.style.setProperty("--carry-cover", c.col);
    // where the page being left was captured: the arriving page starts the rest of the way off screen
    var vh = innerHeight, o = Math.max(0, Math.min(vh, (c.o || 0) * (c.vh ? vh / c.vh : 1))), rest = vh - o;
    h.style.setProperty("--carry-rest", rest.toFixed(1) + "px");
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
    var last = c.w ? performance.now() - (Date.now() - c.w) : -1e9, low = c.a || 0, peak = c.a || 0, rise = 0, first = true, swallowed = 0, start = 0, recent = [], sign = c.dir === "up" ? -1 : 1, on = true;
    var stop = function () { if (!on) return; on = false; removeEventListener("wheel", swallow, { passive: false }); };
    var swallow = function (e) {
      // as src/chain.ts reads a gesture: its strength as px per 60 Hz frame over the last 50 ms (bursts and merged
      // events are not a new swipe), and a new swipe is a pause, a reversal, or the strength rising again after it
      // had begun to fall, two events running
      var now = e.timeStamp || performance.now(), unit = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? innerHeight : 1, dy = e.deltaY * unit;
      var dt = now - last;
      if (first) start = now;
      recent.push([now, Math.abs(dy)]); while (recent.length && recent[0][0] < now - 50) recent.shift();
      var sum = 0; for (var i = 0; i < recent.length; i++) sum += recent[i][1];
      var r = sum * 16.7 / Math.min(50, now - start + 16.7);   // px per 60 Hz frame over the last 50 ms
      rise = !first && low < peak * 0.8 && r > Math.max(low * 1.6, low + 4) && r >= 6 ? rise + 1 : 0;
      // the wheel events that come while the browser changes pages reach neither page, so the first one here may
      // follow a gap of a few hundred ms and still be the same gesture: up to 500 ms is allowed for it, 100 after
      var fresh = dt > (first ? 500 : 100) || (dy !== 0 && (dy > 0 ? 1 : -1) !== sign) || rise >= 2;
      if (fresh) { window.__carry.landing = { swallowed: swallowed, ended: dt > (first ? 500 : 100) ? "pause " + Math.round(dt) + " ms" : rise >= 2 ? "rise" : "reversal" }; stop(); mark(); return; }
      first = false; last = now;
      if (r >= peak) { peak = r; low = r; } else low = Math.min(low, r);   // low: the lowest point since the peak
      swallowed++; e.preventDefault();
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
      if (e.viewTransition) {
        var words = play(e.viewTransition);
        e.viewTransition.finished.then(function () { return words; }, function () { return words; }).then(over, over);
      }
      else if (c.cover) setTimeout(over, 650);   // the fallback's cover lifts over 600 ms (chain.css)
      else over();
    };
    // The motion, continued: lukres.dev's eased scroll, each frame closing 1 - e^(-12 dt) of the way. Memoryless,
    // so taking it up from wherever the page being left was captured keeps its speed. Run over 0.6 s (by then
    // under 0.1% of the way is left), as a linear() easing. The header holds still and turns to the new page's
    // as the moving edge passes under it; the headline's words rise once it is in view.
    var K = 12, D = 0.6, norm = 1 - Math.exp(-K * D);
    var pts = []; for (var i = 0; i <= 24; i++) { var x = i / 24; pts.push(((1 - Math.exp(-K * D * x)) / norm).toFixed(4)); }
    var EASE = "linear(" + pts.join(", ") + ")";
    var at = function (p) { return p <= 0 ? 0 : p >= 1 ? D : -Math.log(1 - p * norm) / K; };   // time when the motion is at progress p
    function play(vt) {
      var sgn = c.dir === "down" ? -1 : 1, ms = D * 1000;
      var wordsDone = Promise.resolve();
      if (c.dir === "down") wordsDone = raiseWords(function (top) { return at(1 - (vh - top) / Math.max(1, rest)); });
      vt.ready.then(function () {
        var opts = function (p) { return { duration: ms, easing: EASE, fill: "both", pseudoElement: p }; };
        h.animate([{ transform: "translate3d(0, 0, 0)" }, { transform: "translate3d(0, " + (sgn * rest).toFixed(1) + "px, 0)" }], opts("::view-transition-old(root)"));
        h.animate([{ transform: "translate3d(0, " + (-sgn * rest).toFixed(1) + "px, 0)" }, { transform: "translate3d(0, 0, 0)" }], opts("::view-transition-new(root)"));
        // the header turns in one frame, as the moving edge passes under it: everything below it is then the new
        // page (a cross-fade between two opaque headers, one light and one dark, passes through grey)
        var head = document.querySelector(".top"), hh = head ? head.getBoundingClientRect().bottom : 0;
        var flip = at(c.dir === "down" ? 1 - hh / Math.max(1, rest) : 1 - (vh - hh) / Math.max(1, rest)) * 1000;
        h.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 1, delay: flip, fill: "both", pseudoElement: "::view-transition-new(top)" });
        h.animate([{ opacity: 1 }, { opacity: 1 }], { duration: Math.max(ms, flip + 1), fill: "both", pseudoElement: "::view-transition-old(top)" });
      }, function () {});
      return wordsDone;
    }
    // the headline's words, each in its own mask; unwrapped (the original nodes put back) once they have risen
    function raiseWords(startAt) {
      var h1 = document.querySelector("main h1");
      if (!h1) return Promise.resolve();
      var clone = h1.cloneNode(true), undone = false;
      var start = startAt(h1.getBoundingClientRect().top) * 1000, n = 0, last = null;
      var walk = function (node) {
        Array.prototype.slice.call(node.childNodes).forEach(function (t) {
          if (t.nodeType === 1) { walk(t); return; }
          if (t.nodeType !== 3 || !t.textContent.trim()) return;
          var frag = document.createDocumentFragment();
          t.textContent.split(/(\s+)/).forEach(function (w) {
            if (!w) return;
            if (/^\s+$/.test(w)) { frag.appendChild(document.createTextNode(w)); return; }
            var m = document.createElement("span"), inner = document.createElement("span");
            m.className = "carry-w"; inner.textContent = w;
            inner.style.setProperty("--d", Math.round(start + 100 * n++) + "ms");
            m.appendChild(inner); frag.appendChild(m); last = inner;
          });
          t.parentNode.replaceChild(frag, t);
        });
      };
      walk(h1);
      if (!last) return Promise.resolve();
      return new Promise(function (r) {
        var undo = function () { if (undone) return; undone = true; h1.replaceChildren.apply(h1, Array.prototype.slice.call(clone.childNodes)); r(); };
        last.addEventListener("animationend", undo, { once: true });
        setTimeout(undo, start + 100 * n + 1400);   // a backstop
      });
    }
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
