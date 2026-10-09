"""Repro de BUG-0238 (el AR(4) de Salamanca no aparece entre los candidatos) y
BUG-0239 (el AICc acierta los mixtos persistentes que la similitud no).

AR(4) con los coeficientes estimados en Salamanca (0,334; 0,136; 0,111; 0,187),
d = 1, n = 200; y el ARMA(1,1) señal + ruido 0,95/0,7, d = 1. Para cada réplica,
la posición del modelo verdadero en la lista de art (opción B) y en la misma
lista ordenada por AICc. Uso:  python repro.py [REPS]
"""
import sys, math, warnings
import numpy as np
from scipy.signal import lfilter
warnings.filterwarnings("ignore")
import fue, art

REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
rng = np.random.default_rng(2026)

def sim(phi, theta, n=200):
    a = rng.normal(size=n + 300)
    w = lfilter(np.r_[1, -np.array(theta)], np.r_[1, -np.array(phi)], a)[300:]
    return np.cumsum(w) + 100.0

def pos(lista, pq):
    return lista.index(pq) + 1 if pq in lista else None

for nombre, phi, theta in [("AR(4) Salamanca", [0.334, 0.136, 0.111, 0.187], []),
                           ("ARMA(1,1) .95/.7", [0.95], [0.7])]:
    pq = (len(phi), len(theta))
    enB, enA, ausente, ordenes = [], [], 0, {}
    for _ in range(REPS):
        x = sim(phi, theta)
        ts = fue.TimeSeries(list(x), freq=1, start=(2000, 1), name="S")
        sp = art.suggest_orders(ts, d=1, D=0, lam=1.0, top_n=50)
        lb = [(s.p, s.q) for s in sp]
        la = [(s.p, s.q) for s in sorted(sp, key=lambda s: s.aicc if s.aicc is not None and math.isfinite(s.aicc) else math.inf)]
        enB.append(pos(lb, pq)); enA.append(pos(la, pq))
        ausente += pq not in lb
        ordenes[lb[0]] = ordenes.get(lb[0], 0) + 1
    r = lambda v, k: sum(1 for x in v if x is not None and x <= k)
    print(f"{nombre}: {REPS} réplicas · ausente de la lista {ausente} · "
          f"similitud 1.º {r(enB,1)} / top-3 {r(enB,3)} · AICc 1.º {r(enA,1)} / top-3 {r(enA,3)} · "
          f"primeros de la lista: {dict(sorted(ordenes.items(), key=lambda kv: -kv[1]))}")
