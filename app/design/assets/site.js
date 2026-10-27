/* Shared behaviour: the light, reveal on scroll, the verdict counters, the status line.
   Loaded in <head> without defer so the first paint already has the right light (no inline
   script, which keeps the later content security policy strict).

   THE LIGHT FOLLOWS THE STAGE OF A RUN: day while the search grows, night while the null
   re-runs it and at the verdict. One number, n (0 day, 1 night), sets every colour:
   - home: the stage is the section being read (01 the search in daylight, 02 the null onward at
     night), so n follows scroll and goes back to day when the reader scrolls back up;
   - demo-running: n follows the run, 0 during the search, rising with the replicates;
   - the run form is before any search (day); a verdict page is after the null (night).
   Background and graphics interpolate; each text colour is then pushed toward black or white
   only as far as it must go to keep WCAG AA against that background (4.5:1 text, 3:1 graphics). */
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.add("js");
  if (/[?&]still\b/.test(location.search)) root.classList.add("still");
  var reduce = root.classList.contains("still") ||
    (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);

  // [day, night, need, dusk]; `need` is the contrast each must keep against --bg (0: decorative).
  // The page colours pass through a warm dusk at n = 0.5, so the crossover reads as evening light
  // rather than a dimmer.
  var TOKENS = {
    bg:           ["#f7f5ee", "#060912", 0, "#8a7656"],
    surface:      ["#fdfcf8", "#0c1220", 0, "#8f7b5a"],
    ink:          ["#1b1d18", "#e6ebe0", 4.5],
    muted:        ["#4f544a", "#a3ad9e", 4.5],
    faint:        ["#5f6559", "#8b9787", 4.5],
    "amber-text": ["#8a5800", "#f5b544", 4.5],
    tree:         ["#2f7a43", "#3dff8b", 3],
    ghost:        ["#6f8f77", "#3d6b50", 3],
    rule:         ["#dcd8cb", "#1c2433", 0, "#a08c69"],
    amber:        ["#d99a2b", "#f5b544", 0],
    "on-amber":   ["#1b1d18", "#060912", 0]
  };
  // numbers: [day, night, from]: linear from n = `from` to 1. The trees thicken and glow only in
  // the night half, and thin out and lose the glow on the way back to day.
  var NUMS = {
    "tree-w": [1.1, 2.1, 0.45], glow: [0, 1, 0.5], "canopy-a": [0.05, 0.09, 0.3], "beam-a": [0.32, 0.16, 0],
    "grid-a": [0.05, 0.07, 0], "scan-a": [0, 0.022, 0.5], "grain-o": [0.05, 0.07, 0]
  };

  function hex(h) { return [1, 3, 5].map(function (i) { return parseInt(h.slice(i, i + 2), 16); }); }
  function toHex(c) { return "#" + c.map(function (x) { return ("0" + Math.round(Math.max(0, Math.min(255, x))).toString(16)).slice(-2); }).join(""); }
  function mix(a, b, t) { return a.map(function (x, i) { return x + (b[i] - x) * t; }); }
  function lum(c) {
    var l = c.map(function (x) { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); });
    return 0.2126 * l[0] + 0.7152 * l[1] + 0.0722 * l[2];
  }
  function contrast(a, b) { var x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }

  // push c toward black or white, whichever reaches `need` against every backing in the smaller step
  function fit(c, backs, need) {
    var worst = function (d) { return Math.min.apply(null, backs.map(function (b) { return contrast(d, b); })); };
    if (!need || worst(c) >= need) return c;
    var best = null, fallback = null;
    [[0, 0, 0], [255, 255, 255]].forEach(function (end) {
      for (var t = 0.02; t <= 1.0001; t += 0.02) {
        var d = mix(c, end, t), w = worst(d);
        if (!fallback || w > fallback.w) fallback = { w: w, c: d };
        if (w >= need) { if (!best || t < best.t) best = { t: t, c: d }; return; }
      }
    });
    return (best || fallback).c;
  }

  function at(t, n) {                       // day -> (dusk) -> night
    if (!t[3]) return mix(hex(t[0]), hex(t[1]), n);
    return n < 0.5 ? mix(hex(t[0]), hex(t[3]), n * 2) : mix(hex(t[3]), hex(t[1]), n * 2 - 1);
  }
  function palette(n) {
    // near the crossover no text colour can clear two different backings, so cards converge to the
    // page colour there (they keep their border) and separate again on either side
    var out = {}, bg = at(TOKENS.bg, n), surface = mix(bg, at(TOKENS.surface, n), Math.min(1, Math.abs(n - 0.5) * 2.5));
    Object.keys(TOKENS).forEach(function (k) {
      var t = TOKENS[k], c = k === "surface" ? surface : at(t, n);
      // text sits on the page and on cards, so it must clear both; a small margin over the threshold
      if (t[2]) c = fit(c, t[2] >= 4.5 ? [bg, surface] : [bg], t[2] + 0.05);
      out[k] = toHex(c);
    });
    Object.keys(NUMS).forEach(function (k) {
      var v = NUMS[k], u = Math.max(0, Math.min(1, (n - v[2]) / (1 - v[2])));
      out[k] = v[0] + (v[1] - v[0]) * u;
    });
    return out;
  }

  var current = -1;
  function setNight(n) {
    n = Math.max(0, Math.min(1, n));
    if (Math.abs(n - current) < 0.004) return;
    current = n;
    var p = palette(n), s = root.style;
    Object.keys(p).forEach(function (k) { s.setProperty("--" + k, typeof p[k] === "number" ? p[k].toFixed(3) : p[k]); });
    root.dataset.light = n < 0.5 ? "day" : "night";
  }
  var forced = (location.search.match(/[?&]n=([01](?:\.\d+)?)/) || [])[1];    // review and screenshots
  function stage(n) { setNight(forced !== undefined ? +forced : n); }
  // the page's stage, from <html data-stage>: "day", "night", "scroll" (home) or "run" (the demo drives it)
  var mode = root.dataset.stage || "day";
  stage(mode === "night" ? 1 : 0);

  // README vocabulary on screen: the code's CERTIFIED is the README's PASS
  var WORD = { CERTIFIED: "PASS" };
  var MEANING = {
    PASS: "p is below α: the submitted rule beats what the search would find on noise.",
    FAIL: "p is at or above α, and the test had the power to tell: the result is what this search finds by luck.",
    INADMISSIBLE: "p is at or above α, and the search was too wide to certify anything: the test's power against the reference Sharpe (1.0 by default) is below the power floor (0.20).",
    UNDECIDABLE: "the record alone cannot license a correction, for example returns logged without the search that chose them.",
    DEGENERATE: "the test statistic broke on this menu. Do not read its p."
  };

  function countUp(node) {
    var to = parseFloat(node.dataset.count), dec = +(node.dataset.decimals || 3);
    var fmt = function (x) { return (node.dataset.sign && x > 0 ? "+" : "") + x.toFixed(dec); };
    if (reduce) { node.textContent = fmt(to); return; }
    var t0 = null, dur = 1400;
    function frame(t) {
      if (t0 === null) t0 = t;
      var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      node.textContent = fmt(to * e);
      if (k < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  function status(html, live) {
    var s = document.querySelector(".status");
    if (!s) return;
    s.querySelector(".txt").innerHTML = html;
    if (live) s.setAttribute("data-live", ""); else s.removeAttribute("data-live");
  }
  function pfmt(p) { return p < 0.01 ? p.toFixed(4) : p.toFixed(2); }   // never round a small p to 0.00
  function sep() { return '<span class="sep">·</span>'; }
  function lastRun(ex) {
    var v = ex.verdict, w = WORD[v.status] || v.status;
    status("LAST RUN " + sep() + ' <span class="v">' + w + "</span> " + sep() + " p " + pfmt(v.p_replay), false);
  }
  // the demo pages' example, from ?ex=, defaulting to the first
  function example() {
    var key = (location.search.match(/[?&]ex=(\w+)/) || [])[1];
    var exs = window.QX.examples;
    return exs[key] || exs[Object.keys(exs)[0]];
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (mode === "scroll") {
      var target = document.querySelector("[data-night-from]");
      var onScroll = function () {
        var vh = window.innerHeight, top = target.getBoundingClientRect().top;
        if (reduce) { stage(top < vh * 0.55 ? 1 : 0); return; }        // the state, without the transition
        var t = (vh * 0.85 - top) / (vh * 0.6);
        t = Math.max(0, Math.min(1, t));
        stage(t * t * (3 - 2 * t));
      };
      window.addEventListener("scroll", onScroll, { passive: true });
      window.addEventListener("resize", onScroll);
      onScroll();
    }

    var io = "IntersectionObserver" in window ? new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -10% 0px" }) : null;
    document.querySelectorAll(".reveal").forEach(function (n) { io ? io.observe(n) : n.classList.add("in"); });

    document.addEventListener("click", function (e) {
      var b = e.target.closest(".reasons button");
      if (b) {
        var li = b.closest("li"), open = li.classList.toggle("open");
        b.textContent = open ? "Less" : "More";
        b.setAttribute("aria-expanded", open);
        return;
      }
      var c = e.target.closest("[data-copy]");
      if (c && navigator.clipboard) {
        var src = c.dataset.copy && document.querySelector(c.dataset.copy);
        navigator.clipboard.writeText(src ? src.textContent : location.href).then(function () {
          var was = c.textContent; c.textContent = "Copied"; setTimeout(function () { c.textContent = was; }, 1400);
        });
      }
    });
  });

  window.QX_UI = { countUp: countUp, status: status, pfmt: pfmt, sep: sep, lastRun: lastRun, example: example, WORD: WORD,
                   MEANING: MEANING, reduce: reduce, setNight: stage, palette: palette, contrast: function (a, b) {
                     return contrast(hex(a), hex(b)); }, TOKENS: TOKENS };
})();
