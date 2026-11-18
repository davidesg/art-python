#!/usr/bin/env python3
"""BUG-0060 — errores tipicos invalidos impresos con el formato de los validos.

BUG-0027 detecta que una covarianza puede ser la semilla del BFGS (c·I) en vez
del hessiano, y el bloque de la ecuacion lo AVISA... debajo. Dentro del cerco,
la cifra sale con el mismo formato que una valida:

    (2)  (1 - 0·B) (∇Nₜ + 0.7202) = aₜ
                        (0.1552)

0.1552 es exactamente √(2/n) con n=83. El t que sale de ahi es -4.64. El honesto,
σ̂ₐ/√n = 0.2966, da **-2.43**. De abrumador a justo significativo, que es la
diferencia entre incluir la media y no incluirla.

Uso:  python repro.py
"""
import sys, os, math, warnings
warnings.filterwarnings("ignore")

import os as _os
import sys as _sys
# The replica's tree is private data, outside the repository: its path comes in
# ART_REPLICA (and ART_REPLICA_DS); without it this repro cannot run (exit 2).
_REPLICA = _os.environ.get("ART_REPLICA", "").rstrip("/")
_REPLICA_DS = _os.environ.get("ART_REPLICA_DS", "").rstrip("/")
if not _REPLICA:
    print("needs ART_REPLICA (the replica's tree; private data, not in the repository)")
    _sys.exit(2)

R = _REPLICA + "/"
CASOS = [("ITCER_m00mu — todo semilla", R + "run3/ITCER/ITCER_m00mu.pre", 1),
         ("PGAS_m03    — parcial",      R + "run3/PGAS/PGAS_m03.pre",     2)]


def main():
    from art.mcp_server import _load_fitted
    from art.describe import model_equation
    from art.diagnosis import bfgs_seed_var

    roto = False
    vivos = 0
    for etq, p, esperados in CASOS:
        if not os.path.exists(p):
            print(f"{etq}: datos no disponibles"); continue
        ts, m = _load_fitted(p)
        r = m._result
        semilla = math.sqrt(bfgs_seed_var(r))
        eq = model_equation(ts, m)
        marcados = eq.count("(✗")
        n_semilla = sum(1 for se in m.std_errors
                        if abs(abs(float(se)) - semilla) <= 1e-4 * semilla)

        print(f"=== {etq}   niter={getattr(r,'niter','?')}  npar={r.npar}")
        print(f"    semilla √(2/n) = {semilla:.4f}")
        print(f"    errores que SON la semilla: {n_semilla}   marcados en el bloque: {marcados}")
        if n_semilla == 0:
            print("    ya no es un testigo: ningún error típico en la semilla (fdhess)")
            continue
        vivos += 1
        ok = (marcados == n_semilla == esperados)
        print(f"    {'OK' if ok else 'FALLO'}  (esperados {esperados})")
        if n_semilla and "NO VÁLIDO" not in eq:
            print("    falta la leyenda del marcador  ← el bug"); ok = False
        roto |= not ok
        print()

    if not vivos:
        # Con fue >= 0.1.17 los errores típicos son del hessiano por diferencias
        # y no hay semilla: los testigos no miden nada. La lógica la guardan las
        # pruebas sintéticas de tests/test_bug_0060_errores_tipicos_marcados.py.
        print("ningún testigo de la réplica tiene ya errores en la semilla: no mide nada")
        return 2
    # El error tipico honesto de mu, cuando no hay ARMA libre
    p = R + "run3/ITCER/ITCER_m00mu.pre"
    if os.path.exists(p):
        ts, m = _load_fitted(p)
        eq = model_equation(ts, m)
        tiene = "el error típico correcto es" in eq
        print(f"¿se publica el error tipico honesto de μ?  {'si' if tiene else 'NO  ← el bug'}")
        if tiene:
            print("   " + next(l.strip() for l in eq.splitlines()
                               if "el error típico correcto" in l))
        roto |= not tiene

    print("\n" + ("BUG PRESENTE" if roto else
                  "ARREGLADO: se marcan dentro del cerco y se da el honesto"))
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
