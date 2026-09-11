"""BUG-0155 — `evento_naturaleza` no decía qué admite, y lo que admitía no bastaba.

Dos defectos, y el segundo es el de fondo.

**1 · No decía qué admite.** El esquema publicaba `{"type": "string"}` a secas:
ni descripción ni valores. Lo único que los enumeraba era la prosa de un
docstring, que el cliente puede recortar (BUG-0116), así que el valor válido se
aprendía **por el mensaje de error**. En la corrida de ITCER el analista metió la
frase entera del suceso y se la rechazaron.

**2 · El enum no cubría lo que hay que decir.** El suceso de 2008-09 es una
caída seguida de una recuperación PARCIAL: el nivel no vuelve —no es
transitorio— y tampoco se queda donde cayó —no es el permanente que el contraste
rotula—. Había que elegir entre dos respuestas equivocadas, y encima el aviso de
discrepancia se disparaba comparando lo declarado con un contraste que no tenía
esa casilla.

La tercera casilla existe AHORA porque existe el instrumento que la mide: la
ganancia neta de dos intervenciones (BUG-0157). Una casilla que nada puede
contrastar sería peor que no tenerla.
"""
import asyncio
import os

import pytest

os.environ.setdefault("ART_NO_VIEWER", "1")

from art.configuracion import (NATURALEZAS, Candidato, ConjuntoCandidatos,
                               InfoExtramuestral, describe_configuraciones,
                               normaliza_naturaleza)

_F = "prueba sintética de BUG-0155"


def _cand(n=3, wald_p=1e-7):
    return Candidato(arranque_resid=17, n_escalones=n, aic=381.93,
                     omega_1=-21.16, se_omega_1=3.94, wald_p=wald_p,
                     fecha="Q2/2008", fecha_fin="Q4/2008",
                     etiqueta=f"Q2/2008×{n}", model=object())


def _conj(naturaleza):
    return ConjuntoCandidatos(
        candidatos=[_cand()], dominio="price_index",
        info=InfoExtramuestral(naturaleza=naturaleza, fuente=_F,
                               aportada_por="analista"))


# ── 1 · el enum viaja en el ESQUEMA, no en la prosa ────────────────────────

@pytest.mark.parametrize("tool", ["guided_intervention",
                                  "incident_configurations"])
def test_el_esquema_publica_los_valores(tool):
    """Lo que decide tiene que ir donde el cliente NO recorta. Un `Literal` no
    es prosa: es una restricción que el cliente no puede ni construir mal."""
    import art.mcp_server as srv
    ts = asyncio.run(srv.mcp.list_tools())
    t = next(x for x in ts if x.name == tool)
    prop = (t.inputSchema or {})["properties"]["evento_naturaleza"]
    assert "enum" in prop, f"{tool}: `evento_naturaleza` sigue siendo string libre"
    assert set(prop["enum"]) == {""} | set(NATURALEZAS)


def test_son_tres_lecturas_y_no_dos():
    assert NATURALEZAS == ("permanente", "transitorio", "recuperacion_parcial")


# ── 2 · y si un cliente no lo respeta, el error ENUMERA ────────────────────

def test_el_error_dice_cuales_son_los_validos():
    """Se aprendía por el error; el error al menos tiene que enseñar."""
    with pytest.raises(ValueError) as e:
        InfoExtramuestral(naturaleza="transitorio: crisis financiera global",
                          fuente=_F)
    t = str(e.value)
    for v in NATURALEZAS:
        assert f"`{v}`" in t, f"el error no nombra {v}"
    assert "fuente" in t, "no dice dónde va la descripción del suceso"


def test_la_frase_entera_va_a_fuente_no_a_naturaleza():
    """El error exacto de la corrida de ITCER."""
    with pytest.raises(ValueError, match="La descripción del suceso va en"):
        InfoExtramuestral(
            naturaleza=("transitorio: crisis financiera global; depreciación "
                        "fuerte de las monedas de los socios comerciales"),
            fuente=_F)


@pytest.mark.parametrize("escrito", [
    "recuperación parcial", "Recuperacion-Parcial", "recuperacion_parcial",
    "  RECUPERACIÓN  PARCIAL  ", "parcial",
])
def test_no_se_castiga_al_analista_por_una_tilde(escrito):
    assert normaliza_naturaleza(escrito) == "recuperacion_parcial"
    assert InfoExtramuestral(naturaleza=escrito,
                             fuente=_F).naturaleza == "recuperacion_parcial"


def test_las_dos_de_siempre_siguen_valiendo():
    for v in ("permanente", "transitorio"):
        assert InfoExtramuestral(naturaleza=v, fuente=_F).naturaleza == v
    assert InfoExtramuestral().naturaleza == ""


def test_declarar_naturaleza_sin_fuente_sigue_sin_valer():
    """No se afirma que un suceso fue permanente sin decir por qué se sabe. La
    tercera casilla no relaja eso."""
    with pytest.raises(ValueError, match="sin `fuente`"):
        InfoExtramuestral(naturaleza="recuperacion_parcial")


# ── 3 · la tercera lectura no la decide este contraste, y se dice ──────────

def test_la_tercera_no_cabe_en_un_contraste_de_dos_casillas():
    c = _conj("recuperacion_parcial")
    assert c.la_tercera_lectura_no_cabe_en_este_contraste is True
    assert c.concuerda_con_lo_extramuestral is None, (
        "afirma concordancia sobre una lectura que no sabe distinguir")


def test_y_manda_al_instrumento_que_SI_la_mide():
    c = _conj("recuperacion_parcial")
    d = describe_configuraciones(c)
    assert "dos casillas" in d.summary
    assert "ganancia NETA" in d.summary
    assert "ganancia_neta=[i, j]" in d.summary, "no dice con qué contrastarla"
    assert "no lo decide esta llamada" in d.recommendation


def test_no_se_confunde_con_el_aviso_de_la_vuelta_diferida():
    """`transitorio` rechazado y `recuperacion_parcial` son dos estados
    distintos con dos mensajes distintos (BUG-0157 y BUG-0155)."""
    t = describe_configuraciones(_conj("transitorio")).summary
    p = describe_configuraciones(_conj("recuperacion_parcial")).summary
    assert "SITÚA la vuelta" in t and "dos casillas" not in t
    assert "dos casillas" in p and "SITÚA la vuelta" not in p


def test_las_otras_dos_lecturas_no_cambian():
    assert _conj("permanente").la_tercera_lectura_no_cabe_en_este_contraste is False
    assert _conj("transitorio").la_tercera_lectura_no_cabe_en_este_contraste is False
    # y una `permanente` que el contraste confirma sigue concordando
    ok = ConjuntoCandidatos(
        candidatos=[_cand(wald_p=1e-7)],
        info=InfoExtramuestral(naturaleza="permanente", fuente=_F))
    assert ok.concuerda_con_lo_extramuestral is True


def test_el_dato_lo_publica_para_el_carril():
    d = describe_configuraciones(_conj("recuperacion_parcial"))
    assert d.data["tercera_lectura"] is True
    assert d.data["info"]["naturaleza"] == "recuperacion_parcial"
