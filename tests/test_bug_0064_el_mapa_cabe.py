"""BUG-0064 — el mapa orienta; `export_guion` documenta.

`guion_map` volcaba cinco campos sin límite, uno por línea. Con nodos bien
razonados el RATIO del RUN 3 salía en 52.921 bytes y se truncaba a fichero —
justo la serie con más ramas.
"""
import json
import os
import warnings

import pytest

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run3/"
RATIO = R + "RATIO/RATIO_guion.json"


def _map(p, **kw):
    if not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    import art.mcp_server as M
    f = getattr(M.guion_map, "fn", M.guion_map)
    return f(p, **kw)[0].text


@pytest.mark.parametrize("rel", ["RATIO/RATIO_guion.json",
                                 "PGAS/PGAS_guion.json",
                                 "ITCER/ITCER_guion.json"])
def test_el_mapa_cabe(rel):
    assert len(_map(R + rel).encode()) < 25_000


def test_el_caso_sigue_siendo_grande_sin_recorte():
    """Si el guion adelgaza, este test deja de medir nada."""
    entero = _map(RATIO, detalle=True)
    assert len(entero.encode()) > 40_000, (
        "el caso ya no desborda; el test no mide lo que dice medir")


def test_el_recorte_se_anuncia():
    """Un recorte silencioso sería peor que el desbordamiento."""
    t = _map(RATIO)
    assert "textos recortados" in t
    assert "detalle=True" in t
    assert "export_guion" in t


def test_detalle_devuelve_el_texto_intacto():
    assert "[…]" not in _map(RATIO, detalle=True)


def test_no_se_pierde_ninguna_entrada():
    """Se recorta el TEXTO, no el árbol: el mapa sigue completo."""
    t = _map(RATIO)
    n = len(json.load(open(RATIO, encoding="utf-8"))["entries"])
    marcas = sum(t.count(f"n{v} ") + t.count(f"v{v} ") for v in range(1, n + 1))
    assert marcas >= n, f"faltan entradas en el mapa: {marcas} de {n}"


def test_se_corta_por_palabra():
    """Cortar a mitad de una cifra convertiría un número en otro."""
    t = _map(RATIO)
    for linea in t.splitlines():
        if "[…]" in linea:
            antes = linea.split("[…]")[0]
            assert not antes.rstrip().endswith((",", ".", ";", ":"))


def test_un_guion_corto_no_se_recorta(tmp_path):
    """El aviso sólo aparece donde hay algo que recortar."""
    g = {"series": "X", "analyst": "", "created": "2026-08-30",
         "entries": [{"version": 1, "name": "dominio", "inp_path": "",
                      "timestamp": "", "spec": {}, "stats": None,
                      "equation": "", "decision": "", "rationale": "corta",
                      "problems_found": "", "next_version": "",
                      "parent": None, "kind": "node",
                      "node": {"nodo": "dominio", "decidido": "ratio",
                               "evidencia": "n=84"}}]}
    p = tmp_path / "g.json"
    p.write_text(json.dumps(g), encoding="utf-8")
    t = _map(str(p))
    assert "textos recortados" not in t
    assert "[…]" not in t
