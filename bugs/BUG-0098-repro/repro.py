"""BUG-0098 — un guion escrito por una versión anterior de art no se puede leer.

Determinista, sintético, sin motor. Reproduce las DOS caras del mismo fallo:

  A) el registro caduca con el instrumento — `GuionStats` fue ganando campos
     obligatorios (`loglik`, `bic`, `sigma_a`) y todo guion anterior a ellos
     dejó de abrirse con un TypeError;
  B) el camino guardado es relativo al cwd del día — el guion viaja, el cwd no.

    python bugs/BUG-0098-repro/repro.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from art.guion import load_guion  # noqa: E402

# Un guion tal como lo escribía una versión anterior: stats sin loglik/bic/
# sigma_a, e `inp_path` relativo. Ambas cosas están tomadas del corpus real.
VIEJO = {
    "series": "FOOD", "analyst": "", "created": "2025-01-01",
    "entries": [{
        "version": 1, "name": "PC1", "inp_path": "work/FOOD_m01.inp",
        "timestamp": "2025-01-01T00:00:00",
        "spec": {"lam": 0.0, "d": 1}, "equation": "",
        "decision": "", "rationale": "", "problems_found": "", "next_version": "",
        "stats": {"aic": 12.3, "jb_pass": True, "jb_pvalue": 0.4,
                  "n_extreme": 0, "q_pass": True},
    }],
}

with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "work"))
    real = os.path.join(d, "work", "FOOD_m01.inp")
    open(real, "w").write("# la evidencia, donde siempre estuvo\n")
    gp = os.path.join(d, "FOOD_guion.json")
    json.dump(VIEJO, open(gp, "w"))

    # (A) ¿se puede leer?
    try:
        g = load_guion(gp)
        print(f"A) OK  el guion abre: {len(g.entries)} entrada(s), "
              f"loglik={g.entries[0].stats.loglik} (NO CONSTA, que es lo cierto)")
    except TypeError as ex:
        print(f"A) FALLO  el registro es ilegible: {ex}")
        sys.exit(1)

    # (B) ¿apunta a la evidencia? Se lee desde OTRO cwd, que es el caso real.
    os.chdir(tempfile.gettempdir())
    p = g.entries[0].inp_path
    if os.path.exists(p):
        print(f"B) OK  la evidencia se encuentra desde otro cwd: {p}")
    else:
        print(f"B) FALLO  camino muerto: {p!r} (relativo a un cwd que ya no es)")
        sys.exit(1)
