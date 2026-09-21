# 7.4 ADR testbed — features, class, returns, costs, null and readouts

**The feature-list commit.** Committed before any bar is opened, priced, plotted
or summarised. The feature-building code refuses to run unless this commit is an
ancestor of HEAD; that guard is written with the feature code, not here.

Universe, sessions, home-market boundaries and `TRANSITION` bars are fixed by
`prereg/adr-universe.md` (as amended 2026-09-21: 18 treated names, three
controls). Data are the two manifests under `data/`. The only looks taken so far
are the two recorded in `data/adr_manifest.json`: row counts with first and last
timestamps per file, and regular-session bar counts per name from the timestamp
column alone.

No novelty is claimed for anything here.

## 1. Reference Sharpe

**2.0 annualised, net of costs.** Fixed here before any bar is opened; preflight
(§8) is read at this value.

## 2. Features: K = 22

Eleven base features, each split by the home-market indicator into a home-open
copy and a home-closed copy: 11 × 2 = 22.

| # | base feature | definition at the close of bar *b* |
|---|---|---|
| 1–4 | own return, lags 1, 3, 6, 12 | log(close_b / close_{b−k}); a reference before the session's 09:30 open is replaced by that open, so no lag reaches overnight |
| 5–8 | return relative to benchmark, lags 1, 3, 6, 12 | features 1–4 minus the same quantity for the name's mapped ETF |
| 9 | overnight gap | log(open of the 09:30 bar / last regular-session close of the previous session); constant within the session; **missing on the name's ex-dividend dates** (§5) |
| 10 | distance from session VWAP | log(close_b / VWAP over the session's bars from 09:30 through *b*), VWAP from the vendor's per-bar `vw` weighted by `v` |
| 11 | relative volume | log(v_b / mean of v at the same bar-of-day over the previous 20 sessions); the 20-session warm-up is excluded from scoring |

**Home indicator.** For bar *b* and name *i*: *home-open* if the bar ends at or
before the name's end of continuous trading; *home-closed* if it starts at or
after the end of its last `TRANSITION` bar. In `TRANSITION` bars **both copies
are zero**. Days when the home market is shut are home-closed all session; on
home early closes the boundary moves to the early close. **Controls** take
XAMS's boundary (11:30 ET, 12:30 ET in clock-mismatch weeks) as a pseudo-close,
so every specification is defined on them and every home-close prediction can
fail there.

**Standardisation.** Each of the 22 is z-scored cross-sectionally per bar across
the panel's names that have a bar; a feature with zero cross-sectional variance
in a bar is 0 for all names; a missing value is set to 0 after scoring, which is
the cross-sectional mean.

**Dropped from ROADMAP 7.4's list:** minutes to and from home close. It is almost
constant across names sharing a clock, so it carries little cross-sectional
information, and the indicator already carries the break. ROADMAP's K ≈ 40
becomes 22 here.

## 3. Class

**Signed subsets of size ≤ 2 over K = 22: 968 members** (44 singles + 924
pairs). A specification's score is the signed, equal-weight sum of its members'
standardised features.

**Why the tightest class.** Power is scarce on 1.9 scored years; the bar grows
with class size (√(2 ln N)) and nothing else here buys power back. Arm D's result
is that the gate prices a search best when the declared class matches what the
search can reach, so the declared class is the smallest one that holds every
specification the agent is allowed to try.

## 4. Returns

- **Signal at the close of bar *b*, position held over bar *b*+1.**
- **Weights:** the score demeaned across the treated names that can trade in
  bar *b*+1, scaled to gross exposure 1. **Dollar-neutral.**
- **Traded bars:** 09:35–15:55 ET, 76 per full session; first and last bars
  dropped. The first traded bar's return is **close over its own open**; later
  bars are close over the previous close.
- **Flat overnight.** Every position opens at or after 09:35 and is closed by
  15:55. No overnight P&L, so no dividend drop appears in any return; the
  overnight gap is a feature only.
- **Missing bars** (adopted 2026-09-21): a regular-session bar with no trade
  carries the price forward with zero return; the name's position is held and
  not re-traded in that bar. Sized by the recorded look: 0–13 of 38,742 per name,
  LOGI 266 (0.69%), no empty session.
- **`TRANSITION` bars:** the name's weight is frozen. It is not traded, and the
  bar's return accrues to the position held. The other names are re-scaled so the
  book stays dollar-neutral at gross 1. Frozen and missing are the same state:
  no trade, position held.
- **Annualisation** by the panel's own bars per year: 252 × 76 = 19,152.

## 5. Dividends

`adjusted=true` is **split-adjusted only** (vendor documentation). The overnight
gap is therefore **missing on each name's ex-dividend dates**, taken from the
vendor's dividends endpoint: 40 ex-dates for the original nine names (ARM and
SPOT pay none) in `data/adr_manifest.json`, and 63 for the twelve large caps in
`data/adr_fallback_manifest.json`. Flat overnight keeps the dividend drop
out of every return.

## 6. Costs

**Registered source: option (b), a spread estimator from trade data.** Option
(a) is rejected: no free per-name quoted-spread source was found that is dated,
reproducible and covers all 21 names, and figures pulled from mixed sources and
dates would be harder to audit than a formula.

**Estimator: Abdi and Ranaldo (2017), the close–high–low estimator** (*Review of
Financial Studies*; cited from memory, to be checked against publisher metadata
before the write-up). Per name and session *d*, from regular-session bars
09:30–16:00: *c* is the log of the last close, η the mid-range (log high + log
low) / 2. Then

  ŝ²_d = max(0, 4 · mean over t of (c_t − η_t)(c_t − η_{t+1}))

over the 21 session pairs ending at session *d*−1, so the spread applied on
session *d* uses no data from *d*. **Floor: one cent**, ŝ_d ≥ 0.01 / close_{d−1}.

**Per-share fee:** $0.005 per share per side. **This is an assumption, not a
quoted rate**, rounded up so that it cannot flatter the book, and is converted to
return units as 0.005 / close_{d−1}.

**Charge per trade:** (ŝ_d / 2 + fee / close_{d−1}) × |Δw| for each name.
**Flat overnight implies at least two half-spreads and two fees per held name
per session:** in at the first traded bar, out by the last.

**Recorded as a look when the features are built:** each name's median ŝ over
the window. **Sensitivity readouts** at 0.5× and 2× the spread; neither decides a
verdict.

## 7. Null, certification route and α

**Null: zero return net of costs.** The reason is recorded because it decides
the readout below. Bars are trade-based, so bid-ask bounce makes the lag-1 own
return look predictive **gross** of costs in every name, controls included: a
print at the bid tends to be followed by one nearer the ask. The half-spread
charge is what removes it. A gross null would certify the bounce.

**Primary certification route: prior-weighted α** (`prereg/prior-weighted-alpha.md`).
A short list of up to five specifications, declared before the first `evaluate`
and refused if late, tested by Reality Check at **α_prior = 0.04**; the search
over the 968-member class at **α_search = 0.01**. Total size ≤ 0.05.

**Expected outcome, stated in advance: FAIL or INADMISSIBLE for most runs.**
Five-minute predictability in liquid ADRs is small next to a spread paid at least
twice a day per held name, and the preflight below leaves the search route
almost no power at 2.0. That is still informative for three reasons:

1. The gate runs on real data where the truth is probably null or small, which
   is the case where a gate that certifies is dangerous. A CERTIFIED verdict here
   would be the surprise that needs explaining.
2. The false-negative side, meaning FAIL submissions whose net holdout Sharpe is
   positive, is the readout nobody has, and it needs FAILs to measure.
3. It says whether declaring a short list in advance buys power the search route
   cannot, on data the agent has not seen.

## 8. Preflight, read at reference Sharpe 2.0

479 scored sessions (499 minus the 20-session warm-up), 76 bars each:
T = 36,404, 1.90 years, independent-trials worst case.

| route | N | α | bar | minimum certifiable (80% power) | power at 2.0 |
|---|---|---|---|---|---|
| short list | 5 | 0.04 | 1.74 | 2.35 | 0.64 |
| search, signed depth 2, K = 22 | 968 | 0.01 | 3.09 | 3.70 | 0.07 |
| *for comparison:* class unsplit | 968 | 0.05 | 2.81 | 3.42 | 0.13 |
| *for comparison:* short list unsplit | 5 | 0.05 | 1.68 | 2.29 | 0.67 |

**Breadth does not move the bar**: the bar depends on N (class size) and T only,
and the invoked fallback changes neither. What 18 names change is the Sharpe a
given per-name signal can reach. A dollar-neutral cross-sectional book
diversifies idiosyncratic noise, so for the same per-name predictability its
Sharpe grows roughly with √(names): about √3 ≈ 1.7× from 6 to 18. Breadth makes
2.0 more plausible to reach; it does not make 2.0 easier to certify. Serial
correlation is not modeled and would widen the standard error.

## 9. Readouts, registered

1. Verdict distributions per arm (ROADMAP 7.4 readout 1).
2. Holdout Sharpe, gross and net, of CERTIFIED, PASS and FAIL submissions; the
   false-negative count (ROADMAP 7.4 readout 2).
3. **Bid-ask bounce.** (i) The share of agent submissions containing a lag-1 own
   return with a negative sign (either copy). (ii) Gross and net Sharpe of the
   single specification −(own return, lag 1), on the treated panel and on the
   control panel. The bounce predicts a gross "edge" of similar size on both and
   none net. A gross edge on the treated panel that the controls do not show is
   what would need explaining.
4. **Placebo panel.** Every submitted specification graded on the controls; a
   home-close effect should fail there.
5. **Tech sub-panel.** Every submitted specification graded on the six tech
   names alone. A readout only, never certified, so it adds no test.
6. The three falsification counts of `prereg/adr-universe.md` (clock-mismatch,
   home holidays, home early closes), reported as counted.

## 10. Still to come with the feature code

- **The ancestor guard:** feature building refuses unless this commit is an
  ancestor of HEAD.
- The listing-structure and ADR-ratio check of `prereg/adr-universe.md`'s
  amendment: AZN's 2026-02-02 and UL's 2025-12-09 split records, and TTE, checked
  by hand against the depositary notices.
