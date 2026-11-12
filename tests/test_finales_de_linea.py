"""El repositorio guarda LF, y hay una razón concreta.

Editar un fichero desde Windows por el Dropbox compartido lo devuelve en CRLF.
`mcp_server.py` volvió una vez así: **17.621 líneas cambiadas sobre un fichero
de 7.500**, de las cuales 86 eran el cambio real. Un diff de ese tamaño no se
revisa — se comitea a ciegas, que es exactamente lo que no debe pasar con un
fichero que lleva el protocolo entero.
"""
import os
import subprocess
import sys

import pytest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# En una copia sacada con git en Windows el CRLF es lo que toca: `text=auto`
# deja que cada copia de trabajo use el final de su plataforma (.gitattributes),
# y git lo vuelve a LF al comitear. Lo que esta prueba caza es el CRLF que
# trae el Dropbox a una copia de Linux o macOS, donde git no lo pondría.
@pytest.mark.skipif(sys.platform == "win32",
                    reason="en Windows, text=auto saca la copia de trabajo en CRLF")
def test_ningun_fuente_lleva_CRLF():
    malos = []
    for sub in ("src", "tests", "bugs", "docs"):
        for raiz, _, ficheros in os.walk(os.path.join(RAIZ, sub)):
            if "__pycache__" in raiz:
                continue
            for f in ficheros:
                if not f.endswith((".py", ".md", ".toml", ".yml", ".yaml")):
                    continue
                ruta = os.path.join(raiz, f)
                with open(ruta, "rb") as fh:
                    if b"\r\n" in fh.read():
                        malos.append(os.path.relpath(ruta, RAIZ))
    assert not malos, (
        f"ficheros con CRLF: {malos[:5]}"
        + (f" (+{len(malos)-5} más)" if len(malos) > 5 else "")
        + ". Un fichero en CRLF hace ilegible su propio diff.")


def test_hay_gitattributes_que_lo_impide():
    """La prueba de arriba caza el síntoma; esto evita la causa. Sin
    `.gitattributes`, cada copia de trabajo decide por su cuenta."""
    p = os.path.join(RAIZ, ".gitattributes")
    assert os.path.exists(p), "sin .gitattributes, el CRLF vuelve"
    contenido = open(p, encoding="utf-8").read()
    assert "text=auto" in contenido
    for ext in (".inp", ".pre", ".out"):
        assert ext in contenido, f"{ext} —del contrato— sin declarar"
