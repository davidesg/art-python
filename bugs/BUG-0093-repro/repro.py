"""BUG-0093 — `n_omega` tenía dos semánticas y el docstring documentaba la falsa.

`guided_intervention` decía en su docstring **«n_omega: orden del numerador
ω(B)»**, y el parámetro cuenta COEFICIENTES. Y su Call 3 informaba «de orden ω
{n_omega−1}», reforzando la lectura equivocada.

Consecuencia: un analista al que la regla de Treadway le ordenaba subir de
peldaño pasaba `n_omega=1` creyendo pedir la escalera de dos, recibía un escalón
simple, y leía «orden ω 0» — con lo que parecía que la herramienta le había
ignorado. No le ignoraba: le había documentado otra cosa.

**Cuál de las dos semánticas gana, y por qué.** La de CONTAR, porque es la de las
otras cuatro piezas del nodo: `suggest_intervention_form` («nº de coeficientes
ω»), `incident_configurations` («N escalones consecutivos en el nivel»), la
escalera («N escalones») y la propia Call 2, que devuelve el `n_omega` ya
calculado listo para pegar en la Call 3. Cambiarla habría roto esas cuatro para
arreglar un docstring.

Este repro NO comprueba «n_omega=1 da 2 escalones» —ése era el criterio del
reporte y codifica el lado perdedor—. Comprueba que hay UNA semántica, que está
documentada de verdad, y que el bucle de la herramienta se cierra.
"""
import inspect
import os
import sys
import tempfile

sys.path.insert(0, "sys" and "src")

import numpy as np

FALLOS = []
try:
    import fue
    from art import mcp_server
    from art.pipeline import _RESCALE_FACTOR, _load_ts_model, _write_inp
except ImportError as e:                                   # pragma: no cover
    print(f"sin motor: {e}")
    sys.exit(0)


def doc(nombre):
    f = getattr(mcp_server, nombre)
    return inspect.getdoc(getattr(f, "fn", f)) or ""


print("== A. Una sola semántica en las dos herramientas")
d_gi, d_sif = doc("guided_intervention"), doc("suggest_intervention_form")
gi_cuenta = "cuántos ω" in d_gi or "cuántos escalones" in d_gi
gi_miente = "orden del numerador" in d_gi
sif_cuenta = "coeficientes ω" in d_sif
print(f"  guided_intervention documenta CONTAR : {gi_cuenta}")
print(f"  guided_intervention dice «orden»      : {gi_miente}  (debe ser False)")
print(f"  suggest_intervention_form documenta CONTAR : {sif_cuenta}")
if not gi_cuenta or gi_miente or not sif_cuenta:
    FALLOS.append("las dos herramientas no documentan la misma semántica")

print("\n== B. Y la equivalencia está escrita, para quien venga del operador")
if "orden N−1" in d_gi or "orden N-1" in d_gi:
    print("  «N escalones ⇔ ω(B) de orden N−1»: sí")
else:
    print("  FALLA: no se dice la equivalencia")
    FALLOS.append("falta la equivalencia escalones↔orden")

# ── el efecto, de extremo a extremo ──
d = tempfile.mkdtemp()
rng = np.random.default_rng(17)
y = np.cumsum(rng.standard_normal(120) * 0.4) + 100.0
y[60] += 5.0
y[61] += 3.0
ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="R93")
m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
base = os.path.join(d, "R93.inp")
_write_inp(ts, m, base)
gi = getattr(mcp_server.guided_intervention, "fn",
             mcp_server.guided_intervention)

print("\n== C. n_omega=k construye k escalones, y la cabecera lo dice ASÍ")
import warnings
for k in (1, 2, 3):
    out = os.path.join(d, f"m{k}.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = "\n".join(getattr(c, "text", "")
                      for c in gi(base, date="Q1/2010", form="step",
                                  n_omega=k, output_path=out))
    _, mm = _load_ts_model(out)
    itv = [i for i in mm.interventions if i.type == "step"][-1]
    cab = next((l.strip() for l in t.split("\n") if "Se construye" in l), "")
    ok_n = len(itv.omega) == k
    ok_txt = f"{k} escalón(es)" in cab
    print(f"  n_omega={k}: construye {len(itv.omega)}  cabecera habla de "
          f"escalones: {ok_txt}")
    if not ok_n:
        FALLOS.append(f"n_omega={k} no construyó {k}")
    if not ok_txt:
        FALLOS.append(f"la cabecera de n_omega={k} no habla en escalones")

print("\n== D. El bucle se cierra: lo que la Call 2 sugiere, la Call 3 lo hace")
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    t2 = "\n".join(getattr(c, "text", "")
                   for c in gi(base, date="Q1/2010", threshold=2.5))
import re
mm_ = re.search(r"n_omega=(\d+)", t2)
if not mm_:
    print("  FALLA: la Call 2 no sugiere n_omega")
    FALLOS.append("la Call 2 no sugiere n_omega")
else:
    n_sug = int(mm_.group(1))
    out = os.path.join(d, "cierre.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        gi(base, date="Q1/2010", form="step", n_omega=n_sug, output_path=out)
    _, mm2 = _load_ts_model(out)
    itv = [i for i in mm2.interventions if i.type == "step"][-1]
    print(f"  la Call 2 sugiere n_omega={n_sug}; la Call 3 construye "
          f"{len(itv.omega)} escalón(es)")
    if len(itv.omega) != n_sug:
        FALLOS.append("el bucle no se cierra")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: una semántica, documentada de verdad, y el bucle se cierra.")
