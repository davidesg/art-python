"""BUG-0040 — la taxonomía de dominio era binaria y una magnitud multiplicativa
no tenía dónde caer.

`decide_domain` devolvía `"price_index"` o `"generic"`, y `decide_lambda` sólo
tenía regla para el primero. Un PRECIO —magnitud multiplicativa con cero
natural, donde el log es práctica estándar— caía en `"generic"` y su λ la
decidía el SIGNO de `gap`, que sobre series cortas es ruido.

Es el arreglo de BUG-0015 quedándose corto: añadió el dominio a la política con
las dos únicas categorías que aquel caso necesitaba. El texto que art imprime
dice «índice de precios **o magnitud multiplicativa**»; el código no tenía la
segunda.

Testigo real: PGAS (precio de exportación del gas boliviano, 95→500 USD/t), gap
= −0.023. Dos carriles independientes cometieron el mismo error —la heurística
por lotes y un analista LLM sin contexto previo— y el segundo lo escribió con
todas las letras: «es un precio con cero natural, NO un índice, así que la
transformación la decide el estadístico». No fue un descuido: es la taxonomía
leída correctamente. Con λ=1 ninguno de sus seis modelos alcanzó la adecuación,
con el JB entre 46.7 y 8.9.
"""
import numpy as np
import pytest

import fue
from art.policy import (BANDA_AMBIGUA_BOXCOX, DOMINIOS, RANGO_MULTIPLICATIVO,
                        decide_domain, decide_lambda)


def _serie(valores, nombre="X"):
    return fue.TimeSeries(list(map(float, valores)), freq=4,
                          start=(2004, 1), name=nombre)


# ── la clasificación ────────────────────────────────────────────────────────

def test_a_wide_range_positive_series_is_multiplicative():
    """Sobre un recorrido de factor R, un modelo de varianza aditiva afirma la
    misma innovación absoluta en los dos extremos. Con R≥3 eso es implausible."""
    rng = np.random.default_rng(1)
    y = np.linspace(100, 500, 84) + 10 * rng.standard_normal(84)
    assert decide_domain(_serie(y, "PRECIO")) == "multiplicative"


def test_a_narrow_range_series_stays_generic():
    """El umbral es una convención y hay que respetarla en las dos direcciones:
    por debajo, el dominio no se pronuncia y decide el estadístico."""
    rng = np.random.default_rng(2)
    y = 100 + 5 * rng.standard_normal(84)     # factor de recorrido ≈ 1.5
    assert decide_domain(_serie(y, "ALGO")) == "generic"


def test_a_bounded_share_is_a_ratio():
    rng = np.random.default_rng(3)
    y = 0.16 + 0.03 * rng.standard_normal(84)
    assert decide_domain(_serie(np.clip(y, 0.05, 0.95), "GPPIB")) == "ratio"


def test_non_positive_values_fall_back_to_generic():
    """El log no está definido: no hay nada que discutir."""
    rng = np.random.default_rng(4)
    y = rng.standard_normal(84) * 50          # cruza el cero
    assert decide_domain(_serie(y, "SALDO")) == "generic"


def test_the_index_rule_still_goes_by_name():
    """Un índice no tiene firma en el DATO que lo distinga: lo que lo define es
    que su nivel es una convención, y eso no se ve en la serie."""
    rng = np.random.default_rng(5)
    y = 100 + np.cumsum(rng.standard_normal(84))
    assert decide_domain(_serie(y, "IPC_ES")) == "price_index"
    assert decide_domain(_serie(y, "ITCER")) == "price_index"


def test_every_inferred_domain_is_a_declared_category():
    rng = np.random.default_rng(6)
    for nombre, y in (("IPC", 100 + np.cumsum(rng.standard_normal(84))),
                      ("PRECIO", np.linspace(100, 500, 84)),
                      ("RATIO", np.full(84, 0.16) + 0.02 * rng.standard_normal(84)),
                      ("SALDO", rng.standard_normal(84))):
        assert decide_domain(_serie(y, nombre)) in DOMINIOS


# ── la regla ────────────────────────────────────────────────────────────────

def test_inside_the_band_the_domain_decides():
    """El testigo: gap = −0.023, el valor medido sobre PGAS."""
    assert decide_lambda({"gap": -0.023}, "multiplicative") == 0.0
    assert decide_lambda({"gap": -0.023}, "ratio") == 0.0
    # y esto es lo que hacía la taxonomía binaria con ese mismo número
    assert decide_lambda({"gap": -0.023}, "generic") == 1.0


def test_outside_the_band_the_data_decides():
    """El dominio NO es un decreto: un gap grande y negativo lo desmiente."""
    g = -(BANDA_AMBIGUA_BOXCOX + 0.2)
    assert decide_lambda({"gap": g}, "multiplicative") == 1.0
    assert decide_lambda({"gap": g}, "ratio") == 1.0


def test_the_index_rule_is_absolute():
    """Un índice sí es decreto, y por una razón distinta: su nivel es una
    convención, así que un modelo en niveles no tiene escala interpretable."""
    for g in (-0.9, -0.3, 0.0, +0.5):
        assert decide_lambda({"gap": g}, "price_index") == 0.0


def test_generic_is_unchanged():
    """La categoría que ya existía se comporta igual que antes."""
    assert decide_lambda({"gap": +0.001}, "generic") == 0.0
    assert decide_lambda({"gap": -0.001}, "generic") == 1.0


def test_the_band_matches_what_art_prints():
    """El interruptor es la misma banda que la herramienta anuncia al analista
    («Δcorr=0.024 < 0.10 → decisión ambigua»). Si se separan, el texto y la
    decisión dejan de ser la misma cosa."""
    assert BANDA_AMBIGUA_BOXCOX == 0.10
    assert RANGO_MULTIPLICATIVO == 3.0
