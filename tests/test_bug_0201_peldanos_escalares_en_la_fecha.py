"""BUG-0201 — la escalera juzgaba los peldaños escalares en otra fecha.

Alineada con la configuración (BUG-0156), la escalera ponía los TRES peldaños en
el arranque del mecanismo. Sobre el IVA de 09/2012 del IPC español el mecanismo
arranca en 05/2012, así que el «1a» era un escalón cuatro meses antes del único
extremo —ω=−0.43, AIC 77.44— y `suggest_intervention_form` construía después el
de 09/2012 —ω=+0.88, AIC 69.90—. El aviso de dominio («caída permanente») salía
del ω equivocado.

Ahora los escalares caen en la fecha del suceso (`at_simple`) y el peldaño 2
sigue siendo la configuración, desde su arranque.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art import policy
from art.configuracion import arranques_candidatos, evalua_configuraciones
from art.diagnosis import diagnose
from art.escalera import describe_escalera, escalera_de_ockham
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _caso(tmp):
    """El testigo de BUG-0156: un tramo pequeño y luego uno grande, así que el
    mecanismo arranca un período ANTES que el primer extremo."""
    rng = np.random.default_rng(3)
    n, T = 120, 60
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    y[T:] += -1.0
    y[T + 1:] += -5.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="X")
    f = os.path.join(tmp, "X.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]]), f)
    _, m = estimar(f)
    dg = diagnose(m, z_threshold=3.0)
    ep = policy.decide_episodios(dg.extreme, d=1)[0]
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / (r.std(ddof=0) or 1.0)
    conj = evalua_configuraciones(
        m, arranques_candidatos(z, [o - 1 for o, _ in ep.extremos], d=1),
        d=1, dominio="generic", freq=4, start_year=1995, start_per=1)
    mj = conj.mejor
    at_cfg, at_ep = mj.arranque_resid - 1 + 1, ep.at_0based(1)
    assert at_cfg != at_ep, "el testigo dejó de valer: no hay desplazamiento"
    return m, ep, mj, at_cfg, at_ep


def _at(peldano):
    return [i.at for i in peldano.model.interventions
            if i.type in ("step", "impulse")][-1]


def test_los_escalares_caen_en_el_suceso_y_el_2_en_el_mecanismo(tmp_path):
    m, ep, mj, at_cfg, at_ep = _caso(str(tmp_path))
    esc = escalera_de_ockham(m, ep, dominio="generic", at=at_cfg,
                             n_alto=mj.n_escalones, fecha_arranque=mj.fecha)
    assert _at(esc.por_nivel("1a")) == at_ep
    assert _at(esc.por_nivel("1b")) == at_ep
    assert _at(esc.por_nivel("2")) == at_cfg
    assert esc.at_arranque == at_cfg, "BUG-0156: el 2 es la configuración"


def test_at_simple_manda_sobre_el_episodio(tmp_path):
    m, ep, mj, at_cfg, at_ep = _caso(str(tmp_path))
    esc = escalera_de_ockham(m, ep, dominio="generic", at=at_cfg,
                             n_alto=mj.n_escalones, at_simple=at_ep + 1,
                             fecha_simple="Q3/2010")
    assert _at(esc.por_nivel("1a")) == at_ep + 1
    assert "Q3/2010" in describe_escalera(esc).summary


def test_el_peldano_1a_reproduce_el_modelo_que_se_construye(tmp_path):
    """El AIC y el ω del 1a son los de un escalón ajustado en la fecha del
    suceso sobre el mismo base: lo que la herramienta construye si lo elige."""
    from art.escalera import _clona_con
    m, ep, mj, at_cfg, at_ep = _caso(str(tmp_path))
    esc = escalera_de_ockham(m, ep, dominio="generic", at=at_cfg,
                             n_alto=mj.n_escalones)
    itv = fue.Intervention("step", at=at_ep, omega=[0.0], omega_free=[True])
    ref = _clona_con(m, list(m.interventions or []) + [itv])
    ref.fit()
    p1a = esc.por_nivel("1a")
    assert p1a.aic == pytest.approx(float(ref.aic), abs=1e-6)
    assert p1a.omega[0] == pytest.approx(
        float(ref.interventions[-1].omega[0]), rel=1e-5)


def test_el_informe_dice_las_dos_fechas(tmp_path):
    m, ep, mj, at_cfg, at_ep = _caso(str(tmp_path))
    esc = escalera_de_ockham(m, ep, dominio="generic", at=at_cfg,
                             n_alto=mj.n_escalones, fecha_arranque=mj.fecha)
    txt = describe_escalera(esc).summary
    assert "El peldaño 1 cae en" in txt and mj.fecha in txt


def test_el_instrumento_pasa_la_fecha_pedida_a_la_escalera():
    import pathlib
    src = pathlib.Path("src/art/mcp_server.py").read_text()
    assert "at_simple=at_0" in src
    assert "_al_esc.update(at=at_esc" in src, (
        "alinear con la configuración vuelve a borrar la fecha del suceso")
