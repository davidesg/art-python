"""BUG-0241 — guion_adopt cerraba el nodo `ordenes` de un ARMA(0,0) como ARMA(1,0).

El `.inp` de un paseo aleatorio lleva el relleno «1 1 / 0.0 0» —un AR(1) FIJO a
cero— y el spec del guion lo registraba como p=1. Al adoptar el (0,1,0) del IPC
de Alemania, el nodo de los órdenes se cerraba con «ARMA(1,0) — corrige la
propuesta», cuando lo adoptado ERA la propuesta.
"""
import json
import os
import shutil
import tempfile

os.environ.setdefault("ART_NO_VIEWER", "1")

from art import mcp_server as s

INP = os.path.join(os.path.dirname(__file__), "..", "bugs", "BUG-0241-repro",
                   "IPC_DE.inp")


def T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


def test_adoptar_arma00_cierra_ordenes_como_arma00():
    w = tempfile.mkdtemp(prefix="bug0241-")
    shutil.copy(INP, w)
    inp, g = os.path.join(w, "IPC_DE.inp"), os.path.join(w, "g.json")
    GI = dict(guion_path=g, domain="price_index")
    T(s.guided_identification(inp, expectativas="índice", **GI))
    T(s.guided_identification(inp, lam=0, razon="dominio", **GI))
    T(s.guided_identification(inp, lam=0, d=1, razon="tendencia", **GI))
    T(s.guided_identification(inp, lam=0, d=1, D=0, razon="sin est.", **GI))
    T(s.confirm_and_estimate(inp, os.path.join(w, "m01.inp"), lam=0, d=1, D=0,
                             p=0, q=0, n_harmonics=0, seasonal=False,
                             estimate_mu=True, domain="price_index",
                             guion_path=g, guion_name="m01 (0,1,0)", parent=5))
    v = max(e["version"] for e in json.load(open(g))["entries"])
    t = T(s.guion_adopt(g, v, why="El sobreajuste AR(1) no es significativo."))
    assert "ordenes = ARMA(0,0)" in t
    assert "corrige la propuesta" not in t
