"""El guion como MAPA del laberinto, no como registro lineal.

El método es una búsqueda iterativa con vuelta atrás. Sus callejones sin salida
no son fallos del método: son el método funcionando. Lo que una iteración
fallida produce de valor no es el modelo que se descarta — es la RAZÓN, que es
lo único que impide volver a entrar por esa puerta.

Para eso el guion necesita tres cosas que antes no tenía: de qué versión
desciende cada versión, cuáles se abandonaron, y por qué.

Ver docs/ARCHITECTURE_REVIEW.md §5.1.
"""
import os
import tempfile

import numpy as np
import pytest

from art import mcp_server as A
from art.guion import (Guion, GuionEntry, GuionStats, load_guion,
                       infer_parent, abandon, safe_ancestor, path_to_root,
                       descendants)


# ── el mapa, sobre una estructura sintética ────────────────────────────────

def _entrada(v, nombre, padre):
    return GuionEntry(version=v, name=nombre, inp_path="/x/%s.inp" % nombre,
                      timestamp="", spec={},
                      stats=GuionStats(0.0, 0.0, 0.0, 0.0, None, None, 0),
                      equation="", decision="", rationale="",
                      problems_found="", next_version="", parent=padre)


@pytest.fixture
def arbol():
    """v1 → v2 → v3, y una rama v2 → v4 → v5."""
    g = Guion(series="S", analyst="", created="")
    for v, n, p in ((1, "m00", None), (2, "m10", 1), (3, "m20", 2),
                    (4, "alt", 2), (5, "alt2", 4)):
        g.entries.append(_entrada(v, n, p))
    return g


def test_descendientes_incluyen_los_indirectos(arbol):
    assert descendants(arbol, 2) == [3, 4, 5]
    assert descendants(arbol, 3) == []


def test_el_camino_a_la_raiz_es_la_cadena_de_decisiones(arbol):
    assert path_to_root(arbol, 5) == [1, 2, 4, 5]


def test_abandonar_arrastra_a_los_descendientes(arbol):
    """Una decisión contaminada contamina lo que viene después: ésa es la
    propiedad que obliga a volver atrás en vez de parchear hacia delante."""
    # `abandon` devuelve (abandonadas, recolocadas) desde BUG-0037: los MODELOS
    # descendientes se arrastran igual que siempre, y sólo los NODOS de decisión
    # se recolocan en el tronco. Este árbol es todo modelos, así que no se
    # recoloca nada y la cascada es la de siempre.
    tocadas, recolocadas = abandon(arbol, 4, "el MEG se corrió fuera de etapa")
    assert tocadas == [4, 5]
    assert recolocadas == []
    por_v = {e.version: e for e in arbol.entries}
    assert por_v[4].status == "dead-end" and por_v[5].status == "dead-end"
    assert por_v[2].status == "exploring"          # el padre NO se toca
    assert "fuera de etapa" in por_v[5].why_abandoned


def test_un_callejon_sin_razon_se_rechaza(arbol):
    """Marcar sin anotar por qué no impide volver a entrar, que es para lo
    único que sirve marcarlo."""
    with pytest.raises(ValueError, match="razón"):
        abandon(arbol, 4, "   ")


def test_el_lugar_seguro_sube_hasta_el_primer_ancestro_sano(arbol):
    abandon(arbol, 4, "por lo que sea")
    assert safe_ancestor(arbol, 5) == 2
    assert safe_ancestor(arbol, 3) == 3        # rama sana: es ella misma


def test_sin_ancestro_sano_devuelve_None(arbol):
    abandon(arbol, 1, "todo mal desde el principio")
    assert safe_ancestor(arbol, 5) is None


# ── el parentesco se infiere solo ──────────────────────────────────────────

def test_encadenar_desde_un_pre_ANTIGUO_se_registra_como_RAMA(arbol):
    """El caso que decide si el mapa vale algo. Volver a una versión anterior y
    seguir por otra puerta es una BIFURCACIÓN; registrarla como continuación de
    la última rama es la mentira que borra el mapa."""
    assert infer_parent(arbol, "/x/m10.pre") == 2      # no 5, que es el último
    assert infer_parent(arbol, "/x/m00.inp") == 1


def test_sin_encadenar_el_padre_es_el_ultimo(arbol):
    assert infer_parent(arbol, "") == 5


def test_la_primera_version_no_tiene_padre():
    assert infer_parent(Guion(series="S", analyst="", created=""), "") is None


# ── de punta a punta, por el servidor ──────────────────────────────────────

@pytest.fixture(scope="module")
def caso():
    d = tempfile.mkdtemp(prefix="guionmap-")
    rng = np.random.default_rng(5)
    y = 100.0 + np.cumsum(rng.normal(0, 1.0, 80))
    inp = os.path.join(d, "S.inp")
    A.create_inp(list(map(float, y)), inp, name="S", freq=4,
                 start_year=2004, start_period=1)

    def est(src, out, nombre, base="", **kw):
        A.confirm_and_estimate(inp_path=src, output_path=os.path.join(d, out),
                               base_pre_path=base, lam=1.0, D=0, n_harmonics=0,
                               seasonal=False, estimate_mu=False,
                               guion_name=nombre, **kw)

    est(inp, "S_m00.inp", "m00", d=1, p=0, q=0)
    est(os.path.join(d, "S_m00.pre"), "S_m10.inp", "m10",
        base=os.path.join(d, "S_m00.pre"), d=1, p=1, q=0)
    # vuelta atrás: otra puerta desde m00
    est(os.path.join(d, "S_m00.pre"), "S_alt.inp", "alt",
        base=os.path.join(d, "S_m00.pre"), d=1, p=0, q=1)
    return d, os.path.join(d, "S_guion.json")


def test_el_guion_se_escribe_SIN_que_nadie_pase_la_ruta(caso):
    """Documentar es el método, no un extra. Exigir la ruta lo hace opcional de
    hecho, y lo opcional no se hace."""
    d, gp = caso
    assert os.path.exists(gp)
    assert len(load_guion(gp).entries) == 3


def test_la_vuelta_atras_queda_registrada_como_rama(caso):
    _, gp = caso
    por_n = {e.name: e for e in load_guion(gp).entries}
    assert por_n["m00"].parent is None
    assert por_n["m10"].parent == por_n["m00"].version
    assert por_n["alt"].parent == por_n["m00"].version   # NO m10


def test_la_salida_no_crece_por_documentar(caso):
    """El registro es interno: una línea corta, no un bloque."""
    d, _ = caso
    out = A.confirm_and_estimate(
        inp_path=os.path.join(d, "S.inp"),
        output_path=os.path.join(d, "S_x.inp"),
        lam=1.0, d=1, D=0, p=0, q=0, n_harmonics=0, seasonal=False,
        estimate_mu=False, guion_name="x")
    txt = "\n".join(c.text for c in out if hasattr(c, "text"))
    linea = [l for l in txt.splitlines() if l.startswith("*guion:")]
    assert len(linea) == 1
    assert len(linea[0]) < 40


def test_guion_map_dibuja_el_arbol_y_las_razones(caso):
    _, gp = caso
    A.guion_abandon(gp, 2, "el AR se añadió antes de tratar el anómalo")
    txt = "\n".join(c.text for c in A.guion_map(gp, version=2)
                    if hasattr(c, "text"))
    assert "Mapa del análisis" in txt
    assert "callejón: el AR se añadió antes" in txt      # la razón, en el árbol
    assert "Lugar seguro más cercano" in txt
    assert "✗" in txt and "·" in txt


def test_guion_abandon_nombra_el_lugar_al_que_volver(caso):
    _, gp = caso
    txt = "\n".join(c.text for c in
                    A.guion_abandon(gp, 3, "otra razón cualquiera")
                    if hasattr(c, "text"))
    assert "Lugar seguro al que volver" in txt
    assert "base_pre_path" in txt        # dice CÓMO volver, no sólo adónde
