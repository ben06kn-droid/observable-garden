# Agent cell on the ETF recent panel: do the gate's numbers describe what happened out of sample?

**Status: DRAFT, NOT LIVE (2026-10-11, America/Chicago).** For the author's review.
- **Nothing has run for it.** No session, no smoke, no precompute.
- The code is written after this draft is committed (Part 3 of the brief). The launcher refuses
  until this registration is live and the precompute manifest matches.
- No agent session is launched by the agent; the author launches every session, on the seat.
- Amendments are append-only and dated. The [AUTHOR] points are listed at the end.

**The parent panel:** `prereg/etf-recent-panel.md`, live at `310225c`, with amendment 1 (`80ec191`)
and amendment 2 (`850d59d`; design numbers at `d56d39e`).

## 1. The question

On recent real data, how well do the gate's search-adjusted numbers describe what happened out
of sample? They are compared with two things:
- the raw backtest (the in-sample Sharpe the agent saw);
- the agent's own stated expectation.

**Certificates are reported, but they are not the outcome of interest.** The outcome is the
closeness of each kind of number to the realised holdout result (section 8, R1–R2). There are
also in-sample reads of what the agent states (R3) and a money read (R4).

## 2. The panel

- **The amended ETF recent in-sample:** 38 ETFs (the cut at `ad233e7`). Rows are used from
  2010-01-04, with warm-up 253, timing d = 1 and the panel's costs. The scored window is earned
  dates **2015-01-02..2024-12-31**, 2,516 rows (amendment 2).
- **Masked:**
  - no tool shows an ETF name, a ticker, a calendar date or the number of ETFs;
  - features are shown as numbers 0–39 only, never by name (as 6.5: "No 6.5 agent was shown a
    feature name", `prereg/agent-on-real-data.md`);
  - periods, if any are shown, are indices.
- **No agent ever receives a 2025+ row, or any scripted result on this panel** (the panel's three
  tests, their verdicts or their L90s), except what section 4 gives arm B.
- **The holdout** is 2025-01-02..2026-10-09, 444 rows. It is graded once, on the host, after
  every session is committed (amendment 2, item 7).

## 3. The agent

- **Model:** `claude-sonnet-5`, thinking off, as `prereg/agent-on-real-data.md`
  (`experiments/agent_backend.py` asserts the model string).
- **Where:** on **the seat**, the subscription logged in on the laptop. Never EC2. **The
  author launches every session;** the agent writes the launcher and prints the command.
- **Budget:** at most 60 turns per session. A session that reaches 60 without submitting is
  recorded `no_submit`, counted, and reported in every read's denominator.

## 4. Moves, tools and arms

**The search:** the harness's typed search over feature rules.
- A rule is an equal-weight signed subset of up to 3 of the 40 features, a member of the
  declared class of 82,240.
- The moves are the grammar of the 6.5 grammar arms: `pick_prior`, `declare_triggers`,
  `change_trigger`, `init`, `extend_best`, `swap_worst`, `flip`, `refine`, `pick`, `stop`,
  `restart` (`quixote/agent_adapter.py`).
- Every move returns what it did, the support, its in-sample Sharpe, the best so far and the
  number of candidates seen.
- [AUTHOR] confirms the grammar, rather than 6.5's `evaluate`, so that the replay tier can
  apply (section 6).

**The Sancho tool, new:** `sancho()`.
- It returns Sancho's one stream for this panel: the panel's test-1 stream (d = 1, version 2 as
  confirmed at `97d2519`).
- It shows the stream's in-sample net Sharpe on the scored window and its mean daily turnover.
- **No settings are exposed and no arguments are taken.** It reads only the precomputed files
  (section 9).
- Each call is logged. Repeated calls return the same text.

**What a Sharpe means in a tool result** ([AUTHOR]):
- Proposed: both the unweighted net Sharpe and the W2-weighted net Sharpe over the scored
  window, as two labelled numbers: "Sharpe (all years equal)" and "Sharpe (recent years
  weighted)".
- The certificate is on the weighted one. 6.5 showed only the unweighted.

**The submission, one per session:** a rule (the best support reached) or Sancho's stream.
1. `submit_candidate(kind)`, where kind is "rule" or "sancho", names the candidate.
   - In **arm A** it returns the candidate's in-sample Sharpes.
   - In **arm B** it returns the same, plus one line: **"Gate's 90% lower bound (weighted) for
     this candidate: L90 = x."**
2. `predict(mean, sd, note)` states the expected out-of-sample annualised net Sharpe and its
   standard deviation: the stated distribution is Normal(mean, sd). A zero sd is a point
   forecast.
3. `confirm()` ends the session.

`predict` is required before `confirm`, and the candidate cannot change after
`submit_candidate`. Both arms take the same number of steps.

**The arms:**
- **A:** in-sample Sharpes only.
- **B:** the same, plus the gate's weighted L90 for the candidate about to be submitted.
- **40 sessions per arm,** 80 in all, interleaved by a fixed schedule.
- **The agents are not told there are arms.** The arm-B line appears only in arm B's
  `submit_candidate` result.
- The system prompts of A and B are **byte-identical**, as the 6.5 declared-class gate was to
  control.

**L90 for arm B** is a lookup:
- **for a rule:** S_w(rule) − q₀.₉₀(M_b), where M_b are the class's W2 null maxima on the scored
  window;
- **for Sancho's stream:** S_w − q₀.₉₀ of its own W2 null (supplied-streams tier).

  Both come from the precompute (section 9).

**Conflict, stated:** `AGENT_PROMPTS_REAL.md` §5 (6.5) says "No arm tells the agent its own
statistic's null distribution, a critical value, or a p-value." Arm B's L90 reveals S − L90, a
null quantile. **This cell registers arm B as an explicit exception to that rule,** for this
cell only. Arm A keeps the rule. No arm shows a p-value or a verdict.

## 5. What an agent never sees (leak tests, section 9)

Nothing an agent can call reveals:
- an ETF name or ticker, a calendar date, or the panel's size in ETFs;
- the arm;
- any scripted verdict, p-value or certificate: the panel's three tests or any session's;
- any row after 2024-12-31, and any value computed from one.

Feature names are never shown. These are tested on the tool layer's outputs, not only on the
prompts.

## 6. Pricing, from committed logs only

For each submission, the pricing script reads the committed session log and the pinned
precompute. Nothing is refitted.

| quantity | a rule | Sancho's stream |
|---|---|---|
| raw in-sample net Sharpe, weighted (W2) and unweighted | yes | yes |
| **the W2 certificate** at the panel's split | **class tier**: p = share of the class's W2 null maxima ≥ S_w; 96% iff p < 0.01 (90% iff p < 0.02, labelled) | **supplied-streams tier**: the stream's W2 null, the panel's test 1 (96% iff p < 0.03; 90% iff p < 0.06, labelled) |
| the weighted L90 | S_w − q₀.₉₀(class W2 maxima) | S_w − q₀.₉₀(stream W2 null) |
| the search-adjusted point estimate (below) | EB on the class | not defined (one stream) |
| the replay tier (6.5's trigger-replay) | where 6.5's condition holds (below) | no |

**The search-adjusted point estimate.** `prereg/point-estimate.md` was never live, and its text
says "No point estimate is registered". Its definitions are therefore registered here, as
descriptive, unweighted only:
- **EB** = S − mean_b[S*_b(m_b) − S(m_b)], where m_b is the class argmax on replicate b of the
  class's unweighted null (the panel's B = 5,000, seed 721002). The precompute stores m_b and
  S*_b(m_b).
- A W2 version is not defined there. [AUTHOR]: define one, or keep EB unweighted beside the
  weighted L90.
- **Display rule** (from point-estimate.md): never shown to an agent; in the reads, printed for
  every submission, labelled.

**The replay tier.** 6.5's condition, quoted: "the replay arm runs iff the declared class is
tabulated for this panel" (`prereg/agent-on-real-data.md`, lines 299–301).
- The class is tabulated for this panel by the precompute, so the condition holds for every
  rule submission.
- A session whose log shows a trigger change gets `DEPENDS_ON_JUDGMENT` and no certifying p, as
  registered. It does not fall through.
- **A session that called `sancho()` and then submitted a rule:** the rule's replay covers its
  logged grammar search only, and the Sancho call is outside it. Proposed: report the replay
  verdict with a flag, "a non-grammar look (Sancho) was taken" ([AUTHOR]).

**A Sancho submission chosen after a search** ([AUTHOR]).
- The supplied-streams tier treats Sancho's stream as if declared alone, but the agent chose it
  after seeing rule Sharpes.
- Proposed beside it, labelled "selection-aware, descriptive": the stream's p against the joint
  maximum of the class's W2 null maxima and the stream's W2 null, on shared index draws.
- Not a certificate.

## 7. Holdout grading (on the host, once, after all sessions are committed)

- **The grader takes the committed submission list.** That is a file of each session's
  submission: a rule's support, or "sancho". It is pinned by SHA-256 and written by the
  collector from committed logs. Nothing else is taken.
- **For each submission:** the realised unweighted net Sharpe and the net return over
  2025-01-02..2026-10-09, on one spanning panel (2010-01-04 to the last fetched session).
  - The positions are continuous across the boundary.
  - Sancho's stream continues causally, as in the B1 grading.
- **The same no-restart checks as the B1 grading** (`prereg/french-long-b1-grading.md`, sections
  3–4):
  - features and positions on in-sample rows bit-identical to an in-sample-only build;
  - the first holdout trade costed from the carried position;
  - no restart signature;
  - the in-sample Sharpes of the precompute reproduced to 3 decimals.
- **The same session grades the panel's three objects** (amendment 2, item 7), under the panel's
  own grading registration. That registration is written after BOX-ETF's read and before this
  grading.
- **Only `grades.json` returns.** No holdout row or position leaves the host.
- **The 2026-only realised value** (the panel's amendment answers, item 7) is printed beside,
  descriptive.

## 8. Reads, once, in this order

Every read reports the count of submissions in it (80 minus `no_submit`), and splits rules from
Sancho submissions where both occur.

- **R1, lower bounds:** the share of submissions with realised ≥ weighted L90, with the count.
  For both arms, and for each arm separately.
- **R2, closeness:**
  - the mean signed error and the mean absolute error of realised against:
    - (i) the raw in-sample Sharpe, weighted and unweighted;
    - (ii) the agent's stated mean;
    - (iii) the gate's point estimate (EB, rules only);
  - the CRPS of the agent's stated Normal(mean, sd) against the gate's predictive distribution,
    as in `prereg/agent-on-real-data.md` (lines 208–215, 254–259).
    - The gate's predictive distribution is F_b = S − M_b + SE_oos·Z_b, using the class maxima for
      a rule and the stream null for Sancho. SE_oos = sqrt((1 + S²/(2·252)) / 1.76). That is the corrected form: 6.5 wrote (1 + S²/2), which overstates the error at nonzero Sharpe (`b45f111`).
    - Proposed: the weighted version (S_w and the W2 maxima) as primary, since the bound graded is
      the weighted L90, and the unweighted (6.5's `sr_deflated`) beside ([AUTHOR]).
- **R3, in-sample only** (no holdout value):
  - the stated mean and the stated sd against the session's search length (moves, and candidates
    seen), by arm;
  - arm B against arm A: the difference in mean stated expectation, and in mean stated sd.
- **R4, money:**
  - the share of submissions with positive holdout net return;
  - the holdout net Sharpe of the equal-weight book of all submissions, and of each arm's book.

**Both branches, for R1, R2 and R3's B against A:**
- **R1.** Either "the share at or above L90 is consistent with a 90% bound (it is not below
  [the registered floor])", or "below it".
  - [AUTHOR] fixes the floor before the read. Proposed: the bound is "too high" iff the share's
    one-sided 95% upper end (joint bootstrap, section 9) is below 0.90.
- **R2.** The gate's point estimate is closer than the raw backtest (smaller MAE), or not closer.
  The agent's stated mean is closer than the raw backtest, or not. Each is stated with its
  bootstrap interval, and "not distinguished" when the interval covers 0.
- **R3 B against A.** Arm B's stated expectations are lower than A's (the interval excludes 0),
  or not distinguished.

## 9. Uncertainty

**Every submission shares one 444-row window, so they are not independent.**
- All intervals come from **one stationary bootstrap over holdout days**, applied jointly to
  every submission, with sessions held fixed.
  - B = 10,000.
  - The block length is the class rule on the holdout's demeaned base columns.
  - Seed 723000, from the block 723000–723099.
- R3 is in-sample. Its B-against-A interval resamples sessions within arm (B = 10,000, seed
  723001).

**What 444 rows can and cannot separate:**
- **One realised Sharpe** has an SE of about 0.75 (1.76 years).
- **R1:** submissions on overlapping rules are highly correlated, so the share at or above L90
  behaves more like a few draws than 80.
  - The bootstrap interval is reported. If submissions concentrate on a few candidates, R1 is
    nearly all-or-none.
  - **R1 cannot separate** "the bounds are right" from "the window was kind". It can flag bounds
    that miss by more than about one SE.
- **R2:**
  - The signed error of a predictor against realised equals realised minus the predictor. So the
    *difference* between two predictors' mean signed errors is fixed in-sample, and the holdout
    adds only the common level.
  - MAE and CRPS differences do depend on the window. They are distinguishable only when the
    predictors differ by more than a fraction of an SE.
  - A "closer" verdict on one 1.76-year window is evidence about that window, not a general
    claim.
- **R3:** with 40 sessions per arm, a difference of about 0.63 standard deviations of the stated
  expectation is detectable at 80% power (two-sided 5%). Its SD is unknown before the smoke, and
  the smoke reports it.
- **R4:** the equal-weight book's realised Sharpe has an SE of about 0.75, like any one stream.
  "Positive" is a coin flip at a true Sharpe of 0.
- **The second grading on 2028-01-03** (the parent's section g) repeats R1, R2 and R4 on about 752
  rows, with an SE of about 0.58. Its registration is written then.

## 10. Limits, stated beside every read

- **One window:** 444 rows, one market period.
- **One agent model.**
- **The ETFs were chosen in 2026, from survivors** (the parent's section a, item 4).
- **Costs are assumed:** 5 bps one-way, and 50 bps a year borrow.
- **2025 was inside a window opened once** for other strategies (the 6.5 grading).
- **The second grading is in 2028.**
- **The agent model may know these ETFs' history,** even masked. 6.5's recall note applies.
- **A rule search and a Sancho call** are not one declared search (section 6).

## 11. Seeds (checked 2026-10-11 with `seed_block_check`: NO COLLISION)

- **Session masters:** 20261011 (arm A) and 20261012 (arm B). Each draws 40 session seeds by
  `default_rng(master).integers(0, 2**31 - 1)`, the agent runners' construction.
- **The interleaving schedule:** fixed by session index, A then B alternately, written into the
  launcher before any session.
- **Joint holdout bootstrap:** 723000. **R3's session bootstrap:** 723001. Block 723000–723099.
- **The smoke** (five sessions, cost only): block 723100–723199. Master 723100 for its session
  seeds.

## 12. Precompute, code and order (Part 3 of the brief)

- **The precompute is produced by the BOX-ETF read itself and pinned** (proposed):
  - the runner also writes Sancho's d = 1 scored stream and turnover;
  - the class's scored net streams (82,240 × 2,516, about 1.7 GB);
  - every member's weighted and unweighted in-sample Sharpe;
  - the class's W2 null maxima, and the unweighted null maxima with their argmax m_b and S*_b(m_b);
  - the stream's W2 null;
  - all with a SHA-256 manifest.

  That needs a runner change before BOX-ETF (it adds outputs; it changes no statistic), and
  about 5–10 more box minutes and 2 GB of disk. The files come back to the laptop with the
  results.
- **Order:**
  1. this draft, reviewed;
  2. the runner change and BOX-ETF;
  3. this registration live;
  4. the code;
  5. the smoke;
  6. the 80 sessions;
  7. pricing;
  8. the panel's grading registration;
  9. one host grading session;
  10. the reads.

## [AUTHOR] points

1. The grammar search (6.5's grammar arms) rather than `evaluate`, so that the replay tier
   applies (section 4).
2. Tool results show both Sharpes, unweighted and W2-weighted, labelled (section 4).
3. The arm-B exception to 6.5's §5 "no critical value" rule (section 4).
4. EB unweighted only, or define a W2 point estimate (section 6).
5. The replay flag for a Sancho look before a rule submission (section 6).
6. The selection-aware line for a Sancho submission (section 6).
7. R2's CRPS: weighted primary with the unweighted beside (section 8).
8. R1's floor for "too high" (section 8).
9. The precompute made by BOX-ETF, which means a runner change before the box (section 12).
10. `no_submit` sessions: counted and reported, not replaced (section 3).
