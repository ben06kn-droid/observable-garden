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

### Phipson & Smyth (2010): partly verified. "Exact under exchangeability" is not what it says

"Permutation p-values should never be zero: calculating exact p-values when
permutations are randomly drawn", *Statistical Applications in Genetics and Molecular
Biology* 9(1), Article 39, doi:10.2202/1544-6115.1585 (Crossref). **Read in full:**
arXiv:1603.05766v1, "corrected 9 February 2011". Page numbers are the arXiv PDF's.

**Cited for:** the twin rank p-value `(1 + #)/(K + 1)` (`quixote/twins.py`,
`prereg/twin-calibration.md`), and that a p-value of this kind is never zero.

**What it says:**
- §1, p. 3: "it makes no inferential sense to assert that the p-value can be reduced
  to zero by considering only a subset of the permutations".
- §4, p. 6, Monte Carlo tests: assuming "it is possible to generate independent random
  datasets under the null hypothesis", and "that the test statistic t is continuous",
  "the exact Monte Carlo p-value is p_u = P(B ≤ b) = (b + 1)/(m + 1)".
- §5, p. 7: the same formula is exact for permutations drawn without replacement.
- §6.1-6.2, pp. 7-8: with replacement, "the exact p-value is now slightly less than
  (b + 1)/(m + 1)", so p_u is "valid but conservative".

**Verdict: PARTLY.** Verified: never zero, and valid at any K. Exact only for
independent null datasets with a continuous statistic and no ties. **Not supported:
"exact under exchangeability".** The paper does not treat exchangeable replicates in
general; that extension is the standard rank argument. Ties counted by `<=` make it
conservative. `quixote/twins.py` is reworded (2026-10-02), and
`prereg/twin-calibration.md` carries a dated note. **No verdict changes.** The closed
score-rank cell's rule asks for validity (rate ≤ α), not exactness, and every one of
its twelve rates was below 0.05, which is the direction this predicts.

### Besag & Clifford (1991): metadata verified; the text could not be accessed

"Sequential Monte Carlo p-values", *Biometrika* 78(2), 301-304,
doi:10.1093/biomet/78.2.301 (Crossref). The 1989 paper cited beside it,
"Generalized Monte Carlo significance tests", *Biometrika* 76(4), 633-642,
doi:10.1093/biomet/76.4.633, also exists as cited.

**Cited for:** a sequential stopping rule that keeps a Monte Carlo p-value valid
(`OPEN_QUESTIONS.md`), and as the reason twin stopping is **not** built
(`prereg/twin-calibration.md`, `quixote/twins.py`, `quixote/__init__.py`, a test).
**Nothing built or run rests on it.** It is cited for something deliberately absent.
An earlier line of this file said the twin construction rests on it; that was wrong.
The construction is Phipson & Smyth's.

**Copies tried:** the OUP page and PDF (403, a bot check); JSTOR 2337256, abstract
only, read through a Wayback snapshot of 2022-10-17; Unpaywall, OpenAlex and Semantic
Scholar, all listing it closed with no repository copy.

**What can be said:**
- The abstract reads: "a number of ways of calculating exact Monte Carlo p-values by
  sequential sampling … a sequential method is proposed for dealing with situations
  in which values can only be conveniently generated using a Markov chain".
- The formula, from secondary sources only: stop at `h` exceedances with `p = h/l`;
  otherwise `(1 + #)/(M + 1)` at the cap. Stoepker & Castro, arXiv:2409.18908, §3.3,
  say it is "unconditionally valid" with "no conditional validity guarantees".

**Verdict: COULD NOT ACCESS** for the formula's location and for whether the
validity argument assumes i.i.d. draws. The abstract's Markov-chain case suggests
exchangeable rather than i.i.d. Reading it needs institutional access to the JSTOR
scan or the OUP PDF. `OPEN_QUESTIONS.md` is reworded so it claims no more than this.

## Unverified: cited, not checked against the text

| source | where cited |
|---|---|
| Chen et al. (2023), arXiv:2307.08678 | not yet cited; the candidate closer neighbour above |
| Nair & Janson (2023); Markovic, Taylor & Taylor (2019); Banerjee (2026); Miao, Pritchard & Zou (2026); van der Vaart, Thm 18.11(i) | `THEORY.md`, `docs/RELATED_WORK_2026.md`; Miao et al. also `prereg/pivotal-interrogation.md` |
| Liu et al. (2024) | `THEORY.md` (abstract only; the full text not opened) |
| Gençay; Qu; Chen & Wang; Gonuguntla; Rewolinski; Bertran (two); Hoover & Perez; Mundry & Nunn; Simonsohn et al. | `docs/RELATED_WORK_2026.md` (abstract-only entries) |
| Rewolinski et al. (2026) | `prereg/agent-cell.md`, `AGENT_PROMPTS.md`, `AGENT_PROMPTS_REAL.md` |
| Abdi & Ranaldo; Roll | `prereg/adr-features.md`, `prereg/agent-pilot.md`, `data/adr_costs.py`, `environments/real_panel.py` (formula checked against the R package only, not the papers) |
| Waudby-Smith & Ramdas (2024) | `prereg/living-verdict.md` (draft) |
| Genovese, Roeder & Wasserman (2006) | `prereg/prior-weighted-alpha.md` (draft) |

Also unchecked, and not citations: the FTT treatment, XETR's 30 December close, and
XSTO's half day.
