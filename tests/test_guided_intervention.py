"""`guided_intervention` — la puerta del nodo de intervención.

Arquitectura §4.1. El nodo tenía NUEVE instrumentos —el que más de toda la
suite— y era el único sin entrada secuenciada: ninguno remitía a otro, y tres
contestaban «¿qué forma?» con criterios distintos y sin árbitro. Esta
herramienta los secuencia, en tres llamadas, y **no decide**: presenta y espera,
como `guided_identification`.

    Llamada 1 (sin fecha)  → ¿hay que intervenir? — calibración del correlograma
    Llamada 2 (fecha)      → ¿qué forma admite el dato? — episodio + configuraciones
                             + escalera, en una respuesta y con un veredicto
    Llamada 3 (fecha+forma)→ construir, estimar y verificar (Treadway + ganancia)

La llamada 3 es la que no existía (BUG-0079) y la que cierra el nodo.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _load_ts_model, _write_inp

GI = getattr(srv.guided_intervention, "fn", srv.guided_intervention)


def _txt(res):
    return "\n".join(getattr(c, "text", "") for c in res)


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """Serie trimestral con un ESCALÓN permanente de nivel en Q1/2015."""
    d = tmp_path_factory.mktemp("gi")
    rng = np.random.default_rng(5)
    y = np.cumsum(rng.standard_normal(120) * 0.3) + 100.0
    y[60:] += 6.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="GI")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(d / "base.inp")
    _write_inp(ts, m, f)
    return f, str(d)


# ───────────────── llamada 1 ─────────────────

def test_llamada1_pregunta_si_cambia_la_identificacion(base):
    f, _ = base
    t = _txt(GI(f))
    assert "Llamada 1" in t
    assert "cambian la identificación" in t
    # la pregunta no es «¿hay anómalos?»
    assert "PACF" in t and "ACF" in t


def test_llamada1_da_las_fechas_candidatas_como_fechas(base):
    """El analista habla en fechas; los dos espacios de índices (serie y
    residuos) se quedan dentro de la herramienta (BUG-0067)."""
    f, _ = base
    t = _txt(GI(f))
    assert "Fechas candidatas" in t
    assert "/20" in t or "Q" in t


def test_llamada1_propone_la_llamada_siguiente(base):
    f, _ = base
    t = _txt(GI(f))
    assert "guided_intervention(inp_path=" in t
    assert "date=" in t


def test_llamada1_avisa_de_sobre_intervenir_si_no_cambia_nada(tmp_path):
    """El criterio de parada, comprobado sobre una serie donde de verdad no
    cambia nada: ningún retardo cruza la banda al omitir los anómalos.

    Y la razón por la que hace falta decirlo: la escalada no se detiene sola.
    Cada intervención encoge σ̂, con lo que el siguiente residuo sube de |z| y
    pide su turno."""
    rng = np.random.default_rng(5)
    y = np.cumsum(rng.standard_normal(140) * 0.3) + 100.0
    y[70] += 1.6
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1990, 1), name="LIMPIA")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(tmp_path / "limpia.inp")
    _write_inp(ts, m, f)
    t = _txt(GI(f))
    assert "NO cambian la identificación" in t
    assert "sobre-intervenir" in t
    assert "encoge σ̂" in t


# ───────────────── llamada 2 ─────────────────

def test_llamada2_da_las_tres_cosas_en_una_respuesta(base):
    f, _ = base
    t = _txt(GI(f, date="Q1/2015", threshold=2.5))
    assert "Llamada 2" in t
    assert "El suceso" in t                    # el episodio
    assert "Configuraciones del incidente" in t
    assert "Escalera de Ockham" in t
    assert "## Veredicto" in t


def test_llamada2_nombra_el_arbitro_de_la_forma(base):
    """§4.2: para la FORMA gobierna la configuración sobre el episodio, porque
    extiende el arranque por el mecanismo y el otro sólo agrupa extremos."""
    f, _ = base
    t = _txt(GI(f, date="Q1/2015", threshold=2.5))
    assert "MECANISMO" in t


def test_llamada2_dice_la_lectura_escalar_y_que_no_la_decide_el_aic(base):
    f, _ = base
    t = _txt(GI(f, date="Q1/2015", threshold=2.5))
    assert "Lectura escalar" in t
    assert "El AIC no arbitra" in t


def test_llamada2_propone_la_llamada_3_con_su_orden(base):
    f, _ = base
    t = _txt(GI(f, date="Q1/2015", threshold=2.5))
    assert "n_omega=" in t
    assert "output_path=" in t


def test_llamada2_rechaza_una_fecha_fuera_del_rango_de_residuos(base):
    """Y lo explica: el modelo consume `d + D·s` observaciones al diferenciar."""
    f, _ = base
    t = _txt(GI(f, date="Q1/1990"))
    assert "❌" in t
    assert "fuera del rango" in t or "outside" in t.lower()


def test_llamada2_rechaza_una_fecha_sin_episodio_y_dice_cuales_hay(base):
    f, _ = base
    t = _txt(GI(f, date="Q3/2002", threshold=2.5))
    assert "❌" in t
    assert "no cae en ningún episodio" in t


def test_llamada2_exige_fuente_para_lo_extramuestral(base):
    """No se afirma que un suceso fue permanente sin decir por qué se sabe."""
    f, _ = base
    t = _txt(GI(f, date="Q1/2015", threshold=2.5,
                evento_naturaleza="permanente"))
    assert "❌" in t
    assert "fuente" in t


# ───────────────── llamada 3 — la que faltaba ─────────────────

def test_llamada3_exige_donde_escribir(base):
    f, _ = base
    t = _txt(GI(f, date="Q1/2015", form="step"))
    assert "❌" in t
    assert "output_path" in t


def test_llamada3_construye_estima_y_verifica(base):
    f, d = base
    out = os.path.join(d, "m1.inp")
    t = _txt(GI(f, date="Q1/2015", form="step", n_omega=2, output_path=out))
    assert "Llamada 3" in t
    assert os.path.exists(out)
    _, m = _load_ts_model(out)
    itv = [i for i in m.interventions if i.type == "step"][0]
    assert len(itv.omega) == 2
    # y las dos verificaciones
    assert "Treadway" in t
    assert "ω(1)" in t


def test_llamada3_emite_el_wald_de_ganancia_nula(base):
    """El contraste que separa transitorio de permanente. Antes de BUG-0079 era
    inalcanzable desde el carril guiado: sólo se emite con más de un ω libre y
    no había forma de construir uno."""
    f, d = base
    out = os.path.join(d, "m2.inp")
    t = _txt(GI(f, date="Q1/2015", form="step", n_omega=3, output_path=out))
    assert "Wald" in t
    assert "TRANSITORIO" in t or "permanente" in t


def test_llamada3_conserva_la_escala_de_la_suite(base):
    """BUG-0085: un modelo escrito fuera de convención mete unidades distintas
    en la misma columna del guion."""
    f, d = base
    out = os.path.join(d, "m3.inp")
    GI(f, date="Q1/2015", form="step", n_omega=2, output_path=out)
    _, m = _load_ts_model(out)
    assert m.refactor == _RESCALE_FACTOR


def test_llamada3_registra_el_nodo_en_el_guion(base):
    f, d = base
    g = os.path.join(d, "g.json")
    GI(f, date="Q1/2015", form="step", n_omega=2,
       output_path=os.path.join(d, "m4.inp"), guion_path=g,
       guion_decision="prueba")
    from art.guion import load_guion
    assert load_guion(g).entries


# ───────────────── la puerta, como arquitectura ─────────────────

def test_las_herramientas_sueltas_remiten_a_la_puerta():
    """§2.1: se midieron CERO referencias cruzadas entre las nueve del nodo. Un
    analista que llamara a `residual_episodes` no tenía forma de saber que
    `incident_configurations` existía, ni cuál gobernaba."""
    import inspect
    for n in ("residual_outlier_scan", "residual_episodes",
              "incident_configurations", "intervention_ladder",
              "intervention_plot", "test_interventions",
              "intervention_analysis", "preliminary_outlier_scan"):
        f = getattr(srv, n)
        doc = inspect.getdoc(getattr(f, "fn", f)) or ""
        assert "guided_intervention" in doc, f"{n} no remite a la puerta"


def test_la_puerta_no_decide():
    """§5: `guided_intervention` secuencia y presenta; el analista decide. Es
    la línea que separa evidencia de juicio en toda la arquitectura."""
    import inspect
    doc = inspect.getdoc(GI) or ""
    assert "el analista decide en cada paso" in doc
    assert "WAIT for user" in doc


def test_dominio_es_declarable_desde_la_puerta():
    """BUG-0080 en este nodo: la política dice que «lo declarado gana siempre» y
    el parámetro sólo existía en `build_model`."""
    import inspect
    assert "dominio" in inspect.signature(GI).parameters
