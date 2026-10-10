# The recency-weighted certificate on planted panels, round 2: plan, 2026-10-09 (America/Chicago)

**Status: PLAN with a registered decision rule, committed alone before any round-2 code. NOT
RUN.** Nothing runs on the box without the author's typed go. Round 1 is
`prereg/recency-weight-planted.md` (`07fa892`; amendments `e48113e`, `a2fc19f`, `5bf5b43`); its
read is at `754c295`.

## 1. Why a round 2: the diagnosis of NA40

Round 1's NA40 arm adds dependence to the most recent 25% of rows. Its weighted rate failed:
0.075 at the 4% level and 0.119 at the 8% level. The unweighted rate passed (0.028 and
0.055). The two block-length medians were close (7 by the registered rule, 8 on the last
n_eff rows).

**The diagnosis (the author's, checked here; this agrees):**
- **The statistic's variance is set by the recent rows.** For a weight that varies slowly
  against the dependence length, Var(m_w) ≈ Σ_t w_t² σ²_LR(t) / (Σ w)², where σ²_LR(t) is
  the local long-run variance.
  - With h = 1,260 rows, w² halves every 630 rows.
  - So the newest 2,520 rows of a 40-year panel (25%) carry 1 − 2^(−4) ≈ 94% of the Σw² mass.
- **The null's long-run variance is the pool average.** It draws blocks uniformly from the
  pool.
- **In NA40:**
  - the recent rows' long-run variance is (1 + 0.3 + 0.3)² / 1.18 = 2.17 times the base
    (marginal variance unchanged);
  - the statistic's variance is therefore about 2.1 (recent units);
  - the null's is about 0.75 × 1 + 0.25 × 2.17 = 1.29.
  - The ratio is 1.63, an sd ratio of 1.28. The predicted rate at the 4% level is
    P(Z > 1.751 / 1.28) ≈ 0.085; observed 0.075.
- **So it is not the block length.** The same statistic with the right block length and a
  uniform draw still compares against the wrong long-run variance.
- **Round 1's NV40 rate (0.025) points the same way.** There the old rows have twice the
  volatility, and the uniform draw overstates the null's spread, which makes the test
  conservative.

## 2. Candidate W2: the weighted draw

- **The draw:** a stationary bootstrap as now (geometric block lengths with mean L, blocks
  running forward and wrapping circularly), except for where each block STARTS:
  - every block after the first starts at row s with probability π_s ∝ w_s²;
  - **the first block starts at row s with probability q_s,** defined below (proposed here;
    see the derivation).
- **The weights still attach to position.** The statistic and its replicates are the
  weighted Sharpe of section a of the note.
- **Centring:** each stream is centred by its q-weighted mean, x0_s = x_s − Σ_r q_r x_r, so
  that E*[y_t] = 0 at every position t.

**The derivation.**
- Write p = 1/L and let J_t be the resampled row at position t. A stationary bootstrap with
  geometric lengths is the Markov chain J_t = J_{t−1} + 1 (mod n) with probability 1 − p,
  and a new start drawn from π with probability p. The per-block sampler with geometric
  lengths has the same law.
- So the marginal q_t of J_t satisfies q_t = p·π + (1 − p)·S q_{t−1}, where S shifts
  forward by one row on the circle.
- **Its fixed point:** q = Σ_{k≥0} p (1 − p)^k S^k π. That is π circularly convolved with
  the geometric offset. On a circle of n rows the kernel is exact:
  g_k = p (1 − p)^k / (1 − (1 − p)^n), for k = 0 … n − 1.
- **If the first start is drawn from π,** as the current sampler does: q_t = q for large t,
  but not for the first few blocks. The gap decays as (1 − p)^(t−1). It is small (those are
  the oldest, least-weighted positions) but not zero.
- **Drawing the first start from q instead makes q_t = q at every position, exactly,**
  because q is the fixed point. Then the q-centring gives E*[y_t] = Σ_s q_s x0_s = 0 at every
  t. This is the proposed form [AUTHOR].
- **Numerical check:** the code is tested by computing the empirical marginal of J_t over
  many replicates, at early and late positions, against q. Also, E*[mean of y] is checked
  to be 0 within Monte Carlo error.

**Equal weights:** π and q are uniform, and the q-weighted mean is the plain mean. The code
then calls the current sampler (`estimator.bootstrap.stationary_bootstrap_indices`) with
the same random stream. **So W2 with equal weights reproduces the current null bit for
bit,** by the same code path. This is tested.

**The class maximum:**
- the same index sets for every member;
- each member centred by its own q-weighted mean;
- the weighted-count kernel unchanged in form: W[s, b] = Σ_t w_t 1{I_b(t) = s}.

On the planted panels, q is aggregated to pool rows as round 1 aggregated the weights.

## 3. Candidate R15: the fallback

- **The existing unweighted test, unchanged, on the last 3,780 scored rows only** (15 years
  of daily rows).
- Its block length is by the class rule on the base columns of those same 3,780 rows,
  which is the existing test applied to that window.
- It has no weights, and needs no new null.

## 4. Arms

Every arm uses fresh seed blocks, checked with `experiments.seed_block_check` on 2026-10-09:
NO COLLISION for each block below.

| arm | length | what | panels | seeds |
|---|---|---|---|---|
| N40 | 40 y | stationary null | 1,000 | 709000–709999 |
| NV40 | 40 y | volatility ×2 on the oldest 75% (as round 1) | 1,000 | 710000–710999 |
| NA40 | 40 y | dependence on the newest 25%, scaled form (as round 1) | 1,000 | 711000–711999 |
| **NAREV40** | 40 y | **dependence on the OLDEST 75%,** the same scaled form, none recent | 1,000 | 712000–712999 |
| E20 | 20 y | emerging, β 1.0 | 400 | 713000–713399 |
| D20 | 20 y | decaying, β 0.5 | 400 | 713400–713799 |
| C20 | 20 y | constant, β 0.5 | 400 | 713800–714199 |
| smoke and dry run | — | cost only (smoke); fields (dry) | 10 | 714900–714909, never read |

- **Panels as in round 1:** the ETF pool row-resampled (block 7), exact gross nulls, with
  every shift applied to every stream on the panel.
- **The tests on every panel, on one shared set of seeds per panel:**
  - W2;
  - R15;
  - the round-1 fixed centring, beside;
  - the unweighted statistic on the whole window, beside.
- **The class tier under W2 runs on N40 and NA40 only.**
- **Levels:** the 96% level (stream p < 0.04, class p < 0.01) and the 90% level (stream
  p < 0.08, class p < 0.02).
- **The block length** for W2 and the round-1 fixed centring is by the registered rule on
  the whole window. The Politis–White median on the last n_eff rows is recorded beside it,
  in every panel.

## 5. The registered rule

**No expectation is registered for W2 on NA40.** Both of its branches are below.

- **W2 is ADOPTED for weighted reads iff no null arm fails at either level.** A rate fails
  iff the lower end of its 95% Wilson interval exceeds the level. The arms checked:
  - the stream, on all four null arms (N40, NV40, NA40, NAREV40);
  - the class, on N40 and NA40.
- **Otherwise recency reads use R15,** provided R15's stream fails on no null arm at either
  level.
- **If both fail, stop;** the author decides.
- **Power** is reported and does not enter the rule: paired differences W2 − unweighted,
  R15 − unweighted and W2 − R15 on E20, D20 and C20, at both levels. Each is a 95% paired
  bootstrap interval, B 10,000, seed 714999.

**Both branches for NA40 under W2:**
- **It does not fail:** the weighted draw corrects the null's long-run variance on this
  shift.
- **It fails:** reported with its rate, and the rule decides (R15, or stop).

**The reviewer's rough check, recorded as the reviewer's only.** It is not a registered result.
- Setup: iid, a fixed mean block of 8, B 300, 300 trials pooled, the 4% level.
- NA40 with a uniform draw 0.113; with a draw proportional to w² 0.073. Plain noise in the
  same setup: 0.067 and 0.057.
- Inconclusive at that n.

## 6. Detectability, and what the rule can do

**Each single check** (n = 1,000; the one-sided Wilson test), as in round 1:
- **Stream at 0.04:** the probability of failing is 0.026 at the level, 0.35 at 0.05, 0.84
  at 0.06 and 0.99 at 0.07.
- **Class at 0.01:** 0.026 at the level, and 0.78 at 0.02.

**The rule as a whole: 12 checks.** Four stream arms and two class arms, each at two
levels. Simulated (20,000 runs; the two levels nested within an arm):

| true size on every arm | P(the rule refuses W2) |
|---|---|
| exactly nominal | **0.25** |
| 1.10 × nominal | 0.69 |
| 1.15 × nominal | 0.87 |

- **So even a correctly sized W2 is refused about one time in four.** If W2 runs 10–15% over
  nominal on every arm, as round 1's fixed centring did on N20 (0.046 against 0.04), it is
  refused most of the time.
- **R15 then faces the same strictness** with 8 stream checks.
- [AUTHOR] This is the rule as written. If that refusal rate is more than intended, the
  options are a Bonferroni-adjusted Wilson end across the checks, or larger n per arm. Any
  change is registered by amendment before the run.

**Power differences, n = 400:** with about 30% discordant pairs, a difference of about 0.06
is detected with 80% power.

## 7. Cost (to be re-measured by the smoke)

Round 1 on the box: 5,200 tasks in 3,713 s on 180 workers. The class arms ran about 3× slower
per task than the laptop smoke, because every worker read the 2 GB pool at once. Scaled from
that:

| arm | panels | tests | core-seconds (box, estimated) |
|---|---|---|---|
| N40, NA40 | 2,000 | 4 stream, class under W2 | about 600,000 |
| NV40, NAREV40 | 2,000 | 4 stream | about 200,000 |
| E20, D20, C20 | 1,200 | 4 stream | about 60,000 |
| **total** | 5,200 | | **about 860,000** |

That is about 80 minutes of run on 180 workers. With setup, about 1.6–1.7 box-hours, roughly
$18–20, under the 2-hour limit but near it. The smoke re-measures it. If the projection passes
2 box-hours, the run stops and asks.

## 8. What this does not change

- The round-1 results stand as read.
- The statistic is unchanged: weights at position, the weighted Sharpe, h = 1,260.
- Only the null's draw and centring (W2), or the window (R15), are candidates.

## [AUTHOR] points

1. The first block's start drawn from q, so that the centring is exact at every position.
2. The rule's strictness: about a 25% refusal of a correctly sized W2 (section 6). Keep it,
   or amend before the run.
