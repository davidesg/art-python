"""`formal_tests` es la etapa de CIERRE y no presentaba el modelo.

El analista da aquí su vistazo final, y tiene que dárselo al MODELO, no sólo a
los contrastes. La forma en que este sistema presenta un modelo es la ecuación
con sus parámetros y sus errores típicos debajo — y esa capacidad existía
(`model_equation_display`) sin que nada la conectara donde hace falta. Es el
patrón que describe docs/ARCHITECTURE_REVIEW.md: no faltan herramientas, sobran
sin cablear.

Orden: primero QUÉ modelo, luego si es adecuado, luego qué dicen los contrastes
sobre su especificación.
"""
import os

import pytest

from art import mcp_server as A

CASO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "cases", "GASTO_PIB_BO", "GASTO_PIB_BO_m31.inp")


@pytest.fixture(scope="module")
def salida():
    if not os.path.exists(CASO):
        pytest.skip("el caso GASTO_PIB_BO no está presente")
    out = A.formal_tests(CASO, run_meg=False)
    return "\n".join(c.text for c in out if hasattr(c, "text"))


def test_presenta_la_ecuacion_del_modelo(salida):
    assert "MODELO ESTIMADO" in salida
    assert "σ̂ₐ" in salida and "AIC" in salida


def test_la_ecuacion_trae_los_errores_tipicos(salida):
    """Un parámetro sin su error típico no es un resultado."""
    import re
    assert re.search(r"\(\d+\.\d+\)", salida)


def test_presenta_el_veredicto_de_la_diagnosis(salida):
    assert "**Diagnosis:**" in salida
    assert "ruido blanco (Q)" in salida and "normalidad (JB)" in salida


def test_presenta_los_contrastes(salida):
    assert "Contrastes formales" in salida


def test_el_orden_es_modelo_diagnosis_contrastes(salida):
    i_mod = salida.index("MODELO ESTIMADO")
    i_dia = salida.index("**Diagnosis:**")
    i_con = salida.index("Contrastes formales")
    assert i_mod < i_dia < i_con
