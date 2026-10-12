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

## Binance USDT-margined perpetuals, 4h, formation 2021-01, top 50

Entered 2026-10-09 (America/Chicago), with `prereg/binance-panel.md` going live.

| field | value |
|---|---|
| registration | `prereg/binance-panel.md` |
| dataset | Binance USDT-margined perpetuals, 4h, formation 2021-01, top 50 |
| fetched | 2026-10-08 (formation, funding) and 2026-10-09 (4h klines, fill), laptop; manifests in section a |
| derived CSVs | `data/raw/binance_4h_2021-01/`, 190 files; combined SHA-256 `5ae9a12fa37c73b34bbf862029665f2ba1ce0fbac2c0acfbd348e6f60ba31cb8` (`data/binance_4h_2021-01_derived_manifest.json`) |
| grid | 2021-02-01 00:00 – 2025-03-31 20:00 UTC, 9,120 bars |
| scored in-sample | d = 0: earned bars 2021-03-15 08:00 – 2025-03-31 20:00 (8,866; class), stream from 2021-07-20 08:00 (8,104) |
| holdout | 2025-04-01 00:00 – 2026-09-30 20:00; never downloaded to the laptop; 1,660 published CHECKSUMs recorded (`data/binance_4h_2021-01_holdout_checksums.json`) |
| raw zips | `~/Desktop/og-quarantine/binance/` (in-sample only) |
| pinned | d = 0: X `da66f540df2102eed75c9ca2580eb44ccc733835e9cbac0f2bb04a73cf12eafa`, v2 `602325699910ebf3adc4326aaa8c150c993a1e1711a732f5a429a07d5f644164`, costs `9fe8813e06cdd7dc8dd3ac70b5b0d34bd4dd3e7ba0f5d59a2798ae5c482acecf`; d = 1: X `e6ff168cc06dbe795b90d73edfeafad332f886417331f2e921404ad677e8e257`, v2 `47c688ee76ba8e9f5070a31e4ff155a0d702e6e7a72bc99aee5c4e224206e6c5`, costs `74be4b19b9fad50cc878aae82d4b616b1ec93f12026aedf8aa51a45033399789` (arm64) |
| pricing platform | laptop (arm64) only |
| reads so far | outcome-free design quantities, and the book-ticker spread check |
| outcome reads | none |
