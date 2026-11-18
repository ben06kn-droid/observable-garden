// The in-page instrument for measuring with real input (scripts/onepage_measure.mjs; on site-revamp, the carry profiler). Injected first in the <head> of a COPY of the
// built chain pages, never into dist/ itself. Nothing attached to the browser, so Chrome prerenders as it would for
// a visitor. Records, on each document: marks (the carry's trigger, pageswap, pagereveal, the view transition's
// ready and finished, WebGL and Worker creation), every animation frame's time, long animation frames (Chrome),
// how the document was entered (prerendered or not), the landing (carry.js's window.__carry), and the scroll
// position over time; posts it to the profiler's server (/__carry-log) as the page is left and every second.
(function () {
  var T = function () { return performance.timeOrigin + performance.now(); };   // epoch ms, comparable across pages
  var L = { path: location.pathname, ua: navigator.userAgent, vw: innerWidth, vh: innerHeight, marks: [], frames: [], scroll: [], loaf: [], wheel: [], start: T() };
  // where the page sits on the screen, for the driver's swipes: the content's top-left, in screen points
  var where = function () { L.vw = innerWidth; L.vh = innerHeight; L.sx = screenX; L.sy = screenY + (outerHeight - innerHeight); };
  addEventListener("wheel", function (e) { if (L.wheel.length < 1500) L.wheel.push([Math.round(T()), Math.round(e.deltaY), Math.round(scrollY), Math.round(document.documentElement.scrollHeight - innerHeight)]); }, { passive: true, capture: true });
  var mark = function (n) { L.marks.push([T(), n]); };
  window.__instrMark = mark;
  mark(document.prerendering ? "doc-start (prerendering)" : "doc-start");
  document.addEventListener("prerenderingchange", function () { mark("activated"); });
  var gc = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type) { if (!this.__m) { this.__m = 1; mark("getContext " + type + " " + (this.className || "?")); } return gc.apply(this, arguments); };
  var W = window.Worker; if (W) { var Wp = function (u, o) { mark("worker"); return new W(u, o); }; Wp.prototype = W.prototype; window.Worker = Wp; }
  var si = Storage.prototype.setItem;
  Storage.prototype.setItem = function (k, v) { if (k === "qx-carry" && !L.trigger) { L.trigger = T(); mark("carry-trigger"); } return si.apply(this, arguments); };
  addEventListener("pageswap", function (e) { mark("pageswap vt=" + !!e.viewTransition); send(); }, true);
  addEventListener("pagereveal", function (e) {
    mark("pagereveal vt=" + !!e.viewTransition);
    var vt = e.viewTransition;
    if (vt) { vt.ready.then(function () { mark("vt-ready"); }, function () { mark("vt-ready-rejected"); }); vt.finished.then(function () { mark("vt-finished"); send(); }, function () { mark("vt-finished-rejected"); }); }
  }, true);
  var lastY = -1;
  // each frame's own time (the callback's timestamp: when the frame began), not when the callback happened to run
  var f = function (ts) { var t = performance.timeOrigin + ts; if (L.frames.length < 4000) L.frames.push(Math.round(t * 10) / 10); var y = Math.round(scrollY); if (y !== lastY) { L.scroll.push([t, y]); lastY = y; } requestAnimationFrame(f); };
  requestAnimationFrame(f);
  try { new PerformanceObserver(function (l) { l.getEntries().forEach(function (e) { L.loaf.push([performance.timeOrigin + e.startTime, Math.round(e.duration), Math.round(e.blockingDuration),
    e.scripts.map(function (x) { return [(x.sourceURL || "").split("/").pop(), x.sourceFunctionName, x.sourceCharPosition, Math.round(x.duration), x.invokerType, String(x.invoker).slice(0, 60)]; }), Math.round(scrollY)]); }); }).observe({ type: "long-animation-frame", buffered: true }); } catch (e) {}
  var send = function () {
    try {
      var n = performance.getEntriesByType("navigation")[0];
      L.activationStart = n ? n.activationStart : null; L.nav = n ? { responseEnd: n.responseEnd, domInteractive: n.domInteractive } : null;
      L.carry = window.__carry ? { dir: window.__carry.dir, viewTransition: window.__carry.viewTransition, landing: window.__carry.landing || null, frames: window.__carry.frames || null } : null;
      L.pmarks = performance.getEntriesByType("mark").map(function (m) { return [m.name, performance.timeOrigin + m.startTime]; });
      L.sections = [].slice.call(document.querySelectorAll("[data-section]")).map(function (s) { return [s.getAttribute("data-section"), Math.round(s.getBoundingClientRect().top + scrollY)]; });
      where(); L.sent = T();
      navigator.sendBeacon("/__carry-log", JSON.stringify(L));
    } catch (e) {}
  };
  addEventListener("pagehide", send);
  setInterval(send, 1000);
})();
