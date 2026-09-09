#!/usr/bin/env python3
"""BUG-0126 — la misma figura abría tres ventanas.

Determinista: sustituye `_abrir_visor` por un contador y compara ventanas
abiertas contra imágenes devueltas. La invariante es 1 a 1.
"""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src"))
os.environ.pop("ART_NO_VIEWER", None)
os.environ.setdefault("ART_FIG_DIR", os.path.join(
    os.environ.get("TMPDIR", "/tmp"), "art_repro_0126"))

import art.mcp_server as srv  # noqa: E402

sys.modules.pop("pytest", None)
srv._BAJO_SERVIDOR = True                      # como el servidor real, en POSIX
ventanas = []
srv._abrir_visor = lambda p: ventanas.append(p) or ""

CASO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caso")
if not os.path.isdir(CASO):
    print(f"*(este repro necesita un caso en {CASO}; se salta)*")
    raise SystemExit(0)

fallos = 0
print(f"{'herramienta':28s} {'imágenes':>9} {'ventanas':>9}")
for nombre, kw in (("boxcox_analysis", dict(inp_path=f"{CASO}/RATIO.inp")),
                   ("model_histogram", dict(inp_path=f"{CASO}/RATIO_m41.inp"))):
    ventanas.clear()
    fn = getattr(getattr(srv, nombre), "fn", getattr(srv, nombre))
    res = fn(**kw)
    imgs = sum(1 for i in res if getattr(i, "type", "") == "image")
    ok = imgs == len(ventanas)
    fallos += not ok
    print(f"{nombre:28s} {imgs:>9} {len(ventanas):>9}  {'OK' if ok else '** FALLA **'}")

print()
print("Escribir es idempotente; abrir una ventana no. Con las dos en la misma")
print("función, cada sitio que necesitaba la RUTA abría además una ventana.")
sys.exit(1 if fallos else 0)
