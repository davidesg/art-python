"""BUG-0094 — la salida del carril guiado no estaba estandarizada.

El argumento del analista, y es el que decide:

> «El problema si no está mínimamente estandarizado es que es caótico y
>  **desobliga al analista**. Cuando en el fondo está perfectamente
>  estandarizado.»

Las dos mitades importan. Una salida de forma variable no se puede exigir: no
cabe preguntar por qué se decidió sin mirar la diagnosis, porque quizá la
diagnosis no estaba. Con forma fija, la ausencia de una sección es una omisión
atribuible — la misma lógica del guion, que obliga porque siempre lleva
`decision` y `rationale`.

Y la variabilidad era gratuita: el proceso ya está estandarizado. De la tesis
(§1.1.1.2, §2.3): «un proceso iterativo consciente … (1) especificación inicial,
(2) estimación eficiente por MVENC, (3) diagnosis estadística (métodos formales
e informales) y, en su caso, (4) reformulación».

**No se uniforma el contenido — cada nodo llena lo suyo — se uniforma a qué
etapa pertenece cada bloque.**

La cuarta va SIEMPRE, también cuando el modelo se sostiene: el «en su caso» de
la cita es sobre si hay que reformular, no sobre si hay que pronunciarse.

Y el sobre es el mismo en los dos carriles, porque el guion también lo es. La
única diferencia: en autónomo **la figura no viaja**.
"""
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.mcp_server import ETAPAS_ITERACION, envuelve_iteracion
from art.pipeline import _RESCALE_FACTOR, _write_inp

CE = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
BM = getattr(srv.build_model, "fn", srv.build_model)


def _secciones(t):
    return re.findall(r"^## \d · (.+)$", t, re.M)


@pytest.fixture(scope="module")
def serie(tmp_path_factory):
    d = tmp_path_factory.mktemp("s94")
    rng = np.random.default_rng(23)
    y = np.cumsum(rng.standard_normal(120) * 0.4) + 100.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="S94")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(d / "S94.inp")
    _write_inp(ts, m, f)
    return f, str(d)


def _txt(fn, *a, **k):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return "\n".join(getattr(c, "text", "") for c in fn(*a, **k))


# ───────────── el sobre, como pieza ─────────────

def test_las_cuatro_etapas_son_las_de_la_escuela():
    assert ETAPAS_ITERACION == ("ESPECIFICACIÓN", "ESTIMACIÓN", "DIAGNOSIS",
                                "REFORMULACIÓN")


def test_las_cuatro_salen_siempre_y_en_orden():
    t = envuelve_iteracion(nombre="X")
    assert _secciones(t) == list(ETAPAS_ITERACION)


def test_una_seccion_vacia_se_DICE_en_vez_de_desaparecer():
    """Que falte es lo que desobliga: si no está, no se puede exigir."""
    t = envuelve_iteracion(nombre="X")
    assert "Sin cambios de especificación" in t
    assert "No se ha estimado" in t
    assert "Sin diagnosis" in t


def test_la_cuarta_es_SIEMPRE_explicita():
    """El «en su caso» de la cita es sobre si hay que reformular, no sobre si
    hay que pronunciarse. Una iteración que no dice qué haría después no ha
    terminado."""
    t = envuelve_iteracion(nombre="X", ecuacion="y=…", diagnosis="todo bien")
    assert "4 · REFORMULACIÓN" in t
    assert "No procede reformular" in t


def test_el_extra_no_inventa_una_quinta_etapa():
    t = envuelve_iteracion(nombre="X", extra="*guion: v1*")
    assert len(_secciones(t)) == 4
    assert "*guion: v1*" in t


# ───────────── la distinción de carril ─────────────

def test_en_autonomo_las_figuras_se_CITAN_no_viajan():
    t = envuelve_iteracion(nombre="X", diagnosis="Q ok",
                           rutas_figuras=["figs/X_v1.png"])
    assert "no viajan en este carril" in t
    assert "figs/X_v1.png" in t


def test_build_model_no_manda_figuras_por_defecto(serie):
    """Medido sobre las tres realizaciones del run 3: el 97.4% de los bytes que
    salen del servidor son imágenes, y en un bucle agéntico cada byte se
    reenvía en todos los turnos siguientes. En autónomo nadie las mira."""
    f, d = serie
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = BM(f, os.path.join(d, "auto.inp"), max_rounds=2)
    assert not [c for c in r if getattr(c, "type", "") == "image"]


def test_pero_se_pueden_pedir(serie):
    f, d = serie
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = BM(f, os.path.join(d, "conf.inp"), max_rounds=2, con_figuras=True)
    assert [c for c in r if getattr(c, "type", "") == "image"]


def test_no_mandarlas_no_las_PIERDE(serie):
    """«No viajan» sólo vale si el registro las tiene."""
    f, d = serie
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _txt(BM, f, os.path.join(d, "guarda.inp"), max_rounds=2)
    citadas = re.findall(r"· `(.+\.png)`", t)
    assert citadas, "no cita ninguna figura"
    assert all(os.path.exists(c) for c in citadas), "cita figuras que no están"


# ───────────── el sobre en las herramientas ─────────────

def test_confirm_and_estimate_emite_LA_SALIDA_GUIADA(serie):
    """Corregido: esta prueba exigía las cuatro ETAPAS del método, que es la
    forma del REGISTRO. `confirm_and_estimate` es la herramienta del carril
    guiado y su salida va dirigida al analista, que ya sabe de dónde viene el
    modelo —lo decidió él— y lo que necesita es lo que tiene delante y qué se
    le pregunta."""
    from art.mcp_server import SECCIONES_GUIADO
    f, d = serie
    t = _txt(CE, f, os.path.join(d, "m00.inp"), lam=0.0, d=1, D=0, p=0, q=0,
             n_harmonics=0)
    assert _secciones(t) == list(SECCIONES_GUIADO)


def test_build_model_sigue_con_las_ETAPAS_del_metodo(serie):
    """Y aquí está la diferencia entre los dos carriles, que antes no existía:
    en autónomo no hay a quién preguntar, así que la salida ES el registro."""
    from art.mcp_server import FIN_DE_TURNO_GUIADO
    f, d = serie
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _txt(BM, f, os.path.join(d, "mismo.inp"), max_rounds=2)
    assert _secciones(t) == list(ETAPAS_ITERACION)
    assert FIN_DE_TURNO_GUIADO not in t, "el autónomo no pregunta"


def test_la_reformulacion_sale_de_la_diagnosis_no_del_agente(serie):
    """La 4ª etapa no se le pide al LLM: se deduce de lo que la diagnosis ya
    dictaminó."""
    from art.mcp_server import _reformulacion_desde

    class _D:
        data = {"q_pass": False, "jb_pass": True, "n_extreme": 2}

    r = _reformulacion_desde(_D())
    assert "no se sostiene" in r
    assert "Q rechaza" in r and "2 residuo" in r


def test_lo_declarado_por_el_analista_entra_en_la_cuarta():
    from art.mcp_server import _reformulacion_desde

    class _D:
        data = {}

    r = _reformulacion_desde(_D(), guion_next="probar MA(1)")
    assert "probar MA(1)" in r


def test_las_herramientas_que_estiman_pasan_por_el_sobre():
    """La prueba que impide la regresión: una herramienta nueva que estime y no
    envuelva deja de estar estandarizada, y eso desobliga al analista."""
    from tests._fuente import fuente_de
    for n in ("confirm_and_estimate", "estimate_and_diagnose",
              "suggest_intervention_form", "build_model"):
        assert "envuelve_iteracion(" in fuente_de(getattr(srv, n)), n


def test_el_carril_va_en_la_cabecera_no_enterrado():
    """Quién decidió es una propiedad de la iteración, y quien lee la salida
    tiene que saberlo antes que nada. Lo pilló una prueba dorada que exigía el
    modo en la primera línea, y tenía razón: mi primera versión del sobre lo
    enterró en la sección 1."""
    t = envuelve_iteracion(nombre="X", modo="autónomo")
    assert "autónomo" in t.splitlines()[0]
    assert t.splitlines()[0].startswith("# Iteración — X")


def test_sin_modo_la_cabecera_no_lleva_adorno():
    assert envuelve_iteracion(nombre="X").splitlines()[0] == "# Iteración — X"
