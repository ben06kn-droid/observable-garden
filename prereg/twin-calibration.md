# twin-calibration (item 5): the agent as its own null

**DRAFT — committed but not live.** Authorises nothing. A new Phase 7 item.
**This one changes what certifies.** Prior art not yet searched beyond the note
below.

## Question

Every certifier built so far prices the search the *log* records. Anything the
grammar missed — unfaithful reasons, fill errors, search the agent never logged —
is invisible to it. Re-running the same agent on data where the null holds by
construction prices whatever it actually did, logged or not. Does that work, and
what does it cost?

## Design

Run the **same agent** — same prompt, same model, separate sessions — on **K
placebo twins** of the dataset, in which the null holds by construction. Compute
the gate's own p-value on the real run and on each twin. The reported p-value is
the real run's rank among them:

    p = (1 + #{twins with p_k <= p_real}) / (K + 1)

Under the twin null the K+1 runs are **exchangeable**, so this controls type-I at
any K. The construction is the permutation-test logic of Phipson & Smyth,
*Permutation p-values should never be zero*, Statistical Applications in Genetics
and Molecular Biology 9(1):Article 39, 2010. **Read-level: seen in another
paper's reference list, not opened.**

**The replay null becomes the test statistic, not the certifier.** Replay, the
class gate and item 1's bracket explain *why* a run ranks where it does; the twin
rank is what certifies.

### Twin construction — this IS the null hypothesis

What a twin destroys is what the test can detect. State it per testbed.

- **Synthetic:** a fresh s0 draw, or a joint time-permutation of returns against
  features.
- **ADR (7.4):** re-pair mornings with afternoons from different days, using the
  **same permutation across names** so cross-sectional structure survives.
- **Any return-derived feature is recomputed from the permuted returns**, so a
  twin is not detectable by internal inconsistency.

**Limits, stated in advance:** day permutation destroys volatility clustering;
block permutation is approximate; circular shifts leave a seam. A twin that an
agent could identify is not a twin, and each of these gives it a way to try.

### Masking

Tickers and calendar dates are masked, so memorised price history cannot break
exchangeability. **This is in tension with 7.4's theory-driven picks**, which
need to know what a name *is*. Resolution: expose **structural metadata without
identity** — whether a name has a home market, that market's close time, sector,
liquidity band — so a theory-driven pick remains possible while the specific
security does not. **7.4's pre-registration must state how it resolved this**;
this file records the constraint, not the resolution.

### K, and sequential stopping

**K = 19 for α = 0.05; K = 99 for α = 0.01.** These give attainable levels of
exactly 1/20 = 0.05 and 1/100 = 0.01, verified.

**Sequential stopping is NOT registered here.** Stopping early once a clear
failure is evident would save most of the cost, and the sequential Monte Carlo
construction that keeps it exactly valid is Besag & Clifford (1991), already
logged in `OPEN_QUESTIONS.md`. That entry records two unresolved checks — the
validity argument is for i.i.d. replicates, and the stopping rule interacts with
the full-class maximum in a way not yet checked. **Until those are resolved,
every certification runs the full K.** Registering early stopping without the
check is exactly the kind of shortcut this repository exists to refuse.

### Interaction with item 2

If prior-weighted α is active, the twin statistic is the **weighted min-p**:
`min(p_prior / α_prior, p_search / α_search)`.

### Readouts

- **The gap** between the log-based p-value and the twin-calibrated p-value, per
  run. This is the measured size of **latent forking** — what the log missed.
- Reported per run and pooled.

## Free check, done now, exploratory

**The stored s0 agent runs are twins of one another.** Computed on 419 graded s0
runs, rerunning nothing:

| quantity | value |
|---|---|
| KS against U(0,1) | D = 0.0991, **p = 4.9e-04 — rejects** |
| rejection rate at 0.10 | 6.92% (4.86–9.76) |
| rejection rate at 0.05 | 3.58% (2.18–5.82) |
| rejection rate at 0.01 | 0.72% (0.24–2.08) |
| mean p-value | 0.5683 |
| median p-value | 0.5791 |
| **5th percentile** | **0.0661** (95% bootstrap 0.0488–0.1159) |

So the class gate's p-values on these runs are **not uniform** but are **shifted
conservative** (mean 0.57 against 0.50), and a threshold of **0.066** would give a
true 5% rate. The bootstrap interval on that percentile includes 0.05, so the
departure at the 5% point is not itself established.

**This holds only for a fixed agent and configuration.** It is exploratory, not
pre-registered, and is not evidence about any other agent, model or dataset.

## Decision rules

1. **Scripted twins hit nominal on s0 (primary).** Scripted searchers with twins:
   the rejection rate at the attainable levels — exactly 1/(K+1) and its
   multiples — with the Wilson interval containing nominal. *Passes 0.9548 at
   α = 0.05 for a correct procedure.* The attainable grid is stated with the
   result so a rate "below nominal" is not read as conservatism when it is
   discreteness.
   - *Holds:* exchangeability is implemented correctly.
   - *Fails high:* the twins are not exchangeable with the real run — the
     construction is detectable, or masking leaked. Halt.
   - *Fails low beyond discreteness:* over-conservative, reported with its size.
2. **Twins correct what the log-based null misses (primary).** Add an
   **unfaithful searcher** — one whose logged moves do not match what it did. Its
   log-based p-value should be liberal; its twin-calibrated p-value should not.
   - *Twin-calibrated rate at nominal while log-based exceeds it:* the case for
     the whole item.
   - *Both liberal:* the twins are not catching it, and the item does not do what
     it claims. Reported plainly.
3. **The latent-forking gap, reported not gated.** Distribution of
   `p_twin − p_log` across runs.

## Cost — the binding constraint

Sized from the 661 stored agent runs: **mean $0.268 per run** (median $0.220,
90th percentile $0.473), mean wall time 160 s.

| | runs per certification | seat cost | serial seat-hours |
|---|---|---|---|
| K = 19 (α = 0.05) | 20 | **$5.35** | 0.9 |
| K = 99 (α = 0.01) | 100 | **$26.77** | 4.5 |

**Proposed design, given that cost.**

- **Synthetic cells: a shared pool of population-level twins.** 419 graded s0
  runs from the same agent and config already exist. For a fixed agent and
  config, twins of the *process* need not be twins of the *dataset*, so one pool
  serves many certifications at zero marginal cost. The free check above is that
  pool used exactly this way. **The limitation is registered: a shared pool tests
  the agent-and-config, not the dataset**, so it cannot detect a dataset-specific
  failure.
- **Per-dataset twins are reserved for a small number of 7.4 certifications**,
  where the dataset is the thing in question and a shared pool would not answer
  it. At K = 19 that is $5.35 each; **five such certifications is $27 and about
  4.5 seat-hours**, which is affordable and is the registered budget.
- K = 99 is **not** budgeted for routine use. It is reserved for a single
  headline certification if one is wanted at α = 0.01.
