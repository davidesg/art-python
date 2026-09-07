"""BUG-0109 — suggest_intervention_form registra el guion ANTES de persistir.

Determinista, sin datos ni motor: lee `src/art/mcp_server.py` y compara el orden
real de las llamadas. La comprobación de la terna (BUG-0092) mira si el `.pre` y
el `.out` existen EN EL MOMENTO de registrar; si se registra antes de
escribirlos, la entrada del guion los da por ausentes aunque acaben en disco un
instante después.

    python bugs/BUG-0109-repro/repro.py

(Reconstruido: el repro original se perdió en una colisión de identificadores
—dos informes numerados 0102 el mismo día— que se resolvió renumerando éste.)
"""
import os
import re
import sys

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
FUENTE = os.path.join(RAIZ, "src", "art", "mcp_server.py")


def cuerpo(nombre):
    """El cuerpo de una función, por nombre, con los números de línea reales."""
    lineas = open(FUENTE, encoding="utf-8").read().splitlines()
    ini = next(i for i, l in enumerate(lineas)
               if re.match(rf"^(async )?def {nombre}\(", l))
    fin = next((i for i in range(ini + 1, len(lineas))
                if re.match(r"^(async )?def |^@mcp\.tool", lineas[i])), len(lineas))
    return [(i + 1, l) for i, l in enumerate(lineas[ini:fin], start=ini)]


def primera(cuerpo_fn, aguja):
    for n, l in cuerpo_fn:
        if aguja in l:
            return n
    return None


fallos = 0
for nombre, debe_persistir_antes in (("suggest_intervention_form", True),
                                     ("confirm_and_estimate", True)):
    c = cuerpo(nombre)
    reg = primera(c, "_record_to_guion(")
    pre = primera(c, ".write_pre(") or primera(c, "_persist_pre_out")
    out = primera(c, ".write_out(")
    print(f"== {nombre}")
    print(f"   _record_to_guion  línea {reg}")
    print(f"   write_pre         línea {pre}")
    print(f"   write_out         línea {out}")
    if reg is None or pre is None:
        print("   ? no se encuentran las dos llamadas")
        continue
    if reg < pre:
        print("   ✗ REGISTRA ANTES DE PERSISTIR — el guion negará la terna")
        fallos += 1
    else:
        print("   ✓ persiste primero, registra después")

sys.exit(1 if fallos else 0)
