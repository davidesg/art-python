"""BUG-0241 — guion_adopt cerraba el nodo `ordenes` de un ARMA(0,0) como ARMA(1,0).

El `.inp` de un paseo aleatorio lleva el relleno «1 1 / 0.0 0» —un AR(1) FIJO a
cero— y el spec del guion lo registraba como p=1. Al adoptar el (0,1,0) del IPC
de Alemania (IPC_DE.inp, al lado), el nodo de los órdenes se cerraba con
«ARMA(1,0) — corrige la propuesta», cuando lo adoptado ERA la propuesta.

El recorrido del carril guiado sobre IPC_DE, hasta adoptar el (0,1,0).
Exit 1 mientras el nodo se cierre como otra cosa que ARMA(0,0) o se diga que
corrige la propuesta; 0 cuando no.
"""
import json
import os
import shutil
import sys
import tempfile
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
os.environ.setdefault("ART_NO_VIEWER", "1")
warnings.filterwarnings("ignore")

from art import mcp_server as s                         # noqa: E402


def T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


w = tempfile.mkdtemp(prefix="bug0241-")
shutil.copy(os.path.join(HERE, "IPC_DE.inp"), w)
inp, g = os.path.join(w, "IPC_DE.inp"), os.path.join(w, "g.json")
GI = dict(guion_path=g, domain="price_index")
T(s.guided_identification(inp, expectativas="índice", **GI))
T(s.guided_identification(inp, lam=0, razon="dominio", **GI))
T(s.guided_identification(inp, lam=0, d=1, razon="tendencia", **GI))
T(s.guided_identification(inp, lam=0, d=1, D=0, razon="sin est.", **GI))
T(s.confirm_and_estimate(inp, os.path.join(w, "m01.inp"), lam=0, d=1, D=0,
                         p=0, q=0, n_harmonics=0, seasonal=False,
                         estimate_mu=True, domain="price_index",
                         guion_path=g, guion_name="m01 (0,1,0)", parent=5))
v = max(e["version"] for e in json.load(open(g))["entries"])
t = T(s.guion_adopt(g, v, why="El sobreajuste AR(1) no es significativo."))
linea = next((l for l in t.splitlines() if "ordenes =" in l), "(no aparece)")
print("el nodo de los órdenes se cierra:", linea.strip())
ok = "ordenes = ARMA(0,0)" in t and "corrige la propuesta" not in t
print("=" * 70)
print("OK: se cierra como ARMA(0,0), que era la propuesta." if ok else
      "FALLA (bug presente): el relleno AR(1) fijo cuenta como un orden estimado")
sys.exit(0 if ok else 1)
