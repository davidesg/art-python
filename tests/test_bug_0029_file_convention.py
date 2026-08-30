"""BUG-0029 — el `.out` y `get_out_report` eran inalcanzables.

El `.out` guarda los parámetros CON SUS ERRORES TÍPICOS, sigma, la verosimilitud
y las matrices de covarianza y correlación. `get_out_report` existe para leerlo.
Nada en el servidor mencionaba ninguno de los dos, todas las sugerencias
encadenaban por `.pre`, y la cabecera presentaba `.inp` y `.pre` como entradas
intercambiables añadiendo que «cada llamada es idempotente» — que es una
invitación a reestimar sobre el óptimo, o sea a BUG-0027.

El convenio SÍ estaba escrito, pero en drtran, que es un escalón POSTERIOR. Los
tres ficheros nacen en art.
"""
import os
import re
import tempfile

import numpy as np
import pytest

from art import mcp_server as A

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "src", "art", "mcp_server.py")
FUENTE = open(SRC, encoding="utf-8").read()


# ── el convenio está escrito, y en art ─────────────────────────────────────

def test_las_instrucciones_traen_el_convenio():
    assert "EL CONVENIO DE FICHEROS" in A._INSTRUCTIONS


@pytest.mark.parametrize("regla", [
    "NUNCA DE REEJECUTAR",          # de dónde salen los errores típicos
    "NUNCA ESCRIBAS UN .pre",       # sólo el programa que estimó afirma un óptimo
    "VUELVE A SER UN .inp",         # tocar un .pre lo devuelve a especificación
])
def test_las_tres_reglas_estan_enunciadas(regla):
    assert regla in A._INSTRUCTIONS


def test_el_convenio_nombra_la_herramienta_que_lee_el_out():
    assert "get_out_report" in A._INSTRUCTIONS


def test_el_convenio_remite_al_defecto_medido():
    """Una regla sin su medición es una opinión."""
    assert "BUG-0027" in A._INSTRUCTIONS


def test_la_secuencia_marca_el_paso_que_se_salta():
    assert "REFORMULAS LEYENDO EL .out" in A._INSTRUCTIONS


def test_la_cabecera_ya_no_dice_que_sean_intercambiables():
    cabecera = FUENTE.split('"""')[1]
    assert "no son formatos intercambiables" in cabecera
    assert "cada llamada es idempotente" not in cabecera


# ── y está cableado: la salida dirige al .out ──────────────────────────────

@pytest.fixture(scope="module")
def salida():
    d = tempfile.mkdtemp(prefix="conv-")
    rng = np.random.default_rng(7)
    y = 100.0 + np.cumsum(rng.normal(0, 1.0, 80))
    inp = os.path.join(d, "S.inp")
    A.create_inp(list(map(float, y)), inp, name="S", freq=4,
                 start_year=2004, start_period=1)
    out = A.confirm_and_estimate(
        inp_path=inp, output_path=os.path.join(d, "S_m00.inp"),
        lam=1.0, d=1, D=0, p=1, q=0, n_harmonics=0, seasonal=False,
        estimate_mu=False, guion_name="m00")
    return d, "\n".join(c.text for c in out if hasattr(c, "text"))


def test_la_salida_nombra_el_out_y_como_leerlo(salida):
    _, txt = salida
    assert ".out" in txt
    assert "get_out_report(" in txt


def test_la_salida_dice_para_que_sirve_cada_fichero(salida):
    """«resultados: x.out» no bastaba: nadie lo abría."""
    _, txt = salida
    assert "Parámetros, errores típicos y covarianza" in txt
    assert "semilla del siguiente paso" in txt
    assert "no reestimando el `.pre`" in txt


def test_el_out_existe_y_trae_los_errores_tipicos(salida):
    """Lo que se estaba recalculando a mano estaba aquí desde el principio."""
    d, _ = salida
    out = open(os.path.join(d, "S_m00.out"), encoding="utf-8", errors="replace").read()
    assert "Estimated covariance matrix" in out
    # parámetro con su error típico entre paréntesis
    assert re.search(r"-?\d+\.\d+\s+\(\s*\d+\.\d+\)", out)


def test_get_out_report_lo_devuelve(salida):
    d, _ = salida
    res = A.get_out_report(os.path.join(d, "S_m00.inp"))
    txt = "\n".join(c.text for c in res if hasattr(c, "text"))
    assert "Estimated covariance matrix" in txt
