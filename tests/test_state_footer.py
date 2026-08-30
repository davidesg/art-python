"""El pie de estado: dónde estamos, qué falta, qué puertas hay.

Ver docs/ARCHITECTURE_REVIEW.md §5.2. Es un PIE y no una herramienta a propósito:
una herramienta hay que descubrirla y acordarse de llamarla; un pie aparece se
pregunte o no. Y es corto a propósito: documentar no debe engordar cada salida.

La línea que más trabajo hace es `etapa`. Los contrastes formales derivan sus
nulas suponiendo residuos de ruido blanco, así que son la ÚLTIMA etapa: mientras
la diagnosis falle NO son una puerta. Avisar después no basta (BUG-0025) — hay
que no invitar antes.
"""
import os
import tempfile

import numpy as np
import pytest

from art import mcp_server as A


def _estima(d, nombre, y, **kw):
    inp = os.path.join(d, "S.inp")
    if not os.path.exists(inp):
        A.create_inp(list(map(float, y)), inp, name="S", freq=4,
                     start_year=2004, start_period=1)
    base = dict(lam=1.0, d=1, D=0, p=0, q=0, n_harmonics=0,
                seasonal=False, estimate_mu=False)
    base.update(kw)
    out = A.confirm_and_estimate(inp_path=inp,
                                 output_path=os.path.join(d, f"S_{nombre}.inp"),
                                 guion_name=nombre, **base)
    return "\n".join(c.text for c in out if hasattr(c, "text"))


def _pie(txt):
    i = txt.find("── Estado ──")
    return txt[i:] if i >= 0 else ""


@pytest.fixture(scope="module")
def sucio():
    """Paseo aleatorio con un anómalo enorme: la diagnosis falla."""
    d = tempfile.mkdtemp(prefix="pie-sucio-")
    rng = np.random.default_rng(12)
    a = rng.normal(0, 1.0, 90); a[50] = 9.0
    return _pie(_estima(d, "m00", 100.0 + np.cumsum(a)))


@pytest.fixture(scope="module")
def limpio():
    d = tempfile.mkdtemp(prefix="pie-limpio-")
    rng = np.random.default_rng(7)
    return _pie(_estima(d, "m00", 100.0 + np.cumsum(rng.normal(0, 1.0, 90))))


def test_el_pie_aparece_sin_pedirlo(limpio, sucio):
    assert limpio and sucio


def test_el_pie_es_corto(limpio, sucio):
    """Cinco líneas. Si crece, deja de ser gratis y empieza a costar en cada
    llamada."""
    for pie in (limpio, sucio):
        assert len([l for l in pie.strip().splitlines() if l.strip()]) <= 6


def test_dice_lo_decidido(limpio):
    assert "decidido:" in limpio and "d=1" in limpio


def test_con_diagnosis_sucia_NO_ofrece_contrastes_formales(sucio):
    """El invariante central: no invitar a la etapa equivocada."""
    assert "formal_tests" not in sucio
    assert "los contrastes formales van DESPUÉS" in sucio
    assert "diagnosis / reformulación" in sucio


def test_con_diagnosis_sucia_ofrece_la_puerta_util(sucio):
    assert "suggest_intervention_form" in sucio
    assert "anómalo" in sucio           # y dice cuál falta


def test_con_diagnosis_limpia_SI_ofrece_contrastes_formales(limpio):
    assert "formal_tests" in limpio
    assert "← sobre" in limpio          # la ruta, una sola vez
    assert "la diagnosis está limpia, es su etapa" in limpio
    assert "nada — diagnosis limpia" in limpio


def test_siempre_ofrece_el_registro_del_paso(limpio, sucio):
    """El `.out` es la evidencia que hace SÓLIDO un paso, y era inalcanzable
    (BUG-0029)."""
    for pie in (limpio, sucio):
        assert "get_out_report" in pie


def test_cuenta_coeficientes_LIBRES_no_presentes():
    """fue guarda factores con ceros fijos que no son parámetros: contarlos
    haría decir ARMA(1,0) a un modelo con p=q=0."""
    d = tempfile.mkdtemp(prefix="pie-orden-")
    rng = np.random.default_rng(7)
    y = 100.0 + np.cumsum(rng.normal(0, 1.0, 90))
    assert "ARMA" not in _pie(_estima(d, "m00", y, p=0, q=0))
    assert "ARMA(1,0)" in _pie(_estima(d, "m10", y, p=1, q=0))


def test_el_pie_nombra_la_version_y_su_padre():
    d = tempfile.mkdtemp(prefix="pie-padre-")
    rng = np.random.default_rng(7)
    y = 100.0 + np.cumsum(rng.normal(0, 1.0, 90))
    _estima(d, "m00", y)
    pie = _pie(_estima(d, "m10", y, p=1))
    assert "m10 v2" in pie and "← v1" in pie


def test_el_pie_nunca_tumba_una_salida_valida():
    """Un modelo que no se puede diagnosticar debe devolver pie vacío, no error."""
    assert A._state_footer(object(), inp_path="/x/y.inp") == ""
