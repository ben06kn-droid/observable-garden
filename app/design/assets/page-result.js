/* The verdict pages (demo-result.html, result.html). The four numbers count up once when the
   verdict lands, the light comes up, then nothing moves. */
document.addEventListener("DOMContentLoaded", function () {
  var QX = window.QX, UI = window.QX_UI, v = QX.verdict, log = QX.log;
  var word = UI.WORD[v.status] || v.status;
  function $(id) { return document.getElementById(id); }
  function short(h) { return h.slice(0, 12) + "…"; }

  UI.lastRun(QX);
  $("verdict").dataset.status = word;
  $("v-word").textContent = word;
  $("v-meaning").textContent = UI.MEANING[word] || v.meaning_cli;
  $("v-submitted").textContent = "submitted " + v.submitted_feature_names.join(" ") + " · after " + v.n_moves +
    " moves · replay tier at α " + v.alpha + ", B " + v.B;
  $("n-bar-note").textContent = "class tier: critical Sharpe over all " + v.class_size.toLocaleString("en") + " members";
  $("n-p-note").textContent = "replay tier, the verdict · α " + v.alpha;
  var nums = { "n-sharpe": v.submitted_sharpe, "n-bar": v.class_bar, "n-p": v.p_replay, "n-l90": v.L90 };

  var ol = $("reasons");
  v.reasons.forEach(function (r) {
    var li = document.createElement("li"), p = document.createElement("p"), b = document.createElement("button");
    p.textContent = r; b.type = "button"; b.textContent = "More"; b.setAttribute("aria-expanded", "false");
    li.append(p, b); ol.appendChild(li);
  });
  $("cmd").textContent = QX.command;

  var g = QXGarden.render($("garden"), QX, {});
  var evals = QX.trees.real.reduce(function (n, m) { return n + m.candidates.length; }, 0);
  $("g-cap").textContent = "Frozen at the verdict. " + evals + " evaluations in " + v.n_moves +
    " moves; the submitted rule at " + v.submitted_sharpe.toFixed(3) + ". The pale trees are the same scripted policy " +
    "re-run on three resampled, demeaned copies of the rows: an illustration of the null, not its " + v.B + " certifying replicates.";

  // [label, value, note]; built as text nodes, since in phase 2 file names come from visitors
  var rec = [
    ["Class", log.class_name, log.class_size + " members · " + log.class_file],
    ["Class hash", log.class_sha256, "sha256, taken before the first evaluation"],
    ["Panel", log.panel_file, QX.panel_shape.rows + " rows × " + QX.panel_shape.assets + " assets × " +
      QX.panel_shape.features + " features"],
    ["Panel hash", log.panel_sha256, "sha256"],
    ["Seeds", "search " + log.seed + " · audit 0", "stationary bootstrap, block length " + QX.block_length],
    ["Model", log.agent, "scripted; no language model, no prompt"],
    ["Budget", log.max_moves + " moves · " + log.n_moves + " used · " + evals + " evaluations", "B " + v.B + " · α " + v.alpha],
    ["Run", log.started_utc, log.format],
    ["Code", "—", "the commit the server ran; recorded per run from phase 2"]
  ];
  if (document.body.dataset.mode === "permalink") {
    rec.splice(6, 0, ["Prompt", "—", "the agent prompt's sha256, for a model run"],
                     ["API key", "not stored", "held in memory for the run only; not part of the record"]);
  }
  var dl = $("record");
  rec.forEach(function (r) {
    var dt = document.createElement("dt"), dd = document.createElement("dd"), sm = document.createElement("small");
    dt.textContent = r[0]; dd.textContent = r[1]; sm.textContent = r[2]; dd.appendChild(sm); dl.append(dt, dd);
  });
  var blob = new Blob([JSON.stringify(log, null, 1)], { type: "application/json" });
  $("dl-log").href = URL.createObjectURL(blob);

  // the verdict lands
  function land() {
    document.body.dataset.light = "bright";
    g.verdict(word);
    Object.keys(nums).forEach(function (id) {
      var n = $(id); n.dataset.count = nums[id]; UI.countUp(n);
    });
  }
  if (UI.reduce) land(); else setTimeout(land, 350);
});
