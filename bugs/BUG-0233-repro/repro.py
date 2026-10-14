"""BUG-0233: el paso 4 declara el empate «entre ARIMA(1,1,1) y ARIMA(3,1,0)»
—los dos primeros de la lista— mientras la ficha del empate compara (1,1,1),
(1,1,2) y (2,1,1).

Salamanca (precio €/m², 2010:01-2025:08), con el .inp de BUG-0232-repro.

    PYTHONPATH=src python3 bugs/BUG-0233-repro/repro.py   # sale 1 mientras siga abierto
"""
import os, re, shutil, sys, tempfile
os.environ.setdefault("ART_NO_VIEWER", "1")
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
txt = lambda o: "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                          for c in (o if isinstance(o, list) else [o]))
HERE = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as tmp:
    shutil.copy(os.path.join(HERE, "..", "BUG-0232-repro", "Salamanca.inp"), tmp)
    out = txt(fn(M.guided_identification)(os.path.join(tmp, "Salamanca.inp"),
                                          lam=0, d=1, D=0))
rec = next((l for l in out.splitlines() if l.startswith("Decisión ambigua entre")), "")
ficha = next((l for l in out.splitlines() if l.startswith("| | (")), "")
en_rec = set(re.findall(r"ARIMA\((\d+),\d+,(\d+)\)", rec))
en_ficha = set(re.findall(r"\| \((\d+),\d+,(\d+)\)", ficha))
print("recomendación:", rec[:90])
print("ficha:        ", ficha)
sys.exit(0 if en_rec and en_rec == en_ficha else 1)
