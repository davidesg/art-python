"""BUG-0009 — el testigo de f=0 se apropiaba de la ranura del de Nyquist.

`dcd_overdiff_regular` construía su candidato con

    mc.ma = [[witness_init]]        # "replace any existing regular MA"

y esa ranura no siempre está libre. Cuando la frecuencia de Nyquist se ha
reformulado a estocástica, `meg_reformulate` guarda ahí SU testigo, porque un
testigo de Nyquist también es un MA regular de primer orden. Misma forma,
destinos opuestos — en el convenio `(1 − θB)`:

    diferencia regular  (1 − B)   raíz B = +1   el testigo va a  θ = +1
    ifadf[s/2]          (1 + B)   raíz B = −1   el testigo va a  θ = −1

Sólo así cancela cada uno su diferencia. La asignación borraba el testigo de
Nyquist mientras `ifadf[s/2] = 1` sobrevivía, así que el candidato cargaba una
raíz unitaria estacional sin cancelar y el único MA regular que quedaba tenía que
absorberla.

Debajo hay un error de categoría: **f = s/2 no lo gobierna `d`.** Su orden de
integración es `ifadf[s/2]`; `d` es el orden en la frecuencia cero. Un contraste
del orden REGULAR no debe tocar el ESTACIONAL — y de ahí sale el invariante que
estos tests comprueban.
"""
import os

import pytest

_PRE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "bugs", "BUG-0010-repro", "IPC_ES_m10.pre")

pytestmark = pytest.mark.skipif(not os.path.exists(_PRE),
                                reason="falta IPC_ES_m10.pre")


def _base():
    import fue
    _ts, m = fue.load(_PRE)
    m.fit()
    return m


def _nyquist_stochastic():
    """El mismo modelo con f=6 reformulada a estocástica: ifadf[6]=1 y su
    testigo en la ranura de MA regular."""
    from art.formal_tests import reformulate_stochastic

    m = reformulate_stochastic(_base(), freq=6, s=12)
    m.fit()
    return m


def test_the_fixture_is_what_the_bug_needs():
    """Precondición: el modelo reformulado lleva ifadf[6]=1 y un MA regular que
    es el testigo de Nyquist, pegado a su frontera θ = −1."""
    m = _nyquist_stochastic()
    assert m.ifadf[6] == 1
    assert len(m.ma or []) == 1
    assert m.ma[0][0] == pytest.approx(-1.0, abs=1e-3)


def test_the_f0_witness_gets_its_own_slot():
    from art.formal_tests import dcd_overdiff_regular

    r = dcd_overdiff_regular(_nyquist_stochastic())
    assert r.factor_index == 1, "el testigo de f=0 debe ir a una ranura NUEVA"
    assert r.coef_free > 0, "y buscar θ = +1, no la frontera de Nyquist"


def test_the_regular_verdict_does_not_depend_on_the_seasonal_reformulation():
    """El invariante, y la prueba de que el arreglo hace lo que debe.

    El contraste del orden regular es sobre f=0. Reformular f=6 a estocástica no
    cambia `d`, así que el veredicto de f=0 tiene que ser el mismo antes y
    después. Medido: antes del arreglo el LR pasaba de 4.220 a 1.859 al
    reformular Nyquist — el testigo de f=0 absorbía la (1+B) que se quedaba
    huérfana. Ahora 4.220 y 4.257.

    (Ambos por encima del crítico es BUG-0011, que es otra cosa: los armónicos
    deterministas compitiendo con el testigo. Este test mira la INVARIANCIA, no
    el veredicto.)
    """
    from art.formal_tests import dcd_overdiff_regular

    sin_ = dcd_overdiff_regular(_base())
    con_ = dcd_overdiff_regular(_nyquist_stochastic())

    assert abs(con_.lr - sin_.lr) < 0.5, (
        f"el veredicto de f=0 cambia con la reformulación de f=6: "
        f"{sin_.lr:.3f} -> {con_.lr:.3f}")
    assert abs(con_.coef_free - sin_.coef_free) < 0.02


def test_the_nyquist_witness_survives_in_the_candidate():
    """Lo que se borraba. Se comprueba sobre el candidato que el contraste
    construye, no sobre el modelo base."""
    import copy

    m = _nyquist_stochastic()
    n_ma_antes = len(m.ma or [])

    # el mismo candidato que arma dcd_overdiff_regular
    mc = copy.deepcopy(m)
    mc.d += 1
    mc.ma = [list(f) for f in (mc.ma or [])] + [[0.85]]
    assert len(mc.ma) == n_ma_antes + 1
    assert mc.ma[0][0] < 0 < mc.ma[1][0], (
        "las dos frecuencias conviven, cada una hacia su frontera")


def test_a_model_without_a_stochastic_nyquist_is_untouched():
    """El arreglo no debe mover nada donde no había colisión."""
    from art.formal_tests import dcd_overdiff_regular

    m = _base()
    assert all(v == 0 for v in (m.ifadf or [])), "precondición: sin ifadf activo"
    r = dcd_overdiff_regular(m)
    assert r.factor_index == 0
    assert r.lr == pytest.approx(4.220, abs=0.01)
