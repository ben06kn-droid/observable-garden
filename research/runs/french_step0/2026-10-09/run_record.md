# French holdout grading, step 0: run record, 2026-10-09

**The draft:** `prereg/french-holdout-grading.md` (DRAFT, NOT LIVE), section 4, step 0.
**The script:** `experiments/french_step0.py` (`2c0f25b`). It is in-sample only, and **no
holdout row was read**: the loader refuses any row dated 2020 or later, and the script
refuses a panel that reaches 2020.

1. **The laptop reference** (Darwin arm64, the macOS LightGBM pin), before the box
   session: `reference.json` and `ref_positions.npy` (ridge_stack on the pinned French X).
2. **The box comparison** (c7a.48xlarge, Linux x86_64, the Linux LightGBM pin), in the
   second version-2 pilot's session, after the pilot was fetched and before the stop. The
   box was at HEAD `704241a9311bb0cc703b0bd64eea7f9612777bfe`.
   - The French in-sample CSV (`1547da6f…c04e`) and the pinned X (`07488718…d3fc`) were
     copied and checked with `sha256sum -c` (OK).
   - **Output:** `step0.txt` and `step0.json` (SHA-256
     `dbd6d3fdb9692aa57a2e9231314c59c2ef1af101afad3b47595f2ca586c0a7e3`).
   - **PASS on all four Option A tolerances:**
     - z-features: largest difference 6.223e-14;
     - rank entries differing: 2 of 2,465,680;
     - member 2937: 0.679;
     - ridge_stack: 0.547.
   - **ridge_stack's refits:** penalties differed on 0 of 7; stack weights differed on 7 of
     7 (by more than 1e-9); the positions correlate with the laptop's at 1.000000.

These outputs were first committed with the pilot's raw outputs (`4a0e621`). This record
is added on 2026-10-09.
