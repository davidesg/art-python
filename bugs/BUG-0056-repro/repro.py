#!/usr/bin/env python3
"""BUG-0056 — `unit_root_analysis` se salta la capa de politica y dice «Usa d=2».

El tope de la escuela --un paso cada vez, y la estacionalidad acota d-- vive en
`policy.decide_d`, y eso es correcto por diseño: `describe_unit_root` es la CAPA
DE EVIDENCIA y `recommended_d` informa en crudo de lo que los contrastes
encuentran. El propio docstring de `decide_d` lo dice: «This is a POLICY cap, so
the table still shows that d=2 was suggested».

Lo que estaba mal es el TEXTO. Hablaba con voz de recomendacion --«Recomendacion:
d = 2», «Usa d=2»-- sin mencionar el tope ni que la estacionalidad no se ha
contrastado todavia. Un analista que llama a la herramienta directamente se salta
la politica sin enterarse y vuelve al salto d=0 -> d=2 que BUG-0016 y BUG-0023
arreglaron aguas abajo.

Sobre RATIO: d=0 raiz unitaria, d=1 AMBIGUO, d=2 estacionaria. Recomendaba 2,
saltandose la duda entera. Los dos carriles del RUN 3 llamaron a esta herramienta
y los dos volvieron a evaluar d=2.

Uso:  python repro.py
"""
import sys, warnings
warnings.filterwarnings("ignore")

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/"


def main():
    import os
    if not os.path.exists(R + "RATIO.inp"):
        print("datos de la replica no disponibles"); return 0

    from art.pipeline import _load_ts_model
    from art.describe import describe_unit_root
    from art.policy import decide_d

    roto = False
    for serie in ("RATIO", "ITCER", "PGAS"):
        ts, _ = _load_ts_model(R + f"{serie}.inp")
        d = describe_unit_root(ts, lam=0.0, max_d=2)
        crudo = d.data["recommended_d"]
        pol = decide_d(d.data, seasonal=None, current_d=0, max_step=1)
        avisa = "Punto de partida recomendado" in d.summary
        manda = ("Usa d=" in d.recommendation)

        print(f"=== {serie}")
        print(f"    evidencia (crudo)          d = {crudo}")
        print(f"    politica (un paso)         d = {pol}")
        if crudo != pol:
            print(f"    ¿el texto avisa del tope?  {'si' if avisa else 'NO  ← el bug'}")
            print(f"    ¿ordena «Usa d={crudo}»?      "
                  f"{'SI  ← el bug' if manda else 'no'}")
            roto |= (not avisa) or manda
        else:
            print(f"    (coinciden: no hay nada que advertir"
                  f"{', y no se advierte' if not avisa else ', pero AVISA igual ← ruido'})")
            roto |= avisa
        print()

    print("BUG PRESENTE" if roto else
          "ARREGLADO: la evidencia sigue cruda, el texto lleva el tope y su razon")
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
