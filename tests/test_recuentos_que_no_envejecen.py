"""ORDEN 0.4 — los recuentos que mentían, y la prueba que impide que vuelvan.

`docs/TOOLS.md` decía **35 tools** y `AGENTS.md` **32**. Son **46**. Nadie
mintió: se escribieron a mano en su día y las herramientas siguieron creciendo.
Es la enfermedad del proyecto en su forma más simple —una propiedad que vive en
tres sitios— y la única cura es que dos de los tres se generen o se comprueben.

`docs/TOOLS.md` **ya se genera** (`tools/gen_tools_md.py`), y por una razón que
su propia cabecera explica mejor que ésta:

    en un servidor MCP el docstring es lo que lee el MODELO, así que la
    documentación tiene dos audiencias —el analista y Claude— y el modo de
    fallo es la DIVERGENCIA. Una regla que vive en TOOLS.md y no en el
    docstring es una regla que el modelo no aplica nunca.

Lo que faltaba era que alguien comprobase que se ha regenerado.
"""
import importlib.util
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

RAIZ = Path(__file__).resolve().parent.parent
TOOLS_MD = RAIZ / "docs" / "TOOLS.md"
AGENTS_MD = RAIZ / "AGENTS.md"


def _gen():
    ruta = RAIZ / "tools" / "gen_tools_md.py"
    spec = importlib.util.spec_from_file_location("_gen_tools_md", ruta)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_gen_tools_md"] = mod
    spec.loader.exec_module(mod)
    return mod


def _n_tools():
    import asyncio
    import art.mcp_server as M
    return len(asyncio.run(M.mcp.list_tools()))


def test_TOOLS_md_esta_regenerado():
    """Si falla: `python3 tools/gen_tools_md.py art.mcp_server art docs/TOOLS.md`."""
    esperado = _gen().render("art.mcp_server", "art")
    actual = TOOLS_MD.read_text(encoding="utf-8")
    assert actual == esperado, (
        "docs/TOOLS.md no está al día con los docstrings registrados. "
        "Regenéralo: python3 tools/gen_tools_md.py art.mcp_server art docs/TOOLS.md")


def test_el_recuento_de_TOOLS_md_es_el_real():
    n = _n_tools()
    m = re.search(r"\*\*(\d+) tools\.\*\*", TOOLS_MD.read_text(encoding="utf-8"))
    assert m, "docs/TOOLS.md no declara su recuento"
    assert int(m.group(1)) == n, f"TOOLS.md dice {m.group(1)}, son {n}"


def test_el_recuento_de_AGENTS_md_es_el_real():
    """El tercer sitio. Éste no se genera —es prosa— así que se comprueba."""
    n = _n_tools()
    txt = AGENTS_MD.read_text(encoding="utf-8")
    citados = {int(x) for x in re.findall(r"the (\d+) MCP tools", txt)}
    assert citados, "AGENTS.md no cita el número de herramientas"
    assert citados == {n}, f"AGENTS.md dice {sorted(citados)}, son {n}"
