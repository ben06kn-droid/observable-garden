# Terms of every data file the site serves

The site serves no third-party data. Each data file, where it comes from, and its terms:

| file (under `app/web/public/`) | source | terms |
|---|---|---|
| `examples/tiny_panel.npz` | `examples/data/tiny_panel.npz`, synthetic, written by `examples/make_tiny_panel.py` (`quixote.panel.tiny(seed=7)`) | MIT, as the repository |
| `examples/tiny_panel_planted.npz`, `examples/tiny_panel_planted.json` | `examples/data/`, the same panel with a known rule planted by `make_tiny_panel.py --plant`, and its truth file | MIT |
| `examples/scripted_session.json`, `planted_session.json`, `restart_session.json` | `examples/logs/`, logs the harness wrote for the repository's scripted searchers | MIT |
| `examples/class.json` | `examples/class.json` | MIT |
| `examples/overview-tree.json` | derived from `restart_session.json` by `app/web/scripts/make_overview_tree.py` | MIT |
| `examples/MANIFEST.json`, `examples/demos.json` | written by `app/web/scripts/copy_examples.mjs` | MIT |

Every copy is checked byte for byte against its source by `app/web/scripts/check_examples.mjs` in the
build and in CI. Software the site serves (Pyodide, numpy, pandas, python-dateutil, pytz, six, the
fonts) is not data; its licences are in `public/licenses.txt`.

No other data file may be added to the site without a row here first.
