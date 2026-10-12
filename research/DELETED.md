# Deleted in the 2026-10 cleanup

Every path below was deleted on the branch `cleanup-2026-10`. **Each one is recoverable from the tag
`pre-cleanup-2026-10-12`**, with its pre-cleanup path (no `research/` prefix), for example:

    git show pre-cleanup-2026-10-12:runs/ml_v2_smoke/2026-10-08/smoke.txt

Kept instead of deleted, whatever the pattern:
- anything cited by EXPERIMENTS.md, NOTE_MAP.md, a registration or runs/EXCLUSIONS.md;
- any read, any raw output behind a read, any superseded read kept beside a read;
- every registration and amendment.

Matched but kept because cited: `runs/_smoke/` (planted-edge.md, twin-calibration.md),
`runs/french_long_smoke/` (french-long-history.md), `runs/ml_smoke/` (ml-pipeline-exploratory),
`figures/fixed_sequence_replay_cost.txt` (holdout-grading.md), `docs/french_long_operator_sheets.md`
and `docs/french_step0_box_commands.md` (cited by registrations), and `runs/shakeout2_s0_*`
(read by `runs/self_enforcement_exploratory.txt`). No note was found that only records a bug
met in testing and its fix, so none was deleted under that heading.

| path (now under research/) | files | bytes | reason |
|---|---|---|---|
| `docs/cleanup_proposal.md` | 1 | 7,303 | a proposal for this cleanup, superseded by the work order |
| `docs/etf_recent_grading_sheet.md` | 1 | 6,806 | operator command sheet for a finished box or host session (the run records keep what ran) |
| `docs/etf_recent_operator_sheets.md` | 1 | 14,571 | operator command sheet for a finished box or host session (the run records keep what ran) |
| `docs/ml_confirm_box_commands.md` | 1 | 3,414 | operator command sheet for a finished box or host session (the run records keep what ran) |
| `docs/ml_v2_confirm_box_commands.md` | 1 | 3,741 | operator command sheet for a finished box or host session (the run records keep what ran) |
| `docs/ml_v2_pilot2_box_commands.md` | 1 | 4,702 | operator command sheet for a finished box or host session (the run records keep what ran) |
| `docs/ml_v2_pilot_box_commands.md` | 1 | 3,980 | operator command sheet for a finished box or host session (the run records keep what ran) |
| `docs/recency_planted_2_box_commands.md` | 1 | 3,240 | operator command sheet for a finished box or host session (the run records keep what ran) |
| `docs/recency_planted_box_commands.md` | 1 | 4,591 | operator command sheet for a finished box or host session (the run records keep what ran) |
| `figures/calibration_at_1pct_armD_smoke48.txt` | 1 | 1,783 | smoke / cost-only output, cited by no registration |
| `figures/calibration_at_1pct_armD_smoke48_data.pkl` | 1 | 8,313 | smoke / cost-only output, cited by no registration |
| `figures/fixed_sequence_replay_scaling_w1.txt` | 1 | 668 | scaling-curve / timing output, cost only |
| `figures/fixed_sequence_replay_scaling_w16.txt` | 1 | 666 | scaling-curve / timing output, cost only |
| `figures/fixed_sequence_replay_scaling_w24.txt` | 1 | 666 | scaling-curve / timing output, cost only |
| `figures/fixed_sequence_replay_scaling_w32.txt` | 1 | 666 | scaling-curve / timing output, cost only |
| `figures/fixed_sequence_replay_scaling_w8.txt` | 1 | 667 | scaling-curve / timing output, cost only |
| `figures/fixed_sequence_replay_smoke_cost.txt` | 1 | 766 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s0_cost.txt` | 1 | 1,533 | cost-only output |
| `figures/gate_comparison_s0_replication_budgeted-random-25_holdout_70_30_cost.txt` | 1 | 1,532 | cost-only output |
| `figures/gate_comparison_s0_smoke192_w192_cost.txt` | 1 | 1,527 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s0_smoke192_w192_data.pkl` | 1 | 973,261 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s0_smoke192_w24_cost.txt` | 1 | 1,580 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s0_smoke192_w24_data.pkl` | 1 | 973,261 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s0_smoke192_w48_cost.txt` | 1 | 1,580 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s0_smoke192_w48_data.pkl` | 1 | 973,261 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s0_smoke192_w96_cost.txt` | 1 | 1,525 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s0_smoke192_w96_data.pkl` | 1 | 973,261 | smoke / cost-only output, cited by no registration |
| `figures/gate_comparison_s3_cost.txt` | 1 | 1,533 | cost-only output |
| `figures/scaling_c7a48xl/` | 12 | 186,743 | smoke / cost-only output, cited by no registration |
| `figures/us_curve_B1000/` | 2 | 70,105 | smoke / cost-only output, cited by no registration |
| `figures/us_curve_B125/` | 2 | 69,998 | smoke / cost-only output, cited by no registration |
| `figures/us_curve_B250/` | 2 | 69,998 | smoke / cost-only output, cited by no registration |
| `figures/us_curve_B500/` | 2 | 70,087 | smoke / cost-only output, cited by no registration |
| `runs/etf_recent_smoke/` | 2 | 945 | smoke / cost-only output, cited by no registration |
| `runs/ml_confirm_dry/` | 4 | 15,471 | dry run (pipeline check before a registered run), cited by no registration |
| `runs/ml_confirm_smoke/` | 2 | 2,559 | smoke / cost-only output, cited by no registration |
| `runs/ml_pilot_dry/` | 4 | 369,804 | dry run (pipeline check before a registered run), cited by no registration |
| `runs/ml_smoke_box/` | 3 | 46,542 | smoke / cost-only output, cited by no registration |
| `runs/ml_v2_confirm_dry/` | 3 | 19,368 | dry run (pipeline check before a registered run), cited by no registration |
| `runs/ml_v2_pilot2_dry/` | 4 | 28,070 | dry run (pipeline check before a registered run), cited by no registration |
| `runs/ml_v2_pilot_dry/` | 4 | 19,653 | dry run (pipeline check before a registered run), cited by no registration |
| `runs/ml_v2_smoke/` | 2 | 130,141 | smoke / cost-only output, cited by no registration |
| `runs/ml_v2_smoke_box/` | 3 | 157,659 | smoke / cost-only output, cited by no registration |
| `runs/ml_v2_smoke_box2/` | 3 | 158,085 | smoke / cost-only output, cited by no registration |
| `runs/ml_v2_smoke_box3/` | 2 | 128,263 | smoke / cost-only output, cited by no registration |
| `runs/recency_planted_2_dry/` | 4 | 9,003 | dry run (pipeline check before a registered run), cited by no registration |
| `runs/recency_planted_2_smoke/` | 2 | 3,286 | smoke / cost-only output, cited by no registration |
| `runs/recency_planted_dry/` | 4 | 7,247 | dry run (pipeline check before a registered run), cited by no registration |
| `runs/recency_planted_smoke/` | 2 | 2,896 | smoke / cost-only output, cited by no registration |
| `runs/shakeout_s0_orientation/` | 4 | 36,580 | shakeout run, cited by no registration, EXPERIMENTS.md or NOTE_MAP.md |
| `runs/shakeout_s0_reasoned/` | 4 | 53,167 | shakeout run, cited by no registration, EXPERIMENTS.md or NOTE_MAP.md |

**In all: 104 files, 5,626,067 bytes.**
