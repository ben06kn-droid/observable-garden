/* Shared behaviour: theme switch, reveal on scroll, the verdict counters, the status line.
   Loaded in <head> without defer so the theme is set before first paint (no inline script,
   which keeps the later content security policy strict). */
(function () {
  "use strict";
  var root = document.documentElement;
  root.classList.add("js");
  var saved = null;
  try { saved = localStorage.getItem("qx-theme"); } catch (e) { /* storage may be blocked */ }
  var forced = (location.search.match(/[?&]theme=(light|dark)/) || [])[1];   // for review and screenshots
  if (forced) root.dataset.theme = forced;
  else if (saved === "light" || saved === "dark") root.dataset.theme = saved;

  function current() {
    if (root.dataset.theme) return root.dataset.theme;
    return window.matchMedia && matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  // ?still renders every page in its final state with no motion, as reduced motion does
  if (/[?&]still\b/.test(location.search)) root.classList.add("still");
  var reduce = root.classList.contains("still") ||
    (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches);

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
    if (reduce) { node.textContent = to.toFixed(dec); return; }
    var t0 = null, dur = 1400;
    function frame(t) {
      if (t0 === null) t0 = t;
      var k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      node.textContent = (to * e).toFixed(dec);
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
  function sep() { return '<span class="sep">·</span>'; }
  function lastRun(QX) {
    var v = QX.verdict, w = WORD[v.status] || v.status;
    status("LAST RUN " + sep() + ' <span class="v">' + w + "</span> " + sep() + " p " + v.p_replay.toFixed(2), false);
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.querySelector(".theme");
    function label() {
      var c = current();
      btn.textContent = c === "dark" ? "Day" : "Night";
      btn.setAttribute("aria-label", c === "dark" ? "Switch to the day theme" : "Switch to the night theme");
    }
    if (btn) {
      label();
      btn.addEventListener("click", function () {
        var next = current() === "dark" ? "light" : "dark";
        root.dataset.theme = next;
        try { localStorage.setItem("qx-theme", next); } catch (e) { /* fine without it */ }
        label();
      });
    }

    var io = "IntersectionObserver" in window ? new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
    }, { rootMargin: "0px 0px -10% 0px" }) : null;
    document.querySelectorAll(".reveal").forEach(function (n) { io ? io.observe(n) : n.classList.add("in"); });

    document.querySelectorAll(".reasons li").forEach(function (li) {
      var b = li.querySelector("button");
      if (!b) return;
      b.addEventListener("click", function () {
        var open = li.classList.toggle("open");
        b.textContent = open ? "Less" : "More";
        b.setAttribute("aria-expanded", open);
      });
    });

    document.querySelectorAll("[data-copy]").forEach(function (b) {
      b.addEventListener("click", function () {
        var src = document.querySelector(b.dataset.copy);
        var text = src ? src.textContent : location.href;
        if (navigator.clipboard) navigator.clipboard.writeText(text).then(function () {
          var was = b.textContent; b.textContent = "Copied"; setTimeout(function () { b.textContent = was; }, 1400);
        });
      });
    });
  });

  window.QX_UI = { countUp: countUp, status: status, sep: sep, lastRun: lastRun, WORD: WORD, MEANING: MEANING, reduce: reduce };
})();
