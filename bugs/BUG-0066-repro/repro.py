#!/usr/bin/env python3
"""BUG-0066 — la FLT de una intervención se imprime con el signo crudo,
pero fue la estima restada (ω₀ − ω₁B − …).

Caso real que lo delató: ES_CORE, FLT (ω₀ − ω₁B) Step 9/2012.
  omega almacenado = [0.7397, −0.4296]
  display          = "(0.7397 − 0.4296·B)"   ← signo CRUDO (_sign_det)
  motor            = 0.7397 − (−0.4296)·B = 0.7397 + 0.4296·B
  (equivalencia comprobada: dos steps separados Step(9)=+0.7397,
   Step(10)=+0.4296 dan el MISMO loglik → el motor RESTA ω₁)

Aquí se reproduce de forma autocontenida: serie sintética con un escalón de
DOS subidas en t=24 y t=25. La FLT que lo representa es v(B) = 1.0 + 0.5B, que
el motor parametriza como ω = [1.0, −0.5]. El display correcto es "(1.0 + 0.5·B)";
con el bug imprime "(1.0 − 0.5·B)".

Uso:  python repro.py
"""
import sys


def main():
    import numpy as np
    import fue
    from fue.report import _extract_fitted
    from art.describe import model_equation

    # Serie sintética (centrada en 0, ruido): escalón con dos subidas
    # (+1.0, +0.5). Sin constante ni tendencia, ω₀ ≈ +1.0 y ω₁ ≈ −0.5.
    rng = np.random.default_rng(0)
    n = 60
    x = [0.05 * rng.standard_normal() for i in range(n)]
    for i in range(24, n):
        x[i] += 1.0 + (0.5 if i >= 25 else 0.0)

    ts = fue.TimeSeries(x, freq=12, start=(2000, 1), name="SINT")
    itv = fue.Intervention(type="step", at=24, omega=[1.0, -0.5],
                           omega_free=[True, True])
    m = fue.Model(ts, interventions=[itv], d=0)
    m.fit()

    fit = _extract_fitted(m, m._result)
    w = fit["omega_vals"][-1]          # omega estimado del step
    w0, w1 = w[0], w[1]
    eq = model_equation(ts, m)

    # Línea de la intervención con FLT: contiene '·B' y la etiqueta del step.
    flt_line = next((l for l in eq.splitlines()
                     if "·B" in l and "S," in l), "")

    roto = False
    print(f"omega estimado = [{w0:.4f}, {w1:.4f}]")
    print(f"render: {flt_line.strip()}")

    # El motor resta: v(B) = w0 − w1·B.  Con w1 < 0 el término B es +|w1|.
    if w1 < 0:
        bien = f"+ {abs(w1):.4f}·B" in flt_line
        mal = f"− {abs(w1):.4f}·B" in flt_line
        if bien:
            print("OK: término B con signo restado (+|w1|)  ← arreglado")
        elif mal:
            print("FALLO: término B con signo crudo (−|w1|)  ← el bug")
            roto = True
        else:
            print(f"FALLO: no se pudo leer el signo (buscado '+ {abs(w1):.4f}·B')")
            roto = True
    else:
        # si w1 resultara >= 0 (no debería), el caso no discrimina
        print("(w1 >= 0: el caso no discrimina; repro no concluyente)")

    print("BUG PRESENTE" if roto else "ARREGLADO")
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
