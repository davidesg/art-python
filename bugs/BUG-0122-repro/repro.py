#!/usr/bin/env python3
"""BUG-0122 — quince de las veintiocho herramientas que devuelven figura no la
ESCRIBÍAN: viajaba sólo como imagen en la respuesta MCP. Sin fichero, sin
ventana y sin ruta que citar, con la herramienta reportando éxito.

Determinista y sintético: no toca red, ni `fue`, ni datos. Fabrica una
`Description` con una figura de un píxel y la pasa por las dos vías por las que
una figura sale del servidor.

Antes del arreglo:  _result -> no escribe (sólo BUSCA la huella)
                    ImageContent a mano -> tampoco
"""
import base64
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src"))
os.environ["ART_NO_VIEWER"] = "1"        # medimos el FICHERO, no la ventana

import art.mcp_server as srv  # noqa: E402

PNG = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000a49444154789c6360000002000100ffff03000006000557bfabd4000000"
    "0049454e44ae426082")).decode()


class Desc:
    summary = "resumen"
    recommendation = "recomendación"
    figure_b64 = PNG


def escrita(b64):
    return srv._huella_figura(b64) in srv._FIGURAS


fallos = 0

srv._FIGURAS.clear()
srv._result(Desc())
ok = escrita(PNG)
fallos += not ok
print(f"{'ok ' if ok else 'FALLA'}  _result escribe la figura que devuelve")

srv._FIGURAS.clear()
tiene = hasattr(srv, "_imagen")
if tiene:
    srv._imagen(PNG, "repro")
ok = tiene and escrita(PNG)
fallos += not ok
print(f"{'ok ' if ok else 'FALLA'}  _imagen escribe la figura que devuelve"
      f"{'' if tiene else '  (no existe: los 23 sitios la construían a mano)'}")

# La regla estructural: un ImageContent no puede nacer en ningún otro sitio.
import io  # noqa: E402
fuente = io.open(os.path.join(os.path.dirname(srv.__file__), "mcp_server.py"),
                 encoding="utf-8").read()
sitios = [l for l in fuente.splitlines()
          if "ImageContent(" in l and "from mcp.types" not in l]
fuera = [l for l in sitios if "return ImageContent(type=" not in l]
ok = not fuera
fallos += not ok
print(f"{'ok ' if ok else 'FALLA'}  el ImageContent nace en UN sitio "
      f"({len(fuera)} fuera de _imagen)")

print()
print("`_result` no salvaba nada: BUSCA la huella en _FIGURAS por si otro la")
print("escribió. Si nadie lo hizo, se calla y no cita ninguna ruta.")
sys.exit(1 if fallos else 0)
