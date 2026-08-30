#!/usr/bin/env python3
"""BUG-0033 — σ̂ₐ lleva un `%` que sólo es cierto si λ=0.

fue escala los residuos por `refactor` (×100 de serie). Qué SIGNIFICA ese
residuo escalado depende de λ:

    λ=0, refactor=100  →  ∇ln(y)·100   ES un porcentaje.
    λ=1, refactor=100  →  ∇y·100       son las UNIDADES de la serie ×100.

La regla miraba sólo `refactor` y ponía el `%` en los dos casos. En un modelo en
niveles eso publica un número 100× inflado con una etiqueta que miente.

Este repro estima la MISMA serie dos veces, en logs y en niveles, con la misma
especificación, y enseña que la innovación real es prácticamente idéntica —
mientras la línea impresa las separaba en dos órdenes de magnitud.

Uso:  python repro.py
"""
import warnings
warnings.filterwarnings("ignore")

import os
import tempfile

import numpy as np
import fue
from art.describe import model_equation
from art.pipeline import _make_model, _write_inp


def serie():
    """Nivel positivo con crecimiento e innovación multiplicativa ~8%."""
    rng = np.random.default_rng(11)
    n = 84
    w = 0.08 * rng.standard_normal(n)          # 8% en log-diferencias
    level = 300.0 * np.exp(np.cumsum(w) - np.arange(n) * 0.0)
    return fue.TimeSeries(level.tolist(), freq=4, start=(2004, 1), name="NIVEL")


def linea_sigma(ts, m):
    return [l.strip() for l in model_equation(ts, m).splitlines() if "σ̂ₐ" in l][0]


def main():
    ts = serie()
    y = np.asarray(ts.data, float)
    print(f"serie: media={y.mean():.2f}  min={y.min():.2f}  max={y.max():.2f}\n")

    # Hay que pasar POR EL .inp: el factor de reescalado ×100 lo pone el
    # escritor de ART, y es justo la rama donde vive el defecto. Un
    # `fue.Model(...)` construido a mano sale con refactor=1 y no lo toca.
    tmp = tempfile.mkdtemp()
    for etq, lam in (("logs   (λ=0)", 0.0), ("niveles (λ=1)", 1.0)):
        ruta = os.path.join(tmp, f"nivel_lam{lam:g}.inp")
        _write_inp(ts, _make_model(ts, lam, 1, 0, 0, 1, 0), ruta)
        ts_l, m = fue.load(ruta)
        m.fit()
        r = np.asarray(m.residuals.data, float)
        refactor = float(getattr(m, "refactor", 1.0))
        sd_crudo = r.std(ddof=1)
        sd_real = sd_crudo / refactor
        print(f"{etq}")
        print(f"   refactor = {refactor:g}")
        print(f"   sd(residuos crudos)       = {sd_crudo:.4f}")
        if lam == 0.0:
            print(f"   -> innovación             = {sd_crudo:.4f}% (el crudo YA es %)")
        else:
            print(f"   -> innovación             = {sd_real:.4f} unidades"
                  f"  = {100*sd_real/y.mean():.3f}% de la media")
        print(f"   ART imprime: {linea_sigma(ts_l, m)}")
        print()

    print("Las dos innovaciones son la MISMA en términos relativos (~8%).")
    print("Si la línea de λ=1 sale con `%` y sin dividir por refactor, el")
    print("defecto sigue: dos modelos equivalentes parecen diferir 100×, y")
    print("eso invalida cualquier comparación entre carriles.")


if __name__ == "__main__":
    main()
