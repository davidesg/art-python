"""BUG-0020: IPC_ES's Box-Cox lambda depends on WHO ELSE is in the batch.

art writes its decision on line 26 of the `.inp` it produces:
`** Box-Cox lambda, regular differences and complete annual differences:`

    python3 bugs/BUG-0020-repro/repro.py
"""
import os
import tempfile

from art import mcp_server as A

CSV = ("/home/david/Dropbox/Nivel de Precios y Energia/passthrough_multiart"
       "/data/levels_2002_2019.csv")
if not os.path.exists(CSV):
    raise SystemExit(f"the level series are missing: {CSV}")


def decision(cols, leer):
    d = tempfile.mkdtemp(prefix="bug0020-")
    ps = []
    for col in cols:
        p = os.path.join(d, f"{col}.inp")
        A.load_data(CSV, p, column=col, series_name=col,
                    freq=12, start_year=2002, start_period=2)
        ps.append(p)
    A.batch_build(ps, d)
    hit = [q for q in sorted(os.listdir(d))
           if q.startswith(leer) and q.endswith(".inp")]
    t = open(os.path.join(d, hit[-1])).read().splitlines()
    for i, l in enumerate(t):
        if "Box-Cox lambda" in l:
            return t[i + 1].strip()
    return "?"


print("lambda / d / D que art escribe para IPC_ES")
print("  sola en el lote      :", decision(["IPC_ES"], "IPC_ES"))
print("  en lote con WTI      :", decision(["IPC_ES", "WTI"], "IPC_ES"))
print("  fijado el 2026-08-07 : 1.00 1 0")
