"""7.5 design analysis: the class's population Sharpes at each level, on design seeds.

Produced `runs/planted_edge_population_levels.json`, which `prereg/planted-edge.md`'s
2026-10-01 amendment reads (whether the planted member is the population-best member,
the class maximum population Sharpe and the count of positive members, per level).

**Analytic, no residual draw**: every number is a population Sharpe under the planted
DGP (`environments.planted_panel.population_sharpes`, the direct per-level batched
pass), on design seeds 640000-640006. Run 2026-10-01, before the closed-form path
existed; `tests/test_planted_panel.py` holds the two paths equal, and the driver's
closed form reproduced this file's figures on seeds 640004 and 640001.

    python experiments/planted_edge_population_levels.py
"""
import json

import numpy as np

from environments import planted_panel as pp
from environments.class_table import CHUNK, canonical

SEEDS = range(640000, 640007)
OUT = "runs/planted_edge_population_levels.json"


def one(args):
    seed, beta = args
    b = pp.load_base()
    P, S = b.in_sample, b.Sigma_is
    m = pp.planted_member(seed, b.members)
    w = pp.member_weights(P, m)
    c = pp.planted_scale(P, S, w, beta)
    sr = np.concatenate([pp.population_sharpes(P, S, w, c, b.members[i:i + CHUNK])
                         for i in range(0, len(b.members), CHUNK)])
    j = int(np.argmax(sr))
    star = b.members.index(m)
    best = b.members[j]
    return {"seed": seed, "beta": beta, "c": c, "planted": [list(p) for p in m],
            "sr_pop_planted": float(sr[star]),
            "class_max_sr_pop": float(sr[j]), "pop_best": [list(p) for p in canonical(best)],
            "planted_is_pop_best": canonical(best) == canonical(m),
            "rank_of_planted": int((sr > sr[star]).sum()) + 1,
            "n_positive": int((sr > 0).sum()),
            "pop_best_shares_two_of_three":
                len(set(canonical(best)) & set(canonical(m))) >= 2}


if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor
    tasks = [(s, b) for b in pp.LEVELS for s in SEEDS]
    with ProcessPoolExecutor(7) as ex:
        rows = list(ex.map(one, tasks))
    json.dump(rows, open(OUT, "w"), indent=1)
    for r in rows:
        print(r["beta"], r["seed"], "SRpop(m*) %+.3f max %+.3f best=m* %s rank %d n>0 %d" % (
            r["sr_pop_planted"], r["class_max_sr_pop"], r["planted_is_pop_best"],
            r["rank_of_planted"], r["n_positive"]))
