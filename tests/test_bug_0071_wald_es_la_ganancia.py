"""BUG-0071/0072/0073 — el Wald conjunto sobre ω.

Tres defectos en la misma región de `test_intervention`:

  0071  α = (1, −δ₁, −δ₂, …) mete los coeficientes del DENOMINADOR en un
        contraste sobre el NUMERADOR. No es ω(1), no es la ganancia ν(1), y no
        es ninguna cantidad reconocible. El correcto es α = (1, −1, …, −1),
        porque fue guarda ω(B) = ω₀ − ω₁B − ⋯ − ω_sB^s.
  0072  la guarda `any(f for f in dlf)` sólo dejaba correr el contraste si
        había δ libres — justo al revés de lo que hace falta: el caso del nodo
        de episodios son N escalones en el nivel SIN denominador.
  0073  `summary()` rotulaba χ²(k) mientras el cálculo usaba df=1.

El de fondo es 0071: con δ₁=0,5 y ω=(0,80, −0,30) el contraste viejo devolvía
0,95 donde ω(1) vale 1,10 y la ganancia 2,20.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.interventions import test_intervention as contrasta


def _serie_con_efecto(nivel, T=120, n=240, semilla=0):
    """Ruido blanco más un efecto en el NIVEL dado por `nivel` desde T."""
    rng = np.random.default_rng(semilla)
    y = rng.standard_normal(n)
    for k, v in enumerate(nivel):
        if T + k < n:
            y[T + k] += v
    return fue.TimeSeries(y.tolist(), freq=1, start=(1, 1), name="sint")


def _ajusta_escalon_s2(ts, T=120):
    """Tres escalones en el nivel: ω(B) de orden 2 sobre un escalón.

    La respuesta es ω₀ en T, ω₀−ω₁ en T+1, y ω(1)=ω₀−ω₁−ω₂ de T+2 en
    adelante. ω(1)=0 ⟺ el nivel vuelve a la base ⟺ episodio TRANSITORIO de
    dos períodos.
    """
    m = fue.Model(ts, d=0, mu=0.0, estimate_mu=False,
                  interventions=[fue.Intervention(
                      "step", at=T, omega=[0.0, 0.0, 0.0],
                      omega_free=[True, True, True])])
    m.fit()
    return m


# ───────────────────────── BUG-0071 ─────────────────────────

def test_el_contraste_es_omega_de_uno_y_no_la_mezcla_con_delta():
    """ω(1) = ω₀ − ω₁ − ω₂, con los signos de la convención de fue."""
    ts = _serie_con_efecto([6.0, 4.0, 0.0])       # dos impulsos: transitorio
    m = _ajusta_escalon_s2(ts)
    r = contrasta(m, 0)

    w = r.omega
    assert len(w) == 3
    esperado = w[0] - w[1] - w[2]
    assert r.omega_1 == pytest.approx(esperado, abs=1e-12)

    # y NO es lo que devolvía el contraste viejo, α = (1, −δ₁, …).
    # Sin δ el viejo ni siquiera corría; con δ habría dado otra cosa. Aquí se
    # fija lo esencial: ω(1) resta TODOS los retardos ≥ 1.
    suma_ingenua = sum(w)
    assert r.omega_1 != pytest.approx(suma_ingenua, abs=1e-6)


def test_la_ganancia_es_omega_uno_partido_delta_uno():
    ts = _serie_con_efecto([6.0, 4.0, 0.0])
    m = _ajusta_escalon_s2(ts)
    r = contrasta(m, 0)
    # sin denominador, δ(1) = 1 y la ganancia coincide con el numerador
    assert r.gain == pytest.approx(r.omega_1, abs=1e-12)


# ───────────────────────── BUG-0072 ─────────────────────────

def test_el_contraste_corre_sin_denominador():
    """El caso del nodo de episodios —N escalones, sin δ— tiene contraste.

    Con la guarda vieja `any(f for f in dlf)` esto era None sin excepción.
    """
    ts = _serie_con_efecto([6.0, 4.0, 0.0])
    m = _ajusta_escalon_s2(ts)
    r = contrasta(m, 0)
    assert not m.interventions[0].delta, "el caso debe ser SIN denominador"
    assert r.wald_stat is not None
    assert r.wald_p is not None
    assert 0.0 <= r.wald_p <= 1.0


# ───────────────────────── BUG-0073 ─────────────────────────

def test_el_rotulo_dice_chi_cuadrado_de_uno():
    ts = _serie_con_efecto([6.0, 4.0, 0.0])
    m = _ajusta_escalon_s2(ts)
    txt = contrasta(m, 0).summary()
    assert "χ²(1)" in txt
    assert "χ²(3)" not in txt, "es UNA restricción lineal, no k"


# ────────────── lo que el nodo va a apoyar en esto ──────────────

@pytest.mark.parametrize("nivel,permanente", [
    ([6.0, 4.0, 0.0], False),          # dos impulsos en el nivel → transitorio
    ([6.0] * 120, True),               # escalón HASTA EL FINAL   → permanente
])
def test_distingue_transitorio_de_permanente(nivel, permanente):
    """La premisa del nodo de episodios, medida como tasa.

    Un único sorteo de un estadístico no decide nada: se mide sobre varias
    realizaciones y se exige una tasa, que es la lección que ya costó una
    prueba inestable en esta misma suite.
    """
    rechazos = 0
    REPS = 15
    for s in range(REPS):
        ts = _serie_con_efecto(nivel, semilla=s)
        r = contrasta(_ajusta_escalon_s2(ts), 0)
        if r.wald_p is not None and r.wald_p < 0.05:
            rechazos += 1
    tasa = rechazos / REPS
    if permanente:
        assert tasa >= 0.80, f"potencia insuficiente: {tasa:.2f}"
    else:
        assert tasa <= 0.20, f"tamaño desbordado: {tasa:.2f}"
