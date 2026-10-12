# Commit map: history rewrite of 2026-09-15

On 2026-09-15 this repository's history was rewritten to remove commit-message
trailers and to set the author and committer on 40 commits to the GitHub
account's identity. No file changed. Every rewritten commit has the same tree,
author date, committer date and subject line as the commit it replaces; the
tree column lets anyone holding a pre-rewrite clone check that.

Hashes recorded before the rewrite refer to the **old** column. That includes
`git_at_launch` in `figures/e16_pointwise_dominance_data.pkl`,
`figures/e17_graded_coupling_data.pkl` and E18's data file, whose run launched
from the old `eaf378236c83`. Pre-registration order is unchanged: each
`prereg/` commit keeps its original date and still precedes its results.

| old commit | new commit | tree | date | subject |
|---|---|---|---|---|
| `b3fe132fc197` | `be3c0df93820` | `a211e464e5e4` | 2026-09-15 | E17 results: naive distortion rises with anchor coupling across rules (trend p = 0.0001) |
| `eaf378236c83` | `ab903659f814` | `8f37634fd10c` | 2026-09-15 | Fix E18's --smoke help string: escape the percent sign for argparse |
| `76f08199aafb` | `00f7879d4342` | `7931a1d4fe11` | 2026-09-15 | Pre-register E18: search depth and whether recursive nulls coincide across beams |
| `5f4ad9d9f47b` | `3a2c3351ee0b` | `9023dc74f0b5` | 2026-09-15 | Record prior work read in full for P4, P5 and kappa; draft E18 |
| `034a6332f12a` | `575678a831b2` | `a21f51cc0855` | 2026-09-15 | Transcript format v2 and the full-class verdict path |
| `c6c0cc5010e5` | `1ab912154fce` | `952dcbca4275` | 2026-09-15 | Correct citation details that rested on generated summaries, not publisher metadata |
| `0d87397b8bc7` | `34934a1717e1` | `84c7b5c760af` | 2026-09-15 | Draft THEORY.md: when a logged search transcript licenses a search-adjusted test |
| `0cfcf52d62f6` | `254cddaf9ff3` | `6b5797767c96` | 2026-09-15 | Pre-register E17: is the naive bootstrap's distortion graded in anchor coupling? |
| `7fbe33c5b1cc` | `714ee26910ed` | `6990147d8447` | 2026-09-15 | E16 results: winner-anchoring's distortion is pointwise dominance, gate passed |
| `809f31f5b37b` | `88049e56ebac` | `5da06ad35dab` | 2026-09-15 | Add the full-class matrix, GumbelAnchored searcher, and two related-work entries |
| `10f5c3be6bb8` | `c8c5d60849ca` | `f6dad0bcffb3` | 2026-09-15 | Pre-register E16: is P4's pointwise dominance the mechanism behind e15? |
| `a00828449123` | `309332d4a66c` | `4f03430493a8` | 2026-09-15 | Adopt López de Prado & Porcu's DSR framing and scope the effective-N claim |
| `5a1b567d2744` | `66eb7cab22d3` | `3732af0f89da` | 2026-09-15 | e15 results: only the winner-anchored menu distorts the naive bootstrap |
| `d2b8c5b220fc` | `675278d90bb7` | `e27e7a97091b` | 2026-09-15 | Fix NeighborAdaptive's anchor and pre-register e15: anchor coupling vs. type-I |
| `7c4b63510443` | `64961cd6645f` | `1d1a18709013` | 2026-09-15 | Recalibrate the degeneracy check on fresh seeds and adopt e14's thresholds |
| `94a523600721` | `a8f0cd3bde84` | `3683da03b053` | 2026-09-15 | Add a checkpointing parallel runner and run e11 through it |
| `efe523082677` | `795f33f40761` | `17486a545839` | 2026-09-15 | Pre-register e14: recalibrate the degeneracy check against a broken-bar definition |
| `1d4fd7490119` | `c72a29cf6c39` | `bddd6338c72a` | 2026-09-15 | Add EC2 setup and detached-run scripts for running experiments in the cloud |
| `70fb4386d3f2` | `8380d9c74430` | `db0b93d2fa2b` | 2026-09-15 | Ship the garden gate: a verdict on whether a search's result can be believed |
| `7e915bef2dc4` | `3446f10cd5a4` | `cd9ecce59178` | 2026-09-14 | Cite White's Reality Check as the estimator's actual prior art |
| `e701df7362c3` | `c92abbc9ef77` | `e6c36fdd1aa4` | 2026-09-14 | Fix power analysis description in README |
| `38bcd636a10f` | `c4849a7d1365` | `3de72d779984` | 2026-09-14 | The pure multiple-testing cost, isolated: power falls in N as it must |
| `26b244fd06e0` | `810d003589c3` | `bfcc66c2fb97` | 2026-09-14 | Fix a real confound in e10: search benefit and multiple-testing cost were tangled |
| `073370bd6053` | `eb2b2a3c91d2` | `130fab263949` | 2026-09-14 | Deconfounded power-vs-signal-strength results: clean, monotone, as predicted |
| `d5be1639fdcb` | `80d95458c25e` | `4bdd6ee0a8de` | 2026-09-14 | Correct a conflation: power-vs-rho measured task difficulty, not sensitivity |
| `38fdc033b92e` | `323fc14237d6` | `74a56fbbbdf2` | 2026-09-14 | Analyze the power data Experiment 2 already collected but never surfaced |
| `2a71ba515fd3` | `3672d2f4cdcc` | `d8efd8c6eda7` | 2026-09-14 | Close out Experiment 2 with its figures; cut README to a 1-2 minute read |
| `29c95fa12cf3` | `99014d19f991` | `b15cbd1c197d` | 2026-09-14 | Experiment 2 v2 results: bias, not RMSE, distinguishes the three corrections |
| `61deff0007a9` | `626afbf4d08b` | `bfaeed5e356c` | 2026-09-14 | Two DGP fixes for Experiment 2, sequenced correctly: criterion first |
| `c232ec25f131` | `85fc4079b85c` | `749ad7332358` | 2026-09-14 | Experiment 2 results: a mixed finding, reported straight |
| `bc709393880c` | `7eaa9455f5d8` | `2731cd9378ee` | 2026-09-14 | Shorten README to a scannable summary; move full detail to SCOPE.md |
| `b22418f732d8` | `4dc6051d223d` | `9a256e157ef1` | 2026-09-14 | Experiment 2 infrastructure, gated by a cheap precondition check first |
| `0cd2efb1eae9` | `478aa856422c` | `c0e51c2d1503` | 2026-09-14 | Verify, don't narrate: recursive's 5-point agreement was one measurement |
| `7b9163c752b7` | `304880af5d8e` | `243afb1ac7d1` | 2026-09-14 | Update README.md |
| `35039ad7d47c` | `95016d4742eb` | `0bfd097d28c4` | 2026-09-14 | Dose-response sweep confirms the mechanism generalizes: strictly monotone |
| `2fba87e5a7ff` | `d2c45916d7cd` | `8bb930eeb400` | 2026-09-14 | Dose-response infrastructure; find and fix a real sr_sel bug along the way |
| `125e4f35b6c9` | `6d72bf1d7162` | `7d3c328534ca` | 2026-09-14 | Definitive n=500 Adaptive result: recursive bootstrap fix holds at power |
| `2e744bb5a2e7` | `495ae3bbf102` | `8ab6881cb775` | 2026-09-14 | Generalize the adaptive-search fix; find and fix its own dependency gap |
| `b467cf73221c` | `065cffcec688` | `8a10049712d3` | 2026-09-14 | Scope the validated claim; ground Adaptive's failure in post-selection theory |
| `b8b432a9220d` | `23ba6530dc1d` | `dd1312a7a924` | 2026-09-14 | Days 7-9: scripted searchers; e1 null-calibration gate finds a real failure |
| `06d3886889a1` | `0a757fedc237` | `c3466884b926` | 2026-09-14 | Days 4-6: bootstrap null-maximum estimator, closed-form DSR baseline |
| `96ea77c5ef83` | `ed14594bc408` | `8015c24f9bf2` | 2026-09-14 | Days 1-3: synthetic DGP with computable oracle, sandbox contract |
