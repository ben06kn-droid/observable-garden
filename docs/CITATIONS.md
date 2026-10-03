# Citation checks

What each source was checked for, what was found, where, and against which copy. A
citation not listed under "Verified" is **unverified** and is not to be cited as saying
anything until it is checked here.

## Verified, 2026-10-02 (America/Chicago)

### Turpin, Michael, Perez & Bowman (2023): verified as a neighbour, not a precedent

"Language Models Don't Always Say What They Think: Unfaithful Explanations in
Chain-of-Thought Prompting", NeurIPS 2023, arXiv:2305.04388. The author order is
**Turpin, Michael, Perez, Bowman**.

**Cited for:** a neighbour of the fidelity measurement in `ROADMAP.md` 7.3 item 2 and
`prereg/agent-cell.md`, "Prior art". The fidelity measurement re-presents one decision
about 20 times with resampled numbers and records how often the declared rule predicts
the choice.

**What it says:**
- §2, p. 3, framing: "The counterfactual simulatability framework of explanation
  faithfulness aims to measure whether model explanations on one input help humans
  predict what predictions models will give on other inputs…"
- p. 4, method: the context is biased by reordering, "We reorder the multiple-choice
  answer options … so that the correct answer is always the first one (A)."
- p. 5, metric: "decrease in model accuracy when exposed to biased contexts".

**Verdict:** a genuine neighbour, not the same measurement. The paper measures whether a
free-text chain of thought omits a bias, through an accuracy drop under biased
contexts. It does not measure the rate at which a declared rule predicts a choice under
resampled re-presentations. "Neighbour" is accurate; "precedent" or "prior measurement"
would not be.

**Closer, unverified:** Chen et al. (2023), arXiv:2307.08678, on counterfactual
simulatability. Not read.

### Faraway (1992): verified, but cited nowhere

"On the Cost of Data Analysis", *Journal of Computational and Graphical Statistics*
1(3), 213–229, doi:10.1080/10618600.1992.10474582. Metadata checked via Crossref. The
text was read from the Wayback copy of the author's Bath preprint, so page numbers are
the preprint's.

**Cited, since 2026-10-02, in `THEORY.md` (the bootstrap definitions, and prior work for P4) and `quixote/README.md` (the central idea), as prior art for trigger replay.** Before that it was cited nowhere in the repository.

**What it says**, and why it matters to novelty wording:
- §3.2, p. 6: "Perform the data analysis in the same order as for the original data",
  on bootstrap samples.
- p. 6: "a valid bootstrap predictive distribution may only be obtained by applying the
  same sequence of actions to the resampled datasets".
- §6, pp. 11–12: informal actions that go unlogged, and abuse of restarts.

That is a precedent for **replaying a logged analysis sequence on resampled data**,
which is what the trigger-replay tier does. Any claim that replaying a search's logged
sequence is new must cite it.

## Unverified: cited, not checked against the text

| source | where cited |
|---|---|
| Chen et al. (2023), arXiv:2307.08678 | not yet cited; the candidate closer neighbour above |
| Besag & Clifford (1991) | `OPEN_QUESTIONS.md`, `prereg/twin-calibration.md`, `prereg/calibration-at-1pct.md`, `quixote/twins.py`, `quixote/__init__.py`, a test. **The twin construction rests on it and the score-rank cell is closed: check this first** |
| Nair & Janson (2023); Markovic, Taylor & Taylor (2019); Banerjee (2026); Miao, Pritchard & Zou (2026); van der Vaart, Thm 18.11(i) | `THEORY.md`, `docs/RELATED_WORK_2026.md`; Miao et al. also `prereg/pivotal-interrogation.md` |
| Liu et al. (2024) | `THEORY.md` (abstract only; the full text not opened) |
| Gençay; Qu; Chen & Wang; Gonuguntla; Rewolinski; Bertran (two); Hoover & Perez; Mundry & Nunn; Simonsohn et al. | `docs/RELATED_WORK_2026.md` (abstract-only entries) |
| Rewolinski et al. (2026) | `prereg/agent-cell.md`, `AGENT_PROMPTS.md`, `AGENT_PROMPTS_REAL.md` |
| Abdi & Ranaldo; Roll | `prereg/adr-features.md`, `prereg/agent-pilot.md`, `data/adr_costs.py`, `environments/real_panel.py` (formula checked against the R package only, not the papers) |
| Waudby-Smith & Ramdas (2024) | `prereg/living-verdict.md` (draft) |
| Genovese, Roeder & Wasserman (2006) | `prereg/prior-weighted-alpha.md` (draft) |

Also unchecked, and not citations: the FTT treatment, XETR's 30 December close, and
XSTO's half day.
