#!/usr/bin/env python3
"""BUG-0035 — meg_reformulate no escribía el `.inp`, y rotulaba el modelo con el
nombre del anterior.

El convenio de ficheros de la suite tiene tres piezas: el `.inp` es la
ESPECIFICACIÓN, el `.pre` es ese mismo modelo con las estimaciones como nuevos
valores iniciales (un óptimo reejecutable) y el `.out` es el registro. Todas las
herramientas de estimación escriben la terna. `meg_reformulate` escribía `.pre` y
`.out` y NO el `.inp` de `output_path` — el fichero cuya ruta el propio llamador
había pasado.

Consecuencia: el paso siguiente (`formal_tests` sobre ese `.inp`) moría con
FileNotFoundError, y el eslabón no se podía reestimar, que es de donde salen los
errores típicos válidos (BUG-0027).

Y como la ecuación se componía del modelo en memoria —heredado del de origen— el
bloque salía rotulado con el nombre del modelo ANTERIOR.

Uso:  python repro.py
"""
import os
import tempfile
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art import mcp_server as M
from art.pipeline import _make_model, _write_inp, _load_fitted


def serie(n=100, seed=6):
    rng = np.random.default_rng(seed)
    a = np.cumsum(rng.standard_normal(n)) * 0.5
    b = np.cumsum(rng.standard_normal(n)) * 0.5
    t = np.arange(n)
    est = a * np.cos(np.pi / 2 * t) + b * np.sin(np.pi / 2 * t)
    nivel = 100.0 + np.cumsum(rng.standard_normal(n)) + est
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="BASE")


def main():
    ts = serie()
    with tempfile.TemporaryDirectory() as td:
        # línea base determinista: armónicos, sin ARMA
        base = os.path.join(td, "BASE_m00.inp")
        _write_inp(ts, _make_model(ts, 1.0, 1, 0, 0, 0, 1, seasonal=True), base)
        _, m0 = _load_fitted(base)
        m0.write_pre(os.path.join(td, "BASE_m00.pre"))

        salida = os.path.join(td, "BASE_m10.inp")
        res = M.meg_reformulate(os.path.join(td, "BASE_m00.pre"), 1, salida,
                                base_pre_path=os.path.join(td, "BASE_m00.pre"))
        txt = res[0].text
        rotulo = [l for l in txt.splitlines() if "MODELO ESTIMADO" in l]
        print("rótulo del bloque:", rotulo[0].strip() if rotulo else "(no hay)")

        ficheros = sorted(f for f in os.listdir(td) if f.startswith("BASE_m10"))
        print("ficheros escritos para m10:", ficheros)

        hay_inp = os.path.exists(salida)
        print(f"¿existe el .inp que se pidió? {hay_inp}")

        print()
        if not hay_inp:
            print("BUG-0035 REPRODUCIDO: la herramienta devuelve una ruta .inp")
            print("  que no ha escrito. El paso siguiente sobre ella falla.")
        else:
            print("BUG-0035 ARREGLADO: la terna .inp/.pre/.out está completa,")
            print("  y el rótulo lleva el nombre del fichero que se escribió.")
            ok = "BASE_m10" in (rotulo[0] if rotulo else "")
            print(f"  rótulo coherente con el fichero: {ok}")


if __name__ == "__main__":
    main()
