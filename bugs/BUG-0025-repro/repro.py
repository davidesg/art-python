"""BUG-0025: `formal_tests` cierra en "el modelo es adecuado" sin haber mirado
NUNCA la diagnosis del modelo.

Los contrastes formales -- MEG, Shin-Fuller, los DCD -- son la ULTIMA etapa del
ciclo. Presuponen un modelo escueto, adecuado y con la diagnosis limpia: sus
distribuciones nulas se derivan bajo residuos que son ruido blanco. Correrlos
sobre un modelo cuya Q, cuya normalidad o cuyos anomalos estan fallando no es
una imprecision, es preguntar por la frontera de un parametro a una
verosimilitud que aun no describe los datos.

El propio ART lo dice tres veces en su capa guiada:
    mcp_server.py:149   "Hipotesis B1 es revisable AL FINAL mediante MEG"
    mcp_server.py:1983  "El contraste MEG (formal_tests) evalua AL FINAL ..."
    mcp_server.py:1742  "B) Contrastes formales (SI LOS RESIDUOS ESTAN LIMPIOS)"

Pero esa condicion es PROSA. `describe_formal_tests` no la comprueba: construye
su lista `issues` solo con hallazgos de los propios contrastes formales y, si
sale vacia, imprime "Los contrastes formales no detectan problemas. El modelo es
adecuado." -- una afirmacion sobre el MODELO que esa funcion no esta en
condiciones de hacer.

El precedente esta en el mismo fichero, en el comentario de BUG-0010:
    "una frecuencia sin contrastar no puede terminar en 'el modelo es adecuado'"
Una diagnosis que falla tampoco.

    python3 bugs/BUG-0025-repro/repro.py
"""
import os
import tempfile

import numpy as np

from art import mcp_server as A
from art.pipeline import _load_ts_model
from art.diagnosis import diagnose
from art.describe import describe_formal_tests

# --- paseo aleatorio LIMPIO con UN anomalo enorme en la innovacion -----------
# El modelo correcto es ARIMA(0,1,0). Sin tratar el anomalo, la Q sale bien
# (no hay estructura que capturar) pero la normalidad se hunde: es el caso
# de libro de "hay que intervenir antes de seguir".
rng = np.random.default_rng(12)
n = 120
a = rng.normal(0, 1.0, n)
a[60] = 9.0                                  # el anomalo, z ~ 9
y = 100.0 + np.cumsum(a)

d = tempfile.mkdtemp(prefix="bug0025-")
inp = os.path.join(d, "SYN.inp")
A.create_inp(list(map(float, y)), inp, name="SYN", freq=4,
             start_year=1990, start_period=1)

out = os.path.join(d, "SYN_m00.inp")
A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=1, D=0,
                       p=0, q=0, n_harmonics=0, seasonal=False,
                       estimate_mu=False)

ts, m = _load_ts_model(out.replace(".inp", ".pre"))
m.fit()

# --- lo que la diagnosis ve -------------------------------------------------
dg = diagnose(m)
peor_q = min(dg.q_pvalues) if dg.q_pvalues else 1.0
print("DIAGNOSIS del modelo:")
print("  Q  (p-valor minimo) : %.4f  %s" % (peor_q, "OK" if peor_q > 0.05 else "FALLA"))
print("  JB (normalidad)     : %.3f  p=%.6f  %s"
      % (dg.jb_stat, dg.jb_pvalue, "OK" if dg.jb_pvalue > 0.05 else "FALLA"))
print("  residuos |z|>3      : %d  %s"
      % (len(dg.extreme), [f"obs {i} z={z:+.2f}" for i, z in dg.extreme]))

# --- lo que formal_tests concluye -------------------------------------------
r = describe_formal_tests(m, run_meg=True)
print("\nformal_tests CONCLUYE:")
print("  ", r.recommendation.replace("\n", "\n   "))

adecuado = "El modelo es adecuado" in r.recommendation
mal = (dg.jb_pvalue <= 0.05) or (peor_q <= 0.05) or bool(dg.extreme)
avisa = "aún no es adecuado" in r.recommendation or "NO es adecuado" in r.summary
if adecuado and mal:
    print("\nBUG-0025 REPRODUCIDO: la diagnosis falla y formal_tests firma")
    print("  'El modelo es adecuado' sin haberla consultado siquiera.")
elif mal and avisa:
    print("\nARREGLADO: la diagnosis falla y formal_tests lo dice, en vez de")
    print("  firmar que el modelo es adecuado.")
else:
    print("\n(!) esta corrida no monto el caso (la diagnosis no falla)")
