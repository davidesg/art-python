"""BUG-0026: `_write_inp` escribe la linea `ifadf` VACIA y el fichero deja de
poder leerse.

`ifadf` especifica las diferencias POR FRECUENCIA e indexa desde f=0, asi que la
linea tiene siempre `freq//2 + 1` entradas:

    trimestral (freq=4)   ->  0 0 0              (f=0, f=1, f=2)
    mensual    (freq=12)  ->  0 0 0 0 0 0 0      (f=0 ... f=6)

El lector cuenta esas posiciones. Si la linea sale vacia se desincroniza, toma la
SIGUIENTE linea --la del Box-Cox, " 1.00  1  0"-- como si fuera la de ifadf, e
intenta convertir '1.00' a entero.

La causa es una guarda que no cubre el caso real:

    ifadf = getattr(model, "ifadf", None)
    if ifadf is None:                     # <- fue.Model guarda [], no None
        ifadf = [0] * (freq // 2 + 1)

`fue.Model(ts, d=1)` sin ifadf lo almacena como LISTA VACIA. El modelo es
legitimo -- fue lo acepta y lo estima -- pero el .inp que produce no se puede
releer. Es decir: un modelo que el motor acepta genera un fichero que el motor
no puede leer.

No muerde en el flujo normal de ART, que puebla ifadf siempre; muerde a quien
construya un Model mediante codigo, que es lo que hacen los tests.

    python3 bugs/BUG-0026-repro/repro.py
"""
import os
import tempfile

import numpy as np

import fue
from art.pipeline import _write_inp, _load_ts_model


def prueba(freq, n):
    y = 100.0 + np.cumsum(np.random.default_rng(1).normal(0, 1.0, n))
    ts = fue.TimeSeries(list(map(float, y)), freq=freq, start=(2004, 1), name="T")
    m = fue.Model(ts, d=1)                      # sin ifadf -> []
    print("  fue.Model(...).ifadf = %r   (no None: la guarda no lo cubre)" % (m.ifadf,))

    d = tempfile.mkdtemp(prefix="bug0026-")
    p = os.path.join(d, "T.inp")
    _write_inp(ts, m, p)

    txt = open(p).read().splitlines()
    k = next(i for i, l in enumerate(txt) if "Individual factors" in l)
    linea = txt[k + 1]
    esperado = freq // 2 + 1
    print("  linea ifadf escrita : %r  -> %d entradas (esperadas %d)"
          % (linea, len(linea.split()), esperado))

    try:
        _load_ts_model(p)
        print("  relectura           : OK")
        return True
    except Exception as e:
        print("  relectura           : FALLA -> %s: %s" % (type(e).__name__, e))
        print("    (ha leido la linea siguiente, la del Box-Cox, como si fuera ifadf)")
        return False


ok = True
for freq, n in ((4, 40), (12, 60)):
    print("─── freq = %d ───" % freq)
    ok &= prueba(freq, n)
    print()

print("BUG-0026 REPRODUCIDO" if not ok else
      "ARREGLADO: la linea lleva freq//2+1 ceros y el fichero se relee.")
