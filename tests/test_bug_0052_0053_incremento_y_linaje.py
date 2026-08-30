"""BUG-0052 y BUG-0053 — el ciclo iterativo tiene que cerrarse solo.

0052: `guided_identification(pre_path=…)` identifica sobre RESIDUOS, o sea
sugiere un INCREMENTO, pero la llamada que imprime SUSTITUYE el ARMA.
0053: `meg_reformulate` escribía un modelo que el guion nunca veía, y rompía el
linaje de la única rama que el ejercicio del MEG existe para documentar.
"""
import inspect
import json
import os
import re
import shutil
import warnings

import pytest

from datos_replica import REPLICA, REPLICA_DS, requiere_replica


PGAS = REPLICA + "run2/PGAS/PGAS_m03.pre"
RATIO = REPLICA + "run2/RATIO/RATIO_m03.pre"


def _fn(name):
    import art.mcp_server as M
    f = getattr(M, name)
    return getattr(f, "fn", f)


# ── BUG-0052 ──────────────────────────────────────────────────────────────

@pytest.fixture
def salida_pgas():
    if not os.path.exists(PGAS):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    out = _fn("guided_identification")(PGAS, lam=0.0, d=1, D=0, pre_path=PGAS)
    return out[0].text if isinstance(out, list) else str(out)


def test_la_sugerencia_es_el_orden_TOTAL(salida_pgas):
    """La base lleva MA(1) y los residuos piden 1 más: hay que pasar q=2."""
    from art.mcp_server import _load_fitted
    _, m = _load_fitted(PGAS)
    q_base = len(m.ma[0]) if m.ma else 0
    assert q_base == 1, "el caso cambió; ya no mide lo que dice medir"

    mo = re.search(r"\(Sugerencia: p=(\d+), q=(\d+)", salida_pgas)
    assert mo, "no se encontró la línea de sugerencia"
    q_sug = int(mo.group(2))
    assert q_sug > q_base, (
        f"sugiere q={q_sug} sobre una base que ya lleva q={q_base}: "
        "reestimaría el mismo modelo")


def test_se_avisa_de_que_la_lista_es_un_incremento(salida_pgas):
    assert "INCREMENTO" in salida_pgas
    assert "sustituye" in salida_pgas.lower()


@requiere_replica
def test_sin_base_arma_no_se_inventa_el_aviso(tmp_path):
    """Un .pre sin ARMA no necesita la advertencia: incremento y total coinciden."""
    if not os.path.exists(PGAS):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    base = REPLICA + "run2/PGAS/PGAS_m00.pre"
    if not os.path.exists(base):
        pytest.skip("PGAS_m00.pre no disponible")
    from art.mcp_server import _load_fitted
    _, m = _load_fitted(base)
    if (len(m.ar[0]) if m.ar else 0) or (len(m.ma[0]) if m.ma else 0):
        pytest.skip("la base elegida sí lleva ARMA")
    out = _fn("guided_identification")(base, lam=0.0, d=1, D=0, pre_path=base)
    txt = out[0].text if isinstance(out, list) else str(out)
    assert "INCREMENTO" not in txt


# ── BUG-0053 ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("par", ["guion_path", "guion_name",
                                 "guion_decision", "guion_rationale"])
def test_meg_reformulate_acepta_los_parametros_del_guion(par):
    assert par in inspect.signature(_fn("meg_reformulate")).parameters


def test_la_reformulacion_cuelga_de_su_padre(tmp_path):
    """El linaje: la reformulación es hija del baseline, no una huérfana."""
    if not os.path.exists(RATIO):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _record_to_guion, _load_fitted

    g = str(tmp_path / "g.json")
    base = str(tmp_path / "RATIO_m03.pre")
    shutil.copy(RATIO, base)

    _, mb = _load_fitted(base)
    _record_to_guion(mb, base, 0.0, g, name="m03", decision="baseline")

    _fn("meg_reformulate")(base, freq=1, output_path=str(tmp_path / "MEG.inp"),
                           base_pre_path=base, guion_path=g,
                           guion_name="m06_MEG_f1")

    entries = json.load(open(g))["entries"]
    assert len(entries) == 2, "la reformulación no se registró"
    hijo = entries[1]
    assert hijo["parent"] == entries[0]["version"]
    # Y con SU especificación, no la del baseline (BUG-0051 la hace visible).
    assert hijo["spec"]["ifadf"] == [0, 1, 0]
    assert entries[0]["spec"]["ifadf"] == [0, 0, 0]


# ── BUG-0057 ──────────────────────────────────────────────────────────────

@requiere_replica
def test_un_operador_FIJADO_no_cuenta_como_base(tmp_path):
    """Un AR(1) fijado en cero está en la estructura, no en la estimación.

    Contarlo hacía que la sugerencia pidiera p=1 sobre una base sin AR libre, y
    seguirla estimaba un AR donde el analista no había pedido ninguno.
    """
    import os
    base = REPLICA + "guiado/ITCER/ITCER_m10.pre"
    if not os.path.exists(base):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _load_fitted
    _, m = _load_fitted(base)
    assert m.ar and m.ar[0] == [0.0], "el caso ya no tiene el AR fijado"
    assert m.ar_free == [[False]], "el AR ya no está fijado; el test no mide nada"

    out = _fn("guided_identification")(base, lam=0.0, d=1, D=0, pre_path=base)
    txt = out[0].text if isinstance(out, list) else str(out)
    mo = re.search(r"\(Sugerencia: p=(\d+), q=(\d+)", txt)
    assert mo and int(mo.group(1)) == 0, (
        f"cuenta el AR fijado como base: {mo.group(0) if mo else 'sin sugerencia'}")
    assert "INCREMENTO" not in txt, "no hay base ARMA libre; no procede el aviso"
