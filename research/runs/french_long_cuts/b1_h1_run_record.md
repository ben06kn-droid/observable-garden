# French long history, H1: the host cut for B1, run record, 2026-10-11

**The registration:** `prereg/french-long-history.md`, live at `756af89`.
**The script:** `data/french_long_split.py` (blob `ddaad1cd…`, last changed at `dab1ac0`).
**Run by the author** on the holdout host (`i-0886a189b85d4d051`, IP 3.138.193.165), in his own
terminal. No agent session ran on the host.

## Deviation: a first pass on the old commit

- The first pass ran the checks and the cut before the checkout had succeeded:
  - the ancestor check printed nothing;
  - the cut failed with "No module named data.french_long_split";
  - **no file was written.**
- **The checkout was blocked** by the untracked `runs/french_holdout/2026-10-09/grades.json`.
  - Its `git hash-object` equalled the committed blob `629026bfbdaa3bcd8645c9b3dca7541361a2363e`
    (checked on the laptop: `git rev-parse b541ddf:runs/french_holdout/2026-10-09/grades.json`
    gives the same blob).
  - It was moved to `~/moved_aside/grades.json.2026-10-11` ("moved-identical").

## After the checkout (the author's outputs)

- `git rev-parse HEAD`: `b541ddf7d1b1ff9eb02b42c2b51ee3e7314ab498`.
- `git merge-base --is-ancestor 756af89… HEAD`: `ancestor-ok`.
- `git status --porcelain --untracked-files=no | wc -l`: `0`. This was run after the cut, not
  captured right after the checkout. The cut writes only under `~/french_long`, outside the
  repository.
- The zip check (`sha256sum -c`): `/home/ubuntu/french_holdout/49_Industry_Portfolios_daily_CSV.zip: OK`.
- The cut: `b1: 17084 rows 19260701 .. 19891229; SHA-256 c380c3eaa578734a4de8c019220b5babce9c2e6adc3f7a6175a68999d4910693; record b1_insample.cut.json; no value printed`.

**The cut line appeared twice in the author's terminal. Not explained.**
- `ls -l ~/french_long/` shows exactly one `b1_insample.csv` (4,471,350 bytes) and one
  `b1_insample.cut.json` (54,571 bytes), both at 12:40 host time.
- `sha256sum` on the host gives `c380c3ea…0693`, the printed hash.
- The script refuses an existing output before writing anything, so a second successful
  write cannot have happened. No refusal message was seen, so the cause of the repeated line
  is unknown.

## The copy and its check (laptop)

- `scp` of both files to `runs/french_long_cuts/`. The sizes match the host's.
- `shasum -a 256 runs/french_long_cuts/b1_insample.csv` gives
  `c380c3eaa578734a4de8c019220b5babce9c2e6adc3f7a6175a68999d4910693`. That equals the host's
  `sha256sum` and the record's `csv_sha256`. **Verified.**
- The CSV is gitignored (`runs/french_long_cuts/*.csv`, `a85d87b`) and is not committed.
- **Committed:** the cut record `b1_insample.cut.json`. It holds hashes, the row count, first
  and last dates, missing-cell counts per industry per year, the first date all 49 are
  present (1969-07-01) and each industry's entry date by rule (ii). **It holds no value.**

## Note: the row count against the registration's "about 16,000"

- The cut has **17,084 rows**. Sections b, f and g of the registration say "about 16,000"
  for B1. The design table and the smoke were computed at 16,000.
- Rows per decade from the record: 1920s (from July 1926) 1,037; 1930s 2,988; 1940s 2,918;
  1950s 2,598; 1960s 2,489; 1970s 2,526; 1980s 2,528.
- The 1930s and 1940s are about 400–500 rows a decade above the later decades. That is consistent
  with Saturday sessions, but **this was not checked.**
- **No registered rule changes:**
  - the rules are stated as p thresholds, not as row counts;
  - W2's effective length (h = 1,260) does not depend on n.
- The B1 Sancho and class times scale up roughly with n, about 7% above the estimates in
  section g.

## Entry dates by rule (ii), from the record (dates only)

- 36 industries enter at 1926-07-01.
- The other 13 enter on these dates:
  - 1927-05-18, 1931-04-21, 1933-08-07, 1935-11-19, 1941-07-14, 1945-06-30, 1945-09-15: one each;
  - 1963-07-01: four;
  - 1969-07-01, 1971-03-12: one each.
- None is missing.
- After BOX-B1, these are compared with `pins.json`'s entry dates. That comparison is a check,
  not a rule.
