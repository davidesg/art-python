"""Nada de lo que se publica nombra una carpeta personal.

La rueda y el sdist llevan src/ —con el registro de bugs/*.md copiado en
src/art/material/bugs, que las herramientas del MCP sirven—, tests/ y los
documentos de MANIFEST.in. Hasta 0.2.6 iban en ellos rutas de la máquina del
autor, algunas de carpetas privadas. Una prueba que necesita un fichero local
lee su ruta de una variable de entorno (ART_PASSTHROUGH_CSV…) y se salta sin
ella (docs/PUBLISHING.md: ninguna ruta personal en el sdist)."""
import fnmatch
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHIPS = ("src", "tests", "bugs", "README.md", "CHANGELOG.md", "TODO.md",
         "docs/QUICKSTART.md", "docs/TOOLS.md", "docs/SUITE_DOCUMENTATION_PLAN.md",
         "docs/ARCHITECTURE.md", "docs/RESCALING_ARCHITECTURE.md")
#: una ruta con nombre de usuario: /home/<nombre>/, /Users/<nombre>/,
#: C:\Users\<nombre> (sin el nombre, «/home/» a secas es texto, no una ruta)
_RUTA = re.compile(r"/(?:home|Users)/[\w.-]+/|C:\\Users\\[\w.-]+")
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
            if _RUTA.search(line):
                hits.append(f"{os.path.relpath(f, ROOT)}:{n}: {line.strip()[:100]}")
    assert not hits, "rutas personales en lo que se publica:\n" + "\n".join(hits)


def test_nada_del_repositorio_nombra_una_carpeta_personal():
    """El repositorio es público: tampoco lo que no se publica (los repros de
    bugs/, los casos, CASE_STUDIES.md). Los datos privados llegan por variables
    (ART_REPLICA, ART_REPLICA_DS, ART_PASSTHROUGH_CSV, ART_CASE_STUDIES)."""
    import subprocess
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                             text=True, check=True).stdout.split("\n")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("no es un checkout de git")
    hits = []
    for rel in filter(None, out):
        if rel == ".gitignore" or not any(fnmatch.fnmatch(os.path.basename(rel), g)
                                          for g in TEXT + ("*.html", "*.inp", "*.pre", "*.sh")):
            continue
        try:
            text = open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if _RUTA.search(line):
                hits.append(f"{rel}:{n}: {line.strip()[:100]}")
    assert not hits, "rutas personales en el repositorio:\n" + "\n".join(hits[:40])
