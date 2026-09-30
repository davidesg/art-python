"""BUG-0046 — el OBJETIVO del modelo tiene que llegar al LOTE.

`run_full` adjudica la ruta estacional con `objetivo`, y en "multivariante"
veta la ruta B2 (D=1) para que todas las series compartan tratamiento. Pero
`batch_build` --la entrada que se usa justamente para preparar las series de un
sistema-- no aceptaba el parámetro y llamaba a `run_full` siempre con el
defecto.

Se contrasta el COMPORTAMIENTO (qué D sale), no la redacción, salvo en el caso
de las instrucciones del servidor, donde el texto ES la entrega.
"""
import inspect
import warnings

import numpy as np
import pytest

import fue
from art.pipeline import run_full


def _serie_estocastica(n=120, seed=2):
    """Estacionalidad que EVOLUCIONA: ln y = paseo + paseo estacional.

    seed=2 desde BUG-0198: con la semilla 1 el identificador (ahora con
    plantillas buscadas) encuentra en B1 un AR(3) ≈ 1 + B + B² + B³, la
    estacionalidad estocástica escondida en un AR regular, B1 pasa la
    diagnosis que B2 no pasa y el caso deja de separar las dos rutas. Lo
    medido aquí es la unificación de D, no ese caso concreto."""
    rng = np.random.default_rng(seed)
    tend = np.cumsum(rng.standard_normal(n)) / 60.0
    s = np.zeros(n + 4)
    e = rng.standard_normal(n + 4) / 40.0
    for t in range(4, n + 4):
        s[t] = s[t - 4] + e[t]
    return fue.TimeSeries((100.0 * np.exp(tend + s[4:])).tolist(),
                          freq=4, start=(2000, 1), name="ESTOC")


def _serie_determinista(n=120, amp=0.06, seed=2):
    """Estacionalidad FIJA: un armónico sobre un paseo aleatorio."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    tend = np.cumsum(rng.standard_normal(n)) / 60.0
    return fue.TimeSeries(
        (100.0 * np.exp(tend + amp * np.cos(2 * np.pi * t / 4.0))).tolist(),
        freq=4, start=(2000, 1), name="DETER")


def _unwrap(name):
    import art.mcp_server as M
    f = getattr(M, name)
    return getattr(f, "fn", f)


@pytest.mark.parametrize("entrada", ["build_model", "batch_build",
                                     "guided_identification"])
def test_objetivo_es_declarable_en_toda_entrada(entrada):
    """Ninguna puerta del carril autónomo puede quedarse sin el parámetro."""
    assert "objetivo" in inspect.signature(_unwrap(entrada)).parameters


def test_multivariante_unifica_la_D_que_univariante_deja_dispar():
    """El daño y su reparación, medidos en la decisión de ruta.

    Univariante: con las frecuencias estocásticas y las dos ramas adecuadas,
    gana B2 (D=1) — correcto para uso univariante, e inservible para un
    sistema. Multivariante: B1 (D=0), una sola D, que es el requisito para que
    los órdenes de integración sean comparables.

    BUG-0198: antes se medía sobre una serie sintética completa, y la ruta se
    decidía allí porque NINGUNA rama pasaba la diagnosis; con el identificador
    nuevo una de las dos la pasa y manda la adecuación, como debe. La propiedad
    es de la política, y se mide en ella.
    """
    from art.policy import decide_seasonal_route
    megs = {1: "stochastic", 2: "stochastic"}
    uni, _ = decide_seasonal_route(megs, True, objetivo="univariante",
                                   b1_ok=True, b2_ok=True)
    multi, _ = decide_seasonal_route(megs, True, objetivo="multivariante",
                                     b1_ok=True, b2_ok=True)
    assert uni == "B2"
    assert multi == "B1", "el veto es a D=1"
    # y la adecuación manda antes que el objetivo
    solo_b2, _ = decide_seasonal_route(megs, True, objetivo="multivariante",
                                       b1_ok=False, b2_ok=True)
    assert solo_b2 == "B2"


def test_batch_build_pasa_el_objetivo_a_run_full(tmp_path, monkeypatch):
    """El cable: lo que recibe el tool es lo que recibe el motor.

    Sin esto el parámetro puede existir en la firma y no llegar a ninguna parte,
    que es exactamente la forma que tenía el fallo.
    """
    import art.mcp_server as M

    vistos = []
    real = M.run_full

    def espia(ts, out, **kw):
        vistos.append(kw.get("objetivo"))
        return real(ts, out, **kw)

    monkeypatch.setattr(M, "run_full", espia)

    inp = tmp_path / "DETER.inp"
    ts = _serie_determinista()
    run_full(ts, str(inp), max_rounds=0)          # un .inp de partida
    vistos.clear()

    _unwrap("batch_build")([str(inp)], str(tmp_path / "out"),
                           max_rounds=1, objetivo="multivariante")
    assert vistos == ["multivariante"]


def test_el_lote_declara_su_objetivo_y_avisa_si_las_D_no_coinciden(tmp_path):
    """El defecto silencioso es el peligroso: si no se declaró, hay que decirlo."""
    warnings.simplefilter("ignore")
    inps = []
    for ts in (_serie_estocastica(), _serie_determinista()):
        out = tmp_path / f"{ts.name}.inp"
        run_full(ts, str(out), max_rounds=0)
        inps.append(str(out))

    res = _unwrap("batch_build")(inps, str(tmp_path / "out"), max_rounds=1)
    txt = res[0].text

    # Se anuncia, y se anuncia que NADIE lo eligió.
    assert "univariante" in txt
    assert "defecto" in txt.lower()
    # Y se avisa de la consecuencia concreta, no en abstracto.
    assert "multivariante" in txt
    assert "D=" in txt


def test_la_pregunta_del_objetivo_esta_en_la_apertura():
    """Las instrucciones son la entrega: sin la pregunta, nadie declara nada."""
    from art.mcp_server import _INSTRUCTIONS

    apertura = _INSTRUCTIONS.split("DATOS DE ENTRADA")[0]
    assert "PREGUNTA INICIAL OBLIGATORIA" in apertura
    for opcion in ("UNIVARIANTE", "MULTIVARIANTE", "ESTRUCTURAL"):
        assert opcion in apertura, f"falta la opción {opcion}"
    # Sólo en autónomo: en guiado la pregunta va en la LLAMADA 3, con la
    # estacionalidad ya a la vista.
    assert "LLAMADA 3" in apertura
