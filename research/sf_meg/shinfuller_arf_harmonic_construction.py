"""Paso 2 — Φ̂_f harmonic-estimated (factor complejo aislado): escalar vs armónico.

Mismo esquema que shinfuller_meanest.py (validado), cambiando SOLO el detrending
del estadístico: la 'media' pasa de un escalar (1 nuisance) al armónico bidimensional
A·cos ωt + B·sin ωt (2 nuisance, la solución homogénea del operador complejo).

DGP nulo idéntico: RW estacional complejo puro (ρ=1, sin armónico añadido).
Dos pasadas: (1) mediana de ρ̂ → ρ_m (pile-up=½ por construcción); (2) críticos de Φ̂.
"""
import warnings; warnings.filterwarnings("ignore")
import numpy as np
from scipy.optimize import minimize_scalar


def Bform(a, b, phi1, phi2, Minv):
    """a' Ω⁻¹ b por descomposición de error de predicción del AR(2) complejo."""
    init = Minv[0, 0]*a[0]*b[0] + Minv[0, 1]*(a[0]*b[1]+a[1]*b[0]) + Minv[1, 1]*a[1]*b[1]
    fa = a[2:] - phi1*a[1:-1] - phi2*a[:-2]
    fb = b[2:] - phi1*b[1:-1] - phi2*b[:-2]
    return init + np.sum(fa*fb)


def _MinvDet(rho, cw):
    phi1 = 2*cw*rho; phi2 = -rho*rho
    den = (1+phi2)*((1-phi2)**2 - phi1**2)
    if den <= 0: return None
    v0 = (1-phi2)/den; v1 = v0*phi1/(1-phi2); detM = v0*v0 - v1*v1
    if detM <= 0: return None
    return phi1, phi2, np.array([[v0, -v1], [-v1, v0]])/detM, detM


def g_scalar(rho, y, cw):
    if rho <= 0 or rho >= 1: return np.inf
    r = _MinvDet(rho, cw)
    if r is None: return np.inf
    phi1, phi2, Minv, detM = r
    one = np.ones_like(y)
    mu = Bform(one, y, phi1, phi2, Minv)/Bform(one, one, phi1, phi2, Minv)
    z = y - mu
    return y.size*np.log(Bform(z, z, phi1, phi2, Minv)) + np.log(detM)


def g_harm(rho, y, cw, C, S):
    if rho <= 0 or rho >= 1: return np.inf
    r = _MinvDet(rho, cw)
    if r is None: return np.inf
    phi1, phi2, Minv, detM = r
    Scc = Bform(C, C, phi1, phi2, Minv); Scs = Bform(C, S, phi1, phi2, Minv)
    Sss = Bform(S, S, phi1, phi2, Minv)
    Scy = Bform(C, y, phi1, phi2, Minv); Ssy = Bform(S, y, phi1, phi2, Minv)
    M2 = np.array([[Scc, Scs], [Scs, Sss]])
    try:
        beta = np.linalg.solve(M2, np.array([Scy, Ssy]))
    except np.linalg.LinAlgError:
        return np.inf
    z = y - beta[0]*C - beta[1]*S
    return y.size*np.log(Bform(z, z, phi1, phi2, Minv)) + np.log(detM)


def rhohat(gfun):
    return minimize_scalar(gfun, bounds=(0.02, 0.999999), method="bounded",
                           options={"xatol": 1e-8}).x


def gen(n, cw, rng, nb=60):
    e = rng.standard_normal(n+nb); y = np.zeros(n+nb)
    for t in range(2, n+nb):
        y[t] = 2*cw*y[t-1] - y[t-2] + e[t]
    return y[nb:]


for f in (1, 3):
    w = 2*np.pi*f/12; cw = np.cos(w)
    print(f"\n{'='*70}\nf={f}  (ω={w:.4f}, cos ω={cw:.4f})\n{'='*70}")
    for n in (100, 250):
        t = np.arange(n); C = np.cos(w*t); S = np.sin(w*t)
        reps = 5000
        rng = np.random.default_rng(21)
        ys = [gen(n, cw, rng) for _ in range(reps)]
        # pasada 1: mediana de ρ̂ para cada construcción
        rs_sc = np.array([rhohat(lambda r: g_scalar(r, y, cw)) for y in ys])
        rs_hm = np.array([rhohat(lambda r: g_harm(r, y, cw, C, S)) for y in ys])
        rm_sc, rm_hm = np.median(rs_sc), np.median(rs_hm)
        # pasada 2: Φ̂ con ρ_m = mediana
        def phis(gfun, rs, rm):
            out = []
            for y, rh in zip(ys, rs):
                if rh > rm: out.append(0.0)
                else: out.append(0.5*(gfun(rm, y) - gfun(rh, y)))
            return np.array(out)
        ph_sc = phis(lambda r, y: g_scalar(r, y, cw), rs_sc, rm_sc)
        ph_hm = phis(lambda r, y: g_harm(r, y, cw, C, S), rs_hm, rm_hm)
        print(f"\n n={n}")
        print(f"  {'':14} {'med n(ρ̂−1)':>11} {'c=n(1−ρ_m)':>11} {'ρ_m':>8} "
              f"{'pileup':>7} {'10%':>7} {'5%':>7} {'1%':>7}")
        for tag, rs, rm, ph in (("ESCALAR (1)", rs_sc, rm_sc, ph_sc),
                                ("ARMÓNICO (2)", rs_hm, rm_hm, ph_hm)):
            q = np.quantile(ph, [.90, .95, .99])
            print(f"  {tag:14} {n*(rm-1):>11.2f} {n*(1-rm):>11.3f} {rm:>8.4f} "
                  f"{np.mean(ph<1e-9):>7.3f} {q[0]:>7.3f} {q[1]:>7.3f} {q[2]:>7.3f}")
