"""BUG-0080 — `domain` no es alcanzable desde el carril guiado.

La política declara que el dominio es una SUGERENCIA y que «lo declarado gana
siempre». Pero la salida de escape sólo existe en `build_model`. Un analista que
recorre los nodos uno a uno no puede declarar nada.

Precedente literal en la MISMA función: el docstring de `objetivo` en
`guided_identification` dice que estaba «reachable only from build_model, so an
analyst walking the nodes one at a time could not state the purpose at all».
Se arregló para `objetivo` y no para `domain`.

Determinista, sin datos: sólo firmas.
"""
import inspect, sys
sys.path.insert(0, "src")
from art import mcp_server, policy

def sig(nombre):
    fn = getattr(mcp_server, nombre)
    fn = getattr(fn, "fn", fn)
    return list(inspect.signature(fn).parameters), inspect.getdoc(fn) or ""

print("DOMINIOS reconocidos por la politica:", policy.DOMINIOS)
print()
fallos = []
for nombre in ("build_model", "guided_identification", "confirm_and_estimate"):
    params, _ = sig(nombre)
    tiene = "domain" in params
    print(f"  {nombre:24} domain= : {'SI' if tiene else 'NO'}")
    if nombre != "build_model" and not tiene:
        fallos.append(nombre)

_, doc = sig("guided_identification")
print()
print("  ...y en el docstring de guided_identification, sobre `objetivo`:")
for L in doc.split("\n"):
    if "reachable only from" in L or "could not state the purpose" in L:
        print("   ", L.strip())

print()
print("La politica afirma que lo declarado gana:")
for L in (inspect.getdoc(policy.decide_domain) or "").split("\n"):
    if "declarado gana" in L or "SUGERENCIA" in L:
        print("   ", L.strip())

print()
if fallos:
    print("INALCANZABLE desde:", ", ".join(fallos))
    sys.exit(1)
