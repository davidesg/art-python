"""BUG-0223: con d = 0 el paso 3 de guided_identification no contrasta la
estacionalidad y aun así concluye «Decisión A — sin armónicos».

BXE = X/M de Ecuador (trimestral 2003T1–2019T4, n = 68), del paper de
dolarización: estacionalidad fuerte heredada de M (F-HAC = 9.58).

    PYTHONPATH=src python3 bugs/BUG-0223-repro/repro.py   # sale 1 mientras siga abierto
"""
import os, sys, tempfile
os.environ.setdefault("ART_NO_VIEWER", "1")
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
txt = lambda o: "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                          for c in (o if isinstance(o, list) else [o]))
HERE = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as tmp:
    inp = os.path.join(tmp, "BXE.inp")
    fn(M.load_data)(os.path.join(HERE, "BXE.csv"), inp, column="BXE",
                    freq=4, start_year=2003, start_period=1)
    out = txt(fn(M.guided_identification)(inp, lam=0, d=0, domain="multiplicative",
                                          objetivo="multivariante"))
contrastado = "F-test HAC" in out
decide_a = "Decisión A" in out
print("paso 3 con d=0 — contraste HAC impreso:", contrastado,
      "· dice «Decisión A»:", decide_a)
sys.exit(0 if contrastado else 1)
