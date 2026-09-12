"""BUG-0178 y BUG-0179 — el carril autónomo tiene que ser autónomo.

Salieron del run 4 automático de IPC_ES, lanzado con `domain` declarado.

0179: `domain` es un DATO —qué clase de serie es—, no una decisión de
      especificación. Pero entraba en el mismo diccionario que λ, d, D, p, q…
      y `guided = bool(overrides)` lo contaba: declararlo volvía «guiada» la
      llamada, la salida tomaba forma de turno guiado y terminaba en ⏸. El
      asistente paraba y preguntaba: el autónomo dejaba de iterar solo.

0178: un `domain` que la política NO reconoce se aceptaba en silencio. Cae a
      `decide_domain`, decide el estadístico, y sobre un índice de precios eso
      da λ=1 donde la regla dice λ=0 — con la cabecera anunciando el dominio
      como si se hubiera aplicado. La guarda existía en `guided_identification`
      y en `confirm_and_estimate`; faltaba justo en `build_model`, que es la
      puerta del carril autónomo.
"""
import os
import re
import shutil
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art import policy
from art.mcp_server import dominio_declarado
from art.pipeline import _write_bare_inp
from tests._texto import dice


def _fn(nombre):
    import art.mcp_server as M
    f = getattr(M, nombre)
    return getattr(f, "fn", f)


def _texto(o):
    return o[0].text if isinstance(o, list) and o else str(o)


@pytest.fixture(scope="module")
def indice(tmp_path_factory):
    """Un índice de precios sintético: nivel ~100, creciente, estacional."""
    d = tmp_path_factory.mktemp("dom")
    r = np.random.default_rng(11)
    n = 216
    t = np.arange(n)
    y = 100.0 * np.exp(0.0025 * t
                       + 0.01 * np.sin(2 * np.pi * t / 12)
                       + 0.004 * np.cumsum(r.standard_normal(n)))
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2002, 1), name="IPC_TEST")
    p = str(d / "IPC_TEST.inp")
    warnings.simplefilter("ignore")
    _write_bare_inp(ts, p)
    return d, p


def _corre(indice, nombre, **kw):
    d, base = indice
    warnings.simplefilter("ignore")
    return _texto(_fn("build_model")(inp_path=base,
                                     output_path=str(d / f"{nombre}.inp"),
                                     max_rounds=3, **kw))


# ── BUG-0179 — el carril ──────────────────────────────────────────────────

def test_sin_nada_declarado_el_carril_es_autonomo(indice):
    out = _corre(indice, "m_sin")
    assert dice(out.splitlines()[0], "· autónomo")
    assert "⏸" not in out, "un autónomo que para no es autónomo"


def test_declarar_el_DOMINIO_no_saca_del_carril_autonomo(indice):
    """EL DEFECTO. El dominio es un dato, no una decisión."""
    out = _corre(indice, "m_dom", domain="price_index")
    assert dice(out.splitlines()[0], "· autónomo"), (
        "declarar un DATO volvía guiada la llamada")
    assert "⏸" not in out, (
        "terminaba en la marca de fin de turno guiado y el asistente paraba")


def test_declarar_una_DECISION_si_saca_del_carril(indice):
    """Y lo contrario tiene que seguir valiendo: si el analista decide, es guiado."""
    out = _corre(indice, "m_dec", d=1)
    assert dice(out.splitlines()[0], "guiado (spec confirmada)")
    assert "⏸" in out


def test_el_dominio_declarado_sigue_llegando_a_la_politica(indice):
    """No basta con no cambiar de carril: el dato tiene que APLICARSE."""
    out = _corre(indice, "m_apl", domain="price_index")
    assert re.search(r"\*\*λ:\*\* log \(λ=0\)", out), (
        "un índice va en log SIEMPRE; si el dominio no llega, decide el estadístico")


# ── BUG-0178 — el dominio que nadie reconoce ─────────────────────────────

def test_un_dominio_no_reconocido_se_rechaza(indice):
    out = _corre(indice, "m_malo", domain="índice de precios")
    assert "no es un dominio reconocido" in out
    for v in policy.DOMINIOS:
        assert v in out, "el rechazo tiene que decir cuáles valen"


def test_el_guardian_esta_en_UN_solo_sitio():
    """Tres puertas aceptan `domain`; la regla no puede estar copiada en cada
    una — es la lección de BUG-0015, y es por donde se coló ésta."""
    import art.mcp_server as M
    src = open(M.__file__, encoding="utf-8").read()
    assert src.count("no es un dominio reconocido") == 1, (
        "hay más de una copia de la regla del dominio")


def test_las_tres_puertas_rechazan_lo_mismo():
    import inspect

    import art.mcp_server as M
    from tests._fuente import cuerpo_de

    for nombre in ("build_model", "guided_identification", "confirm_and_estimate"):
        f = _fn(nombre)
        assert "domain" in inspect.signature(f).parameters
        # `inspect.getsource` congela `co_firstlineno` en el import: editar
        # mientras la suite corre le hace devolver el trozo equivocado. Se
        # localiza por NOMBRE (BUG-0141).
        assert "dominio_declarado" in cuerpo_de(M, nombre), (
            f"{nombre} no pasa por el guardián")


@pytest.mark.parametrize("valor", list(policy.DOMINIOS))
def test_los_dominios_de_la_politica_pasan(valor):
    assert dominio_declarado(valor) == valor


def test_vacio_significa_no_declarado():
    assert dominio_declarado("") == ""
    assert dominio_declarado("   ") == ""
    assert dominio_declarado(None) == ""


def test_el_mensaje_nombra_el_valor_rechazado():
    with pytest.raises(ValueError, match="índice de precios"):
        dominio_declarado("índice de precios")
