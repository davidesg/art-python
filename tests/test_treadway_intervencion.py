"""La regla de Treadway: ¿funcionó la intervención?

Dos reglas de la escuela:

  1. Si intervienes en una fecha, NO puedes tener un anómalo de vecino, ni
     antes ni después. Es evidencia de que la REPRESENTACIÓN es errónea.
  2. Que haya funcionado se ve en que los residuos EN LAS FECHAS de
     intervención están en la media, que es cero.

Las dos salen de la misma condición de primer orden —los residuos quedan
ortogonales a los regresores filtrados de la intervención— y estas pruebas la
verifican empíricamente, no sólo la citan. Ver la derivación en
`src/art/interventions.py`.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.interventions import check_intervention_fit


T = 60                       # 0-based: el suceso arranca aquí
N = 200


def _serie(nivel, semilla=11):
    """Ruido blanco con un efecto en el NIVEL desde T."""
    y = np.random.default_rng(semilla).standard_normal(N)
    for k, v in enumerate(nivel):
        y[T + k] += v
    return fue.TimeSeries(y.tolist(), freq=1, start=(1, 1), name="sint")


def _ajusta(ts, at, n_omega, tipo=None):
    """`impulse` para un solo ω (una espiga); `step` con varios, que es la forma
    general del episodio —N escalones en el nivel—. Un `step` con UN solo ω es
    un escalón permanente y no absorbe una espiga: lo comprobamos."""
    tipo = tipo or ("impulse" if n_omega == 1 else "step")
    m = fue.Model(ts, d=0, mu=0.0, estimate_mu=False,
                  interventions=[fue.Intervention(
                      tipo, at=at, omega=[0.0] * n_omega,
                      omega_free=[True] * n_omega)])
    m.fit()
    return m


# ────────── regla 2, y la matemática detrás ──────────

def test_sin_arma_el_residuo_CRUDO_en_la_fecha_es_cero_exacto():
    """La condición de primer orden con π(B)=1 da a_T = 0 exactamente.

    Un ω libre en una fecha absorbe esa observación entera, igual que una
    variable ficticia en regresión. Es el caso donde la regla de la escuela no
    es aproximada sino exacta.
    """
    ts = _serie([8.0])
    chk, = check_intervention_fit(_ajusta(ts, T, 1))
    assert abs(chk.residuo_en_fechas[0]) < 1e-6, "absorción exacta"
    assert chk.absorbido


def test_el_tipificado_se_queda_EN_LA_MEDIA_no_en_cero():
    """El enunciado de la escuela es literal y más preciso que «es cero».

    a_T = 0 exacto ⇒ z_T = (0 − media)/sd = −media/sd. Con μ fijado en 0 la
    media muestral de los residuos no es exactamente cero, así que el
    tipificado tampoco — se queda EN LA MEDIA de los residuos, que es como lo
    dice la escuela. Si μ se estima, la media es ~0 y ambas cosas coinciden.
    """
    ts = _serie([8.0])
    m = _ajusta(ts, T, 1)
    chk, = check_intervention_fit(m)
    res = np.asarray(m._result.residuals, dtype=float)
    esperado = (0.0 - res.mean()) / res.std(ddof=0)
    assert chk.z_en_fechas[0] == pytest.approx(esperado, abs=1e-6)


def test_un_escalon_de_un_solo_omega_NO_absorbe_una_espiga():
    """Comprobación de que la forma importa: `step` con un ω es un cambio de
    nivel permanente, y sobre una espiga de un período no absorbe nada."""
    ts = _serie([8.0])
    chk, = check_intervention_fit(_ajusta(ts, T, 1, tipo="step"))
    assert not chk.absorbido
    assert abs(chk.z_en_fechas[0]) > 3.0


def test_con_arma_el_residuo_esta_en_la_media_pero_no_es_cero():
    """Con π(B) ≠ 1, a_T = −Σ π_k a_{T+k}: pequeño, no nulo.

    Por eso la regla se enuncia «están en la media» y no «son cero»."""
    ts = _serie([8.0])
    m = fue.Model(ts, d=0, ar=[[0.5]], ar_free=[[True]], mu=0.0, estimate_mu=False,
                  interventions=[fue.Intervention("impulse", at=T, omega=[0.0],
                                                  omega_free=[True])])
    m.fit()
    chk, = check_intervention_fit(m)
    assert chk.absorbido, "en la media"
    # con filtro ya NO es cero exacto: a_T = −Σ π_k a_{T+k}
    assert abs(chk.residuo_en_fechas[0]) > 1e-6


# ────────── regla 1: el vecino anómalo delata la representación ──────────

def test_un_impulso_sobre_un_episodio_de_dos_deja_vecino_anomalo():
    """El ω absorbe T; la parte de T+1 no tiene dónde ir y cae en a_{T+1}.

    El vecino anómalo ES la parte no modelizada del mismo suceso.
    """
    ts = _serie([9.0, 6.0])
    chk, = check_intervention_fit(_ajusta(ts, T, 1))
    assert chk.absorbido, "la fecha intervenida sí queda absorbida"
    assert chk.vecino_anomalo == "después"
    assert not chk.funciona
    assert abs(chk.z_despues) > 3.0


def test_la_forma_correcta_no_deja_vecino():
    """Tres escalones en el nivel cubren el episodio de dos: nada al lado."""
    ts = _serie([9.0, 6.0])
    chk, = check_intervention_fit(_ajusta(ts, T, 3))
    assert chk.funciona
    assert chk.vecino_anomalo is None
    assert chk.absorbido


def test_la_fecha_desplazada_tambien_deja_vecino():
    """Intervenir en T−1 cuando el suceso está en T: el ω absorbe la fecha
    equivocada y queda el residuo grande al lado. Es BUG-0030 visto desde la
    diagnosis — y allí la verosimilitud casi no lo distinguía (Δ logL = 0,03),
    así que este contraste ve lo que el ajuste no."""
    ts = _serie([9.0])
    chk, = check_intervention_fit(_ajusta(ts, T - 1, 1))
    assert chk.vecino_anomalo == "después"
    assert not chk.funciona


def test_el_diagnostico_dice_las_dos_lecturas():
    ts = _serie([9.0, 6.0])
    txt = check_intervention_fit(_ajusta(ts, T, 1))[0].summary()
    assert "representación es errónea" in txt
    assert "FORMA" in txt and "FECHA" in txt


# ────────── bordes ──────────

def test_los_armonicos_no_son_sucesos_y_no_se_revisan():
    ts = _serie([9.0])
    m = fue.Model(ts, d=0, mu=0.0, estimate_mu=False,
                  interventions=[fue.Intervention("cos", harmonic=1.0,
                                                  omega=[0.1])])
    m.fit()
    assert check_intervention_fit(m) == []


def test_sin_intervenciones_no_hay_nada_que_revisar():
    ts = _serie([])
    m = fue.Model(ts, d=0, mu=0.0, estimate_mu=False)
    m.fit()
    assert check_intervention_fit(m) == []


def test_un_suceso_al_final_no_tiene_vecino_por_la_derecha():
    ts = _serie([7.0])
    m = fue.Model(ts, d=0, mu=0.0, estimate_mu=False,
                  interventions=[fue.Intervention("step", at=N - 1,
                                                  omega=[0.0],
                                                  omega_free=[True])])
    m.fit()
    chk, = check_intervention_fit(m)
    assert chk.z_despues is None
    assert chk.z_antes is not None
