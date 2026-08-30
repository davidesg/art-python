"""BUG-0058 — la cascada de abandono no pisa razones ni barre ramas ajenas.

Dos fallos observados en el RUN 3:
(a) `why_abandoned` se sobrescribía siempre, así que abandonar una versión
    borraba la razón de cualquier callejón anterior que la cascada tocara;
(b) un NODO alcanzado se recoloca al tronco, pero sus descendientes seguían
    marcándose aunque ya colgaran de una versión viva.
"""
import pytest

from art.guion import Guion, GuionEntry, abandon, descendants


def _e(v, parent, kind="model", **kw):
    return GuionEntry(version=v, name=f"v{v}", inp_path="", timestamp="",
                      spec={}, stats=None, equation="", decision="",
                      rationale="", problems_found="", next_version="",
                      parent=parent, kind=kind, **kw)


@pytest.fixture
def guion():
    """v1 → v2 → {v5 callejón con razón propia, v3 NODO → v4}."""
    g = Guion(series="X", analyst="", created="2026-08-29")
    g.entries = [
        _e(1, None),
        _e(2, 1),
        _e(5, 2, status="dead-end", why_abandoned="RAZON PROPIA de v5"),
        _e(3, 2, kind="node"),
        _e(4, 3),
    ]
    return g


def _por_v(g):
    return {e.version: e for e in g.entries}


# ── (a) las razones no se pisan ───────────────────────────────────────────

def test_una_razon_ya_escrita_no_se_pierde(guion):
    abandon(guion, 2, "v2 no blanquea")
    assert "RAZON PROPIA de v5" in _por_v(guion)[5].why_abandoned


def test_el_descendiente_dice_que_lo_arrastraron(guion):
    """Su razón no es la del ancestro: es que el ancestro cayó."""
    abandon(guion, 2, "v2 no blanquea")
    w = _por_v(guion)[5].why_abandoned
    assert "Arrastrado por el callejón de v2" in w
    assert w != "v2 no blanquea", "copia literal de la razón del ancestro"


def test_la_version_abandonada_directamente_lleva_su_razon(guion):
    abandon(guion, 2, "v2 no blanquea")
    assert _por_v(guion)[2].why_abandoned == "v2 no blanquea"


def test_un_descendiente_sin_razon_previa_recibe_la_heredada(guion):
    g = guion
    g.entries.append(_e(6, 5))          # cuelga de v5, sin razón propia
    abandon(g, 2, "v2 no blanquea")
    assert _por_v(g)[6].why_abandoned.startswith("Arrastrado por el callejón de v2")


# ── (b) los subárboles recolocados se podan ───────────────────────────────

def test_el_nodo_se_recoloca_al_ancestro_vivo(guion):
    _, rec = abandon(guion, 2, "v2 no blanquea")
    assert rec == [3]
    assert _por_v(guion)[3].parent == 1


def test_lo_que_cuelga_del_nodo_recolocado_sobrevive(guion):
    ab, _ = abandon(guion, 2, "v2 no blanquea")
    assert 4 not in ab, "v4 cuelga de un nodo que volvió al tronco: no descendía del fallo"
    assert _por_v(guion)[4].status != "dead-end"


def test_lo_que_si_desciende_del_fallo_se_abandona(guion):
    """La poda no puede dejar de barrer lo que sí está contaminado."""
    ab, _ = abandon(guion, 2, "v2 no blanquea")
    assert 2 in ab and 5 in ab


def test_sin_cascada_solo_cae_la_version_pedida(guion):
    ab, rec = abandon(guion, 2, "v2 no blanquea", cascade=False)
    assert ab == [2] and rec == []
    assert "RAZON PROPIA de v5" in _por_v(guion)[5].why_abandoned


def test_la_razon_sigue_siendo_obligatoria(guion):
    with pytest.raises(ValueError):
        abandon(guion, 2, "   ")
