"""The registered feature-family map Sancho groups the 40 features by (data only).

A byte-identical copy of `learn.inputs.FAMILIES` and `PAIRS` (model version 1, now under
`research/learn/`), so that Sancho does not import the research record.
`research/tests/test_sancho_families.py` checks the two are equal.
"""
FAMILIES = ((0, 1), (2, 3), (4, 5, 24, 25), (6, 7), (8, 9, 26, 27, 28, 29), (10, 11, 12, 13),
            (14, 15, 16, 17, 18, 19), (20, 21), (22, 23), (30, 31), (32, 33), (34, 35),
            (36, 37), (38, 39))
NF = len(FAMILIES)
PAIRS = tuple((f, g) for f in range(NF) for g in range(f + 1, NF))     # 91, f < g
