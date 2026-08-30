"""BUG-0021: formal_tests revienta en cuanto el modelo lleva un factor AR(2).

El contraste RV (frecuencia del factor AR(2)) construye un `RVResult` cuyo campo
es `freq_estimated`; el bloque que lo imprime en describe.py lee `freq_hat`. El
campo no existe, así que salta AttributeError y se pierde TODO el informe de
contrastes formales — Shin-Fuller y el DCD incluidos, que ya estaban calculados.

Sólo se dispara con AR(2), que es justo la especificación en la que uno quiere
mirar la frecuencia del factor. Con AR(1) o MA(1) no hay RV y no se nota.

    python3 bugs/BUG-0021-repro/repro.py
"""
import numpy as np

from art.pipeline import _load_ts_model, _write_inp
from art.describe import describe_formal_tests

import tempfile, os

# --- una serie con un factor AR(2) de frecuencia baja (raíz casi unitaria) ----
rng = np.random.default_rng(7)
n = 120
y = np.zeros(n)
for t in range(2, n):
    y[t] = 1.55 * y[t - 1] - 0.68 * y[t - 2] + rng.normal(0, 1.0)
y = y + 100.0

d = tempfile.mkdtemp(prefix="bug0021-")
inp = os.path.join(d, "SYN.inp")

from art import mcp_server as A
A.create_inp(list(map(float, y)), inp, name="SYN", freq=4,
             start_year=1990, start_period=1)

out = os.path.join(d, "SYN_ar2.inp")
A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=0, D=0,
                       p=2, q=0, n_harmonics=0, seasonal=False,
                       estimate_mu=True)

ts, m = _load_ts_model(out.replace(".inp", ".pre"))
m.fit()
phi1, phi2 = m.ar[0]
print("modelo AR(2) ajustado, phi =", m.ar)
print("discriminante = %.4f  ->  raices %s"
      % (phi1**2 + 4*phi2, "COMPLEJAS (el RV actua)" if phi1**2 + 4*phi2 < 0
         else "REALES (el RV no actua; el bug no se dispara)"))

# el invariante que causaba el crash
from art.formal_tests import RVResult
campos = set(RVResult.__dataclass_fields__)
print("\ncampos de RVResult:", sorted(campos))
print("  tiene 'freq_estimated'? ", "freq_estimated" in campos)
print("  tiene 'freq_hat'?       ", "freq_hat" in campos,
      " <- describe.py leia ESTE")

try:
    r = describe_formal_tests(m, run_meg=False)
except AttributeError as e:
    print("\nBUG-0021 REPRODUCIDO ->  AttributeError:", e)
    print("  el informe entero se pierde, incluidos Shin-Fuller y el DCD.")
else:
    print("\nsin crash. Bloque RV del informe:")
    for line in r.summary.splitlines():
        if "f̂=" in line:
            print("  ", line.strip())
