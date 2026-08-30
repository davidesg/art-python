#!/usr/bin/env python3
"""BUG-0047 — `max_rounds=0` no estimaba NADA, y el None reventaba abajo.

`_outlier_loop` recorre `range(1, max_rounds + 1)`. La ronda 1 no interviene:
es la estimación BASE, con la lista de intervenciones vacía; las intervenciones
sólo se añaden AL FINAL de una ronda, para la siguiente. O sea que `max_rounds`
cuenta rondas de intervención y la primera vuelta no es una.

Con `max_rounds=0` --que es lo que escribe quien quiere decir "estima, pero no
me añadas intervenciones"-- el rango sale VACÍO. No se estima nada, `m_fit` se
queda en `None`, y `run_full` se lo pasa a `_write_inp`, que hace
`model.interventions` y muere con

    AttributeError: 'NoneType' object has no attribute 'interventions'

Un AttributeError en las tripas por un argumento legal en la frontera.

Uso:  python repro.py
"""
import sys, tempfile, os, warnings
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.pipeline import run_full


def serie(n=80, seed=3):
    rng = np.random.default_rng(seed)
    tend = np.cumsum(rng.standard_normal(n)) / 60.0
    return fue.TimeSeries((100.0 * np.exp(tend)).tolist(),
                          freq=4, start=(2000, 1), name="LLANA")


def main():
    ts  = serie()
    tmp = tempfile.mkdtemp(prefix="bug0047_")

    print("max_rounds  modelo devuelto")
    print("-" * 34)
    roto = False
    for mr in (0, 1, 2):
        out = os.path.join(tmp, f"m{mr}.inp")
        try:
            r = run_full(ts, out, max_rounds=mr)
            estado = "None  ← el agujero" if r.final_model is None else "ajustado"
            roto |= r.final_model is None
        except AttributeError as e:
            estado = f"AttributeError: {e}"
            roto = True
        print(f"    {mr}       {estado}")

    print("\n" + ("BUG PRESENTE" if roto
                  else "ARREGLADO: siempre hay una estimación base; 0 y 1 "
                       "coinciden, que es lo que significan"))
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
