"""BUG-0171 — la fecha extramuestral se comparaba como TEXTO.

`evento_desde="03/2022"` sobre un conjunto que contiene `3/2022×4` respondía «no
coincide con ningún arranque candidato» — y la tabla, en la misma salida, listaba
`3/2022×4`.

La causa era `c.fecha == self.info.desde`, y las etiquetas se construyen **sin
cero a la izquierda** mientras la llamada 1 del nodo imprime las fechas **con**
cero. **El uso normal fallaba**: el analista copiaba la fecha de la salida
anterior y no se la aceptaban.

Lo que se pierde no es cosmético. `evento_desde` es una de las dos cosas que
identifican de verdad la configuración cuando el dato no identifica —«la fecha en
que empezó el suceso fija el arranque, y con el arranque fijo el resto se
estima»—, así que perderla deja la elección al AIC. Y en el run 3 el veredicto,
la figura y la «Siguiente llamada» siguieron proponiendo otra configuración sin
que nada indicara que la declaración se había descartado.
"""
import pytest

from art.configuracion import (Candidato, ConjuntoCandidatos, InfoExtramuestral,
                               describe_configuraciones, normaliza_fecha)

_F = "prueba sintética de BUG-0171"


def _cand(fecha, n=4, aic=100.0):
    return Candidato(arranque_resid=240, n_escalones=n, aic=aic, omega_1=-1.0,
                     se_omega_1=0.1, wald_p=1e-6, fecha=fecha, fecha_fin=fecha,
                     etiqueta=f"{fecha}×{n}", model=object())


def _conj(fechas, desde):
    c = [_cand(f, aic=100.0 + i) for i, f in enumerate(fechas)]
    return ConjuntoCandidatos(candidatos=c, info=InfoExtramuestral(
        desde=desde, naturaleza="permanente", fuente=_F, aportada_por="analista"))


# ── el normalizador ────────────────────────────────────────────────────────

@pytest.mark.parametrize("escrito,esperado", [
    ("Q3/2008", (3, 2008)),
    ("3/2008", (3, 2008)),
    ("03/2008", (3, 2008)),        # ← el que fallaba
    ("2008-03", (3, 2008)),
    ("2008/03", (3, 2008)),
    ("T3/2008", (3, 2008)),        # trimestre en castellano
    ("q3/2008", (3, 2008)),
    (" 03 / 2008 ", (3, 2008)),
    ("2008", (1, 2008)),
])
def test_se_reconocen_las_formas_que_un_analista_escribe(escrito, esperado):
    assert normaliza_fecha(escrito) == esperado


@pytest.mark.parametrize("basura", ["", "vaya", "marzo de 2008", "2008-13-99x", None])
def test_lo_que_no_es_una_fecha_devuelve_None(basura):
    assert normaliza_fecha(basura) is None


# ── el caso del run 3 ──────────────────────────────────────────────────────

@pytest.mark.parametrize("escrito", ["03/2022", "3/2022", "2022-03", "Q3/2022"])
def test_el_cero_a_la_izquierda_deja_de_decidir(escrito):
    """Cuatro formas de escribir la misma fecha; las cuatro fijan el candidato."""
    cj = _conj(["2/2022", "3/2022"], escrito)
    f = cj.fijado_por_lo_extramuestral
    assert f is not None, f"«{escrito}» sigue sin encontrar `3/2022`"
    assert f.etiqueta == "3/2022×4"


def test_una_fecha_que_de_VERDAD_no_esta_sigue_sin_encajar():
    """Normalizar no puede volverlo permisivo: si la fecha no está, no está."""
    assert _conj(["2/2022", "3/2022"], "07/2022").fijado_por_lo_extramuestral is None


def test_el_aviso_dice_CUALES_hay():
    """«No coincide» a secas sugiere que el analista se equivocó, y la mitad de
    las veces la fecha que escribió es la que la herramienta imprimió antes."""
    t = describe_configuraciones(_conj(["2/2022", "3/2022"], "07/2022")).summary
    assert "no coincide con ningún arranque candidato" in t
    assert "`2/2022`" in t and "`3/2022`" in t, "no lista los arranques disponibles"


def test_sin_fecha_declarada_no_fija_nada():
    cj = ConjuntoCandidatos(candidatos=[_cand("3/2022")],
                            info=InfoExtramuestral(naturaleza="permanente",
                                                   fuente=_F))
    assert cj.fijado_por_lo_extramuestral is None


def test_los_trimestrales_siguen_encajando():
    """El formato `QN/AAAA` es el que el sistema usa para freq=4: no puede
    romperse al arreglar el mensual."""
    cj = _conj(["Q2/2008", "Q3/2008"], "Q3/2008")
    assert cj.fijado_por_lo_extramuestral.etiqueta == "Q3/2008×4"
    # y da igual cómo lo escriba el analista
    assert _conj(["Q2/2008", "Q3/2008"], "3/2008").fijado_por_lo_extramuestral \
        .etiqueta == "Q3/2008×4"


def test_la_fecha_fijada_LLEGA_al_veredicto():
    """Lo que el defecto rompía de verdad: con la fecha perdida, el veredicto
    seguía proponiendo otra configuración sin decir que la había descartado."""
    d = describe_configuraciones(_conj(["2/2022", "3/2022"], "03/2022"))
    assert "3/2022" in d.summary
    assert "La fecha declarada fija la configuración" in d.summary
