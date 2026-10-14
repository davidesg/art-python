"""BUG-0233 — el paso 4 declaraba un empate que no era el de la ficha.

La lista va por parsimonia dentro de bandas de 0,04 de similitud
(`_nested_parsimony`), así que el 2.º puede salir de la banda SIGUIENTE. El aviso
y la recomendación tomaban «los dos primeros»: en Salamanca, «Decisión ambigua
entre ARIMA(1,1,1) y ARIMA(3,1,0)», mientras la ficha del empate genuino
comparaba (1,1,1), (1,1,2) y (2,1,1). Ahora la ambigüedad es la banda del
primer puesto, la misma de la ficha, y la lista dice por qué criterio va.
"""
import os
import re
import warnings

import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.describe import describe_identification

INP = os.path.join(os.path.dirname(__file__), "..", "bugs", "BUG-0232-repro",
                   "Salamanca.inp")
pytestmark = pytest.mark.skipif(not os.path.exists(INP),
                                reason="falta el .inp de Salamanca (BUG-0232-repro)")


@pytest.fixture(scope="module")
def ident():
    ts, _ = fue.load(INP)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return describe_identification(ts, d=1, D=0, lam=0.0, estacional=False)


def _pq(t):
    return set(re.findall(r"ARIMA\((\d+),\d+,(\d+)\)", t))


def test_la_recomendacion_nombra_los_de_la_ficha(ident):
    ficha = next(l for l in ident.summary.splitlines() if l.startswith("| | ("))
    en_ficha = set(re.findall(r"\| \((\d+),\d+,(\d+)\)", ficha))
    assert en_ficha == {("1", "1"), ("1", "2"), ("2", "1")}, "precondición"
    assert _pq(ident.recommendation) == en_ficha
    assert ("3", "0") not in _pq(ident.recommendation)


def test_el_aviso_nombra_la_banda_no_los_dos_primeros(ident):
    aviso = next(l for l in ident.summary.splitlines() if "Decisión ambigua" in l)
    assert "dos primeros" not in aviso
    assert _pq(aviso) == {("1", "1"), ("1", "2"), ("2", "1")}


def test_la_lista_dice_por_que_criterio_va(ident):
    assert "Orden de la lista: por parsimonia dentro de bandas" in ident.summary
