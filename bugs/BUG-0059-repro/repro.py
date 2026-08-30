#!/usr/bin/env python3
"""BUG-0059 — el Box-Cox imprimia el modulo y perdia el signo.

`_abscorr` devolvia `abs(corrcoef(medias, desviaciones))`. El MODULO es el
criterio correcto para decidir --se elige la escala cuya dependencia
media-dispersion esta mas cerca de cero-- pero el SIGNO es el diagnostico, y dice
cosas opuestas:

    corr > 0   la dispersion CRECE con el nivel  →  INFRA-transformado
    corr < 0   la dispersion CAE con el nivel    →  SOBRE-transformado

Lo que de verdad se perdia es el caso de SIGNOS OPUESTOS. Sobre PGAS, lambda=1 da
+0.150 y lambda=0 da -0.173: una escala se queda corta y la otra se pasa, asi que
la lambda correcta esta ENTRE las dos. Impreso en valor absoluto salia «0.150
frente a 0.173, diferencia 0.024, decision ambigua, las dos son razonables», que
es falso: ninguna de las dos lo es.

Uso:  python repro.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/"


def main():
    if not os.path.exists(R + "PGAS.inp"):
        print("datos de la replica no disponibles"); return 0

    from art.pipeline import _load_ts_model
    from art.describe import describe_boxcox

    roto = False
    for s in ("PGAS", "ITCER", "RATIO"):
        ts, _ = _load_ts_model(R + f"{s}.inp")
        d = describe_boxcox(ts)
        c1 = d.data.get("corr_raw_signed")
        c0 = d.data.get("corr_log_signed")
        horq = d.data.get("horquilla")
        print(f"=== {s}")
        if c1 is None:
            print("    el .data NO transporta el signo   ← el bug"); roto = True; continue
        print(f"    lambda=1: {c1:+.3f}   lambda=0: {c0:+.3f}   "
              f"signos {'OPUESTOS' if c1*c0 < 0 else 'iguales'}")
        # ¿aparece el signo impreso?
        impreso = f"{c1:+.3f}" in d.summary and f"{c0:+.3f}" in d.summary
        print(f"    ¿se imprimen con signo?  {'si' if impreso else 'NO  ← el bug'}")
        roto |= not impreso
        if horq:
            aviso = "signos son OPUESTOS" in d.summary.replace("**","")
            print(f"    ¿avisa de la horquilla?  {'si' if aviso else 'NO  ← el bug'}")
            roto |= not aviso
        elif "signos son OPUESTOS" in d.summary.replace("**",""):
            print("    avisa de horquilla SIN haberla  ← ruido"); roto = True
        print()

    print("BUG PRESENTE" if roto else
          "ARREGLADO: el modulo decide, el signo diagnostica, y la horquilla se nombra")
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
