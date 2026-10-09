"""Repro de BUG-0232…0234: el carril guiado de Salamanca (P02, 8-oct-2026).

Uso:  ART_NO_VIEWER=1 python repro.py   (trabaja en un directorio temporal)
"""
import os, re, shutil, tempfile
os.environ.setdefault("ART_NO_VIEWER", "1")
import art.mcp_server as s

HERE = os.path.dirname(os.path.abspath(__file__))
def T(r): return r if isinstance(r, str) else "\n".join(
    t for c in r if isinstance(t := getattr(c, "text", None), str))
def grep(pat, t): return [l.strip()[:220] for l in t.splitlines() if re.search(pat, l)]

w = tempfile.mkdtemp(); shutil.copy(os.path.join(HERE, "Salamanca.inp"), w)
inp, g = os.path.join(w, "Salamanca.inp"), os.path.join(w, "g.json")
kw = dict(lam=0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=True,
          domain="multiplicative")

# 0232 — formal_tests sobre el AR(4)
s.confirm_and_estimate(inp, os.path.join(w, "m01.inp"), p=4, q=0, guion_path=g,
                       guion_name="m01 AR(4)", **kw)
ft = T(s.formal_tests(os.path.join(w, "m01.pre"), run_meg=False, subdiferenciacion=True))
print("0232", grep(r"DCD sub-diferenciación", ft) + grep(r"LR=-inf", ft))
print("0232", grep(r"Pero por ABAJO no cierra", ft)[:1], grep(r"El modelo es adecuado", ft))

# 0233 — paso 4: el empate que se declara no es el de la ficha
t4 = T(s.guided_identification(inp, lam=0, d=1, D=0))
print("0233", grep(r"^\s*(→)?\s*\d\. ARIMA", t4))
print("0233", grep(r"Decisión ambigua entre", t4), grep(r"^\| \| \(", t4))

# 0234 — un nodo d que concluye sobre modelos ya estimados cuenta como «sin modelo»
s.guion_node(g, "d", "ambiguo: I(1) con el AR(4)", razon="conclusión sobre m01",
             parent=1)
mp = T(s.guion_map(g))
print("0234", grep(r"sin modelo estimado detrás", mp))
print("tmp:", w)
