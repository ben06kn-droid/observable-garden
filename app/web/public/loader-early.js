// The one-page site's first word, before its first frame (a classic, render-blocking script in <head>): if the
// loading screen has already played in this browser session, this load is a rebuild (coming back from the demo,
// the viewer or Eucalyptus without the browser's back-forward cache), and the screen shows the finished B at once,
// with no minimum time (src/styles/loader.css, src/loader.ts).
(function () {
  try { if (sessionStorage.getItem("qx-loader-seen") === "1") document.documentElement.setAttribute("data-loader", "formed"); } catch (e) { /* private mode */ }
})();
