# stability-statistic (item 4): minimum Sharpe across blocks, as an option

**DRAFT — committed but not live.** Authorises nothing. Prior art not yet
searched. This item **changes a statistic** and is one of the authorised
exceptions to ROADMAP's no-new-estimator-variants rule.

## Question

The default statistic is the full-sample Sharpe, which a strategy can earn in one
favourable stretch and nothing else. `--statistic stability` replaces it with the
**minimum Sharpe across J contiguous time blocks**, priced under the same null,
so it is valid by construction. It is **an option, never the default**. Does it
buy anything worth its cost in power?

## Design

**J = 2 and J = 4 are both registered**, and both are run. J = 4 is the primary;
J = 2 is registered alongside it so the **power-cost curve is visible** rather
than a single point, since the loss grows steeply with J and a lone figure would
hide that. Blocks are contiguous and equal-length: 2,500 periods each at J = 2,
1,250 at J = 4.

**The statistic is priced under the same null**, so validity needs no new
argument: whatever the statistic, the bar is the maximum of that statistic over
the declared class, computed on the same resamples. What changes is power.

**This is an engine change, and it moves the fingerprint.** `garden/_full_class_engine`
computes closed-form **full-sample** moments; per-block moments are a different
computation. `experiments/code_state.py`'s `CODE_PATHS` covers `garden/`, so the
harness fingerprint moves and any batch mid-flight stops. That is the intended
behaviour and is recorded here so it is not mistaken for a fault.

**Three parts.**

1. **s0 calibration**, with `ExhaustiveClass` as the exactness anchor — the only
   searcher for which exactness is claimed, predicted by P1.
2. **s3 power** against the default statistic, at matched nominal α.
3. **A regime cell**: the edge exists in **one block only**. This is where the
   option is supposed to earn its cost.

**Computed before the run**, calibrating effective breadth to arm D's *measured*
5% class bar of 1.0213 (which implies N ≈ 19,071; note this differs from the
N ≈ 4,442 that matches the null-max *mean*, and item 6 records that sensitivity):

| statistic | bar | power at stationary SR = 1.0 |
|---|---|---|
| default (full sample) | 1.0213 | **46.2%** |
| stability, J = 2 | 0.9335 | 34.0% |
| stability, J = 3 | 0.8554 | 26.8% |
| **stability, J = 4** | **0.7835** | **22.0%** |
| stability, J = 5 | 0.7160 | 18.6% |

**The registered figures are 46.2% → 34.0% at J = 2 and 46.2% → 22.0% at J = 4.**
Reporting both is the point: the cost is not a constant of the method, it is a
function of J, and a single number would present a design choice as a property.

**The regime cell needs a large enough within-block edge to discriminate**, and
this was nearly registered wrong. With an edge of Sharpe 1.0 in one of four
blocks, the full-sample Sharpe is 0.25 and **neither** statistic passes, so the
cell would have shown nothing:

| within-block Sharpe | full-sample | default passes | stability passes |
|---|---|---|---|
| 1.0 | 0.25 | 0.0% | 0.0% |
| 2.0 | 0.50 | 1.0% | 0.0% |
| **4.0** | **1.00** | **46.2%** | **0.0%** |
| 6.0 | 1.50 | 98.4% | 0.0% |

**Registered: within-block Sharpe 4.0**, giving a full-sample Sharpe of 1.0 —
the level at which the default certifies at its nominal power and the cell can
therefore show a difference. Stability's pass rate is ~0 at every level, which is
the point: it refuses non-persistent edges.

## Decision rules

1. **Anchor exactness on s0 (primary).** `ExhaustiveClass` under the stability
   statistic: the Wilson interval contains nominal at α = 0.05 and 0.01, and KS
   does not reject. Predicted by **P1**. *Passes 0.9548 / 0.9455 / 0.9500 for a
   correct procedure; family rate over the three checks 0.1358, so the one-shot
   replication branch applies on **fresh seed block 420000–421999**.*
   - *Holds:* the statistic is correctly sized and the power comparison is
     readable.
   - *Fails high:* the per-block moment path is wrong; nothing else is read.
   - *Fails low:* conservative where P1 predicts exactness; reported, and the
     stated size becomes an upper bound.
2. **Power cost at both J, reported not gated.** s3 PASS rate under the default
   and under stability at **J = 2 and J = 4**, at matched nominal α, against the
   registered 46.2% → 34.0% and 46.2% → 22.0%. The two points are reported
   together as the cost curve.
   - *Within a paired bootstrap interval of the prediction:* as designed.
   - *Materially worse:* the option costs more than registered and that is
     stated in the write-up.
3. **The regime cell (this is what the option is for).** Pass rate on the
   one-block-edge DGP at within-block Sharpe 4.0, under both statistics.
   - *Stability's pass rate materially below the default's:* the option reduces
     non-persistent passes, which is the case for offering it.
   - *Not materially below:* **the write-up says plainly that the option loses
     power and does not reduce non-persistent passes**, and it is not offered.
     Registered now so that outcome cannot be quietly dropped.

## Cost

Per-block moments over J = 4 blocks are roughly J times the moment work of the
default path, against an unchanged bootstrap resampling cost. **Not sized.** The
standing pre-launch rule in `ROADMAP.md` binds here because this changes the
workload's shape, which is exactly the condition 6.3's deviation 1 established.
