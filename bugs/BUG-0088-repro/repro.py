"""BUG-0088 — `estimate_and_diagnose` persistía `.pre`/`.out` pero no el guion.

Su docstring prometía «the same trio confirm_and_estimate writes, so a model
estimated through this clean path is not left without artefacts», y era cierto
para los artefactos y falso para el registro: no llevaba `guion_path` ni escribía
el guion, que `_derive_guion_path` declara OBLIGATORIO. Un modelo por esta vía
quedaba con artefactos y sin entrada, y el guion se desincronizaba en silencio.

Comprueba el EFECTO, no la firma: una firma con parámetros de guion que no
escriben nada pasaría igual. Cae a la comprobación de firmas sólo si no hay
motor.
"""
import inspect
import os
import shutil
import sys
import tempfile

sys.path.insert(0, "src")

from art import mcp_server

FALLOS = []
GUION = ("guion_path", "guion_name", "guion_decision", "guion_rationale",
         "guion_problems", "guion_next")


def params(nombre):
    f = getattr(mcp_server, nombre)
    return list(inspect.signature(getattr(f, "fn", f)).parameters)


print("== A. La superficie")
for n in ("estimate_and_diagnose", "confirm_and_estimate"):
    tiene = [p for p in params(n) if p in GUION]
    print(f"  {n:24} parámetros de guion: {tiene or 'NINGUNO'}")
    if not tiene:
        FALLOS.append(f"{n} sin parámetros de guion")

print("\n== B. El efecto: ¿queda la entrada en disco?")
try:
    import numpy as np

    import fue
    from art.pipeline import _RESCALE_FACTOR, _write_inp

    d = tempfile.mkdtemp()
    rng = np.random.default_rng(4)
    y = np.cumsum(rng.standard_normal(80) * 0.3) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="R88")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    base = os.path.join(d, "R88.inp")
    _write_inp(ts, m, base)

    ed = getattr(mcp_server.estimate_and_diagnose, "fn",
                 mcp_server.estimate_and_diagnose)
    salida = os.path.join(d, "R88_m00.inp")
    ed(base, salida)

    hay = sorted(f for f in os.listdir(d) if f.endswith((".pre", ".out"))
                 or f.endswith("guion.json"))
    print("  artefactos y registro:", hay)
    pre = any(f.endswith(".pre") for f in hay)
    out = any(f.endswith(".out") for f in hay)
    gui = any(f.endswith("guion.json") for f in hay)
    print(f"  .pre={pre}  .out={out}  guion={gui}")
    if pre and out and not gui:
        print("  FALLA: persiste los artefactos y NO el registro.")
        FALLOS.append("artefactos sin guion")
    elif not gui:
        FALLOS.append("no se escribió el guion")

    if gui:
        import json
        with open(os.path.join(d, "R88_guion.json")) as fh:
            g = json.load(fh)
        print(f"  entradas en el guion: {len(g['entries'])}"
              f"  ({g['entries'][0]['name']})")
        if not g["entries"]:
            FALLOS.append("guion vacío")
    shutil.rmtree(d, ignore_errors=True)
except ImportError as e:
    print(f"  [sin motor: {e}] — sólo se comprobaron las firmas")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: la vía limpia deja los artefactos Y el registro, como la guiada.")
