"""Las tres operaciones del contrato de ficheros (estudio §6-B).

`_load_fitted` significaba dos cosas a la vez —«estima esto» y «déjame mirar
esto»— y el contrato distingue tres:

    estimar(inp)         exige `.inp`; promete desviaciones típicas válidas.
    mirar(inp|pre)       acepta los dos; NO promete SE. Residuos, figuras,
                         diagnosis, previsión dependen de los VALORES, y en un
                         `.pre` los valores son exactos.
    outfile.lee_out      el registro, sin tocar el motor. La operación que no
                         existía y que el `.out` legible hizo posible.

Que sean tres no es ceremonia: hace que **el sitio que llama declare lo que
necesita**. Y de ahí sale lo que de verdad importa — `mirar` no avisa, porque no
promete nada que un `.pre` estropee. Avisar ahí sería ruido, y el ruido cuesta
tokens: el LLM tiene que parar a averiguar si el aviso le concierne.
"""
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art import pipeline
from art.outfile import lee_out
from art.pipeline import (_RESCALE_FACTOR, _write_inp, estimar, mirar,
                          viene_de_pre)


@pytest.fixture(scope="module")
def terna(tmp_path_factory):
    d = tmp_path_factory.mktemp("contrato")
    rng = np.random.default_rng(13)
    y = np.cumsum(rng.standard_normal(120) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="RC")
    m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
                  estimate_mu=False, refactor=_RESCALE_FACTOR)
    f_inp = str(d / "RC.inp")
    _write_inp(ts, m, f_inp)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, fit = estimar(f_inp)
    f_pre, f_out = str(d / "RC.pre"), str(d / "RC.out")
    fit.write_pre(f_pre)
    fit.write_out(f_out)
    return f_inp, f_pre, f_out


def _n_avisos(fn, *a):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        fn(*a)
    return sum(1 for x in w if "`.pre`" in str(x.message))


# ───────────── las tres existen y prometen cosas distintas ─────────────

def test_las_tres_operaciones_existen():
    assert callable(estimar) and callable(mirar) and callable(lee_out)


def test_el_nombre_historico_sigue_valiendo():
    """17 herramientas lo usan; renombrarlas de golpe mezclaría dos cambios."""
    assert pipeline._load_fitted is estimar


def test_estimar_avisa_sobre_un_pre(terna):
    _, f_pre, _ = terna
    assert _n_avisos(estimar, f_pre) == 1


def test_mirar_NO_avisa_sobre_un_pre(terna):
    """Lo que se va a mirar depende de los valores, y en un `.pre` son exactos.
    Avisar sería ruido, y el ruido cuesta tokens."""
    _, f_pre, _ = terna
    assert _n_avisos(mirar, f_pre) == 0


def test_ninguna_avisa_sobre_un_inp(terna):
    f_inp, _, _ = terna
    assert _n_avisos(estimar, f_inp) == 0
    assert _n_avisos(mirar, f_inp) == 0


def test_las_dos_sellan_el_origen(terna):
    """El sello no depende del contrato: quien imprima una SE lo necesita venga
    por donde venga."""
    f_inp, f_pre, _ = terna
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert viene_de_pre(estimar(f_pre)[1])
        assert viene_de_pre(mirar(f_pre)[1])
        assert not viene_de_pre(mirar(f_inp)[1])


def test_las_dos_dan_los_mismos_valores(terna):
    """`mirar` no es una estimación peor: es la misma, sin la promesa sobre la
    covarianza."""
    _, f_pre, _ = terna
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, a = estimar(f_pre)
        _, b = mirar(f_pre)
    assert abs(a._result.loglik - b._result.loglik) < 1e-9


def test_leer_no_toca_el_motor(terna):
    """La tercera operación: no estima, así que no puede corromper nada."""
    _, _, f_out = terna
    r = lee_out(f_out)
    assert r.parametros and r.loglik is not None


# ───────────── el reparto de las herramientas ─────────────

MIRAN = ("generate_forecast", "intervention_analysis", "record_version")


@pytest.mark.parametrize("nombre", MIRAN)
def test_las_que_solo_miran_usan_mirar(nombre):
    from tests._fuente import fuente_de
    src = fuente_de(getattr(srv, nombre))
    assert "_mirar(" in src, f"{nombre} sigue estimando para mirar"


@pytest.mark.parametrize("nombre", MIRAN)
def test_las_que_solo_miran_no_tocan_la_covarianza(nombre):
    """El reparto tiene que seguir siendo cierto: si una de éstas empieza a
    imprimir un error típico, cambia de lado."""
    from tests._fuente import fuente_de
    src = fuente_de(getattr(srv, nombre))
    for k in ("std_errors", "cov_matrix", "omega_se", "_equation_for_prompt",
              "test_intervention"):
        assert k not in src, f"{nombre} consume {k}: le toca `estimar`"


def test_las_que_imprimen_SE_siguen_estimando():
    from tests._fuente import fuente_de
    for nombre in ("test_interventions", "confirm_and_estimate",
                   "seasonal_param_analysis"):
        src = fuente_de(getattr(srv, nombre))
        assert "_load_fitted(" in src or "estimar(" in src


def test_una_herramienta_de_mirar_calla_de_extremo_a_extremo(terna):
    """La comprobación que importa: por la superficie MCP, no en la API."""
    _, f_pre, _ = terna
    fn = getattr(srv.intervention_analysis, "fn", srv.intervention_analysis)
    assert _n_avisos(fn, f_pre) == 0


def test_una_herramienta_de_estimar_avisa_de_extremo_a_extremo(terna):
    _, f_pre, _ = terna
    fn = getattr(srv.test_interventions, "fn", srv.test_interventions)
    assert _n_avisos(fn, f_pre) == 1


# ═══════ La CUARTA puerta: cargar y ajustar a mano (revisión externa, #2) ═══════

def test_ninguna_herramienta_carga_y_ajusta_POR_SU_CUENTA():
    """El contrato declaraba tres operaciones y había una cuarta vía abierta:
    `_load_ts_model(path)` seguido de `m.fit()` a mano. **Ocho herramientas** la
    usaban, y por ahí `_art_origen` nunca se sella — así que `viene_de_pre()`
    devuelve False por construcción y el aviso de BUG-0090 es **inalcanzable**.

    Lo encontró una revisión con contexto limpio. Entre las ocho estaban
    `model_equation_display`, cuya salida entera son parámetros con su error
    típico, y `guided_intervention`, escrita en esta misma sesión por quien
    construyó el contrato.

    Es la tercera cara del patrón: la capacidad está abajo, la superficie no la
    nombra — y aquí la superficie ni siquiera pasa por la puerta.
    """
    import ast
    import pathlib

    src = pathlib.Path("src/art/mcp_server.py").read_text()
    lin = src.split("\n")
    malas = []
    for n in ast.walk(ast.parse(src)):
        if not isinstance(n, ast.FunctionDef):
            continue
        cuerpo = "\n".join(lin[n.lineno - 1:n.end_lineno])
        if "_load_ts_model(" in cuerpo and re.search(r"^\s*m\.fit\(\)\s*$",
                                                     cuerpo, re.M):
            malas.append(f"{n.name}:{n.lineno}")
    assert not malas, (
        "cargan y ajustan fuera del contrato — usa `_load_fitted`/`estimar` si "
        f"vas a imprimir un error típico, o `_mirar` si no: {malas}")


@pytest.mark.parametrize("nombre,avisa", [
    ("model_equation_display", True),     # su salida ENTERA son SE
    ("estimate_and_diagnose", True),
    ("incident_configurations", True),
    ("intervention_ladder", True),
    ("guided_intervention", True),
    ("residual_episodes", False),         # sólo residuos: avisar sería ruido
    ("residual_outlier_scan", False),
    ("intervention_plot", False),
])
def test_cada_una_pasa_por_la_puerta_que_le_toca(nombre, avisa):
    """`estimar` promete SE y avisa; `mirar` no promete y calla. La clasificación
    se hizo sobre el CUERPO sin docstring: mirar el fuente entero daba falsos
    positivos por los punteros que las docstrings llevan unas a otras."""
    from tests._fuente import cuerpo_de
    c = cuerpo_de(getattr(srv, nombre))
    assert "_load_ts_model" not in c or ".fit()" not in c
    if avisa:
        assert "_load_fitted(" in c or "estimar(" in c, nombre
    else:
        assert "_mirar(" in c or "mirar(" in c, nombre


def test_el_aviso_no_publica_un_rango_como_si_fuera_una_cota():
    """La primera versión decía «entre 0.46× y 3.47×», que era la muestra de un
    caso. La revisión externa midió **4.23×** sobre otro modelo. Un rango
    presentado sin «al menos» se lee como un límite que no existe."""
    from art.pipeline import AVISO_SE_DESDE_PRE
    assert "al menos" in AVISO_SE_DESDE_PRE
    assert "4.23×" in AVISO_SE_DESDE_PRE
    assert "ni cota conocida" in AVISO_SE_DESDE_PRE


def test_el_aviso_dice_que_cambia_DECISIONES_no_solo_numeros():
    """Es lo que convierte el aviso en accionable: dos armónicos pasan de
    |t|=3.02 y 2.83 a 1.31 y 1.28 — de conservarse a podarse, que es la decisión
    del nodo estacional."""
    from art.pipeline import AVISO_SE_DESDE_PRE
    assert "cambia decisiones" in AVISO_SE_DESDE_PRE
    assert "3.02" in AVISO_SE_DESDE_PRE and "1.31" in AVISO_SE_DESDE_PRE
