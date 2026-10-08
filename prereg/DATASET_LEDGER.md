# Dataset ledger

One entry per dataset, written before any run on it. Entries are append-only and dated.
Each records the data's identity (hashes), its windows, where the holdout sits, and what
has been read from it.

## French 49 industries, daily, value-weighted

Entered 2026-10-07 (America/Chicago), with `prereg/french-panel.md` going live.

| field | value |
|---|---|
| registration | `prereg/french-panel.md` |
| source | Kenneth R. French Data Library, `49_Industry_Portfolios_daily_CSV.zip`, block "Average Value Weighted Returns -- Daily" (percent) |
| fetched | 2026-10-08 04:04:13 UTC, laptop, once; no `Last-Modified` header returned |
| zip SHA-256 | `8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de` (4,173,817 bytes) |
| in-sample CSV SHA-256 | `1547da6fe357bab194a22ce04ff80effc45ed61c6955325b179213be0b87c04e` (2,771 rows, 2008-12-29 – 2019-12-31) |
| warm-up | 253 rows, 2008-12-29 – 2009-12-29 (3 from 2008), features only |
| scored in-sample | earned dates 2010-01-04 – 2019-12-31 (2,516) |
| holdout | 2020-01-01 – last row of the fetch; 1,674 lines, counted only |
| missing-value codes | none in the in-sample rows |
| pinned X | `data/pinned/french49_X.npy`, SHA-256 `07488718c8c48b6d872c580f1dc3a3c0e87fb8a4c6403131b0beddd55ea3d3fc` (arm64; average ranks for exact ties) |
| pricing platform | laptop (Darwin arm64) only; LightGBM macOS pin |
| zip location | `~/Desktop/og-quarantine/french/`; moves to the holdout host before any agent session or any grading |
| reads so far | outcome-free design quantities only (`522151f`, superseded; `e099d46`) |
| outcome reads | none |
