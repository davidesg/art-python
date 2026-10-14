"""Repro de BUG-0235: formal_tests sobre un modelo con d=2 contrasta d=3.

Villaverde (P02), IMA(2,1), y el AR(7) en d=1 para el par cruzado de la
frontera 1/2. Sale 1 mientras BUG-0235 siga abierto.
Uso:  ART_NO_VIEWER=1 python repro.py
"""
import os, re, shutil, sys, tempfile
os.environ.setdefault("ART_NO_VIEWER", "1")
import art.mcp_server as s

HERE = os.path.dirname(os.path.abspath(__file__))
def T(r): return r if isinstance(r, str) else "\n".join(
    t for c in r if isinstance(t := getattr(c, "text", None), str))
def grep(pat, t): return [l.strip()[:200] for l in t.splitlines() if re.search(pat, l)]

w = tempfile.mkdtemp(); shutil.copy(os.path.join(HERE, "Villaverde.inp"), w)
inp = os.path.join(w, "Villaverde.inp")
s.confirm_and_estimate(inp, os.path.join(w, "m.inp"), lam=0, d=2, D=0, p=0, q=1,
                       n_harmonics=0, seasonal=False, estimate_mu=False,
                       domain="multiplicative")
ft = T(s.formal_tests(os.path.join(w, "m.pre"), run_meg=False, subdiferenciacion=True))
print("0235", grep(r"sobre-diferenciación regular", ft))
print("0235", grep(r"Candidato: ∇\^3", ft))
print("0235", grep(r"d confirmado ✓", ft))
print("0235", grep(r"Sin par confirmatorio|Shin-Fuller no es aplicable", ft)[:1])

abierto = bool(grep(r"Candidato: ∇\^3", ft)) or bool(grep(r"d confirmado ✓", ft))
# el par cruzado: el modelo en d=1 (AR(7) con μ, como en el guiado)
s.confirm_and_estimate(inp, os.path.join(w, "m1.inp"), lam=0, d=1, D=0, p=7, q=0,
                       n_harmonics=0, seasonal=False, estimate_mu=True,
                       domain="multiplicative")
try:
    fx = T(s.formal_tests(os.path.join(w, "m.pre"), run_meg=False,
                          modelo_d_menos_1=os.path.join(w, "m1.pre")))
except TypeError as e:                       # sin el parámetro: abierto
    fx = str(e)
print("0235 par cruzado", grep(r"Par de la frontera|AMBIGUO", fx))
abierto |= not grep(r"AMBIGUO", fx)
print("BUG-0235", "ABIERTO" if abierto else "arreglado")
sys.exit(1 if abierto else 0)
