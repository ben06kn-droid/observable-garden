# Sancho's levers (`sancho/config.json`)

Every lever Sancho has is in one file. **The defaults are the registered version-2 values**
(`research/prereg/ml-v2-confirmation.md`, section 1: blocks P, X and V; horizon 5; market-neutral;
always; M2; G3; L grid {1, 3, 10, 30}). The registered results apply to the default only.

The config's SHA-256 (of its canonical JSON) goes into every run's output. A non-default config
prints one line saying so: every configuration tried on the same data is another strategy, and
must be declared as such (counted in the class you price against).

| lever | default | what it is |
|---|---|---|
| `version` | 2 | the model version these levers belong to |
| `information` | `"all"` | the input blocks the base view uses: `"all"` available, or a list from `P` (the 40 registered features), `X` (return structure), `V` (volume), `F` (funding) |
| `horizon` | 5 | rows ahead the target sums over |
| `neutrality` | `"market"` | `market` (cross-sectional) or `group` |
| `regime` | `"always"` | the regime gate (`always`, `vol_high`, `vol_low`, `mkt_up`, `mkt_down`, `disp_high`, `disp_low`) |
| `memories` | `{"roll756": 756, "expand": null}` | M2: training windows averaged (rows; `null` = expanding) |
| `rates` | `[0.3, 0.1, 0.03]` | G3: trading rates averaged |
| `first_scored_row` | 756 | the first refit row, before the embargo `h + 1 + d` is added |
| `refit_every` | 252 | rows between refits |
| `warmup_rows` | 64 | rows dropped from the start of every training set |
| `ridge.grids` | L {1,3,10,30}; Q {0.3,1,3,off}; I, S {1,3,10,off} | penalty grids per ridge block (`1000000.0` = off) |
| `trees.lightgbm` | `"4.7.0"` | the LightGBM version required (the optional extra `sancho`) |
| `trees.rounds` | 50 | boosting rounds |
| `trees.params` | as registered | LightGBM parameters (depth-2 trees, deterministic, one thread) |
