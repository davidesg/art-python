"""BUG-0206 — el contraste F-HAC de estacionalidad rechaza de más.

Con residuos que son ruido blanco (n=216, mensual) el F-HAC de art declaraba
estacionalidad en el 18 % de los casos; como veredicto de la DIAGNOSIS eso
decidía si el bucle de atípicos paraba y si el modelo salía «limpio».

Decisión y arreglo (04-10-2026): el F-HAC se queda en la IDENTIFICACIÓN, que es
un cribado; la diagnosis de residuos usa la F de MCO. El estudio de tamaño que
llevó a esa decisión está al lado, en `hac_size.py`.

Este repro comprueba el arreglo: que `diagnose` pide la F de MCO sobre los
residuos (d=0), y que con ella las falsas alarmas sobre ruido blanco quedan por
debajo del 9 %. Exit 1 = bug presente; exit 0 = corregido.
"""
import os
import sys
import warnings

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))
warnings.filterwarnings("ignore")

import fue                                              # noqa: E402
from art import diagnosis                               # noqa: E402
from art import seasonal_detection as sd                # noqa: E402


def _ts(y):
    return fue.TimeSeries(list(map(float, y)), freq=12, start=(2000, 1), name="S")


FALLOS = []

visto = {}
real = diagnosis.detect_seasonality
def espia(*a, **k):
    visto.update(k)
    return real(*a, **k)
diagnosis.detect_seasonality = espia
rng = np.random.default_rng(3)
y = 100 + np.cumsum(0.2 + rng.standard_normal(216))
m = fue.Model(_ts(y), d=1, boxlam=1.0, refactor=1.0, mu=0.2, estimate_mu=True)
m.fit()
diagnosis.diagnose(m)
diagnosis.detect_seasonality = real
print(f"== diagnose contrasta los residuos con test={visto.get('test')!r}, d={visto.get('d')!r}")
if visto.get("test") != "ols":
    FALLOS.append("la diagnosis de residuos no usa la F de MCO")

R = 300
rng = np.random.default_rng(2)
hits = sum(sd.detect_seasonality(_ts(rng.standard_normal(216)), d=0, lam=1.0,
                                 test="ols").seasonal_detected for _ in range(R))
print(f"== falsas alarmas sobre ruido blanco (n=216, F de MCO): {hits / R:.3f}")
if hits / R >= 0.09:
    FALLOS.append(f"la F de los residuos rechaza el {hits / R:.0%} del ruido blanco")

print("=" * 70)
if FALLOS:
    print("FALLA (bug presente):", "; ".join(FALLOS))
    sys.exit(1)
print("OK: la diagnosis usa la F de MCO y su tamaño es el nominal.")
