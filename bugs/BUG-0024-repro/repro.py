"""BUG-0024: la banda de cuasi-cancelacion se afirma por la DISCREPANCIA de los
dos contrastes, sin mirar nunca la distancia del testigo a la frontera.

En la tabla `tab:compare` del paper (SF_MEG), la `r` de la banda r~0.90-0.95 es
el MODULO DEL FACTOR MA de la familia N = phi_f(B)^-1 theta_f(B;r) a.  En el
caso regular ese modulo es |theta_hat|, que el codigo tiene delante en
`od_res.coef_free`.  Aun asi, cualquier discrepancia se rotula como esa banda.

Esta corrida ensena un testigo en el eje correcto (theta_hat > 0) pero LEJOS de
la frontera: r_hat ~ 0.78, que en la propia tabla del paper NO es la banda.

    python3 bugs/BUG-0024-repro/repro.py
"""
import os
import tempfile

import numpy as np

from art import mcp_server as A
from art.pipeline import _load_ts_model
from art.formal_tests import dcd_overdiff_regular, shin_fuller
from art.describe import describe_formal_tests

# Misma construccion que BUG-0022 (ARIMA(1,1,0), phi=0.58, n=84, ajustado con un
# AR(2) EN NIVELES) pero con la semilla 7, que deja al testigo en el eje bueno.
rng = np.random.default_rng(7)
n = 84
u = np.zeros(n)
for t in range(1, n):
    u[t] = 0.58 * u[t - 1] + rng.normal(0, 1.0)
y = 100.0 + np.cumsum(u)

d = tempfile.mkdtemp(prefix="bug0024-")
inp = os.path.join(d, "S.inp")
A.create_inp(list(map(float, y)), inp, name="S", freq=4,
             start_year=2004, start_period=1)
out = os.path.join(d, "S_ar2.inp")
A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=0, D=0,
                       p=2, q=0, n_harmonics=0, seasonal=False,
                       estimate_mu=True)
ts, m = _load_ts_model(out.replace(".inp", ".pre"))
m.fit()

sf = shin_fuller(m)
od = dcd_overdiff_regular(m)
th = od.coef_free
print("Shin-Fuller: estacionario = %s   (lado AR: 'd basta')" % sf.stationary)
print("testigo:  theta_hat = %+.4f   LR = %.3f  (crit 5%% = %.2f)"
      % (th, od.lr, od._crit['5%']))
print("  => r_hat = |theta_hat| = %.3f      distancia a la frontera = %.3f"
      % (abs(th), 1.0 - th))
print("  la banda del paper es r ~ 0.90-0.95, o sea distancia 0.05-0.10.")

txt = describe_formal_tests(m, run_meg=False)
banda = "es la **banda de cuasi-cancelación**" in txt.summary
equiv = "equivalentes en **previsión**" in txt.summary or "equivalentes en previsión" in txt.summary
print("\ninforme:")
print("  afirma la banda r~0.90-0.95 ...... %s" % banda)
print("  afirma equivalencia en prevision . %s" % equiv)
print("  distancia impresa ................ %.4f" % (1.0 - th))

if banda and abs(th) < 0.85:
    print("\nBUG-0024 REPRODUCIDO: se rotula 'banda r~0.90-0.95' con r_hat = %.3f."
          % abs(th))
else:
    print("\n(!) esta corrida no cayo en la rama (semilla cambiada?)")

print("\ntabla tab:compare del paper, para situar r_hat:")
print("  r          1.00   0.95   0.90   0.80   0.50   0.00")
print("  DCD->stoch 0.05   0.93   1.00   1.00   1.00   1.00")
print("  SF->determ 1.00   1.00   1.00   0.87   0.20   0.05")
print("  => la discrepancia NO es exclusiva de 0.90-0.95: a r=0.80 ocurre el 87%")
print("     de las veces, y a r=0.50 todavia el 20%.")
