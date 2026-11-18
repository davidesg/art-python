#!/usr/bin/env python3
"""BUG-0054 — la alarma de estacionalidad residual se leia sobre residuos sucios.

`detect_seasonality` corre una regresion armonica con F de HAC. Aplicada a los
RESIDUOS de un modelo, hereda la regla de siempre: sobre residuos que no son
ruido blanco no es un contraste debil, NO ES UN CONTRASTE.

El mecanismo es inmediato en trimestral: el retardo 2 ES la frecuencia de
Nyquist --el armonico semestral (-1)^t--, asi que una ACF(2) positiva sin
modelar entra en la regresion armonica como si fuera patron estacional.

Caso real: PGAS_m03 (MA(1)) daba F=3.16, p=0.0293 sobre una serie cuyo contraste
en el NODO estacional habia dado F=0.669, p=0.5734. Corregido el orden a MA(2)
la alarma desaparece sola, sin tocar nada estacional.

Uso:  python repro.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")

import numpy as np

import os as _os
import sys as _sys
# The replica's tree is private data, outside the repository: its path comes in
# ART_REPLICA (and ART_REPLICA_DS); without it this repro cannot run (exit 2).
_REPLICA = _os.environ.get("ART_REPLICA", "").rstrip("/")
_REPLICA_DS = _os.environ.get("ART_REPLICA_DS", "").rstrip("/")
if not _REPLICA:
    print("needs ART_REPLICA (the replica's tree; private data, not in the repository)")
    _sys.exit(2)

R = _REPLICA + "/run2/PGAS/"


def main():
    if not os.path.exists(R + "PGAS_m03.pre"):
        print("datos de la replica no disponibles"); return 0

    from art.mcp_server import _load_fitted
    from art.diagnosis import diagnose
    from art.describe import describe_diagnosis
    from fue.diagnostics import acf

    print(f"{'modelo':8s} {'Q p-min':>9s} {'blanco':>7s} {'F seas':>8s} {'p seas':>8s}"
          f"  {'ACF(1)':>8s} {'ACF(2)':>8s}   alarma")
    avisado = None
    for m in ("m03", "m04"):
        _, mm = _load_fitted(R + f"PGAS_{m}.pre")
        dg = diagnose(mm)
        q = min(dg.q_pvalues)
        a = np.asarray(acf(np.asarray(dg.residuals), lags=2))
        ss = dg.seasonal
        salta = bool(ss and ss.seasonal_detected)
        txt = describe_diagnosis(mm).summary
        if salta:
            avisado = "NO LEÍBLE" in txt
        print(f"{m:8s} {q:9.4f} {'si' if q > 0.05 else 'NO':>7s} "
              f"{(ss.f_stat if ss else 0):8.2f} {(ss.p_value if ss else 1):8.4f}"
              f"  {a[0]:+8.3f} {a[1]:+8.3f}   {'SALTA' if salta else '-'}")

    print("\nm03 tiene los residuos sucios Y la alarma; m04 corrige el ARMA")
    print("regular y las dos cosas se callan a la vez. La estacionalidad no se")
    print("toco en ningun momento.")
    print("\n¿La alarma de m03 avisa de que no es leible?  "
          f"{'si' if avisado else 'NO'}")
    if avisado is None:
        # Ya no es un testigo: m03 no levanta hoy la alarma (fue >= 0.1.17 estima
        # mejor). La lógica la guardan las pruebas sintéticas de
        # tests/test_bug_0054_0055_avisos_legibles.py.
        print("\nel testigo de la réplica ya no levanta la alarma: no mide nada")
        return 2
    print("\n" + ("ARREGLADO" if avisado else "BUG PRESENTE"))
    return 0 if avisado else 1


if __name__ == "__main__":
    sys.exit(main())
