"""BUG-0167 — el contraste d−1 se PIDE, no se ofrece.

Decisión del analista, 11-sep-2026:

    «Es un contraste que se debe pedir, pero no ofrecer, por razones conocidas
    en inferencia. Está bien tenerlo, pero sirve para casos específicos que el
    analista debe pedir, o que la serie parece estacionaria en nivel —como un
    precio relativo o en estudios de cointegración—.»

La razón es de INFERENCIA. Una batería de contrastes que nadie pidió, corrida
sobre cada modelo y presentada con su ✓, es pre-testing: el veredicto no tiene
el tamaño que aparenta.

El par confirmatorio en f=0 lo forman **Shin-Fuller sobre el AR** y el **DCD con
testigo de sobrediferenciación** —complementarios como ADF y KPSS en la
especificación inicial—, y ése se corre siempre. El lado d−1 contesta otra
pregunta, que sólo se hace cuando hay motivo.

El caso que lo motivó (BUG-0045, PGAS) era una petición legítima: se estaba
evaluando si la serie era d=0 desde el principio. Legítima **porque se preguntó**.

Y hay una segunda razón para no dispararlo solo, medida en BUG-0167: con un AR
de orden 1 el brazo nulo gasta su única raíz en la unitaria y el LR mide dinámica
perdida. Sobre `ES_CPI_m10`, de los 39,9 puntos de LR, 38,3 son eso.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.describe import describe_formal_tests
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

_ROTULO = "sub-diferenciación"


@pytest.fixture(scope="module")
def modelo(tmp_path_factory):
    """Una serie I(1) con AR(1) — el caso donde el contraste NO discrimina."""
    rng = np.random.default_rng(4)
    n = 216
    e = rng.standard_normal(n) * 0.4
    for t in range(1, n):
        e[t] += 0.40 * e[t - 1]
    ts = fue.TimeSeries((100.0 + np.cumsum(e)).tolist(), freq=12,
                        start=(2002, 1), name="I1")
    f = str(tmp_path_factory.mktemp("d1") / "I1.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]]), f)
    return estimar(f)[1]


def test_por_defecto_NO_se_corre(modelo):
    t = describe_formal_tests(modelo, run_meg=False).summary
    assert _ROTULO not in t, "el lado d−1 se sigue ofreciendo sin pedirlo"


def test_pedido_SI_se_corre(modelo):
    t = describe_formal_tests(modelo, run_meg=False,
                              subdiferenciacion=True).summary
    assert _ROTULO in t


def test_el_par_confirmatorio_NO_depende_de_el(modelo):
    """Shin-Fuller y el DCD de sobrediferenciación son el par, y se corren
    siempre: quitar el tercero no puede dejar cojo al par."""
    t = describe_formal_tests(modelo, run_meg=False).summary
    assert "Shin-Fuller" in t
    assert "sobre-diferenciación" in t


def test_no_se_ESTIMA_nada_cuando_no_se_pide(modelo):
    """No es sólo que no se imprima: son DOS ajustes que no se hacen."""
    import art.describe as D
    llamadas = []
    orig = D.dcd_underdiff_regular
    D.dcd_underdiff_regular = lambda m, **k: (llamadas.append(1), orig(m, **k))[1]
    try:
        describe_formal_tests(modelo, run_meg=False)
        assert llamadas == [], "se estimó el lado d−1 sin pedirlo"
        describe_formal_tests(modelo, run_meg=False, subdiferenciacion=True)
        assert llamadas == [1], "pedido, no se estimó"
    finally:
        D.dcd_underdiff_regular = orig


def test_la_superficie_MCP_lo_expone_y_dice_CUANDO_pedirlo():
    """Un instrumento que se pide tiene que decir en qué casos, o no se pide
    nunca — o se pide siempre, que es lo mismo que ofrecerlo."""
    import asyncio

    import art.mcp_server as srv
    ts = asyncio.run(srv.mcp.list_tools())
    t = next(x for x in ts if x.name == "formal_tests")
    props = (t.inputSchema or {}).get("properties", {})
    assert "subdiferenciacion" in props
    assert props["subdiferenciacion"].get("default") is False

    # `_texto.plano` une los saltos de línea: si no, esto deja de ser una
    # prueba de CONTENIDO y pasa a serlo de MAQUETACIÓN — «es un precio\n
    # relativo» la rompía.
    from tests._texto import dice
    d = t.description or ""
    assert dice(d, "se pide, no se ofrece")
    for motivo in ("estacionaria en nivel", "precio relativo", "cointegración"):
        assert dice(d, motivo), f"no dice el caso «{motivo}»"
