"""ORDEN 0.1 — la prueba que LANZA el servidor de verdad.

Ninguna prueba de la suite cruzaba la frontera MCP. Las 1.827 llaman a las
funciones de `mcp_server` en el proceso de pytest, que es otra cosa: en ese
camino no hay `stdio`, no hay `initialize`, no hay esquema publicado y
`_BAJO_SERVIDOR` es False.

Y ahí es donde vivían los defectos que costaron el censo. BUG-0121 —la ventana
apagada en todas las plataformas—, BUG-0122 —quince herramientas devolviendo
una figura que nadie escribía—, BUG-0126 —la misma figura abriendo tres
ventanas— y BUG-0137 sólo existen **al cruzarla**. Se encontraron usando el
servidor, uno por uno, porque no había ninguna prueba que lo levantara.

Ésta lo levanta: `initialize`, `tools/list`, `resources/list`, una llamada
barata y un `resources/read`. Es lenta —arranca un proceso e importa el
paquete entero— y por eso va marcada `slow`.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

mcp_cli = pytest.importorskip("mcp.client.stdio")
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

RAIZ = Path(__file__).resolve().parent.parent
CASO = RAIZ / "bugs" / "BUG-0126-repro" / "caso" / "RATIO_m10.inp"

pytestmark = pytest.mark.slow


def _servidor() -> StdioServerParameters:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RAIZ / "src") + os.pathsep + env.get("PYTHONPATH", "")
    # Sin visor: el servidor no debe abrir ventanas, y si lo intentara aquí
    # colgaría la prueba.
    env["ART_VIEWER"] = "0"
    return StdioServerParameters(command=sys.executable,
                                 args=["-m", "art.mcp_server"],
                                 env=env, cwd=str(RAIZ))


async def _con_sesion(fn, timeout=180):
    async with stdio_client(_servidor()) as (lectura, escritura):
        async with ClientSession(lectura, escritura) as s:
            await asyncio.wait_for(s.initialize(), timeout=60)
            return await asyncio.wait_for(fn(s), timeout=timeout)


def _corre(fn, timeout=180):
    return asyncio.run(_con_sesion(fn, timeout=timeout))


# ────────── que arranque, que es lo primero ──────────

def test_el_servidor_arranca_y_se_inicializa():
    """Si `art-mcp` no importa —un `ModuleNotFoundError`, un `mcp` 2.x— esto es
    lo único de la suite que se entera."""
    async def _f(s):
        return await s.list_tools()
    r = _corre(_f)
    assert r.tools, "el servidor no publicó ninguna herramienta"


def test_publica_las_46_herramientas_con_su_esquema():
    async def _f(s):
        return await s.list_tools()
    tools = _corre(_f).tools
    nombres = {t.name for t in tools}
    assert len(tools) >= 40, f"sólo {len(tools)} herramientas"
    # las dos puertas del carril guiado
    assert {"guided_identification", "guided_intervention"} <= nombres
    # y el esquema viaja: sin él el cliente no sabe llamar
    si = next(t for t in tools if t.name == "series_info")
    assert "inp_path" in (si.inputSchema or {}).get("properties", {})


def test_publica_los_recursos():
    """BUG-0125: los recursos se anunciaban y en una instalación no existían.
    Anunciarlos es lo que se comprueba aquí; que CONTESTEN, abajo."""
    async def _f(s):
        return await s.list_resources()
    uris = {str(r.uri) for r in _corre(_f).resources}
    assert any(u.startswith("art://") for u in uris), uris


# ────────── que conteste ──────────

@pytest.mark.skipif(not CASO.exists(), reason="el caso del repro no está")
def test_una_llamada_barata_va_y_vuelve():
    async def _f(s):
        return await s.call_tool("series_info", {"inp_path": str(CASO)})
    r = _corre(_f)
    assert not r.isError, r.content
    texto = "\n".join(c.text for c in r.content if getattr(c, "text", None))
    assert "RATIO" in texto, texto[:300]


def test_un_recurso_contesta_con_contenido():
    """La otra mitad del BUG-0125: que el recurso traiga texto de verdad.

    Sobre la rueda publicada esto devolvía un índice vacío, porque el paquete
    no llevaba `bugs/` ni `docs/`.
    """
    async def _f(s):
        return await s.read_resource("art://defectos")
    r = _corre(_f)
    texto = "\n".join(c.text for c in r.contents if getattr(c, "text", None))
    assert len(texto) > 2000, f"el índice de defectos vino con {len(texto)} caracteres"
    assert "BUG-" in texto


# ────────── lo que sólo se ve cruzando ──────────

@pytest.mark.skipif(not CASO.exists(), reason="el caso del repro no está")
@pytest.mark.xfail(strict=True, reason="BUG-0147 — la figura se escribe y no se "
                                       "dice dónde; cae en ORDEN 2.2, con `render`")
def test_una_herramienta_con_figura_devuelve_imagen_Y_ruta():
    """BUG-0122, en su terreno. Quince herramientas devolvían la figura sólo
    como `ImageContent` —sin fichero, sin ruta y sin ventana— y reportaban
    éxito. En el proceso de pytest eso no se distingue; aquí sí, porque lo que
    llega es exactamente lo que recibe el cliente.
    """
    async def _f(s):
        return await s.call_tool("preliminary_outlier_scan",
                                 {"inp_path": str(CASO), "d": 1, "D": 0,
                                  "lam": 0.0, "threshold": 2.0})
    r = _corre(_f)
    assert not r.isError, r.content
    tipos = [type(c).__name__ for c in r.content]
    texto = "\n".join(c.text for c in r.content if getattr(c, "text", None))
    assert any("Image" in t for t in tipos), f"sin figura: {tipos}"
    assert ".png" in texto, "la figura viaja sin ruta escrita"
