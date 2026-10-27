document.addEventListener("DOMContentLoaded", function () {
  var QX = window.QX, UI = window.QX_UI, ex = QX.examples.nothing, v = ex.verdict;
  var word = UI.WORD[v.status] || v.status;
  var g = QXGarden.render(document.getElementById("hero-garden"), ex, { species: "oak" });
  g.verdict(word);
  UI.lastRun(ex);

  document.getElementById("hero-cap").textContent = "The demo's first example, as an oak: " + v.n_moves + " moves, " +
    ex.evaluations + " evaluations, submitted " + v.submitted_feature_names.join(" ") + " at " +
    v.submitted_sharpe.toFixed(3) + ". " + word + ", p " + v.p_replay.toFixed(4) + ".";
  document.getElementById("null-p").textContent = "p " + v.p_replay.toFixed(4);
  document.getElementById("null-b").textContent = "B " + v.B;
  document.getElementById("cmd").textContent = ex.command;
  QX_CARDS.certificate(document.getElementById("cert"), QX.certificate);

  var t = document.getElementById("statuses");
  ["PASS", "FAIL", "INADMISSIBLE", "UNDECIDABLE", "DEGENERATE"].forEach(function (s) {
    var tr = t.insertRow(), th = document.createElement("th");
    th.textContent = s; tr.appendChild(th);
    tr.insertCell().textContent = UI.MEANING[s];
  });
});
