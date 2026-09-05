"""BUG-0099 — el guardián de `base_pre_path` compara la FORMA, no el CONTENIDO.

Determinista y sintético: dos series distintas de 120 datos mensuales.

    python bugs/BUG-0099-repro/repro.py
"""
import os
import sys
import tempfile
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
os.environ.setdefault("ART_NO_VIEWER", "1")

import numpy as np  # noqa: E402
import fue  # noqa: E402

from art.mcp_server import _exige_la_misma_serie  # noqa: E402
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar  # noqa: E402


def serie(seed, escala, start=(2010, 1)):
    r = np.random.default_rng(seed)
    y = np.cumsum(r.standard_normal(120) * escala) + 100.0
    return fue.TimeSeries(y.tolist(), freq=12, start=start, name="S")


A, B = serie(7, 0.4), serie(9, 0.9)
print(f"A y B: nobs {A.nobs}/{B.nobs}, freq {A.freq}/{B.freq}, start {A.start}/{B.start}")
print("el guardián VIEJO comparaba nobs y freq -> las daba por la misma:",
      A.nobs == B.nobs and A.freq == B.freq)

d = tempfile.mkdtemp()
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    m = fue.Model(A, d=1, mu=0.0, estimate_mu=True, refactor=_RESCALE_FACTOR)
    _write_inp(A, m, f"{d}/A.inp")
    _, mA = estimar(f"{d}/A.inp")

fallos = 0
try:
    _exige_la_misma_serie(B, mA.series, "B.inp", "A.pre")
    print("FALLO  encadenó el .pre de A sobre los datos de B"); fallos += 1
except ValueError as e:
    print("OK  detectado:", str(e).splitlines()[0])

try:
    _exige_la_misma_serie(serie(7, 0.4, (2011, 1)), mA.series, "A2.inp", "A.pre")
    print("FALLO  encadenó una serie desalineada un año"); fallos += 1
except ValueError as e:
    print("OK  detectado:", str(e).splitlines()[0])

try:
    _exige_la_misma_serie(A, mA.series, "A.inp", "A.pre")
    print("OK  el encadenado legítimo pasa (el .inp reproduce la serie a ~5e-7)")
except ValueError as e:
    print("FALLO  regresión, rechaza lo legítimo:", e); fallos += 1

sys.exit(1 if fallos else 0)
