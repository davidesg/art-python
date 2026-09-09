#!/usr/bin/env python3
"""BUG-0121 — bajo servidor MCP la ventana de la figura se apagó en TODAS las
plataformas, y el defecto medido era del anfitrión de Windows.

Determinista y sintético: no toca red, ni fue, ni datos. Fabrica un PNG de 1x1
en memoria, sustituye `_abrir_visor` por un contador, y pregunta a la decisión
—no al efecto— qué haría en cada plataforma.

Antes del arreglo:  posix bajo servidor -> NO abre   (la regresión)
Después:            posix bajo servidor -> abre
                    nt    bajo servidor -> NO abre   (el 0111, conservado)
"""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src"))

import art.mcp_server as srv  # noqa: E402


def decide(so, bajo_servidor, entorno):
    """Lo que el servidor hará con la ventana, sin abrir ninguna."""
    fn = getattr(srv, "_visor_procede", None)
    if fn is None:                       # antes del arreglo no existe
        return not (bajo_servidor or entorno.get("ART_NO_VIEWER"))
    return fn(bajo_servidor, so, entorno, bajo_pytest=False)


CASOS = [
    #  so      bajo servidor  entorno              esperado
    ("posix",  True,          {},                  True),   # ← la regresión
    ("posix",  False,         {},                  True),
    ("nt",     True,          {},                  False),  # ← el 0111
    ("nt",     False,         {},                  True),
    ("nt",     True,          {"ART_VIEWER": "1"}, True),
    ("posix",  True,          {"ART_NO_VIEWER": "1"}, False),
    ("nt",     True,          {"ART_VIEWER": "1", "ART_NO_VIEWER": "1"}, False),
]

fallos = 0
for so, srv_, entorno, esperado in CASOS:
    obtenido = decide(so, srv_, entorno)
    ok = obtenido == esperado
    fallos += not ok
    print(f"{'ok ' if ok else 'FALLA'}  so={so:5s}  servidor={srv_!s:5s} "
          f"entorno={entorno or '{}'!s:38s} abre={obtenido!s:5s} "
          f"(esperado {esperado})")

print()
print("La guarda del 0111 apagaba la ventana bajo servidor SIN mirar la"
      " plataforma.")
print("En un cliente que no pinta el ImageContent esa ventana era el único"
      " canal del analista.")
sys.exit(1 if fallos else 0)
