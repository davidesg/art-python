"""Las tres operaciones del contrato de ficheros (estudio §6-B).

`_load_fitted` significaba dos cosas a la vez —«estima esto» y «déjame mirar
esto»— y el contrato distingue tres:

    estimar(inp)         EXIGE `.inp` — un `.pre` se RECHAZA (BUG-0159);
                         promete desviaciones típicas válidas.
    mirar(inp|pre)       acepta los dos; NO promete SE. Residuos, figuras,
                         diagnosis, previsión dependen de los VALORES, y en un
                         `.pre` los valores son exactos.
    outfile.lee_out      el registro, sin tocar el motor. La operación que no
                         existía y que el `.out` legible hizo posible.

Que sean tres no es ceremonia: hace que **el sitio que llama declare lo que
necesita**. Y de ahí sale lo que de verdad importa — `mirar` no avisa, porque no
promete nada que un `.pre` estropee. Avisar ahí sería ruido, y el ruido cuesta
tokens: el LLM tiene que parar a averiguar si el aviso le concierne.

**La regla, en su forma operativa** (BUG-0164): quien imprime **las
desviaciones típicas DEL MODELO QUE CARGA** necesita `estimar`. Quien sólo toma
de él la estructura, la serie o los residuos —porque las SE que publica son de
**otro** modelo, estimado después— necesita `mirar`. La primera versión de esa
frase decía «quien imprima una SE», y con ella cuatro herramientas que estiman
algo distinto de lo que cargan se quedaron sin poder aceptar un `.pre`.

**Y desde BUG-0159 `estimar` no avisa: se NIEGA.** El convenio llevaba desde el
principio dando problemas con un `RuntimeWarning` que ningún carril lee y un
alias —`_load_fitted`— que no dice que estima. Una propiedad que sólo se
sostiene si todo el mundo se acuerda no es una propiedad del sistema: es una
costumbre. Lo que la convierte en propiedad es que la operación prohibida falle
ruidosamente al intentarla — y que al fallar diga por dónde salir.
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


def test_estimar_RECHAZA_un_pre(terna):
    """El cambio de BUG-0159: de avisar a negarse."""
    from art.pipeline import ErrorDeContrato
    _, f_pre, _ = terna
    with pytest.raises(ErrorDeContrato):
        estimar(f_pre)


def test_y_el_rechazo_dice_por_donde_salir(terna):
    """Negarse sin dar la salida convierte una regla en un muro."""
    from art.pipeline import ErrorDeContrato
    f_inp, f_pre, _ = terna
    try:
        estimar(f_pre); t = ""
    except ErrorDeContrato as e:
        t = str(e)
    assert os.path.basename(f_inp) in t, "no nombra el `.inp` hermano"
    assert "mirar()" in t and "`.out`" in t, "no da las dos salidas"


def test_mirar_NO_avisa_sobre_un_pre(terna):
    """Lo que se va a mirar depende de los valores, y en un `.pre` son exactos.
    Avisar sería ruido, y el ruido cuesta tokens."""
    _, f_pre, _ = terna
    assert _n_avisos(mirar, f_pre) == 0


def test_ninguna_avisa_sobre_un_inp(terna):
    f_inp, _, _ = terna
    assert _n_avisos(estimar, f_inp) == 0
    assert _n_avisos(mirar, f_inp) == 0


def test_el_sello_sigue_puesto_por_la_via_viva(terna):
    """El sello no depende del contrato: quien imprima una SE lo necesita venga
    por donde venga. Con `estimar` rechazando el `.pre`, la vía que queda es
    `mirar`, y tiene que sellar igual."""
    f_inp, f_pre, _ = terna
    assert viene_de_pre(mirar(f_pre)[1])
    assert not viene_de_pre(mirar(f_inp)[1])
    assert not viene_de_pre(estimar(f_inp)[1])


def test_mirar_no_es_una_estimacion_PEOR(terna):
    """`mirar` sobre el `.pre` da los mismos VALORES que estimar el `.inp`: es
    la misma estimación, sin la promesa sobre la covarianza. Eso es lo que hace
    legítimo mirar residuos, figuras y diagnosis desde un `.pre`, y saltar con
    él a `drtran` o `drvec`."""
    f_inp, f_pre, _ = terna
    _, a = estimar(f_inp)
    _, b = mirar(f_pre)
    assert abs(a._result.loglik - b._result.loglik) < 1e-6


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


def test_una_herramienta_de_estimar_SE_NIEGA_de_extremo_a_extremo(terna):
    """Lo que el analista tiene que ver por la superficie MCP no es un aviso
    —que nadie lee— sino la negativa, **sin traceback**: el carril sólo enseña
    el texto que le llega, así que una excepción cruda se le presenta como una
    avería del programa en lugar de como una regla del método."""
    _, f_pre, _ = terna
    fn = getattr(srv.test_interventions, "fn", srv.test_interventions)
    t = "\n".join(getattr(x, "text", "") for x in fn(f_pre))
    assert "Traceback" not in t, "la negativa llega como avería"
    assert "`.pre`" in t and "RC.inp" in t, "no dice qué hay que usar"


def test_y_el_que_solo_mira_sigue_pasando(terna):
    """La otra mitad de la regla: negar el `.pre` a quien estima no puede
    cerrarlo a quien sólo mira. Si lo cerrara, el `.pre` dejaría de servir para
    lo único para lo que se guarda."""
    _, f_pre, _ = terna
    fn = getattr(srv.intervention_analysis, "fn", srv.intervention_analysis)
    t = "\n".join(getattr(x, "text", "") for x in fn(f_pre))
    assert "Traceback" not in t and "No se puede hacer eso" not in t


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
    # BUG-0164: las SE que publican NO son las del modelo que cargan —son las
    # de cada configuración, estimada aparte sobre ese base— así que les toca
    # `mirar`. Con `estimar` negándose al `.pre` (BUG-0159) estas dos puertas se
    # quedaron cerradas para el encadenado, que es el modo normal del nodo.
    ("incident_configurations", False),
    ("guided_intervention", False),
    ("intervention_ladder", False),    # BUG-0159: pasó a `_mirar`
    ("model_histogram", False),        # idem
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


def test_el_aviso_NO_PUBLICA_NINGUNA_MAGNITUD_DE_SESGO():
    """Dos intentos y la lección — BUG-0168.

    La primera versión decía «entre 0.46× y 3.47×» y se leía como una cota. El
    arreglo de entonces fue añadir «al menos» y una tercera cifra (4.23×), o sea
    **atacar la forma** —rango contra cota— dejando el fondo intacto: publicar
    una magnitud de sesgo que nadie ha calculado.

    Y se aplicó, como tenía que pasar. El analista, en la corrida de ES_CPI:
    «el LLM aparentemente está calculando el sesgo, pero ¿cómo lo hace? No tiene
    ningún algoritmo para calcular el sesgo de los SE». No lo tiene: repetía
    estas cifras.

    Lo que este aviso puede afirmar es que el número no sirve, y por qué. Cuánto
    se desvía **no se sabe**, y no por falta de medirlo: la covarianza del BFGS
    es un subproducto del camino del optimizador, así que no hay una cantidad
    que estimar.
    """
    import re
    from art.pipeline import AVISO_SE_DESDE_PRE
    assert not re.findall(r"\d+[.,]?\d*×", AVISO_SE_DESDE_PRE), "publica un factor"
    assert not re.findall(r"\|t\|\s*=\s*\d", AVISO_SE_DESDE_PRE), "publica razones t"
    assert "No hay forma de saber cuánto se desvían" in AVISO_SE_DESDE_PRE


def test_el_aviso_dice_que_cambia_DECISIONES_no_solo_numeros():
    """Sigue siendo lo que lo hace accionable —que no es cosmética— pero sin
    cifras: «se han visto armónicos pasar de conservarse a podarse» dice lo que
    importa sin dar un factor que luego se aplica."""
    from art.pipeline import AVISO_SE_DESDE_PRE
    assert "cambia decisiones" in AVISO_SE_DESDE_PRE
    assert "podarse" in AVISO_SE_DESDE_PRE
