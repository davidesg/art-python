"""BUG-0208 — el modo autónomo devolvía las figuras como imagen.

Decisión (b): en AUTÓNOMO la figura se dibuja y se GUARDA junto al modelo
(`<stem>__<huella>.png`), pero no viaja como `ImageContent`; el texto dice la
ruta. El guiado no cambia, y `con_figuras=True` las devuelve en autónomo.
"""
import asyncio
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp


@pytest.fixture(scope="module")
def serie(tmp_path_factory):
    d = tmp_path_factory.mktemp("b208")
    rng = np.random.default_rng(208)
    z = np.cumsum(rng.standard_normal(180) * 0.01 + 0.002)
    ts = fue.TimeSeries(np.exp(4 + z).tolist(), freq=12, start=(2005, 1),
                        name="W")
    f = str(d / "W.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, refactor=_RESCALE_FACTOR), f)
    return d, f


def _llama(serie, salida, **k):
    d, f = serie
    fn = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = fn(f, str(d / salida), lam=0, d=1, D=0, p=1, q=0, n_harmonics=0,
               seasonal=False, estimate_mu=True, domain="price_index", **k)
    imgs = [c for c in r if getattr(c, "type", "") == "image"]
    txt = "\n".join(c.text for c in r if getattr(c, "type", "") == "text")
    return imgs, txt


def test_autonomo_guarda_la_figura_y_no_la_devuelve(serie):
    d, _ = serie
    imgs, txt = _llama(serie, "aut.inp", modo="autonomo")
    assert imgs == []
    rutas = re.findall(r"`([^`]*aut__[0-9a-f]{12}\.png)`", txt)
    assert rutas, txt[-600:]
    for r in rutas:
        assert os.path.isabs(r)
        assert os.path.dirname(r) == str(d)          # junto a la terna
        assert os.path.getsize(r) > 1000
        with open(r, "rb") as fh:
            assert fh.read(8) == b"\x89PNG\r\n\x1a\n"
    # una sola línea, y sin la nota de la copia temporal
    assert len([l for l in txt.splitlines() if "Figura" in l]) == 1
    assert "con_figuras=True" in txt


def test_guiado_sigue_devolviendo_la_figura(serie):
    imgs, txt = _llama(serie, "gui.inp", modo="guiado")
    assert imgs
    assert "no se devuelve como imagen" not in txt


def test_autonomo_con_figuras_las_devuelve(serie):
    imgs, txt = _llama(serie, "con.inp", modo="autonomo", con_figuras=True)
    assert imgs
    assert "no se devuelve como imagen" not in txt


def test_todas_las_herramientas_con_modo_aceptan_con_figuras():
    tools = asyncio.run(srv.mcp.list_tools())
    con_modo = [t for t in tools if "modo" in t.inputSchema.get("properties", {})]
    assert len(con_modo) >= 5
    for t in con_modo:
        assert "con_figuras" in t.inputSchema["properties"], t.name


def test_el_ayudante_respeta_el_fin_de_turno(tmp_path):
    from mcp.types import ImageContent, TextContent
    import base64
    b64 = base64.b64encode(b"\x89PNG\r\n\x1a\nxx").decode()
    items = [TextContent(type="text", text="cuerpo"),
             ImageContent(type="image", data=b64, mimeType="image/png")]
    # guiado: intacto
    assert srv._figuras_del_carril(list(items), "guiado", False,
                                   str(tmp_path / "m.inp")) == items
    out = srv._figuras_del_carril(list(items), "autonomo", False,
                                  str(tmp_path / "m.inp"))
    assert len(out) == 1 and "m__" in out[0].text
    assert list(tmp_path.glob("m__*.png"))
