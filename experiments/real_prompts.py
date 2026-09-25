"""The real-data arms' prompts, read from `prereg/AGENT_PROMPTS_REAL.md`.

Same arrangement as `experiments/e_agent.read_prompts`, for the same reason: the
pre-registration requires byte identity of the shared text across arms, and that
can only be guaranteed if there is **one copy** — the registered one. Nothing
here retypes a prompt.

The file's §2 gives each arm as the control prompt, plus the cost sentence, plus
exactly what that arm adds. This module assembles that and refuses anything it
cannot find, rather than falling back to a default and producing a prompt no
pre-registration authorises.
"""
from __future__ import annotations

import re
from pathlib import Path

from quixote.agent_adapter import CONTENT_TOOLS, META_TOOLS
from quixote.triggers import PREDICATES

PREREG = Path(__file__).resolve().parent.parent / "prereg" / "AGENT_PROMPTS_REAL.md"

ARMS = ("control", "declared-class gate", "prior-weighted", "replay gate",
        "replay gate (reasoned pick)", "orientation")

# §2, pinned: which tools each arm gets. The replay arm's list is the adapter's
# own grammar, so a move added there cannot be missing here.
TOOLS_FOR = {
    "control": ("evaluate", "submit"),
    "declared-class gate": ("evaluate", "submit"),
    "prior-weighted": ("short_list", "evaluate", "submit"),
    # `pick_prior` by amendment 1 of AGENT_PROMPTS_REAL.md, before any run.
    "replay gate": ("pick_prior",) + CONTENT_TOOLS + META_TOOLS + ("predict", "submit"),
    # amendment 3: the same tools; the difference is that the prompt ASKS for a
    # reasoned pick, because 7.3's fidelity measurement has no unit without one.
    "replay gate (reasoned pick)": ("pick_prior",) + CONTENT_TOOLS + META_TOOLS
    + ("predict", "submit"),
    # amendment 6: the same tools again. Orientation changes what the agent is
    # TOLD before it starts, not what it can do.
    "orientation": ("pick_prior",) + CONTENT_TOOLS + META_TOOLS
    + ("predict", "submit"),
}


def read_prompts(path: Path = PREREG) -> dict:
    """The registered text: the control prompt, the cost sentence, and each arm's
    appended block, all read from the pre-registration."""
    text = path.read_text()
    blocks = [b.strip() for b in re.findall(r"```\n(.*?)\n```", text, re.S)]
    names = ("control", "cost", "prior_weighted_suffix", "replay_suffix",
             "reasoned_pick_sentence", "orientation_paragraph")
    if len(blocks) != len(names):
        raise ValueError(
            f"expected exactly {len(names)} fenced blocks in {path.name} "
            f"({', '.join(names)}), found {len(blocks)}")
    return dict(zip(names, blocks))


def build_prompt(control: str, M: int, K: int, d: int) -> str:
    out = control.replace("{M}", str(int(M))).replace("{K}", str(int(K))) \
                 .replace("{d}", str(int(d)))
    left = re.findall(r"\{[A-Za-z_]+\}", out)
    if left:
        raise ValueError(f"unsubstituted placeholders remain: {left}")
    return out


def system_prompt_for(arm: str, M: int, K: int, d: int,
                      prompts: dict | None = None,
                      orientation_table: str | None = None) -> str:
    """Control prompt + cost sentence + exactly what the arm adds (§2).

    `declared-class gate` adds nothing: §2 records that the gate is applied by
    the harness after the run and is not described to the agent, so its prompt is
    byte-identical to control's. That identity is a test, not a convention.
    """
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}; the registered arms are {list(ARMS)}")
    prompts = prompts or read_prompts()
    base = build_prompt(prompts["control"], M, K, d) + "\n\n" + prompts["cost"]
    if arm == "prior-weighted":
        return base + "\n\n" + prompts["prior_weighted_suffix"]
    if arm == "replay gate":
        return base + "\n\n" + prompts["replay_suffix"]
    if arm == "replay gate (reasoned pick)":
        return (base + "\n\n" + prompts["replay_suffix"] + "\n\n"
                + prompts["reasoned_pick_sentence"])
    if arm == "orientation":
        if orientation_table is None:
            raise ValueError(
                "the orientation arm's prompt carries a table; pass the rendered "
                "table from quixote.orientation, which is built from the feature "
                "matrix alone (prereg/agent-cell.md)")
        return (base + "\n\n" + prompts["replay_suffix"] + "\n\n"
                + prompts["orientation_paragraph"].replace("{orientation_table}",
                                                           orientation_table))
    return base


def registered_triggers() -> tuple[str, ...]:
    """The trigger library, from the code. §2's replay block names these, and the
    test compares the two so prompt and library cannot drift."""
    return tuple(PREDICATES)
