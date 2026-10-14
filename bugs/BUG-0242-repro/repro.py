"""Repro de BUG-0242: el Shin-Fuller por sobreajuste se calla con raíz real negativa.

IPC_US m06 (AR(2) complejo + dos intervenciones). Sale 1 mientras siga abierto.
Uso:  ART_NO_VIEWER=1 python repro.py
"""
import os, sys, warnings
os.environ.setdefault("ART_NO_VIEWER", "1")
warnings.simplefilter("ignore")
from art.mcp_server import _load_fitted
import art.mcp_server as s
from art.formal_tests import shin_fuller_sobreajuste

HERE = os.path.dirname(os.path.abspath(__file__))
pre = os.path.join(HERE, "IPC_US_m06.pre")
ts, m = _load_fitted(pre)
try:
    r = shin_fuller_sobreajuste(m)
    print("sobreajuste: φ̂ real recuperada =", r.phi_real, "sin raíz positiva:",
          getattr(r, "sin_raiz_positiva", None))
except ValueError as e:
    print("sobreajuste lanza:", str(e)[:160]); r = None
ft = "\n".join(c.text for c in s.formal_tests(pre, run_meg=False))
calla = "no existe en esta corrida" in ft
print("el informe dice «el lado AR no existe»:", calla)
abierto = r is None or calla
print("BUG-0242", "ABIERTO" if abierto else "arreglado")
sys.exit(1 if abierto else 0)
