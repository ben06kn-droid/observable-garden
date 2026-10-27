"""The vendored Politis-White block length (estimator/block_length.py) against arch's.

`estimator.bootstrap` uses arch when it is installed; the browser, which has no arch, installs the
vendored port under arch's name first (`install_as_arch`). These hold the two equal to 1e-12, so a verdict computed without arch uses the same
block length as one computed with it. Skipped when arch is absent: there is nothing to compare.
"""
import numpy as np
import pytest

arch_bootstrap = pytest.importorskip("arch.bootstrap")

from estimator import block_length as vendored  # noqa: E402


def _both(x):
    a = arch_bootstrap.optimal_block_length(x)
    v = vendored.optimal_block_length(x)
    assert list(a.columns) == list(v.columns) == ["stationary", "circular"]
    assert list(a.index) == list(v.index)
    return a.to_numpy(), v.to_numpy()


def _ar(rng, T, N, phi):
    e = rng.standard_normal((T, N))
    x = np.zeros_like(e)
    for t in range(1, T):
        x[t] = phi * x[t - 1] + e[t]
    return x


CASES = {
    "white noise": lambda rng: rng.standard_normal((600, 12)),
    "AR(0.3)": lambda rng: _ar(rng, 600, 8, 0.3),
    "AR(0.9), long": lambda rng: _ar(rng, 3000, 3, 0.9),
    "one column": lambda rng: rng.standard_normal((400, 1)),
    "1-d input": lambda rng: _ar(rng, 500, 1, 0.5)[:, 0],
    "short, at the rule's edge": lambda rng: rng.standard_normal((12, 4)),
    "heavy tails": lambda rng: rng.standard_t(3, size=(800, 5)),
}


@pytest.mark.parametrize("name", list(CASES))
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_vendored_equals_arch(name, seed):
    a, v = _both(CASES[name](np.random.default_rng(seed)))
    np.testing.assert_allclose(v, a, rtol=0, atol=1e-12)


def test_zero_variance_column_matches_arch():
    rng = np.random.default_rng(3)
    x = rng.standard_normal((300, 4))
    x[:, 2] = 0.25                      # a rule that never trades: arch returns NaN here, and so must the port
    with np.errstate(all="ignore"):
        a, v = _both(x)
    np.testing.assert_allclose(v, a, rtol=0, atol=1e-12, equal_nan=True)
    assert np.isnan(v[2]).all() == np.isnan(a[2]).all()


def test_dataframe_index_kept():
    pd = pytest.importorskip("pandas")
    rng = np.random.default_rng(4)
    df = pd.DataFrame(rng.standard_normal((200, 3)), columns=["a", "b", "c"])
    a, v = _both(df)
    np.testing.assert_allclose(v, a, rtol=0, atol=1e-12)


def test_select_block_length_same_with_either(monkeypatch):
    """The function the gate calls gives the same integer whichever implementation it uses."""
    import estimator.bootstrap as eb
    rng = np.random.default_rng(5)
    R = _ar(rng, 600, 30, 0.2)
    with_arch = eb.select_block_length(R)
    monkeypatch.setattr(eb, "optimal_block_length", vendored.optimal_block_length)
    assert eb.select_block_length(R) == with_arch


def test_install_as_arch_is_a_no_op_with_arch():
    assert vendored.install_as_arch() is False
    import arch.bootstrap
    assert arch.bootstrap.optimal_block_length is arch_bootstrap.optimal_block_length


def test_without_arch_the_gate_uses_the_port_and_prints_the_same(tmp_path):
    """In a fresh interpreter with arch unimportable, install_as_arch() puts the port under arch's
    name, estimator.bootstrap picks it up unchanged, and `quixote example --json` prints exactly
    what it prints with arch."""
    import subprocess
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    env_path = f"{repo}:{repo / 'quixote' / 'engine'}"
    blocked = (
        "import sys, importlib.abc\n"
        "class B(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, n, p, t=None):\n"
        "        if n.split('.')[0] == 'arch': raise ImportError(n)\n"
        "sys.meta_path.insert(0, B())\n"
        "import estimator.block_length as bl\n"
        "assert bl.install_as_arch()\n"
        "import estimator.bootstrap as eb\n"
        "assert eb.optimal_block_length is bl.optimal_block_length\n"
        "import runpy; sys.argv = ['quixote', 'example', '--json']\n"
        "runpy.run_module('quixote.cli', run_name='__main__')\n")
    run = lambda code: subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                                      cwd=repo, env={"PYTHONPATH": env_path, "PATH": "/usr/bin:/bin"})
    without = run(blocked)
    with_arch = run("import sys, runpy; sys.argv = ['quixote', 'example', '--json']\n"
                    "runpy.run_module('quixote.cli', run_name='__main__')\n")
    assert without.stderr == "" or "Traceback" not in without.stderr, without.stderr
    assert without.stdout and without.stdout == with_arch.stdout
