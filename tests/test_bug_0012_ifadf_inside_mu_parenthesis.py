"""BUG-0012 — los factores `ifadf` se imprimían FUERA del paréntesis de μ.

La ecuación salía así:

    (1 − 0.4074·B) (1 + B + B²)_f=4 (∇Nₜ − 0.4642) = (1 + B + 0.9678·B²)_f=4 aₜ

Leído literalmente eso es `A_f(B)·(∇Nₜ − μ)`, cuya media es `A_f(1)·(m − μ)`. Con
m = 0.1545 y μ̂ = 0.4642 eso vale 3·(−0.3097) = −0.93 ≠ 0: **la ecuación impresa
no es de media cero, luego no es el modelo que se ajustó.**

El modelo ajustado es `(A_f(B)∇Nₜ − μ)`: μ es la media de la variable
COMPLETAMENTE diferenciada, e `ifadf` es parte de la diferenciación. Su media es
`A_f(1)·m − μ = 0.4635 − 0.4642 ≈ 0`.

La estimación siempre fue correcta — esto era sólo renderizado — pero costó un
informe de bug falso: midiendo el escalado de μ en tres frecuencias se concluyó
que la media se trataba de forma inconsistente entre el factor AR regular y el
estacional. La colocación del paréntesis es lo que invitaba a leer μ como la
media de ∇Nₜ, que es 0.1545, en vez de la de A_f(B)∇Nₜ.

**f=2 no sirve como caso de prueba**: allí A_f(1)=1, así que las dos lecturas
coinciden. Se usan f=3, f=4 y el Nyquist f=6.
"""
import os
import re

import numpy as np
import pytest

_PRE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "bugs", "BUG-0010-repro", "IPC_ES_m10.pre")

pytestmark = pytest.mark.skipif(not os.path.exists(_PRE),
                                reason="falta IPC_ES_m10.pre")

# f -> (ganancia A_f(1), factor tal y como lo escribe el renderizador)
_CASES = {
    3: (2.0, "(1 + B²)_f=3"),
    4: (3.0, "(1 + B + B²)_f=4"),
    6: (2.0, "(1 + B)_f=6"),
}


def _base():
    import fue
    _ts, m = fue.load(_PRE)
    m.fit()
    return _ts, m


def _reformulated(f):
    from art.formal_tests import reformulate_stochastic

    ts, m0 = _base()
    m = reformulate_stochastic(m0, freq=f, s=12)
    m.fit()
    return ts, m


def _equation(ts, m):
    from art.describe import model_equation

    return model_equation(ts, m)


def _noise_line(eq):
    """La línea (2), la del ruido: la que lleva el operador de diferenciación.

    No vale «Nₜ y un igual»: la línea (1) —`ln IPC_ESₜ = Dₜ + Nₜ`, la
    descomposición determinista/ruido— también los lleva.
    """
    for line in eq.splitlines():
        if "∇" in line and "=" in line:
            return line.strip()
    raise AssertionError(f"no hay línea de ruido con ∇ en:\n{eq}")


def _mu_parenthesis(line):
    """El contenido del paréntesis que lleva μ: (... − 0.4642)."""
    m = re.search(r"\(([^()]*(?:\([^()]*\)[^()]*)*[−+]\s*\d+\.\d+)\)", line)
    assert m, f"no se encontró el paréntesis de μ en: {line}"
    return m.group(1)


# ── el defecto ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("f", sorted(_CASES))
def test_the_ifadf_factor_is_inside_the_mu_parenthesis(f):
    _gain, factor = _CASES[f]
    ts, m = _reformulated(f)
    line = _noise_line(_equation(ts, m))

    assert factor in line, f"el factor no aparece: {line}"
    inside = _mu_parenthesis(line)
    assert factor in inside, (
        f"f={f}: el factor ifadf sigue FUERA del paréntesis de μ\n  {line}")
    assert "∇" in inside, "la diferencia regular también va dentro"


@pytest.mark.parametrize("f", sorted(_CASES))
def test_no_differencing_operator_is_left_outside(f):
    """El contraste que atrapa la CLASE entera, no sólo este caso.

    Todo operador de diferenciación tiene que quedar dentro del paréntesis de μ,
    porque μ es la media de lo que queda después de TODOS ellos. Lo que queda
    fuera —los factores AR, regulares o de frecuencia fija— es estacionario y no
    afecta a la media.
    """
    _gain, factor = _CASES[f]
    line = _noise_line(_equation(*_reformulated(f)))
    # OJO: `line.split("=")` corta en el `=` de `_f=4`, no en el de la ecuación,
    # y deja un `lhs` truncado con el que este test pasaba sin arreglar nada.
    eq_pos = re.search(r"\s=\s", line)
    assert eq_pos, f"no se encontró el signo igual de la ecuación en: {line}"
    lhs = line[:eq_pos.start()]
    assert "_f=" not in lhs or lhs.count("(") == lhs.count(")"), lhs
    fuera = lhs.replace(f"({_mu_parenthesis(line)})", "")

    assert "∇" not in fuera, f"quedó una ∇ fuera del paréntesis:\n  {lhs}"
    assert factor not in fuera, f"quedó el ifadf fuera:\n  {lhs}"


# ── el invariante numérico, que es la sustancia ────────────────────────────

@pytest.mark.parametrize("f", sorted(_CASES))
def test_mu_is_the_mean_of_the_fully_differenced_variable(f):
    """μ̂ ≈ A_f(1)·m, y por tanto la ecuación impresa es de media cero.

    Tres ganancias distintas (2, 3, 2) y la deriva implícita μ̂/A_f(1) invariante
    en ≈0.155 — que es la media de ∇ln(IPC)·100. Eso es la definición
    funcionando, no una inconsistencia.
    """
    gain, _factor = _CASES[f]
    ts, m = _reformulated(f)

    y = np.asarray(ts.data, float)
    m_bar = float(np.mean(np.diff(np.log(y)))) * 100.0     # ∇ln·100
    mu_hat = float(m.mu0)

    assert mu_hat == pytest.approx(gain * m_bar, rel=0.05), (
        f"f={f}: μ̂={mu_hat:.4f} no sigue a A_f(1)·m={gain * m_bar:.4f}")
    # media de la expresión impresa: A_f(1)·m − μ ≈ 0
    assert abs(gain * m_bar - mu_hat) < 0.05 * abs(mu_hat)


def test_f2_is_useless_as_a_test_case_and_this_records_why():
    """En f=2 la ganancia es 1, así que las dos lecturas coinciden y el defecto
    es invisible. Se deja escrito para que nadie lo use de fixture."""
    ts, m = _reformulated(2)
    y = np.asarray(ts.data, float)
    m_bar = float(np.mean(np.diff(np.log(y)))) * 100.0
    assert float(m.mu0) == pytest.approx(m_bar, rel=0.05)   # gain = 1


# ── y las rutas que ya eran correctas, como guardia ────────────────────────

def test_the_plain_d_path_is_unchanged():
    """Sin ifadf la ecuación es la de siempre: ∇ dentro, μ dentro, nada más."""
    ts, m = _base()
    line = _noise_line(_equation(ts, m))
    inside = _mu_parenthesis(line)
    assert "∇Nₜ" in inside
    assert "_f=" not in inside, "sin ifadf no debe entrar ningún factor de frecuencia"


def test_a_model_without_mu_still_renders():
    """El camino sin μ comparte la cadena que se ha tocado."""
    ts, m0 = _base()
    from art.formal_tests import reformulate_stochastic

    m = reformulate_stochastic(m0, freq=4, s=12)
    m.estimate_mu = False
    m.mu0 = 0.0
    m.fit()
    line = _noise_line(_equation(ts, m))
    assert "(1 + B + B²)_f=4" in line and "∇Nₜ" in line
