#!/usr/bin/env python3
"""Copia a `src/art/material/` lo que los recursos MCP sirven en ejecución.

BUG-0125. `recursos.py` sirve el registro de defectos y la documentación por
`art://defectos` y `art://docs`, y los buscaba contando directorios por encima
del módulo — la disposición del REPOSITORIO. En una instalación eso no existe, y
además el material no viajaba: `pyproject.toml` empaqueta sólo `src/`, y
`MANIFEST.in` tiene un `prune bugs` deliberado. La rueda 0.2.0 publicada lleva
27 ficheros y ninguno de `bugs/` ni de `docs/`.

Este guion resuelve el conflicto sin duplicar nada en git: `bugs/` y `docs/`
siguen siendo el único original, y `src/art/material/` es una copia GENERADA
—ignorada por git— que el empaquetado sí distribuye.

Se ejecuta antes de construir. La prueba `test_recursos_instalados.py` falla si
la copia no está o está desincronizada, así que la suite lo detecta antes que el
CI y el CI antes que PyPI.
"""
from __future__ import annotations

import filecmp
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESTINO = os.path.join(RAIZ, "src", "art", "material")

#: Qué se distribuye. Los informes de defecto ENTEROS —son el material del
#: recurso— y de `docs/` sólo lo que `recursos.py` tiene sentido que sirva.
#: Las notas internas (ANNOUNCEMENT, PUBLISHING, STATUS) no salen, como manda
#: el criterio ya escrito en `MANIFEST.in`.
DOCS_FUERA = {"ANNOUNCEMENT.md", "PUBLISHING.md", "STATUS.md"}


def _copia(origen: str, destino: str, filtro) -> tuple[int, int]:
    os.makedirs(destino, exist_ok=True)
    nombres = sorted(f for f in os.listdir(origen) if filtro(f))
    copiados = 0
    for f in nombres:
        o, d = os.path.join(origen, f), os.path.join(destino, f)
        if not (os.path.exists(d) and filecmp.cmp(o, d, shallow=False)):
            shutil.copy2(o, d)
            copiados += 1
    for f in os.listdir(destino):          # lo que ya no está en el original
        if f not in nombres:
            os.remove(os.path.join(destino, f))
    return len(nombres), copiados


def sincroniza() -> dict[str, tuple[int, int]]:
    res = {}
    res["bugs"] = _copia(os.path.join(RAIZ, "bugs"),
                         os.path.join(DESTINO, "bugs"),
                         lambda f: f.endswith(".md"))
    res["docs"] = _copia(os.path.join(RAIZ, "docs"),
                         os.path.join(DESTINO, "docs"),
                         lambda f: f.endswith(".md") and f not in DOCS_FUERA)
    return res


def desincronizado() -> list[str]:
    """Qué falta o sobra en la copia. Vacío = al día. No escribe nada."""
    fallos = []
    for sub, origen, filtro in (
            ("bugs", os.path.join(RAIZ, "bugs"), lambda f: f.endswith(".md")),
            ("docs", os.path.join(RAIZ, "docs"),
             lambda f: f.endswith(".md") and f not in DOCS_FUERA)):
        dst = os.path.join(DESTINO, sub)
        try:
            esperados = {f for f in os.listdir(origen) if filtro(f)}
        except OSError:
            continue                       # sin árbol de trabajo: nada que decir
        try:
            hay = {f for f in os.listdir(dst) if f.endswith(".md")}
        except OSError:
            fallos.append(f"falta {sub}/ entero")
            continue
        for f in sorted(esperados - hay):
            fallos.append(f"falta {sub}/{f}")
        for f in sorted(hay - esperados):
            fallos.append(f"sobra {sub}/{f}")
        for f in sorted(esperados & hay):
            if not filecmp.cmp(os.path.join(origen, f),
                               os.path.join(dst, f), shallow=False):
                fallos.append(f"difiere {sub}/{f}")
    return fallos


if __name__ == "__main__":
    r = sincroniza()
    for k, (total, copiados) in r.items():
        print(f"{k}: {total} ficheros ({copiados} actualizados)")
    print(f"-> {DESTINO}")
    sys.exit(0)
