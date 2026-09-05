"""BUG-0081 — `_show_fig` se pisa el fichero entre llamadas del MISMO proceso,
y `_result` publica la ruta de una GLOBAL, no la de su propia figura.

BUG-0078 añadió un discriminante para que «dos herramientas con la misma
etiqueta ya no se sobrescriban la figura». El discriminante es `os.getpid()`, y
el servidor MCP es UN SOLO proceso: dentro de una sesión no discrimina nada, que
es justo donde ocurría la colisión.

Determinista, sin ventanas (ART_NO_VIEWER). Ejerce el código real: comprueba las
rutas Y lo que `_result` acaba publicando.
"""
import base64
import io
import os
import sys

os.environ["ART_NO_VIEWER"] = "1"
sys.path.insert(0, "src")
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from art import mcp_server
from art.describe import Description

FALLOS = []


def fig_b64(color):
    f = plt.figure(figsize=(1, 1)); plt.plot([0, 1], [0, 1], color=color)
    buf = io.BytesIO(); f.savefig(buf, format="png"); plt.close(f)
    return base64.b64encode(buf.getvalue()).decode()


A, B = fig_b64("red"), fig_b64("blue")

# ── A. dos series distintas por el MISMO nodo guiado -> misma etiqueta ──
print("== A. Dos series por el mismo nodo")
p1 = mcp_server._show_fig(A, "boxcox")     # serie 1
p2 = mcp_server._show_fig(B, "boxcox")     # serie 2
print("  figura de la serie 1 ->", p1)
print("  figura de la serie 2 ->", p2)
print("  MISMA RUTA:", p1 == p2)
if p1 == p2:
    print("  COLISION: el contenido de la serie 1 queda sobrescrito por el de la 2.")
    FALLOS.append("colision de rutas")
else:
    with open(p1, "rb") as f1, open(p2, "rb") as f2:
        if f1.read() == f2.read():
            print("  ...pero el CONTENIDO es el mismo")
            FALLOS.append("mismo contenido en dos rutas")
        else:
            print("  cada serie conserva su fichero: OK")

# ── B. la misma figura DOS veces sigue dando el mismo fichero ──
print("\n== B. La ventana se reemplaza, no se multiplica")
if mcp_server._show_fig(A, "boxcox") == p1:
    print("  la misma figura vuelve al mismo fichero: OK")
else:
    print("  FALLA: una figura idéntica abre un fichero nuevo")
    FALLOS.append("la ruta no es estable para la misma figura")

# ── C. lo que _result acaba publicando ──
print("\n== C. La nota de _result cita SU figura, no la última global")
mcp_server._show_fig(A, "identificacion")          # mueve _ULTIMA_FIGURA
print("  _ULTIMA_FIGURA tras una tercera llamada:", mcp_server._ULTIMA_FIGURA)
texto = "\n".join(
    getattr(c, "text", "")
    for c in mcp_server._result(Description(summary="s", figure_b64=B,
                                            recommendation="r")))
if p2 in texto:
    print("  _result cita", p2, "-> la suya: OK")
elif mcp_server._ULTIMA_FIGURA in texto:
    print("  FALLA: _result cita la global", mcp_server._ULTIMA_FIGURA)
    FALLOS.append("_result publica _ULTIMA_FIGURA")
else:
    print("  FALLA: _result no cita ninguna ruta")
    FALLOS.append("_result no cita ruta")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: cada figura tiene su fichero y cada respuesta cita el suyo.")
