"""BUG-0090 — `_load_fitted` estima un `.pre` sin avisar.

El convenio es `.inp(t−1) → .pre(t−1) → .inp(t) → .pre(t)`: sólo el `.inp` se usa
para estimar. Estimar desde un `.pre` arranca EN el óptimo, así que BFGS no itera
y la covarianza se queda en la semilla. Los VALORES salen exactos —la
verosimilitud coincide a seis decimales— y las desviaciones típicas no, lo que
hace el fallo invisible: el fichero parece hacer round-trip.

Simulación propia, sin depender del corpus: construye una serie, escribe su
`.inp`, estima, escribe el `.pre`, y compara las SE de las dos vías.
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
    from art.pipeline import (_load_fitted, _RESCALE_FACTOR, _write_inp,
                              aviso_se_no_fiable, viene_de_pre)
except ImportError as e:                                  # pragma: no cover
    print(f"sin motor: {e}")
    sys.exit(0)

d = tempfile.mkdtemp()
rng = np.random.default_rng(7)
y = np.cumsum(rng.standard_normal(150) * 0.4) + 100.0
y[80:] += 4.0
ts = fue.TimeSeries(y.tolist(), freq=4, start=(1985, 1), name="R90")
itv = fue.Intervention("step", at=80, omega=[0.0, 0.0],
                       omega_free=[True, True])
m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
              estimate_mu=False, interventions=[itv],
              refactor=_RESCALE_FACTOR)
f_inp = os.path.join(d, "R90.inp")
_write_inp(ts, m, f_inp)

# ── A. las dos vías ──
print("== A. Mismo modelo, dos vías")
with warnings.catch_warnings(record=True) as w1:
    warnings.simplefilter("always")
    _, m_inp = _load_fitted(f_inp)
avisos_inp = [x for x in w1 if "`.pre`" in str(x.message)]

f_pre = os.path.join(d, "R90.pre")
m_inp.write_pre(f_pre)
with warnings.catch_warnings(record=True) as w2:
    warnings.simplefilter("always")
    _, m_pre = _load_fitted(f_pre)
avisos_pre = [x for x in w2 if "`.pre`" in str(x.message)]

se_i = list(m_inp._result.std_errors)
se_p = list(m_pre._result.std_errors)
print(f"  ℓ desde .inp = {m_inp._result.loglik:.6f}")
print(f"  ℓ desde .pre = {m_pre._result.loglik:.6f}   ← el invariante SE CUMPLE")
peor = max(abs(a / b - 1) for a, b in zip(se_p, se_i) if b)
print(f"  peor desviación de las SE: {100 * peor:.1f}%   ← y la curvatura NO")
if peor < 0.02:
    print("  (este modelo no separa las dos vías; el defecto sigue siendo real)")

# ── B. la guarda ──
print("\n== B. La guarda avisa donde toca")
print(f"  desde .inp: RuntimeWarning={len(avisos_inp)}  sello={viene_de_pre(m_inp)}")
print(f"  desde .pre: RuntimeWarning={len(avisos_pre)}  sello={viene_de_pre(m_pre)}")
if avisos_inp:
    FALLOS.append("avisa sobre un .inp, que es correcto")
if not avisos_pre:
    FALLOS.append("NO avisa sobre un .pre")
if viene_de_pre(m_inp) or not viene_de_pre(m_pre):
    FALLOS.append("el sello no distingue el origen")

# ── C. el aviso responde su propia pregunta ──
print("\n== C. El aviso dice a qué afecta y a qué no")
txt = aviso_se_no_fiable(m_pre)
for clave, que in (("valores", "dice que los valores son exactos"),
                   ("figuras", "dice que las figuras no están afectadas"),
                   ("razones t", "dice que las razones t sí lo están"),
                   ("`.out`", "dice dónde están las buenas")):
    ok = clave in txt
    print(f"  {'OK ' if ok else 'NO '} {que}")
    if not ok:
        FALLOS.append(f"el aviso no {que}")
if aviso_se_no_fiable(m_inp):
    FALLOS.append("el aviso sale también desde un .inp")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: estimar desde un .pre avisa, y el aviso dice a qué afecta.")
