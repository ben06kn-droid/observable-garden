# French holdout grading: run record, 2026-10-09

- Registration (LIVE): 4f11f952092831d77c4d8287f083bda12b425f22
- Grader commit (G): 0259c126de737226a9e294b0f60dd848426e7784
- Checklist: `docs/french_holdout_checklist.md` at 1057820637cdc5bf33fca719ff96f201df8c9f21
- Author's go: given 2026-10-09 in session (both runs back to back; host steps [H] run by
  the author in their own terminal, laptop steps [L] by the agent).
- Holdout host: i-0886a189b85d4d051 (c7a.8xlarge), IP 18.216.184.59 (ssh alias og-holdout).

## Steps

1. [L] G is on origin/main (checked 2026-10-09 06:01:49 UTC). LIVE and G recorded above.
2. [author] Host started; IP sent.
3. [L] Zip copied to og-holdout:~/french_holdout/ at 06:01:51 UTC (laptop SHA-256 before
   the copy: 8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de). The laptop
   copy is kept until ZIP-DELETE.
4. [H] The author ran the zip's sha256sum check on the host and saw OK. The output was
   reported to the agent through the confirmation line below, not pasted.
5. ZIP-DELETE. The author's confirmation line, verbatim: "ZIP-DELETE confirmed: host SHA-256 OK
   for 8f394fe3…40de at 06:07:37 UTC; delete the laptop copy." [L] The laptop copy
   (~/Desktop/og-quarantine/french/49_Industry_Portfolios_daily_CSV.zip) was deleted at
   06:07:58 UTC; `ls` of the folder no longer lists it.
6. [L] Target directories created (added step); in-sample CSV, pinned X and the Linux
   LightGBM wheel copied to the host at 06:08:11 UTC.
7. [H] Run by the author. Its output was not pasted back. The step 9 block re-checks HEAD = G,
   a clean tree and LIVE as an ancestor before the split runs.
8. [H] Run by the author. They reported the wheel, in-sample CSV and pinned X sha256sum checks
   all OK, and the last line printing "4.7.0 573d57e8…616a" (abbreviated as reported).
   **Deviation (reported by the author):** `.venv-grading` already existed from the ETF
   grading and has no pip. The wheel was installed with
   `uv pip install --python .venv-grading/bin/python --no-deps <wheel>` instead of
   `.venv-grading/bin/pip install --no-deps <wheel>`. The (added) creation line did nothing,
   because the directory existed. The grader's start-up refusals re-check LightGBM 4.7.0
   and the lib_lightgbm.so SHA-256 in full.
9. [H] Run by the author, the lines pasted one at a time; output pasted back verbatim:
   head-ok, clean-ok, ancestor-ok at HEAD 0259c126de737226a9e294b0f60dd848426e7784; the
   lib_lightgbm.so check printed 4.7.0 573d57e8a2c6290c2271b99b87afa7a802e796eafc9e8d66aefa0913cbc1616a.
   The split printed "holdout CSV written (1674 rows, 20200102 .. 20260831); SHA-256
   3191d79bf0b99c83e0e920508542d949a8d0baf17ba42b743a60c5d2e09157f8; no return value printed".
   holdout.split.json: zip_sha256 8f394fe34bea54d41b9aafed410425ee8f8e252ede3c71a7c1cd20bab83040de,
   holdout_csv_sha256 3191d79bf0b99c83e0e920508542d949a8d0baf17ba42b743a60c5d2e09157f8, rows 1674,
   first_date 20200102, last_date 20260831, registration 4f11f952092831d77c4d8287f083bda12b425f22.
   The holdout CSV stays on the host.
10. [H] Run by the author; output pasted back verbatim: head-ok; "grades written to
    runs/french_holdout/2026-10-09/grades.json; no value printed"; exit=0; grades.json
    1872 bytes, 06:17 host time. No refusal: start-up checks, Option A tolerances and
    no-restart checks all passed (the grader writes grades only after all of them pass).
11. [L] Only grades.json fetched at 06:19:10 UTC (SHA-256 8d3dd68d3ac96e5e4fde906769bf897644cb7fcbcb110ad9d4e5d56fe92c0246). Committed with this record before the read.
