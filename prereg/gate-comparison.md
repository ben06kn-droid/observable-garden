# gate-comparison (7.0): which test should certify?

**DRAFT — committed but not live.** It is in the tree so it cannot be lost, it
has not been reviewed, and it authorises nothing. 7.0 does not run until it has
been read and the launch decision is taken, which waits on `calibration-at-1pct`
arm D: arm D's rule 4 decomposition splits the class gate's conservatism into
confinement and sub-maximal search, and the matched-class design below rests on
which of the two dominates. Code: `experiments/gate_comparison.py`, not yet
written.

## Question

Three certifiers can license a claim that a searched-for strategy has an edge,
and they are not interchangeable. Which should the gate use, and in what order
should 7.2's tiers fall back?

- **Declared class, full sample.** The full-class null over a class fixed before
  the search. Finite-sample valid, conservative, and already built.
- **Holdout.** Split the sample, search the first part, test once on the second.
  Exact under slice independence, but it buys that exactness with standard error:
  a 70/30 split tests on 30% of the data.
- **Process replay, full sample.** Re-execute the search on each bootstrap
  resample. Uses the whole sample and prices the actual search, but its validity
  is asymptotic and its size is what 7.1 and 7.3 measure.

Unregistered scouting on 2026-09-19 (scripted greedy, K=40, d=3 signed, T=5,000,
n=120-300, null rates 4-9% so direction only) put the class gate ahead of the
holdout under search and behind it for a single fixed strategy. That reversal is
the thing to establish properly, because it decides 7.2's tier order.

## Design

**Draws.** 2,000 per cell, seeds 200000-201999. A different block from
`calibration-at-1pct`'s 100000-101999, so no draw is shared with arm D and
nothing is reused across pre-registrations.

**Configuration.** M = 50, T = 5,000, T_oos = 1,000, K = 40, rho = 0, the s0 and
s3 configurations of `experiments/e_agent.py`. s0 is the pure null and every
rejection is a type-I error; s3 carries the real edge and is where PASS rate
means power.

**Searchers, each priced against a class it can actually reach.** This is the
correction `calibration-at-1pct` deviation 1 forced. `Greedy` and `Adaptive`
build weights with `_one_hot_sum` and are confined to the unsigned sublattice —
10,700 members at K=40, d=3 — while the signed class holds 82,240. Pricing an
unsigned searcher against a signed bar measures its confinement, not the
certifier, and that is what made arm B unreadable.

| searcher | class priced against | members |
|---|---|---|
| `Greedy` | `SubsetClass(max_size=3, signed=False)` | 10,700 |
| `Adaptive` | `SubsetClass(max_size=3, signed=False)` | 10,700 |
| `SignedGreedy` | `SubsetClass(max_size=3, signed=True)` | 82,240 |
| `SignedAdaptive` | `SubsetClass(max_size=3, signed=True)` | 82,240 |
| `ExhaustiveClass` | `SubsetClass(max_size=3, signed=True)` | 82,240 |

**The exhaustive searcher is the calibration anchor, not a competitor.**
`ExhaustiveClass` submits the argmax over its declared class, so P2's inequality
binds with equality and its conservatism vanishes; what remains is P1, which
predicts exact calibration. It is therefore the only arm whose size measures the
*certifier* rather than its own position in the class, and every other arm's size
is read as a distance from it. It is scored under the declared-class certifier
only: a holdout or a replay of an exhaustive enumeration is a different object
and is not part of this question.

**Certifiers.** Four per draw, on the same panel:

1. declared class, full sample;
2. holdout 70/30 — search on the first 3,500 periods, one test at alpha on the
   last 1,500;
3. holdout 50/50;
4. process replay, full sample, via `estimator/recursive_bootstrap.py`.

**Regime-shift cell.** One additional cell per certifier, on s3 only: the true
beta on `S[0]` **sign-flipped** in the out-of-sample panel, the submission held
fixed. This is the same shift `costs-and-regime-change` ran, deliberately, so
the two results are directly comparable: 6.2 measured the class gate's PASS
advantage eroding from +0.46 to +0.08 in median gross OOS Sharpe under it. The
question here is whether a later-in-time holdout tier degrades differently under
the same shift, which is the case where the holdout might win.

**Recorded per draw**, so no later experiment has to re-price a null: the
observed statistic, the p-value under each certifier, and the null-max quantiles
at 0.90 / 0.95 / 0.99 / 0.999. Arm B stored only a mean and had to be paid for
twice; that is not repeated.

## Decision rules

Per `prereg/README.md`: validity claims get one-sided rules, exactness rules name
the proposition predicting them, and every rule states both directions.

1. **Anchor calibration (exactness, primary).** For `ExhaustiveClass` under the
   declared-class certifier on s0, the Wilson 95% interval for the rejection
   rate contains alpha at 0.05 and at 0.01, and KS does not reject uniformity.
   **Exactness is admissible here and only here**, predicted by P1 for a
   data-independent menu whose maximum is submitted.
   - *Holds:* the declared-class certifier is correctly sized, and every other
     arm's shortfall is that arm's own position in the class.
   - *Fails high:* the certifier over-rejects; nothing downstream is read until
     that is understood, since all three certifiers are compared against it.
   - *Fails low:* not predicted by P1 and not explicable by searcher position.
     Reported, and the declared-class tier's stated size is treated as an upper
     bound rather than a rate.
2. **Size of every certifier (validity, one-sided).** For each searcher and each
   certifier on s0, the **upper** end of the Wilson interval for the rejection
   rate does not exceed alpha by more than 0.5 percentage points at alpha = 0.05,
   or 0.2 at alpha = 0.01.
   - *Holds:* that certifier is usable at that level.
   - *Fails high:* it is liberal. It is excluded from 7.2's tier order regardless
     of its power, and the exclusion is reported.
   - *Fails low:* conservative, which is permitted and is exactly what rule 3
     then has to price.
3. **Power at matched actual type-I, never at matched nominal.** PASS rate on s3,
   compared across certifiers **at their measured s0 rates**, not at nominal
   alpha. Arm A measured the class gate's actual size at 1.0% for scripted
   Adaptive against a nominal 5%; comparing PASS rates at nominal alpha would
   credit a competitor with power that is really the class gate's unused size.
   Reported as a PASS-rate curve against realised type-I, with a paired bootstrap
   interval over draws.
   - *Reported both ways* — no halt. This rule ranks, it does not gate.
4. **Tier order (the gate on 7.2).** The ordering of certifiers by power at
   matched actual type-I, among those surviving rule 2. Expected: replay, class,
   holdout.
   - *As expected:* 7.2 builds the tiers in that order.
   - *Replay does not beat the class gate on s3 at matched type-I:* Phase 7
     reduces to the holdout fallback plus the measurements, and says so. This is
     a reportable outcome, not a reason to retune replay.
   - *The holdout wins outright:* the split is worth its standard error, and the
     class tier becomes the fallback rather than the primary. Not predicted by
     the scouting, and investigated before write-up.
5. **The regime-shift cell (secondary, no halt).** The change in PASS rate on s3
   under the `S[0]` sign flip, per certifier, with a paired bootstrap interval.
   - *A certifier that degrades less* is evidence for it on robustness grounds
     and is reported alongside its power, not instead of it.
   - *All degrade alike:* the shift does not separate them, reported as such.
   - Comparable by construction to 6.2's +0.46 to +0.08 erosion, since it is the
     same shift on the same DGP.

## Cost

**Measured, not extrapolated, for the part that has been measured.** The
declared-class null at K=40, d=3 signed, T=5,000, B=10,000 costs **75.03 s per
draw at 16 workers** (`calibration-at-1pct` arm D's sizing smoke, 2026-09-20),
which is $0.0022 per draw at $1.64/h. One null is priced per draw and shared
across searchers, as in arm D.

- Declared class, s0 + s3: 4,000 draws ≈ **5.2 h, $8.6**.
- Holdout cells: negligible; no bootstrap over a class.
- Regime-shift cell: one extra grading pass per draw, no new null.

**Process replay is not yet sized, and 7.0 does not launch until it is.** It
re-executes the search inside every replicate, so its per-draw cost is a
different order and cannot be inferred from the class null. The standing
pre-launch step in `ROADMAP.md`'s Compute section applies: a four-point scaling
curve at 1/4/16/32 workers and an end-to-end smoke at the worker count the run
will use, before any budget is committed. Skipping that cost arm B 4.7x its
estimate.

**Standing configuration:** 16 workers on the 32-core instance. Not
`nproc --all`; 32 workers are 4% slower in wall-clock and marginally dearer per
draw on this workload.
