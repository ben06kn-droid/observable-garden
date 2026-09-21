# bits-of-selection (item 6): a measurement layer, with no role in any verdict

**DRAFT — committed but not live.** Authorises nothing. Prior art not yet
searched beyond the citations below. **Bits are descriptive and never enter the
correction** — that sentence appears in the Verdict's reasons.

## Question

"How much did this search look at?" currently has no unit. Effective breadth is
reported as a count, which is not comparable across classes, statistics or
searchers. Is there a common currency, and what does it show?

## The inversion

Define a search's **effective number of independent trials** as the `N` at which
Bailey & López de Prado's closed-form expected maximum equals the search's
measured null maximum, in units of the Sharpe standard error:

    E[max of N] = (1 - gamma) * Phi^-1(1 - 1/N) + gamma * Phi^-1(1 - 1/(N e))
    bits = log2(N)

with `gamma` the Euler–Mascheroni constant. The reference is already cited in
`THEORY.md`: Bailey & López de Prado (2014), *The deflated Sharpe ratio*.

**Computed from arm D's s0 null-max means**, at T = 5,000 (SE = 0.2245):

| searcher | mean null max | z | N | bits |
|---|---|---|---|---|
| `Greedy` | 0.4847 | 2.159 | **37** | **5.21** |
| `exhaustive-unsigned` / `Adaptive` | 0.7045 | 3.138 | **667** | **9.38** |
| `exhaustive-signed` | 0.8211 | 3.658 | **4,442** | **12.12** |

`Greedy` recovers ≈37 against forty independent single-feature trials, which is
the sanity check the inversion has to pass.

**The inversion is sensitive to which moment it matches, and this is registered
as a limitation rather than discovered later.** Matching the null-max **mean**
gives N = 4,442 for the signed class; matching arm D's measured **5% quantile**
(1.0213) gives N = 19,071 — **2.1 bits apart**. The registered definition matches
the **mean**, as the formula above specifies. Any figure quoted in bits must say
which moment it inverted, and the 5% figure is reported alongside for every cell.

**Why bits, and not some other monotone transform of N.** Russo & Zou bound the
bias of an adaptively chosen estimate by `|E[phi_T - mu_T]| <= sigma * sqrt(2 I(T;phi))`,
with `I` the mutual information between the selection and the estimates —
Proposition 1 of *How much does your data exploration overfit? Controlling bias
via information usage*, arXiv:1511.05219 (AISTATS 2016). **Read-level: opened in
full and the proposition verified verbatim.** For the maximum of N independent
Gaussians the bias is `sigma * sqrt(2 ln N)`, so equating gives `I = ln N` nats,
i.e. `log2 N` bits **exactly**, under that model. Outside it the two coincide
only approximately, and the observed bias gives a **lower** bound on information
absorbed. The bound is the reason information is the right currency; it is not
the definition.

## What is registered

- **The inversion formula**, above.
- **A per-move ledger**: bits added by each move, from replaying the sequence
  truncated at each step.
- **7.1's fixed-sequence gap** against trigger replay, expressed in bits.
- **Item 1's bracket**, expressed as a bits interval.
- **Item 5's gap**, expressed as **latent bits** — the information the log did
  not account for.
- The Verdict reports `bits` alongside `effective_breadth`, plus a reasons line
  stating that bits are descriptive and never enter the correction.

**For future agent cells**: register "stated confidence regressed on bits
absorbed" **alongside** the existing log-trial-count regression. It does **not**
replace the agent arm's registered primary analysis. **On stored runs this
analysis is exploratory.**

## Decision rules

**One, and it gates nothing else.**

1. **The inversion recovers a known breadth (sanity, one-sided).** On an
   oblivious menu of N pre-specified independent strategies, the inverted N is
   within a registered factor of 2 of the true N, for N in {10, 40, 100, 1000}.
   *A correct implementation passes this essentially always; the rule exists to
   catch an implementation error, not a statistical one.*
   - *Holds:* the ledger's units mean what they say.
   - *Fails:* the inversion is misimplemented or the null max is not what the
     formula assumes. Bits are not reported until it is fixed.

There is deliberately no rule on the bits themselves. **Bits enter no verdict**,
so no bits figure can pass or fail anything.

## Cost

Free. Every input is already computed: the null maximum per draw, and for the
ledger, replays the gate already performs. The per-move ledger costs one extra
truncated replay per move, which is the same order as the replay itself.

## Link

This feeds the later effective-N note. **The note is not written now**; the link
is recorded in `ROADMAP.md`.
