"""BUG-0032 — el carril autónomo registraba el DESTINO, no el CAMINO.

`build_model` corre un bucle: estima, diagnostica, y decide DESDE esa diagnosis
qué intervención añadir antes de volver a estimar. Cada vuelta deja un modelo y
una diagnosis en `result.rounds`. Al terminar escribía **una** entrada en el
guion, la del modelo final, y `guion_map` dibujaba un mapa de un solo nodo para
una búsqueda de tres pasos.

Lo que se perdía no es el modelo intermedio —ese se descarta a propósito— sino
la RAZÓN de haber pasado al siguiente, que es lo único que impide volver a
probar la misma rama. Un mapa con nodos y sin aristas no dice por dónde se fue.

Testigo real: RATIO (Gasto/PIB Bolivia) de la réplica del TFM — tres rondas, dos
intervenciones añadidas, un guion con una entrada.

Y hay un corolario de ficheros: `output_path` se reescribe en cada vuelta, así
que una entrada intermedia que apuntase ahí sería un registro FALSO. Cada ronda
escribe su propio `.pre`.
"""
import json
import os

import numpy as np
import pytest

import fue
from art import mcp_server as M
from art.guion import models as g_models


@pytest.fixture
def serie_dos_anomalos():
    """Trimestral I(1) con dos impulsos separados: obliga a más de una ronda."""
    rng = np.random.default_rng(3)
    w = rng.standard_normal(100)
    w[30] += 9.0
    w[70] -= 8.0
    level = 100.0 + np.cumsum(w)
    return fue.TimeSeries(level.tolist(), freq=4, start=(2000, 1), name="DOSANOM")


def _write_inp(ts, path):
    from art.pipeline import _make_model, _write_inp as w
    w(ts, _make_model(ts, 1.0, 1, 0, 0, 1, 0), path)
    return path


def test_the_guion_gets_one_entry_per_round(tmp_path, serie_dos_anomalos):
    src = _write_inp(serie_dos_anomalos, str(tmp_path / "dosanom.inp"))
    out = str(tmp_path / "run" / "dosanom_auto.inp")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    M.build_model(src, out, run_meg=False, guion_name="auto",
                  guion_decision="corrida de prueba")

    gpath = str(tmp_path / "run" / "DOSANOM_guion.json")
    guion = json.load(open(gpath))
    # Sólo los MODELOS: desde que build_model registra también los nodos de
    # especificación, la cadena lleva las dos cosas y este test es sobre las
    # rondas del bucle. Los nodos tienen su propio test.
    entries = [e for e in guion["entries"] if e.get("kind", "model") != "node"]

    # el bucle da 2 vueltas sobre esta serie
    assert len(entries) >= 2, "el guion volvió a registrar sólo el destino"

    # encadenadas: cada una desciende de la anterior
    for prev, cur in zip(entries, entries[1:]):
        assert cur["parent"] == prev["version"]

    # cada entrada dice POR QUÉ se pasó a la siguiente
    for e in entries[:-1]:
        assert e["decision"], "una ronda intermedia sin razón registrada"
        assert "Ronda" in e["decision"]

    # la última conserva la decisión que puso el analista
    assert entries[-1]["decision"] == "corrida de prueba"


def test_every_entry_points_at_a_file_that_really_holds_that_model(
        tmp_path, serie_dos_anomalos):
    """El corolario de ficheros: `output_path` se reescribe cada vuelta, así que
    una entrada intermedia que apuntase ahí mentiría sobre su propio modelo."""
    src = _write_inp(serie_dos_anomalos, str(tmp_path / "dosanom.inp"))
    out = str(tmp_path / "run" / "dosanom_auto.inp")
    os.makedirs(os.path.dirname(out), exist_ok=True)

    M.build_model(src, out, run_meg=False, guion_name="auto")

    guion = json.load(open(str(tmp_path / "run" / "DOSANOM_guion.json")))
    entries = [e for e in guion["entries"] if e.get("kind", "model") != "node"]

    rutas = [e["inp_path"] for e in entries]
    assert len(set(rutas)) == len(rutas), "dos entradas apuntan al mismo fichero"
    for e in entries:
        assert os.path.exists(e["inp_path"]), f"{e['inp_path']} no existe"
        # y el fichero reproduce la verosimilitud que la entrada afirma
        _ts, m = fue.load(e["inp_path"])
        m.fit()
        assert m.loglik == pytest.approx(e["stats"]["loglik"], abs=1e-6)


def test_the_round_reason_names_what_the_diagnosis_found(serie_dos_anomalos):
    """La razón no es decorativa: nombra el extremo y la forma que disparó."""
    from art.pipeline import run_full
    from art.policy import ClaudePolicy
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        res = run_full(serie_dos_anomalos, os.path.join(td, "x.inp"),
                       decision_policy=ClaudePolicy(lam=1.0, d=1, D=0,
                                                    decision="A", n_harmonics=0))
    primera = res.rounds[0]
    texto = M._round_decision_text(primera)
    assert "Ronda 1" in texto
    assert "PULSE" in texto or "STEP" in texto
    problemas = M._round_problems_text(primera)
    assert "extremos" in problemas or "JB" in problemas or "Q rechaza" in problemas
