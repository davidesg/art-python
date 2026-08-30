"""BUG-0030: toda intervencion que anade el carril autonomo se coloca d+D*s
periodos ANTES de donde esta el anomalo que la disparo.

`diag.extreme` devuelve indices 1-based sobre la serie de RESIDUOS, que empieza
`d + D*s` observaciones despues de la original. `decide_interventions` los
convierte a posicion 0-based sobre la serie ORIGINAL con

    at_0 = obs - 1          # policy.py:331

y eso solo seria correcto si las dos series arrancaran a la vez. La conversion
correcta es `obs - 1 + d + D*s`.

Y la forma del defecto es estructural, no aritmetica: `decide_interventions` no
recibe `d` ni `D`, asi que NO PUEDE hacer la conversion aunque quisiera.

Lo que lo hace grave es que es SILENCIOSO. El modelo sigue aprobando: una
intervencion colocada un periodo antes absorbe parte del episodio, la diagnosis
da limpio, y nadie nota que se esta modelando la fecha equivocada -- con el signo
invertido, ademas, porque esta ajustando otra cosa.

    python3 bugs/BUG-0030-repro/repro.py
"""
import os
import tempfile

import numpy as np

from art import mcp_server as A
from art import policy as pol
from art.describe import _resid_start
from art.diagnosis import diagnose
from art.pipeline import _load_ts_model


def _fecha_residuos(m, k):
    """Fecha de la observacion k (1-based) de la serie de RESIDUOS."""
    y0, p0 = _resid_start(m)
    o = (p0 - 1) + (k - 1)
    return y0 + o // 4, o % 4 + 1


def _fecha_original(ts, at_0):
    """Fecha de la posicion at_0 (0-based) de la serie ORIGINAL."""
    st = list(ts.start)
    yy, qq = (st[0], st[1]) if st[0] > 100 else (st[1], st[0])
    o = (qq - 1) + at_0
    return yy + o // 4, o % 4 + 1


# --- serie con UN anomalo en una fecha conocida -----------------------------
rng = np.random.default_rng(23)
n = 84
a = rng.normal(0, 1.0, n)
OBJETIVO = 19                      # 0-based en la serie original -> 2008:Q4
a[OBJETIVO] = -9.0
y = 100.0 + np.cumsum(a)

d = tempfile.mkdtemp(prefix="bug0030-")
inp = os.path.join(d, "SYN.inp")
A.create_inp(list(map(float, y)), inp, name="SYN", freq=4,
             start_year=2004, start_period=1)
out = os.path.join(d, "SYN_m00.inp")
A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=1, D=0,
                       p=0, q=0, n_harmonics=0, seasonal=False, estimate_mu=False)

ts, m = _load_ts_model(out)
m.fit()
dg = diagnose(m)
obs, z = max(dg.extreme, key=lambda t: abs(t[1]))

print("el anomalo se PUSO en la posicion 0-based %d de la serie original = %d:Q%d"
      % (OBJETIVO, *_fecha_original(ts, OBJETIVO)))
print()
print("diagnose lo encuentra en:   obs %d (z=%+.2f) de la serie de RESIDUOS" % (obs, z))
print("   y esa obs es la fecha:   %d:Q%d      <- coincide, la deteccion es correcta"
      % _fecha_residuos(m, obs))
print()

desfase = int(m.d) + int(m.D) * ts.freq
sin = pol.decide_interventions(dg.extreme, [])[0][0]              # offset=0
con = pol.decide_interventions(dg.extreme, [], offset=desfase)[0][0]

print("decide_interventions SIN el desfase:  at_0 = %d  ->  %d:Q%d   <- el defecto"
      % (sin, *_fecha_original(ts, sin)))
print("decide_interventions CON el desfase:  at_0 = %d  ->  %d:Q%d   <- correcto"
      % (con, *_fecha_original(ts, con)))
print("\ndesfase = d + D*s = %d periodo(s)" % desfase)

print()
if sin != OBJETIVO and con == OBJETIVO:
    print("BUG-0030 REPRODUCIDO y ARREGLADO: sin el desfase la intervencion cae")
    print("  %d periodo(s) antes del anomalo; con el, en su fecha." % (OBJETIVO - sin))
elif con != OBJETIVO:
    print("(!) ni con el desfase cae en la fecha esperada")
else:
    print("(!) esta corrida no reprodujo el desfase")

# --- y lo que lo hace silencioso --------------------------------------------
print("\n--- por que no salta: por AJUSTE son indistinguibles ---")
import fue
for etiqueta, a0 in (("mal colocada (at_0=%d)" % at_0, at_0),
                     ("bien colocada (at_0=%d)" % OBJETIVO, OBJETIVO)):
    mm = fue.Model(ts, d=1, ifadf=[0, 0, 0],
                   mu=0.0, estimate_mu=False,
                   interventions=[fue.Intervention("impulse", at=a0, omega=[0.0],
                                                   omega_free=[True])])
    mm.fit()
    ddg = diagnose(mm)
    w = mm.interventions[0].omega[0]
    se = float(np.sqrt(np.diag(np.asarray(mm._result.cov_matrix))[0]))
    print("  %-26s omega=%+8.3f (t=%+5.2f)  logL=%9.3f  Q p-min=%.4f"
          % (etiqueta, w, w / se, mm._result.loglik, min(ddg.q_pvalues)))
print()
print("  Signo INVERTIDO, magnitud casi identica, y la verosimilitud apenas se")
print("  mueve: un pulso de nivel un periodo antes ajusta la imagen especular.")
print("  Nada los distingue por ajuste, y por eso el defecto no salta.")
