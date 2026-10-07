# holdout-grading (6.9): grading 6.5's 80 submissions on the sealed ETF holdout

**DRAFT — committed, not live. Nothing runs on it, and nothing in it opens the holdout.**
It fixes the grading sequence and the readouts before anyone is in a position to vary
them after seeing a number. It goes live by a dated commit once the remaining build item
exists and passes its tests, and every `[GAP]` below is resolved.

**One opening only.** The holdout is made plaintext once and graded once, by the
sequence below, and the plaintext is deleted when grading ends. There is no second
opening. Any later grading (other code, costs or features) is a new registration,
reported beside the first and never in place of it, and it grades from the first
opening's committed grades file or not at all.

## Question

How do 6.5's submissions perform on the sealed 2023–2025 holdout, gross and net? Do the
gate's confidence readouts and the agents' own stated expectations bound or anticipate
what was realized?

**What this cannot test, stated plainly.** **No submission was certified in 6.5**: the
class tier issued 0 of 80, and the replay tier no PASS (`prereg/agent-on-real-data.md`).
**So 6.9 cannot test whether a pass holds out of sample.** The registered PASS-versus-FAIL
readout is reported as "no PASS". Everything below is about uncertified submissions:
- whether anything the gate refused would have earned out of sample;
- whether the gate's lower bounds and the agents' stated beliefs were consistent with
  what was realized.

## What is graded

**80 submissions**, one per run, 20 per arm:

| arm | run directory | logs / priced |
|---|---|---|
| control | `runs/etf_control` | `3f6c189` |
| declared-class gate | `runs/etf_declared_class` | `3f6c189` |
| replay gate | `runs/etf_replay` | `62644b8` / `43cd139` |
| orientation | `runs/etf_orientation` | `62644b8` / `43cd139` |

Three arms ran at 20 against a registered 40 (`agent-on-real-data.md`, deviation of
2026-10-02). There are 80 submissions, not 120.

**The registered 6.5 results are the B = 200 verdicts and class tier in those files.**
6.9's confidence readouts need confidence fields at B = 1,000, which 6.5 did not compute.
They come from a re-pricing (step 0) that writes **new records in a new location**, with
the B = 200 fields beside them marked as superseded. **The re-priced fields exist only to
supply the confidence readouts for 6.9.** They change no 6.5 result, and the source run
files are not touched (`experiments/price_runs.py --reprice-to`, `65b47ac`).

## The sequence — one direction of travel

Repository to holdout host: **one sealed submissions file and code at one commit**.
Holdout host to repository: **grades**. Nothing else crosses, in either direction, at
any step.

0. **Re-price the confidence fields, before S.** Run, for each of the four directories:
   `python -m experiments.price_runs --dir runs/etf_<arm> --B 1000 --reprice-to
   runs/etf_repriced_b1000/<arm>`. This writes the class tier at B = 1,000 with its
   confidence fields, and the replay-tier verdict at B = 1,000 for the 40 runs that
   carry one. The output is committed **before S**, so the bounds exist before the
   holdout opens. It is in-sample only: no holdout row is involved.
1. **Seal the submissions by commit, before the holdout is opened.**
   - `experiments/collect_submissions.py --dirs runs/etf_control runs/etf_declared_class
     runs/etf_replay runs/etf_orientation` writes the 80 `{name, weights}` objects, built
     with the gate's own `quixote.grammar.weights`.
   - The file is committed and pushed as commit **S**. Its SHA-256 and S are written
     into this file by a dated commit **before step 3**.
   - After S, no submission, run file, re-priced record or weight rule changes.
   - (The rehearsal's collection gave 80 submissions, sha256 `265dccca4577e340…`. That
     is not S. S is made at the live commit.)
2. **Fix the grading code by commit.** The grading code, the feature build and this file
   are at commit **G**, with S an ancestor of G. G is recorded here.
3. **The holdout is made plaintext on the holdout host — not by this sequence.** The
   operator does that by hand, once, as `agent-on-real-data.md` describes. **No step
   here decrypts anything.** `grade_real` has no decryption step and refuses `.enc`,
   `.gpg`, `.asc` and any `~/Desktop` path.
4. **The guards, in order** (`experiments/grade_real.py`, `run_grading`):
   - the **platform** must be the pinned one, Linux x86_64, the holdout host;
   - **HEAD must equal G** with a clean tracked tree;
   - **S must be an ancestor of HEAD**, and the **submissions file must hash** to the
     recorded SHA-256.

   Any refusal stops grading.
5. **Content-hash check.** Before any price is read, every in-sample and every holdout
   CSV must hash to its entry in the single fetch's manifest (`data/etf_manifest.json`,
   `derived[ticker]["insample" | "holdout"]`), with none missing or extra. Any mismatch
   refuses, and nothing is graded.
6. **Features built once, on one pinned platform, over in-sample and holdout together.**
   - `grade_real.build_span` is `environments.real_panel.build_etf_panel`'s computation
     over the concatenated 2005–2025 series. The tests (`tests/test_grade_real.py`)
     check it equals that computation exactly.
   - The build's platform and its feature matrix's SHA-256 are written beside the
     grades.
   - **Ties:** on arm64 the build equals the pinned X exactly (the rehearsal, `0bb1251`).
     On the x86 holdout host, `ret1_rank` and `drawdown_rank` break exact ties
     differently from the arm64 build the agents searched. **Control run 8 is the only
     submission containing either**, and its grade carries that note.
7. **Grade.** The graded periods are those whose **earned return** is dated 2023-01-01
   to 2025-12-31.
   - Registered execution: signal at the close of t, held from the close of t+1 to
     t+2.
   - The book is continuous across the boundary: the first graded period's turnover is
     measured from the position actually held.
   - Each submission's holdout Sharpe is reported gross, and net at **5 and 10 bps**
     one-way plus 50 bps a year borrow.
   - Over the in-sample window the same code reproduces the class table's streams
     (tests) and the agents' own in-sample scores (rehearsal: 40 compared, max |diff|
     1.7e-16).
8. **Grades travel back, and are committed unread.**
   - The grades file holds the per-submission gross and net Sharpe, number of periods,
     platform, feature-matrix SHA-256, S and G. `grade_real` prints no Sharpe.
   - It is copied to the repository and committed **unread** as commit **R**.
   - The read is a separate step, by a reader committed and tested on synthetic files
     before R exists.
9. **The plaintext is deleted** when grading ends. Stopping the holdout host is the
   operator's action after R is pushed; no command here issues it.

## The readouts, in the order the reader prints them

All are read once from R and the step-0 records, by the reader.
- **The realized holdout Sharpe** of a submission is its grade, net at 5 bps, unless
  stated.
- **"One future."** All 80 submissions are graded on the same three years. Every
  readout across runs therefore shares one realization of the market. A Wilson interval
  or t interval over runs treats the runs as independent, and **overstates the
  precision for any claim beyond this one holdout.** Each readout is read as a statement
  about this holdout, not about futures.

**(1) Registered by 6.5** (`agent-on-real-data.md`, "Out-of-sample readouts"):
- **PASS against FAIL:** "no PASS".
- **The FAIL side on its own:** the median holdout Sharpe, gross and net at 5 and
  10 bps, with a bootstrap interval over runs, per arm and pooled.
- **`sr_deflated` coverage per run:** whether each run's realized holdout Sharpe falls
  inside its 95% predictive interval, pooled over runs.
  - The point, `S - mean(M_b)`, is exact from the stored `null_max_mean`.
  - The interval needs the M_b draws, which no record stores. It is **approximated
    from the step-0 confidence curve** (the class null's survival on the 81-point
    grid), with replicates placed at grid midpoints, and **labelled an approximation**.

**(2) H1 — the gate's lower bounds against realized (one rule).** The class tier's
`L_0.90` from step 0 (B = 1,000) is a 90% lower confidence bound on the submission's
population Sharpe under stationarity (`quixote/confidence.py`). **Coverage** is the share
of the 80 submissions whose realized holdout Sharpe is at least its `L_0.90`.
- **The rule fails low iff the upper end of the Wilson 95% interval of the coverage is
  below `[GAP: 0.80. Proposed: 0.90 less an allowance of 0.10 for the holdout's own
  sampling error, which the bound does not contain]`.** With a per-run holdout SE of
  0.58 at a true Sharpe of 0, a realization can fall below a valid bound on the
  population Sharpe. The allowance keeps the rule from failing on that noise alone.
- **Holds:** the bounds were not shown to be too high out of sample on this holdout.
  Reported with the coverage and its interval, V2's synthetic coverage beside it, and
  the label "one future".
- **Fails low:** the bounds overstate what was realized on this holdout. Reported with
  the direction, and with the gross-against-net gap (costs) and the coverage at the
  gross figure. Regime change and costs are named as the candidate causes, as 6.5
  predicted ("under-coverage is expected").
- **Also reported, no rule:**
  - coverage of `L_0.95` and `L_0.99`;
  - the replay tier's `L_g` for the 40 runs that carry a replay verdict;
  - coverage at gross and at 10 bps.

**(3) H2 — the agents' stated expectations against realized (one rule).** Each run's
`predict` gives a mean mu (and sd); 79 of the 80 runs carry one. For each, `d = mu -
realized`.
- **The rule fails high iff the lower end of the one-sided 95% t interval for mean(d)
  exceeds `[GAP: 0. Proposed 0]`.** That is, the agents' stated expectations
  demonstrably overstate the realized holdout Sharpe.
- **Fails high (predicted):** the agents overstated. 6.5 measured stated means above
  the deflated figure (+0.53), and 7.5 found positive gaps at level 0. Reported with
  the mean, its interval and the per-arm means.
- **Holds:** not shown to overstate on this holdout. Reported likewise, with "one
  future".
- **Also reported, no rule:**
  - the CRPS of the agent's normal(mu, sd) against realized, beside the CRPS of the
    gate's class-tier confidence curve read as a distribution and of `sr_deflated`'s
    predictive distribution (6.5's check 3). A zero sd is scored as a point forecast.
  - mu against `L_0.90` and against `S - mean(M_b)`, per run.

**(4) Descriptive, no rule:**
- the stored `C0` and `P_5` against realized holdout Sharpe > 0 (Brier score).
  **`P_5` is shown beside certified verdicts only, and none here is certified**, so
  this is the stored field read for calibration, labelled as such. V3 found it
  overstates where there is no edge.
- per-arm medians;
- control run 8's tie note.

## Detectability at n = 80

**H1.** At n = 80 the Wilson upper end falls below 0.80 only at **56 or fewer covered
(0.700)**. So the rule detects a true coverage of roughly 0.70 or lower, and nothing
finer. With the one-future dependence, the effective n is smaller, so even that is
optimistic.

**H2.** The smallest mean overstatement detectable (one-sided 0.05, 80%) is
`2.486 sd / sqrt(80)`:
- sd of d at 0.30: **0.083**;
- sd 0.45: **0.125**;
- sd 0.58: **0.161**.

The last is the per-run holdout SE at a true Sharpe of 0; the stated means' own sd is
0.177. A common shock to the holdout shifts every d alike and is not averaged away by n,
so H2 cannot separate "the agents overstate" from "this holdout was a bad draw for
everything". That is reported with the result.

## Build items, before the live commit

1. `grade_real`: refuse unless HEAD equals the recorded G and the tracked tree is clean.
   **Done** (`e276871`).
2. `grade_real`: the content-hash check against `data/etf_manifest.json`, and the
   submissions hash. **Done** (`e276871`).
3. `grade_real`: one feature build over in-sample and holdout; the earned-return window
   2023-01-01 to 2025-12-31; platform and matrix SHA-256 beside the grades; 5 and
   10 bps. **Done** (`e276871`, `run_grading` `1804e3b`). Rehearsed on an in-sample
   split (`0bb1251`).
4. The re-price mode for step 0. **Done** (`65b47ac`), tested on a synthetic run. Not
   yet run on the 80 runs.
5. **Open:** the reader, committed and tested on synthetic grades and re-priced records
   before R. It prints (1)–(4) in order.

## Cost

- **Step 0, the re-pricing:**
  - *Laptop:* one worker, because the ETF class table is about 2.8 GB. About **1.5–2
    hours**.
  - *Box:* the c7a.48xlarge, one worker per run. About **5 minutes** of compute after
    about 10 minutes of boot and pull, **about $2–3**.
  - The figures are scaled from the measured planted pricing: class table 176 s, class
    tier 17 s at B = 1,000, and replay verdict 86 s on the laptop. They are scaled by
    the ETF panel's longer T (4,276 against 3,019 days). The class table is built once
    per worker and reused.
- **Grading:** minutes on the holdout host (c7a.8xlarge `i-0886a189b85d4d051`): one
  feature build and 80 gradings.
- No seat cost.
