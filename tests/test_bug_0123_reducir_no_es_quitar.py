"""BUG-0123 — quitar no es la única simplificación.

`simplify_interventions` conocía UN solo tipo: quitar una intervención no
significativa. Cuando todas lo eran cerraba con

    *Todas las intervenciones son significativas — no hay simplificación posible.*

y eso es **falso** siempre que un ESCALÓN con dos o más ω tenga la ganancia nula
sin rechazar. Ahí no hay que quitar nada: hay que **reducir**.

Y la fórmula estaba escrita en el propio módulo, en el comentario del campo
`entrada`: *«elegir input impulso ES imponer la restricción de ganancia nula»*.
Es álgebra elemental — si ω(1)=0 entonces (1−B) divide a ω(B), o sea
ω(B) = (1−B)·ψ(B), y como I_t = (1−B)S_t:

    ω(B)·S_t = ψ(B)·(1−B)·S_t = ψ(B)·I_t

El programa CALCULABA el contraste —lo imprimía tres líneas más arriba, con su
Wald y su veredicto TRANSITORIO— y después declaraba que no había nada que hacer
con él. El conocimiento estaba en un comentario y no llegaba a ser
comportamiento. Es la enfermedad recurrente en una variante nueva: no un
concepto escrito dos veces con una copia atrasada, sino un concepto escrito UNA
vez y sólo en prosa, que nunca se conectó con la función que tenía que usarlo.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.interventions import (InterventionTestResult, simplify_interventions,
                               simplify_summary)
from art.interventions import test_intervention as _test_intervention
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

_T = 70


def _res(entrada="escalon", n=3, wald_p=0.98, itv_type="step"):
    """Un resultado fabricado: lo que hace falta para decidir, y nada más."""
    return InterventionTestResult(
        itv_index=0, itv_type=itv_type, itv_at=_T, harmonic=None,
        omega=[0.0] * n, omega_se=[1.0] * n, omega_t=[9.0] * n,
        omega_p=[0.0] * n,
        # los dos van juntos o no van: `test_intervention` nunca produce un
        # estadístico sin su p
        wald_stat=(0.001 if wald_p is not None else None), wald_p=wald_p, df=100,
        significant=True, entrada=entrada, n_omega_total=n, omega_1=0.01)


# ── la condición vive en el RESULTADO, no en el formateador ────────────────

def test_un_escalon_con_ganancia_nula_ES_reducible():
    r = _res()
    assert r.es_reducible() is True
    assert r.forma_reducida == ("impulse", 2)


@pytest.mark.parametrize("caso,kw", [
    ("un solo ω: no hay orden que bajar",  dict(n=1)),
    ("la ganancia SE rechaza",             dict(wald_p=0.001)),
    ("ya es impulso: la restricción está", dict(entrada="impulso",
                                                itv_type="impulse")),
    ("sin Wald no hay contraste",          dict(wald_p=None)),
])
def test_lo_que_NO_es_reducible(caso, kw):
    assert _res(**kw).es_reducible() is False, caso


def test_el_alfa_manda():
    r = _res(wald_p=0.03)
    assert r.es_reducible(alpha=0.05) is False
    assert r.es_reducible(alpha=0.01) is True


def test_la_condicion_se_PREGUNTA_no_se_deduce_otra_vez():
    """Vive en el resultado a propósito: un sitio que presente esto tiene que
    poder preguntarlo, no volver a deducir la regla. Es lo que falló — la regla
    estaba en un comentario y el formateador no la conocía."""
    from tests._fuente import fuente_de
    src = fuente_de(simplify_summary)
    assert "es_reducible(" in src
    assert 'entrada == "escalon"' not in src, "el formateador vuelve a deducirla"


# ── el resumen ─────────────────────────────────────────────────────────────

def test_ya_no_dice_que_no_hay_simplificacion_posible():
    txt = simplify_summary([_res()])
    assert "no hay simplificación posible" not in txt
    assert "Reducibles" in txt


def test_dice_la_forma_equivalente_y_la_llamada_que_la_construye():
    txt = simplify_summary([_res()])
    assert "`impulse` con 2 ω" in txt
    assert "form=\"impulse\", n_omega=2" in txt
    assert "LR de 1 g.l." in txt


def test_cuando_de_verdad_no_hay_nada_lo_sigue_diciendo():
    txt = simplify_summary([_res(wald_p=0.001)])
    assert "no hay simplificación posible" in txt
    assert "Reducibles" not in txt


def test_quitar_y_reducir_pueden_salir_las_dos():
    """No son excluyentes: una intervención puede sobrar y otra reducirse."""
    sobra = _res(n=1, wald_p=None)
    sobra.significant = False
    txt = simplify_summary([sobra, _res()])
    assert "considerar eliminar" in txt and "Reducibles" in txt


def test_el_impulso_dice_que_la_restriccion_esta_IMPUESTA_y_como_contrastarla():
    """La ida del mismo camino. Y con cuidado: el informe proponía avisar
    cuando un impulso tuviera la ganancia RECHAZADA, y eso está mal — el Wald de
    un impulso mira si el ÁREA es nula, que es otra pregunta (BUG-0076). Desde
    el impulso la restricción no se puede contrastar; lo que se puede es decir
    cómo se contrasta."""
    txt = simplify_summary([_res(entrada="impulso", itv_type="impulse", n=2)])
    assert "impuesta por construcción" in txt
    assert "escalón con un ω más" in txt
    assert "LR de 1 g.l." in txt
    # y NO afirma que la restricción falle
    assert "no se sostiene" not in txt


# ── y que el álgebra sea cierta, no sólo el texto ──────────────────────────

@pytest.fixture(scope="module")
def dos_formas(tmp_path_factory):
    """El mismo suceso transitorio, en las dos parametrizaciones."""
    d = tmp_path_factory.mktemp("red")
    rng = np.random.default_rng(8)
    n, phi = 160, 0.5
    a = rng.standard_normal(n) * 0.5
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = phi * e[t - 1] + a[t]
    y = 100.0 + np.cumsum(e)
    y[_T] += -6.0
    y[_T + 1] += -3.0                  # sube y VUELVE: el nivel acaba igual
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1985, 1), name="TR")

    def monta(tipo, k, nom):
        f = str(d / f"{nom}.inp")
        _write_inp(ts, fue.Model(
            ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR,
            ar=[[0.0]], ar_free=[[True]],
            interventions=[fue.Intervention(tipo, at=_T, omega=[0.0] * k,
                                            omega_free=[True] * k)]), f)
        return estimar(f)[1]

    return monta("step", 3, "ESC"), monta("impulse", 2, "IMP")


def test_las_dos_formas_son_EL_MISMO_MODELO_con_y_sin_la_restriccion(dos_formas):
    """Lo que convierte esto en una simplificación y no en una opinión: la
    verosimilitud no se mueve, y el LR de la restricción es de 1 g.l."""
    esc, imp = dos_formas
    lr = 2 * (esc._result.loglik - imp._result.loglik)
    assert lr >= -1e-6, "el restringido no puede ajustar MEJOR"
    assert lr < 0.5, f"LR={lr:.4f}: la restricción no debería costar nada aquí"
    assert imp._result.npar == esc._result.npar - 1


def test_y_la_reduccion_devuelve_exactamente_dos_puntos_de_AIC(dos_formas):
    """Un parámetro menos con la misma ℓ es ΔAIC = −2 por definición. Que salga
    el número exacto es la prueba de que la equivalencia es algebraica y no una
    coincidencia del ajuste."""
    esc, imp = dos_formas
    assert abs((imp.aic - esc.aic) + 2.0) < 0.05


def test_sobre_el_modelo_REAL_se_propone(dos_formas):
    esc, _ = dos_formas
    tr = _test_intervention(esc, 0)
    assert tr.wald_p > 0.05, "el testigo dejó de valer: la ganancia se rechaza"
    assert tr.es_reducible() is True
    assert tr.n_omega_total == 3

    txt = simplify_summary(simplify_interventions(esc))
    assert "Reducibles" in txt
    assert "no hay simplificación posible" not in txt
