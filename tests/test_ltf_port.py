"""F0 — el simulador FLT portado de C, y el diccionario nivel ↔ diferencias.

Dos clases de prueba:

1. **Contra el C, al dígito.** `tests/fixtures/ltf_c_reference.json` lo generó
   `tests/ltf_referencia/harness.c`, cuyo bloque numérico está copiado VERBATIM
   de `SRC/LTF/LTF-1.0.2/ltf.c`. Copiado y no reescrito a propósito: si el
   puerto diverge, la divergencia es del puerto y no de una re-derivación de lo
   que el C "quería decir".

2. **El diccionario de docs/DISENO-nodo-intervencion.md §2.1**, escrito como
   afirmaciones ejecutables. Es la aritmética sobre la que descansa el nodo de
   episodios, y hasta ahora sólo existía en prosa.
"""
import json
from pathlib import Path

import numpy as np
import pytest

from art.ltf import respuesta_flt

FIXTURE = Path(__file__).parent / "fixtures" / "ltf_c_reference.json"
CASOS = json.loads(FIXTURE.read_text())["casos"]


# ───────────────── 1. al dígito contra el C ─────────────────

@pytest.mark.parametrize("caso", CASOS, ids=[c["nombre"] for c in CASOS])
def test_coincide_con_el_c_al_digito(caso):
    r = respuesta_flt(caso["omega"], caso["delta"],
                      b=caso["b"], K=caso["K"], d=caso["d"])
    assert np.array_equal(r.nu, np.array(caso["nu"])), "IRF diverge del C"
    assert np.array_equal(r.srf, np.array(caso["srf"])), "SRF diverge del C"


# ───────── 2. el diccionario nivel ↔ primeras diferencias ─────────
#
# `srf` con d=0 ES el camino del NIVEL; con d=1 es lo que se ve en la serie
# transformada.

def test_escalon_en_el_nivel_es_un_impulso_en_diferencias():
    nivel = respuesta_flt([2.5], K=8, d=0).srf
    assert np.allclose(nivel, 2.5), "el nivel se queda en ω₀: permanente"

    dif = respuesta_flt([2.5], K=8, d=1).srf
    assert dif[0] == pytest.approx(2.5)
    assert np.allclose(dif[1:], 0.0), "UN impulso y nada más"
    assert dif.sum() == pytest.approx(2.5), "ganancia = ω₀ ≠ 0: permanente"


def test_impulso_en_el_nivel_son_dos_impulsos_que_se_compensan():
    """ω=(3,3) ⟹ ω(1)=3−3=0: dos escalones con ganancia nula."""
    r = respuesta_flt([3.0, 3.0], K=8, d=0)
    assert r.omega_1 == pytest.approx(0.0)
    assert r.transitorio
    assert r.duracion_episodio == 1, "un solo período alterado"
    assert r.srf[0] == pytest.approx(3.0)
    assert np.allclose(r.srf[1:], 0.0), "el nivel vuelve a la base"

    dif = respuesta_flt([3.0, 3.0], K=8, d=1).srf
    assert dif[0] == pytest.approx(+3.0)
    assert dif[1] == pytest.approx(-3.0)
    assert np.allclose(dif[2:], 0.0)
    assert dif.sum() == pytest.approx(0.0), "ganancia nula: transitorio"


def test_dos_impulsos_en_el_nivel_son_tres_en_diferencias():
    """ω=(6,2,4) ⟹ ω(1)=6−2−4=0: tres escalones con ganancia nula.

    El nivel queda 6 en T y 4 en T+1 — DOS impulsos en el nivel — y en primeras
    diferencias se ven TRES: +ω₀, ω₁−ω₀, −ω₁ con ω₀=6, ω₁=4.
    """
    r = respuesta_flt([6.0, 2.0, 4.0], K=8, d=0)
    assert r.omega_1 == pytest.approx(0.0)
    assert r.duracion_episodio == 2, "episodio de dos períodos"
    assert r.srf[0] == pytest.approx(6.0)
    assert r.srf[1] == pytest.approx(4.0)
    assert np.allclose(r.srf[2:], 0.0)

    dif = respuesta_flt([6.0, 2.0, 4.0], K=8, d=1).srf
    assert dif[0] == pytest.approx(+6.0)          # +ω₀
    assert dif[1] == pytest.approx(4.0 - 6.0)     # ω₁ − ω₀
    assert dif[2] == pytest.approx(-4.0)          # −ω₁
    assert np.allclose(dif[3:], 0.0)
    assert dif.sum() == pytest.approx(0.0)


def test_la_ganancia_lleva_los_signos_de_la_convencion_de_fue():
    """ω(1) = ω₀ − ω₁ − ⋯, no la suma. Es lo que costó BUG-0066."""
    r = respuesta_flt([0.80, -0.30], [0.50], K=200)
    assert r.omega_1 == pytest.approx(0.80 - (-0.30))     # 1.10
    assert r.omega_1 != pytest.approx(sum([0.80, -0.30]))  # 0.50, la ingenua
    assert r.gain == pytest.approx(2.20)
    assert r.srf[-1] == pytest.approx(2.20, abs=1e-9), "la acumulada converge a la ganancia"


# ───────────────── 3. las guardas ─────────────────

def test_d_igual_a_dos_se_niega_y_dice_por_que():
    with pytest.raises(ValueError, match="RAMPA"):
        respuesta_flt([1.0], K=10, d=2)


def test_la_ventana_tiene_que_caber():
    with pytest.raises(ValueError, match="mayor que s"):
        respuesta_flt([1.0, 2.0, 3.0], K=2)


def test_retardo_muerto_negativo():
    with pytest.raises(ValueError, match="hacia atrás"):
        respuesta_flt([1.0], K=10, b=-1)


def test_retardo_muerto_desplaza_y_no_deforma():
    sin_b = respuesta_flt([1.20, -0.50], [0.45], K=20, b=0)
    con_b = respuesta_flt([1.20, -0.50], [0.45], K=20, b=3)
    assert np.allclose(con_b.nu[:3], 0.0)
    assert np.allclose(con_b.nu[3:], sin_b.nu[:-3])


def test_denominador_unitario_deja_la_ganancia_sin_definir():
    r = respuesta_flt([1.0, 0.3], [1.0], K=10)
    assert np.isnan(r.gain), "δ(1)=0: ganancia no acotada, modelo inadmisible"


# ───────────────── 4. la presentación ─────────────────

def test_describe_lee_transitorio_y_permanente():
    from art.ltf import describe_ltf
    d = describe_ltf([6.0, 2.0, 4.0], K=12)
    assert "TRANSITORIO" in d.summary
    assert d.data["duracion_episodio"] == 2
    assert d.figure_b64 and len(d.figure_b64) > 1000

    d = describe_ltf([2.5], K=12)
    assert "PERMANENTE" in d.summary
    assert d.data["duracion_episodio"] is None
    assert d.data["gain"] == pytest.approx(2.5)


def test_describe_avisa_de_la_ganancia_no_acotada():
    from art.ltf import describe_ltf
    d = describe_ltf([1.0, 0.3], [1.0], K=12)
    assert "INADMISIBLE" in d.summary


def test_la_herramienta_mcp_esta_registrada():
    import art.mcp_server as srv
    assert hasattr(srv, "intervention_plot")
