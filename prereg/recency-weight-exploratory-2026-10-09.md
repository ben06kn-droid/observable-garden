# A recency-weighted certificate: exploratory note, 2026-10-09 (America/Chicago)

**Status: EXPLORATORY NOTE, committed alone before any code.** It defines a statistic, its
null, its levels and its descriptive line. Nothing here is live.
- No code exists for it yet. No panel, real or planted, has been priced with it.
- It changes no registered read. The French, ETF and Binance registrations keep their
  unweighted statistics.
- Validation is Part 2 of the author's request: code behind a flag, then planted panels on
  dedicated seed blocks. It comes after this note, under its own registered expectations.

**Notation.** "Half-life" (written h below) is this note's H. It is not
`quixote.confidence`'s `H`, which is the horizon of P_H and is unchanged.

## a. The statistic

- **Weights:** w_t = 2^(−(T − t)/h) for each scored row t, where T is the last scored row.
  The last row has weight 1, and a row h rows earlier has weight 1/2.
- **Half-life: h = 5 years of rows.**
  - On daily panels (252 rows a year), that is **1,260 rows**.
  - On 4h panels (2,190 rows a year), it is **10,950 rows**. The Binance panel scores 3.70
    years, under one half-life, so its oldest row still carries weight about 0.6.
- **The weighted Sharpe of a net stream x over the scored rows:**
  - weighted mean m_w = Σ w_t x_t / Σ w_t;
  - weighted variance v_w = Σ w_t (x_t − m_w)² / (Σ w_t − Σ w_t² / Σ w_t). This is the
    reliability-weights correction, which reduces to the usual n − 1 when all weights are
    equal;
  - S_w = m_w / sqrt(v_w) × sqrt(ppy), annualised with the panel's periods per year, as
    now.
- **With all weights equal** (h → ∞), S_w equals the current statistic exactly. Part 2
  tests that limit.

**How much data the weights leave: the effective length.** n_eff = (Σw)² / Σw². For a
window of Y years it is about (2h / ln 2) · (1 − a)/(1 + a), with a = 2^(−Y/h):

| window (years) | 3.7 (Binance) | 7 | 10 (French) | 20 | 30 | 60 |
|---|---|---|---|---|---|---|
| effective years | 3.6 | 6.5 | 8.7 | 12.7 | 14.0 | 14.4 |

**However long the history, the statistic never uses more than about 14.4 effective
years.** Lo's standard error then floors at about sqrt((1 + SR²/2) / 14.4), which is
0.26 at SR = 0. That is the detection floor's limit under these weights (section c and
Part 2).

## b. The null

- **Centre the stream by its own weighted mean:** x0_t = x_t − m_w(x). The null is then a
  stream whose weighted mean is exactly zero.
- **Resample as now:** stationary bootstrap index sets I_b of length T, with the block
  length of section c. The seeds are registered per read.
- **The weights attach to POSITION, not to the resampled row.** The b-th replicate is the
  series y_t = x0[I_b(t)], weighted by w_t at position t. So a block drawn from an old
  period, placed at a recent position, carries a recent weight.
  S_w,b = the weighted Sharpe of y under w.
- **p = (1 + #{b : S_w,b ≥ S_w}) / (B + 1),** the same convention as the current tiers.
- **The class maximum, the same construction:**
  - every member's stream is centred by its own weighted mean;
  - all members are resampled jointly with the same I_b;
  - each member is weighted per position;
  - M_b = the maximum over members of the weighted Sharpes; the observed statistic is the
    maximum of the members' observed weighted Sharpes.
- **How the fast kernel carries it:** a replicate's weighted moments are linear in a
  weighted count. Let W[s, b] = Σ over t with I_b(t) = s of w_t (the unweighted kernel uses
  plain counts). Then Σ_t w_t y_t = Σ_s W[s, b] · x0_s, and the same holds for the
  squares. The kernel's matrix products are unchanged with W in place of the count
  matrix. The variance correction needs Σw and Σw² only, which are fixed.

## c. Block length

- **The Politis–White rule, as now:** for the class tier, the class rule on its window;
  for a stream, the rule each registration names (on Binance, the whole in-sample
  window).
- **The rule is computed on unweighted data.** Dependence is measured over the whole window,
  while the statistic leans on its last ~14 effective years.
- **What changes when the effective length is ~14 years:**
  - **Nothing in the mechanics.** The block length is a few rows to a few dozen, far below
    14 years of rows. The resampled series still has length T, and the weights are
    applied after.
  - **What the null assumes changes in practice.** The bootstrap draws blocks from the
    whole window, including decades the statistic down-weights. If the stream's variance
    or dependence differs between old and recent periods, the null mixes them. The
    weighted Sharpe is scale-free, so a pure level shift in volatility matters little. A
    change in tail shape or dependence does matter. Part 2 checks this by simulation; it
    is not proved.
  - **A check, not a rule:** each read also reports the Politis–White median on the last
    n_eff rows. A large difference from the registered length is flagged in the read,
    and changes nothing.

## d. Levels

- **The registered certificate stays at the current split:** stream p < 0.04, class
  p < 0.01. It is called the **96% level**, after the stream's 1 − 0.04, as now, and its
  family-wise error over the two tiers is at most 5%.
- **A second registered level, always labelled "90% level":** stream p < 0.08, class
  p < 0.02. Its family-wise error is at most 10%.
  - Every result at it carries the words "90% level" in the same line.
  - A certificate at the 90% level only is reported as such, never as a certificate
    without qualification.
- **Both levels are read from the same p-values.** No extra test is run.

## e. The lower bound

- **L90 is computed under the same weights:** L90 = S_w − q_0.90(null replicates), from
  `quixote.confidence.confidence` given the weighted statistic and the weighted null. The
  class tier uses the weighted class maxima, as now.
- **It bounds the recency-weighted Sharpe, not the unweighted one.** The read says so
  beside it.

## f. The performance line (descriptive; never gates)

- **The UNWEIGHTED net Sharpe over the last 252 and the last 756 scored rows,** each with a
  bootstrap 90% interval: the 5% and 95% points over B stationary-bootstrap resamples of
  those rows, with the block length of section c and seeds registered per read.
- **It never gates, and never enters a p-value or a bound.** It is printed after the
  verdicts, labelled "performance line, descriptive".
- **On 4h panels,** 252 and 756 rows are 42 and 126 days. Whether to use 1 and 3 years of
  rows there (2,190 and 6,570) is left to the registration that uses it.

## g. What is not claimed

- **No novelty.** Exponentially weighted moments and recency-weighted performance measures
  are standard. This note only fixes one version for this project's gate.
- **The weighted bootstrap's validity is checked by simulation, not proved.** No result is
  claimed on its asymptotic size or power. Part 2's planted panels measure the
  false-positive rate and the power against constant, decaying and emerging edges, under
  expectations registered before they run.
- **It trades power for recency.** On a constant edge it has less power than the
  unweighted statistic, because it discards effective data (the table in section a). That
  cost is stated in advance and measured in Part 2.
