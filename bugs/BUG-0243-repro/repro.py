"""Repro de BUG-0243: con un MA(2), el DCD de subdiferenciación añade un MA(1) aparte.

Moncloa m03, ARIMA(1,2,2). Sale 1 mientras siga abierto.
Uso:  ART_NO_VIEWER=1 python repro.py
"""
import os, sys, warnings
import numpy as np
os.environ.setdefault("ART_NO_VIEWER", "1")
warnings.simplefilter("ignore")
from art.mcp_server import _load_fitted
from art.formal_tests import dcd_underdiff_regular

HERE = os.path.dirname(os.path.abspath(__file__))
ts, m = _load_fitted(os.path.join(HERE, "Moncloa_m03.pre"))
fac = list(m.ma[0])
z = np.roots([-c for c in reversed(fac)] + [1.0])
raiz = max(1.0 / r.real for r in z if abs(r.imag) < 1e-8)
r = dcd_underdiff_regular(m)
print(f"MA(2) = {fac}; su raíz real más cercana a +1: θ = {raiz:.4f}")
print(f"testigo del DCD: θ̂ = {r.coef_free:+.4f}, LR = {r.lr:.3f}")
abierto = abs(r.coef_free - raiz) > 1e-6
print("BUG-0243", "ABIERTO" if abierto else "arreglado")
sys.exit(1 if abierto else 0)
