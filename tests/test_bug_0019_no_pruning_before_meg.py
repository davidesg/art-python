"""No se prescribe podar armónicos antes del MEG. Ni antes ni después de estimar.

`bugs/BUG-0019`. El punto metodológico es de BUG-0010 y la regla es de Treadway:
**el MEG va antes de podar armónicos estacionales**, y es un ORDEN, no una
preferencia. La razón por la que no admite excepción:

* el modelo nulo del MEG en la frecuencia f **es** el armónico determinista en
  f. Si se poda, esa frecuencia deja de ser una pregunta;
* un |t| bajo en f es evidencia **a favor** de estacionalidad estocástica en f
  —amplitud que vaga y promedia hacia cero—, que es justo lo que el MEG decide;
* y la regla general de contrastar sobre un modelo parsimonioso **no alcanza a
  los parámetros que SON la hipótesis bajo contraste**.

BUG-0010 puso el aviso en tres sitios —la nota de sobreparametrización, dos
docstrings y las instrucciones— y los tres están aguas abajo. BUG-0019 encontró
los dos que faltaban, que son los que el analista lee de verdad:

1. el nodo guiado, ANTES de estimar: «armónicos cos/sin para cada frecuencia
   significativa», que contradecía al `n_harmonics=freq//2-1` impreso dos líneas
   más abajo en la misma salida;
2. la recomendación de `describe_seasonal_params`, DESPUÉS de estimar:
   «Considera eliminarlos», sin nombrar el MEG y sin exigir que el modelo sea
   adecuado.

Estas pruebas fijan el texto porque **el texto es el comportamiento**: quien lo
lee —analista o asistente— hace lo que dice.
"""
import warnings

import numpy as np
import pytest

import fue


def _serie_mixta(n=240, s=12, seed=20260814):
    """Estacionalidad MIXTA por construcción: f=1 determinista, f=2 estocástica.

    Es el caso que destapa el defecto: en f=2 el armónico determinista sale no
    significativo POR CONSTRUCCIÓN, porque la amplitud vaga.
    """
    rng = np.random.RandomState(seed)
    t = np.arange(1, n + 1)
    det = 3.0 * np.cos(2 * np.pi * t / s) + 1.5 * np.sin(2 * np.pi * t / s)
    c2 = 2 * np.cos(2 * np.pi * 2 / s)
    x2 = np.zeros(n)
    u = rng.normal(0, 0.35, n)
    for k in range(2, n):
        x2[k] = c2 * x2[k - 1] - x2[k - 2] + u[k]
    y = 100 + det + x2 + rng.normal(0, 1.0, n)
    return fue.TimeSeries(list(y), freq=s, start=(2000, 1), name="MIXTA"), y


def _modelo_inicial(ts, y):
    interv = []
    for f in range(1, 6):
        interv.append(fue.Intervention("cos", harmonic=float(f), omega=[0.1]))
        interv.append(fue.Intervention("sin", harmonic=float(f), omega=[0.1]))
    interv.append(fue.Intervention("alter", omega=[0.1]))
    m = fue.Model(ts, d=0, interventions=interv, ar=[[0.3]], ar_free=[[True]],
                  mu=float(y.mean()), estimate_mu=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit()
    return m


# ── foco 1: el nodo guiado, antes de estimar ───────────────────────────────

def test_the_guided_node_does_not_prescribe_a_significance_filter():
    from art.describe import describe_seasonality

    ts, _y = _serie_mixta()
    d = describe_seasonality(ts)
    txt = d.summary + "\n" + (d.recommendation or "")
    if "Decisión B1" not in txt:
        pytest.skip("esta serie no llega a la rama B1")

    assert "para cada frecuencia significativa" not in txt, (
        "el nodo vuelve a prescribir el filtro de significación: es una "
        "instrucción de omitir armónicos antes de que exista un modelo")
    assert "TODAS" in txt, "el nodo ya no pide armónicos en todas las frecuencias"


def test_the_guided_node_says_why_the_list_is_not_a_selection_rule():
    """No basta con quitar la instrucción mala: hay que decir por qué, o vuelve."""
    from art.describe import describe_seasonality

    ts, _y = _serie_mixta()
    txt = describe_seasonality(ts).summary + "\n" + (
        describe_seasonality(ts).recommendation or "")
    if "Decisión B1" not in txt:
        pytest.skip("esta serie no llega a la rama B1")

    assert "DESCRIPTIVA" in txt
    assert "modelo nulo del MEG" in txt
    assert "estocástica" in txt


def test_the_prose_agrees_with_the_code_block_below_it():
    """Una pantalla, dos instrucciones contradictorias, era medio defecto."""
    import inspect

    from art import mcp_server

    src = inspect.getsource(mcp_server)
    assert "n_harm = max(ts.freq // 2 - 1, 0)" in src, (
        "el bloque de código ya no recomienda el conjunto completo; si eso "
        "cambia a propósito, este test y el texto del nodo cambian con él")


# ── foco 2: la recomendación posterior a la estimación ─────────────────────

def test_the_recommendation_does_not_prescribe_pruning():
    from art.describe import describe_seasonal_params

    ts, y = _serie_mixta()
    m = _modelo_inicial(ts, y)
    d = describe_seasonal_params(m)

    assert d.data["droppable_k"], (
        "esta serie debe producir frecuencias con |t| ≤ 2 — si no, el test no "
        "está ejercitando el camino que importa")

    rec = d.recommendation
    assert "Considera eliminarlos" not in rec, (
        "vuelve a prescribir la poda sin condición, sobre un modelo cualquiera")
    assert "MEG" in rec, "la recomendación no nombra el MEG"
    assert "ifadf" in rec, (
        "no dice qué se hace con una frecuencia que el MEG declare estocástica: "
        "no se poda, se reformula")


def test_the_two_legitimate_routes_to_pruning_are_offered():
    """La poda no está prohibida: está ORDENADA, y art ya ofrecía las dos vías.

    (a) se va a contrastar el MEG -> todavía no se poda;
    (b) el analista fija la estacionalidad como determinista y renuncia al MEG
        -> el contraste de simplificación procede AHORA.

    Y en un modelo mixto ya resuelto, podar los armónicos que quedan
    deterministas es el paso final. Un texto que sólo dijera «no podes» sería
    tan defectuoso como el que decía «poda»: dejaría sin salida al analista que
    ya decidió.
    """
    from art.describe import describe_seasonal_params

    ts, y = _serie_mixta()
    rec = describe_seasonal_params(_modelo_inicial(ts, y)).recommendation

    assert "(a)" in rec and "(b)" in rec, "no ofrece los dos caminos"
    assert "no podes todavía" in rec, "el camino (a) no dice qué hacer"
    assert "procede simplificar ahora" in rec, (
        "el camino (b) —fijar determinista y renunciar al MEG— no autoriza el "
        "contraste de simplificación, que es justo lo que procede ahí")
    assert "MIXTO" in rec, (
        "no dice que en un modelo mixto resuelto la poda final procede")


def test_it_says_what_a_low_t_also_means():
    """El corazón del asunto: por qué el |t| bajo no decide por sí solo.

    La redacción importa y se afinó al escribirla: un |t| bajo en f no es
    «evidencia a favor» de estacionalidad estocástica —eso sería afirmar de más—,
    es que **también es lo que ésta produce**, porque la amplitud vaga y promedia
    hacia cero. Por eso hace falta el MEG para separar los dos casos, y por eso
    el mismo estadístico no puede zanjarlo.
    """
    from art.describe import describe_seasonal_params

    ts, y = _serie_mixta()
    rec = describe_seasonal_params(_modelo_inicial(ts, y)).recommendation
    assert "también es lo que produce" in rec
    assert "ESTOCÁSTICA" in rec
    assert "modelo nulo del MEG" in rec


def test_the_all_significant_case_also_defers_to_the_meg():
    """Cuando no hay nada que podar, el mensaje tampoco puede cerrar la puerta:
    que todos los t sean altos no responde si alguna frecuencia es estocástica."""
    import inspect

    from art import describe

    src = inspect.getsource(describe.describe_seasonal_params)
    i = src.find("Todos los armónicos son significativos")
    assert i > 0
    assert "MEG" in src[i:i + 400], (
        "la rama 'todos significativos' vuelve a zanjar la cuestión sin el MEG")
