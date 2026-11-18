"""BUG-0113 — el carril guiado descartaba la ruta que devuelve _show_fig.

`_show_fig` escribía la figura y devolvía su ruta; cinco puntos del carril
guiado la descartaban, así que el analista se quedaba sin figura y sin ruta
cuando el visor no se abría.

Cómo quedó: tras BUG-0122 y BUG-0147 hay un solo embudo. Toda figura pasa por
`_imagen`, que la escribe SIEMPRE (con `_show_fig`, cuyo retorno ahí sobra), y
`_cita_figuras` hace que el texto de la respuesta diga dónde quedó cada una, por
su contenido. La ruta ya no la tiene que recoger cada herramienta: no se puede
olvidar, que era el defecto.

Antes este repro contaba llamadas a `_show_fig` dentro de guided_identification
—hoy no hay ninguna— y salía 1 con el bug cerrado. Ahora comprueba la
propiedad: una figura que sale de una herramienta va CITADA en el texto, con
una ruta que existe. Exit 1 = bug presente; exit 0 = corregido.
"""
import base64
import io
import os
import re
import sys

os.environ.setdefault("ART_NO_VIEWER", "1")
os.environ.setdefault("MPLBACKEND", "Agg")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

import matplotlib.pyplot as plt                         # noqa: E402
from mcp.types import TextContent                       # noqa: E402

from art import mcp_server as M                         # noqa: E402

fig = plt.figure()
plt.plot([1, 3, 2])
buf = io.BytesIO()
fig.savefig(buf, format="png")
b64 = base64.b64encode(buf.getvalue()).decode()

items = M._cita_figuras([TextContent(type="text", text="informe"),
                         M._imagen(b64, "repro0113")])
texto = "\n".join(i.text for i in items if getattr(i, "type", "") == "text")
rutas = re.findall(r"`([^`]+\.png)`", texto)
print("texto de la respuesta:", texto.replace("\n", " | "))
ok = bool(rutas) and all(os.path.exists(r) for r in rutas)
print("=" * 70)
if not ok:
    print("FALLA (bug presente): la figura no va citada en el texto, o su ruta no existe")
    sys.exit(1)
print("OK: la figura va citada en el texto, con una ruta que existe.")
