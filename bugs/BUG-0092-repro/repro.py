"""BUG-0092 — `estimate_and_diagnose` registra un `.inp` que nunca escribe.

El convenio hace de cada versión una TERNA con el mismo basename: el `.inp` que
se estimó, el `.pre` con el óptimo y el `.out` con el registro. La entrada del
guion apunta al `.inp`, que es por donde el analista vuelve a un nodo y reestima.

`_persist_pre_out` escribe el `.pre` y el `.out` en el basename de
`output_path`, y el `.inp` no estaba: la entrada apuntaba al vacío. Y como los
otros dos SÍ están, la carpeta parece completa.
"""
import os
import sys
import tempfile

sys.path.insert(0, "src")

import numpy as np

FALLOS = []
try:
    import fue
    from art import mcp_server
    from art.pipeline import _RESCALE_FACTOR, _write_inp
except ImportError as e:                                  # pragma: no cover
    print(f"sin motor: {e}")
    sys.exit(0)

d = tempfile.mkdtemp()
rng = np.random.default_rng(3)
y = np.cumsum(rng.standard_normal(90) * 0.4) + 100.0
ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="R92")
m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
src = os.path.join(d, "R92.inp")
_write_inp(ts, m, src)

ed = getattr(mcp_server.estimate_and_diagnose, "fn",
             mcp_server.estimate_and_diagnose)
dst = os.path.join(d, "R92_m00.inp")
texto = "\n".join(getattr(c, "text", "") for c in ed(src, dst))

print("== A. La terna del basename de salida")
base = os.path.splitext(dst)[0]
est = {ext: os.path.exists(base + ext) for ext in (".inp", ".pre", ".out")}
for ext, hay in est.items():
    print(f"   {ext}: {'sí' if hay else 'NO'}")
if not est[".inp"]:
    print("   FALLA: hay artefactos y no la especificación que los produjo.")
    FALLOS.append("terna sin .inp")

print("\n== B. Lo que el guion registra, ¿resuelve?")
import json
g = [f for f in os.listdir(d) if f.endswith("guion.json")]
if not g:
    print("   FALLA: no se registró nada")
    FALLOS.append("sin guion")
else:
    e = json.load(open(os.path.join(d, g[0])))["entries"][0]
    p = e.get("inp_path") or ""
    ok = os.path.exists(p)
    print(f"   inp_path = {os.path.basename(p)}   ¿existe? {ok}")
    if not ok:
        print("   FALLA: el mapa apunta a un fichero que no está.")
        FALLOS.append("inp_path no resuelve")

print("\n== C. La copia es del ESPEC, no del modelo ajustado")
# Reserializar el modelo ajustado escribiría las estimaciones donde van las
# semillas — la trampa de BUG-0027 dentro de un `.inp`.
if est[".inp"]:
    import filecmp
    igual = filecmp.cmp(src, dst, shallow=False)
    print(f"   copia byte a byte del fuente: {igual}")
    if not igual:
        print("   FALLA: el .inp de la terna no es la especificación de origen")
        FALLOS.append("el .inp copiado difiere del fuente")

print("\n== D. Un registro que no resuelve se DICE")
from art.pipeline import _load_fitted
_, m_fit = _load_fitted(src)
n = mcp_server._record_to_guion(
    model=m_fit, inp_path=os.path.join(d, "no_existe.inp"), lam=0.0,
    guion_path=os.path.join(d, "aviso.json"), name="x")
print(f"   nota: {n}")
if "no existe" not in n:
    print("   FALLA: se registra una ruta ausente en silencio")
    FALLOS.append("no avisa de la ruta ausente")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: la terna queda completa y el guion avisa si lo que registra no está.")
