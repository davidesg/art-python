"""BUG-0234: guion_map counts as «decisión sin modelo estimado detrás» a node
that concludes on models already estimated.  Salamanca (P02): after the AR(4),
the analyst writes the node `d = ambiguo: …` hung from it, as a CONCLUSION.

    PYTHONPATH=src python3 bugs/BUG-0234-repro/repro.py   # exits 1 while open
"""
import os, shutil, sys, tempfile, warnings
os.environ.setdefault("ART_NO_VIEWER", "1")
warnings.simplefilter("ignore")
import art.mcp_server as s
fn = lambda t: getattr(t, "fn", t)
T = lambda r: r if isinstance(r, str) else "\n".join(
    t for c in r if isinstance(t := getattr(c, "text", None), str))
HERE = os.path.dirname(os.path.abspath(__file__))
w = tempfile.mkdtemp()
try:
    shutil.copy(os.path.join(HERE, "Salamanca.inp"), w)
    inp, g = os.path.join(w, "Salamanca.inp"), os.path.join(w, "g.json")
    fn(s.confirm_and_estimate)(inp, os.path.join(w, "m01.inp"), p=4, q=0,
                               lam=0, d=1, D=0, n_harmonics=0, seasonal=False,
                               estimate_mu=True, guion_path=g,
                               guion_name="m01 AR(4)")
    try:
        r = T(fn(s.guion_node)(g, "d", "ambiguo: I(1) con el AR(4)",
                               razon="conclusión sobre m01", parent=1,
                               conclusion=True))
    except TypeError as exc:
        print("guion_node cannot mark the node as a conclusion:", exc)
        sys.exit(1)
    mp = T(fn(s.guion_map)(g))
finally:
    shutil.rmtree(w, ignore_errors=True)
malas = [l.strip() for l in mp.splitlines() if "sin modelo estimado" in l]
print("map:", malas or "no «decisión sin modelo» line")
sys.exit(1 if malas else 0)
