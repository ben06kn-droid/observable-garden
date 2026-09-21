# living-verdict (item 3): a verdict that can be revoked

**DRAFT STUB — committed but not live, and not built.** Belongs to 6.9. Design
and pre-registration stub only; construction waits until after the paper, which
is recorded in `ROADMAP.md`. Prior art not yet searched beyond the citation
below. This item **changes a statistic** and is one of the authorised exceptions
to ROADMAP's no-new-estimator-variants rule.

## Question

A CERTIFIED verdict is a statement about the sample it was computed on. Forward
returns keep arriving. Can the certification be kept under continuous review
without spending type-I error every time it is looked at, and revoked when the
edge stops being there?

## The null

`H0: E[r_t] ≤ 0` for the certified strategy's forward returns, tested
continuously from the moment of certification.

## The bet construction, and the open choices

A betting-style test martingale (an e-process): wealth starts at 1 and is
multiplied each period by `1 + λ_t · r̃_t`, with `λ_t` chosen from the past
only. Under H0 the wealth process is a non-negative supermartingale, so by
Ville's inequality `P(sup_t W_t ≥ 1/δ) ≤ δ` — **valid under continuous
monitoring, with no penalty for looking**. That is the property this item is
for.

**Returns are unbounded and the construction requires boundedness.** The
reference result is for bounded random variables: Waudby-Smith & Ramdas,
*Estimating means of bounded random variables by betting*, JRSS-B 86(1):1–27,
2024 (arXiv:2010.09686). **Read-level: abstract via search summary; the paper
was not opened.** The open choices are listed rather than picked silently:

- **truncate** returns at a pre-registered quantile, which is simple and
  changes the estimand;
- **a bounded transform** (e.g. `tanh(r/c)` at pre-registered `c`), which keeps
  every observation and changes the estimand differently;
- **an unbounded-friendly e-process** for sub-exponential or heavy-tailed
  returns, which avoids the transform and needs a moment assumption this
  project's own 6.3 cell (B) suggests may not hold at ν = 4.

Each changes what "mean return > 0" means. The choice must be registered, with
its estimand stated, before any forward data is used.

## The revocation rule

Symmetric to the certification: a second e-process for `E[r_t] ≥ 0`, and the
verdict is **revoked** when its wealth exceeds `1/δ_revoke`. Both thresholds are
registered in advance. The revocation is a statement about the forward period
only and does not retract the original certification, which was a claim about a
different sample — the file must say so explicitly, or revocation will be read
as the gate admitting error.

## How it attaches to 6.9

6.9 holds a sealed forward test. The living verdict consumes the same forward
returns as they unseal, so the e-process must be the **only** thing reading them
before the seal opens, or the seal is broken. The attachment is therefore a
constraint on 6.9's design, not an addition to it, and 6.9's pre-registration
must be amended before this is built.

## Decision rules

**None yet.** This is a stub. Rules require the estimand choice above to be made
first, and each rule will carry its pass-rate-under-correctness figure per
`prereg/README.md` amendment 2.

## Cost

Nothing until built. Building waits until after the paper.
