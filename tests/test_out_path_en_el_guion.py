"""El `.out` como artefacto de primera clase del guion (estudio §6-D).

La terna comparte basename, así que el `.out` se PODRÍA derivar del `inp_path`.
Pero derivarlo es SUPONER que está, y esa suposición ya falló: sobre el corpus
real, 4 de 15 entradas apuntaban a ficheros ausentes (BUG-0092).

Y no es un artefacto cualquiera. La covarianza no es una propiedad del óptimo
sino un subproducto del camino del optimizador, así que el `.pre` no puede
llevarla: **el `.out` es la única constancia fiel de las desviaciones típicas**
(BUG-0090, BUG-0091). Una entrada sin `.out` es una entrada cuyos errores típicos
no se recuperan sin reestimar, y eso cambia lo que se puede hacer desde ese nodo.

El `.pre` NO lleva campo, y es deliberado: es la semilla del paso siguiente, no
algo que se relea.
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

ED = getattr(srv.estimate_and_diagnose, "fn", srv.estimate_and_diagnose)
GM = getattr(srv.guion_map, "fn", srv.guion_map)


@pytest.fixture
def caso(tmp_path):
    rng = np.random.default_rng(5)
    y = np.cumsum(rng.standard_normal(90) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="R4")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(tmp_path / "R4.inp")
    _write_inp(ts, m, f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ED(f, str(tmp_path / "R4_m00.inp"))
    g = [x for x in os.listdir(str(tmp_path)) if x.endswith("guion.json")][0]
    return str(tmp_path / g), str(tmp_path)


def _mapa(g):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return "\n".join(getattr(c, "text", "") for c in GM(g))


# ───────────── el campo ─────────────

def test_la_entrada_tiene_campo_para_el_out():
    assert "out_path" in GuionEntry.__dataclass_fields__


def test_el_pre_no_tiene_campo():
    """Deliberado: es la semilla del paso siguiente, no algo que se relea."""
    assert "pre_path" not in GuionEntry.__dataclass_fields__


def test_se_registra_y_resuelve(caso):
    g, _ = caso
    e = load_guion(g).entries[0]
    assert e.out_path
    assert os.path.exists(e.out_path)


def test_se_registra_solo_si_existe(caso, tmp_path):
    """Un campo que apunta al vacío es peor que un campo vacío."""
    from art.pipeline import _load_fitted
    g, d = caso
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, m = _load_fitted(os.path.join(d, "R4.inp"))
    srv._record_to_guion(model=m, inp_path=os.path.join(d, "sin_artefactos.inp"),
                         lam=0.0, guion_path=g, name="huerfano")
    e = [x for x in load_guion(g).entries if x.name == "huerfano"][0]
    assert e.out_path is None


def test_un_guion_viejo_sigue_abriendose(tmp_path):
    """El campo es nuevo; los guiones ya escritos no lo llevan."""
    from art.guion import Guion, save_guion
    p = str(tmp_path / "viejo.json")
    save_guion(Guion(series="S", analyst="t", created="2026-09-05",
                     entries=[]), p)
    d = json.load(open(p))
    d["entries"] = [{
        "version": 1, "name": "m00", "inp_path": "/no/existe.inp",
        "timestamp": "", "spec": {}, "equation": "", "decision": "",
        "rationale": "", "problems_found": "", "next_version": "",
    }]
    with open(p, "w") as fh:
        json.dump(d, fh)
    e = load_guion(p).entries[0]
    assert e.out_path is None


# ───────────── lo que el mapa dice ─────────────

def test_el_mapa_avisa_de_los_nodos_sin_out(caso):
    """«Puedo releerlo» y «tengo que rehacerlo» no son lo mismo, y el mapa es
    donde se decide a dónde volver."""
    g, d = caso
    e = load_guion(g).entries[0]
    os.remove(e.out_path)
    t = _mapa(g)
    assert "sin su `.out`" in t
    assert "no se pueden LEER" in t


def test_el_mapa_avisa_MAS_de_los_nodos_sin_inp(caso):
    """Sin `.out` se puede reestimar; sin `.inp` el nodo es irrecuperable. Son
    dos gravedades distintas y el aviso las distingue."""
    g, d = caso
    e = load_guion(g).entries[0]
    os.remove(os.path.splitext(e.inp_path)[0] + ".inp")
    t = _mapa(g)
    assert "sin su `.inp`" in t
    assert "no se puede reestimar" in t


def test_una_terna_completa_no_produce_avisos(caso):
    g, _ = caso
    t = _mapa(g)
    assert "sin su `.out`" not in t
    assert "sin su `.inp`" not in t


def test_los_nodos_de_decision_no_cuentan(caso):
    """Un nodo de decisión no tiene modelo, así que no tiene terna que echar en
    falta."""
    g, _ = caso
    srv_node = getattr(srv.guion_node, "fn", srv.guion_node)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        srv_node(g, nodo="d1", decidido="una decisión", razon="porque sí")
    t = _mapa(g)
    assert "sin su `.inp`" not in t
