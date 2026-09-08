"""BUG-0117 — el índice de defectos lleva tiempo en rojo y nadie se enteró.

Determinista y sin motor: corre la misma validación que `art-bug check`.

    python bugs/BUG-0117-repro/repro.py

Exit 1 = hay informes inválidos.
"""
import os
import sys

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

from art import bugs  # noqa: E402

carpeta = os.path.join(RAIZ, "bugs")
todos, errores = [], []
for f in sorted(os.listdir(carpeta)):
    if not (f.startswith("BUG-") and f.endswith(".md")):
        continue
    try:
        b = bugs.load_bug(os.path.join(carpeta, f))
    except Exception as exc:
        errores.append(f"{f}: no se puede leer ({type(exc).__name__})")
        continue
    todos.append(b)
    for e in b.problems():
        errores.append(f"{b.id}: {e}")

print(f"informes revisados: {len(todos)}")
if errores:
    print(f"INVÁLIDOS: {len(errores)} error(es)\n")
    for e in errores:
        print("  " + e)
    print("\nDos clases distintas, y conviene no confundirlas:")
    print("  · PROSA en un campo de vocabulario cerrado — el matiz existe y no")
    print("    cabe en el enum, así que se escribió al lado y rompió el campo;")
    print("  · `fixed_in` VACÍO con `status: fixed` — un informe que dice estar")
    print("    arreglado sin decir dónde no se puede releer.")
    sys.exit(1)
print("todos válidos")
