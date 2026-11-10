# Sablier sample world: an exploratory Quixote session (2026-11-10)

**EXPLORATORY and UNREGISTERED.** Written before any run on this world. Nothing here is a registered
result, enters the record of any registered panel, or is reported to Sablier until the author says.

## The world and the panel
- **The world:** Sablier's sample, 504 trading days of the 12 Ken French industry portfolios, generated
  jointly, prices indexed to 100, closes only, drift removed (checked: exact sample demeaning of log
  returns, every series ends at 100). External data under Sablier's terms: personal research, nothing
  redistributed. SHA-256 `0d06a26cc8d86b500dc5f09fcdc772c1e00e41e7dce17287532257eac52e3e76`; kept in
  Overfitting-Gate's gitignored `data/sablier/sample_2026-11-10/`, never committed to either repo.
- **The panel** (`research/experiments/sablier_sample_panel.py`): simple returns; the equal-weighted market;
  phase 1's French feature set (`prereg/french-panel.md` d: the 20 base signals of `etf-features.md`,
  each as a z-score and an average-tie rank, 40 features, computed causally from returns only; none needs
  volume, none dropped); the first 253 rows dropped as the French panel's warm-up; masked names I00-I11;
  periods_per_year 252, delay 1, cost 5 bps one-way, borrow 50 bps a year (French panel e).
  **250 rows x 12 assets x 40 features; 248 earning rows (0.98 years).** Panel file (gitignored, beside the
  world): SHA-256 `417be33ab9437e0743c07d6715adce941c408a8ac5c786131369b6483590424f`.
- **The class:** phase 1's declared class for 40 features, `{"kind": "subsets", "features": "all",
  "max_size": 3, "signed": true}`: signed equal-weight combinations of up to 3 features, **82,240
  members** (`research/experiments/sablier_sample_class.json`).

## What is expected, and what would follow
- **The world is a null by construction:** drift removed, nothing planted. With 248 rows the class's bar
  is high: `quixote power` gives 4.887 to certify and 5.763 for 80% power (alpha 0.05, independent
  members, the worst case).
- **The expected verdict is a refusal:** not certified (FAIL, or UNDECIDABLE/INADMISSIBLE on the
  harness's own grounds).
- **A certificate would mean the generator leaks predictability or the gate misbehaves.** It would be
  investigated before anything else: the leak first (a plant-free world must not certify), then the
  harness, and nothing would be reported to Sablier until both were understood.

## The runs
- **First, a smoke with phase 1's scripted searcher** (`examples.scripted_searcher:Agent`, no model): the
  full path, run then audit, must produce a verdict. The path, not a result.
- **Then one agent session**, run by the author from a shell holding the credential, wrapped in
  Overfitting-Gate's `checks/laptop_budget.py` (a laptop exception, recorded there: one exploratory agent
  session, network-bound):
  - **agent:** `examples.llm_agent:Agent` (the Anthropic SDK; reads `ANTHROPIC_API_KEY`);
  - **model:** `claude-sonnet-5` (the adapter's default, `QUIXOTE_MODEL` unset);
  - **budget:** `--max-moves 60`, 512 output tokens a turn (the adapter's), one session;
  - **seed:** 20261110 for the run and for the audit; audit B 2,000 (the default); alpha 0.05.
- **Limits stated now:** the adapter has no served-model check (that lives in
  `experiments/agent_backend.py`, which the agent-cell runners use) and the session log does not record
  which model answered; the verdict is read from the audit, the stated forecast from the `predict` move.

## Results
_To be filled after the session: the verdict, the log's moves, the agent's stated forecast._
