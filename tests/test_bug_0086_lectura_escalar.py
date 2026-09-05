"""BUG-0086 — la escalera arbitraba entre 1a y 1b por AIC.

`escalera_de_ockham` prohíbe en su propio docstring que el AIC arbitre, y la
selección del peldaño simple era `min(simples, key=lambda p: p.aic)`. `1a`
—escalón permanente— y `1b` —impulso transitorio— no están anidadas y cuestan un
parámetro cada una: el AIC no puede compararlas, y el hueco entre ellas es ruido.

Sobre FOOD_UEM 12/2004 ese ruido eran 0.74 puntos, prestados de una cola
sub-umbral que el impulso capturaba a medias, y la escalera recomendaba un
impulso TRANSITORIO para un escalón PERMANENTE de nivel.

Ahora decide la firma del residuo, vía el diccionario de la FLT.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.episodes import Episodio
from art.escalera import (TOL_CANCELA, Escalera, Peldano, describe_escalera,
                          escalera_de_ockham, lectura_escalar)


def ep(*ext, d=1):
    e = list(ext)
    return Episodio(inicio=e[0][0], fin=e[-1][0], extremos=e, d=d)


# ───────────── el diccionario de la FLT, con d ≥ 1 (residuos en ∇) ─────────────

def test_pico_unico_es_un_escalon():
    """El caso del reporte. En ∇ un impulso solo es la ∇ de un escalón."""
    assert lectura_escalar(ep((35, 3.56)), 1)[0] == "1a"


def test_par_que_cancela_es_un_impulso():
    """+ω, −ω con suma cero: la ∇ de un impulso de nivel."""
    assert lectura_escalar(ep((35, 3.50), (36, -3.40)), 1)[0] == "1b"


def test_par_de_signo_opuesto_que_no_cancela_es_un_escalon():
    """FOOD_UEM con el umbral bajado: (+3.56, −2.20) suma +1.36, el 38% del
    pico. Lo que no revierte es escalón; el segundo extremo es cola del suceso
    (BUG-0083), no la mitad compensadora de un impulso."""
    assert lectura_escalar(ep((35, 3.56), (36, -2.20)), 1)[0] == "1a"


def test_la_lectura_no_depende_de_si_la_cola_cruza_el_umbral():
    """La robustez que se buscaba: contar o no el −2.20 como extremo no cambia
    la lectura. Un criterio que dependiera de eso sería el umbral disfrazado."""
    con = lectura_escalar(ep((35, 3.56), (36, -2.20)), 1)[0]
    sin = lectura_escalar(ep((35, 3.56)), 1)[0]
    assert con == sin == "1a"


def test_dos_extremos_del_mismo_signo_no_son_un_impulso():
    assert lectura_escalar(ep((35, 3.50), (36, 2.90)), 1)[0] == "1a"


def test_extremos_no_contiguos_no_forman_par():
    assert lectura_escalar(ep((35, 3.50), (38, -3.40)), 1)[0] == "1a"


@pytest.mark.parametrize("z1,esperado", [
    (-3.50, "1b"),      # cancela del todo
    (-3.00, "1b"),      # 14% del pico
    (-2.40, "1b"),      # 31%, dentro
    (-2.20, "1a"),      # 38%, fuera
    (-1.00, "1a"),      # 71%, claramente cola
])
def test_la_frontera_es_la_cancelacion_declarada(z1, esperado):
    assert lectura_escalar(ep((35, 3.50), (36, z1)), 1)[0] == esperado


# ───────────── con d = 0 el diccionario se invierte ─────────────

def test_sin_diferenciar_un_extremo_solo_es_un_impulso():
    assert lectura_escalar(ep((35, 3.50), d=0), 0)[0] == "1b"


def test_sin_diferenciar_una_racha_es_un_escalon():
    assert lectura_escalar(ep((35, 3.50), (36, 3.10), d=0), 0)[0] == "1a"


# ───────────── el AIC ya no entra ─────────────

def test_lectura_escalar_no_mira_el_ajuste():
    """No recibe modelos: sólo puede mirar la firma."""
    import inspect
    ps = inspect.signature(lectura_escalar).parameters
    assert set(ps) == {"episodio", "d"}


def test_la_seleccion_del_peldano_simple_ya_no_es_por_aic():
    from _fuente import fuente_de
    assert "min(simples" not in fuente_de(escalera_de_ockham)


def test_la_razon_se_da_por_escrito():
    """El informe tiene que poder decir POR QUÉ, no sólo qué."""
    nivel, razon = lectura_escalar(ep((35, 3.56)), 1)
    assert "ESCALÓN" in razon and "3.56" in razon


# ───────────── de extremo a extremo sobre datos sintéticos ─────────────

def _serie_con_escalon(n=120, at=60, salto=5.0, seed=7):
    rng = np.random.default_rng(seed)
    y = np.cumsum(rng.standard_normal(n) * 0.3) + 100.0
    y[at:] += salto                       # ESCALÓN permanente de nivel
    return fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="E")


def test_un_escalon_de_verdad_se_lee_como_escalon(tmp_path):
    """El AIC puede decir lo que quiera: la firma manda."""
    ts = _serie_con_escalon()
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=100.0)
    m.fit()
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / (r.std(ddof=0) or 1.0)
    k = int(np.argmax(np.abs(z)))
    e = Episodio(inicio=k + 1, fin=k + 1, extremos=[(k + 1, float(z[k]))], d=1)
    esc = escalera_de_ockham(m, e, dominio="generic")
    assert esc.nivel_simple == "1a"
    assert "ESCALÓN" in esc.criterio_simple


def test_la_escalera_publica_el_criterio_en_el_informe(tmp_path):
    ts = _serie_con_escalon()
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=100.0)
    m.fit()
    r = np.asarray(m._result.residuals, dtype=float)
    z = (r - r.mean()) / (r.std(ddof=0) or 1.0)
    k = int(np.argmax(np.abs(z)))
    e = Episodio(inicio=k + 1, fin=k + 1, extremos=[(k + 1, float(z[k]))], d=1)
    d = describe_escalera(escalera_de_ockham(m, e, dominio="generic"))
    assert "Se lee `1a`" in d.summary
    assert "no para arbitrar" in d.summary


def test_el_respaldo_ya_no_es_el_impulso():
    """`suggest_intervention_form` caía en `\"1b\"` cuando la escalera no
    recomendaba. Ése es el lado menos conservador: afirma que revierte."""
    import inspect
    import art.mcp_server as srv
    fn = getattr(srv.suggest_intervention_form, "fn",
                 srv.suggest_intervention_form)
    from _fuente import fuente_de
    src = fuente_de(fn)
    assert 'esc.recomendado or "1b"' not in src
    assert "esc.nivel_simple" in src


def test_el_predicado_de_subir_tiene_UNA_definicion():
    """Revisión previa a 0.2.0, menor #1. `Escalera.subio` nombraba el estado y
    `_texto_escalera` lo re-derivaba como `rec == "2"` en otro fichero: dos
    definiciones que pueden divergir, porque `rec` llega como parámetro y el
    llamante lo calcula como `esc.recomendado or esc.nivel_simple or "1a"`.

    Misma familia que los cuatro `umbral_vecino` con tres valores (BUG-0087) y
    las dos copias de la regla de λ (BUG-0080) — cometida el día después de
    arreglar ésas."""
    from tests._fuente import cuerpo_de, fuente_de

    import art.mcp_server as srv
    assert "esc.subio" in fuente_de(srv._texto_escalera)
    # `cuerpo_de` y no `fuente_de`: `ast.unparse` descarta los comentarios, y el
    # único `rec == "2"` que queda está DENTRO del comentario que explica por qué
    # se dejó de usar. La primera versión de esta prueba falló por eso — un
    # aserto sobre el código fuente tropezando con su propia explicación.
    assert 'rec == "2"' not in cuerpo_de(srv._texto_escalera)
