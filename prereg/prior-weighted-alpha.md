# prior-weighted-alpha (item 2): spending some of α on a declared short list

**DRAFT — committed but not live.** Authorises nothing. A 7.2 slot, validated by
scripted searchers in 7.3, and an arm in 7.4. Prior art not yet searched beyond
the citation below.

## Question

An agent that already believes something before it searches currently gets no
credit for it: its prior conviction is tested against the same wide class as the
rest of its search. Splitting α between a small declared list and the adaptive
search buys power on the list at the cost of power on the search. Is the trade
worth taking, and at what split?

## Design

**The declaration.** Before its first `evaluate`, the agent may declare a short
list of specifications. **Cap: 5.** The harness timestamps the declaration
exactly as it does `pick_prior`, and refuses a declaration that arrives after
any evaluation — a list assembled after seeing results is not a prior.

**The split, fixed here and not at run time: α_prior = 0.04, α_search = 0.01.**

- the short list is tested by Reality Check over **just those specifications**,
  at α_prior;
- the adaptive search is tested by the replay or declared-class tier, at
  α_search;
- the run **certifies if either rejects**, and the Verdict records **which
  family rejected**.

**Why total error is controlled.** `P(reject either) ≤ α_prior + α_search` by
the union bound, which holds **under any dependence** between the two families,
provided the list preceded all results — which the timestamp enforces. No
independence is assumed and none is available. The weighted-p-value literature
is the general setting for allocating error across families with prior
information: Genovese, Roeder & Wasserman, *False discovery control with p-value
weighting*, Biometrika 93(3):509–524, 2006. **Read-level: abstract via a
publisher listing and the related preprint (Wasserman & Roeder, arXiv
math/0604172, opened in full); the Biometrika paper itself was not opened.** The
guarantee this design rests on is the union bound, which needs no citation; the
reference is for the idea, not the proof.

**The measured trade, computed before the run** at T = 5,000, K = 40, d = 3
signed, against arm D's measured class bar:

| | bar (annualised Sharpe) | power at true SR = 1.0 |
|---|---|---|
| five-item list at α = 0.04 | **0.5395** | — |
| declared class at α = 0.05 (arm D measured) | **1.0213** | **46.2%** |
| declared class at α = 0.01 | 1.1156 | **30.3%** |

So the list's bar is roughly **half** the class bar, and the cost is the search's
power falling from 46.2% to 30.3%. Both sides are reported; neither is presented
alone.

**Scripted validation (7.3).** Total type-I on s0 must be ≤ α. On s3, power is
measured twice: **with the true specification on the list**, and **with it off
the list**. The second is the case where the split is pure cost.

## Decision rules

1. **Total size (primary, one-sided).** On s0, the lower Wilson end of the
   combined rejection rate — either family rejecting — does not exceed α = 0.05.
   *Passes 0.9749 for a correct procedure at n = 2,000.*
   - *Holds:* the split is safe to offer.
   - *Fails high:* the union bound is being violated, which can only mean the
     timestamp did not enforce priority. Halt and find it.
   - *Fails low:* conservative, expected, since the union bound is not tight.
     Reported with its size.
2. **Power, both directions (no halt).** On s3, PASS rate with the true spec on
   the list and off it, against the unsplit gate at α = 0.05.
   - *On-list power exceeds unsplit:* the split pays when the prior is right.
   - *Off-list power below unsplit by more than the predicted 46.2% → 30.3%:*
     the cost is larger than the arithmetic says and the discrepancy is
     investigated.
   - Reported as a table, not a verdict. **This rule ranks, it does not gate.**
3. **Which family rejected, reported not gated.** The share of certifications
   coming from each family. A split that never certifies through the list is
   paying α for nothing, and that is reportable.

## Cost

No additional bootstrap: the five-member list is priced by the ordinary Reality
Check on five streams, which is negligible beside the class null. Scripted
validation is one extra scored submission per draw in whatever cell hosts it.
Agent-facing use costs nothing extra per run.
