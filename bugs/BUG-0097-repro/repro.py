"""BUG-0097 — un determinista sin rama de render DESPLAZA toda la ecuación.

Determinista, sin motor ni datos: comprueba la estructura del renderizador.

El defecto no era «falta el easter». Era que `_seq` —la secuencia de parámetros
en orden de render— acepta TODOS los tipos deterministas y el render sólo tenía
ramas para unos pocos, así que el cursor no consumía el ω del tipo sin rama y
**todo lo que venía después salía corrido, con el error típico del anterior**.

    python bugs/BUG-0097-repro/repro.py
"""
import os
import re
import sys

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))

fallos = []


def cuerpo(ruta, nombre):
    src = open(os.path.join(RAIZ, ruta), encoding="utf-8").read()
    i = src.index(f"def {nombre}(")
    j = src.find("\ndef ", i + 1)
    return src[i:j if j > 0 else len(src)]


# (1) los dos recorridos de la MISMA secuencia tienen que cerrar la clase
for fn in ("model_equation", "describe_seasonal_params"):
    cuerpo_fn = cuerpo("src/art/describe.py", fn)
    if "\n        else:\n" not in cuerpo_fn:
        fallos.append(f"{fn}: sin `else` final — un tipo nuevo vuelve a desplazar")
    else:
        print(f"OK  {fn} consume cualquier tipo determinista")

# (2) el easter tiene su propia rama, con su símbolo y sin fecha
eq = cuerpo("src/art/describe.py", "model_equation")
if '"easter"' not in eq or "Easter" not in eq:
    fallos.append("model_equation: el easter no tiene rama de render")
else:
    print("OK  el easter se renderiza como ξₜ^{Easter}")

# (3) la red de seguridad: si el cursor no agota la secuencia, se DICE
if "pi.i != len(_seq)" not in eq:
    fallos.append("model_equation: no comprueba que el cursor cuadre")
else:
    print("OK  un desajuste futuro sale como aviso, no como modelo falso")

# (4) el guion no puede inventar una fecha para un regresor de calendario
g = open(os.path.join(RAIZ, "src/art/guion.py"), encoding="utf-8").read()
if "SIN_FECHA" not in g:
    fallos.append("guion: el easter sigue registrándose con una fecha inventada")
else:
    print("OK  el guion no le pone fecha a un regresor de calendario")

# (5) y el analista puede pedirlo sin editar el .inp a mano
m = open(os.path.join(RAIZ, "src/art/mcp_server.py"), encoding="utf-8").read()
if "easter: bool" not in m:
    fallos.append("mcp_server: el easter no está expuesto en el flujo guiado")
else:
    print("OK  `confirm_and_estimate(..., easter=True)` lo añade")

if fallos:
    print("\nFALLOS:")
    for f in fallos:
        print("  ·", f)
    sys.exit(1)
print("\nTodo cerrado.")
