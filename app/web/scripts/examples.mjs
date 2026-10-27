// The demo's examples: which repository files the site serves, under which names, and the B each
// runs at. The restart example declares no stop rule, so every replicate runs to its 60-move budget:
// at B 2000 it takes about 60 s under Pyodide, so the demo runs it at B 500 (about 15 s) and says so.
export const FILES = [
  ["examples/logs/scripted_session.json", "scripted_session.json"],
  ["examples/data/tiny_panel.npz", "tiny_panel.npz"],
  ["examples/class.json", "class.json"],
  ["examples/logs/planted_session.json", "planted_session.json"],
  ["examples/data/tiny_panel_planted.npz", "tiny_panel_planted.npz"],
  ["examples/data/tiny_panel_planted.json", "tiny_panel_planted.json"],
  ["examples/logs/restart_session.json", "restart_session.json"],
];

export const DEMOS = [
  { key: "nothing", title: "Nothing to find", log: "scripted_session.json", panel: "tiny_panel.npz", cls: "class.json", B: 2000,
    about: "a weak edge" },
  { key: "planted", title: "Planted edge", log: "planted_session.json", panel: "tiny_panel_planted.npz", cls: "class.json", B: 2000,
    truth: "tiny_panel_planted.json", about: "a known rule, planted" },
  { key: "restart", title: "A longer search", log: "restart_session.json", panel: "tiny_panel.npz", cls: "class.json", B: 500,
    about: "swaps, flips, restarts" },
];
