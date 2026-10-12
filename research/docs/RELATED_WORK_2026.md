# Related work, literature search of 2026-09-30

Every reference below was **opened before being cited**, and its read-level is
recorded. Where a URL returned an error, that is said instead of being hidden.
Categories are `concurrent-independent`, `design-alternative`,
`objection-to-address`, `ancestor`.

**How dates are used here.** This repository's documentary record begins with
commit `ed14594`, **2026-09-14**. Where an outside work reaches a shared premise
**before** that date, it is recorded as an earlier published statement of the
premise, in neutral wording, and **no finding in this project is described as
derived from, following, or building on it**. Where this project's record is
earlier, the outside work is `concurrent-independent`. Git records when a finding
was **committed**, not when it was made; no claim is made here about work
predating the repository.

---

## Earlier published statements of a shared premise

**Gençay, E. (2026).** *What survives honest evaluation? Leakage-safe,
search-aware assessment of LLM-driven trading strategy discovery.*
arXiv:2608.27734, submitted 27 August 2026.
<https://arxiv.org/abs/2608.27734>
**Read-level:** abstract and listing metadata read 2026-09-30; full text not
opened.
**Summary:** An LLM agent is restricted to validated tools that structurally
exclude look-ahead bias, and its reported performance is deflated by the system's
own search volume; across 453 stocks and 39 ETFs the framework certifies passive
benchmarks and rejects every LLM-discovered strategy.
**Difference:** It applies closed-form Deflated Sharpe and PBO to a completed
trial ledger; it has no correction for candidates chosen adaptively from earlier
results, no replay of a logged search inside a null, and no record hierarchy.
**Category:** `ancestor`

**Kinlay, J. (2026a).** *A Sharpe of 2.1 From Nothing: The Second Number Your
Agent Doesn't Log.* Blog post, 2 September 2026.
<https://jonathankinlay.com/2026/09/a-sharpe-of-2-1-from-nothing-the-second-number-your-agent-doesnt-log/>
Companion repository: <https://github.com/jkinlay/agent-selection-surface>
**Read-level:** post read in full 2026-09-30; repository landing page read; code
not run.
**Summary:** An LLM agent reported an in-sample Sharpe of 2.12 on synthetic
panels built to contain no predictability, and blind top-*k*-of-*N* selection at
each run's own logged trial count and leg count accounts for 88% of it.
**Difference:** It measures the size of the effect and names the two integers that
drive it; it does not ask whether the logged candidate set is sufficient when the
search is adaptive, which is this project's subject.
**Category:** `ancestor`

**The neutral statement, as it appears in `README.md`:** Gençay (2026) and Kinlay
(2026a) published the observation that an agent's trial count is observable by
construction before this project's first record; this project reached it
independently. Neither addresses whether the logged candidate set suffices when the
search is adaptive, which is the subject here.

---

## Concurrent, independent work

**Kinlay, J. (2026b).** *The Holdout That Made the Sharpe Bigger.* Blog post,
22 September 2026.
<https://jonathankinlay.com/2026/09/the-holdout-that-made-the-sharpe-bigger/>
Companion repository: <https://github.com/jkinlay/research-controls>
**Read-level:** post read in full 2026-09-30; repository landing page read; code
not run.
**Summary:** On null panels a reused validation holdout *inflates* the reported
Sharpe by about 74%; Romano–Wolf rejects on 12 of 60 empty panels when pointed at
the family the search produced and on none when the family is fixed in advance;
and feeding the Deflated Sharpe an effective trial count of 13 in place of 193
logged candidates takes it from 0 rejections to 9 of 60.
**Difference:** Empirical only — no sign or size theory, no replay, and no
mechanism for the effective-*N* error; this project's double-counting result
derives that error from `Var[SR_n]` in the closed-form baseline.
**This project's first records, both earlier:** the effective-*N* double-counting
result at `3446f10`, **2026-09-14** (`SCOPE.md`); the distinction between a family
fixed in advance and the search's own trace at `309332d` and `34934a1`,
**2026-09-15** (`THEORY.md`, P1/P3).
**Category:** `concurrent-independent`

---

## Design alternative

**Qu, B., Chen, M. & Wang, L. (2026).** *Propose, Don't Judge: An Anytime-Valid
Referee for LLM Agents That Mine Investment Factors.* arXiv:2609.27051, submitted
22 September 2026. <https://arxiv.org/abs/2609.27051>
**Read-level:** abstract and listing metadata read 2026-09-30; full text not
opened.
**Summary:** A frozen statistical referee scores each agent-proposed factor only
on outcomes revealed after submission, using online e-BH and e-processes, and
admits 5–11 times fewer sub-threshold factors than leaky referees.
**Difference:** Validity is bought with **waiting time** — roughly 500 trading
days to admission — whereas Quixote certifies on the in-sample data already in
hand and pays instead in the strength of what it can claim.
**Category:** `design-alternative`

---

## Objection to address

**Gonuguntla, A. (2026).** *The Replay Gap: Static Evaluation of Model Switching
in LLM Agents Scores the Wrong World.* arXiv:2608.08239, submitted 8 August 2026;
accepted at the Conference on Language Modeling 2026.
<https://arxiv.org/abs/2608.08239>
**Read-level:** abstract and listing metadata read 2026-09-30; full text not
opened.
**Summary:** Substituting one model's outputs into a logged agent trajectory
assumes downstream actions are unaffected, and they are not: 74–77% of early model
swaps diverge at the first post-fork action, leaving only 3% of replayed states
valid, so replay mispredicts every success-relevant outcome call.
**Difference:** The objection is correct about what it examines and does not reach
Quixote, because **Quixote never replays the LLM** — it replays harness-executed
typed moves and declared triggers, prices undeclared judgment at the maximum over
alternatives, and covers the model itself with twins. That is what the grammar is
for.
**Category:** `objection-to-address`

---

## Ancestors and neighbours

Nothing in this section overlaps a finding of this project.

**Rewolinski, Z.T., Zane, A.V., Huang, H., Singh, C., Wang, C., Gao, J. & Yu, B.
(2026).** *Sanity Checks for Agentic Data Science.* arXiv:2604.11003, submitted
13 April 2026. <https://arxiv.org/abs/2604.11003>
**Read-level:** abstract and listing metadata read 2026-09-30; full text not
opened.
**Summary:** Agentic data-science pipelines are re-run under reasonable
perturbations of the data to screen whether the agent can distinguish signal from
noise, and self-reported confidence turns out to be poorly calibrated to the
empirical stability of the conclusions.
**Difference:** Its hypothesis concerns **stability** under perturbation; this
project's concerns **trial count** and the sufficiency of a logged candidate set,
and the two are different quantities.
**Category:** `ancestor`

**Miao, J., Pritchard, J.K. & Zou, J. (2026).** *The Agentic Garden of Forking
Paths.* arXiv:2607.01507, submitted 1 July 2026.
<https://arxiv.org/abs/2607.01507>
**Read-level:** abstract and listing metadata read 2026-09-30 (read-level updated
by this search); full text not opened.
**Summary:** Agents sample plausible analysis paths and the resulting m-value is
the probability that a path would produce a claim at least as extreme as the one
reported.
**Difference:** It builds a reference distribution over paths and runs no
data-snooping test, and it does not analyse the order in which specifications are
tried.
**Category:** `ancestor`

**Bertran, M., Roth, A. & Wu, Z.S. (2026).** *What Fits (Into Few Tokens) Doesn't
Overfit: Compression and Generalization in ML Research Agents.* arXiv:2606.11045,
submitted 9 June 2026. <https://arxiv.org/abs/2606.11045>
**Read-level:** abstract and listing metadata read 2026-09-30; full text not
opened.
**Summary:** Two information bottlenecks — output compression via a reproducer
agent and one-bit input feedback — barely change performance across eight
datasets, supporting a description-length account of why benchmark reuse overfits
less than expected.
**Difference:** It explains why adaptive reuse often fails to overfit; this
project prices a search that did.
**Category:** `ancestor`

**Bertran, M., Fogliato, R. & Wu, Z.S. (2026).** *Many AI analysts, one dataset:
navigating the agentic data science multiverse.* *PNAS* 123(29), e2606495123,
21 July 2026. <https://www.pnas.org/doi/10.1073/pnas.2606495123>
**Read-level:** the publisher landing page returned **HTTP 403** on 2026-09-30;
title, authors, volume, issue, article number and date confirmed from the PNAS
table of contents for 123(29) and the PubMed record (PMID 42446982). Full text not
opened — cite only for what that metadata supports.
**Summary:** Autonomous LLM analysts, each running a full pipeline on one fixed
dataset and hypothesis under an AI auditor, reproduce the analytic dispersion seen
in human many-analyst studies and reach divergent verdicts from identical data.
**Difference:** It measures dispersion across independent analysts; this project
prices one analyst's adaptive search.
**Category:** `ancestor`

**Markovic, J., Taylor, J. & Taylor, J. (2019).** *Inference after black box
selection.* arXiv:1901.09973, submitted 28 January 2019.
<https://arxiv.org/abs/1901.09973>
**Read-level:** abstract and listing metadata read 2026-09-30; full text not
opened.
**Summary:** Given in-silico access to a selection algorithm, post-selection
inference is recast as a binary-regression learning problem and applied to
stability selection and cross-validation.
**Difference:** Selective and all-or-nothing — it conditions on the selection
event for a chosen parameter, where this project prices the maximum over a
declared class.
**Category:** `ancestor`

**Nair, Y. & Janson, L. (2023).** *Randomization Tests for Adaptively Collected
Data.* arXiv:2301.05365, submitted 13 January 2023 (revised 19 March 2023).
<https://arxiv.org/abs/2301.05365>
**Read-level:** abstract and listing metadata read 2026-09-30; full text not
opened.
**Summary:** A weighted randomization test restores exact finite-sample validity
for data collected adaptively by bandit, reinforcement-learning and adaptive-design
policies, despite non-exchangeability.
**Difference:** The **closest statistical ancestor** of replaying a known policy
on resampled data — but there the policy governs **data collection**, and here it
governs **selection** among specifications on data already in hand.
**Category:** `ancestor`

**Banerjee, S. (2026).** *A Leakage Bound for Confidence Sets after Black-Box
Selection.* arXiv:2604.26706, submitted 29 April 2026.
<https://arxiv.org/abs/2604.26706>
**Read-level:** abstract and listing metadata read 2026-09-30; full text not
opened.
**Summary:** Selected-target non-coverage is bounded by the nominal fixed-target
non-coverage plus the average total-variation distance between marginal and
conditional laws, recovering sample splitting as the zero-leakage case.
**Difference:** It bounds the cost of selection in information-theoretic terms
without executing the selection; this project executes it.
**Category:** `ancestor`

**Hoover, K.D. & Perez, S.J. (1999).** *Data mining reconsidered: encompassing and
the general-to-specific approach to specification search.* *Econometrics Journal*
2(2), 167–191.
<https://public.econ.duke.edu/~kdh9/Source%20Materials/Research/3.%20Data%20Mining%20Reconsidered.pdf>
**Read-level:** title, authors, journal, volume, issue, pages and abstract
confirmed 2026-09-30 via the publisher listing and the author's own copy; full
text not opened.
**Summary:** A mechanical algorithm mimicking LSE general-to-specific search is
run over 1,000 replications of nine regression models on Lovell's data-mining
design, and the approach comes out largely favourably.
**Difference:** An executable search procedure studied by simulation, with no
multiple-testing correction attached to its output.
**Category:** `ancestor`

**Mundry, R. & Nunn, C.L. (2009).** *Stepwise model fitting and statistical
inference: turning noise into signal pollution.* *American Naturalist* 173(1),
119–123.
<https://dash.harvard.edu/bitstream/1/5344225/1/Mundry%20and%20Nunn.pdf>
**Read-level:** title, authors, journal, volume, issue and pages confirmed
2026-09-30 via the repository copy; full text not opened. **The title was absent
from the brief this search worked from and is supplied here.**
**Summary:** Stepwise model fitting performs many implicit hypothesis tests and so
inflates type-I error, turning noise into apparent signal.
**Difference:** It names the failure for stepwise regression and recommends
avoiding the procedure; it does not price a search that was run.
**Category:** `ancestor`

**Simonsohn, U., Simmons, J.P. & Nelson, L.D. (2020).** *Specification curve
analysis.* *Nature Human Behaviour* 4, 1208–1214,
doi:10.1038/s41562-020-0912-z. <https://www.nature.com/articles/s41562-020-0912-z>
**Read-level:** title, authors, journal, volume, pages, DOI and abstract confirmed
2026-09-30 via the publisher page; full text not opened. A publisher correction
exists at doi:10.1038/s41562-020-00974-w.
**Summary:** All defensible specifications are enumerated and reported as a curve,
with joint inference over the whole set.
**Difference:** The specification set is enumerated by the analyst in advance;
this project's is reached adaptively, and the order of evaluation is what it
prices.
**Category:** `ancestor`

---

## Citation-hygiene closure

**Liu, J., Qu, W., Gaboardi, M., Garg, D. & Ullman, J. (2024).** *Program analysis
for adaptive data analysis.* *Proceedings of the ACM on Programming Languages*
8(PLDI), Article 184. arXiv:2608.19575. <https://arxiv.org/abs/2608.19575>
**Read-level:** **verified 2026-09-30.** The arXiv record resolves, and its
journal reference confirms PACMPL, PLDI 2024, Article 184 (June 2024); the 2608
identifier is a 2026 posting of the 2024 paper, which is why the pairing looked
wrong. Abstract read; full text not opened.
**Status:** previously listed without a resolving identifier; now resolved.

---

## What this search did not find

No prior replay of an adaptive search's logged decisions inside a data-snooping
null, and no mixed replay/max-over-alternatives pricing. **Not a proof of
absence.**
