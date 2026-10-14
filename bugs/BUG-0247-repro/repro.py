"""BUG-0247: the Box-Cox node says both «Eso NO es "las dos son razonables"»
and «Ambas transformaciones son razonables».  Buffalo (flour_prices.csv, the
lutkepohl_poskitt example of sima): corr +0.159 (lambda=1), -0.077 (lambda=0).

    python3 bugs/BUG-0247-repro/repro.py      # exits 1 while the bug is open
"""
import os, sys, tempfile
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
HERE = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as tmp:
    inp = os.path.join(tmp, "Buffalo.inp")
    fn(M.load_data)(os.path.join(HERE, "flour_prices.csv"), inp, column="Buffalo")
    out = fn(M.guided_identification)(inp, domain="price_index")
    text = "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                     for c in (out if isinstance(out, list) else [out]))
both = "Los dos signos son OPUESTOS" in text and "Ambas transformaciones son razonables" in text
wrong_next = "Siguiente paso: detección de estacionalidad" in text
print("horquilla + «Ambas … razonables»:", both)
print("«Siguiente paso: detección de estacionalidad» en el nodo lambda:", wrong_next)
sys.exit(1 if (both or wrong_next) else 0)
