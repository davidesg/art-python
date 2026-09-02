"""BUG-0030 — toda intervención autónoma caía d+D·s períodos antes del anómalo.

`diag.extreme` indexa la serie de RESIDUOS, que empieza `d + D*s` observaciones
después de la original. `decide_interventions` convertía con `at_0 = obs - 1`,
que sólo valdría si las dos series arrancaran a la vez.

Y era estructural, no aritmético: la función NO RECIBÍA `d` ni `D`, así que no
podía hacer la conversión aunque quisiera.

Lo que lo hacía silencioso: un pulso de NIVEL un período antes ajusta la imagen
especular del correcto — signo invertido, magnitud igual, verosimilitud
indistinguible. Nada en la diagnosis lo delata.
"""
import os
import tempfile

import numpy as np
import pytest

import fue
from art import mcp_server as A
from art import policy as pol
from art.describe import _resid_start
from art.diagnosis import diagnose
from art.pipeline import _load_ts_model

OBJETIVO = 19          # posición 0-based del anómalo en la serie original


@pytest.fixture(scope="module")
def caso():
    """Serie con UN anómalo en una posición conocida."""
    rng = np.random.default_rng(23)
    a = rng.normal(0, 1.0, 84)
    a[OBJETIVO] = -9.0
    y = 100.0 + np.cumsum(a)
    d = tempfile.mkdtemp(prefix="bug0030-")
    inp = os.path.join(d, "SYN.inp")
    A.create_inp(list(map(float, y)), inp, name="SYN", freq=4,
                 start_year=2004, start_period=1)
    out = os.path.join(d, "SYN_m00.inp")
    A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=1, D=0,
                           p=0, q=0, n_harmonics=0, seasonal=False,
                           estimate_mu=False)
    ts, m = _load_ts_model(out)
    m.fit()
    return ts, m, diagnose(m)


def test_la_deteccion_es_correcta(caso):
    """El defecto no está en encontrar el anómalo: está en traducir su índice."""
    ts, m, dg = caso
    obs, _ = max(dg.extreme, key=lambda t: abs(t[1]))
    y0, p0 = _resid_start(m)
    o = (p0 - 1) + (obs - 1)
    assert (y0 + o // 4, o % 4 + 1) == (2008, 4)     # la fecha del anómalo


def test_sin_el_desfase_cae_un_periodo_antes(caso):
    _, _, dg = caso
    assert pol.decide_interventions(dg.extreme, [])[0][0] == OBJETIVO - 1


def test_con_el_desfase_cae_en_su_fecha(caso):
    ts, m, dg = caso
    off = int(m.d) + int(m.D) * ts.freq
    assert pol.decide_interventions(dg.extreme, [], offset=off)[0][0] == OBJETIVO


def test_el_pipeline_pasa_el_desfase(monkeypatch, caso):
    """El arreglo no sirve si el llamador no lo usa.

    Antes esto comparaba el TEXTO FUENTE de `pipeline.py` contra la expresión
    literal del desfase. Se rompió sin que nada estuviera mal el día que el
    bucle de anómalos se extrajo a `_outlier_loop` para poder recorrerlo una vez
    por ruta estacional, y el desfase pasó a leerse de `spec_base.d`/`.D`. Un
    test que fija cómo está ESCRITO el código, y no lo que hace, denuncia
    refactorizaciones correctas y calla ante errores reales.

    Ahora se intercepta la llamada y se comprueba el ARGUMENTO: que el offset
    que recibe `decide_interventions` sea `d + D·s` de la especificación que se
    está estimando. En una rama B2, con D=1, eso son `d + s` — y leerlo de la
    especificación es lo que hace que cada rama use SU propio desfase.
    """
    import art.pipeline as P

    ts, _m, _dg = caso
    vistos = []
    original = pol.DefaultPolicy.decide_interventions

    # F4 añadió `d` a la firma: la posición necesita el desfase `d + D·s` y la
    # DURACIÓN del episodio necesita `d` — son las DOS conversiones entre el
    # espacio de residuos y el del nivel, y las dos tienen que llegar aquí.
    def espia(self, extreme, existing_ats, offset=0, d=0):
        vistos.append((offset, d))
        return original(self, extreme, existing_ats, offset, d)

    monkeypatch.setattr(pol.DefaultPolicy, "decide_interventions", espia)

    d = tempfile.mkdtemp(prefix="bug0030-off-")
    res = P.run_full(ts, os.path.join(d, "SYN.inp"),
                     decision_policy=pol.DefaultPolicy())

    assert vistos, "el bucle no llegó a pedir intervenciones"
    assert all(dd == vistos[0][1] for _, dd in vistos), \
        "la diferenciación tiene que llegar igual en todas las rondas"
    esperado = int(res.d) + int(res.D) * int(ts.freq)
    assert all(o == esperado for o, _ in vistos), (
        f"el llamador no pasa el desfase correcto: esperaba {esperado}, "
        f"vistos {vistos}")
    assert esperado >= 1, "un modelo con d>=1 tiene desfase, no cero"


def test_el_carril_autonomo_coloca_la_intervencion_en_su_fecha(caso):
    """De punta a punta: build_model debe intervenir donde está el anómalo."""
    ts, _, _ = caso
    d = tempfile.mkdtemp(prefix="bug0030-auto-")
    inp = os.path.join(d, "SYN.inp")
    A.create_inp([float(v) for v in ts.data], inp, name="SYN", freq=4,
                 start_year=2004, start_period=1)
    A.build_model(inp_path=inp, output_path=os.path.join(d, "SYN_auto.inp"),
                  run_meg=False)
    _, m = _load_ts_model(os.path.join(d, "SYN_auto.inp"))
    ats = [i.at for i in (m.interventions or [])
           if i.type in ("impulse", "step", "ramp", "compimp")]
    if not ats:
        pytest.skip("el autónomo no añadió intervenciones en esta corrida")
    assert OBJETIVO in ats


def test_por_que_era_silencioso(caso):
    """Un período antes ajusta la imagen especular: signo invertido, magnitud
    casi igual, verosimilitud indistinguible."""
    ts, _, _ = caso
    def fit(a0):
        m = fue.Model(ts, d=1, ifadf=[0, 0, 0], mu=0.0, estimate_mu=False,
                      interventions=[fue.Intervention("impulse", at=a0,
                                                      omega=[0.0], omega_free=[True])])
        m.fit()
        return m.interventions[0].omega[0], m._result.loglik

    w_mal, ll_mal = fit(OBJETIVO - 1)
    w_bien, ll_bien = fit(OBJETIVO)
    assert w_mal * w_bien < 0                              # signos opuestos
    assert abs(abs(w_mal) - abs(w_bien)) < 0.05 * abs(w_bien)   # misma magnitud
    assert abs(ll_mal - ll_bien) < 1.0                     # y el ajuste no distingue
