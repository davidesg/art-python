"""BUG-0023: el nodo guiado de `d` salta de d=0 a d=2 de una vez.

En la escuela de Box y Jenkins nunca se saltan dos decisiones sin pasar por los
instrumentos de especificacion y diagnosis: desde d=0 solo se puede ir a d=1 o
quedarse en d=0. Y hay un motivo tecnico ademas del metodologico: la regresion
del ADF no lleva terminos estacionales, asi que con estacionalidad fuerte el
patron cae en su varianza residual, infla el error tipico del coeficiente y
sesga el contraste hacia NO rechazar la raiz unitaria -- que se lee como "vuelve
a diferenciar". Fallar en d=0 y en d=1 es EXACTAMENTE lo que hace una serie muy
estacional, y es la condicion con la que `recommended_d` se permitia llegar a 2.

La estacionalidad, ademas, solo empieza a ser visible a partir de d=1: en la
escuela se evalua sobre una serie mas o menos centrada. Por eso en el flujo
guiado el nodo de estacionalidad va DESPUES (paso 3) y cuando se recomienda `d`
(paso 2) todavia no se ha contrastado nada.

    python3 bugs/BUG-0023-repro/repro.py
"""
import os
import tempfile

import numpy as np

from art import mcp_server as A
from art.identification import unit_root_tests, recommended_d
from art.pipeline import _load_ts_model

# --- serie I(1) con estacionalidad determinista fuerte, n=84 trimestral ------
# Paseo aleatorio + patron trimestral fijo. El orden de integracion regular es
# 1 POR CONSTRUCCION: no hay ninguna segunda raiz unitaria que encontrar.
rng = np.random.default_rng(5)
n = 84
paseo = 100.0 + np.cumsum(rng.normal(0, 1.0, n))
patron = np.array([-8.0, +1.5, +1.0, +5.5])          # Q1 bajo, Q4 alto
y = paseo + np.tile(patron, n // 4)

_d = tempfile.mkdtemp(prefix="bug0023-")
_inp = os.path.join(_d, "SEAS_I1.inp")
A.create_inp(list(map(float, y)), _inp, name="SEAS_I1", freq=4,
             start_year=2004, start_period=1)
ts, _m = _load_ts_model(_inp)

res2 = unit_root_tests(ts, lam=1.0, max_d=2)
print("tabla ADF/KPSS tal como la pedia el nodo guiado (max_d=2):")
for r in res2:
    print("  d=%d  ADF p=%.4f %s   KPSS p=%.4f %s   -> %s"
          % (r.d, r.adf_pvalue, "rechaza" if r.adf_rejects else "NO rechaza",
             r.kpss_pvalue, "no rechaza" if not r.kpss_rejects else "rechaza",
             r.verdict))

d_viejo = recommended_d(res2)
d_nuevo = recommended_d(unit_root_tests(ts, lam=1.0, max_d=1))

print("\n  recomendacion con la tabla hasta d=2 : d = %d   <- el defecto" % d_viejo)
print("  recomendacion con la tabla hasta d=1 : d = %d   <- la correcta" % d_nuevo)
print("  verdad del DGP                       : d = 1")

if d_viejo == 2:
    print("\nBUG-0023 REPRODUCIDO: dos decisiones de un salto, y sobre una serie")
    print("cuya estacionalidad el flujo guiado aun no ha contrastado.")
else:
    print("\n(!) esta realizacion no salto a 2; prueba otra semilla")

# --- y la incoherencia interna del nodo -------------------------------------
print("\nEl paso 2 del flujo guiado solo ofrece DOS continuaciones:")
print("    guided_identification(inp, lam=..., d=1)")
print("    guided_identification(inp, lam=..., d=0, D=0)")
print("Recomendar d=2 es recomendar un valor que el propio nodo no admite.")
