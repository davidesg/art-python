"""BUG-0251: adopting a model from a declared tie says «coincide con la
propuesta» and records coincide=True next to a propuesta that is ANOTHER
order.  Minneapolis (flour_prices.csv, the lutkepohl_poskitt example of sima):
the orders node proposes ARMA(0,1) (tie with AR(1)); the analyst adopts AR(1).

    python3 bugs/BUG-0251-repro/repro.py      # exits 1 while the bug is open
"""
import json, os, sys, tempfile
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
txt = lambda o: "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                          for c in (o if isinstance(o, list) else [o]))
HERE = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as tmp:
    inp, gp = os.path.join(tmp, "Minneapolis.inp"), os.path.join(tmp, "guion.json")
    fn(M.load_data)(os.path.join(HERE, "flour_prices.csv"), inp, column="Minneapolis")
    gi = fn(M.guided_identification)
    gi(inp, domain="price_index", expectativas="price", guion_path=gp)
    gi(inp, lam=0.0, domain="price_index", guion_path=gp)
    gi(inp, lam=0.0, d=1, domain="price_index", guion_path=gp)
    gi(inp, lam=0.0, d=1, D=0, domain="price_index", guion_path=gp)
    fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m01.inp"), lam=0.0, d=1, D=0, p=1, q=0,
                               n_harmonics=0, seasonal=False, estimate_mu=False,
                               guion_path=gp, guion_name="m01")
    g = json.load(open(gp))
    v = max(e["version"] for e in g["entries"] if e.get("name") == "m01")
    out = txt(fn(M.guion_adopt)(gp, v, why="AR(1) por dominio"))
    node = [e for e in json.load(open(gp))["entries"] if e.get("nodo") == "ordenes"
            and e.get("propuesta")][-1]
print("propuesta:", node["propuesta"], "| decidido:", node["node"]["decidido"],
      "| coincide:", node["coincide"])
said = "coincide con la propuesta" in out
print("the adoption says «coincide con la propuesta»:", said)
bad = said and node["propuesta"] != node["node"]["decidido"]
sys.exit(1 if bad else 0)
