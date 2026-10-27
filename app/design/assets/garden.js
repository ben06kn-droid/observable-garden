/* The garden: a logged search drawn as a tree of one species, from an example in window.QX.
   Bud = one evaluation, drawn at the height of its in-sample Sharpe; the dashed line is the bar.
   A move fans out to every candidate it scored; the kept one grows on; a restart is a new stem.
   The species (oak, baobab, bonsai) decides only what the data does not: the trunk's shape,
   where twigs attach to it, how wide a fan spreads, and the canopy outline around the buds. The
   trunk is the anchor's own edge, so it too is an evaluation; a twig's attachment point on the
   trunk is drawing, its bud's height is data. Ghosts are the certifying null's first replicates,
   drawn as the rule each held after every step, in the same species, pale. */
(function () {
  "use strict";
  var NS = "http://www.w3.org/2000/svg";
  var W = 1080, H = 570, GROUND = 500, TOP = 40;

  var SPECIES = {
    oak:    { trunk: [18, 8], bulge: 0, flare: 10, spread: 1.0, attachRise: 44, canopyCut: 0.45, pad: 18, bump: 30, lean: 0.10 },
    baobab: { trunk: [34, 20], bulge: 14, flare: 6, spread: 0.55, attachTop: true, canopyCut: 0.14, pad: 12, bump: 18, lean: 0.02 },
    bonsai: { trunk: [12, 5], bulge: 0, flare: 3, spread: 0.7, attachRise: 26, canopyCut: 0.5, pad: 12, bump: 16, lean: 0.35, pot: true }
  };

  function el(name, attrs, parent) {
    var e = document.createElementNS(NS, name);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  // seeded jitter: the hand-drawn wobble is the same on every load
  function jit(i, amp) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return (x - Math.floor(x) - 0.5) * 2 * amp; }
  function f(n) { return n.toFixed(1); }

  function scale(ex) {
    var lo = -3.2, hi = 2.3;
    ex.tree.forEach(function (m) { m.candidates.forEach(function (c) { lo = Math.min(lo, c.sharpe - 0.2); hi = Math.max(hi, c.sharpe + 0.45); }); });
    ex.ghosts.forEach(function (g) { g.path.forEach(function (p) { hi = Math.max(hi, p.sharpe + 0.45); }); });
    hi = Math.max(hi, ex.verdict.class_bar + 0.45);
    return { lo: lo, hi: hi, y: function (s) { return GROUND - (s - lo) / (hi - lo) * (GROUND - TOP); } };
  }

  // candidates placed by score: the best nearest the parent, the rest alternating outwards
  function offsets(cands, spread) {
    var order = cands.map(function (c, i) { return i; }).sort(function (a, b) { return cands[b].sharpe - cands[a].sharpe; });
    var n = cands.length, unit = spread / Math.max(1, Math.ceil(n / 2)), out = new Array(n);
    order.forEach(function (idx, r) { out[idx] = r === 0 ? 0 : (r % 2 ? -1 : 1) * Math.ceil(r / 2) * unit; });
    return out;
  }

  function twig(ax, ay, bx, by, i, sp) {
    var c1, c2;
    if (sp.attachTop && by < ay) {           // baobab: angular, up first then out
      c1 = [ax + (bx - ax) * 0.1, ay - (ay - by) * 0.9];
      c2 = [bx - (bx - ax) * 0.2, by + 4];
    } else if (by <= ay) {
      c1 = [ax + jit(i, 3), ay + (by - ay) * 0.55];
      c2 = [bx + jit(i + 1, 6) - (bx - ax) * 0.15, by + (ay - by) * 0.18];
    } else {                                  // scored below its parent: arches, then droops
      c1 = [ax + (bx - ax) * 0.35, ay - 14 + jit(i, 4)];
      c2 = [bx + jit(i + 1, 5), by - 18];
    }
    return "M" + f(ax) + " " + f(ay) + " C" + f(c1[0]) + " " + f(c1[1]) + " " + f(c2[0]) + " " + f(c2[1]) + " " + f(bx) + " " + f(by);
  }

  function centre(x0, x1, y1, sp, t) {
    return x0 + (x1 - x0) * t * t + sp.lean * 40 * Math.sin(Math.PI * t) * (sp.pot ? Math.sin(2 * Math.PI * t) : 1);
  }

  // a tapered trunk around a gently curved centreline from (x0, base) to (x1, y1)
  function trunk(x0, base, x1, y1, sp, k) {
    var w0 = sp.trunk[0] * k, w1 = sp.trunk[1] * k, n = 10, L = [], R = [], i;
    for (i = 0; i <= n; i++) {
      var t = i / n, y = base + (y1 - base) * t, x = centre(x0, x1, y1, sp, t);
      var w = w0 + (w1 - w0) * t + sp.bulge * k * Math.sin(Math.PI * Math.min(1, t * 1.4)) + sp.flare * k * Math.pow(1 - t, 6);
      L.push([x - w / 2 + jit(i + k * 7, 0.8), y]); R.push([x + w / 2 + jit(i + 31 + k * 7, 0.8), y]);
    }
    var d = "M" + f(L[0][0]) + " " + f(L[0][1]);
    for (i = 1; i <= n; i++) d += " L" + f(L[i][0]) + " " + f(L[i][1]);
    d += " Q" + f((L[n][0] + R[n][0]) / 2) + " " + f(y1 - w1 * 0.5) + " " + f(R[n][0]) + " " + f(R[n][1]);
    for (i = n - 1; i >= 0; i--) d += " L" + f(R[i][0]) + " " + f(R[i][1]);
    return { d: d, at: function (y) {             // centreline x at height y (for attachments)
      return centre(x0, x1, y1, sp, Math.max(0, Math.min(1, (base - y) / Math.max(1, base - y1))));
    } };
  }

  function hull(pts) {
    pts = pts.slice().sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    if (pts.length < 3) return pts;
    function cross(o, a, b) { return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]); }
    var lo = [], up = [];
    pts.forEach(function (p) { while (lo.length >= 2 && cross(lo[lo.length - 2], lo[lo.length - 1], p) <= 0) lo.pop(); lo.push(p); });
    pts.slice().reverse().forEach(function (p) { while (up.length >= 2 && cross(up[up.length - 2], up[up.length - 1], p) <= 0) up.pop(); up.push(p); });
    return lo.slice(0, -1).concat(up.slice(0, -1));
  }

  // a cartoon canopy: the buds' hull, padded, its edges drawn as outward bumps
  function canopy(pts, pad, bump, seed) {
    if (!pts.length) return null;
    var h = hull(pts), cx = 0, cy = 0;
    pts.forEach(function (p) { cx += p[0]; cy += p[1]; }); cx /= pts.length; cy /= pts.length;
    if (h.length < 3) {                         // one or two buds: a small round crown
      var r = pad + 6;
      h = []; for (var a = 0; a < 6; a++) h.push([cx + r * Math.cos(a * Math.PI / 3), cy + r * 0.8 * Math.sin(a * Math.PI / 3)]);
    } else {
      h = h.map(function (p) { var dx = p[0] - cx, dy = p[1] - cy, n = Math.hypot(dx, dy) || 1; return [p[0] + dx / n * pad, p[1] + dy / n * pad]; });
    }
    var d = "M" + f(h[0][0]) + " " + f(h[0][1]), k = seed;
    for (var i = 0; i < h.length; i++) {
      var p = h[i], q = h[(i + 1) % h.length], len = Math.hypot(q[0] - p[0], q[1] - p[1]) || 1;
      var segs = Math.max(1, Math.round(len / bump));
      var nx = (q[1] - p[1]) / len, ny = -(q[0] - p[0]) / len;
      var mxc = (p[0] + q[0]) / 2 - cx, myc = (p[1] + q[1]) / 2 - cy;
      if (nx * mxc + ny * myc < 0) { nx = -nx; ny = -ny; }        // bumps always face outward
      for (var s = 1; s <= segs; s++) {
        var tm = (s - 0.5) / segs, t1 = s / segs, out = (len / segs) * 0.42 + jit(k++, 2);
        d += " Q" + f(p[0] + (q[0] - p[0]) * tm + nx * out) + " " + f(p[1] + (q[1] - p[1]) * tm + ny * out) +
             " " + f(p[0] + (q[0] - p[0]) * t1) + " " + f(p[1] + (q[1] - p[1]) * t1);
      }
    }
    return d + " Z";
  }

  function wobble(x0, x1, yy) {
    var d = "M" + x0 + " " + yy, n = 18, dx = (x1 - x0) / n;
    for (var i = 1; i <= n; i++) d += " L" + f(x0 + dx * i) + " " + f(yy + jit(i + 400, 1.2));
    return d;
  }

  function pot(g, x, k) {
    var w = 46 * k, h = 20 * k;
    el("path", { d: "M" + f(x - w / 2 - 4 * k) + " " + f(GROUND - h) + " L" + f(x + w / 2 + 4 * k) + " " + f(GROUND - h) +
      " M" + f(x - w / 2) + " " + f(GROUND - h) + " L" + f(x - w / 2 + 7 * k) + " " + f(GROUND) + " L" + f(x + w / 2 - 7 * k) +
      " " + f(GROUND) + " L" + f(x + w / 2) + " " + f(GROUND - h), class: "pot" }, g);
    return GROUND - h;
  }

  /* Lay out one search: where each bud goes and where its twig attaches. Each stem's trunk is its
     anchor's edge from the ground and then every kept edge for as long as the kept moves climb, so
     every trunk segment is an evaluation and later twigs attach at their real parent node. */
  function layout(moves, opt) {
    var sp = SPECIES[opt.species], Y = opt.Y, stems = {}, step = 0, laid = [];
    var nStems = 1 + Math.max.apply(null, moves.map(function (m) { return m.stem; }));
    var per = (opt.x1 - opt.x0) / nStems;
    var k = (opt.k || 1) * Math.min(1, per / 170);                 // narrow stems get slimmer trunks
    var fan = Math.min(per * 0.5, 230 * (opt.k || 1)) * sp.spread;
    moves.forEach(function (m, mi) {
      var st = stems[m.stem];
      if (!st) {
        var rx = opt.x0 + per * (m.stem + 0.5);
        st = stems[m.stem] = { root: rx, node: null, buds: [], chain: [], climbing: true, last: 0, k: k,
                               base: sp.pot && opt.under ? pot(opt.under, rx, k) : GROUND };
      }
      var off = offsets(m.candidates, m.from_ground ? fan : fan * 0.85);
      var ox = m.from_ground ? st.root : st.node[0], oy = m.from_ground ? st.base : st.node[1];
      var lean = m.from_ground ? 0 : (st.root < W / 2 ? 1 : -1) * 6;
      var tips = m.candidates.map(function (c, ci) { return [ox + off[ci] + lean, Y(c.sharpe)]; });
      var tr = null;
      if (m.from_ground) {
        tr = trunk(st.root, st.base, tips[m.chosen][0], tips[m.chosen][1], sp, k);
        st.chain = [tips[m.chosen]];
      }
      var extends_ = !m.from_ground && m.kept && st.climbing && tips[m.chosen][1] < st.node[1] - 2;
      if (!m.from_ground && m.kept && !extends_) st.climbing = false;
      m.candidates.forEach(function (c, ci) {
        step++;
        var tip = tips[ci], isChosen = ci === m.chosen, a = [ox, oy], seg = null;
        if (m.from_ground) {
          if (isChosen) { a = null; seg = tr; }             // the trunk is this edge
          else {
            var top = tips[m.chosen];
            var ay = sp.attachTop ? top[1] + 8 + jit(step, 4)
                                  : Math.max(top[1] + 10, Math.min(st.base - 8, tip[1] + sp.attachRise));
            a = [tr.at(ay), ay];
          }
        } else if (isChosen && extends_) {
          var w = Math.max(3, sp.trunk[1] * k * Math.pow(0.78, st.chain.length));
          seg = { d: limb(ox, oy, tip[0], tip[1], w * 1.25, w) };
          a = null;
        }
        laid.push({ stem: m.stem, step: step, tip: tip, from: a, kept: isChosen && m.kept,
                    sharpe: c.sharpe, rule: c.rule, trunk: seg });
        st.buds.push(tip);
        st.last = step;
      });
      if (extends_) st.chain.push(tips[m.chosen]);
      if (m.kept) st.node = tips[m.chosen];
    });
    return { laid: laid, stems: stems, steps: step };
  }

  // a tapered limb from (ax, ay) to (bx, by), width wa to wb, slightly bowed
  function limb(ax, ay, bx, by, wa, wb) {
    var dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy) || 1, nx = -dy / L, ny = dx / L, bow = L * 0.06;
    var mx = (ax + bx) / 2 + nx * bow, my = (ay + by) / 2 + ny * bow;
    return "M" + f(ax + nx * wa / 2) + " " + f(ay + ny * wa / 2) +
      " Q" + f(mx + nx * (wa + wb) / 4) + " " + f(my + ny * (wa + wb) / 4) + " " + f(bx + nx * wb / 2) + " " + f(by + ny * wb / 2) +
      " L" + f(bx - nx * wb / 2) + " " + f(by - ny * wb / 2) +
      " Q" + f(mx - nx * (wa + wb) / 4) + " " + f(my - ny * (wa + wb) / 4) + " " + f(ax - nx * wa / 2) + " " + f(ay - ny * wa / 2) + " Z";
  }

  function drawLaid(res, lay, sp, opt) {
    Object.keys(res.stems).forEach(function (key) {
      var st = res.stems[key];
      var top = Math.min.apply(null, st.buds.map(function (p) { return p[1]; }));
      var crown = st.chain[st.chain.length - 1];
      var cut = Math.min(crown[1], top) + sp.canopyCut * (st.base - Math.min(crown[1], top));
      var pts = opt.allBuds ? st.buds : st.buds.filter(function (p) { return p[1] <= cut; });
      var d = canopy(pts.length ? pts : [crown], sp.pad * opt.k * Math.max(0.5, st.k), sp.bump * opt.k * Math.max(0.5, st.k),
                     +key * 97 + (opt.seed || 0));
      if (d) { var c = el("path", { d: d, class: "canopy" }, lay.canopy); c.dataset.step = st.last; }
    });
    res.laid.forEach(function (b) {
      var cls = opt.onPath && opt.onPath[b.step] ? " path" : "";
      var e;
      if (b.trunk) e = el("path", { d: b.trunk.d, class: "trunk" + cls }, lay.trunk);
      else e = el("path", { d: twig(b.from[0], b.from[1], b.tip[0], b.tip[1], b.step + (opt.seed || 0), sp),
                            class: "twig" + cls + (b.tip[1] > b.from[1] + 4 ? " down" : ""), pathLength: 1 }, lay.twig);
      e.dataset.step = b.step;
      var ang = b.from ? Math.atan2(b.tip[1] - b.from[1], b.tip[0] - b.from[0]) * 180 / Math.PI + 90 : 0;
      var r = (b.kept ? 1.4 : 1) * opt.bud;
      var bud = el("ellipse", { cx: f(b.tip[0]), cy: f(b.tip[1]), rx: f(r * 2.5), ry: f(r * 3.5),
        transform: "rotate(" + f(ang) + " " + f(b.tip[0]) + " " + f(b.tip[1]) + ")",
        class: "bud" + cls + (b.kept ? " kept" : "") }, lay.bud);
      bud.dataset.step = b.step;
    });
  }

  function layers(parent) {
    return { canopy: el("g", { class: "canopies" }, parent), under: el("g", { class: "pots" }, parent),
             trunk: el("g", {}, parent), twig: el("g", {}, parent), bud: el("g", {}, parent), label: el("g", {}, parent) };
  }
  function pathMoves(path) {                     // a ghost path: one bud per held rule, a new stem from the ground
    var moves = [], prev = -1;
    path.forEach(function (p) {
      moves.push({ stem: p.stem, from_ground: p.stem !== prev, candidates: [p], chosen: 0, kept: true });
      prev = p.stem;
    });
    return moves;
  }

  function render(svg, ex, opts) {
    opts = opts || {};
    var species = opts.species || "oak", sp = SPECIES[species], v = ex.verdict, sc = scale(ex);
    var word = (window.QX_UI && QX_UI.WORD[v.status]) || v.status;
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("role", "img");
    svg.classList.add("garden");
    svg.dataset.species = species;
    while (svg.firstChild) svg.removeChild(svg.firstChild);

    var id = svg.id || ("g" + Math.random().toString(36).slice(2));
    var title = el("title", { id: id + "-t" }, svg), desc = el("desc", { id: id + "-d" }, svg);
    svg.setAttribute("aria-labelledby", id + "-t " + id + "-d");
    var gtops = ex.ghosts.map(function (g) { return g.score; });
    title.textContent = "The search drawn as " + (species === "oak" ? "an oak" : "a " + species) + "; height is in-sample Sharpe.";
    desc.textContent = ex.tree.length + " moves on " + ex.stems + " stem" + (ex.stems > 1 ? "s" : "") + ", " +
      ex.evaluations + " evaluations; the submitted rule " + v.submitted_feature_names.join(" ") + " at " +
      v.submitted_sharpe.toFixed(3) + "; the bar is " + v.class_bar.toFixed(3) + "; verdict " + word + "." +
      (opts.ghosts === false ? "" : " Beside it, the null's first " + ex.ghosts.length + " replicates reach " +
        Math.min.apply(null, gtops).toFixed(3) + " to " + Math.max.apply(null, gtops).toFixed(3) + ".");

    var ax = el("g", { class: "axis", "aria-hidden": "true" }, svg);
    for (var s = Math.ceil(sc.lo); s <= Math.floor(sc.hi); s++) {
      el("line", { x1: 34, x2: 40, y1: f(sc.y(s)), y2: f(sc.y(s)) }, ax);
      el("text", { x: 28, y: f(sc.y(s) + 5), "text-anchor": "end" }, ax).textContent = s;
    }
    el("text", { x: 4, y: TOP - 16 }, ax).textContent = "SHARPE";
    var bar = el("g", { class: "bar", "aria-hidden": "true" }, svg);
    el("line", { x1: 40, x2: W - 10, y1: f(sc.y(v.class_bar)), y2: f(sc.y(v.class_bar)) }, bar);
    el("text", { x: W - 10, y: f(sc.y(v.class_bar) - 8), "text-anchor": "end" }, bar).textContent =
      "THE BAR " + v.class_bar.toFixed(3) + " (CLASS TIER)";
    el("path", { d: wobble(40, W - 10, GROUND), class: "ground", "aria-hidden": "true" }, svg);

    var ghostsOn = opts.ghosts !== false, x1 = !ghostsOn ? W - 30 : ex.stems > 3 ? 760 : 640;   // a many-stem search gets more room
    var gr = el("g", { class: "real" }, svg), L = layers(gr);
    var res = layout(ex.tree, { species: species, Y: sc.y, x0: 60, x1: x1, under: L.under });

    // the submitted bud: the first kept evaluation of the submitted rule at its score, and the
    // kept chain on its stem up to it
    var key = function (r) { return r.split(" ").sort().join(" "); };
    var subRule = v.submitted_feature_names.join(" "), sub = null, onPath = {};
    res.laid.forEach(function (b) {
      if (!sub && b.kept && Math.abs(b.sharpe - v.submitted_sharpe) < 1e-12 && key(b.rule) === key(subRule)) sub = b;
    });
    if (sub) res.laid.forEach(function (b) { if (b.stem === sub.stem && b.kept && b.step <= sub.step) onPath[b.step] = true; });
    drawLaid(res, L, sp, { k: 1, bud: 1, onPath: onPath });
    if (sub) {
      var tx = el("text", { x: f(sub.tip[0] + 12), y: f(sub.tip[1] - 14), class: "kept-label" }, L.label);
      tx.dataset.step = sub.step;
      tx.textContent = subRule + "  ";
      el("tspan", { class: "s" }, tx).textContent = v.submitted_sharpe.toFixed(3);
    }
    el("text", { x: (60 + x1) / 2, y: GROUND + 46, "text-anchor": "middle", class: "note", "aria-hidden": "true" }, svg)
      .textContent = "THE SEARCH · " + ex.evaluations + " EVALUATIONS" + (ex.stems > 1 ? " · " + ex.stems + " STEMS" : "");

    var ghostEls = [];
    if (ghostsOn) {
      var gx0 = x1 + 40, gw = (W - 20 - gx0) / ex.ghosts.length;
      ex.ghosts.forEach(function (gh, i) {
        var gg = el("g", { class: "ghost", "aria-hidden": "true" }, svg), GL = layers(gg);
        var r = layout(pathMoves(gh.path), { species: species, Y: sc.y, x0: gx0 + i * gw, x1: gx0 + (i + 1) * gw, k: 0.75, under: GL.under });
        drawLaid(r, GL, sp, { k: 1.1, bud: 0.7, allBuds: true, seed: 500 + i * 31 });
        el("text", { x: f(gx0 + (i + 0.5) * gw), y: GROUND + 22, "text-anchor": "middle", class: "ghost-label" }, gg)
          .textContent = gh.score.toFixed(2);
        ghostEls.push(gg);
      });
      el("text", { x: (gx0 + W - 20) / 2, y: GROUND + 46, "text-anchor": "middle", class: "note", "aria-hidden": "true" }, svg)
        .textContent = "THE NULL · FIRST " + ex.ghosts.length + " OF " + v.B + " REPLICATES";
    }

    var growable = svg.querySelectorAll(".real [data-step]");
    return {
      total: res.steps,
      grow: function () { svg.classList.add("growing"); },
      setStep: function (n) { growable.forEach(function (e) { e.classList.toggle("on", +e.dataset.step <= n); }); },
      nulling: function (on) { svg.classList.toggle("nulling", on); },
      ghost: function (i, state) {
        var g = ghostEls[i]; if (!g) return;
        g.classList.toggle("on", state !== "off");
        g.classList.toggle("fade", state === "fade");
      },
      verdict: function (status) { svg.dataset.verdict = status; }
    };
  }

  /* A specimen: one species drawn large from a short path [{stem, rule, sharpe}], for the
     type-and-species page. */
  function specimen(svg, path, species, label) {
    var vals = path.map(function (p) { return p.sharpe; });
    var lo = Math.min(-0.5, Math.min.apply(null, vals) - 0.4), hi = Math.max(2, Math.max.apply(null, vals) + 0.6);
    var Y = function (s) { return GROUND - (s - lo) / (hi - lo) * (GROUND - TOP); };
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    svg.setAttribute("role", "img");
    svg.classList.add("garden");
    svg.dataset.species = species;
    el("title", {}, svg).textContent = label;
    el("path", { d: wobble(40, W - 10, GROUND), class: "ground" }, svg);
    var gr = el("g", { class: "real" }, svg), L = layers(gr);
    var r = layout(pathMoves(path), { species: species, Y: Y, x0: 200, x1: 880, k: 2.2, under: L.under });
    drawLaid(r, L, SPECIES[species], { k: 2, bud: 2.2, allBuds: true });
  }

  window.QXGarden = { render: render, specimen: specimen, SPECIES: Object.keys(SPECIES) };
})();
