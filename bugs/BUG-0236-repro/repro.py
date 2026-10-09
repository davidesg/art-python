"""Repro de BUG-0236, BUG-0237 y de los añadidos a BUG-0224 y BUG-0235.

Regenera las MISMAS series que research/bateria_contrastes_d.py (N=200,
SEED=2026: se recorre el generador en el mismo orden) y estima sólo los casos
que hacen falta. Uso:  ART_NO_VIEWER=1 python repro.py
"""
import os, re, sys, tempfile
import numpy as np
from scipy.signal import lfilter
os.environ.setdefault("ART_NO_VIEWER", "1")
import art.mcp_server as s

N, SEED = 200, 2026
ESTR = [("ruido", [], []), ("AR(1) .6", [0.6], []), ("AR(1) .95", [0.95], []),
        ("AR(2) reales .5,.3", [0.5, 0.3], []), ("AR(2) complejo 1,-.5", [1.0, -0.5], []),
        ("MA(1) .5", [], [0.5]), ("ARMA(1,1) .6/.3", [0.6], [0.3])]
CASOS = {  # (d, nombre): qué se mira
    (1, "AR(2) reales .5,.3"): "0236 LR negativo en el DCD de sobrediferenciación",
    (2, "AR(1) .95"):          "0236 testigo negativo y LR negativo · 0235 SF pide d=3",
    (1, "AR(1) .6"):           "0224 DCD de subdiferenciación con AR libre, sin aviso",
    (0, "AR(2) reales .5,.3"): "0237 modelo verdadero «no adecuado» (Q)",
    (1, "AR(2) complejo 1,-.5"): "0237 «estacionalidad en los residuos» en un AR(2) sin estacionalidad",
    (1, "MA(1) .5"):           "0237 modelo verdadero «no adecuado» (Q)",
    (2, "ARMA(1,1) .6/.3"):    "0237 modelo verdadero «no adecuado» (media)",
}

def T(r): return r if isinstance(r, str) else "\n".join(
    t for c in r if isinstance(t := getattr(c, "text", None), str))
def grep(p, t): return [l.strip()[:170] for l in t.splitlines() if re.search(p, l)]

rng = np.random.default_rng(SEED)
with tempfile.TemporaryDirectory() as w:
    for d in (0, 1, 2):
        for nombre, phi, theta in ESTR:
            a = rng.normal(size=N + 300)
            x = lfilter(np.r_[1, -np.array(theta, float)], np.r_[1, -np.array(phi, float)], a)[300:]
            for _ in range(d):
                x = np.cumsum(x)
            x = x - x.min() + 100.0
            if (d, nombre) not in CASOS:
                continue
            inp, out = os.path.join(w, "S.inp"), os.path.join(w, "m.inp")
            s.create_inp([float(v) for v in x], inp, name="S", freq=12, start_year=2000, start_period=1)
            T(s.confirm_and_estimate(inp, out, lam=1.0, d=d, D=0, p=len(phi), q=len(theta),
                                     n_harmonics=0, seasonal=False, estimate_mu=(d == 0),
                                     domain="generic", modo="autonomo"))
            ft = T(s.formal_tests(out.replace(".inp", ".pre"), run_meg=False, subdiferenciacion=True))
            print(f"\n== d={d} {nombre}: {CASOS[(d, nombre)]}")
            for p in (r"Φ̂₁ᵤ=", r"^- θ̂=", r"Candidato: ∇", r"La diagnosis falla en",
                      r"Considera aumentar d|d\+1", r"no es fiable|AR libre|BUG-0224"):
                for l in grep(p, ft)[:2]:
                    print("   ", l)
