#!/usr/bin/env python3
"""Repros de BUG-0208 a BUG-0222 (revisión de la P02 en modo autónomo, 6-oct-2026).

Las .inp son las de la P02 de Econometría Aplicada (UCM): IPC de EE. UU., España y
Alemania (precios_consumo, 2002-2019) y dos distritos de Madrid (vivienda, 2010-2025).
Corre en un directorio temporal; cada bloque imprime lo que demuestra el defecto.

    ART_NO_VIEWER=1 python3 repro.py
"""
import os, re, json, shutil, tempfile, time
import art.mcp_server as s

HERE = os.path.dirname(os.path.abspath(__file__))
W = tempfile.mkdtemp(prefix="art_p02_"); os.chdir(W)
for f in os.listdir(HERE):
    if f.endswith(".inp"): shutil.copy(os.path.join(HERE, f), W)

def T(r):
    if isinstance(r, str): return r
    return "\n".join(t for c in r if isinstance(t := getattr(c, "text", None), str))

kw = dict(lam=0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=True,
          domain="price_index", modo="autonomo")

# BUG-0208 · el modo autónomo dibuja y devuelve las figuras
s.confirm_and_estimate("IPC_US.inp", "w.inp", p=2, q=0, **kw)          # calentar
t0 = time.time(); r = s.confirm_and_estimate("IPC_US.inp", "w.inp", p=2, q=0, **kw); con = time.time() - t0
img = [len(c.data) for c in r if getattr(c, "type", "") == "image"]
import matplotlib.figure as MF
_orig = MF.Figure.savefig
MF.Figure.savefig = lambda self, *a, **k: (a[0].write(b"") if a and hasattr(a[0], "write") else None)
t0 = time.time(); s.confirm_and_estimate("IPC_US.inp", "w.inp", p=2, q=0, **kw); sin = time.time() - t0
MF.Figure.savefig = _orig
print(f"0208  con figura {con:.2f}s · sin rasterizar {sin:.2f}s ({100*(con-sin)/con:.0f} %) · imágenes {img} bytes")

# BUG-0209 · tras D=0 sin estacionalidad, el paso 4 propone estacionalidad
t = T(s.guided_identification("IPC_US.inp", lam=0, d=1, D=0, domain="price_index"))
print("0209  n_harmonics=5:", "n_harmonics=5" in t, "· candidatos:",
      re.findall(r"ARIMA\(\d,1,\d\)\(\d,0,\d\)_12", t)[:3])

# BUG-0210 · nodo d: «ambiguo» en la tabla, «consenso» en el resumen
t = T(s.guided_identification("Retiro.inp", lam=0))
print("0210 ", re.findall(r"\| 1 \| ∇ln[^\n]*", t)[:1], re.findall(r"Lo que encuentran[^\n]*", t)[:1])

# BUG-0216 · ecuación con un factor AR vacío
t = T(s.confirm_and_estimate("IPC_DE.inp", "de.inp", p=0, q=0, **kw))
print("0216 ", re.findall(r"\(2\)[^\n]*", t)[:1])

# BUG-0217 · coincide deducido por cadenas; «parcial» rechazado
g = "g.json"
s.guion_node(g, "dominio", "price_index", razon="r", expectativas="e")
print("0217 ", re.findall(r"propuesta del asistente[^\n]*",
      T(s.guion_node(g, "lambda", "0 (logaritmos)", razon="r", propuesta="λ=0")))[:1])
print("0217 ", T(s.guion_node(g, "d", "1", razon="r", coincide="parcial"))[:80])

# BUG-0214 · JB de la diagnosis frente al .out
t = T(s.confirm_and_estimate("IPC_US.inp", "us2.inp", p=2, q=0, **kw))
jb_d = re.findall(r"JB=([0-9.]+)", t)[:1]
out = open("us2.out").read(); jb_o = re.findall(r"Jarque-Bera:\s*([0-9.]+)", out)[:1]
print("0214  JB diagnosis", jb_d, "· JB .out", jb_o)
print("\ndirectorio:", W)
