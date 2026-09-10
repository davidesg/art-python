"""ORDEN 0.3 — que el uso de RECURSOS sea medible, y lo que entra también.

`ART_CALL_LOG` envolvía `mcp.tool` y no `mcp.resource`. Consecuencia: **el uso
de recursos no era medible**. La hipótesis de MATERIAL §6 es que es cero —que
el modelo nunca los pide— y no había forma de comprobarla, que es la peor
posición para una hipótesis.

Y había una trampa debajo: el bloque del contador vivía DESPUÉS de los
`@mcp.resource` en el módulo, así que aunque se hubiera envuelto `mcp.resource`
ahí, los cinco recursos ya estaban registrados sin envolver. El envoltorio va
ahora inmediatamente detrás de crear el servidor.

Se añade además `bytes_recibidos`: se medía sólo lo que sale, y el coste de una
llamada tiene dos mitades.
"""
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")


def _servidor_con_log(tmp_path, monkeypatch):
    """Reimporta `art.mcp_server` con `ART_CALL_LOG` puesto."""
    destino = tmp_path / "log.jsonl"
    monkeypatch.setenv("ART_CALL_LOG", str(destino))
    for m in [m for m in list(sys.modules) if m.startswith("art.mcp_server")]:
        del sys.modules[m]
    mod = importlib.import_module("art.mcp_server")
    return mod, destino


def _filas(destino):
    """El contador pone el PID en el nombre: un fichero por proceso."""
    base, ext = os.path.splitext(str(destino))
    salidas = list(Path(base).parent.glob(Path(base).name + "-*" + (ext or ".jsonl")))
    out = []
    for f in salidas:
        for l in f.read_text(encoding="utf-8").splitlines():
            if l.strip():
                out.append(json.loads(l))
    return out


def test_los_recursos_tambien_se_cuentan(tmp_path, monkeypatch):
    """LA prueba. Antes esto devolvía cero filas para un recurso."""
    mod, destino = _servidor_con_log(tmp_path, monkeypatch)
    mod._r_defectos()
    filas = _filas(destino)
    recursos = [f for f in filas if f.get("clase") == "resource"]
    assert recursos, f"ningún recurso contado; filas={filas}"
    assert recursos[-1]["tool"] == "_r_defectos"
    assert recursos[-1]["bytes_texto"] > 1000


def test_las_herramientas_siguen_contandose(tmp_path, monkeypatch):
    mod, destino = _servidor_con_log(tmp_path, monkeypatch)
    caso = Path(__file__).resolve().parent.parent / "bugs" / "BUG-0126-repro" \
        / "caso" / "RATIO_m10.inp"
    if not caso.exists():
        pytest.skip("el caso del repro no está")
    mod.series_info(str(caso))
    tools = [f for f in _filas(destino) if f.get("clase") == "tool"]
    assert tools, "ninguna herramienta contada"
    assert tools[-1]["tool"] == "series_info"


def test_se_pesa_lo_que_ENTRA(tmp_path, monkeypatch):
    """`bytes_recibidos`: la mitad del coste que el analista controla."""
    mod, destino = _servidor_con_log(tmp_path, monkeypatch)
    mod._r_defectos()
    fila = _filas(destino)[-1]
    assert "bytes_recibidos" in fila
    assert isinstance(fila["bytes_recibidos"], int)
    # y con argumentos largos, sube
    mod._r_defecto("0001")
    a, b = _filas(destino)[-2:]
    assert b["bytes_recibidos"] > a["bytes_recibidos"], (a, b)


def test_sin_la_variable_no_se_envuelve_nada(tmp_path, monkeypatch):
    """Cero coste y cero cambio de comportamiento en el uso normal."""
    monkeypatch.delenv("ART_CALL_LOG", raising=False)
    for m in [m for m in list(sys.modules) if m.startswith("art.mcp_server")]:
        del sys.modules[m]
    mod = importlib.import_module("art.mcp_server")
    assert not list(tmp_path.glob("*.jsonl"))
    assert mod._CALL_LOG == ""
