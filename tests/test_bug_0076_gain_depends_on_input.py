"""BUG-0076 — la lectura de la ganancia depende del TIPO DE ENTRADA.

  escalón   ν(1) es el DESPLAZAMIENTO PERMANENTE del nivel
  impulso   ν(1) es el ÁREA acumulada, y el efecto permanente es CERO por
            construcción: la entrada no persiste

BUG-0071 introdujo la lectura correcta para el caso que tenía delante —N
escalones en el nivel— y la generalizó sin condicionar a la entrada. Sobre una
FLT con input impulso la herramienta declaraba «efecto permanente» un modelo
cuyo efecto permanente es estructuralmente nulo.

Y de ahí la consecuencia de diseño: **elegir input impulso ES imponer ω(1)=0**.
Escalón con s+1 coeficientes e impulso con s son el mismo modelo con y sin esa
restricción, y compararlos es un LR de un grado de libertad.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.interventions import test_intervention as contrasta
from art.ltf import respuesta_flt


T, N = 40, 160


def _serie(semilla=5):
    rng = np.random.default_rng(semilla)
    y = np.cumsum(rng.standard_normal(N))
    y[T] += 3.0; y[T+1] += 5.0; y[T+2] += 2.0      # episodio de tres períodos
    return fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="S")


def _ajusta(tipo, n_om):
    ts = _serie()
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                  interventions=[fue.Intervention(tipo, at=T, omega=[0.0]*n_om,
                                                  omega_free=[True]*n_om)],
                  ar=[[0.1]], ar_free=[[True]])
    m.fit()
    return m


# ───────── la entrada se detecta y gobierna la lectura ─────────

@pytest.mark.parametrize("tipo,esperado", [
    ("impulse", "impulso"), ("pulse", "impulso"),
    ("step", "escalon"), ("ramp", "rampa"),
])
def test_la_entrada_se_deriva_del_tipo(tipo, esperado):
    r = contrasta(_ajusta(tipo, 2), 0)
    assert r.entrada == esperado


def test_con_impulso_el_efecto_permanente_es_cero_EXACTO():
    """No estimado: por construcción. La entrada no persiste."""
    r = contrasta(_ajusta("impulse", 3), 0)
    assert r.efecto_permanente == 0.0
    assert r.omega_1 != 0.0, "y sin embargo ω(1) NO es cero: es el área"


def test_con_escalon_el_efecto_permanente_ES_la_ganancia():
    r = contrasta(_ajusta("step", 3), 0)
    assert r.efecto_permanente == r.gain


def test_el_area_de_la_respuesta_al_impulso_es_omega_de_uno():
    """Comprobación de que ω(1) con impulso es lo que la etiqueta dice."""
    m = _ajusta("impulse", 3)
    r = contrasta(m, 0)
    w = [float(v) for v in m.interventions[0].omega]
    assert respuesta_flt(w, K=60).nu.sum() == pytest.approx(r.omega_1, abs=1e-8)


def test_y_la_respuesta_al_impulso_VUELVE_a_cero():
    m = _ajusta("impulse", 3)
    w = [float(v) for v in m.interventions[0].omega]
    assert abs(respuesta_flt(w, K=60).nu[-1]) < 1e-12


# ───────── lo que la presentación puede y no puede decir ─────────

def test_con_impulso_NO_se_emite_el_veredicto_de_permanencia():
    r = contrasta(_ajusta("impulse", 3), 0)
    assert r.contrasta_permanencia is False
    txt = r.summary()
    assert "0 por construcción" in txt
    assert "NO la permanencia" in txt
    assert "efecto permanente" not in txt.replace(
        "efecto permanente en el nivel: **0 por construcción**", "")


def test_con_escalon_SI_se_emite():
    r = contrasta(_ajusta("step", 3), 0)
    assert r.contrasta_permanencia is True
    assert "TRANSITORIO" in r.summary()


def test_la_etiqueta_nombra_lo_que_el_numero_ES():
    assert contrasta(_ajusta("impulse", 3), 0).lectura_de_ganancia \
        == "área acumulada de la respuesta"
    assert contrasta(_ajusta("step", 3), 0).lectura_de_ganancia \
        == "desplazamiento permanente del nivel"


# ───────── la consecuencia de diseño ─────────

def test_impulso_con_s_coeficientes_es_escalon_con_s_mas_1_restringido():
    """Elegir input impulso ES imponer ω(1)=0, así que los dos modelos están
    ANIDADOS y la comparación es un LR de un grado de libertad."""
    from scipy import stats
    m_imp = _ajusta("impulse", 3)     # restringido: ganancia nula por entrada
    m_esc = _ajusta("step", 4)        # sin restringir: ganancia libre
    assert m_esc._result.npar == m_imp._result.npar + 1
    LR = 2 * (m_esc._result.loglik - m_imp._result.loglik)
    assert LR > -1e-6, "el sin restringir no puede ajustar peor"
    p = float(stats.chi2.sf(max(LR, 0.0), df=1))
    assert 0.0 <= p <= 1.0
