# 6.5 ETF universe: the candidate list and the inclusion rule

**DRAFT for the universe commit.** Committed alone and before any bar is opened,
so the fetch has a hash to run against. It fixes **what is fetched and how the
panel is chosen from it**, by a rule applied mechanically. It does not fix the
features, which are the next commit.

## Candidates: 40, chosen before any data

The list is from general knowledge of fund histories and is not checked against
any price or volume. **The inclusion rule below, applied to the fetch, decides
the panel; this list does not.** Where memory of an inception date is wrong, the
rule drops the fund and the drop is recorded.

| group | tickers | n |
|---|---|---|
| broad US equity | SPY, QQQ, DIA, IWM, MDY | 5 |
| size and style | IWD, IWF, IWN, IWO, IJH, IJR | 6 |
| US sectors (Select Sector SPDRs) | XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY | 9 |
| developed international | EFA, EWJ, EWG, EWU, EWC, EWA, EWH | 7 |
| emerging and Asia | EEM, EWZ, EWT, EWY | 4 |
| US Treasuries | SHY, IEF, TLT | 3 |
| credit and inflation-linked | LQD, TIP, AGG | 3 |
| real assets | GLD, IYR, VNQ | 3 |
| **total** | | **40** |

Four candidates have inception dates remembered as late 2003 to late 2004 (AGG,
TIP, GLD, VNQ). They are the ones most likely to fail rule (a), and are kept
because the rule, not memory, decides.

## Inclusion rule, applied to the single fetch on the holdout host

A candidate is in the panel iff **all** of:

1. **Continuous history.** Its first daily bar is on or before 2005-01-03, and it
   has a bar on every NYSE session from 2005-01-03 to 2025-12-31, with no gap
   longer than one session. The exchange calendar is pinned in the manifest.
2. **Liquidity, in-sample only, from share volume.** Its median daily **share**
   volume over **2005-01-03 to 2022-12-31** is at least **500,000 shares**. The
   holdout's volume is not consulted.
3. **One ticker throughout.** No ticker change, merger or fund-structure change
   inside 2005–2025. This is checked against issuer records, **not** against the
   fetch.

**What the rule reads: bar dates and share volume. Nothing else.** Rule 1 reads
only which sessions have a bar. Rule 2 reads only the volume column. Rule 3 reads
no data. **No price is read**, not a close level and not a return. That is why
liquidity is in shares, not dollars: dollar volume would need the close. The cost
is that the "under 0.1% of volume" guarantee becomes approximate. At $25,000 a
position, 500,000 shares keeps a position under 0.1% of median volume for any
price above $50 a share, and under 0.5% down to $10. At the registered $1
million notional, impact stays negligible either way, which is what the
execution assumption states.

**Applied once, recorded as a look.** The per-candidate pass or fail, with the
failing criterion, goes in `data/etf_manifest.json`. This is the one look at the
data before the feature commit.

**No replacements, and a minimum panel.** If fewer than 40 pass, the panel is
smaller and nothing is added after the rule has been applied. **The minimum
accepted panel is 30 assets**, three quarters of the candidate list. Below that
the panel no longer has the designed mix of equity, bond and real-asset exposure,
so 6.5 does not go live as registered, and a new universe commit is needed. At 30
or more, K and the class are unchanged and the shortfall is reported.

## Survivorship

Rule 1 requires survival through 2025-12-31, so the panel is conditioned on
survival through the holdout (`prereg/agent-on-real-data.md`, "Survivorship").
Stated, not corrected.

## Download list

The 40 candidates, from the single fetch, 2005-01-01 to 2025-12-31, daily, with
adjusted close, close and volume.
