# Note outline: fixed and adaptive candidate sets under the DSR

**Status: the message to López de Prado was sent on 2026-09-16.** Drafting and
sending are done; this file is kept as the record of the decisions behind it,
not as a to-do list.

Drafting decisions for the note addressed to López de Prado & Porcu, recorded
so the wordings and their provenance survive. Section numbers are the note's,
not this repository's.

Terminology is THEORY.md's Terminology table: trial, candidate set, `ŜR_c`,
`F_{M_K}`, liberal, DSR-EO.

## §3, Proposition 1 route

Do **not** write "White (2000) requires a data-independent universe." Write:

> White's asymptotics hold the specification set fixed and finite (`l` fixed
> as `T → ∞`) while treating the specifications as products of a specification
> search; they do not state what "fixed" requires when the specifications were
> chosen from the evaluation data. Proposition 1 makes that condition explicit
> — the menu is data-oblivious — and §4 shows what fails without it.

Verified against the published text: §2 fixes `l`; the paper does not address
selection of the specifications from the evaluation data.

**Large-K remark.** Cite White (2000) §5's open problems for both growing `l`
with `T` and cross-validation. Verified quotation: "permitting the number of
specifications tested to increase with the sample size, application of the
method to the results of cross-validation, and the use of recentering,
rescaling".

## §4, after Corollary 4.1

> A random-anchored search has the same menu construction, depth and K as a
> winner-anchored one and is exactly calibrated under the realized-menu test
> (limit 5.00%, E17 measured 5.0%). Adaptivity is not what breaks the
> realized-menu null; anchoring direction is.

The limit figure is 5.00% ± 0.02 as measured by `experiments/limit_model.py`,
not the 5.01% the plan quoted; report the measurement.

## §4, growth paragraph — three sentences

1. **Growth in K** is a known phenomenon: Freedman (1983); Dwork et al.
   (2015), whose bounds are symmetric in the raw query count `k`. *(The Dwork
   symmetry claim is from secondary summaries; verify at drafting.)*
2. **Dependence on the running best rather than the count**: Blum & Hardt
   (2015, Thm 3.1) and Hardt (2017, Cor. 2.3, with `B` = number of update
   rounds defined at eq. 3). Note `B` is this note's *depth* axis; the rank
   axis has no counterpart there.
   **Correction to the plan:** the plan cited Hardt's Lemma 2.1 for this.
   Lemma 2.1 is the privacy step, `(ε√B, O(δ))`-differential privacy. The
   error bound scaling with `√B` is Corollary 2.3. Blum & Hardt's Thm 3.1 is
   logarithmic in the query count `k`; their running-best dependence is in the
   mechanism (release only on improvement), not in the bound's rate.
3. **Contribution**: sign, mirror, random-anchor exact calibration, the
   mixture identity, closed-form size in the data-snooping-test setting, and
   damping in ω.

## §8, related work

- **Post-selection**: lead with Leeb & Pötscher (2006), *Annals of Statistics*
  34(5), 2554–2591, for the conditional law; Leeb & Pötscher (2005) second.
- **Hansen (2005)**: conservativeness concerns padding a fixed menu with poor
  alternatives, not a data-chosen menu. One clause.
- **Romano & Wolf (2005)**: "fixed number S" of strategies. One clause.
- **Hsu, Hsu & Kuan (2010)**: "given m models, k = 1,…,m." One clause.
- **Dwork et al. (2015)**: error symmetric in `k`; no anchoring dependence.
- **Blum & Hardt (2015) / Hardt (2017)**: cost scales with best-so-far
  updates; adaptive risk estimation, not a max-test null; no sign, no mirror.

**Unverified as of this writing**: the Hansen, Romano–Wolf, Hsu–Hsu–Kuan and
Dwork characterizations above come from publisher metadata and secondary
summaries. Each quoted phrase must be checked against the paper before the
note asserts it. White, Blum & Hardt and Hardt have been read from full text
(THEORY.md, "Prior work checked").

## Table 1 caption (E21)

> N is driven by K; lattice size and correlation exposure move together.

The two axes are not independent, and the table should not be read as
separating them.
