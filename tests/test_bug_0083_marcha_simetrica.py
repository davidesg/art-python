"""BUG-0083 — la marcha del incidente sólo iba hacia atrás.

`arranques_candidatos` extendía el arranque hacia atrás mientras los vecinos
siguieran ACTIVOS, pero clavaba el final en el último extremo. Un suceso cuya
cola queda ENTRE el umbral de activo y el de extremo —el caso que la herramienta
existe para tratar— no generaba nunca la configuración larga.

Y el informe lo publicaba como *«el dato SÍ identifica la configuración»* con una
sola candidata construida: afirmar identificación sin haber comparado nada.
"""
import numpy as np
import pytest

from art.configuracion import (Candidato, ConjuntoCandidatos,
                               arranques_candidatos, describe_configuraciones)


# ───────────────── la marcha, ahora simétrica ─────────────────

def test_la_cola_por_detras_genera_la_configuracion_larga():
    """El caso de FOOD_UEM 12/2004: extremo +3.56, vecino −2.20 DESPUÉS."""
    z = [0.2, -0.4, 0.3, -0.1, 3.56, -2.2, 0.3, -0.2]
    c = arranques_candidatos(z, [4], d=1, umbral_activo=1.0)
    assert (4, 2) in c, "la configuración de dos escalones no se enumeró"
    assert (4, 1) in c, "la corta tiene que seguir estando: es la alternativa"


def test_la_cola_por_delante_sigue_funcionando():
    """El caso 02-03/2017, que ya funcionaba. No se rompe."""
    z = [0.2, -0.4, 0.3, 2.4, -3.8, -0.1, 0.3, -0.2]
    c = arranques_candidatos(z, [4], d=1, umbral_activo=1.0)
    assert (3, 2) in c and (4, 1) in c


def test_los_dos_lados_dan_el_mismo_juego_de_longitudes():
    """Es el MISMO mecanismo con el extremo en otro sitio. Si la herramienta
    trata uno y no el otro, lo que codifica no es el mecanismo."""
    delante = [0.2, -0.4, 0.3, 2.4, -3.8, -0.1, 0.3, -0.2]
    detras = [0.2, -0.4, 0.3, -0.1, 3.56, -2.2, 0.3, -0.2]
    ld = sorted(n for _, n in arranques_candidatos(delante, [4], d=1,
                                                   umbral_activo=1.0))
    lt = sorted(n for _, n in arranques_candidatos(detras, [4], d=1,
                                                   umbral_activo=1.0))
    assert ld == lt == [1, 2]


# ───────────────── lo que NO cambia ─────────────────

def test_sin_vecinos_activos_sigue_habiendo_un_solo_candidato():
    """Compatibilidad: el conjunto degenera exactamente en el de antes."""
    z = [0.1, -0.2, 0.1, 0.0, 3.9, 0.1, -0.1, 0.2]
    assert arranques_candidatos(z, [4], d=1, umbral_activo=1.0) == [(4, 1)]


def test_la_marcha_para_en_el_primer_vecino_inactivo():
    """No salta huecos: un residuo tranquilo corta el suceso."""
    z = [0.0, 2.0, 0.1, 3.9, 0.1, 2.0, 0.0, 0.0]
    #        ^activo  ^hueco ^ext ^hueco ^activo — ninguno de los dos entra
    assert arranques_candidatos(z, [3], d=1, umbral_activo=1.0) == [(3, 1)]


def test_el_tope_delante_acota():
    """Sin tope la cola larga se comería la serie entera; con tope, no."""
    z = [0.0, 0.0, 4.0] + [2.0] * 10
    corto = arranques_candidatos(z, [2], d=0, umbral_activo=1.0, tope_delante=2)
    largo = arranques_candidatos(z, [2], d=0, umbral_activo=1.0, tope_delante=9)
    assert max(n for _, n in corto) == 4      # finales 2,3,4 → n = f-2+2
    assert max(n for _, n in largo) == 11
    assert len(corto) < len(largo)


def test_no_se_sale_del_array_por_la_derecha():
    z = [0.0, 0.0, 4.0, 2.5]                  # el extremo activo es el último
    c = arranques_candidatos(z, [2], d=1, umbral_activo=1.0)
    assert c == [(2, 1), (2, 2)]


def test_no_hay_duplicados_y_el_orden_es_estable():
    z = [2.0, 4.0, 2.0]
    c = arranques_candidatos(z, [1], d=1, umbral_activo=1.0)
    assert len(c) == len(set(c))
    assert c == sorted(c)


# ───────────────── el informe deja de fabricar identificación ─────────────────

def _conj(n, banda=2.0):
    """n candidatos estimados, con AIC separados de sobra."""
    cs = [Candidato(arranque_resid=5, n_escalones=k + 1,
                    etiqueta=f"Q1/2005×{k+1}", fecha="Q1/2005",
                    model=object(), aic=100.0 + 10.0 * k, wald_p=0.30)
          for k in range(n)]
    return ConjuntoCandidatos(candidatos=cs, banda_aic=banda)


def test_una_sola_construida_no_es_identificacion():
    c = _conj(1)
    assert c.identificado is True          # sigue siendo True: sólo una en banda
    assert c.unica_construida is True      # pero no hubo nada que comparar


def test_varias_construidas_y_una_gana_si_es_identificacion():
    c = _conj(3)
    assert c.identificado is True
    assert c.unica_construida is False


def test_el_informe_no_dice_que_el_dato_identifica_si_solo_hubo_una():
    d = describe_configuraciones(_conj(1))
    assert "sí** identifica" not in d.summary
    assert "no hubo nada que comparar" in d.summary
    assert d.data["unica_construida"] is True
    assert d.data["n_construidas"] == 1


def test_el_informe_si_lo_dice_cuando_las_alternativas_perdieron():
    d = describe_configuraciones(_conj(3))
    assert "sí** identifica" in d.summary
    assert "Se construyeron 3" in d.summary
    assert d.data["unica_construida"] is False


def test_el_informe_dice_que_umbral_uso():
    d = describe_configuraciones(
        ConjuntoCandidatos(candidatos=_conj(1).candidatos, umbral_activo=1.5))
    assert "1.5σ" in d.summary or "1,5σ" in d.summary


def test_un_solo_escalon_se_dice_en_singular():
    """La rama de una sola candidata se imprime mucho más ahora; «1 escalones»
    delataba que la frase se montaba sin mirar el número."""
    c = Candidato(arranque_resid=5, n_escalones=1, fecha="10/2007",
                  model=object(), aic=1.0)
    assert "un escalón en el nivel" in c.en_palabras
    assert "1 escalones" not in c.en_palabras
