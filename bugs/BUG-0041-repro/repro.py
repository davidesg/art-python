#!/usr/bin/env python3
"""BUG-0041 — la guarda de covarianza degenerada sólo caza la semilla EXACTA.

BUG-0027 detecta los errores típicos que son la semilla del BFGS (c·I, con
c = 2/n) en vez del hessiano. Su comparación es

    abs(d[i] - semilla) <= 1e-5 * semilla

es decir, igualdad. Caza la dirección que el optimizador no tocó nunca
(`niter=0`) y nada más. Pero una dirección que se movió un 7% tampoco lleva
información del hessiano, y no disparaba ningún aviso.

Testigo real: ITCER de la réplica del TFM, modelo de dos parámetros con
`niter=2`. La varianza de μ salió 0.022473 contra una semilla de 0.024096 — el
93% de ella. El error típico publicado fue 0.1499, cuando el correcto para un
modelo sin ARMA es la desviación típica residual sobre √n = 0.2864: **la mitad**,
sin ningún aviso. El mismo modelo con una intervención más y `niter=5` dio
0.2687, que sí coincide.

Lo encontró el experimento del chat limpio, que sospechó del número (por un
motivo equivocado: comparó el error típico del PARÁMETRO μ con el "Standard
error of mean" del bloque de residuos, que es σ_a/√n y es otra cosa). La
sospecha era buena aunque el argumento no lo fuera.

Uso:  python repro.py
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np

from art.diagnosis import (BANDA_CASI_SEMILLA, bfgs_seed_var,
                           degenerate_variance_indices,
                           near_seed_distances,
                           near_seed_variance_indices)


class _Res:
    """Lo justo de un resultado de fue para las dos guardas."""

    def __init__(self, n, varianzas, niter):
        self.residuals = np.zeros(n)
        self.cov_matrix = np.diag(np.asarray(varianzas, dtype=float))
        self.niter = niter
        self.npar = len(varianzas)


def main():
    n = 83
    semilla = 2.0 / n
    print(f"n = {n}   semilla del BFGS = 2/n = {semilla:.6f}  (√ = {semilla**0.5:.4f})")
    print(f"banda de sospecha: distancia relativa ≤ {BANDA_CASI_SEMILLA:.0%}")
    print()

    casos = [
        ("niter=0, la semilla EXACTA", [semilla], 0),
        ("niter=2, al 93% de la semilla (ITCER m01)", [3.404577, 0.022473], 2),
        ("niter=5, movida de verdad (ITCER m02)", [5.992264, 0.072188], 5),
    ]
    for etq, var, niter in casos:
        r = _Res(n, var, niter)
        ex = degenerate_variance_indices(r)
        casi = near_seed_variance_indices(r)
        dist = near_seed_distances(r)
        print(f"{etq}")
        print(f"   varianzas   = {[round(v, 6) for v in var]}")
        print(f"   exactas     = {ex}"
              + ("      → veredicto: NO válidos" if ex else ""))
        print(f"   sospechosas = {casi}"
              + (f"   dist = {[f'{dist[i]*100:+.1f}%' for i in casi]}" if casi else "")
              + ("      → aviso: contrastar" if casi else ""))
        print()

    r = _Res(n, [3.404577, 0.022473], 2)
    if near_seed_variance_indices(r) and not degenerate_variance_indices(r):
        print("BUG-0041 REPRODUCIDO y ARREGLADO: la varianza al 93% de la semilla")
        print("  no era exacta —así que la guarda de BUG-0027 la dejaba pasar— y")
        print("  ahora se marca como sospechosa, con su distancia.")
        print()
        print("  Y sigue siendo SOSPECHA, no veredicto: una varianza puede valer")
        print("  2/n legítimamente. Lo que se publica es la distancia, para que")
        print("  quien lea decida — marcarla como inválida sería un falso")
        print("  positivo caro.")
    else:
        print("(!) el testigo no separa las dos guardas.")


if __name__ == "__main__":
    main()
