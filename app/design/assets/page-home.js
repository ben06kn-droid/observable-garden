document.addEventListener("DOMContentLoaded", function () {
  var QX = window.QX, UI = window.QX_UI, v = QX.verdict;
  var g = QXGarden.render(document.getElementById("hero-garden"), QX, {});
  g.verdict(UI.WORD[v.status] || v.status);
  UI.lastRun(QX);

  var evals = QX.trees.real.reduce(function (n, m) { return n + m.candidates.length; }, 0);
  document.getElementById("hero-cap").textContent = "The bundled example: " + v.n_moves + " moves, " + evals +
    " evaluations, submitted " + v.submitted_feature_names.join(" ") + " at " + v.submitted_sharpe.toFixed(3) +
    ". " + (UI.WORD[v.status] || v.status) + ", p " + v.p_replay.toFixed(4) + ".";
  document.getElementById("null-p").textContent = "p " + v.p_replay.toFixed(4);
  document.getElementById("null-b").textContent = "B " + v.B;
  document.getElementById("cmd").textContent = QX.command;

  var t = document.getElementById("statuses");
  ["PASS", "FAIL", "INADMISSIBLE", "UNDECIDABLE", "DEGENERATE"].forEach(function (s) {
    var tr = t.insertRow(), th = document.createElement("th");
    th.textContent = s; tr.appendChild(th);
    tr.insertCell().textContent = UI.MEANING[s];
  });
});
