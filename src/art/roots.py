"""Roots and factorization of a normalized AR polynomial, with AR_f identification.

Python migration of the ``Root`` C tool (Guerrero, UCM; version Root-1.01, the one
without the ``malloc(orden-1)`` buffer overflow that segfaults version 1.02 at high
order). Root-finding uses ``numpy.roots`` (companion-matrix eigenvalues), which is
robust and order-independent, in place of the original Laguerre routine. The
frequency/period of the complex factors is computed correctly here (the C versions
used a wrong ``atan(...)/(2*pi)`` formula).

A normalized AR operator is written
    P(B) = 1 - c[1] B - c[2] B^2 - ... - c[N] B^N
and factorizes into first-order real factors (1 - a1 B) and second-order
complex-conjugate factors (1 - a1 B - a2 B^2). For a complex pair with root z of
P(B)=0 (so |z|>1 for a stationary operator):

    r      = 1/|z|                 modulus of the inverse roots (the damping),
    omega  = |arg z|               angular frequency in radians,
    a1     = 2 Re(z)/|z|^2 = 2 cos(omega) r,
    a2     = -1/|z|^2      = -r^2,
    k      = omega * s / (2 pi)    frequency in seasonal-harmonic units,
    period = 2 pi / omega.

This is exactly fue's ``FixedFreqFactor`` parametrization (coef = a2 = -r^2,
freq = k). Because fue can estimate an AR operator either factored or unfactored,
factorizing a freely estimated AR(p) reveals AR_f factors hidden inside it -- a
complex pair whose frequency k sits at (or near) a seasonal harmonic and whose
modulus r is near one is a candidate seasonal (stochastic) autoregressive factor.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class RealFactor:
    a1: float          # factor is (1 - a1 B)
    root: float        # the B-root, 1/a1
    modulus: float     # |root|; >1 stationary


@dataclass
class ComplexFactor:
    a1: float          # factor is (1 - a1 B - a2 B^2)
    a2: float          # = -r^2
    r: float           # modulus of the inverse roots (damping), sqrt(-a2)
    omega: float       # angular frequency (radians)
    harmonic: float    # omega * s / (2 pi); integer-valued at a seasonal frequency
    period: float      # 2 pi / omega (in observations)
    root_modulus: float  # |z|; >1 stationary
    is_arf_candidate: bool  # harmonic near an integer seasonal frequency
    near_unit_root: bool    # r near 1 (candidate stochastic seasonality)


@dataclass
class Factorization:
    order: int
    sper: int
    roots: list          # complex B-roots, sorted by modulus
    real: list           # list[RealFactor]
    complex: list        # list[ComplexFactor]

    def arf_candidates(self):
        """Complex factors whose frequency sits at a seasonal harmonic."""
        return [c for c in self.complex if c.is_arf_candidate]


def factor_ar(coefs, sper: int = 12, imag_tol: float = 1e-6,
              harmonic_tol: float = 0.15, unit_root_tol: float = 0.05) -> Factorization:
    """Factorize the normalized AR polynomial 1 - c[1]B - ... - c[N]B^N.

    Parameters
    ----------
    coefs : sequence of the c[1..N] (the AR coefficients, NOT including the leading 1).
    sper  : seasonal period (12 monthly, 4 quarterly). Used for the harmonic index.
    harmonic_tol : a complex factor is flagged AR_f if its harmonic is within this
                   of an integer 1..sper//2.
    unit_root_tol: a complex factor is flagged near-unit-root if 1 - r < this.
    """
    coefs = [float(c) for c in coefs]
    n = len(coefs)
    # P(B) coefficients ascending in B: [1, -c1, ..., -cN]; np.roots wants descending.
    desc = [-c for c in reversed(coefs)] + [1.0]
    roots = np.roots(desc) if n > 0 else np.array([])
    roots = sorted(roots, key=lambda z: abs(z))

    real, comp = [], []
    used = [False] * len(roots)
    for i, z in enumerate(roots):
        if used[i]:
            continue
        if abs(z.imag) <= imag_tol:
            zr = z.real
            real.append(RealFactor(a1=1.0 / zr, root=zr, modulus=abs(zr)))
            used[i] = True
        else:
            # find the conjugate partner
            for j in range(i + 1, len(roots)):
                if not used[j] and abs(roots[j] - np.conj(z)) < 1e-6:
                    used[j] = True
                    break
            used[i] = True
            mod2 = z.real ** 2 + z.imag ** 2
            a1 = 2.0 * z.real / mod2
            a2 = -1.0 / mod2
            r = np.sqrt(-a2)
            omega = abs(np.angle(z))
            k = omega * sper / (2 * np.pi)
            per = 2 * np.pi / omega if omega > 0 else np.inf
            near_h = abs(k - round(k)) <= harmonic_tol and 1 <= round(k) <= sper // 2
            comp.append(ComplexFactor(
                a1=a1, a2=a2, r=float(r), omega=float(omega), harmonic=float(k),
                period=float(per), root_modulus=float(np.sqrt(mod2)),
                is_arf_candidate=bool(near_h),
                near_unit_root=bool(1.0 - r < unit_root_tol)))
    return Factorization(order=n, sper=sper, roots=list(roots), real=real, complex=comp)


def describe(fac: Factorization) -> str:
    """Characterization in the original ``Root`` format and language.

    Reproduces the output of the C tool: the roots table and the real / complex
    factors, the complex ones characterized by the damping factor ``d`` (= sqrt(-a2),
    the modulus of the inverse roots), the frequency ``freq`` (cycles per
    observation, omega/2pi) and the period ``per`` (observations per cycle,
    2pi/omega). Interpretation -- whether a complex factor is a seasonal AR_f
    operator (freq at a seasonal harmonic, d near 1) -- is left to the reader.
    """
    lines = ["------------",
             f"{'RAIZ #':>10}{'REAL':>13}{'IMAG':>13}{'MOD':>13}"]
    for i, z in enumerate(fac.roots, 1):
        lines.append(f"{i:>7}     {z.real:>12.5f}{z.imag:>13.5f}{abs(z):>13.5f}")
    if fac.real:
        lines.append(f"\n    FACTORES REALES (1 - a[1] B): {len(fac.real)}")
        for i, rf in enumerate(fac.real, 1):
            lines.append(f"    ** FACTOR {i}: a[1] = {rf.a1:12.5f}")
    if fac.complex:
        lines.append(f"\n    FACTORES COMPLEJOS (1 - a[1] B - a[2] B^2): {len(fac.complex)}")
        for i, cf in enumerate(fac.complex, 1):
            freq = cf.omega / (2 * np.pi)
            lines.append(
                f"    ** FACTOR {i}: a[1] = {cf.a1:12.5f}   a[2] = {cf.a2:12.5f}"
                f"   d = {cf.r:.2f}   freq = {freq:.2f}   per = {cf.period:.2f}")
    lines.append("------------")
    return "\n".join(lines)


if __name__ == "__main__":
    # self-test: AR(3) = (1 - 0.5 B)(1 + 0.81 B^2), i.e. real root + complex pair at
    # omega=pi/2 (harmonic 3 monthly), damping r=0.9.
    # (1-0.5B)(1+0.81B^2) = 1 - 0.5B + 0.81B^2 - 0.405B^3
    #  = 1 - c1 B - c2 B^2 - c3 B^3  with c1=0.5, c2=-0.81, c3=0.405
    fac = factor_ar([0.5, -0.81, 0.405], sper=12)
    print(describe(fac))
    assert any(c.is_arf_candidate and round(c.harmonic) == 3 for c in fac.complex)
    assert abs(fac.complex[0].r - 0.9) < 1e-6
    print("\nOK")
