"""Repro de BUG-0224: DCD de subdiferenciación sin potencia con AR libre.

Rc (renta + transferencias recibidas, Ecuador, trimestral 2003T1-2019T4, n=68),
ln Rc, d=1, armónicos f=1,2, μ. m00 sin ARMA; m01_ar1 con un AR(1) libre no
significativo. Sale 1 mientras BUG-0224 siga abierto.
Uso:  ART_NO_VIEWER=1 python repro.py
"""
import os, re, sys, warnings
os.environ.setdefault("ART_NO_VIEWER", "1")
warnings.simplefilter("ignore")
import art.mcp_server as s

HERE = os.path.dirname(os.path.abspath(__file__))
def T(r): return r if isinstance(r, str) else "\n".join(
    t for c in r if isinstance(t := getattr(c, "text", None), str))

abierto = False
for m in ("Rc_m00.pre", "Rc_m01_ar1.pre"):
    ft = T(s.formal_tests(os.path.join(HERE, m), run_meg=False, subdiferenciacion=True))
    sub = ft.split("**DCD sub-diferenciación regular**")[1].split("\n\n")[0]
    linea = [l.strip() for l in sub.splitlines() if l.strip().startswith("- ")][0]
    print(m, linea[:220])
    if "bastaba" in linea or "θ→+1" in linea:
        # con θ̂ lejos de +1 y el AR reconstruyendo la ∇, ni «θ→+1» ni «d−1 bastaba»
        th = float(re.search(r"θ̂=([+-]\d+\.\d+)", linea).group(1))
        if th < 0.9:
            abierto = True
print("BUG-0224", "ABIERTO" if abierto else "arreglado")
sys.exit(1 if abierto else 0)
