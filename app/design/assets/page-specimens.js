document.addEventListener("DOMContentLoaded", function () {
  var QX = window.QX, UI = window.QX_UI;
  function h(tag, cls, text, parent) {
    var e = document.createElement(tag); if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text; if (parent) parent.appendChild(e); return e;
  }

  // A: the shortlist, each set heavy; the chosen one first and marked
  var FACES = [
    ["Bricolage Grotesque", "800", "chosen: heavy and warm, with a hand-cut edge that suits the sketched trees; optical sizes keep it tight at display size"],
    ["Archivo Black", "400", "one weight only; blunt and very legible, but colder"],
    ["Space Grotesk", "700", "the lightest of the five; techy, reads as a product UI"],
    ["Syne", "800", "very wide at 800; striking, but long headings wrap early"],
    ["Unbounded", "800", "rounded and wide; closest to a cyberpunk display face, which the brief rules out"]
  ];
  var box = document.getElementById("faces");
  FACES.forEach(function (f, i) {
    var row = h("div", "face", undefined, box);
    if (i === 0) row.setAttribute("aria-current", "true");
    var name = h("div", "name", undefined, row); h("b", null, f[0] + " " + f[1], name); name.append(f[2]);
    var spec = h("div", null, undefined, row), font = "'" + f[0] + "', sans-serif";
    var lab = h("p", "lab", undefined, spec); lab.style.fontFamily = font; lab.style.fontWeight = f[1];
    h("span", null, "01", lab); lab.append("The search");
    var big = h("p", "big", "A backtest is the best of many attempts.", spec); big.style.fontFamily = font; big.style.fontWeight = f[1];
    var w = h("p", "word", "PASS  FAIL  INADMISSIBLE", spec); w.style.fontFamily = font; w.style.fontWeight = f[1];
  });

  // B: one species per mode, each drawn from a real search's held rules
  function held_unused(ex) {               // the rule held after each kept move, as a ghost path is drawn
    var out = [];
    ex.tree.forEach(function (m) { if (m.kept) out.push({ stem: m.stem, rule: m.candidates[m.chosen].rule, sharpe: m.candidates[m.chosen].sharpe }); });
    return out;
  }
  var nothing = QX.examples.nothing, restart = QX.examples.restart, c = QX.certificate;
  QXGarden.render(document.getElementById("sp-oak"), nothing, { species: "oak", ghosts: false });
  document.getElementById("cap-oak").textContent = "Oak · the demo. The first demo example, every candidate (" +
    nothing.evaluations + " evaluations).";
  // the restart example's first stem alone, so one baobab fills the frame
  var stem0 = Object.assign({}, restart, { tree: restart.tree.filter(function (m) { return m.stem === 0; }), stems: 1 });
  stem0.evaluations = stem0.tree.reduce(function (n, m) { return n + m.candidates.length; }, 0);
  QXGarden.render(document.getElementById("sp-baobab"), stem0, { species: "baobab", ghosts: false });
  document.getElementById("cap-baobab").textContent = "Baobab · a visitor's agent. The restart example's first stem, every " +
    "candidate (" + stem0.evaluations + " evaluations); no visitor run exists yet.";
  QXGarden.specimen(document.getElementById("sp-bonsai"), [{ stem: 0, rule: "Sancho", sharpe: c.sharpe }], "bonsai", "A bonsai");
  document.getElementById("cap-bonsai").textContent = "Bonsai · Sancho. One declared candidate is one evaluation: a single bud, at " +
    "the certificate's weighted Sharpe " + c.sharpe.toFixed(3) + ", in its pot.";

  // C: the light, previewed and checked
  var slider = document.getElementById("n"), nv = document.getElementById("n-v");
  slider.addEventListener("input", function () { UI.setNight(+slider.value); nv.textContent = (+slider.value).toFixed(2); });

  var keys = Object.keys(UI.TOKENS).filter(function (k) { return UI.TOKENS[k][2]; });
  var pairs = keys.map(function (k) { return [k, "bg", UI.TOKENS[k][2]]; })
    .concat([["ink", "surface", 4.5], ["muted", "surface", 4.5], ["faint", "surface", 4.5], ["amber-text", "surface", 4.5],
             ["on-amber", "amber", 4.5]]);
  var t = document.getElementById("sweep"), hr = t.insertRow();
  ["colour", "on", "needs", "lowest over 0..1", "n=0", "0.25", "0.5", "0.75", "1"].forEach(function (x) { var th = document.createElement("th"); th.textContent = x; hr.appendChild(th); });
  var allOk = true;
  pairs.forEach(function (pr) {
    var lo = Infinity, at = [];
    for (var i = 0; i <= 100; i++) {
      var p = UI.palette(i / 100), r = UI.contrast(p[pr[0]], p[pr[1]]);
      lo = Math.min(lo, r);
      if (i % 25 === 0) at.push([r, p[pr[0]]]);
    }
    var ok = lo >= pr[2]; allOk = allOk && ok;
    var tr = t.insertRow();
    tr.insertCell().textContent = pr[0]; tr.insertCell().textContent = pr[1]; tr.insertCell().textContent = pr[2] + ":1";
    var c0 = tr.insertCell(); c0.textContent = lo.toFixed(2) + (ok ? "  ok" : "  BELOW"); c0.className = ok ? "ok" : "";
    at.forEach(function (a) {
      var td = tr.insertCell(), sw = h("span", "swatch", undefined, td); sw.style.background = a[1];
      td.append(a[0].toFixed(2));
    });
  });
  t.dataset.allOk = allOk;
  var cap = t.createCaption(); cap.className = "vh"; cap.textContent = allOk ? "Every pair passes at every state." : "Some pairs fall below.";
});
