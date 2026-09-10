"""ORDEN 0.2 — el presupuesto de lo que se empuja en CADA llamada.

Las descripciones de las herramientas y las instrucciones del servidor se
envían **enteras, en todas y cada una de las llamadas**. No son documentación
que se consulta: son coste fijo por turno. Medido el 10-sep-2026 sobre
`mcp.list_tools()`:

    suma de las 46 descripciones    76.531
    `_INSTRUCTIONS`                 35.941
    ─────────────────────────────────────
    empujado en cada llamada       112.472 caracteres

Y el cliente **recorta**. Lo que queda detrás del recorte no llega nunca, así
que una descripción larga no es «más completa»: es una en la que lo que decide
puede estar fuera. Ésa es la medida del BUG-0116.

Estas pruebas fijan el objetivo de la fase 1 y **hoy están en rojo a
propósito**, marcadas `xfail(strict=True)`. Cuando la fase 1 cierre pasarán a
`xpass` y habrá que quitarles la marca: ésa es la señal de que se hizo.
"""
import asyncio

import pytest

pytest.importorskip("mcp")

import art.mcp_server as M

LIMITE_DESC = 1800
LIMITE_CABECERA = 2000


def _tools():
    return asyncio.run(M.mcp.list_tools())


def _descripciones():
    return {t.name: (t.description or "") for t in _tools()}


# ────────── lo que ya se cumple ──────────

def test_todas_las_herramientas_llevan_descripcion():
    vacias = [n for n, d in _descripciones().items() if not d.strip()]
    assert not vacias, f"sin descripción: {vacias}"


def test_la_medida_esta_disponible_y_es_la_que_dice_el_plan():
    """Que el número se pueda recalcular, para que ORDEN no envejezca solo."""
    d = _descripciones()
    total = sum(len(v) for v in d.values()) + len(M._INSTRUCTIONS)
    # La cota de abajo es un centinela contra un borrado accidental, no un
    # objetivo: tras la fase 1 el presupuesto son ~48.000 y el objetivo es que
    # BAJE. Si sube de 70.000, la doctrina ha vuelto al canal que se empuja.
    assert 20_000 < total < 70_000, (
        f"{total:,} caracteres por llamada: revisa ORDEN.md fase 1")
    assert len(d) >= 40


# ────────── el objetivo de la fase 1, hoy en rojo ──────────

def test_ninguna_descripcion_pasa_de_1800_caracteres():
    largas = {n: len(d) for n, d in _descripciones().items()
              if len(d) > LIMITE_DESC}
    assert not largas, (
        f"{len(largas)} por encima de {LIMITE_DESC}: "
        + ", ".join(f"{n}={c}" for n, c in
                    sorted(largas.items(), key=lambda kv: -kv[1])))


def test_la_cabecera_de_las_instrucciones_cabe_en_2000():
    assert len(M._INSTRUCTIONS) <= LIMITE_CABECERA, (
        f"_INSTRUCTIONS mide {len(M._INSTRUCTIONS):,} caracteres")


def test_los_primeros_2000_llevan_las_puertas_y_los_recursos():
    cab = M._INSTRUCTIONS[:LIMITE_CABECERA]
    faltan = [x for x in ("guided_identification", "guided_intervention",
                          "art://") if x not in cab]
    assert not faltan, f"no están en la cabecera: {faltan}"


# ────────── ORDEN 1.1, ya cerrado ──────────

def test_el_protocolo_entero_sigue_disponible_por_recurso():
    """Acortar la cabecera no puede perder texto: lo que sale de ahí tiene que
    seguir entero en `art://protocolo`. Si no, el arreglo del canal se habría
    convertido en un recorte."""
    entero = M._corta_protocolo()
    assert len(entero) > 30_000, f"el protocolo mide {len(entero):,}"
    assert entero == M._PROTOCOLO


@pytest.mark.parametrize("etapa", [k for k, _ in M._ETAPAS_PROTOCOLO])
def test_cada_etapa_del_protocolo_devuelve_texto(etapa):
    t = M._corta_protocolo(etapa)
    assert len(t) > 500, f"{etapa}: {len(t)} caracteres"
    assert t in M._PROTOCOLO, f"{etapa} no es un corte literal del protocolo"


def test_las_etapas_no_se_solapan_ni_se_pisan():
    """Cada etapa es un tramo distinto: si dos devuelven lo mismo, el corte se
    ha desincronizado del texto."""
    cortes = {k: M._corta_protocolo(k) for k, _ in M._ETAPAS_PROTOCOLO}
    assert len(set(cortes.values())) == len(cortes), \
        "dos etapas devuelven el mismo tramo"


def test_una_etapa_que_no_existe_lo_DICE_y_no_calla():
    t = M._corta_protocolo("inventada")
    assert "no hay etapa" in t.lower()
    assert "art://protocolo" in t
