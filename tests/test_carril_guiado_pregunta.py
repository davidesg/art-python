"""En guiado decide el ANALISTA, y la salida tiene que preguntárselo.

BUG-0094, reabierto. La primera vez lo cerré construyendo las cuatro etapas del
método —ESPECIFICACIÓN/ESTIMACIÓN/DIAGNOSIS/REFORMULACIÓN— y eso estaba mal para
esta salida: son la forma del REGISTRO. Al analista le sirven mal, porque
empiezan por la especificación que acaba de decidir él y terminan **anunciando**
la reformulación, que era su decisión. Con esa forma el guiado se comporta como
un autónomo que además narra.

Y había una causa concreta: `confirm_and_estimate` —la herramienta del carril
guiado— no declaraba su modo, así que el sobre siempre tomaba la forma del
registro.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.mcp_server import (FIN_DE_TURNO_GUIADO, SECCIONES_GUIADO,
                            _alternativas_desde, _conclusiones_desde,
                            envuelve_iteracion, es_guiado)
from art.pipeline import _RESCALE_FACTOR, _write_inp


@pytest.fixture(scope="module")
def salida_guiada(tmp_path_factory):
    d = tmp_path_factory.mktemp("guiado")
    rng = np.random.default_rng(2)
    y = np.cumsum(rng.standard_normal(144) * 0.4) + 100.0
    y[60] += 6.0
    y[61] -= 5.0
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="ITCER")
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _write_inp(ts, m, str(d / "ITCER.inp"))
        ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
        r = ce(str(d / "ITCER.inp"), str(d / "ITCER_m00.inp"), lam=0.0, d=1,
               D=0, p=0, q=0, n_harmonics=2, estimate_mu=True,
               guion_decision="m00")
    return r[0].text


# ── la forma ──────────────────────────────────────────────────────────

def test_las_cuatro_secciones_en_orden(salida_guiada):
    pos = [salida_guiada.index(f"· {s}") for s in SECCIONES_GUIADO]
    assert pos == sorted(pos), "las secciones no salen en orden"


def test_el_modelo_va_PRIMERO(salida_guiada):
    """El analista ya sabe de dónde viene el modelo: lo decidió él. Lo que
    necesita ver antes que nada es lo que tiene delante."""
    assert salida_guiada.index("MODELO ESTIMADO") < salida_guiada.index("DIAGNOSIS")


def test_hay_conclusiones_y_no_solo_numeros(salida_guiada):
    """La diagnosis es una lista de contrastes; la conclusión es el veredicto.
    Sin ella el analista tiene que recomponerlo, y cada LLM lo recompone
    distinto."""
    i = salida_guiada.index("· CONCLUSIONES")
    j = salida_guiada.index("· DECISIÓN")
    assert "se sostiene" in salida_guiada[i:j].lower()


def test_termina_en_la_pregunta(salida_guiada):
    """La marca cierra el turno: es lo que hace comprobable que se para."""
    assert salida_guiada.rstrip().endswith(FIN_DE_TURNO_GUIADO)


def test_no_anuncia_la_reformulacion(salida_guiada):
    """Anunciarla ES haber decidido."""
    assert "· REFORMULACIÓN" not in salida_guiada


# ── las alternativas ──────────────────────────────────────────────────

def test_hay_varias_alternativas(salida_guiada):
    i = salida_guiada.index("· DECISIÓN")
    bloque = salida_guiada[i:]
    assert "**A)**" in bloque and "**B)**" in bloque


def test_cada_alternativa_trae_su_llamada_exacta(salida_guiada):
    """Lo que evita los turnos de ida y vuelta averiguando los argumentos."""
    import re
    i = salida_guiada.index("· DECISIÓN")
    j = salida_guiada.index(FIN_DE_TURNO_GUIADO)
    trozos = re.split(r"\n\*\*[A-Z]\)\*\* ", salida_guiada[i:j])[1:]
    assert len(trozos) >= 2, trozos
    for t in trozos:
        assert "`" in t and "(" in t, f"alternativa sin llamada: {t[:80]}"


def test_siempre_se_puede_volver_atras(salida_guiada):
    """El recorrido es un grafo: retroceder es el método, no un fallo."""
    assert "guion_map" in salida_guiada[salida_guiada.index("· DECISIÓN"):]


def test_lo_mas_obvio_primero(salida_guiada):
    """La regla de Treadway: un anómalo sin tratar contamina la estimación de
    todo lo demás, así que la intervención va antes que el orden ARMA."""
    i = salida_guiada.index("· DECISIÓN")
    bloque = salida_guiada[i:]
    assert bloque.index("Intervenir") < bloque.index("ESTACIONAL")


# ── el generador de alternativas, por casos ───────────────────────────

class _Diag:
    def __init__(self, **kw):
        self.data = kw


def test_un_modelo_limpio_ofrece_ADOPTAR():
    """Adoptar es una decisión y hay que poder tomarla explícitamente."""
    alts = _alternativas_desde(_Diag(white_noise=True, normal=True,
                                     n_extreme=0, intervention_hints=[]))
    assert any("Adoptar" in a for a in alts)
    assert any("Sobreparametrizar" in a for a in alts)


def test_JB_solo_manda_a_los_anomalos_no_a_la_distribucion():
    alts = _alternativas_desde(_Diag(white_noise=True, normal=False,
                                     n_extreme=0, intervention_hints=[]))
    assert any("anómalos antes que la distribución" in a for a in alts)


def test_la_conclusion_dice_el_veredicto():
    c = _conclusiones_desde(_Diag(white_noise=False, normal=True, n_extreme=0,
                                  q_fails=["lag 12 (Q=28.5, p=0.005)"]))
    assert "NO se sostiene" in c
    assert "lag 12" in c
    c2 = _conclusiones_desde(_Diag(white_noise=True, normal=True, n_extreme=0))
    assert "se sostiene" in c2 and "NO se sostiene" not in c2


def test_sin_alternativas_se_DICE(tmp_path):
    """Callarlo deja al analista sin saber si no hay opciones o nadie las buscó."""
    t = envuelve_iteracion(nombre="X", modo="guiado", ecuacion="y=a",
                           diagnosis="d", conclusiones="c", alternativas=[])
    assert "No se han derivado alternativas" in t
    assert t.rstrip().endswith(FIN_DE_TURNO_GUIADO)


# ── el autónomo NO cambia ─────────────────────────────────────────────

def test_el_autonomo_sigue_con_las_cuatro_ETAPAS():
    """Son la forma del registro, y allí no hay a quién preguntar."""
    t = envuelve_iteracion(nombre="X", modo="autónomo", ecuacion="y=a",
                           diagnosis="d", reformulacion="r")
    assert "· ESPECIFICACIÓN" in t and "· REFORMULACIÓN" in t
    assert FIN_DE_TURNO_GUIADO not in t


def test_el_autonomo_no_pregunta():
    t = envuelve_iteracion(nombre="X", modo="autónomo", ecuacion="y=a",
                           diagnosis="d", conclusiones="c",
                           alternativas=["A", "B"])
    assert "Tu decisión" not in t


@pytest.mark.parametrize("modo,esperado", [
    ("guiado", True), ("guiado (spec confirmada)", True),
    ("autónomo", False), ("", False),
])
def test_el_carril_se_reconoce_por_el_modo(modo, esperado):
    assert es_guiado(modo) is esperado


# ── la causa, fijada ──────────────────────────────────────────────────

def test_confirm_and_estimate_declara_que_es_guiado():
    """Era la causa: la herramienta del carril guiado no declaraba su modo, así
    que el sobre le daba la forma del registro."""
    from tests._fuente import fuente_de
    ce = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    src = fuente_de(ce)
    assert 'modo="guiado"' in src
    assert "_conclusiones_desde(" in src and "_alternativas_desde(" in src


def test_las_instrucciones_prohiben_decidir_por_el_analista():
    assert "EL QUE DECIDE ES EL ANALISTA" in srv._INSTRUCTIONS
    assert "TU TURNO TERMINA EN ESA MARCA" in srv._INSTRUCTIONS
