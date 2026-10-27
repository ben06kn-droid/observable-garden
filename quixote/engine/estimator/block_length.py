"""Politis-White optimal block length, vendored from `arch` for environments without it.

`estimator.bootstrap.select_block_length` needs one function from `arch`,
`arch.bootstrap.optimal_block_length`. `arch` ships compiled extensions and has no build for
Pyodide, where the gate runs in a visitor's browser, so this module carries a port of that one
function.

`estimator/bootstrap.py` is left exactly as tagged: it is moved research code, and
`research/tests/test_pins_after_cleanup.py` holds it to the pre-cleanup text. So it still says
`from arch.bootstrap import optimal_block_length`, and where `arch` is absent the browser calls
`install_as_arch()` below before importing the package, which registers this port under that
name. Where `arch` is installed (the desktop path, and every registered result) nothing is
registered and `arch` itself runs.

The port follows `arch.bootstrap.base._single_optimal_block` and `optimal_block_length` (arch
8.0.0) line by line, so the numbers agree; `tests/test_block_length.py` holds the two equal to
1e-12 on several kinds of input whenever `arch` is installed.

The method:

- Dimitris N. Politis & Halbert White (2004). Automatic Block-Length Selection for the Dependent
  Bootstrap. Econometric Reviews 23(1), 53-70. doi:10.1081/ETC-120028836.
- Andrew Patton, Dimitris N. Politis & Halbert White (2009). Correction to "Automatic
  Block-Length Selection for the Dependent Bootstrap" by D. Politis and H. White. Econometric
  Reviews 28(4), 372-375. doi:10.1080/07474930802459016.

Licence of the code this is ported from (arch, University of Illinois/NCSA Open Source Licence):

    Copyright (c) 2017 Kevin Sheppard. All rights reserved.

    Developed by: Kevin Sheppard (<kevin.sheppard@economics.ox.ac.uk>,
    <kevin.k.sheppard@gmail.com>)
    https://www.kevinsheppard.com

    Permission is hereby granted, free of charge, to any person obtaining a copy of
    this software and associated documentation files (the "Software"), to deal with
    the Software without restriction, including without limitation the rights to
    use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
    of the Software, and to permit persons to whom the Software is furnished to do
    so, subject to the following conditions:

    Redistributions of source code must retain the above copyright notice, this
    list of conditions and the following disclaimers.

    Redistributions in binary form must reproduce the above copyright notice, this
    list of conditions and the following disclaimers in the documentation and/or
    other materials provided with the distribution.

    Neither the names of Kevin Sheppard, nor the names of its contributors may be
    used to endorse or promote products derived from this Software without specific
    prior written permission.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    CONTRIBUTORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS WITH
    THE SOFTWARE.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _single_optimal_block(x: np.ndarray) -> tuple[float, float]:
    """The optimal window length for one series: (stationary, circular). arch's
    `_single_optimal_block`, statement for statement."""
    nobs = x.shape[0]
    eps = x - x.mean(0)
    b_max = np.ceil(min(3 * np.sqrt(nobs), nobs / 3))
    kn = max(5, int(np.log10(nobs)))
    m_max = int(np.ceil(np.sqrt(nobs))) + kn
    # Find first collection of kn autocorrelations that are insignificant
    cv = 2 * np.sqrt(np.log10(nobs) / nobs)
    acv = np.zeros(m_max + 1)
    abs_acorr = np.zeros(m_max + 1)
    opt_m: int | None = None
    for i in range(m_max + 1):
        v1 = eps[i + 1:] @ eps[i + 1:]
        v2 = eps[: -(i + 1)] @ eps[: -(i + 1)]
        cross_prod = eps[i:] @ eps[: nobs - i]
        acv[i] = cross_prod / nobs
        abs_acorr[i] = np.abs(cross_prod) / np.sqrt(v1 * v2)
        if i >= kn:
            if np.all(abs_acorr[i - kn: i] < cv) and opt_m is None:
                opt_m = i - kn
    m = 2 * max(opt_m, 1) if opt_m is not None else m_max
    m = min(m, m_max)

    g = 0.0
    lr_acv = acv[0]
    for k in range(1, m + 1):
        lam = 1 if k / m <= 1 / 2 else 2 * (1 - k / m)
        g += 2 * lam * k * acv[k]
        lr_acv += 2 * lam * acv[k]
    d_sb = 2 * lr_acv**2
    d_cb = 4 / 3 * lr_acv**2
    b_sb = ((2 * g**2) / d_sb) ** (1 / 3) * nobs ** (1 / 3)
    b_cb = ((2 * g**2) / d_cb) ** (1 / 3) * nobs ** (1 / 3)
    b_sb = min(b_sb, b_max)
    b_cb = min(b_cb, b_max)
    return b_sb, b_cb


def optimal_block_length(x) -> pd.DataFrame:
    """Optimal block lengths column by column, as arch returns them: a DataFrame with columns
    `stationary` and `circular`, indexed like the input (a 1-d input is one column)."""
    x_arr = np.asarray(x, dtype=float)
    if x_arr.ndim == 1:
        x_arr = x_arr[:, None]
    elif x_arr.ndim != 2:
        raise ValueError("x must be 1 or 2-dimensional")
    opt = [_single_optimal_block(col) for col in x_arr.T]
    if isinstance(x, pd.DataFrame):
        idx = list(x.columns)
    elif isinstance(x, pd.Series):
        idx = [x.name]
    else:
        idx = list(range(x_arr.shape[1]))
    return pd.DataFrame(opt, index=idx, columns=["stationary", "circular"])


def install_as_arch() -> bool:
    """Make `from arch.bootstrap import optimal_block_length` resolve to this port, if and only if
    `arch` cannot be imported. Call it before importing `estimator.bootstrap`. Returns whether the
    port was installed (False: the real `arch` is present and is used)."""
    import importlib
    import sys
    import types
    try:
        importlib.import_module("arch.bootstrap")
        return False
    except ImportError:
        pass
    arch = types.ModuleType("arch")
    arch.__doc__ = "Stand-in for arch: only bootstrap.optimal_block_length, from estimator.block_length."
    boot = types.ModuleType("arch.bootstrap")
    boot.optimal_block_length = optimal_block_length
    arch.bootstrap = boot
    sys.modules["arch"], sys.modules["arch.bootstrap"] = arch, boot
    return True
