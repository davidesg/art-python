"""BUG-0162 — reformular una intervención, y BUG-0164, que lo bloqueaba.

Todos los constructores hacían `list(interventions) + [itv]`. Append. Y
reformular —cambiar la forma, bajar el orden de ω, mover la fecha— es la
operación CENTRAL del método iterativo: Box-Jenkins es un ciclo de
reformulación, y es la única que el nodo no sabía hacer.

Se hacía volviendo al `.pre` anterior a la intervención. Correcto, e implícito:
ninguna herramienta lo decía, y dependía de que ese fichero existiera y de que
se supiera cuál era. Apuntar al equivocado deja la intervención DOS VECES sobre
el mismo suceso, y el síntoma es un ω que deja de ser significativo, no un
error.

Y la pieza que retira ya estaba escrita: `hereda_del_base` (BUG-0150) quita la
que cae sobre el suceso estudiado, y su docstring dice literalmente «que es el
caso de rehacer la forma de un suceso ya intervenido». La usaban la escalera y
las configuraciones por dentro; la superficie no la ofrecía.

BUG-0164 — LA REGRESIÓN QUE SALIÓ AL PROBAR ESTO

Al ejercitar el encadenado se vio que las puertas del carril guiado RECHAZABAN
un `.pre`. BUG-0159 hizo que `estimar` se negara —bien— y cuatro herramientas
que sólo necesitan la ESTRUCTURA seguían llamándola. Entre ellas
`guided_identification`, cuyo parámetro se llama `pre_path`.

La suite no lo vio porque ninguna prueba encadenaba desde un `.pre`, que es el
modo NORMAL de usar el nodo. Por eso aquí se prueba la cadena entera.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

_T = 70


def _fn(nombre):
    f = getattr(srv, nombre)
    return getattr(f, "fn", f)


def _texto(res):
    return "\n".join(getattr(x, "text", "") for x in res)


def _itvs(path):
    _, m = fue.load(path)
    return [(i.type, int(i.at), len(i.omega or []))
            for i in (m.interventions or [])]


@pytest.fixture(scope="module")
def cadena(tmp_path_factory):
    """El base estimado y su `.pre`, más un `m10` con una intervención de 1 ω."""
    d = tmp_path_factory.mktemp("rehacer")
    rng = np.random.default_rng(12)
    n = 140
    y = 100.0 + np.cumsum(rng.standard_normal(n) * 0.5)
    y[_T:] += -6.0
    y[_T + 1:] += -2.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1990, 1), name="RH")
    f0 = str(d / "RH_m00.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]]), f0)
    _, fit = estimar(f0)
    fit.write_pre(f0[:-4] + ".pre")

    f1 = str(d / "RH_m10.inp")
    _fn("suggest_intervention_form")(f0[:-4] + ".pre", f1, date="Q3/2007",
                                     form="step", n_omega=1)
    return str(d), f0[:-4] + ".pre", f1[:-4] + ".pre"


# ═══════════ BUG-0164 — el encadenado por `.pre` tiene que funcionar ═══════

@pytest.mark.parametrize("tool,kw", [
    ("guided_intervention", {}),
    ("incident_configurations", {"at": _T + 1}),
    ("suggest_intervention_form", {"date": "Q3/2007", "form": "step"}),
])
def test_las_puertas_del_nodo_ACEPTAN_un_pre(cadena, tool, kw, tmp_path):
    """Encadenar por `.pre` es el modo normal del nodo: `base_pre_path` lo dice
    en el nombre. Que `estimar` se niegue (BUG-0159) es correcto; que estas
    herramientas llamaran a `estimar` sin necesitarlo, no."""
    _, base_pre, _ = cadena
    if tool == "suggest_intervention_form":
        kw["output_path"] = str(tmp_path / "salida.inp")
    t = _texto(_fn(tool)(base_pre, **kw) if tool != "suggest_intervention_form"
               else _fn(tool)(base_pre, kw.pop("output_path"), **kw))
    assert "No se puede hacer eso con este fichero" not in t, (
        f"{tool} rechaza un `.pre`: el encadenado del nodo queda cerrado")
    assert "Traceback" not in t


def test_guided_identification_acepta_su_propio_pre_path(cadena):
    """El caso más claro: el parámetro se llama `pre_path`."""
    _, base_pre, _ = cadena
    t = _texto(_fn("guided_identification")(base_pre, pre_path=base_pre))
    assert "No se puede hacer eso con este fichero" not in t


def test_las_que_SI_imprimen_SE_del_origen_siguen_negandose(cadena):
    """La otra mitad: el arreglo no puede reabrir la puerta que BUG-0159 cerró.
    `test_interventions` publica razones t del modelo que carga."""
    _, base_pre, m10_pre = cadena
    t = _texto(_fn("test_interventions")(m10_pre))
    assert "No se puede hacer eso con este fichero" in t


# ═══════════════════ BUG-0162 — rehacer, no sólo añadir ════════════════════

def test_sin_rehacer_se_AÑADE_encima_y_se_avisa(cadena, tmp_path):
    """El fallo silencioso: dos intervenciones sobre el mismo suceso. Sigue
    siendo posible —puede que de verdad sean dos sucesos— pero ya no es mudo."""
    _, _, m10_pre = cadena
    out = str(tmp_path / "add.inp")
    t = _texto(_fn("suggest_intervention_form")(
        m10_pre, out, date="Q3/2007", form="step", n_omega=3))
    assert _itvs(out[:-4] + ".pre") == [("step", _T, 1), ("step", _T, 3)]
    assert "Ya había una intervención en este suceso" in t
    assert "rehacer=True" in t, "avisa del problema y no de la salida"


def test_con_rehacer_se_SUSTITUYE(cadena, tmp_path):
    _, _, m10_pre = cadena
    out = str(tmp_path / "red.inp")
    t = _texto(_fn("suggest_intervention_form")(
        m10_pre, out, date="Q3/2007", form="step", n_omega=3, rehacer=True))
    assert _itvs(out[:-4] + ".pre") == [("step", _T, 3)], "no sustituyó"
    assert "REHECHO" in t


def test_y_dice_CUAL_retiró(cadena, tmp_path):
    """Retirar una intervención en silencio es cambiar el modelo base sin
    avisar — lo dice el propio docstring de `hereda_del_base`."""
    _, _, m10_pre = cadena
    out = str(tmp_path / "red2.inp")
    t = _texto(_fn("suggest_intervention_form")(
        m10_pre, out, date="Q3/2007", form="step", n_omega=3, rehacer=True))
    assert f"step[obs {_T + 1}]" in t
    assert "(1 ω)" in t, "no dice qué forma tenía la que quitó"


def test_rehacer_sin_nada_que_rehacer_lo_dice(cadena, tmp_path):
    """No retirar cuando se pidió es tan silencioso como retirar sin avisar."""
    _, base_pre, _ = cadena
    out = str(tmp_path / "nada.inp")
    t = _texto(_fn("suggest_intervention_form")(
        base_pre, out, date="Q3/2007", form="step", n_omega=2, rehacer=True))
    assert "no había nada que rehacer" in t
    assert "Se ha AÑADIDO, no sustituido" in t


def test_rehacer_conserva_el_resto_del_modelo(cadena, tmp_path):
    """Lo que hace legítimo rehacer aquí en vez de volver al `.pre` anterior:
    las demás intervenciones, la estructura y μ se heredan intactas."""
    _, _, m10_pre = cadena
    # una segunda intervención LEJOS del suceso
    lejos = str(tmp_path / "lejos.inp")
    _fn("suggest_intervention_form")(m10_pre, lejos, date="Q1/2000",
                                     form="step", n_omega=1)
    antes = _itvs(lejos[:-4] + ".pre")
    assert len(antes) == 2, antes

    out = str(tmp_path / "rehecho.inp")
    _fn("suggest_intervention_form")(lejos[:-4] + ".pre", out, date="Q3/2007",
                                     form="step", n_omega=3, rehacer=True)
    despues = _itvs(out[:-4] + ".pre")
    assert len(despues) == 2, f"se perdió la otra intervención: {despues}"
    assert ("step", _T, 3) in despues, "no se rehizo la del suceso"
    lejana = [i for i in antes if i[1] != _T][0]
    assert lejana in despues, "se retiró una intervención de OTRO suceso"


def test_rehacer_es_equivalente_a_volver_al_pre_anterior(cadena, tmp_path):
    """La prueba que justifica el atajo: rehacer sobre el modelo que ya la lleva
    da EL MISMO modelo que construirla desde el `.pre` de antes. Si no lo diera,
    el atajo sería otra cosa, no una comodidad."""
    _, base_pre, m10_pre = cadena

    por_atajo = str(tmp_path / "atajo.inp")
    _fn("suggest_intervention_form")(m10_pre, por_atajo, date="Q3/2007",
                                     form="step", n_omega=3, rehacer=True)
    a_mano = str(tmp_path / "mano.inp")
    _fn("suggest_intervention_form")(base_pre, a_mano, date="Q3/2007",
                                     form="step", n_omega=3)

    assert _itvs(por_atajo[:-4] + ".pre") == _itvs(a_mano[:-4] + ".pre")
    _, ma = fue.load(por_atajo[:-4] + ".pre")
    _, mb = fue.load(a_mano[:-4] + ".pre")
    # RELATIVA, no absoluta: las dos rutas arrancan de semillas distintas —una
    # del óptimo de `m10`, otra del base— así que convergen al MISMO óptimo, no
    # a los mismos bits. Medido: 1,3e-4 sobre un ω de −606,7, o sea 2e-7
    # relativo. Exigir bits idénticos convertiría esta prueba en una medida de
    # la tolerancia del optimizador.
    for x, y in zip(ma.interventions[0].omega, mb.interventions[0].omega):
        x, y = float(x), float(y)
        assert abs(x - y) <= 1e-5 * max(abs(x), abs(y), 1.0), (
            f"los ω no coinciden: {x} vs {y}")


def test_la_superficie_usa_la_pieza_que_YA_existia():
    """`hereda_del_base` hacía exactamente esto desde BUG-0150, por dentro. La
    tercera cara de BUG-0090: la capacidad está abajo y el nodo no la nombra."""
    from tests._fuente import cuerpo_de
    c = cuerpo_de(srv.suggest_intervention_form)
    assert "hereda_del_base" in c
