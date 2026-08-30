"""BUG-0028: `preliminary_outlier_scan` descarta el modelo y escanea la serie
CRUDA -- y la llamada que ART imprime para analizar residuos cae justo ahi.

`confirm_and_estimate` termina su salida con esta sugerencia, literal:

    **Dudas?** Para ver cuanto distorsiona cada outlier la ACF, llama a:
      `preliminary_outlier_scan(inp_path="<modelo_actual>.pre", d=0, D=0, lam=1.0)`
      (muestra contribucion de cada outlier a cada lag de la ACF)

Pero la herramienta hace, en mcp_server.py:726:

    ts, _ = _load_ts_model(inp_path)          # <- se queda la serie, TIRA el modelo
    desc = describe_prelim_scan(ts, d=d, D=D, lam=lam, threshold=threshold)

de modo que con un `.pre` y `d=0, D=0, lam=1.0` lo que escanea es la serie
ORIGINAL, sin transformar y sin diferenciar. No los residuos del modelo.

Y no falla: devuelve un veredicto tranquilizador y falso -- "Sin observaciones
extremas. Las ACF/PACF reflejan fielmente la estructura ARMA" -- sobre un modelo
cuyos residuos tienen un anomalo de |z| casi 4.

El escaneo de residuos SI existe (`confirm_and_estimate` lo produce, con su panel
de contribucion a la ACF) pero esta encerrado dentro de esa herramienta y no hay
forma de invocarlo por separado.

    python3 bugs/BUG-0028-repro/repro.py
"""
import os
import tempfile

import numpy as np

from art import mcp_server as A
from art.diagnosis import diagnose
from art.pipeline import _load_ts_model

# --- nivel SUAVE con tendencia, y UN anomalo en la innovacion ---------------
# La configuracion que produce el falso negativo, y es la del caso real: en
# NIVELES la serie sube limpiamente y su desviacion tipica esta dominada por la
# tendencia, asi que ningun punto destaca. El anomalo vive en la DIFERENCIA.
rng = np.random.default_rng(31)
n = 96
y = 100.0 + 3.0 * np.arange(n) + np.cumsum(rng.normal(0, 1.0, n))
y[60:] += 40.0          # escalon: invisible en niveles, |z| enorme en la diferencia

d = tempfile.mkdtemp(prefix="bug0028-")
inp = os.path.join(d, "SYN.inp")
A.create_inp(list(map(float, y)), inp, name="SYN", freq=4,
             start_year=2000, start_period=1)

out = os.path.join(d, "SYN_m00.inp")
A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=1, D=0,
                       p=0, q=0, n_harmonics=0, seasonal=False, estimate_mu=False)
pre = out.replace(".inp", ".pre")

# --- lo que los residuos REALMENTE tienen -----------------------------------
ts, m = _load_ts_model(pre)
m.fit()
dg = diagnose(m)
peor = max(dg.extreme, key=lambda t: abs(t[1])) if dg.extreme else None
print("residuos del modelo estimado:")
print("   sigma = %.4f    residuos |z|>3: %d    %s"
      % (np.asarray(dg.residuals).std(ddof=0), len(dg.extreme),
         ("el mayor obs %d con z=%+.2f" % peor) if peor else ""))

# --- lo que la llamada RECOMENDADA POR ART responde -------------------------
res = A.preliminary_outlier_scan(inp_path=pre, d=0, D=0, lam=1.0, threshold=2.5)
texto = "\n".join(c.text for c in res if hasattr(c, "text"))
cabecera = [l for l in texto.splitlines() if "Serie tipificada" in l]
veredicto = [l for l in texto.splitlines()
             if "extrema" in l or "Sin observaciones" in l]

print("\nla llamada que ART recomienda para los residuos:")
print("   preliminary_outlier_scan(inp_path=<modelo>.pre, d=0, D=0, lam=1.0)")
print("  ", cabecera[0].strip() if cabecera else "(sin cabecera)")
for v in veredicto[:2]:
    print("  ", v.strip())

# la cabecera delata QUE serie ha escaneado
crudo = np.asarray(ts.data, float)
print("\n   media/sd de la serie CRUDA      : %.4f / %.4f" % (crudo.mean(), crudo.std(ddof=0)))
print("   media/sd de los RESIDUOS        : %.4f / %.4f"
      % (np.asarray(dg.residuals).mean(), np.asarray(dg.residuals).std(ddof=0)))

# (1) el defecto CENTRAL, siempre: escanea la serie equivocada
escanea_la_cruda = ("%.4f" % crudo.mean()) in texto
print("\n(1) la cabecera del escaneo trae la media/sd de la serie CRUDA: %s"
      % escanea_la_cruda)

# (2) la CONSECUENCIA, cuando el nivel es suave: falso negativo
falso_negativo = bool(dg.extreme) and "Sin observaciones extremas" in texto
print("(2) los residuos tienen un anomalo y el escaneo dice que no hay: %s"
      % falso_negativo)

if escanea_la_cruda:
    print("\nBUG-0028 REPRODUCIDO: la llamada que ART recomienda para los")
    print("  residuos analiza la serie original" +
          (", y aqui ademas devuelve un falso negativo." if falso_negativo else "."))
else:
    print("\n(!) no reproducido en esta corrida")
