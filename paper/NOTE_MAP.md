# A reader's map from the note to the repository

The note is `docs/note.md`, *Fixed and adaptive candidate sets under the DSR*.
Each row is one claim in the note, in the note's order (Sections 3 to 6, then the
closing).

**Commits:**
- **Registration** is the commit at which the experiment was pre-registered (or went
  live).
- **Result** is the commit that added its output.
- **Read** is where a separate read commit exists.

The scripted experiments of Sections 3 to 5 record their outputs as
`figures/<name>_data.pkl`, with the numbers stated in `SCOPE.md` by section name. A
pre-registration that has closed is no longer in `prereg/`. It is recovered with `git show
<registration commit>:prereg/<file>`, as `EXPERIMENTS.md` explains.

**Limit values are computed two ways:** by Monte Carlo in `experiments/limit_model.py`
(2 million draws per cell), and by quadrature of the note's Section 5 integral in
`experiments/size_integral.py`. The two agree to 0.001; the largest difference is
0.0009, at ω = 0, K = 80.

**Run times:** "not recorded" means the run did not write its own timing. No figure is
estimated here.

## Numbering: the note against THEORY.md

| note | THEORY.md |
|---|---|
| Proposition 1 (§3) | P1. Fixed menus are valid (known) |
| Proposition 2 (§3) | P2. Sub-maximal selection is conservative (known) |
| Lemma and Direction (§4) | P4. Winner anchoring is anti-conservative; loser anchoring is conservative |
| The rank mixture (§4) | P4′. The realized-menu null is a uniform mixture over anchor ranks |
| Consequences 1 and 2 (§4) | P4′, Corollaries 4.1 and 4.2 |
| Size: the error-rate formula (§5) | P4, "Breadth": the closed form 1 − F_P(F_C⁻¹(1 − α)) and its table |
| Second level of record: a class declared in advance (§6) | P3. The full-class bound |
| Greedy search reaching only part of the class (§6) | P5. Greedy search and the lattice optimum |
| The process bootstrap's partial justification (§7) | P6. When is the recursive bootstrap consistent? |

## Claims

| # | claim, in one plain sentence | note | THEORY.md | experiment | registration | output; result or read | script; run time |
|---|---|---|---|---|---|---|---|
| 1 | If the candidate list ignores the returns, the realized-set test has the correct error rate. | §3, Prop. 1 | P1 | `oblivious-calibration` (E21) | `prereg/E21.md` at `82bea64` | `figures/oblivious_calibration_data.pkl`; result `b3ce0d5` | `experiments/oblivious_calibration.py`; not recorded |
| 2 | A search that reports no more than the maximum of a validly-nulled set keeps the test valid, at a cost in power. | §3, Prop. 2 | P2 | none needed (known) | — | — | — |
| 3 | A greedy rule on a list written in advance shows no excess; the same rule generating its own candidates does. | §3 | P1 | `lattice-control` (e2) | not registered | no file under `figures/`; the result is in `SCOPE.md` (null calibration and the mechanism) | `experiments/lattice_control.py`; not recorded |
| 4 | The best pair containing any fixed feature lies between the best pair with the loser and the best pair with the winner. | §4, Lemma | P4 | `pointwise-dominance` (E16) | `prereg/E16.md` at `c8c5d60` | `figures/pointwise_dominance_data.pkl`; result `714ee26` | `experiments/pointwise_dominance.py`; not recorded |
| 5 | Winner-anchoring makes the realized-set test too lenient, and loser-anchoring too strict. | §4, Direction | P4 | `anchor-coupling` (e15); `pointwise-dominance` (E16) | e15 pre-registered at `675278d`; E16 at `c8c5d60` | `figures/anchor_coupling_data.pkl`, result `66eb7ca`; E16 as row 4 | `experiments/anchor_coupling.py`, `experiments/pointwise_dominance.py`; not recorded |
| 6 | The realized-set null is the average of the K rank-anchored process nulls. | §4, rank mixture | P4′ | limit model (Corollary 4.1: 5.00% ± 0.02 at K = 20, ω = 0.3); `graded-coupling` at τ = 0 | E17 at `254cdda` | `figures/graded_coupling_data.pkl`; result `be3c0df` | `experiments/limit_model.py`; `experiments/size_integral.py` checks P4′ (tests); `experiments/graded_coupling.py`; not recorded |
| 7 | A uniformly random anchor is exactly calibrated, and anchoring moves error between ranks rather than creating it. | §4, consequences 1–2 | P4′, Cor. 4.1–4.2 | as row 6; `anchor-rank` (E17b) | E17b at `db6b64e` | `figures/anchor_rank_data.pkl`; result `6c076d1` | `experiments/anchor_rank.py`; not recorded |
| 8 | The winner-anchored test rejects too often, the random and worst anchors do not, and the process bootstrap restores nominal. | §4, Evidence 1 | P4 | `anchor-coupling` (e15) | `675278d` | as row 5 | as row 5 |
| 9 | The error rises steadily as the anchor draw leans from worst to best, crossing nominal at the uniform draw. | §4, Evidence 2 | P4 | `graded-coupling` (E17) | `254cdda` | result `be3c0df` (trend p = 0.0001) | `experiments/graded_coupling.py`; not recorded |
| 10 | With the anchor's rank fixed, the measured rates match the limit values computed in advance. | §4, Evidence 3 | P4, P4′ | `anchor-rank` (E17b) | `db6b64e` | result `6c076d1` | `experiments/anchor_rank.py`; not recorded |
| 11 | With finite samples and unequal correlations, the predicted ordering held on almost every reshuffle. | §4, Evidence 4 | P4 | `pointwise-dominance` (E16; 99.9% of replicates); `unequal-correlation` (E19) | E16 `c8c5d60`; E19 `8f4acb5` | E19 `figures/unequal_correlation_data.pkl`, result `2e4417d` | `experiments/unequal_correlation.py`; not recorded |
| 12 | For crossover rules the asymmetry appears, but the error is small, and no size is claimed. | §4, Evidence 5 | P4 (outside additive scoring) | `non-additive-scoring` (E20) | `prereg/E20.md` at `f298103` | `figures/non_additive_scoring_data.pkl`; result `4e32903` | `experiments/non_additive_scoring.py`; not recorded |
| 13 | The limiting error rate is 1 − F_P(F_C⁻¹(1 − α)), and for the two-stage winner-anchored search F_P is the stated integral. | §5 | P4, Breadth | limit model | — | THEORY.md's breadth table | `experiments/limit_model.py` (Monte Carlo) and `experiments/size_integral.py` (quadrature, under 1 s); they agree to 0.001 |
| 14 | More features, more error: with 80 uncorrelated features about a third of null searches pass a 5% test. | §5 | P4, Breadth | `feature-count` (E19c) | `prereg/E19c.md` at `21dbbc1` | `figures/feature_count_data.pkl`; result `daf470c` (10.0% to 36.2%, K = 10 to 80) | `experiments/feature_count.py`; not recorded |
| 15 | Correlation among features limits this error rather than causing it. | §5 | P4, Breadth | `feature-count` (E19c), the ω = 0.3 cells | as row 14 | as row 14 | as row 14 |
| 16 | A third round, building triples around the winning pair, raises the error further. | §5 | P4 (depth 3) | `search-depth` (E18) | `3a2c335` | `figures/search_depth_data.pkl`; result `c21fe86` (winner 10.4%) | `experiments/search_depth.py`; not recorded |
| 17 | A random round-2 anchor with round-3 re-anchoring gave an excess too small to detect. | §5 | P4 (depth 3) | `search-depth` (E18) | as row 16 | as row 16 (5.3%; detectable about 6.9%) | as row 16 |
| 18 | Testing against a class declared in advance is valid for any search inside it, at a cost in power. | §6, second level | P3 (with P1, P2) | `calibration-at-1pct` (6.1), arm D | `e9ad319`; closed `406018f` | `figures/calibration_at_1pct_armD.txt`; result `18e7e6e` (9.60 / 5.50 / 0.95% at 10 / 5 / 1%) | `experiments/calibration_at_1pct.py`; arm D 41.95 CPU-hours over 2,000 draws (its own record) |
| 19 | A greedy search inside the class is tested well below nominal, because it is charged for the whole class. | §6, second level | P3, P5 | `calibration-at-1pct` arm B; `gate-comparison` | `e9ad319`; gate-comparison live `e224f8b`, closed `b42eefb` | `figures/calibration_at_1pct_armB.txt`; `figures/gate_comparison_read.txt` | `experiments/calibration_at_1pct.py`, `experiments/gate_comparison.py`; arm B 221.85 CPU-hours over 5,000 draws; gate-comparison 3.71 h wall per cell at 192 workers (their own records) |
| 20 | Re-running logged typed moves reproduces the search exactly, and a log that fails replay is refused. | §6, third level | — (the harness) | `fixed-sequence-replay` (7.1) | `96b48dc` | `figures/fixed_sequence_replay_rules.txt`; read `9a68c25` | `experiments/fixed_sequence_replay.py`; projected 1,596 CPU-hours at B = 10,000 (its cost file) |
| 21 | Freezing stopping decisions repeats the realized-set error in time, and declared, re-checked stopping rules bring the rate back to nominal or below. | §6, stopping | P2 (below nominal) | `fixed-sequence-replay` (7.1); `unfaithful-searchers` (7.3, the faithful pair) | 7.1 `96b48dc`; 7.3 `359df62` | 7.1 read `9a68c25`; 7.3 read `37abeb2`, closed `17313a0` | `experiments/fixed_sequence_replay.py`, `experiments/unfaithful_searchers.py`; 7.3 cost $9.28 on a c7a.48xlarge |
| 22 | With a planted edge on real ETF features, no validity test failed, passes outperformed fails on held-back data, and the lower bounds covered. | §6, beyond the null | P3 | `planted-edge` (7.5), stage 1; `confidence-output` V2 | 7.5 live `bb0dcc4`; V2 live `697bef8` | 7.5 results `30ee870`, read `8660508`; V2 results `0edab26`, read `afdcb53` | `experiments/planted_edge.py`; about 3 h 37 min on a c7a.48xlarge (7.5); about 1 h 26 min (V2) |
| 23 | Language-model agents usually earned a pass where a planted edge existed and never where none did. | §8 | — | `planted-edge` (7.5), stage 2 | live `067371d` | results `06a5284`, read `b45dba5` | `experiments/planted_agent.py`; seat $28.61, pricing 13 min |
| 24 | On a panel of real ETFs, no submission passed. | §8 | — | `agent-on-real-data` (6.5) and its holdout grading | grading live `3a5483e` | grades `e4bc84b`, read `0426352` (`runs/holdout_grading/read.txt`) | `experiments/grade_real.py`, `experiments/holdout_grading_read.py`; not recorded |
| 25 | ridge_stack, one strategy declared in advance, kept the nominal error rate and passed planted non-linear edges far more often than the class. | §8 | P3 (a class of one) | `ml-ridge-stack-confirmation` | live `77f3ee1` | raw `06358c8`, read `d746a78` (`runs/ml_confirm/ridge_stack/read.txt`) | `experiments/ml_confirm_ridge_stack.py`; 1,116 s on a c7a.48xlarge (run record) |
| 26 | On one real panel of industry portfolios, ridge_stack has not yet produced a pass. | §8 | — | `french-panel`, in-sample read | live `de9da1b` | raw `31622d6`, read `fc92cdb` (`runs/french_insample/2026-10-07/read.txt`) | `experiments/french_insample_read.py`; 1 min 37 s on the laptop (run record) |
| 27 | The limit values come from two scripts, and each measured value from a named experiment; those of Sections 4 to 6 were pre-registered. | §8, reproduction | all | — | the ledger, `EXPERIMENTS.md` | — | `experiments/limit_model.py`, `experiments/size_integral.py` |

Rows 3, 19 and 24 point to experiments whose outputs are spread over several files. The
ledger rows in `EXPERIMENTS.md` give the full commit lists.

Sections 2 (Setup) and 7 (Limitations) of the note carry no separate experiments. Section 2 sets up the objects the rows above test, and Section 7 states the limits of those rows.
