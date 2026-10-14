"""BUG-0237: la puerta de adecuación de formal_tests declara «todavía NO es
adecuado» a 5 de 21 modelos VERDADEROS (n = 200): cuatro contrastes al 5 % cada
uno, sin corrección por multiplicidad.

Regenera las 21 series de research/bateria_contrastes_d.py (N = 200, SEED =
2026, siete estructuras × d = 0, 1, 2; las mismas que BUG-0236-repro), estima la
especificación VERDADERA y cuenta cuántas abren con la puerta cerrada. Con un
tamaño conjunto del 5 % se esperan ~1 de 21; sale 1 mientras haya más de 2.

    PYTHONPATH=src python3 bugs/BUG-0237-repro/repro.py
"""
import os, sys, warnings
import numpy as np
from scipy.signal import lfilter
warnings.filterwarnings("ignore")
os.environ.setdefault("ART_NO_VIEWER", "1")
import fue
from art.pipeline import _make_model
from art.describe import describe_formal_tests

N, SEED = 200, 2026
ESTR = [("ruido", [], []), ("AR(1) .6", [0.6], []), ("AR(1) .95", [0.95], []),
        ("AR(2) reales .5,.3", [0.5, 0.3], []), ("AR(2) complejo 1,-.5", [1.0, -0.5], []),
        ("MA(1) .5", [], [0.5]), ("ARMA(1,1) .6/.3", [0.6], [0.3])]
rng = np.random.default_rng(SEED)
cerrada = []
for d in (0, 1, 2):
    for nombre, phi, theta in ESTR:
        a = rng.normal(size=N + 300)
        x = lfilter(np.r_[1, -np.array(theta, float)], np.r_[1, -np.array(phi, float)], a)[300:]
        for _ in range(d):
            x = np.cumsum(x)
        x = x - x.min() + 100.0
        ts = fue.TimeSeries([float(v) for v in x], freq=12, start=(2000, 1), name="S")
        m = _make_model(ts, lam=1.0, d=d, D=0, p=len(phi), q=len(theta),
                        n_harmonics=0, estimate_mu=(d == 0))
        m.fit()
        t = describe_formal_tests(m, run_meg=False).summary
        if "todavía NO es adecuado" in t:
            linea = next(l for l in t.splitlines() if "La diagnosis falla en" in l)
            cerrada.append(f"d={d} {nombre}: {linea.split('falla en: ')[1][:90]}")
print(f"modelos verdaderos con la puerta cerrada: {len(cerrada)} de 21")
for c in cerrada:
    print("  ", c)
sys.exit(1 if len(cerrada) > 2 else 0)
