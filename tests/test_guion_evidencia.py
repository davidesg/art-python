"""`guion_evidencia` — la evidencia de un nodo, SIN reestimar.

Para volver a un camino seguro hacen falta dos cosas: el MAPA —quién desciende
de quién, qué se abandonó y por qué, que lo da `guion_map`— y la EVIDENCIA del
nodo al que se vuelve. Faltaba lo segundo, y conseguirlo obligaba a reestimar
dirigido por el LLM: llamadas, tokens y decisiones intermedias.

No hace falta, porque el convenio de ficheros ya guarda lo necesario:

    el `.out`   la ecuación CON sus errores típicos, exactos. La covarianza es
                un subproducto del camino del optimizador, así que no se puede
                recuperar de ningún otro sitio (BUG-0090, BUG-0091).
    el guion    la diagnosis registrada: Q con retardos y p-valores, JB, σ̂ₐ.
    `figs/`     residuos + ACF/PACF, y el histograma.
"""
import json
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.guion import GuionEntry, load_guion
from art.pipeline import _RESCALE_FACTOR, _write_inp

GE = getattr(srv.guion_evidencia, "fn", srv.guion_evidencia)
CE = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)


@pytest.fixture(scope="module")
def caso(tmp_path_factory):
    d = tmp_path_factory.mktemp("ev")
    rng = np.random.default_rng(21)
    y = np.cumsum(rng.standard_normal(120) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="EV")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(d / "EV.inp")
    _write_inp(ts, m, f)
    g = str(d / "EV_guion.json")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        CE(f, str(d / "EV_m00.inp"), lam=0.0, d=1, D=0, p=0, q=1,
           n_harmonics=0, guion_path=g, guion_decision="base",
           guion_rationale="punto de partida")
    return g, str(d)


def _res(*a, **k):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return GE(*a, **k)


def _txt(*a, **k):
    return "\n".join(getattr(c, "text", "") for c in _res(*a, **k))


def _imgs(*a, **k):
    return sum(1 for c in _res(*a, **k) if getattr(c, "type", "") == "image")


# ───────────── lo que devuelve ─────────────

def test_devuelve_la_ecuacion_con_sus_errores_tipicos(caso):
    g, _ = caso
    t = _txt(g, con_figura=False)
    assert "del registro de la estimación" in t
    assert "no se ha reestimado nada" in t
    assert "t=" in t


def test_las_SE_salen_del_out_y_no_de_una_reestimacion(caso):
    """Se comprueba contra el fichero: si el número no está ahí, viene de otro
    sitio."""
    from art.outfile import lee_out
    g, _ = caso
    e = load_guion(g).entries[-1]
    r = lee_out(e.out_path)
    t = _txt(g, con_figura=False)
    for p in r.parametros[:3]:
        assert f"({p.se:.6f})" in t


def test_devuelve_la_diagnosis_registrada(caso):
    """Q con sus retardos y p-valores, no el veredicto binario: es lo que
    permite releer un nodo con el instrumento de hoy (BUG-0077)."""
    g, _ = caso
    t = _txt(g, con_figura=False)
    assert "Ruido blanco" in t and "Q(" in t
    assert "Normalidad" in t and "JB p=" in t
    assert "σ̂ₐ" in t


def test_devuelve_las_dos_figuras(caso):
    """La diagnosis de esta escuela son TRES cosas: residuos, ACF/PACF e
    histograma. El Jarque-Bera se lee sobre la tercera."""
    g, _ = caso
    assert _imgs(g) == 2


def test_con_figura_False_no_devuelve_ninguna(caso):
    g, _ = caso
    assert _imgs(g, con_figura=False) == 0


def test_remite_al_mapa(caso):
    """Las dos mitades: el mapa dice a dónde volver, esto qué hay allí."""
    g, _ = caso
    assert "guion_map(" in _txt(g, con_figura=False)


# ───────────── el histograma se guarda ─────────────

def test_el_histograma_queda_en_disco(caso):
    g, d = caso
    e = load_guion(g).entries[-1]
    assert e.hist_path
    assert os.path.exists(os.path.join(d, e.hist_path))


def test_son_dos_ficheros_distintos(caso):
    g, d = caso
    e = load_guion(g).entries[-1]
    a = open(os.path.join(d, e.figure_path), "rb").read()
    b = open(os.path.join(d, e.hist_path), "rb").read()
    assert a != b


def test_la_entrada_tiene_campo_para_el_histograma():
    assert "hist_path" in GuionEntry.__dataclass_fields__


# ───────────── cuando falta algo, lo DICE ─────────────

def test_sin_out_lo_dice_en_vez_de_reestimar(caso):
    g, d = caso
    e = load_guion(g).entries[-1]
    guardado = e.out_path
    os.rename(guardado, guardado + ".apartado")
    try:
        t = _txt(g, con_figura=False)
        assert "No hay `.out` para este nodo" in t
        assert "no se recupera del `.pre`" in t
    finally:
        os.rename(guardado + ".apartado", guardado)


def test_una_figura_regenerada_se_marca_como_tal(caso):
    """Regenerar vale para una figura —depende de los VALORES— pero no es la
    que se guardó, y decirlo es la diferencia entre un registro y una caché."""
    g, d = caso
    e = load_guion(g).entries[-1]
    ruta = os.path.join(d, e.hist_path)
    os.rename(ruta, ruta + ".apartado")
    try:
        t = _txt(g)
        assert "REGENERADO" in t
        assert "no es la que se guardó" in t
    finally:
        os.rename(ruta + ".apartado", ruta)


def test_no_se_reestima_para_la_ecuacion():
    """La propiedad central: la ecuación sale del `.out`, no del motor."""
    from tests._fuente import fuente_de
    src = fuente_de(srv.guion_evidencia)
    assert "lee_out" in src
    assert "_load_fitted" not in src and "estimar(" not in src


def test_para_la_figura_se_usa_mirar_no_estimar():
    """Regenerar una figura no promete errores típicos, así que no debe avisar
    de nada (contrato §6-B)."""
    from tests._fuente import fuente_de
    assert "mirar" in fuente_de(srv.guion_evidencia)


# ───────────── los bordes ─────────────

def test_una_version_que_no_existe_lista_las_que_hay(caso):
    g, _ = caso
    t = _txt(g, version=999, con_figura=False)
    assert "❌" in t and "Hay: v" in t


def test_un_nodo_de_decision_no_tiene_evidencia(caso):
    """Y se dice a dónde ir a por su contenido."""
    g, _ = caso
    nodo = getattr(srv.guion_node, "fn", srv.guion_node)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        nodo(g, nodo="lambda", decidido="λ=0", razon="índice de precios")
    v = load_guion(g).entries[-1].version
    t = _txt(g, version=v, con_figura=False)
    assert "nodo de DECISIÓN" in t
    assert "guion_map" in t


def test_version_0_toma_el_ultimo_MODELO(caso):
    """No la última entrada: un nodo de decisión no tiene evidencia."""
    g, _ = caso
    t = _txt(g, version=0, con_figura=False)
    assert "nodo de DECISIÓN" not in t
    assert "Diagnosis registrada" in t


def test_un_guion_sin_modelos_lo_dice(tmp_path):
    from art.guion import Guion, save_guion
    p = str(tmp_path / "vacio.json")
    save_guion(Guion(series="X", analyst="t", created="2026-09-05",
                     entries=[]), p)
    assert "ningún modelo" in _txt(p)
