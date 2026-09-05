"""BUG-0091 — `get_out_report` no leía el `.out`: lo volvía a fabricar.

La única herramienta cuyo propósito declarado es devolver el registro de la
estimación reestimaba y generaba el informe otra vez. Y su docstring invitaba a
pasarle un `.pre`, con lo que devolvía un informe con las desviaciones típicas
muy desviadas del `.out` que estaba en el mismo directorio.

Importa porque **la covarianza no es una propiedad del óptimo**: es un
subproducto del camino del optimizador (BUG-0090), así que un fichero que sólo
guarda el óptimo no puede llevarla. El `.out` es la única constancia fiel.

Sintético y autónomo: construye su propia terna.
"""
import os
import sys
import tempfile
import warnings

sys.path.insert(0, "src")

import numpy as np

FALLOS = []
try:
    import fue
    from art import mcp_server
    from art.outfile import hay_out, lee_out
    from art.pipeline import _RESCALE_FACTOR, _load_fitted, _write_inp
except ImportError as e:                                  # pragma: no cover
    print(f"sin motor: {e}")
    sys.exit(0)

d = tempfile.mkdtemp()
rng = np.random.default_rng(11)
y = np.cumsum(rng.standard_normal(140) * 0.4) + 100.0
y[70:] += 5.0
ts = fue.TimeSeries(y.tolist(), freq=4, start=(1990, 1), name="R91")
itv = fue.Intervention("step", at=70, omega=[0.0], omega_free=[True])
m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
              estimate_mu=False, interventions=[itv], refactor=_RESCALE_FACTOR)
f_inp = os.path.join(d, "R91.inp")
_write_inp(ts, m, f_inp)
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    _, m_fit = _load_fitted(f_inp)
f_pre, f_out = os.path.join(d, "R91.pre"), os.path.join(d, "R91.out")
m_fit.write_pre(f_pre)
m_fit.write_out(f_out)
disco = open(f_out).read()

gor = getattr(mcp_server.get_out_report, "fn", mcp_server.get_out_report)


def texto(p):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return "\n".join(getattr(c, "text", "") for c in gor(p))


print("== A. Se LEE el registro, venga por donde venga de la terna")
for f in (f_inp, f_pre, f_out):
    t = texto(f)
    ok = disco.strip() in t
    leido = "Leído de" in t
    print(f"   {os.path.basename(f):10} devuelve el .out en disco: {ok}   "
          f"dice que lo lee: {leido}")
    if not ok:
        FALLOS.append(f"{os.path.basename(f)} no devuelve el registro")
    if not leido:
        FALLOS.append(f"{os.path.basename(f)} no dice que lo lee")

print("\n== B. Sin `.out`, se reestima Y SE DICE")
os.remove(f_out)
t = texto(f_inp)
dice = "REESTIMADO" in t
print(f"   avisa de que no es el registro: {dice}")
if not dice:
    FALLOS.append("reestima en silencio")

print("\n== C. El lector saca lo que hace falta para no reestimar")
m_fit.write_out(f_out)
r = lee_out(f_inp)                       # por el hermano
import math
print(f"   npar={r.npar}  ll={r.loglik}  sigma2={r.sigma2}")
print(f"   parámetros con SE: {len(r.parametros)}")
if not r.completo:
    FALLOS.append("la lectura no está completa")
if r.covarianza:
    coh = all(abs(math.sqrt(r.covarianza[i][i]) - r.parametros[i].se) < 1e-6
              for i in range(len(r.parametros)))
    print(f"   SE == sqrt(diag(covarianza)): {coh}")
    if not coh:
        FALLOS.append("las SE no cuadran con la covarianza")

print("\n== D. Un `.out` truncado no revienta la lectura")
recortado = os.path.join(d, "corto.out")
with open(recortado, "w") as fh:
    fh.write("\n".join(disco.split("\n")[:20]))
try:
    rc = lee_out(recortado)
    print(f"   leído sin excepción; completo={rc.completo} "
          f"parámetros={len(rc.parametros)}")
except Exception as e:
    print(f"   FALLA: {type(e).__name__}: {e}")
    FALLOS.append("un .out truncado levanta")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: el registro se lee; sólo se reestima si no está, y se dice.")
