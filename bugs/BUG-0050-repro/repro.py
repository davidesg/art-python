#!/usr/bin/env python3
"""BUG-0050 — la documentación decía que P/Q son «D=1 only». Es falso.

`confirm_and_estimate` documentaba:

    P : seasonal AR order (D=1 only)
    Q : seasonal MA order (D=1 only)

`_make_model` construye un AR estacional con D=0 desde siempre --lleva su propio
comentario, «Stationary stochastic seasonality on top of the deterministic
harmonics»-- y es la forma en que la ruta B1 absorbe lo que los armónicos dejan.

El coste de creérselo no es cosmético. Un analista que ve un AR estacional
residual y lee «D=1 only» concluye que la única salida es diferenciar
estacionalmente, o sea la ruta B2: **justo la que `objetivo="multivariante"`
prohíbe**. La documentación te manda a la ruta prohibida a resolver un problema
que la ruta permitida resuelve.

Uso:  python repro.py
"""
import sys, os, tempfile, warnings, inspect
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.pipeline import _load_ts_model


def serie(n=120, Phi=0.65, seed=11):
    """Trimestral, D=0: armónico fijo + AR(1) ESTACIONAL sobre la diferencia."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(n + 40)
    w = np.zeros(n + 40)
    for t in range(4, n + 40):
        w[t] = Phi * w[t - 4] + a[t]           # AR(1)_4 estacionario
    w = w[40:]
    t = np.arange(n)
    nivel = np.cumsum(w) / 40.0 + 0.06 * np.cos(2 * np.pi * t / 4.0)
    return fue.TimeSeries((100.0 * np.exp(nivel)).tolist(),
                          freq=4, start=(2000, 1), name="PD0")


def main():
    import art.mcp_server as M
    doc = (getattr(M.confirm_and_estimate, "fn", M.confirm_and_estimate).__doc__) or ""

    print("1) ¿Qué dice la documentación?")
    # La comprobación tiene que ser PRECISA: el informe del arreglo cita la
    # frase antigua, así que buscar "(D=1 only)" suelto se autodetecta.
    falso = "seasonal AR order (D=1 only)" in doc
    print(f"   «D=1 only» presente: {falso}"
          f"{'   ← la afirmación falsa' if falso else '   ← corregida'}")

    print("\n2) ¿Existe P=1 con D=0 en el propio proyecto?")
    R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/"
    for f in ("guiado/RATIO/RATIO_m31.pre", "run2/RATIO/RATIO_m03.pre"):
        p = R + f
        if not os.path.exists(p):
            print(f"   {f}: no disponible"); continue
        L = open(p, encoding="utf-8", errors="replace").read().splitlines()
        P = D = None
        for i, l in enumerate(L):
            if "annual AR operators" in l:  P = L[i + 1].split()[0]
            if "Box-Cox lambda" in l:       D = L[i + 1].split()[2]
        print(f"   {f}:  P={P}  D={D}   "
              f"{'← AR estacional CON D=0' if P == '1' and D == '0' else ''}")

    print("\n3) ¿Lo estima el motor sobre datos sintéticos?")
    ts = serie()
    tmp = tempfile.mkdtemp(prefix="bug0050_")
    from art.pipeline import build_and_fit, ModelSpec
    spec = ModelSpec(lam=0.0, d=1, D=0, p=0, q=0, P=1, Q=0, n_harmonics=1,
                     seasonal=True)
    fr = build_and_fit(ts, spec, os.path.join(tmp, "PD0.inp"), 3.5)
    ar_s = getattr(fr.model, "ar_s", None) or []
    Phi = None
    for f_ in ar_s:
        pars = getattr(f_, "params", None) or getattr(f_, "coeffs", None)
        if pars is not None:
            Phi = float(pars[0])
    print(f"   estimado sin error con D=0 y P=1 → Phi_4 = "
          f"{Phi:.4f}" if Phi is not None else "   estimado sin error con D=0 y P=1")
    qmin = min(fr.diag.q_pvalues) if fr.diag.q_pvalues else float("nan")
    print(f"   Q p-minimo = {qmin:.4f}  "
          f"({'ruido blanco' if qmin > 0.05 else 'queda estructura'})")

    print("\n" + ("BUG PRESENTE: la documentación afirma lo contrario de lo que "
                  "el motor hace" if falso else
                  "ARREGLADO: la documentación describe lo que el motor hace"))
    return 1 if falso else 0


if __name__ == "__main__":
    sys.exit(main())
