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

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/"
CASOS = [("ITCER_m00mu — todo semilla", R + "run3/ITCER/ITCER_m00mu.pre", 1),
         ("PGAS_m03    — parcial",      R + "run3/PGAS/PGAS_m03.pre",     2)]


def main():
    from art.mcp_server import _load_fitted
    from art.describe import model_equation
    from art.diagnosis import bfgs_seed_var

    roto = False
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
        ok = (marcados == n_semilla == esperados)
        print(f"    {'OK' if ok else 'FALLO'}  (esperados {esperados})")
        if n_semilla and "NO VÁLIDO" not in eq:
            print("    falta la leyenda del marcador  ← el bug"); ok = False
        roto |= not ok
        print()

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
