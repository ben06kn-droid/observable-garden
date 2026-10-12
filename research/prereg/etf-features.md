# 6.5 ETF features: K = 40, committed before any run

**DRAFT for the feature-list commit.** Committed after the universe commit and
before any bar is opened, priced or summarised. The feature-building code refuses
to run unless this commit is an ancestor of HEAD (the ADR guard pattern).

## Construction

**Twenty base signals, each in two cross-sectional forms: 20 × 2 = 40.**

Every signal for asset *i* on day *t* uses **only data through the close of t**
(strict one-day lag relative to the registered execution, in which the position
runs from the close of t+1 to the close of t+2). Returns are log returns of
adjusted closes.

- **z form:** the signal cross-sectionally demeaned and divided by its
  cross-sectional standard deviation on day *t*, across the panel's assets.
- **rank form:** the signal's cross-sectional rank on day *t*, mapped linearly to
  [−1, 1].

Both forms have cross-sectional mean zero, so **every feature is dollar-neutral**
and the zero-return null needs no benchmark subtraction. A specification's
position is the signed, equal-weight sum of its members' features, demeaned and
scaled to gross exposure 1.

**K = 40 is twenty pairs of near-duplicates, by construction.** Each base signal
appears as its z form and its rank form, which are monotone transforms of each
other and highly correlated. That is **harmless to the bar**: by duplicate
invariance, adding a near-copy of a column adds class members whose streams
nearly coincide with existing ones, so the null maximum, and with it the bar,
barely moves. It is **a budget cost to a searcher**: evaluations spent on a
signal's second form buy almost no new information, so an agent with a fixed
evaluation budget effectively searches fewer distinct signals than K suggests.
This is recorded so that behaviour readouts (which features agents converge on)
are read with it in mind.

**Redundancy under signs.** The class is signed, so a signal and its negative are
one feature. No base signal is the negative of another. In particular,
short-term reversal is a sign on the 1-day return, not a separate signal.

## The twenty base signals

| # | signal | definition on day t |
|---|---|---|
| 1 | return, 1 day | r(t) |
| 2 | momentum, 5 days | sum of r over t−4..t |
| 3 | momentum, 21 days | sum over t−20..t |
| 4 | momentum, 63 days | sum over t−62..t |
| 5 | momentum, 126 days | sum over t−125..t |
| 6 | momentum, 252 days | sum over t−251..t |
| 7 | momentum, 12-1 | sum over t−251..t−21 (skips the last month) |
| 8 | realized volatility, 21 days | standard deviation of r over t−20..t |
| 9 | realized volatility, 63 days | over t−62..t |
| 10 | realized volatility, 252 days | over t−251..t |
| 11 | volatility-scaled momentum, 63 days | #4 ÷ #9 |
| 12 | volatility-scaled momentum, 252 days | #6 ÷ #10 |
| 13 | distance from 50-day average | log(P(t) / mean of P over t−49..t) |
| 14 | distance from 200-day average | log(P(t) / mean of P over t−199..t) |
| 15 | moving-average spread | log(50-day mean / 200-day mean) |
| 16 | drawdown | log(P(t) / max of P over t−251..t) |
| 17 | beta to SPY, 252 days | OLS slope of r_i on r_SPY over t−251..t |
| 18 | idiosyncratic volatility, 63 days | standard deviation of the residual of r_i on r_SPY over t−62..t |
| 19 | skewness, 63 days | sample skewness of r over t−62..t |
| 20 | maximum daily return, 21 days | max of r over t−20..t |

SPY is in the panel, so its own beta (#17) is 1 and its idiosyncratic volatility
(#18) is 0 by construction. Both are kept, because the cross-section is what
matters.

## Warm-up and the effective in-sample length

The longest lookback is 252 days (#6, #7, #10, #12, #16, #17), plus 21 for #7's
skip within the same window. **Scoring starts on the first session on which all
40 features exist**, about the start of 2006, and nothing before it is filled.
That shortens the in-sample period from 4,531 to about **4,280 sessions**. The
6.5 pre-registration's preflight (power 0.27 at 4,531) is re-run at the exact
count once it is known from the fetch, before any run. If it fell below the 20%
floor, the registered fallback order applies.

## Missing data

Adjusted closes from a single fetch, and rule 1 of the universe guarantees a bar
every session. Any NaN that still appears in a feature is set to the
cross-sectional mean (0 in either form) for that asset and day, and each
occurrence is counted and reported.
