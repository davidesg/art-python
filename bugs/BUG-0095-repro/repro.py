"""BUG-0095 — la identificación propone candidatos sparse "solo en B^k".

`suggest_orders` genera, además de los AR(p)/MA(q) completos, candidatos con un
único coeficiente en el retardo k y los anteriores forzados a cero
(sparse_ar_lag / sparse_ma_lag), y los inyecta en el ranking con la etiqueta
"AR sólo en B^k" / "MA sólo en B^k". Esa restricción solo procede a posteriori
vía factorización de raíces; imponerla de entrada no se hace en Box-Jenkins.

Sintético y determinista: serie log con estacionalidad + ruido blanco.
Comprueba que el ranking de candidatos CONTIENE entradas sparse.
"""
import sys
import numpy as np

sys.path.insert(0, "src")

from fue import TimeSeries
from art.model_detection import suggest_orders

FALLOS = []

rng = np.random.default_rng(42)
n = 216
y = np.exp(0.003 * np.arange(n) + 0.2 * np.sin(2 * np.pi * np.arange(n) / 12)
           + 0.1 * rng.standard_normal(n))
ts = TimeSeries(y, freq=12, start=(2002, 1))
cands = suggest_orders(ts, d=1, D=0, lam=0.0, top_n=8)

print("== Candidatos devueltos por la identificación")
sparse_vistos = []
for i, c in enumerate(cands, 1):
    sp = []
    if getattr(c, "sparse_ar_lag", 0):
        sp.append(f"AR solo B^{c.sparse_ar_lag}")
    if getattr(c, "sparse_ma_lag", 0):
        sp.append(f"MA solo B^{c.sparse_ma_lag}")
    if sp:
        sparse_vistos.append((i, sp, c.similarity))
    print(f"  {i}. ARIMA({c.p},{c.d},{c.q})({c.P},{c.D},{c.Q})_{c.s} "
          f"{sp if sp else ''}  sim={c.similarity:.3f}")

print("\n== Veredicto")
if sparse_vistos:
    for i, sp, sim in sparse_vistos:
        print(f"  candidato {i} es sparse: {sp} (sim={sim:.3f})")
    print("  FALLA: el ranking ofrece restricciones 'solo en B^k' de entrada")
    FALLOS.append("candidatos sparse en el ranking")
else:
    print("  OK: no hay candidatos sparse")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK")
