/* The garden: a search drawn as a plant, from window.QX (assets/example-data.js).
   Bud = one evaluation. Twig = the candidate a move scored. The kept candidate grows on.
   Height is in-sample Sharpe, so the dashed line is the bar and a bud's height is its score.
   Every twig is an evaluation that happened; nothing is drawn that the log did not score. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var W = 1080, H = 570, GROUND = 500, TOP = 40, SMIN = -3.2, SMAX = 2.3;

  function y(s) { return GROUND - (s - SMIN) / (SMAX - SMIN) * (GROUND - TOP); }
  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  // deterministic jitter, so the hand-drawn wobble is the same on every load
  function jit(i, amp) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return (x - Math.floor(x) - 0.5) * 2 * amp; }
  function f(n) { return n.toFixed(1); }

  function twigPath(ax, ay, bx, by, i) {
    var c1, c2;
    if (by <= ay) {                       // grows up: rise first, then lean to the tip
      c1 = [ax + jit(i, 3), ay + (by - ay) * 0.55];
      c2 = [bx + jit(i + 1, 6) - (bx - ax) * 0.15, by + (ay - by) * 0.18];
    } else {                              // scored below its parent: arches, then droops
      c1 = [ax + (bx - ax) * 0.35, ay - 14 + jit(i, 4)];
      c2 = [bx + jit(i + 1, 5), by - 18];
    }
    return "M" + f(ax) + " " + f(ay) + " C" + f(c1[0]) + " " + f(c1[1]) + " " + f(c2[0]) + " " + f(c2[1]) + " " + f(bx) + " " + f(by);
  }

  function name(names, c) { return (c.sign > 0 ? "+" : "-") + names[c.feature]; }

  // place candidates by score: the best nearest the parent, the rest alternating outwards
  function offsets(cands, spread, lean) {
    var order = cands.map(function (c, i) { return i; }).sort(function (a, b) { return cands[b].sharpe - cands[a].sharpe; });
    var n = cands.length, unit = spread / Math.ceil(n / 2), out = new Array(n);
    order.forEach(function (idx, r) {
      out[idx] = r === 0 ? lean : (r % 2 ? -1 : 1) * Math.ceil(r / 2) * unit + lean * 0.5;
    });
    return out;
  }

  function tree(g, moves, rootX, opt, names, steps) {
    var x = rootX, yy = GROUND, k = 0, nodes = [];
    moves.forEach(function (m, mi) {
      var off = offsets(m.candidates, opt.spread[mi], opt.lean[mi]);
      var keptIdx = m.candidates.findIndex(function (c) {
        return c.feature === m.kept.feature && c.sign === m.kept.sign;
      });
      var nx = x, ny = yy;
      m.candidates.forEach(function (c, ci) {
        var bx = x + off[ci], by = y(c.sharpe), step = ++k;
        var isPath = ci === keptIdx;
        var cls = isPath ? " path" : "";
        var p = el("path", { d: twigPath(x, yy, bx, by, step + opt.seed), class: "twig" + cls, pathLength: 1 }, g);
        var ang = Math.atan2(by - yy, bx - x) * 180 / Math.PI + 90;
        var b = el("ellipse", { cx: f(bx), cy: f(by), rx: isPath ? 3.4 : 2.4, ry: isPath ? 4.8 : 3.4,
          transform: "rotate(" + f(ang) + " " + f(bx) + " " + f(by) + ")", class: "bud" + cls }, g);
        p.dataset.step = b.dataset.step = step;
        if (isPath) { nx = bx; ny = by; }
      });
      if (opt.labels) {
        var left = mi % 2 === 0;           // alternate sides so stacked nodes' labels do not collide
        var t = el("text", { x: f(nx + (left ? -12 : 12)), y: f(ny + (left ? 30 : -10)), class: "kept-label",
          "text-anchor": left ? "end" : "start" }, g);
        t.dataset.step = k;
        t.textContent = name(names, m.kept) + "  ";
        el("tspan", { class: "s" }, t).textContent = m.kept.sharpe.toFixed(3);
      }
      nodes.push({ x: nx, y: ny });
      x = nx; yy = ny;
    });
    return { evaluations: k, nodes: nodes };
  }

  function wobble(x0, x1, yy) {
    var d = "M" + x0 + " " + yy, n = 18, dx = (x1 - x0) / n;
    for (var i = 1; i <= n; i++) d += " L" + f(x0 + dx * i) + " " + f(yy + jit(i + 400, 1.2));
    return d;
  }

  function render(svg, QX, opts) {
    opts = opts || {};
    var names = QX.feature_names, v = QX.verdict, real = QX.trees.real, ghosts = QX.trees.ghosts;
    var barS = v.class_bar;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("role", "img");
    svg.classList.add("garden");
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    var id = svg.id || ("g" + Math.random().toString(36).slice(2));
    var title = el("title", { id: id + "-t" }, svg);
    var desc = el("desc", { id: id + "-d" }, svg);
    svg.setAttribute("aria-labelledby", id + "-t " + id + "-d");
    var gmax = ghosts.map(function (t) { return t[t.length - 1].kept.sharpe; });
    title.textContent = "The example search drawn as a plant; height is in-sample Sharpe.";
    desc.textContent = real.map(function (m, i) {
      return (i ? "Then " : "") + m.move + " evaluated " + m.candidates.length + " candidates and kept " +
        name(names, m.kept) + " at Sharpe " + m.kept.sharpe.toFixed(3) + ".";
    }).join(" ") + " The submitted rule reaches " + real[real.length - 1].kept.sharpe.toFixed(3) +
      "; the bar is " + barS.toFixed(3) + "." +
      (opts.ghosts === false ? "" : " Beside it, " + ghosts.length + " illustrative searches re-grown on noise reach " +
        Math.min.apply(null, gmax).toFixed(3) + " to " + Math.max.apply(null, gmax).toFixed(3) + ".");

    // axis: in-sample Sharpe
    var ax = el("g", { class: "axis", "aria-hidden": "true" }, svg);
    [-3, -2, -1, 0, 1, 2].forEach(function (s) {
      el("line", { x1: 34, x2: 40, y1: f(y(s)), y2: f(y(s)) }, ax);
      el("text", { x: 28, y: f(y(s) + 4), "text-anchor": "end" }, ax).textContent = s;
    });
    el("text", { x: 4, y: TOP - 16 }, ax).textContent = "SHARPE";

    // the bar
    var bar = el("g", { class: "bar", "aria-hidden": "true" }, svg);
    el("line", { x1: 40, x2: W - 10, y1: f(y(barS)), y2: f(y(barS)) }, bar);
    el("text", { x: W - 10, y: f(y(barS) - 8), "text-anchor": "end" }, bar).textContent =
      "THE BAR " + barS.toFixed(3) + " (CLASS TIER)";

    el("path", { d: wobble(40, W - 10, GROUND), class: "ground", "aria-hidden": "true" }, svg);

    var gr = el("g", { class: "real" }, svg);
    var res = tree(gr, real, 300, { spread: [230, 200], lean: [0, 22], labels: opts.labels !== false, seed: 0 }, names);
    el("text", { x: 300, y: GROUND + 46, "text-anchor": "middle", class: "note", "aria-hidden": "true" }, svg)
      .textContent = "THE SEARCH · " + res.evaluations + " EVALUATIONS";

    var ghostEls = [];
    if (opts.ghosts !== false) {
      var roots = [700, 840, 980];
      ghosts.forEach(function (t, i) {
        var gg = el("g", { class: "ghost", "aria-hidden": "true" }, svg);
        tree(gg, t, roots[i], { spread: [70, 62], lean: [0, 10], labels: false, seed: 100 * (i + 1) }, names);
        var top = t[t.length - 1].kept.sharpe;
        el("text", { x: roots[i], y: GROUND + 22, "text-anchor": "middle", class: "ghost-label" }, gg).textContent =
          "noise " + (i + 1) + " · " + top.toFixed(2);
        ghostEls.push(gg);
      });
      el("text", { x: 840, y: GROUND + 46, "text-anchor": "middle", class: "note", "aria-hidden": "true" }, svg)
        .textContent = "RE-GROWN ON NOISE · ILLUSTRATIVE";
    }

    var growable = svg.querySelectorAll(".real [data-step]");
    return {
      total: res.evaluations,
      grow: function () { svg.classList.add("growing"); },
      setStep: function (n) {
        growable.forEach(function (e) { e.classList.toggle("on", +e.dataset.step <= n); });
      },
      nulling: function (on) { svg.classList.toggle("nulling", on); },
      ghost: function (i, state) {               // state: "on" | "fade" | "off"
        var g = ghostEls[i]; if (!g) return;
        g.classList.toggle("on", state !== "off");
        g.classList.toggle("fade", state === "fade");
      },
      verdict: function (status) { svg.dataset.verdict = status; }
    };
  }

  window.QXGarden = { render: render };
})();
