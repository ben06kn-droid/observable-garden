# heterogeneous-correlation-fat-tails (6.3): does the full-class null survive realistic features?

**DRAFT — committed but not live.** It authorises nothing and 6.3 does not run
until it has been read. Code: `experiments/heterogeneous_and_fat.py`, not yet
written.

## Question

The declared-class tier's calibration was established under **equicorrelated
Gaussian** features. Real features are neither: their correlations come from
shared factor exposure and vary pair by pair, and their innovations are
fat-tailed and volatility-clustered. Does the full-class null hold when both
assumptions are broken?

`calibration-at-1pct` arm D settled the Gaussian equicorrelated case at
K = 40, d = 3: with `ExhaustiveClass` submitting the class maximum, rejection
rates were 9.60 / 5.50 / 0.95 percent against nominal 10 / 5 / 1, and KS did not
reject. That is the baseline this experiment perturbs, and the reason exactness
is claimable here at all.

## Design

**Two DGP variants**, each replacing one assumption and holding everything else
at arm D's configuration (M = 50, T = 5,000, T_oos = 1,000, K = 40, s = 0,
B = 10,000):

- **(A) Heterogeneous correlation.** The one-factor loading structure already
  used by `unequal-correlation`: pairwise correlation `λᵢλⱼ` with loadings
  spread uniformly over 0.2–0.8. Correlation is then pair-specific rather than
  common, so the effective number of independent class members varies across the
  class rather than being a single constant.
- **(B) Fat tails and clustered volatility.** Student-t innovations at ν = 4 on
  a GARCH(1,1)-style volatility path. The stationary block bootstrap is already
  the chosen resampler and is what is supposed to absorb the dependence; this
  cell is where that choice is tested rather than assumed.

A **third cell (C) combines both**, since the two failure modes could interact
and reporting them only separately would miss it. Registered now so its absence
from a result table is not a later choice.

**Searchers, each priced against a class it can reach.** Arm D established that
class mismatch, not search inefficiency, dominates the gate's conservatism, so
every searcher here is matched:

| searcher | class priced against | members | role |
|---|---|---|---|
| `ExhaustiveClass` | `SubsetClass(max_size=3, signed=True)` | 82,240 | **anchor** |
| `SignedAdaptive` | `SubsetClass(max_size=3, signed=True)` | 82,240 | matched, efficient |
| `Greedy` | `SubsetClass(max_size=3, signed=False)` | 10,700 | matched, reachable |
| `Adaptive` | `SubsetClass(max_size=3, signed=False)` | 10,700 | matched, reachable |

**The anchor is what makes exactness claimable.** `ExhaustiveClass` submits the
argmax over its declared class, so P2 binds with equality and its conservatism
vanishes; what remains is P1, which predicts exact calibration for a
data-independent menu. **Exactness is therefore claimed for the anchor and for
nothing else.** Every other searcher submits below its class maximum, so P2
predicts conservatism and only validity is claimed for it — one-sided, upper end
only. This is the rule `calibration-at-1pct` broke, and it cost an arm.

**Draws.** 2,000 per cell on seeds 400000-401999, a block used by no other
pre-registration, s0 only. Three cells × four searchers, with one class null
priced per draw and shared across searchers as in arm D.

**Recorded per draw**: the observed statistic and p-value per searcher, the
selected block length, the guard counts, and the null-max quantiles at
0.90 / 0.95 / 0.99 / 0.999.

## Decision rules

Per `prereg/README.md`.

1. **Anchor exactness (primary).** In each of the three cells, the Wilson 95%
   interval for `ExhaustiveClass`'s rejection rate contains nominal at
   alpha = 0.05 and 0.01, and KS does not reject uniformity at 0.05. Predicted by
   **P1**, which is what licenses an exactness rule here.
   - *Holds:* the full-class null survives that departure, and the tier's stated
     size carries to features with that structure.
   - *Fails high in cell (B) or (C) at 1% only:* the bootstrap tail is not
     absorbing the dependence. **The block-length selector is the first suspect**
     and the chosen block lengths are reported per cell before anything else is
     changed; the tier's validity is restricted to the cells where it held, and
     the restriction is stated in SCOPE.
   - *Fails high at 5% as well:* not a tail problem but a failure of the null
     itself under that structure. Halt and report; no parameter is retuned after
     seeing the rate.
   - *Fails low:* conservative where P1 predicts exactness. Not explicable by
     searcher position, since the anchor has none. Reported, and the tier's size
     is treated as an upper bound in that cell.
2. **Every other searcher is valid (one-sided).** For `Greedy`, `Adaptive` and
   `SignedAdaptive` in each cell, the **upper** end of the Wilson interval does
   not exceed nominal by more than 0.5 points at alpha = 0.05 or 0.2 at 0.01.
   Only validity is claimed — P2 predicts these come in under nominal — so an
   interval that fails to contain nominal is **not** a failure.
   - *Holds:* the tier is usable with those searchers under that structure.
   - *Fails high:* liberal, which P2 forbids; investigated before rule 1 is read
     in that cell, since both rest on the same null.
   - *Fails low:* expected and reported as the conservatism it is, with the
     actual size, for 7.0's matched-type-I comparison.
   - **No KS test is applied to these three.** Under P2 with a sub-maximal
     searcher, uniformity is not predicted and KS would reject whatever the
     bootstrap does. Applying it anyway is the arm B mistake.
3. **Block lengths, reported not gated.** The distribution of selected block
   lengths per cell, with the anchor's rejection rate beside it. Arm D's
   equicorrelated Gaussian cell chose block length 1 (median 1, max 2), which is
   correct for iid features; cells (B) and (C) must choose longer ones or the
   selector is not seeing the dependence, and that is reportable whether or not
   rule 1 holds.
4. **Guards, reported not gated.** Variance-floor and Sharpe-cap bind counts per
   cell. Arm D's were zero. Fat tails at ν = 4 can make the Sharpe statistic
   explode over rarely-trading members, and a non-zero cap count changes what the
   rejection rate means, so it is reported beside every rate.

## Cost

**Sized from measurement.** The full-class null at this configuration costs
**75.03 s per draw at 16 workers** (`calibration-at-1pct` arm D's sizing smoke,
confirmed at 75.50 s over arm D's own 2,000 draws — a 0.6% agreement). One null
is priced per draw and shared across the four searchers, as in arm D, so the
searcher count does not multiply the cost.

- 3 cells × 2,000 draws = 6,000 draws.
- 6,000 × 75.03 s / 16 workers = **7.8 h wall**.
- At $1.64/h: **$12.8**.

Two caveats on that figure, both stated before the run rather than after. The
GARCH path and Student-t draws add per-draw work that the Gaussian measurement
does not contain, and the heterogeneous-correlation variant changes the Cholesky
but not its order. Neither is expected to be material against a 75 s bootstrap,
but **the standing pre-launch step still applies**: an end-to-end smoke at 16
workers on cell (C), the most expensive, before the budget is committed.
Skipping that cost arm B 4.7x its estimate.

**Standing configuration:** 16 workers on the 32-core instance.

## Amendments

**1 — 2026-09-20, before the experiment runs. Rule 2's one-sided form is
corrected.**

Rule 2 above says the **upper** end of the Wilson interval must not exceed
nominal by more than 0.5 points at α = 0.05 or 0.2 at α = 0.01. That wording came
from `prereg/README.md` and is wrong for the reason its amendment 1 records: at
n = 2,000 it passes only if the observed rate is at or below 4.50% and 0.70%
respectively, which an exactly valid test achieves just 16.5% and 10.4% of the
time. It would fail `calibration-at-1pct` arm D's anchor at both levels.

**Rule 2 is replaced.** For `Greedy`, `Adaptive` and `SignedAdaptive` in each
cell, validity **fails high iff the LOWER end of the Wilson 95% interval exceeds
nominal** — liberality demonstrated, not merely un-excluded. The **upper** end is
reported as the largest liberality the data do not rule out. Both other branches
are unchanged: a rate below nominal is expected under P2 and is reported as the
conservatism it is, and no KS test is applied to these three.

**Detectable liberality at this experiment's n = 2,000 per cell**, stated so a
pass is not read as more than it is: the rule fires at k ≥ 120 (6.00%) at
α = 0.05 and k ≥ 29 (1.45%) at α = 0.01, giving 80% power against a true rate of
**6.44%** and **1.67%** respectively, and firing on an exactly valid procedure
2.51% and 3.36% of the time. **This experiment cannot see a searcher that rejects
at 5.5% against a nominal 5%**, and does not claim to.

Rule 1, the anchor's exactness rule, is **unchanged** — it is a two-sided
containment rule licensed by P1, which is a different claim and was never
affected.
