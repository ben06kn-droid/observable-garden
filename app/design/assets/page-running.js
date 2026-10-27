/* The demo's timeline, scripted from the real log. In the app this is an SSE stream; the order of
   events here is the order the harness produced them. Log lines are the log's own text; lines
   marked "·" are the app's progress notes, not CLI output. */
document.addEventListener("DOMContentLoaded", function () {
  var QX = window.QX, UI = window.QX_UI, v = QX.verdict, log = QX.log, sep = UI.sep();
  var g = QXGarden.render(document.getElementById("garden"), QX, {});
  var box = document.getElementById("log"), say = document.getElementById("announce");
  var st = { move: 0, evals: 0, reps: 0 };

  document.getElementById("ex1d").textContent = QX.panel_shape.rows + " rows × " + QX.panel_shape.assets +
    " assets × " + QX.panel_shape.features + " features; class " + log.class_name;

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

  // 01 the search: each call in the log, buds growing one evaluation at a time
  g.grow(); g.nulling(true); g.setStep(0);
  line(null, "session " + log.started_utc + " · " + log.agent + " · class " + log.class_name + " (" + log.class_size +
    " members, hash " + log.class_sha256.slice(0, 12) + "…)", true);
  var k = 0;
  log.calls.forEach(function (c) {
    if (c.tool === "init" || c.tool === "extend_best") {
      var n = c.state.n_candidates;
      for (var i = 0; i < n; i++) at(110, function () { k++; st.evals = k; g.setStep(k); status(); });
      at(250, (function (c) { return function () { st.move++; status(); line(c.tool, c.text); }; })(c));
    } else {
      at(650, (function (c) { return function () { line(c.tool, c.text); }; })(c));
    }
  });

  // 02 the null: the search re-grown on noise
  at(900, function () { phase("ph-null"); line(null, "replaying the search on " + v.B + " resampled copies of the rows (trigger replay)", true); });
  var reps = 60, dur = 7000;
  for (var r = 1; r <= reps; r++) at(dur / reps, (function (r) { return function () { st.reps = Math.round(v.B * r / reps); status(); }; })(r));
  [0, 1, 2].forEach(function (i) {
    var t0 = T - dur + 300 + i * 2200;
    q.push([t0, function () { g.ghost(i, "on"); }]);
    q.push([t0 + 1700, function () { g.ghost(i, "fade"); }]);
  });

  // 03 the verdict
  at(700, function () {
    phase("ph-verdict");
    var w = UI.WORD[v.status] || v.status;
    line(null, "verdict: " + w + " · p " + v.p_replay.toFixed(4) + " at alpha " + v.alpha + ", B " + v.B, true);
    UI.status("FINISHED " + sep + ' <span class="v">' + w + "</span> " + sep + " p " + v.p_replay.toFixed(2) + " " + sep +
      " evaluations " + st.evals + " " + sep + " replicates " + v.B + "/" + v.B, false);
    document.body.dataset.light = "bright";
    g.verdict(w);
    document.getElementById("see").hidden = false;
    document.getElementById("skip").hidden = true;
  });

  q.sort(function (a, b) { return a[0] - b[0]; });
  if (UI.reduce) { q.forEach(function (e) { e[1](); }); return; }
  status();
  // ?at=<ms> renders that frame of the timeline at once, without transitions (review, screenshots)
  var at = +((location.search.match(/[?&]at=(\d+)/) || [])[1] || 0);
  if (at) {
    document.documentElement.classList.add("still");
    q.filter(function (e) { return e[0] <= at; }).forEach(function (e) { e[1](); });
    return;
  }
  q.forEach(function (e) { setTimeout(e[1], e[0]); });
});
