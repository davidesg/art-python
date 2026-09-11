"""BUG-0157 — el aviso de discrepancia usaba un contraste que no ve el suceso.

Cuando el analista declaraba `evento_naturaleza="transitorio"` y el contraste de
ganancia rechazaba ω(1)=0, la herramienta avisaba de que **la explicación no
concuerda con el contraste**, y lo trataba como razón para no fiarse de la
información extramuestral.

En ITCER eso se dijo sobre `Q2/2008×3`, que cubre hasta **Q4/2008**, mientras el
analista describía una recuperación **desde 2009Q2** — dos trimestres fuera del
tramo. El contraste no podía verla.

La razón es de forma, no de delimitación: ω(1)=0 dice «el nivel vuelve **en el
último período que la especificación cubre**», y en ningún otro. Rechazarlo
descarta *esa* vuelta, no cualquier vuelta. Y como `naturaleza` no lleva fecha de
vuelta, **la discrepancia nunca se puede establecer**: son dos afirmaciones
distintas.

El nodo de intervención existe para incorporar lo que el analista sabe y los
datos no dicen. Un aviso que declara «no concuerda» cuando la discrepancia la
produce la propia forma enseña al analista a desconfiar de su información, que
es lo contrario de lo que el nodo pretende.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.configuracion import (BANDA_AIC, Candidato, ConjuntoCandidatos,
                               InfoExtramuestral, describe_configuraciones)

_FUENTE = "prueba sintética de BUG-0157"


def _conj(cands, naturaleza="transitorio", desde=""):
    return ConjuntoCandidatos(
        candidatos=cands, dominio="price_index",
        info=InfoExtramuestral(desde=desde, naturaleza=naturaleza,
                               fuente=_FUENTE, aportada_por="analista"))


def _cand(arr, n, aic, om1, se, wald_p, fecha, fin):
    return Candidato(arranque_resid=arr, n_escalones=n, aic=aic,
                     omega_1=om1, se_omega_1=se, wald_p=wald_p,
                     fecha=fecha, fecha_fin=fin, etiqueta=f"{fecha}×{n}",
                     model=object())


# ── el caso de ITCER, con sus números ───────────────────────────────────────

@pytest.fixture
def itcer():
    """Los tres candidatos tal como salieron en la corrida guiada.

    Todos acaban en Q4/2008 porque la marcha hacia delante para en el primer
    residuo tranquilo. La recuperación que el analista describe es de 2009Q2.
    """
    return _conj([
        _cand(17, 3, 381.93, -21.1642, 3.937, 1e-7, "Q2/2008", "Q4/2008"),
        _cand(18, 2, 384.16, -16.2225, 3.278, 1e-6, "Q3/2008", "Q4/2008"),
        _cand(19, 1, 387.15, -10.7709, None,  None, "Q4/2008", "Q4/2008"),
    ])


def test_ya_no_se_afirma_una_discrepancia_que_no_se_puede_establecer(itcer):
    assert itcer.el_contraste_no_alcanza_la_vuelta is True
    assert itcer.concuerda_con_lo_extramuestral is None, (
        "sigue afirmando que la explicación del analista no concuerda")


def test_el_aviso_dice_DONDE_situa_el_contraste_la_vuelta(itcer):
    txt = describe_configuraciones(itcer).summary
    assert "SITÚA la vuelta" in txt
    assert "Q4/2008" in txt, "no dice dónde cae la vuelta que sí contrasta"
    assert "no concuerda con el contraste" not in txt


def test_el_aviso_dice_que_la_referencia_no_la_eligio_el_analista(itcer):
    """Sin `evento_desde` la comparación es contra el de MEJOR AIC. Decirlo
    importa: el analista no nombró esa configuración."""
    txt = describe_configuraciones(itcer).summary
    assert "mejor AIC" in txt and "evento_desde" in txt


def test_y_dice_que_NINGUNA_configuracion_llega_mas_lejos(itcer):
    """El techo del conjunto es un hecho calculado, no prosa: la marcha hacia
    delante para en el primer residuo tranquilo."""
    assert itcer.vuelta_mas_tardia == "Q4/2008"
    txt = describe_configuraciones(itcer).summary
    assert "ninguna" in txt.lower() and "Q4/2008" in txt
    assert "dos intervenciones" in txt.lower()


def test_la_recomendacion_no_desmiente_al_analista(itcer):
    """Decía «el dato identifica la configuración: … PERMANENTE», sin matiz,
    justo después de que el analista declarara transitorio."""
    rec = describe_configuraciones(itcer).recommendation
    assert "no desmiente" in rec
    assert "ganancia NETA" in rec or "ganancia neta" in rec.lower()


def test_la_configuracion_de_UN_escalon_no_puede_volver_de_ninguna_manera(itcer):
    """El caso extremo: con un solo ω, ω(1)=ω₀. Las dos únicas lecturas son «se
    desplaza» y «no pasó nada»."""
    uno = itcer.candidatos[2]
    assert uno.puede_expresar_una_vuelta is False
    assert itcer.candidatos[0].puede_expresar_una_vuelta is True

    c = _conj([_cand(19, 1, 387.15, -10.77, 1.0, 1e-8, "Q4/2008", "Q4/2008")])
    assert c.referencia.puede_expresar_una_vuelta is False
    txt = describe_configuraciones(c).summary
    assert "un solo ω" in txt and "por construcción" in txt


# ── lo que NO debe cambiar ──────────────────────────────────────────────────

def test_permanente_declarado_sigue_pudiendo_discrepar():
    """La asimetría es real y deliberada. «Transitorio» sin fecha de vuelta no
    es falsable por este contraste; «permanente» sí: una vuelta DENTRO del tramo
    contradice que el nivel se quedara desplazado."""
    c = _conj([_cand(17, 3, 381.93, -0.4, 2.0, 0.84, "Q2/2008", "Q4/2008")],
              naturaleza="permanente")
    assert c.el_contraste_no_alcanza_la_vuelta is False
    assert c.concuerda_con_lo_extramuestral is False
    assert "no concuerda con el contraste" in describe_configuraciones(c).summary


def test_transitorio_que_el_contraste_CONFIRMA_sigue_concordando():
    c = _conj([_cand(17, 3, 381.93, -0.4, 2.0, 0.84, "Q2/2008", "Q4/2008")])
    assert c.el_contraste_no_alcanza_la_vuelta is False
    assert c.concuerda_con_lo_extramuestral is True
    assert "concuerda" in describe_configuraciones(c).summary


def test_sin_naturaleza_declarada_no_se_avisa_de_nada():
    c = ConjuntoCandidatos(
        candidatos=[_cand(17, 3, 381.93, -21.16, 3.9, 1e-7, "Q2/2008", "Q4/2008")],
        info=InfoExtramuestral(desde="Q2/2008", aportada_por="analista"))
    assert c.el_contraste_no_alcanza_la_vuelta is False
    assert c.concuerda_con_lo_extramuestral is None
    txt = describe_configuraciones(c).summary
    assert "SITÚA la vuelta" not in txt and "no concuerda" not in txt


def test_un_escalon_transitorio_no_dice_que_vuelve_tras_cero_periodos():
    """`en_palabras` decía «vuelve a la línea base tras 0 período(s)», que no es
    una vuelta: es que no pasó nada."""
    uno = _cand(19, 1, 387.15, -0.1, 5.0, 0.98, "Q4/2008", "Q4/2008")
    assert uno.transitorio is True
    t = uno.en_palabras
    assert "0 período" not in t
    assert "no deja efecto medible" in t

    tres = _cand(17, 3, 381.93, -0.4, 2.0, 0.84, "Q2/2008", "Q4/2008")
    assert "Q4/2008" in tres.en_palabras, "no dice CUÁNDO vuelve"


# ── la escalera sin salida tiene que nombrar la tercera lectura ─────────────

def test_la_escalera_sin_salida_nombra_la_vuelta_diferida():
    """En ITCER la escalera dijo «ninguna forma resuelve el suceso» y ofreció
    dos salidas: redelimitar, o que no sea un suceso. Faltaba la que el caso
    necesitaba — la caída y la recuperación son DOS tramos, y el vecino anómalo
    quedaba a los dos lados, que es justo su firma.

    El callejón está escrito en dos sitios, así que se comprueban los dos: un
    aviso que sólo la mitad de los carriles da es medio aviso.
    """
    import pathlib
    import re

    for ruta in ("src/art/escalera.py", "src/art/mcp_server.py"):
        # se leen los FICHEROS y no `inspect.getsource`: sobre un módulo sería
        # legítimo, pero el fuente es lo que se quiere mirar y así no hay que
        # pedirle una excepción a la regla de la suite.
        src = re.sub(r'"\s*\n\s*"', "", pathlib.Path(ruta).read_text())
        i = src.find("estructura sin modelizar")
        assert i > 0, f"{ruta}: se movió el texto del callejón"
        tramo = src[i:i + 900]
        assert "vuelta DIFERIDA" in tramo, (
            f"{ruta}: el callejón no nombra la tercera lectura")
        assert "ganancia_neta" in tramo, (
            f"{ruta}: la nombra pero no dice con qué contrastarla")
