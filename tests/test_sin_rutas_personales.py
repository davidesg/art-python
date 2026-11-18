"""Nada de lo que se publica nombra una carpeta personal.

La rueda y el sdist llevan src/ —con el registro de bugs/*.md copiado en
src/art/material/bugs, que las herramientas del MCP sirven—, tests/ y los
documentos de MANIFEST.in. Hasta 0.2.6 iban en ellos rutas de la máquina del
autor, algunas de carpetas privadas. Una prueba que necesita un fichero local
lee su ruta de una variable de entorno (ART_PASSTHROUGH_CSV…) y se salta sin
ella (docs/PUBLISHING.md: ninguna ruta personal en el sdist)."""
import fnmatch
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIPS = ("src", "tests", "bugs", "README.md", "CHANGELOG.md", "TODO.md",
         "docs/QUICKSTART.md", "docs/TOOLS.md", "docs/SUITE_DOCUMENTATION_PLAN.md",
         "docs/ARCHITECTURE.md", "docs/RESCALING_ARCHITECTURE.md")
#: partidos, para que este fichero no se encuentre a sí mismo
PATTERNS = ("/" + "home/", "/" + "Users/", "C:" + "\\\\Users")
TEXT = ("*.py", "*.md", "*.c", "*.h", "*.txt", "*.json", "*.toml", "*.cfg")


def _files():
    for top in SHIPS:
        p = os.path.join(ROOT, top)
        if os.path.isfile(p):
            yield p
            continue
        for d, dirs, fs in os.walk(p):
            # material/ es la copia de bugs/ (tools/sync_material.py): se mira
            # bugs/; y de bugs/ sólo viajan los partes, no los repros
            dirs[:] = [x for x in dirs if x != "material" and not
                       (top == "bugs" and x.endswith("-repro"))]
            for f in fs:
                if top == "bugs" and not f.endswith(".md"):
                    continue
                if any(fnmatch.fnmatch(f, g) for g in TEXT):
                    yield os.path.join(d, f)


def test_nada_de_lo_que_se_publica_nombra_una_carpeta_personal():
    if not os.path.isdir(os.path.join(ROOT, "src", "art")):
        pytest.skip("no es un árbol de fuentes (la suite corre contra un art instalado)")
    hits = []
    for f in _files():
        try:
            text = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if any(pat in line for pat in PATTERNS):
                hits.append(f"{os.path.relpath(f, ROOT)}:{n}: {line.strip()[:100]}")
    assert not hits, "rutas personales en lo que se publica:\n" + "\n".join(hits)
