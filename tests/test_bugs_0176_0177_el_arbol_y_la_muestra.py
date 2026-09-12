"""BUG-0176 y BUG-0177 — lo que el mapa dibuja tiene que poder leerse.

Los dos salieron del run 4 de IPC_ES, y los dos se ven en el mismo árbol.

0176: reinscribir un modelo —para ponerle nombre, para colgarle el veredicto—
      lo colgaba de la ÚLTIMA entrada del guion. Resultado publicado: el modelo
      adoptado descendiendo de la sobreparametrización que lo rechazó, y el
      modelo FINAL descendiendo del que se descartó. Tres veces en un run.

0177: el guion guardaba ℓ, AIC y BIC y no sobre qué muestra. Con `extend_sample`
      (BUG-0173) dos entradas del mismo guion pueden estar sobre muestras
      distintas: el mapa las dibujaba una debajo de otra y el último paso parecía
      un salto de ajuste que sólo era otra n.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.guion import (Guion, GuionEntry, GuionStats, comparaciones_entre_muestras,
                       load_guion, pre_hermano, save_guion, sha_del_fichero)
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar
from tests._texto import dice


def _fn(nombre):
    import art.mcp_server as M
    f = getattr(M, nombre)
    return getattr(f, "fn", f)


def _texto(o):
    return o[0].text if isinstance(o, list) else str(o)


def _serie(n=120, seed=7, start=(2010, 1)):
    r = np.random.default_rng(seed)
    y = np.cumsum(r.standard_normal(n) * 0.4) + 100.0
    return fue.TimeSeries(y.tolist(), freq=12, start=start, name="S")


@pytest.fixture(scope="module")
def caso(tmp_path_factory):
    """Un guion real: m01 estimado, m02 encadenado de él, y m01 REINSCRITO."""
    d = tmp_path_factory.mktemp("arbol")
    warnings.simplefilter("ignore")
    A = _serie()
    base = str(d / "S.inp")
    _write_inp(A, fue.Model(A, d=1), base)
    gp = str(d / "S_guion.json")
    ce = _fn("confirm_and_estimate")

    ce(inp_path=base, output_path=str(d / "S_m01.inp"), lam=1.0, d=1, q=1,
       guion_path=gp, guion_decision="base")
    ce(inp_path=base, output_path=str(d / "S_m02.inp"), lam=1.0, d=1, p=1, q=1,
       base_pre_path=str(d / "S_m01.pre"), guion_path=gp,
       guion_decision="anade AR")
    # …y ahora se reinscribe m01 para colgarle el veredicto final.
    _fn("record_version")(inp_path=str(d / "S_m01.inp"), guion_path=gp,
                          name="FINAL_m01", decision="MODELO FINAL")
    return d, gp


# ── BUG-0176 ──────────────────────────────────────────────────────────────

def test_la_reinscripcion_se_reconoce_por_su_huella(caso):
    d, gp = caso
    g = load_guion(gp)
    assert len(g.entries) == 3
    v1, v2, v3 = g.entries
    assert v3.re_registro_de == v1.version, (
        "el mismo `.pre` byte a byte es el mismo modelo")
    assert v3.pre_sha and v3.pre_sha == v1.pre_sha


def test_la_copia_NO_cuelga_de_la_ultima_entrada(caso):
    """EL DEFECTO. v3 es v1 otra vez: no puede descender de v2."""
    d, gp = caso
    v1, v2, v3 = load_guion(gp).entries
    assert v3.parent != v2.version, (
        "el modelo FINAL colgando del que vino después: el árbol miente")
    assert v3.parent == v1.parent
    assert v3.parent_origen == "re-registro"


def test_el_mapa_dice_que_es_una_reinscripcion(caso):
    d, gp = caso
    t = _texto(_fn("guion_map")(gp))
    assert dice(t, "re-registro de v1")


def test_record_version_puede_declarar_de_donde_viene(caso, tmp_path):
    """La puerta que faltaba: sin ella el padre era siempre una conjetura."""
    import inspect
    f = _fn("record_version")
    assert "base_pre_path" in inspect.signature(f).parameters


# ── BUG-0177 ──────────────────────────────────────────────────────────────

def test_el_guion_guarda_sobre_cuantos_datos(caso):
    d, gp = caso
    for e in load_guion(gp).entries:
        assert e.stats.nobs == 120, f"v{e.version} no dice su muestra"


def _con_n(version, n, parent=None):
    return GuionEntry(
        version=version, name=f"v{version}", inp_path="", timestamp="t",
        spec={}, stats=GuionStats(loglik=-1.0, nobs=n), equation="",
        decision="", rationale="", problems_found="", next_version="",
        parent=parent)


def test_un_salto_de_muestra_se_detecta():
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_con_n(1, 216))
    g.entries.append(_con_n(2, 263, parent=1))
    assert comparaciones_entre_muestras(g) == [(2, 263, 1, 216)]


def test_la_misma_muestra_no_se_denuncia():
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_con_n(1, 216))
    g.entries.append(_con_n(2, 216, parent=1))
    assert comparaciones_entre_muestras(g) == []


def test_sin_muestra_registrada_no_se_denuncia():
    """No consta no es lo mismo que difiere: un guion viejo no se acusa."""
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(_con_n(1, None))
    g.entries.append(_con_n(2, 263, parent=1))
    assert comparaciones_entre_muestras(g) == []


def test_el_mapa_avisa_del_salto_de_muestra(tmp_path):
    g = Guion(series="S", analyst="", created="2026-09-12")
    g.entries.append(_con_n(1, 216))
    g.entries.append(_con_n(2, 263, parent=1))
    gp = str(tmp_path / "S_guion.json")
    save_guion(g, gp)
    t = _texto(_fn("guion_map")(gp))
    assert dice(t, "Hay saltos de MUESTRA en el árbol")
    assert dice(t, "la diferencia no es ajuste, es tamaño")
    assert "n=263" in t and "n=216" in t


def test_el_mapa_pone_la_n_junto_al_ajuste(caso):
    """Si ℓ se lee en columna, la n tiene que estar en la misma línea."""
    d, gp = caso
    t = _texto(_fn("guion_map")(gp))
    assert "n=120" in t
