/* The demo's timeline, scripted from the example's real log. In the app this is an SSE stream;
   the order of events here is the order the harness produced them. Log lines are the log's own
   text; lines marked "·" are the app's progress notes, not CLI output. The light follows the
   stage: day through the search, falling to night as the replicates run, night at the verdict. */
document.addEventListener("DOMContentLoaded", function () {
  var QX = window.QX, UI = window.QX_UI, ex = UI.example(), v = ex.verdict, log = ex.log, sep = UI.sep();
  var key = "?ex=" + ex.key;
  QX_CARDS.picker(document.getElementById("picker"), ex);
  document.getElementById("ex-title").textContent = ex.title;
  document.getElementById("h").textContent = ex.blurb;
  document.getElementById("see").href += key;
  document.getElementById("skip").href += key;

  var g = QXGarden.render(document.getElementById("garden"), ex, { species: "oak" });
  var box = document.getElementById("log"), say = document.getElementById("announce");
  var st = { move: 0, evals: 0, reps: 0 };

  function status() {
    UI.status("NOW RUNNING " + sep + " move <em>" + st.move + "</em> of " + log.max_moves + " " + sep +
      " evaluations <em>" + st.evals + "</em> " + sep + " replicates <em>" + st.reps + "</em>/" + v.B, true);
  }
  function line(tool, text, sys) {
    var p = document.createElement("p");
    if (sys) { p.className = "sys"; p.textContent = text; }
    else {                                    // the log's own text; its leading tool name, if any, in amber
      var t = document.createElement("span"); t.className = "tool"; t.textContent = tool;
      p.append(t, text.indexOf(tool) === 0 ? text.slice(tool.length) : "  " + text);
    }
    box.appendChild(p); box.scrollTop = box.scrollHeight;
  }
  function phase(id) {
    var order = ["ph-search", "ph-null", "ph-verdict"], i = order.indexOf(id);
    order.forEach(function (x, j) {
      var e = document.getElementById(x);
      e.classList.toggle("done", j < i); e.removeAttribute("aria-current");
    });
    document.getElementById(id).setAttribute("aria-current", "step");
    say.textContent = document.getElementById(id).textContent;
  }

  var q = [], T = 0;
  function at(dt, fn) { T += dt; q.push([T, fn]); }

  // 01 the search, in daylight: each call in the log, buds growing one evaluation at a time
  UI.setNight(0);
  g.grow(); g.nulling(true); g.setStep(0);
  line(null, "session " + log.started_utc + " · " + log.agent + " · class " + log.class_name + " (" + log.class_size +
    " members, hash " + log.class_sha256.slice(0, 12) + "…)", true);
  var per = Math.min(110, 8000 / ex.evaluations), k = 0;     // a long search plays faster, never past ~8s
  log.calls.forEach(function (c) {
    var n = (c.state && c.state.n_candidates) || 0;
    if (c.tool === "restart" && c.ok) n = ex.feature_names.length;
    if (n && c.ok) {
      for (var i = 0; i < n; i++) at(per, function () { k++; st.evals = k; g.setStep(k); status(); });
      at(220, (function (c) { return function () { st.move++; status(); line(c.tool, c.text); }; })(c));
    } else {
      at(500, (function (c) { return function () { line(c.tool, c.refused ? "refused: " + c.refused : c.text); }; })(c));
    }
  });

  // 02 the null, falling to night as the replicates run
  at(900, function () { phase("ph-null"); line(null, "replaying the search on " + v.B + " resampled copies of the rows (trigger replay)", true); });
  var reps = 80, dur = 7000;
  for (var r = 1; r <= reps; r++) at(dur / reps, (function (r) { return function () {
    st.reps = Math.round(v.B * r / reps); status(); UI.setNight(r / reps);
  }; })(r));
  ex.ghosts.forEach(function (gh, i) {
    var t0 = T - dur + 300 + i * 2200;
    q.push([t0, function () { g.ghost(i, "on"); }]);
    q.push([t0 + 1700, function () { g.ghost(i, "fade"); }]);
  });

  // 03 the verdict, at night
  at(700, function () {
    phase("ph-verdict");
    var w = UI.WORD[v.status] || v.status;
    line(null, "verdict: " + w + " · p " + v.p_replay.toFixed(4) + " at alpha " + v.alpha + ", B " + v.B, true);
    UI.status("FINISHED " + sep + ' <span class="v">' + w + "</span> " + sep + " p " + UI.pfmt(v.p_replay) + " " + sep +
      " evaluations " + st.evals + " " + sep + " replicates " + v.B + "/" + v.B, false);
    UI.setNight(1);
    g.verdict(w);
    document.getElementById("see").hidden = false;
    document.getElementById("skip").hidden = true;
  });

  q.sort(function (a, b) { return a[0] - b[0]; });
  if (UI.reduce) { q.forEach(function (e) { e[1](); }); return; }
  status();
  // ?at=<ms> renders that frame of the timeline at once, without transitions (review, screenshots)
  var atMs = +((location.search.match(/[?&]at=(\d+)/) || [])[1] || 0);
  if (atMs) {
    document.documentElement.classList.add("still");
    q.filter(function (e) { return e[0] <= atMs; }).forEach(function (e) { e[1](); });
    return;
  }
  q.forEach(function (e) { setTimeout(e[1], e[0]); });
});
