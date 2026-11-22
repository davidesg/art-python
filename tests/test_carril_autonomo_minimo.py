"""BUG-0262 y BUG-0263: lo mínimo para que un agente recorra el carril
autónomo sin las figuras de la identificación a cuestas y con el protocolo a
la vista."""
import asyncio
import inspect
import os
import shutil

import pytest

import art.mcp_server as m
from mcp.types import ImageContent

AQUI = os.path.dirname(os.path.abspath(__file__))
WTI = os.path.join(AQUI, "..", "bugs", "BUG-0262-repro", "WTI.inp")


def _imagenes(res):
    return [c for c in res if isinstance(c, ImageContent)]


def test_guided_identification_tiene_carril():
    p = inspect.signature(m.guided_identification).parameters
    assert p["modo"].default == "guiado" and p["con_figuras"].default is False


def test_en_autonomo_las_figuras_de_la_identificacion_no_viajan(tmp_path, monkeypatch):
    monkeypatch.setenv("ART_FIG_DIR", str(tmp_path / "tmp"))
    (tmp_path / "tmp").mkdir()
    inp = shutil.copy(WTI, tmp_path / "WTI.inp")
    kw = dict(domain="multiplicative", expectativas="I(1) en logaritmos, memoria corta")
    guiado = m.guided_identification(str(inp), **kw)
    assert _imagenes(guiado)                                # el guiado las enseña
    auto = m.guided_identification(str(inp), modo="autonomo", **kw)
    assert not _imagenes(auto)
    hermanas = [f for f in os.listdir(tmp_path) if f.startswith("WTI__") and f.endswith(".png")]
    assert hermanas                                         # junto al modelo
    texto = "".join(getattr(c, "text", "") for c in auto)
    assert "no se devuelve como imagen" in texto and hermanas[0] in texto
    pedidas = m.guided_identification(str(inp), modo="autonomo", con_figuras=True, **kw)
    assert _imagenes(pedidas)


def test_el_protocolo_autonomo_se_puede_pedir():
    nombres = {t.name for t in asyncio.run(m.mcp.list_tools())}
    assert "protocolo_autonomo" in nombres
    s = m.protocolo_autonomo()
    assert s.startswith("EL CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA")
    assert "LOS NODOS" in s and 'modo="autonomo"' in s and "NUNCA DECIDAS NODOS EN LOTE" in s
    assert s in m._INSTRUCTIONS                             # una sola fuente


def test_el_principio_de_las_instrucciones_dice_como_pedirlo():
    """Lo que un cliente que trunca sí entrega: los primeros miles de
    caracteres. Ahí tiene que estar el nombre de la herramienta."""
    assert "protocolo_autonomo()" in m._INSTRUCTIONS[:4000]


def test_la_seccion_no_arrastra_la_siguiente():
    s = m.protocolo_autonomo()
    rayas = [x for x in s.split("\n") if x.startswith("═" * 10)]
    assert len(rayas) == 1                                  # solo la raya de su título
