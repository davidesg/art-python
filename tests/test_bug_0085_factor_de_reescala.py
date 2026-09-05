"""BUG-0085 — el factor de reescala se perdía al clonar o construir un modelo.

La suite estima sobre 100·log(y) (`pipeline._RESCALE_FACTOR`), que es lo que hace
que σ̂ₐ se lea en tanto por ciento. `fue.Model` trae `refactor=1.0` por defecto,
así que todo modelo construido sin pasarlo salía en OTRA escala — y ℓ, AIC y BIC
difieren entonces en n·ln(100).

La red que había en `_write_inp` no saltaba nunca:

    getattr(model, 'refactor', _RESCALE_FACTOR) or _RESCALE_FACTOR

el `getattr` encontraba el 1.0 del defecto, que es *truthy*. La convención sólo
se aplicaba cuando el atributo faltaba, y nunca faltaba.
"""
import math
import os
import tempfile
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.pipeline import _RESCALE_FACTOR, _load_ts_model, _write_inp


def _ts(n=80, seed=3):
    rng = np.random.default_rng(seed)
    y = np.cumsum(rng.standard_normal(n)) + 100.0
    return fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="S")


def _base(refactor=_RESCALE_FACTOR):
    ts = _ts()
    return ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=refactor)


# ───────────────── los dos clonadores ─────────────────

def test_la_escalera_de_ockham_conserva_la_escala():
    from art.escalera import _clona_con
    _, m = _base()
    assert _clona_con(m, []).refactor == _RESCALE_FACTOR


def test_las_configuraciones_del_incidente_conservan_la_escala():
    """Era la fuga más visible: la tabla de `incident_configurations` salía en
    escala 1 mientras el modelo base estaba en 100. Sobre FOOD_UEM eso son
    −2002 frente a −8,20 en la misma pantalla."""
    from art.configuracion import arranques_candidatos, evalua_configuraciones
    ts, m = _base()
    m.fit()
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / (r.std(ddof=0) or 1.0)
    k = int(np.argmax(np.abs(z)))
    conj = evalua_configuraciones(
        m, arranques_candidatos(z, [k], d=1, umbral_activo=1.0), d=1)
    assert conj.vivos, "ninguna configuración estimó"
    for c in conj.vivos:
        assert c.model.refactor == m.refactor


def test_la_escala_del_candidato_pone_el_AIC_en_el_rango_del_base():
    """No basta con que el atributo se copie: el número tiene que caer donde
    corresponde. Sin el arreglo, el AIC del candidato se iba n·ln(100) abajo."""
    from art.configuracion import arranques_candidatos, evalua_configuraciones
    ts, m = _base()
    m.fit()
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / (r.std(ddof=0) or 1.0)
    k = int(np.argmax(np.abs(z)))
    conj = evalua_configuraciones(
        m, arranques_candidatos(z, [k], d=1, umbral_activo=1.0), d=1)
    salto = len(r) * math.log(_RESCALE_FACTOR)
    for c in conj.vivos:
        assert abs(c.aic - m._result.aic) < salto, (
            f"AIC del candidato {c.etiqueta} a {c.aic - m._result.aic:.0f} "
            f"puntos del base: eso es el salto de escala, no ajuste")


# ───────────────── la guarda que no callaba ─────────────────

def test_escribir_fuera_de_la_convencion_avisa():
    ts, m = _base(refactor=1.0)
    d = tempfile.mkdtemp()
    with pytest.warns(RuntimeWarning, match="factor de reescala"):
        _write_inp(ts, m, os.path.join(d, "raro.inp"))


def test_escribir_en_la_convencion_no_avisa():
    ts, m = _base()
    d = tempfile.mkdtemp()
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        _write_inp(ts, m, os.path.join(d, "bien.inp"))


def test_un_refactor_explicito_silencia_el_aviso():
    """Estimar en escala 1 es un uso legítimo de la librería; lo que no vale es
    hacerlo por descuido."""
    ts, m = _base(refactor=1.0)
    d = tempfile.mkdtemp()
    f = os.path.join(d, "adrede.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        _write_inp(ts, m, f, refactor=1.0)
    _, m2 = _load_ts_model(f)
    assert m2.refactor == 1.0


def test_el_factor_escrito_es_el_que_se_relee():
    ts, m = _base()
    d = tempfile.mkdtemp()
    f = os.path.join(d, "rt.inp")
    _write_inp(ts, m, f)
    _, m2 = _load_ts_model(f)
    assert m2.refactor == _RESCALE_FACTOR


def test_create_inp_nace_en_la_convencion():
    """El esqueleto del que arranca todo análisis salía en escala 1."""
    import art.mcp_server as srv
    d = tempfile.mkdtemp()
    f = os.path.join(d, "nuevo.inp")
    fn = getattr(srv.create_inp, "fn", srv.create_inp)
    fn(data=[float(x) for x in range(1, 41)], freq=4, start_year=2000,
       start_period=1, name="X", output_path=f)
    _, m = _load_ts_model(f)
    assert m.refactor == _RESCALE_FACTOR


# ───────────────── el guion deja de apilar unidades distintas ─────────────────

def test_el_guion_guarda_la_escala():
    from art.guion import GuionStats
    assert "refactor" in GuionStats.__dataclass_fields__


def test_el_mapa_avisa_cuando_se_mezclan_escalas(tmp_path):
    import json
    import art.mcp_server as srv
    from art.guion import Guion, GuionEntry, GuionStats, save_guion

    def ent(v, rf):
        return GuionEntry(
            version=v, name=f"m{v}", inp_path="", timestamp="", spec={},
            equation="", decision="", rationale="", problems_found="",
            next_version="",
            stats=GuionStats(loglik=1.0, aic=2.0, bic=3.0, sigma_a=0.1,
                             q_pass=True, jb_pass=True, n_extreme=0,
                             refactor=rf))
    p = str(tmp_path / "g.json")
    save_guion(Guion(series="S", analyst="t", created="2026-09-04", entries=[ent(1, 100.0), ent(2, 1.0)]), p)
    fn = getattr(srv.guion_map, "fn", srv.guion_map)
    txt = "\n".join(getattr(c, "text", "") for c in fn(p))
    assert "misma ESCALA" in txt
    assert "n·ln(factor)" in txt


def test_el_mapa_calla_cuando_la_escala_es_una(tmp_path):
    import art.mcp_server as srv
    from art.guion import Guion, GuionEntry, GuionStats, save_guion

    def ent(v):
        return GuionEntry(
            version=v, name=f"m{v}", inp_path="", timestamp="", spec={},
            equation="", decision="", rationale="", problems_found="",
            next_version="",
            stats=GuionStats(loglik=1.0, aic=2.0, bic=3.0, sigma_a=0.1,
                             q_pass=True, jb_pass=True, n_extreme=0,
                             refactor=100.0))
    p = str(tmp_path / "g.json")
    save_guion(Guion(series="S", analyst="t", created="2026-09-04", entries=[ent(1), ent(2)]), p)
    fn = getattr(srv.guion_map, "fn", srv.guion_map)
    txt = "\n".join(getattr(c, "text", "") for c in fn(p))
    assert "misma ESCALA" not in txt


# ───────────────── compare_versions ─────────────────

def test_compare_versions_suprime_el_delta_entre_escalas(tmp_path):
    import art.mcp_server as srv
    ts, ma = _base(refactor=_RESCALE_FACTOR)
    _, mb = _base(refactor=1.0)
    fa, fb = str(tmp_path / "a.inp"), str(tmp_path / "b.inp")
    _write_inp(ts, ma, fa, refactor=_RESCALE_FACTOR)
    _write_inp(ts, mb, fb, refactor=1.0)
    fn = getattr(srv.compare_versions, "fn", srv.compare_versions)
    txt = "\n".join(getattr(c, "text", "") for c in fn(fa, fb))
    assert "ESCALAS distintas" in txt
    assert "no comp." in txt


def test_compare_versions_no_lanza_un_LR_entre_escalas(tmp_path):
    """El χ² saldría enorme y con p≈0: un contraste que dice «significativo»
    sobre un cambio de unidades."""
    import art.mcp_server as srv
    ts, ma = _base(refactor=_RESCALE_FACTOR)
    _, mb = _base(refactor=1.0)
    fa, fb = str(tmp_path / "a2.inp"), str(tmp_path / "b2.inp")
    _write_inp(ts, ma, fa, refactor=_RESCALE_FACTOR)
    _write_inp(ts, mb, fb, refactor=1.0)
    fn = getattr(srv.compare_versions, "fn", srv.compare_versions)
    txt = "\n".join(getattr(c, "text", "") for c in fn(fa, fb))
    assert "suprimido" in txt or "χ²" not in txt
