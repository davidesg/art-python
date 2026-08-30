"""BUG-0022: un testigo de sobrediferenciación que se va a NEGATIVO se informa
como «banda de cuasi-cancelación».

`dcd_overdiff_regular` documenta su propio modo de fallo:

    «Left free from a data-driven start, a plain regular MA can drift NEGATIVE
     — its root then points toward B=-1 and it measures the *Nyquist*
     (semiannual) frequency, not f=0. The +0.85 start keeps the witness on the
     f=0 axis.»

Cuando esa salvaguarda NO sujeta al testigo, theta_hat sale negativo y la
lectura en f=0 deja de ser valida. Nadie lo comprobaba. Peor: describe.py medía
la distancia a la frontera como

    abs(1.0 - abs(theta_hat))          # <- el abs() INTERIOR borra el signo

de modo que theta_hat=-0.47 se presentaba «a 0.5332 de la frontera», dentro de
la banda de cuasi-cancelacion r~0.90-0.95, cuando la distancia real a theta=+1
es 1.4668 y el testigo esta en OTRO EJE.

Serie de prueba: AR(2) con un par complejo de modulo ~0.79 y frecuencia casi
cero (phi1=1.5708, phi2=-0.6191), que es la que se midio en ln PGAS (precio de
exportacion del gas boliviano, 2004-2024). Esa configuracion es la que dispara
el mensaje enganoso, porque hace que Shin-Fuller diga ESTACIONARIO mientras el
testigo del DCD se va a NEGATIVO: el bloque narrativo solo se emite cuando los
dos lados DISCREPAN. Su primera diferencia tiene ACF(1) claramente POSITIVA, o
sea que la diferencia no sobra y el testigo no tiene ningun motivo para
acercarse a +1.

    python3 bugs/BUG-0022-repro/repro.py
"""
import copy
import os
import tempfile

import numpy as np

from art import mcp_server as A
from art.pipeline import _load_ts_model
from art.formal_tests import dcd_overdiff_regular
from art.describe import describe_formal_tests

# DGP: ARIMA(1,1,0) con phi=0.58 -- I(1) POR CONSTRUCCION, n=84 como el TFM.
# Al ajustarle un AR(2) EN NIVELES (que es lo que hace un analista que cree la
# serie estacionaria) se obtiene la configuracion de ln PGAS: Shin-Fuller dice
# ESTACIONARIO y el testigo del DCD se va a NEGATIVO -> los dos lados discrepan
# -> se emite el bloque narrativo. La semilla 9 la fija; con otras semillas el
# mismo DGP manda el testigo a cualquier punto entre -0.57 y +1.00, que ya dice
# bastante sobre lo fragil que es este optimo.
rng = np.random.default_rng(9)
n = 84
u = np.zeros(n)
for t in range(1, n):
    u[t] = 0.58 * u[t - 1] + rng.normal(0, 1.0)
y = 100.0 + np.cumsum(u)

dy = np.diff(y)
acf1 = np.corrcoef(dy[:-1], dy[1:])[0, 1]
print("ACF(1) de la primera diferencia = %+.3f  (positiva => la dif NO sobra)" % acf1)

d = tempfile.mkdtemp(prefix="bug0022-")
inp = os.path.join(d, "SYN.inp")
A.create_inp(list(map(float, y)), inp, name="SYN", freq=4,
             start_year=1990, start_period=1)

# el AR(2) en NIVELES: la configuracion en que Shin-Fuller dira "estacionario"
out = os.path.join(d, "SYN_base.inp")
A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=0, D=0,
                       p=2, q=0, n_harmonics=0, seasonal=False,
                       estimate_mu=True)
ts, m = _load_ts_model(out.replace(".inp", ".pre"))
m.fit()

r = dcd_overdiff_regular(m)
th = r.coef_free
print("\ntestigo:  theta_hat = %+.4f   LR = %.3f   (crit 5%% = %.2f)"
      % (th, r.lr, r._crit['5%']))
print("  distancia a la frontera theta=+1")
print("    formula ANTIGUA  abs(1-abs(th)) = %.4f   <- lo que se informaba" % abs(1.0 - abs(th)))
print("    distancia REAL         1 - th   = %.4f" % (1.0 - th))
print("  banda de cuasi-cancelacion (r~0.90-0.95) exige |1-th| ~ 0.05-0.10;")
print("  con th = %+.4f el testigo esta en el eje de NYQUIST, no en f=0." % th)

if th >= 0:
    print("\n(!) esta corrida no reprodujo el arrastre negativo (semilla cambiada?)")
else:
    print("\nBUG-0022 REPRODUCIDO: theta_hat < 0.")

print("\n--- el informe completo ---")
txt = describe_formal_tests(m, run_meg=False)
for line in txt.summary.splitlines():
    if any(k in line for k in ("Shin-Fuller", "lado AR", "lado MA", "eje f=0",
                               "cuasi-cancelaci", "DISCREPAN", "Phi", "theta")):
        print(" ", line.strip())
print("\n--- recomendacion ---")
print(" ", txt.recommendation.replace("\n", "\n  "))
