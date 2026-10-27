"""estimator/scipy_lite.py, the browser's stand-in for the scipy functions the audit path imports,
against scipy itself. Skipped where scipy is absent: there is nothing to compare."""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

scipy_special = pytest.importorskip("scipy.special")
from scipy import integrate, optimize, stats  # noqa: E402

from estimator import scipy_lite as lite  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
X = np.concatenate([np.linspace(-40, 40, 4001), [-38.5, -37.5, -20.0001, -19.9999, -8.3, -6.0001, -5.9999,
                                                  -1e-300, 0.0, 1e-300, 5.9999, 6.0001, 8.3, 9.4, 37.0]])
P = np.concatenate([np.logspace(-300, -1, 600), np.linspace(0.01, 0.99, 981),
                    1 - np.logspace(-1, -15.5, 300), [1e-320, 0.425 + 0.5, 0.5 - 0.425, 0.5]])


def close(a, b, tol):
    np.testing.assert_allclose(np.asarray(a, float), np.asarray(b, float), rtol=tol, atol=0)


def test_cdf_sf_pdf_match_scipy_to_1e_14():
    close(lite.norm.cdf(X), stats.norm.cdf(X), 1e-14)
    close(lite.norm.sf(X), stats.norm.sf(X), 1e-14)
    close(lite.norm.pdf(X), stats.norm.pdf(X), 1e-14)
    close(lite.ndtr(X), scipy_special.ndtr(X), 1e-14)


def test_log_ndtr_matches_scipy_to_1e_14_including_the_far_tail():
    xs = np.concatenate([X, -np.logspace(1.31, 3, 200)])      # past -20, the asymptotic series
    close(lite.log_ndtr(xs), scipy_special.log_ndtr(xs), 1e-14)


def test_ppf_and_ndtri_match_scipy_to_1e_14_including_the_tails():
    close(lite.norm.ppf(P), stats.norm.ppf(P), 1e-14)
    close(lite.ndtri(P), scipy_special.ndtri(P), 1e-14)
    assert lite.ndtri(0.0) == -np.inf and lite.ndtri(1.0) == np.inf and np.isnan(lite.ndtri(1.5))


def test_scalars_come_back_as_numpy_floats_like_scipy():
    for f, g in [(lite.norm.cdf, stats.norm.cdf), (lite.ndtri, scipy_special.ndtri)]:
        a, b = f(0.3), g(0.3)
        assert np.ndim(a) == np.ndim(b) == 0 and isinstance(a, np.floating)


def test_brentq_matches_scipy_to_1e_12():
    cases = [(lambda x: x ** 3 - 2 * x - 5, 2, 3), (lambda x: np.cos(x) - x, 0, 1),
             (lambda x: np.exp(x) - 10, -5, 10), (lambda x: x - 1e-9, -1, 1),
             (lambda x: lite.norm.cdf(x) - 0.975, -10, 20), (lambda x: np.tanh(50 * (x - 0.3)), -2, 3)]
    for f, a, b in cases:
        close(lite.brentq(f, a, b), optimize.brentq(f, a, b), 1e-12)
    with pytest.raises(ValueError):
        lite.brentq(lambda x: x * x + 1, -1, 1)


def test_trapezoid_matches_scipy_to_1e_12():
    rng = np.random.default_rng(0)
    y, x = rng.standard_normal(501), np.sort(rng.uniform(-3, 3, 501))
    close(lite.trapezoid(y, x), integrate.trapezoid(y, x), 1e-12)
    close(lite.trapezoid(y, dx=0.1), integrate.trapezoid(y, dx=0.1), 1e-12)


def test_what_it_does_not_provide_fails_loudly():
    with pytest.raises(AttributeError, match=r"scipy\.stats\.norm\.logcdf.*scipy_lite\.py"):
        lite.norm.logcdf(0.0)
    mod = lite._stand_in("scipy.stats", {"norm": lite.norm})
    with pytest.raises(AttributeError, match=r"scipy\.stats\.t; extend quixote/engine/estimator/scipy_lite\.py"):
        mod.t


def test_install_as_scipy_is_a_no_op_with_scipy():
    assert lite.install_as_scipy() is False


_BROWSER_LIKE = """
import sys, importlib.abc
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, n, p, t=None):
        if n.split('.')[0] in ('arch', 'scipy'): raise ImportError(n)
sys.meta_path.insert(0, Block())
import estimator.block_length as bl, estimator.scipy_lite as sl
assert bl.install_as_arch() and sl.install_as_scipy()
{body}
"""


def _run(code):
    env = {"PYTHONPATH": f"{REPO}:{REPO / 'quixote' / 'engine'}", "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO, env=env)


def test_missing_names_name_the_file_in_a_from_import():
    r = _run(_BROWSER_LIKE.format(body="from scipy.stats import t"))
    assert "cannot import name 't' from 'scipy.stats'" in r.stderr and "scipy_lite.py" in r.stderr


@pytest.mark.parametrize("log,panel", [("scripted_session.json", "tiny_panel.npz"),
                                       ("planted_session.json", "tiny_panel_planted.npz"),
                                       ("restart_session.json", "tiny_panel.npz")])
def test_the_gate_without_scipy_or_arch_gives_the_cli_verdict(log, panel):
    """With both stand-ins registered (what the browser ships), every example audits to the same
    status and p values as with scipy and arch, and the other numbers within 1e-12."""
    body = (f"import json, quixote.audit as A\n"
            f"r = A.audit_log('examples/logs/{log}', 'examples/data/{panel}', 'examples/class.json', B=300, seed=0)\n"
            f"assert 'scipy' in sys.modules and sys.modules['scipy'].__version__ == '0+scipy_lite'\n"
            f"print(json.dumps(r.to_dict()))")
    lite_run = _run(_BROWSER_LIKE.format(body=body))
    assert lite_run.returncode == 0, lite_run.stderr
    import json
    from quixote import audit as A
    got = json.loads(lite_run.stdout)
    want = A.audit_log(REPO / "examples/logs" / log, REPO / "examples/data" / panel, REPO / "examples/class.json",
                       B=300, seed=0).to_dict()
    assert got["status"] == want["status"] and got["p_replay"] == want["p_replay"] and got["p_class"] == want["p_class"]
    assert got["reasons"] == want["reasons"]
    for k in ("submitted_sharpe", "class_bar"):
        assert abs(got[k] - want[k]) <= 1e-12 * max(1.0, abs(want[k]))
