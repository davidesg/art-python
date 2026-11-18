"""BUG-0094 — la salida del carril guiado no está estandarizada.

La presentación de cada herramienta MCP quedaba delegada al LLM con
instrucciones en prosa, y la misma estimación producía salidas distintas según
el agente.

Cómo se cerró (ver «Reapertura y cierre de verdad», 06-09-2026): un sobre,
`envuelve_iteracion`, que en el carril GUIADO compone siempre las mismas cuatro
secciones en el mismo orden —MODELO ESTIMADO · DIAGNOSIS · CONCLUSIONES ·
DECISIÓN— y termina en la marca de fin de turno; y `confirm_and_estimate`, la
herramienta del guiado, se lo pide declarando el modo. Las marcas «[Claude: …]»
del protocolo se quedan a sabiendas (el informe lo dice: salida idéntica
carácter a carácter con cualquier LLM NO se hizo).

Antes este repro buscaba las secciones que el informe PROPONÍA y no las que se
construyeron, así que salía 1 con el bug cerrado. Ahora comprueba el sobre.
Determinista, sin datos ni motor. Exit 1 = bug presente; exit 0 = corregido.
"""
import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

FALLOS = []
try:
    from art import mcp_server as M
    E = M.envuelve_iteracion
except (ImportError, AttributeError):
    print("no hay sobre de iteración (envuelve_iteracion)")
    sys.exit(1)

t = E(nombre="m01", modo="guiado", ecuacion="y = a", diagnosis="Q ok",
      conclusiones="se sostiene", alternativas=["A) nada"])
secciones = ["1 · MODELO ESTIMADO", "2 · DIAGNOSIS", "3 · CONCLUSIONES", "4 · DECISIÓN"]
pos = [t.find(s) for s in secciones]
print("== El sobre del guiado")
for s, p in zip(secciones, pos):
    print(f"  {s:24s} : {'sí' if p >= 0 else 'NO'}")
if any(p < 0 for p in pos) or pos != sorted(pos):
    FALLOS.append("las cuatro secciones no salen, o no en su orden")
if "⏸" not in t:
    FALLOS.append("falta la marca de fin de turno")

cae = getattr(M.confirm_and_estimate, "fn", M.confirm_and_estimate)
fuente = inspect.getsource(cae)
pide_modo = "envuelve_iteracion(" in fuente and "modo=" in fuente
print(f"  confirm_and_estimate declara el modo al pedir el sobre : {pide_modo}")
if not pide_modo:
    FALLOS.append("confirm_and_estimate no declara el modo: el guiado recibe la forma del registro")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA (bug presente):", "; ".join(FALLOS))
    sys.exit(1)
print("OK: el carril guiado sale siempre con las cuatro secciones y para en la pregunta.")
