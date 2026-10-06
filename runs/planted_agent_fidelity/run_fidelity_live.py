"""Check 2 for 7.5 stage 2: fidelity.py's live, stateless, forced-choice presentations on
the reasoned-pick arm, as registered (every accepted pick, and the stop and restart
moves of the first 10 runs per level in seed order, 20 presentations each).

It writes ONLY the presentation log and computes no agreement rate; the rate is
experiments/fidelity_read.py's (pinned f948ead), run at the read. Resumable: a line
already in the log is not presented again.

    python runs/planted_agent_fidelity/run_fidelity_live.py
"""
import glob, json, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from experiments import fidelity as fd

OUT = Path(__file__).resolve().parent / "fidelity_live_presentations.jsonl"
N_PRES = 20
files = sorted(glob.glob("runs/planted_agent/cell_planted_*replay_gate_(reasoned_pick)_*.json"))
decs = []
for f in files:
    seed = json.load(open(f))["seed"]
    decs += fd.decisions_of(Path(f), ("pick",))
    if seed < 630010:
        decs += fd.decisions_of(Path(f), ("stop", "restart"))
done = set()
if OUT.exists():
    for ln in OUT.read_text().splitlines():
        r = json.loads(ln); done.add((r["run_id"], r["step"], r["kind"], r["rep"]))
todo = [(d, rep) for d in decs for rep in range(N_PRES)
        if (d["run_id"], d["step"], d["kind"], rep) not in done]
print(f"decisions {len(decs)}; presentations {len(decs) * N_PRES}; already logged {len(done)}; "
      f"model calls now {len(todo)}", flush=True)
lock = threading.Lock()

def one(item):
    d, rep = item
    shown = fd.resampled_shown(d, "planted", rep)
    resp = fd.LiveResponder(fd.system_prompt_of, client=fd.sdk_client)
    resp(d, shown)
    rec = dict(resp.log[0]); rec["rep"] = rep; rec["level"] = d["start"]["level"]
    with lock:
        with open(OUT, "a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")

with ThreadPoolExecutor(max_workers=4) as pool:
    for i, _ in enumerate(pool.map(one, todo), 1):
        if i % 100 == 0:
            print(f"  {i}/{len(todo)} presented", flush=True)
print("done", flush=True)
