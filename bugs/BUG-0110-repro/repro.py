"""BUG-0110 — `decided_by` registra el CARRIL, no quién decidió cada nodo.

Determinista y sin motor: construye un guion guiado en el que el analista decide
un nodo y acepta la propuesta del asistente en otro, y comprueba si el registro
puede distinguirlos.

    python bugs/BUG-0110-repro/repro.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from art.guion import Guion, GuionEntry, load_guion, save_guion  # noqa: E402


def nodo(v, nombre, decidido, quien):
    return GuionEntry(
        version=v, name=nombre, inp_path="", timestamp="t", spec={}, stats=None,
        equation="", decision=f"{nombre} = {decidido}", rationale="",
        problems_found="", next_version="", kind="node",
        node={"nodo": nombre, "decidido": decidido}, decided_by=quien)


with tempfile.TemporaryDirectory() as d:
    g = Guion(series="S", analyst="", created="2026-01-01")
    # Una sesión GUIADA real: el analista no interviene en todos los nodos.
    g.entries += [
        nodo(1, "lambda", "λ=0 CONTRA la recomendación", "analista+LLM"),
        nodo(2, "d", "d=1, aceptada la propuesta", "analista+LLM"),
        nodo(3, "ordenes", "AR(6) completo, CONTRA la propuesta", "analista+LLM"),
    ]
    gp = os.path.join(d, "S_guion.json")
    save_guion(g, gp)
    gg = load_guion(gp)

    quienes = {e.decided_by for e in gg.entries}
    print(f"decisores distintos en el guion: {quienes}")

    # ¿Se puede saber en qué nodos el analista CONTRADIJO y en cuáles aceptó?
    # `parent_origen` NO cuenta: registra cómo se supo el padre (BUG-0108), que
    # es otra cosa.
    CANDIDATOS = ("propuesta", "propuesto", "sugerido", "acuerdo",
                  "contradice", "coincide", "quien_decide")
    campos = set()
    for e in gg.entries:
        campos |= {k for k in vars(e) if any(c in k for c in CANDIDATOS)}
    print(f"campos que registren la propuesta o el acuerdo: "
          f"{sorted(campos) or 'NINGUNO'}")

    if len(quienes) == 1 and not campos:
        print("\nFALLO: los tres nodos son indistinguibles. El registro dice que")
        print("el CARRIL fue guiado, no qué nodos decidió el analista contra la")
        print("propuesta — que es la información que hace falta para saber dónde")
        print("el ojo entrenado corrige al asistente.")
        sys.exit(1)
    print("\nOK: el registro distingue.")
