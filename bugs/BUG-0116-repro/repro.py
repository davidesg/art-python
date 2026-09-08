"""BUG-0116 — la descripción de la herramienta no sobrevive al cliente.

Determinista, sin motor: mide el tamaño de lo que `art` publica y dónde cae
cada cosa importante dentro de ese texto.

    python bugs/BUG-0116-repro/repro.py

`art` publica el docstring ENTERO — eso está bien y está comprobado aquí. Lo
que falla es el reparto: la información que decide el modelo está detrás de
miles de caracteres de prosa, y cualquier cliente que recorte —el de la sesión
del 8 de septiembre entregó el 23%— la deja fuera.
"""
import asyncio
import os
import sys

RAIZ = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(RAIZ, "src"))
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv  # noqa: E402

#: Lo que un cliente real entregó, medido: 2.033 de 8.968 caracteres.
ENTREGADO = 2033

#: Ninguna descripción debería necesitar más que esto para lo que DECIDE.
PRESUPUESTO = 2000

herramientas = asyncio.run(srv.mcp.list_tools())
por_nombre = {t.name: t for t in herramientas}

fallos = 0

# (1) art publica el docstring entero — no es aquí donde se pierde.
d = por_nombre["confirm_and_estimate"].description or ""
print(f"confirm_and_estimate publica {len(d)} caracteres")
if len(d) < 5000:
    print("  ? el docstring ha cambiado; rehacer la medición")

# (2) pero lo que DECIDE está detrás del recorte.
CLAVES = [
    ("easter", "easter          :"),
    ("ar_f_freqs", "ar_f_freqs      :"),
    ("Shin-Fuller", "Shin-Fuller"),
    ("seasonal", "seasonal        :"),
]
print(f"\ncon un cliente que entregue {ENTREGADO} caracteres ({ENTREGADO/len(d)*100:.0f}%):")
perdidas = []
for etiqueta, aguja in CLAVES:
    i = d.find(aguja)
    if i < 0:
        continue
    estado = "llega" if i < ENTREGADO else "SE PIERDE"
    print(f"  {etiqueta:14} al {i/len(d)*100:5.1f}%   {estado}")
    if i >= ENTREGADO:
        perdidas.append(etiqueta)
if perdidas:
    print(f"\nFALLO  se pierden: {', '.join(perdidas)}")
    fallos += 1

# (3) cuántas descripciones exceden el presupuesto
largas = sorted(((len(t.description or ""), t.name) for t in herramientas),
                reverse=True)
excesivas = [(n, l) for l, n in largas if l > PRESUPUESTO]
print(f"\ndescripciones por encima de {PRESUPUESTO} caracteres: "
      f"{len(excesivas)} de {len(herramientas)}")
for n, l in excesivas[:6]:
    print(f"   {l:6}  {n}")
if excesivas:
    fallos += 1

sys.exit(1 if fallos else 0)
