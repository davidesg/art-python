"""BUG-0107 — export_guion_html revienta si el guion contiene un NODO de decision.

La tabla resumen de export_guion_html recorre TODAS las entradas y hace
`e.stats.aic` sin comprobar el tipo de entrada. Una entrada de tipo "node"
--las que escribe guion_node-- no tiene stats (es None), asi que el export
muere con AttributeError.

La ironia esta en el propio docstring de guion_node: existe porque "un guion
que registra solo MODELOS empieza la historia tarde". El exportador no puede
renderizar exactamente los guiones que la suite anima a construir. guion_map,
en cambio, dibuja los nodos sin problema: el exportador es el unico que no
sabe de su existencia.
"""
import json
import sys
import tempfile
import os

sys.path.insert(0, "src")

from art.guion import load_guion, export_guion_html

FALLOS = []

guion = {
    "series": "REPRO",
    "analyst": "",
    "created": "2026-09-06",
    "entries": [
        {"version": 1, "name": "m00", "kind": "model", "inp_path": "", "timestamp": "2026-09-06T00:00:00",
         "spec": {"lam": 0.0, "d": 1, "D": 0, "p": 0, "q": 0, "P": 0, "Q": 0,
                  "n_harmonics": 0, "interventions": [], "estimate_mu": False,
                  "mu": 0.0, "alter": False, "ifadf": [0] * 7,
                  "ar_free": [], "ma_free": [], "ar_s_free": [], "ma_s_free": []},
         "stats": {"loglik": 1.0, "aic": -1.0, "bic": 1.0, "sigma_a": 0.1,
                   "q_pass": True, "jb_pass": True, "n_extreme": 0, "extreme": [],
                   "q_lags": [], "q_pvalues": [], "jb_pvalue": 0.5, "npar": 1,
                   "refactor": 100.0},
         "equation": "y = a", "decision": "modelo", "rationale": "", "problems_found": "",
         "next_version": "", "parent": None, "status": "exploring"},
        # La entrada que rompe: un NODO de decision, sin stats.
        {"version": 2, "name": "", "kind": "node", "inp_path": "", "timestamp": "2026-09-06T00:00:01",
         "nodo": "ordenes", "decidido": "p=1", "razon": "porque si",
         "evidencia": "", "decidido_por": "analista+LLM",
         "spec": None, "stats": None,
         "equation": "", "decision": "ordenes = p=1", "rationale": "porque si",
         "problems_found": "", "next_version": "", "parent": 1, "status": "exploring"},
    ],
}

fd, path = tempfile.mkstemp(suffix=".json")
with os.fdopen(fd, "w", encoding="utf-8") as fh:
    json.dump(guion, fh)

g = load_guion(path)
print("== guion cargado: %d entradas (1 model + 1 node)" % len(g.entries))
print("   stats del nodo: %r" % (g.entries[1].stats,))
try:
    export_guion_html(g)
    print("   export_guion_html: OK")
except AttributeError as e:
    print("   export_guion_html: AttributeError -> %s" % e)
    FALLOS.append("export_guion_html revienta con un nodo de decision en el guion")
finally:
    os.unlink(path)

print("\n== RESULTADO")
for f in FALLOS:
    print("   FALLO: %s" % f)
print("   %d fallo(s)" % len(FALLOS))
sys.exit(1 if FALLOS else 0)
