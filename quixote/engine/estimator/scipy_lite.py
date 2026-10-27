"""The few scipy functions the audit path imports, for environments without scipy (the browser).

An audit under Pyodide would otherwise download scipy (13.8 MB, half the first visit) for what
it actually uses: `quixote/confidence.py` calls `norm.cdf` once per verdict, and
`garden/power.py` imports `brentq`, `trapezoid`, `log_ndtr`, `ndtri` and `norm` when it loads
(calling `norm.pdf` at import) though an audit never calls its functions. Both files stay as they
are (`garden/power.py` is moved research code, pinned by
`research/tests/test_pins_after_cleanup.py`).

`install_as_scipy()` registers this module's functions under scipy's names **only where scipy
cannot be imported**; the browser calls it before importing the package, as it calls
`estimator.block_length.install_as_arch()`. Where scipy is installed (the desktop path, and every
registered result) nothing is registered and scipy itself runs.

Anything not provided fails loudly: attribute access raises an AttributeError naming the function
and this file, and `from scipy.x import name` raises ImportError naming this file as the location.
`tests/test_scipy_lite.py` holds every function here to scipy's: the normal functions to 1e-14 on a
grid that includes the tails, `brentq` and `trapezoid` to 1e-12.

Methods: the normal CDF from Cephes' erf and erfc exactly as scipy builds them (xsf, ported
statement for statement with the published coefficients, so the stand-in rounds where scipy
rounds); log Phi(x) as scipy computes it for x >= -1 (log1p of the upper tail), from the CDF down
to -20 and by the standard asymptotic series beyond; the inverse by
Wichura (1988), Algorithm AS 241 (PPND16), Applied Statistics 37(3), 477-484, followed by one
Newton step on the erfc-based CDF; Brent's root finder as in scipy's `brentq`
(scipy/optimize/Zeros/brentq.c, after Brent 1973, Algorithms for Minimization without
Derivatives, ch. 4); the trapezoidal rule is numpy's.

The erf/erfc/ndtr port carries these notices:

    Cephes Math Library Release 2.2: June, 1992
    Copyright 1984, 1987, 1988, 1992 by Stephen L. Moshier

    xsf (scipy/xsf), BSD 3-Clause License, Copyright (c) 2024, SciPy.
    Redistribution and use in source and binary forms, with or without modification, are
    permitted provided that the following conditions are met: (1) Redistributions of source code
    must retain the above copyright notice, this list of conditions and the following disclaimer.
    (2) Redistributions in binary form must reproduce the above copyright notice, this list of
    conditions and the following disclaimer in the documentation and/or other materials provided
    with the distribution. (3) Neither the name of the copyright holder nor the names of its
    contributors may be used to endorse or promote products derived from this software without
    specific prior written permission. THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND
    CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
    IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO
    EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
    SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
    CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
    NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
    THE POSSIBILITY OF SUCH DAMAGE.
"""
from __future__ import annotations

import math

import numpy as np

_HERE = "quixote/engine/estimator/scipy_lite.py"
_SQRT2 = math.sqrt(2.0)
_SQRT1_2 = 0.70710678118654752440      # M_SQRT1_2, as Cephes and scipy use it
_SQRT2PI = math.sqrt(2.0 * math.pi)
_LOG_SQRT2PI = 0.5 * math.log(2.0 * math.pi)


def _out(x, y):
    """Scalars in, numpy float64 out (as scipy returns); arrays in, float arrays out."""
    y = np.asarray(y, dtype=float)
    return y[()] if np.ndim(x) == 0 else y


# -- the normal distribution ---------------------------------------------------------------------

# Cephes erf, erfc and ndtr as scipy builds them (xsf/include/xsf/cephes/ndtr.h), statement for
# statement with the published coefficients, so that the stand-in rounds where scipy rounds.
_NDTR_P = (2.46196981473530512524E-10, 5.64189564831068821977E-1, 7.46321056442269912687E0,
           4.86371970985681366614E1, 1.96520832956077098242E2, 5.26445194995477358631E2,
           9.34528527171957607540E2, 1.02755188689515710272E3, 5.57535335369399327526E2)
_NDTR_Q = (1.32281951154744992508E1, 8.67072140885989742329E1, 3.54937778887819891062E2,
           9.75708501743205489753E2, 1.82390916687909736289E3, 2.24633760818710981792E3,
           1.65666309194161350182E3, 5.57535340817727675546E2)
_NDTR_R = (5.64189583547755073984E-1, 1.27536670759978104416E0, 5.01905042251180477414E0,
           6.16021097993053585195E0, 7.40974269950448939160E0, 2.97886665372100240670E0)
_NDTR_S = (2.26052863220117276590E0, 9.39603524938001434673E0, 1.20489539808096656605E1,
           1.70814450747565897222E1, 9.60896809063285878198E0, 3.36907645100081516050E0)
_NDTR_T = (9.60497373987051638749E0, 9.00260197203842689217E1, 2.23200534594684319226E3,
           7.00332514112805075473E3, 5.55923013010394962768E4)
_NDTR_U = (3.35617141647503099647E1, 5.21357949780152679795E2, 4.59432382970980127987E3,
           2.26290000613890934246E4, 4.92673942608635921086E4)
_MAXLOG = 7.097827128933839730962063185871E2


def _polevl(x: float, coef) -> float:          # coefficients highest power first, as Cephes stores them
    ans = coef[0]
    for c in coef[1:]:
        ans = ans * x + c
    return ans


def _p1evl(x: float, coef) -> float:           # the same, with a leading coefficient of 1 left out
    ans = x + coef[0]
    for c in coef[1:]:
        ans = ans * x + c
    return ans


def _erf(x: float) -> float:
    if x != x:
        return math.nan
    if x < 0.0:
        return -_erf(-x)
    if abs(x) > 1.0:
        return 1.0 - _erfc(x)
    z = x * x
    return x * _polevl(z, _NDTR_T) / _p1evl(z, _NDTR_U)


def _erfc(a: float) -> float:
    if a != a:
        return math.nan
    x = -a if a < 0.0 else a
    if x < 1.0:
        return 1.0 - _erf(a)
    z = -a * a
    if z < -_MAXLOG:
        return 2.0 if a < 0 else 0.0           # underflow, as scipy
    z = math.exp(z)
    if x < 8.0:
        p, q = _polevl(x, _NDTR_P), _p1evl(x, _NDTR_Q)
    else:
        p, q = _polevl(x, _NDTR_R), _p1evl(x, _NDTR_S)
    y = (z * p) / q
    if a < 0:
        y = 2.0 - y
    if y != 0.0:
        return y
    return 2.0 if a < 0 else 0.0


def _ndtr_scalar(a: float) -> float:
    if a != a:
        return math.nan
    x = a * _SQRT1_2
    z = abs(x)
    if z < 1.0:
        y = 0.5 + 0.5 * _erf(x)
    else:
        y = 0.5 * _erfc(z)
        if x > 0:
            y = 1.0 - y
    return y


_ndtr_v = np.frompyfunc(_ndtr_scalar, 1, 1)


def ndtr(x):
    x = np.asarray(x, dtype=float)
    return _out(x, _ndtr_v(x))


def _log_ndtr_scalar(x: float) -> float:
    if x >= -1.0:                              # as scipy: log1p keeps the digits as Phi(x) -> 1
        return math.log1p(-0.5 * _erfc(x * _SQRT1_2))
    if x > -20.0:
        return math.log(_ndtr_scalar(x))
    # far left tail: log Phi(x) = log phi(x) - log(-x) + log(1 - 1/x^2 + 3/x^4 - 15/x^6 + ...)
    x2 = x * x
    term, total, k = 1.0, 1.0, 1
    while True:
        term *= -(2 * k - 1) / x2
        if abs(term) < 1e-17 * abs(total):
            break
        total += term
        k += 1
    return -0.5 * x2 - _LOG_SQRT2PI - math.log(-x) + math.log(total)


_log_ndtr_v = np.frompyfunc(_log_ndtr_scalar, 1, 1)


def log_ndtr(x):
    x = np.asarray(x, dtype=float)
    return _out(x, _log_ndtr_v(x))


# AS 241, PPND16: coefficients exactly as published
_A = (3.3871328727963666080e0, 1.3314166789178437745e2, 1.9715909503065514427e3, 1.3731693765509461125e4,
      4.5921953931549871457e4, 6.7265770927008700853e4, 3.3430575583588128105e4, 2.5090809287301226727e3)
_B = (1.0, 4.2313330701600911252e1, 6.8718700749205790830e2, 5.3941960214247511077e3,
      2.1213794301586595867e4, 3.9307895800092710610e4, 2.8729085735721942674e4, 5.2264952788528545610e3)
_C = (1.42343711074968357734e0, 4.63033784615654529590e0, 5.76949722146069140550e0, 3.64784832476320460504e0,
      1.27045825245236838258e0, 2.41780725177450611770e-1, 2.27238449892691845833e-2, 7.74545014278341407640e-4)
_D = (1.0, 2.05319162663775882187e0, 1.67638483018380384940e0, 6.89767334985100004550e-1,
      1.48103976427480074590e-1, 1.51986665636164571966e-2, 5.47593808499534494600e-4, 1.05075007164441684324e-9)
_E = (6.65790464350110377720e0, 5.46378491116411436990e0, 1.78482653991729133580e0, 2.96560571828504891230e-1,
      2.65321895265761230930e-2, 1.24266094738807843860e-3, 2.71155556874348757815e-5, 2.01033439929228813265e-7)
_F = (1.0, 5.99832206555887937690e-1, 1.36929880922735805310e-1, 1.48753612908506148525e-2,
      7.86869131145613259100e-4, 1.84631831751005468180e-5, 1.42151175831644588870e-7, 2.04426310338993978564e-15)


def _poly(c, x):
    r = 0.0
    for a in reversed(c):
        r = r * x + a
    return r


def _ndtri_scalar(p: float) -> float:
    if not 0.0 <= p <= 1.0 or p != p:
        return math.nan
    if p == 0.0:
        return -math.inf
    if p == 1.0:
        return math.inf
    q = p - 0.5
    if abs(q) <= 0.425:
        r = 0.180625 - q * q
        z = q * _poly(_A, r) / _poly(_B, r)
    else:
        r = math.sqrt(-math.log(p if q < 0 else 1.0 - p))
        if r <= 5.0:
            r -= 1.6
            z = _poly(_C, r) / _poly(_D, r)
        else:
            r -= 5.0
            z = _poly(_E, r) / _poly(_F, r)
        if q < 0:
            z = -z
    # one Newton step on the CDF, from whichever tail is accurate; skipped where the tail value
    # underflows (beyond about -37.5 sigma), where AS 241 alone is the better answer
    pdf = math.exp(-0.5 * z * z) / _SQRT2PI
    tail = _ndtr_scalar(-abs(z))
    if pdf > 0.0 and tail > 0.0:
        if z < 0:
            z -= (tail - p) / pdf
        else:
            z += (tail - (1.0 - p)) / pdf
    return z


_ndtri_v = np.frompyfunc(_ndtri_scalar, 1, 1)


def ndtri(p):
    p = np.asarray(p, dtype=float)
    return _out(p, _ndtri_v(p))


class _Norm:
    """The standard normal, as much of `scipy.stats.norm` as the audit path imports."""

    def cdf(self, x):
        return ndtr(x)

    def sf(self, x):
        return ndtr(-np.asarray(x, dtype=float))

    def pdf(self, x):
        x = np.asarray(x, dtype=float)
        return _out(x, np.exp(-x ** 2 / 2.0) / _SQRT2PI)

    def ppf(self, q):
        return ndtri(q)

    def __getattr__(self, name):
        raise AttributeError(f"scipy_lite does not provide scipy.stats.norm.{name}; extend {_HERE}")


norm = _Norm()


# -- Brent's method and the trapezoidal rule -------------------------------------------------------

def brentq(f, a, b, args=(), xtol=2e-12, rtol=8.881784197001252e-16, maxiter=100,
           full_output=False, disp=True):
    """A root of f in [a, b], f(a) and f(b) of opposite signs: scipy's brentq, statement for statement."""
    if full_output:
        raise AttributeError(f"scipy_lite's brentq does not provide full_output; extend {_HERE}")
    if xtol <= 0:
        raise ValueError(f"xtol too small ({xtol:g} <= 0)")
    if rtol < 8.881784197001252e-16:
        raise ValueError(f"rtol too small ({rtol:g} < {8.881784197001252e-16:g})")
    xpre, xcur = float(a), float(b)
    xblk = fblk = spre = scur = 0.0
    fpre, fcur = float(f(xpre, *args)), float(f(xcur, *args))
    if fpre * fcur > 0:
        raise ValueError("f(a) and f(b) must have different signs")
    if fpre == 0:
        return xpre
    if fcur == 0:
        return xcur
    for _ in range(maxiter):
        if fpre != 0 and fcur != 0 and (math.copysign(1.0, fpre) != math.copysign(1.0, fcur)):
            xblk, fblk = xpre, fpre
            spre = scur = xcur - xpre
        if abs(fblk) < abs(fcur):
            xpre, xcur, xblk = xcur, xblk, xcur
            fpre, fcur, fblk = fcur, fblk, fcur
        delta = (xtol + rtol * abs(xcur)) / 2
        sbis = (xblk - xcur) / 2
        if fcur == 0 or abs(sbis) < delta:
            return xcur
        if abs(spre) > delta and abs(fcur) < abs(fpre):
            if xpre == xblk:                                  # interpolate
                stry = -fcur * (xcur - xpre) / (fcur - fpre)
            else:                                             # extrapolate
                dpre = (fpre - fcur) / (xpre - xcur)
                dblk = (fblk - fcur) / (xblk - xcur)
                stry = -fcur * (fblk * dblk - fpre * dpre) / (dblk * dpre * (fblk - fpre))
            if 2 * abs(stry) < min(abs(spre), 3 * abs(sbis) - delta):
                spre, scur = scur, stry                       # good short step
            else:
                spre = scur = sbis                            # bisect
        else:
            spre = scur = sbis
        xpre, fpre = xcur, fcur
        xcur += scur if abs(scur) > delta else (delta if sbis > 0 else -delta)
        fcur = float(f(xcur, *args))
    if disp:
        raise RuntimeError(f"Failed to converge after {maxiter} iterations, value is {xcur}")
    return xcur


def trapezoid(y, x=None, dx=1.0, axis=-1):
    return np.trapezoid(y, x=x, dx=dx, axis=axis)


# -- registration -----------------------------------------------------------------------------------

_PROVIDED = {
    "scipy.stats": {"norm": norm},
    "scipy.special": {"ndtr": ndtr, "ndtri": ndtri, "log_ndtr": log_ndtr},
    "scipy.optimize": {"brentq": brentq},
    "scipy.integrate": {"trapezoid": trapezoid},
}


def _stand_in(name: str, attrs: dict):
    import types
    mod = types.ModuleType(name, f"scipy_lite stand-in for {name}: only {', '.join(sorted(attrs)) or 'its submodules'}.")
    mod.__file__ = _HERE                       # `from scipy.x import missing` then names this file

    def __getattr__(attr, _name=name):
        raise AttributeError(f"scipy_lite does not provide {_name}.{attr}; extend {_HERE}")

    mod.__getattr__ = __getattr__
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


def install_as_scipy() -> bool:
    """Register this module under scipy's names, if and only if scipy cannot be imported. Call it
    before importing the package. Returns whether the stand-in was installed (False: the real scipy
    is present and is used)."""
    import importlib
    import sys
    try:
        importlib.import_module("scipy")
        return False
    except ImportError:
        pass
    top = _stand_in("scipy", {})
    top.__version__ = "0+scipy_lite"
    sys.modules["scipy"] = top
    for name, attrs in _PROVIDED.items():
        mod = _stand_in(name, attrs)
        sys.modules[name] = mod
        setattr(top, name.split(".")[1], mod)
    return True
