"""BUG-0246: guided_identification (llamada 4 con pre_path) etiqueta el nodo
estacionalidad «D=0 (B1, armónicos deterministas)» en un modelo SIN armónicos
(Decisión A) y lo escribe como nodo nuevo, duplicado.

GAPGDPD (dolarización): el guion real hasta el n6 (estacionalidad confirmada
«D=0 (sin estacionalidad)», m00 y la intervención m01_s0804), y la llamada 4
con el `.pre` de la intervención.

    PYTHONPATH=src python3 bugs/BUG-0246-repro/repro.py   # sale 1 mientras siga abierto
"""
import json, os, shutil, sys, tempfile
os.environ.setdefault("ART_NO_VIEWER", "1")
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
HERE = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as tmp:
    for f in ("GAPGDPD.inp", "GAPGDPD_m01_s0804.pre"):
        shutil.copy(os.path.join(HERE, f), tmp)
    g = json.load(open(os.path.join(HERE, "GAPGDPD_guion.json")))
    g["entries"] = [e for e in g["entries"] if e["version"] <= 6]
    gp = os.path.join(tmp, "GAPGDPD_guion.json")
    json.dump(g, open(gp, "w"), ensure_ascii=False)
    fn(M.guided_identification)(os.path.join(tmp, "GAPGDPD.inp"), lam=0, d=1, D=0,
                                pre_path=os.path.join(tmp, "GAPGDPD_m01_s0804.pre"),
                                guion_path=gp)
    nodos = [e["decision"] for e in json.load(open(gp))["entries"]
             if e.get("kind") == "node" and e["decision"].startswith("estacionalidad")]
print("nodos estacionalidad:", nodos)
sys.exit(0 if nodos == ["estacionalidad = D=0 (sin estacionalidad)"] else 1)
