"""F2 — agrupar residuos extremos en EPISODIOS.

Hasta este nodo, un suceso que duraba tres períodos eran tres atípicos sueltos,
y la forma la decidía una comprobación de adyacencia que devolvía "step" o
"pulse". Costaba, medido: **16,24 puntos de AIC** por la segunda intervención
del episodio 2008-09 de la réplica, encontrada por **1 de 8** corridas.
"""
import numpy as np
import pytest

from art.episodes import (Episodio, agrupa_episodios, describe_episodios,
                          VENTANA_POR_DEFECTO)
from art.policy import decide_episodios, THRESHOLDS, DefaultPolicy


# ───────────────── la agrupación ─────────────────

def test_extremos_adyacentes_son_un_solo_suceso():
    eps = agrupa_episodios([(30, -4.5), (31, 3.9)], ventana=2)
    assert len(eps) == 1
    e = eps[0]
    assert (e.inicio, e.fin, e.duracion) == (30, 31, 2)
    assert e.n_extremos == 2
    assert not e.aislado


def test_extremos_lejanos_siguen_separados():
    eps = agrupa_episodios([(30, -4.5), (80, 3.9)], ventana=2)
    assert len(eps) == 2
    assert all(e.aislado for e in eps)


def test_la_ventana_es_la_que_decide():
    ext = [(10, -4.0), (13, 3.5)]          # hueco de 3
    assert len(agrupa_episodios(ext, ventana=2)) == 2
    assert len(agrupa_episodios(ext, ventana=3)) == 1


def test_la_union_es_por_encadenamiento_y_se_ve():
    """A-B y B-C dentro de ventana unen A, B y C aunque A y C estén lejos.

    Es la lectura natural de «el mismo suceso», y por eso el episodio publica
    duración, huecos y cohesión: para que la cadena se VEA en vez de esconderse
    detrás de un solo número.
    """
    e, = agrupa_episodios([(10, -4.0), (12, 3.0), (14, -3.2)], ventana=2)
    assert (e.inicio, e.fin) == (10, 14)
    assert e.duracion == 5 and e.n_extremos == 3
    assert e.huecos == [11, 13]
    assert e.cohesion == pytest.approx(3 / 5)
    assert e.parece_encadenado, "duración > 4: hay que mirarlo antes de intervenir"


def test_un_episodio_macizo_no_levanta_aviso():
    e, = agrupa_episodios([(30, -4.5), (31, 3.9), (32, -3.3)], ventana=1)
    assert e.cohesion == 1.0
    assert not e.parece_encadenado


# ────────── la forma general que implica (§2.2 del diseño) ──────────

@pytest.mark.parametrize("ext,L,n_esc", [
    ([(30, 4.0)],                            1, 2),
    ([(30, 4.0), (31, -3.5)],                2, 3),
    ([(30, 4.0), (31, -3.5), (32, 3.1)],     3, 4),
])
def test_un_episodio_de_duracion_L_son_L_mas_1_escalones(ext, L, n_esc):
    e, = agrupa_episodios(ext, ventana=1)
    assert e.duracion == L
    assert e.n_escalones == n_esc


def test_el_aislado_da_dos_escalones_que_es_donde_muere_la_dicotomia():
    """Un atípico solo ya no es «pulse» por regla: son DOS escalones, y si
    ω(1)=0 es impulso de nivel y si no, cambio de nivel. Lo decide el
    contraste."""
    e, = agrupa_episodios([(55, 4.4)], ventana=2)
    assert e.aislado and e.n_escalones == 2


# ────────── el desfase, que es BUG-0030 otra vez ──────────

def test_at_0based_aplica_el_desfase_de_la_diferenciacion():
    e, = agrupa_episodios([(30, -4.5), (31, 3.9)], ventana=2)
    assert e.at_0based(offset=0) == 29
    assert e.at_0based(offset=1) == 30            # d=1
    assert e.at_0based(offset=13) == 42           # mensual con d=1, D=1


# ────────── guardas y bordes ──────────

def test_sin_extremos_no_hay_episodios():
    assert agrupa_episodios([]) == []


def test_ventana_cero_se_niega():
    with pytest.raises(ValueError, match="al menos 1"):
        agrupa_episodios([(1, 4.0)], ventana=0)


def test_da_igual_el_orden_de_entrada():
    a = agrupa_episodios([(31, 3.9), (30, -4.5)], ventana=2)
    b = agrupa_episodios([(30, -4.5), (31, 3.9)], ventana=2)
    assert [(e.inicio, e.fin) for e in a] == [(e.inicio, e.fin) for e in b]


# ────────── la política ──────────

def test_la_ventana_esta_declarada_en_la_politica():
    assert THRESHOLDS["ventana_episodio"] == VENTANA_POR_DEFECTO
    assert decide_episodios([(30, -4.5), (31, 3.9)]) == \
           agrupa_episodios([(30, -4.5), (31, 3.9)], ventana=VENTANA_POR_DEFECTO)


def test_la_politica_la_expone_como_decision():
    eps = DefaultPolicy().decide_episodios([(30, -4.5), (31, 3.9)])
    assert len(eps) == 1 and eps[0].duracion == 2


# ────────── la presentación ──────────

def _residuos_con(pos_valores, n=80, semilla=0):
    r = np.random.default_rng(semilla).standard_normal(n)
    for i, v in pos_valores:
        r[i] = v
    return r


def test_describe_enseña_la_agrupacion_y_la_forma():
    r = _residuos_con([(29, -4.5), (30, 3.9), (55, 4.4)])
    ext = [(i + 1, r[i]) for i in range(len(r)) if abs(r[i]) > 3]
    d = describe_episodios(r, agrupa_episodios(ext, ventana=2), ventana=2)
    assert "3 escalones" in d.summary      # el episodio de dos períodos
    assert "2 escalones" in d.summary      # el aislado
    assert d.figure_b64 and len(d.figure_b64) > 1000
    assert len(d.data["episodios"]) == 2
    assert d.data["episodios"][0]["duracion"] == 2


def test_describe_avisa_del_encadenamiento():
    r = _residuos_con([(9, -4.0), (11, 3.4), (13, -3.6)])
    ext = [(i + 1, r[i]) for i in range(len(r)) if abs(r[i]) > 3]
    d = describe_episodios(r, agrupa_episodios(ext, ventana=2), ventana=2)
    assert "Avisos de agrupación" in d.summary
    assert "estructura" in d.summary


def test_describe_sin_extremos_no_se_rompe():
    r = _residuos_con([])
    d = describe_episodios(r, [], ventana=2)
    assert "Ninguno" in d.summary
    assert d.data["episodios"] == []


# ────────── lo que arregla el fallo medido ──────────

def test_el_escaneo_de_residuos_avisa_de_los_no_aislados():
    """El puntero dentro de `residual_outlier_scan`.

    La razón de que 7 de 8 corridas no encontraran el segundo choque es que
    nada en la salida decía que esos dos anómalos eran UN suceso. Una
    herramienta que nadie llama no lo arregla; el aviso donde el analista ya
    está mirando, sí. Aquí se fija que el aviso se dispara exactamente cuando
    hay un episodio no aislado.
    """
    juntos = decide_episodios([(30, -4.5), (31, 3.9)])
    assert [e for e in juntos if not e.aislado], "debe avisar"

    sueltos = decide_episodios([(30, -4.5), (80, 3.9)])
    assert not [e for e in sueltos if not e.aislado], "no debe avisar"


def test_la_herramienta_mcp_esta_registrada():
    import art.mcp_server as srv
    assert hasattr(srv, "residual_episodes")


# ────────── la SEGUNDA conversión: la duración ──────────
#
# Los residuos están diferenciados. Por el diccionario nivel↔diferencias, L
# impulsos en el nivel se ven como L+d extremos, así que la duración medida
# sobre residuos NO es la duración del suceso. Se descubrió comprobando el
# módulo de punta a punta: con d=1 y dos impulsos de nivel, el episodio salía de
# tres períodos y pedía cuatro escalones donde hacían falta tres.

def test_la_duracion_en_residuos_no_es_la_duracion_del_suceso():
    """Dos impulsos de nivel con d=1 dan TRES residuos extremos."""
    ext = [(100, 5.0), (101, -4.0), (102, 3.5)]
    e, = agrupa_episodios(ext, ventana=2, d=1)
    assert e.duracion == 3, "tres extremos en la serie diferenciada"
    assert e.duracion_nivel == 2, "pero DOS períodos alterados en el nivel"
    assert e.n_escalones == 3, "y tres escalones, no cuatro"


def test_sin_diferenciar_las_dos_duraciones_coinciden():
    e, = agrupa_episodios([(30, 4.0), (31, -3.5)], ventana=2, d=0)
    assert e.duracion == e.duracion_nivel == 2
    assert e.n_escalones == 3


def test_un_extremo_solo_con_d1_es_un_impulso_de_nivel():
    """Un solo residuo extremo con d=1 es un ESCALÓN en el nivel; dos
    consecutivos, un impulso. `aislado` se lee en el nivel."""
    e, = agrupa_episodios([(50, 4.2)], ventana=2, d=1)
    assert e.duracion_nivel == 1 and e.aislado
    assert e.n_escalones == 2


def test_la_politica_propaga_la_diferenciacion():
    e, = decide_episodios([(100, 5.0), (101, -4.0), (102, 3.5)], d=1)
    assert e.duracion_nivel == 2 and e.n_escalones == 3
