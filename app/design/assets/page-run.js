document.addEventListener("DOMContentLoaded", function () {
  var QX = window.QX, s = QX.panel_shape;
  window.QX_UI.lastRun(QX);
  document.getElementById("tiny-desc").textContent = "The bundled synthetic panel: " + s.rows + " rows × " +
    s.assets + " assets × " + s.features + " features, a weak planted edge.";
  document.getElementById("pw-bar").textContent = QX.power.bar.toFixed(3);
  document.getElementById("pw-80").textContent = QX.power.sharpe_for_80pct.toFixed(3);
  document.getElementById("pw-cmd").textContent = QX.power.command;
});
