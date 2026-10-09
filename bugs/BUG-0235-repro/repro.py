"""Repro de BUG-0235: formal_tests sobre un modelo con d=2 contrasta d=3.

Villaverde (P02), IMA(2,1). Uso:  ART_NO_VIEWER=1 python repro.py
"""
import os, re, shutil, tempfile
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
