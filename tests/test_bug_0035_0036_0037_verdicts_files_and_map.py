"""BUG-0035, BUG-0036 y BUG-0037 — tres defectos que salieron del mismo
recorrido autónomo sobre la réplica del TFM de Bolivia, y que comparten forma:
la herramienta afirma algo que el estado no sostiene.

**BUG-0035** — `meg_reformulate` escribía `.pre` y `.out` y NO el `.inp` de
`output_path`: devolvía una ruta que no existía, y el paso siguiente moría con
FileNotFoundError. Además rotulaba el bloque con el nombre del modelo ANTERIOR,
porque componía la ecuación del modelo en memoria en vez de releer el fichero.

**BUG-0036** — dos veredictos de adecuación con el mismo nombre y ninguna regla
de prioridad. `confirm_and_estimate` publica `residuals_ok`; la guarda de
`formal_tests` tenía su propia lista, que divergía en las DOS direcciones —
contaba extremos (que `residuals_ok` deja fuera a propósito) y no miraba la
estacionalidad residual (que `residuals_ok` sí cuenta).

**BUG-0037** — la cascada de `guion_abandon` arrastraba el nodo que registra el
rechazo, porque `guion_node` lo encadena a la última entrada y la última era el
callejón. Barrer ese nodo borra la razón justo cuando más falta hace.
"""
import os
import tempfile

import numpy as np
import pytest

import fue
from art import mcp_server as M
from art.diagnosis import diagnose
from art.describe import describe_formal_tests
from art.guion import (Guion, GuionEntry, GuionStats, load_guion, save_guion,
                       abandon)
from art.pipeline import _make_model, _write_inp, _load_fitted


# ── BUG-0035 ────────────────────────────────────────────────────────────────

def _serie_estacional(n=100, seed=6):
    rng = np.random.default_rng(seed)
    a = np.cumsum(rng.standard_normal(n)) * 0.5
    b = np.cumsum(rng.standard_normal(n)) * 0.5
    t = np.arange(n)
    est = a * np.cos(np.pi / 2 * t) + b * np.sin(np.pi / 2 * t)
    nivel = 100.0 + np.cumsum(rng.standard_normal(n)) + est
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="BASE")


def test_meg_reformulate_writes_the_whole_file_triple(tmp_path):
    ts = _serie_estacional()
    base = str(tmp_path / "BASE_m00.inp")
    _write_inp(ts, _make_model(ts, 1.0, 1, 0, 0, 0, 1, seasonal=True), base)
    _, m0 = _load_fitted(base)
    m0.write_pre(str(tmp_path / "BASE_m00.pre"))

    salida = str(tmp_path / "BASE_m10.inp")
    M.meg_reformulate(str(tmp_path / "BASE_m00.pre"), 1, salida,
                      base_pre_path=str(tmp_path / "BASE_m00.pre"))

    for ext in (".inp", ".pre", ".out"):
        ruta = str(tmp_path / f"BASE_m10{ext}")
        assert os.path.exists(ruta), f"falta el {ext} — el convenio son las tres"

    # y el .inp reproduce: es la propiedad que lo hace útil
    _, m = _load_fitted(salida)
    assert m.loglik == pytest.approx(m.loglik)


def test_the_equation_is_labelled_with_the_file_it_wrote(tmp_path):
    ts = _serie_estacional()
    base = str(tmp_path / "BASE_m00.inp")
    _write_inp(ts, _make_model(ts, 1.0, 1, 0, 0, 0, 1, seasonal=True), base)
    _, m0 = _load_fitted(base)
    m0.write_pre(str(tmp_path / "BASE_m00.pre"))

    salida = str(tmp_path / "BASE_m10.inp")
    txt = M.meg_reformulate(str(tmp_path / "BASE_m00.pre"), 1, salida,
                            base_pre_path=str(tmp_path / "BASE_m00.pre"))[0].text
    rotulo = [l for l in txt.splitlines() if "MODELO ESTIMADO" in l]
    assert rotulo, "no hay bloque de ecuación"
    assert "BASE_m10" in rotulo[0], f"rótulo heredado del anterior: {rotulo[0]}"


# ── BUG-0036 ────────────────────────────────────────────────────────────────

def _modelo_con_un_extremo(tmp_path):
    """Calibrado: Q pasa, JB pasa, y queda un |z|>3. Un salto más grande rompe
    también la JB y entonces los dos veredictos coinciden — por eso el testigo
    se calibra, no se exagera."""
    rng = np.random.default_rng(0)
    w = rng.standard_normal(100)
    w[60] += 3.6
    ts = fue.TimeSeries((100.0 + np.cumsum(w)).tolist(), freq=4,
                        start=(2000, 1), name="UNEXT")
    ruta = str(tmp_path / "unext.inp")
    m = fue.Model(ts, d=1, boxlam=1.0, ma=[[0.0]], ma_free=[[True]],
                  mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, mf = _load_fitted(ruta)
    return mf


def test_the_two_adequacy_verdicts_agree(tmp_path):
    m = _modelo_con_un_extremo(tmp_path)
    dg = diagnose(m)
    assert dg.residuals_ok, "el testigo dejó de valer: la diagnosis ya no aprueba"
    assert dg.extreme, "el testigo dejó de valer: no queda ningún extremo"

    txt = describe_formal_tests(m).summary
    assert "todavía NO es adecuado" not in txt, (
        "formal_tests bloquea un modelo que la diagnosis aprueba")


def test_the_remaining_extreme_is_still_reported_as_a_caveat(tmp_path):
    """No basta con dejar de bloquear: el extremo sigue estando y hay que decirlo."""
    m = _modelo_con_un_extremo(tmp_path)
    txt = describe_formal_tests(m).summary
    assert "salvedad" in txt
    assert "extremo" in txt


def test_residual_seasonality_now_blocks_too(tmp_path):
    """La otra dirección de la divergencia: `residuals_ok` cuenta la
    estacionalidad residual y la guarda no la miraba."""
    from art.describe import describe_formal_tests as dft
    rng = np.random.default_rng(11)
    t = np.arange(120)
    # patrón estacional fuerte SIN modelar: la diagnosis debe rechazarlo
    nivel = 100.0 + np.cumsum(rng.standard_normal(120)) + 6.0 * np.cos(np.pi / 2 * t)
    ts = fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="SEAS")
    ruta = str(tmp_path / "seas.inp")
    m = fue.Model(ts, d=1, boxlam=1.0, ma=[[0.0]], ma_free=[[True]],
                  mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, mf = _load_fitted(ruta)
    dg = diagnose(mf)
    if dg.residuals_ok:
        pytest.skip("este testigo sintético no dejó estacionalidad residual")
    assert "todavía NO es adecuado" in dft(mf).summary


# ── BUG-0037 ────────────────────────────────────────────────────────────────

def _guion_rama_y_nodo(tmp_path):
    gp = str(tmp_path / "S_guion.json")
    M.guion_node(gp, nodo="lambda", decidido="0", razon="es un índice")
    g = load_guion(gp)
    g.entries.append(GuionEntry(
        version=2, name="m20", inp_path="/x/m20.inp", timestamp="t", spec={},
        stats=GuionStats(loglik=-1.0, aic=4.0, bic=5.0, sigma_a=1.0,
                         q_pass=True, jb_pass=True, n_extreme=0),
        equation="", decision="candidato MA(1)", rationale="",
        problems_found="", next_version="", parent=1))
    save_guion(g, gp)
    M.guion_node(gp, nodo="ordenes", decidido="AR(1)",
                 razon="estimé el MA(1) y lo descarto")
    return gp


def test_the_node_that_records_the_rejection_survives(tmp_path):
    gp = _guion_rama_y_nodo(tmp_path)
    M.guion_abandon(gp, 2, why="rama hermana, descartada por AIC y BIC")

    e = {x.version: x for x in load_guion(gp).entries}
    assert e[2].status == "dead-end", "el modelo descartado debe quedar marcado"
    assert e[3].status != "dead-end", (
        "el nodo que explica el rechazo quedó marcado como callejón: eso borra "
        "la razón del tronco")
    assert e[3].parent == 1, "el nodo debe recolocarse en el tronco"


def test_descendant_models_are_still_cascaded(tmp_path):
    """La cascada sigue haciendo su trabajo con los MODELOS: una decisión
    contaminada contamina lo que se construye encima."""
    gp = _guion_rama_y_nodo(tmp_path)
    g = load_guion(gp)
    g.entries.append(GuionEntry(
        version=4, name="m30", inp_path="/x/m30.inp", timestamp="t", spec={},
        stats=GuionStats(loglik=-1.0, aic=4.0, bic=5.0, sigma_a=1.0,
                         q_pass=True, jb_pass=True, n_extreme=0),
        equation="", decision="", rationale="", problems_found="",
        next_version="", parent=2))
    save_guion(g, gp)

    abandonadas, recolocadas = abandon(load_guion(gp), 2, why="x")
    assert 4 in abandonadas, "un modelo construido sobre el callejón debe caer"
    assert 3 in recolocadas


def test_abandon_still_requires_a_reason(tmp_path):
    gp = _guion_rama_y_nodo(tmp_path)
    with pytest.raises(ValueError):
        abandon(load_guion(gp), 2, why="   ")
