"""BUG-0185 — la alternativa «Intervenir <fecha>» fecha el residuo sin el desfase.

Uso (desde la raíz de art-python):

    PYTHONPATH=src python bugs/BUG-0185-repro/repro.py

Estima IPC_ES_m11.pre (run 8: d=1 + raíz estacional estocástica en f=2, que
consume 3 observaciones) y fecha su residuo más extremo de las dos maneras:
como lo hace `_alternativas_desde._fecha` (mcp_server.py) y con el desfase de
`desfase_observaciones`, que es lo que usan los sitios arreglados en BUG-0172.
"""
import os
import warnings

os.environ.setdefault("ART_NO_VIEWER", "1")

import numpy as np

from art.guion import _at_to_date
from art.identification import desfase_observaciones
from art.pipeline import mirar

aqui = os.path.dirname(os.path.abspath(__file__))
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    # sólo se miran residuos: `mirar` acepta el .pre (los valores son exactos)
    res = mirar(os.path.join(aqui, "IPC_ES_m11.pre"))
m = res[1] if isinstance(res, tuple) else res

r = np.asarray(m._result.residuals, dtype=float)
z = (r - r.mean()) / r.std(ddof=1)
obs = int(np.argmax(np.abs(z))) + 1          # 1-based, como diagnosis.py:756
ts = m.series
sy, sp = int(ts.start[0]), int(ts.start[1])
f = int(ts.freq)
desf = desfase_observaciones(m)

como_hoy = _at_to_date(obs, sy, sp, f)                 # mcp_server.py:1970
correcta = _at_to_date(obs - 1 + desf, sy, sp, f)

print(f"nobs={ts.nobs}  residuos={len(r)}  desfase={desf}")
print(f"residuo mayor: obs {obs}  z={z[obs - 1]:+.2f}")
print(f"  _alternativas_desde._fecha : {como_hoy}")
print(f"  con desfase_observaciones  : {correcta}   (el .out dice 12/2021)")
print("REPRODUCIDO" if como_hoy != correcta else "no reproduce")
