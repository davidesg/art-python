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
    assert total > 50_000, "la medida se ha desplomado: revisa ORDEN.md"
    assert len(d) >= 40


# ────────── el objetivo de la fase 1, hoy en rojo ──────────

@pytest.mark.xfail(strict=True,
                   reason="BUG-0116 / ORDEN fase 1.2 — 14 descripciones por "
                          "encima de 1.800; se reescriben con la plantilla de "
                          "SEMAFORO §4.1 y lo que sale va a docs/")
def test_ninguna_descripcion_pasa_de_1800_caracteres():
    largas = {n: len(d) for n, d in _descripciones().items()
              if len(d) > LIMITE_DESC}
    assert not largas, (
        f"{len(largas)} por encima de {LIMITE_DESC}: "
        + ", ".join(f"{n}={c}" for n, c in
                    sorted(largas.items(), key=lambda kv: -kv[1])))


@pytest.mark.xfail(strict=True,
                   reason="BUG-0116 / ORDEN fase 1.1 — `_INSTRUCTIONS` se parte "
                          "en cabecera ≤2.000 y el resto se sirve como "
                          "art://protocolo")
def test_la_cabecera_de_las_instrucciones_cabe_en_2000():
    assert len(M._INSTRUCTIONS) <= LIMITE_CABECERA, (
        f"_INSTRUCTIONS mide {len(M._INSTRUCTIONS):,} caracteres")


@pytest.mark.xfail(strict=True,
                   reason="ORDEN fase 1.1 — los primeros 2.000 caracteres tienen "
                          "que llevar las puertas y el esquema art://")
def test_los_primeros_2000_llevan_las_puertas_y_los_recursos():
    cab = M._INSTRUCTIONS[:LIMITE_CABECERA]
    faltan = [x for x in ("guided_identification", "guided_intervention",
                          "art://") if x not in cab]
    assert not faltan, f"no están en la cabecera: {faltan}"
