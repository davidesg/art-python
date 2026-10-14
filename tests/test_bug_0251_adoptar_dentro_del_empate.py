"""BUG-0251 — adoptar dentro del empate no «coincide con la propuesta».

El nodo `ordenes` con empate guarda como propuesta el primero de la lista.
Adoptar OTRO de los empatados cerraba el nodo con «coincide con la propuesta»
y `coincide: true` junto a una propuesta distinta de lo decidido. Ahora es
`coincide: "empate"` y el texto lo dice, con la propuesta.

Minneapolis (flour_prices.csv, ejemplo lutkepohl_poskitt de sima): propuesta
ARMA(0,1), empate con el AR(1); el analista adopta el AR(1).
"""
import json
import os
import warnings

import pytest

from art import mcp_server as M

CSV = os.path.join(os.path.dirname(__file__), os.pardir,
                   "bugs", "BUG-0251-repro", "flour_prices.csv")


def _fn(t):
    return getattr(t, "fn", t)


def _txt(o):
    return "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                     for c in (o if isinstance(o, list) else [o]))


def _nodo_ordenes(gp):
    return [e for e in json.load(open(gp))["entries"]
            if e.get("nodo") == "ordenes" and e.get("propuesta")][-1]


@pytest.fixture(scope="module")
def minneapolis(tmp_path_factory):
    warnings.simplefilter("ignore")
    tmp = str(tmp_path_factory.mktemp("bug0251"))
    inp, gp = os.path.join(tmp, "Minneapolis.inp"), os.path.join(tmp, "guion.json")
    _fn(M.load_data)(CSV, inp, column="Minneapolis")
    gi = _fn(M.guided_identification)
    gi(inp, domain="price_index", expectativas="price", guion_path=gp)
    gi(inp, lam=0.0, domain="price_index", guion_path=gp)
    gi(inp, lam=0.0, d=1, domain="price_index", guion_path=gp)
    gi(inp, lam=0.0, d=1, D=0, domain="price_index", guion_path=gp)
    nodo = _nodo_ordenes(gp)
    _fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m01.inp"), lam=0.0, d=1,
                                D=0, p=1, q=0, n_harmonics=0, seasonal=False,
                                estimate_mu=False, guion_path=gp, guion_name="m01")
    g = json.load(open(gp))
    v = max(e["version"] for e in g["entries"] if e.get("name") == "m01")
    out = _txt(_fn(M.guion_adopt)(gp, v, why="AR(1) por dominio"))
    return dict(gp=gp, antes=nodo, out=out, nodo=_nodo_ordenes(gp))


def test_precondicion_empate_con_otra_propuesta(minneapolis):
    nd = minneapolis["antes"]["node"]
    assert nd.get("empate"), "el nodo declara empate"
    assert [1, 0, 0, 0] in [list(c) for c in nd["empate"]]
    assert minneapolis["antes"]["propuesta"] != "ARMA(1,0)"


def test_el_registro_no_dice_coincide(minneapolis):
    e = minneapolis["nodo"]
    assert e["node"]["decidido"] == "ARMA(1,0)"
    assert e["coincide"] == "empate"


def test_el_texto_dice_dentro_del_empate(minneapolis):
    out = minneapolis["out"]
    assert "coincide con la propuesta" not in out
    assert "dentro del empate" in out
    assert minneapolis["antes"]["propuesta"] in out


def test_el_mapa_lo_marca(minneapolis):
    mapa = _txt(_fn(M.guion_map)(minneapolis["gp"]))
    assert "dentro del empate" in mapa
