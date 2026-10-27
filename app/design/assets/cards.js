/* Cards built from window.QX as DOM nodes (text only, never markup): the certificate from the
   record, the planted truth, and the demo's example picker. */
(function () {
  "use strict";
  function h(tag, cls, text, parent) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function sign(x, d) { return (x > 0 ? "+" : "") + x.toFixed(d); }

  // the paper's one certificate: numbers from its committed read files, never a live run
  function certificate(box, c) {
    box.classList.add("cert");
    h("span", "tag", "From the research record · not a live run", box);
    h("h3", null, "The one certificate: Sancho on " + c.panel + ", " + c.insample.slice(0, 4) + "–" + c.insample.slice(-10, -6), box);
    h("p", "sub", "Sancho's stream (delay 1) under the " + c.statistic + " statistic, " + c.rows.toLocaleString("en") +
      " rows, certified at the 96% level; the class maximum on the same panel was refused (p " + c.class_p.toFixed(4) +
      "). Its lower bound was then graded once on the " + c.holdout.slice(0, 4) + "–" + c.holdout.slice(-10, -6) + " holdout.", box);
    var dl = h("dl", "numbers", null, box);
    [["Weighted Sharpe", c.sharpe.toFixed(3), "in-sample, net"],
     ["p", c.p.toFixed(4), "certified iff p < " + c.p_needed],
     ["L₀.₉₀", sign(c.L90, 3), "weighted lower bound"],
     ["Holdout", sign(c.holdout_sharpe, 3), (c.held ? "HELD · " : "NOT HELD · ") + "90% " + c.holdout_ci]
    ].forEach(function (r) {
      var d = h("div", null, null, dl); h("dt", null, r[0], d);
      var dd = h("dd", null, r[1], d); h("small", null, r[2], dd);
    });
    h("p", "src", "Registered at " + c.registered.slice(0, 12) + " (grading " + c.grading_registered.slice(0, 12) +
      "); NOTE_MAP row " + c.note_map_row + "; " + c.files.join(", "), box);
  }

  // the planted example: the truth beside the verdict
  function truth(box, ex) {
    var t = ex.truth, v = ex.verdict;
    box.classList.add("truth");
    h("p", "label", "The planted truth", box);
    var dl = h("dl", "kv", null, box);
    [["Planted", t.planted_rule.join(" "), "population Sharpe " + t.population_sharpe.toFixed(2) + " (target " +
       t.population_sharpe_target.toFixed(1) + "), net of costs"],
     ["On this panel", t.insample_sharpe.toFixed(3), "the planted rule's in-sample Sharpe; " +
       (t.evaluated ? "the search evaluated it" : "the search never evaluated it")],
     ["Submitted", v.submitted_feature_names.join(" "), "in-sample " + v.submitted_sharpe.toFixed(3)],
     ["How measured", t.population_method, ""]
    ].forEach(function (r) {
      h("dt", null, r[0], dl); var dd = h("dd", null, r[1], dl); if (r[2]) h("small", null, r[2], dd);
    });
  }

  // the demo's example picker: links that keep the page and change ?ex=
  function picker(ul, current) {
    var exs = window.QX.examples, UI = window.QX_UI;
    Object.keys(exs).forEach(function (k) {
      var ex = exs[k], li = h("li", null, null, ul), a = h("a", null, null, li);
      a.href = location.pathname.split("/").pop() + "?ex=" + k;
      if (ex === current) a.setAttribute("aria-current", "true");
      h("b", null, ex.title, a);
      h("span", null, (UI.WORD[ex.verdict.status] || ex.verdict.status) + " · " + ex.evaluations + " evaluations" +
        (ex.stems > 1 ? " · " + ex.stems + " stems" : ""), a);
    });
  }

  window.QX_CARDS = { certificate: certificate, truth: truth, picker: picker };
})();
