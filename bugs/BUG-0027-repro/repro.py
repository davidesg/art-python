"""BUG-0027: reestimar un modelo desde su PROPIO .pre devuelve una covarianza
degenerada -- todos los errores tipicos identicos y sin sentido.

El invariante del .pre es que los parametros NO se muevan: "corre fue sobre un
.pre y los numeros no cambian". Eso se cumple, y es lo correcto. Pero tiene una
consecuencia que nadie comprueba: el optimizador arranca YA en el optimo, para
en niter=0, y el factor BFGS de la inversa del hessiano --que se inicializa como
un multiplo escalar de la identidad-- nunca llega a actualizarse.

Resultado: cov_matrix = c * I. Todos los errores tipicos valen lo mismo. Y el
resultado se declara `converged=True` con `termcode=1`, asi que nada avisa.

No falla ruidosamente: el valor que sale es pequeno y creible, de modo que los
estadisticos t salen enormes y falsos.

Afecta a todo lo que lea errores tipicos de un .pre:
  - las tablas de parametros que ART imprime (los "(0.1552)" bajo cada coeficiente)
  - `ar_factorization`, cuyos +/- salen del metodo delta sobre esa covarianza
  - `test_intervention` / `simplify_interventions`, cuyos t salen de ahi
y el .pre es el fichero de contrato de la suite.

    python3 bugs/BUG-0027-repro/repro.py
"""
import os
import tempfile

import numpy as np

import fue
from art.pipeline import _write_inp, _load_ts_model


def ee(m):
    return np.sqrt(np.diag(np.asarray(m._result.cov_matrix)))


def degenerada(se):
    return len(se) > 1 and bool(np.allclose(se, se[0], rtol=1e-6))


# --- serie con estructura suficiente para que el ajuste sea no trivial -------
rng = np.random.default_rng(19)
n = 120
a = rng.normal(0, 1.0, n)
u = np.zeros(n)
for t in range(2, n):
    u[t] = 0.75 * u[t - 1] - 0.30 * u[t - 2] + a[t]
y = 100.0 + np.cumsum(u)

ts = fue.TimeSeries(list(map(float, y)), freq=4, start=(2004, 1), name="SYN")

# (1) ajuste NORMAL, arrancando lejos del optimo
m1 = fue.Model(ts, d=1, ifadf=[0, 0, 0], ar=[[0.0, 0.0]], ar_free=[[True, True]],
               mu=0.0, estimate_mu=False)
m1.fit()
se1 = ee(m1)
print("(1) ajuste normal (arranca en 0):")
print("    niter = %s   converged = %s   termcode = %s"
      % (m1._result.niter, m1._result.converged, m1._result.termcode))
print("    params = %s" % np.round(np.asarray(m1._result.params), 5).tolist())
print("    ee     = %s   -> degenerada? %s" % (np.round(se1, 5).tolist(), degenerada(se1)))

# (2) escribir su .pre y reestimar DESDE EL .pre
d = tempfile.mkdtemp(prefix="bug0027-")
p = os.path.join(d, "SYN.pre")
_write_inp(ts, m1, p)
_, m2 = _load_ts_model(p)
m2.fit()
se2 = ee(m2)
print("\n(2) reestimado desde su propio .pre:")
print("    niter = %s   converged = %s   termcode = %s"
      % (m2._result.niter, m2._result.converged, m2._result.termcode))
print("    params = %s" % np.round(np.asarray(m2._result.params), 5).tolist())
print("    ee     = %s   -> degenerada? %s" % (np.round(se2, 5).tolist(), degenerada(se2)))

print("\n    cov_matrix del (2):")
print(np.round(np.asarray(m2._result.cov_matrix), 6))

igual_params = np.allclose(np.asarray(m1._result.params), np.asarray(m2._result.params), atol=1e-8)
print("\n    parametros identicos entre (1) y (2)? %s   <- el invariante del .pre SI se cumple"
      % igual_params)

if degenerada(se2) and not degenerada(se1):
    print("\nBUG-0027 REPRODUCIDO: mismos parametros, misma verosimilitud,")
    print("  covarianza degenerada y converged=True sin ningun aviso.")
    print("  factor entre los ee: %.1fx en el primer parametro" % (se2[0] / se1[0]))
else:
    print("\n(!) no reproducido en esta corrida")
