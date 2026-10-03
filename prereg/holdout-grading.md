# holdout-grading (6.9): grading 6.5's 80 submissions on the sealed ETF holdout

**DRAFT — committed, not live. Nothing runs on it, and nothing in it opens the holdout.**
It fixes the grading sequence before anyone is in a position to vary it after seeing a
number. It goes live by a dated commit once the build items below exist and pass their
tests.

## Question

How do 6.5's submissions perform on the sealed 2023–2025 holdout, gross and net? The
registered readouts are in `prereg/agent-on-real-data.md`: holdout Sharpe of PASS
against FAIL submissions, gross and net at 5 and 10 bps. **6.5 issued no PASS**
(class tier 0/80), so the PASS side is reported as "no PASS". The FAIL side is graded on
its own: whether anything the gate refused would have earned out of sample.

## What is graded

**80 submissions**, one per run, 20 per arm:

| arm | run directory | logs / priced |
|---|---|---|
| control | `runs/etf_control` | `3f6c189` |
| declared-class gate | `runs/etf_declared_class` | `3f6c189` |
| replay gate | `runs/etf_replay` | `62644b8` / `43cd139` |
| orientation | `runs/etf_orientation` | `62644b8` / `43cd139` |

Three arms ran at 20 against a registered 40 (`agent-on-real-data.md`, deviation of
2026-10-02). There are 80 submissions, not 120.

## The sequence — one direction of travel

Repository to holdout host: **one sealed submissions file and code at one commit**.
Holdout host to repository: **grades**. Nothing else crosses, in either direction, at
any step.

1. **Seal the submissions by commit, before the holdout is opened.**
   `experiments/collect_submissions.py --dirs runs/etf_control runs/etf_declared_class
   runs/etf_replay runs/etf_orientation` writes the 80 `{name, weights}` objects, built
   with the gate's own `quixote.grammar.weights`. The file is committed and pushed as
   commit **S**. Its SHA-256 and S are written into this file by a dated commit **before
   step 3**. After S, no submission, run file or weight rule changes.
2. **Fix the grading code by commit.** The grading code, the feature build and this file
   are at commit **G**, with S an ancestor of G. G is recorded here.
3. **The holdout is made plaintext on the holdout host — not by this sequence.** The
   operator does that by hand, as `agent-on-real-data.md` describes. **No step here
   decrypts anything.** `grade_real` has no decryption step and refuses `.enc`, `.gpg`,
   `.asc` and any `~/Desktop` path.
4. **Ancestor-commit guard.** `grade_real.require_sealed_submissions(S)` refuses unless S
   is in the repository and an ancestor of HEAD. HEAD on the holdout host must equal G
   with a clean tracked tree; a different HEAD or a dirty tree refuses (build item 1).
5. **Content-hash check.** Before any price is read:
   - every holdout CSV's SHA-256 must equal its entry in the single fetch's manifest
     (`data/etf_manifest.json`, recorded at the fetch);
   - the submissions file's SHA-256 must equal the one recorded in step 1.

   Any mismatch refuses, and nothing is graded (build item 2).
6. **Features built once, on one pinned platform, over in-sample and holdout together.**
   `_rank` breaks exact ties by numpy's unstable sort, whose order differs between x86
   and arm64 (recorded 2026-10-02 in `agent-on-real-data.md`, `planted-edge.md` and
   `twin-calibration.md`). So the whole span — the in-sample lookback **and** the
   holdout — is built in **one** build on the holdout host (x86_64). The build's
   platform and its feature matrix's SHA-256 are written beside the grades.
   - **Today `grade_real.grade` builds features from the holdout prices alone.** The
     252-day lookback then leaves 2023 without features, and the build differs from the
     in-sample one. Build item 3 replaces it with one build over 2005–2025 that grades
     2023-01-01 to 2025-12-31.
   - **Tie-affected submissions:** `ret1_rank` and `drawdown_rank` break ties
     differently on x86 from the arm64 in-sample build the agents searched. **Control
     run 8 is the only submission containing either**, and its grade carries that note.
7. **Grade.** Each submission's holdout Sharpe, gross and net at **5 and 10 bps** one-way
   plus the registered borrow, under the registered execution (signal at the close of
   t, held from the close of t+1 to t+2).
8. **Grades travel back, and are committed.** The grades file — submission name, gross
   and net Sharpe, number of periods, platform, feature-matrix SHA-256, S and G — is
   copied to the repository and committed **unread** as commit **R**, by the
   fetch-commit-read pattern 7.5 and the twin cell used. The read is a separate step,
   by a reader committed and tested on synthetic files before R exists.
9. **No step shuts anything down.** Stopping or terminating the holdout host is the
   operator's action, after R is pushed. It is not part of this sequence and no command
   here issues it.

**Not re-graded.** Once R exists, a change to the grading code, the feature build or the
cost model is a new, separately registered grading, reported beside R and never in
place of it.

## Build items, before the live commit

1. `grade_real`: refuse unless HEAD equals the recorded G and the tracked tree is clean.
2. `grade_real`: the content-hash check of step 5, against `data/etf_manifest.json` and
   the recorded submissions hash.
3. `grade_real.grade`: one feature build over in-sample and holdout together, grading
   2023-01-01 to 2025-12-31 only, writing platform and matrix SHA-256 beside the grades;
   and 10 bps beside 5 bps.
4. The reader, committed and tested on synthetic grades files before R.

## Cost

Minutes on the holdout host (c7a.8xlarge `i-0886a189b85d4d051`): one feature build and 80
gradings. No seat cost.
