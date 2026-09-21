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

**2 — 2026-09-20, before the code is written. Cell (B) is pinned numerically, and
a replication branch is added against family false alarms.**

### (a) Cell (B), fixed now

**GARCH(1,1) on a common volatility factor.** One path `σ_t`, shared by all
M = 50 assets:

    σ²_t = ω + α ε²_{t-1} + β σ²_{t-1},   α = 0.10, β = 0.85

**Persistence α + β = 0.95**, comfortably stationary, and a standard daily-equity
calibration rather than one chosen to produce an outcome. `ω = σ²(1 − α − β)`, so
the unconditional variance equals the configured `sigma²` and cell (B) differs
from arm D's baseline in the *shape* of the noise, not its scale. The path is
burned in for 1,000 periods before the sample starts.

**Common, not per-asset, and this is the load-bearing choice.** A base feature
column is `mean_i(x[t,i,k] · ε[t,i])`, an average over 50 assets. Independent
per-asset t(4) innovations have finite variance (ν > 2), so that average is close
to Gaussian by the central limit theorem and independent per-asset volatility
paths average away likewise — the cell would stress the estimator barely at all
while appearing to. A **common** factor multiplies every asset's innovation by
the same `σ_t`, so the clustering and the heavy tail survive the
cross-sectional average and reach the statistic the null is taken over. Per-asset
innovations are therefore **not** what is registered, and the reason is recorded
here rather than discovered afterwards.

**The t(4) enters the return noise only; features stay Gaussian.** `ε[t,i]` is
`t(4)`, scaled to unit variance and multiplied by `σ_t`; `x` is unchanged from
arm D's configuration. This isolates one channel — cell (A) is the feature-side
stress — and it matches what `DGPConfig.fat_tails` already does, so no second
code path is introduced. **Fat-tailed features are not tested by this experiment**
and that is a named gap, not an oversight.

**ν = 4 sits on a boundary, deliberately, and this is registered in advance.**
`t(4)` has finite variance but **infinite kurtosis**. The bootstrap consistency
results behind P1 and P6 assume finite fourth moments. So a failure in cell (B)
or (C) is possible **for a reason attributable to the stress level rather than to
the method**, and must not be reported as a failure of the full-class null
without that distinction. If a failure replicates (see (b)), the named diagnostic
is a re-run at **ν = 6**, which has finite kurtosis: a failure that vanishes at
ν = 6 is a moment-condition failure, one that persists is not. That diagnostic is
**not** part of this experiment's registered cells and would be a separate,
separately-registered run.

### (b) Family false-alarm rates and the replication branch

Under exact calibration, each check false-alarms at a known rate, and these
experiments make many checks:

| check | per-check false alarm |
|---|---|
| rule 1 containment at α = 0.05 | 0.0452 |
| rule 1 containment at α = 0.01 | 0.0545 |
| rule 1 KS at 0.05 | 0.0500 |
| rule 2 one-sided at α = 0.05 | 0.0251 |
| rule 2 one-sided at α = 0.01 | 0.0336 |

**Rule 1 makes 9 checks** (3 cells × 3). Within a cell the three are computed on
the same 2,000 draws and are positively dependent, so the family rate is a little
below the independence figure: **0.1358 per cell** by simulation at 40,000
replications, giving **0.3546** across three independent cells. Treating all nine
as independent would say 0.3698.

**Rule 2 makes 18 checks** (3 cells × 3 searchers × 2 levels), giving a family
rate of **0.4151** if every searcher were exactly calibrated. That is not a
conservative overestimate here: arm D measured sub-maximal search as costing
0.0001 in mean Sharpe, so a *matched* searcher sits very close to exact, and
0.4151 is close to the rate actually faced.

So **more likely than not, at least one check fails somewhere in this experiment
even if nothing is wrong.** Reading the first such failure as a finding is the
error this branch exists to prevent.

**Replication branch.** The first failure of any check in rules 1 or 2 triggers
**one** pre-registered replication of **that cell and that searcher only**, on a
fresh seed block, at identical settings. Nothing else is rerun and no parameter
is changed.

- **Replication seed block: 410000–411999**, registered now, used by no other
  experiment.
- **If the replication passes:** the original is recorded as a family false
  alarm, with both rates reported side by side, and the halt / restriction
  branches of rules 1 and 2 do **not** fire.
- **If the replication fails too:** the failure is confirmed and the original
  rules' branches apply in full — the halt, the block-length investigation, the
  SCOPE restriction, as each rule already specifies.
- **Only one replication per failing check**, fixed now, so this cannot become
  resampling until a pass appears.
- The replication is itself a check and its own false-alarm rate is the
  per-check rate above; two independent failures of an exactly-calibrated check
  occur with probability at most 0.0545² ≈ 0.003, which is the level this branch
  actually buys.

**3 — 2026-09-20, before the experiment runs, found while writing the code. Cell
(A) as registered tests nothing, and the cost figure was wrong.**

### (a) Cell (A) needs rho > 0, and the loading range was misdescribed

The Design section registered cells (A) and (C) at **rho = 0**, inheriting arm
D's configuration. `environments.dgp.heterogeneous_correlation` **returns the
identity matrix when rho <= 0** — deliberately, so that "no correlation" has one
meaning whether or not the structure is heterogeneous. So at rho = 0 the
`heterogeneous` flag is a no-op: **cell (A) would have been arm D's baseline
rerun on fresh seeds, and cell (C) would have been identical to cell (B).**
Caught by running all three cells at small scale and finding (B) and (C)
producing bit-identical output.

**Registered fix.** Cells (A) and (C) run at **rho = 0.3**, which is exactly what
`unequal-correlation` used, so the structure is one this project has already
exercised rather than a new one invented here. Cell (B) stays at rho = 0, so each
cell changes one thing from arm D's baseline and (C) changes both:

| cell | correlation | noise |
|---|---|---|
| arm D baseline | rho = 0, equicorrelated | Gaussian |
| (A) | **rho = 0.3, heterogeneous** | Gaussian |
| (B) | rho = 0, equicorrelated | **common GARCH, t(4)** |
| (C) | **rho = 0.3, heterogeneous** | **common GARCH, t(4)** |

**The loading range in the Design section is wrong and is corrected here.** It
says "loadings spread 0.2–0.8", repeating `ROADMAP.md`'s description. The
implementation draws loadings uniformly on `sqrt(rho) +- 0.15`, so at rho = 0.3
they span **0.398 to 0.698**, giving pairwise correlations from **0.164 to
0.482** with mean 0.306. Measured, not asserted.

**On the confound.** Cell (A) now differs from arm D's baseline in two ways at
once: the correlation level (0 to 0.3) and its heterogeneity. An equicorrelated
rho = 0.3 control is **not** added, because one already exists: every earlier
null-calibration experiment in this project ran at rho = 0.3 under
equicorrelation and cost nothing (`SCOPE.md`, *The obliviousness condition*). If
cell (A) fails, that prior result is what separates the two explanations, and
the report must cite it rather than leaving the confound unresolved.

### (b) Two class nulls per draw, not one

The Cost section says "one null is priced per draw and shared across the four
searchers, as in arm D, so the searcher count does not multiply the cost." That
is wrong **because of this experiment's own matched-class design**: `Greedy` and
`Adaptive` are priced against the 10,700-member unsigned class while
`SignedAdaptive` and the anchor are priced against the 82,240-member signed
class, so **two** nulls are priced per draw.

The moment engine's cost is roughly linear in class size, so the unsigned null
adds about 13% to the signed one. The registered estimate of 7.8 h and $12.8 is
therefore an **underestimate by roughly that factor**, and no figure is asserted
here to replace it: the pre-launch smoke on cell (C) measures it, as the Cost
section already requires, and the measured number is what the launch decision
uses. Recorded now so the correction is not made after seeing the smoke.

## Deviations

**1 — 2026-09-21. The standing pre-launch smoke was skipped, deliberately, and
it cost a 2.2x cost surprise.**

`ROADMAP.md`'s Compute section carries a standing rule: measure per-draw cost end
to end, at the worker count the sweep will use, before any EC2 sweep. The Cost
section above repeats it. **It was not done.** The decision was explicit, not an
oversight, and the reasoning was:

1. at roughly $13 no measurement could change the go/no-go, since the experiment
   is on the roadmap either way and even 5x over is $65; and
2. the crash risk was already retired — cells A and C had been run end to end
   locally at the **full registered configuration** (K = 40, M = 50, T = 5,000,
   B = 10,000, both nulls), so the code was known to work at the size it would
   run.

Both points were true. The conclusion drawn from them was wrong, because they
address *whether the run works* and *whether to run it*, and the rule exists for
a third thing: **whether the quoted cost is right**.

**What happened.** Predicted 78 s/draw at 16 workers, from a local single-core
measurement scaled by arm D's laptop-to-instance ratio. Measured on the instance,
from four cell completions: **10.75 s/draw wall, 172 s/draw CPU** — 2.24x the
prediction. Cell C alone projects to 5.97 h and $9.79; all three cells to 17.9 h
and $29.37, against the 7.8 h and $12.8 the Cost section registered.

**Why the local measurement could not have caught it.** Serial work rose only
1.19x when the second class null was added — 26.97 s to 32.15 s, measured by
timing classes of increasing size and fitting: shared per-replicate work is
1.91 s, and the rest is class enumeration, roughly linear in class size at
305 s per million members. But contended throughput fell 2.24x. The extra
**1.91x is pure contention**: at 16 workers with one null the workload was
already at the memory-bandwidth knee, and 19% more bandwidth-bound work per draw
bought a 91% penalty. A single-core run cannot observe contention by
construction.

**The rule's scope, restated.** As written, the standing rule reads as a
budget-protection measure, which is what made it look disproportionate for a $13
run. That is the wrong justification. Its real content is: **contended per-draw
cost is not predictable from serial measurement whenever the workload changes
shape**, and adding a second bootstrap pass is a change of shape. The rule should
therefore bind on *shape changes*, not on *budget size* — a $13 run with a new
workload needs it, and a $500 rerun of an already-measured workload does not.
`ROADMAP.md` is amended to say that.

No decision rule of this pre-registration is affected; only the Cost section's
figure, which is superseded by the measured one above.

**2 — 2026-09-21. The run moved box partway through cell (C); interim outputs
exist on the registered seeds.** Recorded before any rule is read at n = 2,000.

*The box change.* Cell (C) began on the 32-vCPU instance at commit **`35a3fab`**.
It completed 800 draws (32 of 80 checkpoints, `C_0`–`C_775`, seeds
400000–400799) and stopped without an exit marker; its log was last written at
03:21 UTC on 2026-09-21. Cells (A) and (B) were not started there. Those 32
checkpoints were swept into git by an unrelated commit, **`de50c68`**. The
experiment resumed on a c7a.48xlarge (192 vCPU) at commit **`df161c3`**, at
18:38 UTC on 2026-09-21, with 192 workers. It ran cell (C) from the 32 existing
checkpoints, then (A), then (B), in one detached chain. Between `35a3fab` and
`df161c3` the only change to anything 6.3 imports or runs is `pyproject.toml`'s
package list, which gained `quixote`; `experiments/heterogeneous_and_fat.py`,
`experiments/_parallel.py`, `environments`, `estimator`, `garden` and
`searchers` are identical. The 32 checkpoints have identical SHA-256 on the old
box, in the repository, and on the c7a before the resume.

*The cross-box check.* Before resuming, the first checkpoint's 25 draws (seeds
400000–400024) were recomputed on the c7a into a separate directory and
compared with the old box's `C_0` in every stored field except wall-clock
seconds. Result: **identical**, 25 of 25 draws, with an equal canonical hash over
all stored arrays. The comparison tested equality only and computed no rule
quantity.

*Interim outputs on the registered seeds, disclosed.* Two exist before the
n = 2,000 read.

1. **The 800-draw checkpoint set of cell (C).** No rule quantity was computed
   from it in the session that found it. Its structure (field names, draw count)
   was inspected to establish how far the run had got. It has been in the public
   repository since `de50c68`, so an earlier reading cannot be ruled out, and
   none is claimed.
2. **Six scaling-smoke reports of cell (C)**, at n = 2, 32, 96, 192, 288 and 384,
   in `figures/scaling_c7a48xl/`, committed in `2dd4473`. `--smoke N` runs the
   first N registered seeds from 400000, and each report prints rules 1–4 on
   those draws. They are therefore interim readouts of the same draws the full
   cell contains, at up to 19% of its sample. They were produced to measure cost,
   and this record does not state their values.

Neither changes a decision rule, a threshold or a draw. Every rule is read once
at n = 2,000 per cell, in the registered order, and the interim outputs are
disclosed here so that the read is not presented as the first look at these
seeds.

## Rule reading at n = 2,000, 2026-09-21

Read once, in registered order, from the fetched cell reports (commit `df161c3`,
2,000 draws per cell on seeds 400000–401999). **26 of 27 checks pass.** The one
failure is rule 1's KS test on cell (A)'s anchor: **D = 0.0367 against a 5%
critical value of 0.0304, p = 0.0090**. Both of cell (A)'s containment checks
pass: 5.60% (4.67–6.70) at α = 0.05 and 1.00% (0.65–1.54) at α = 0.01. Rule 2
shows no liberal failure in any cell. Block lengths have median 1, 2 and 2 in
cells (A), (B) and (C), with maxima of 2, 52 and 55. Guard counts are zero
throughout.

**Where cell (A)'s anchor ECDF departs from the diagonal.** It lies **above** the
diagonal through the middle and upper range. The largest gap is +0.037 at
p ≈ 0.61, and it stays above from about p = 0.25 to 0.95. There is excess mass in
[0.5, 0.6), 241 draws against 200 expected, and a deficit over [0.6, 1.0), 728
against 800. **The rejection tail is on the diagonal:** ECDF(0.01) = 0.0100,
ECDF(0.05) = 0.056, ECDF(0.10) = 0.1005. The largest gap below the diagonal is
0.007, at p = 0.17. So the p-values are slightly too small in the body of the
distribution, not in the region any decision reads.

**How strong p = 0.009 is.** Under exact calibration the three cells' KS
p-values are independent and uniform, so the chance that the smallest is at or
below 0.009 is 1 − 0.991³ ≈ **2.7%**. That is stronger evidence than a bare
false alarm at the 5% KS level, and weaker than it looks in isolation. Rule 1's
registered family rate (0.3546 across the three cells) covers all nine of its
checks at their own thresholds, not this p-value. **The replication decides**,
per amendment 2(b): cell (A), anchor, seeds 410000–411999, identical settings.
If it passes, cell (A)'s KS rejection is recorded as a family false alarm. If it
fails, rule 1's branches apply in full.
