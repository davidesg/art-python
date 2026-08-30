#!/usr/bin/env python3
"""BUG-0063 — el bloque de la media decia «residuos» y medía la serie diferenciada.

`guided_identification` con `pre_path` publica dos cosas distintas:

  * la IDENTIFICACION ARMA, que SI se calcula sobre los residuos del `.pre`;
  * la decision de la MEDIA, que BUG-0013 hizo deliberadamente sobre la SERIE
    DIFERENCIADA.

Las dos reutilizaban la misma etiqueta `data_label`, que con `pre_path` dice
«residuos de X.pre». Correcta para la primera, FALSA para la segunda.

Y la razon de BUG-0013 es justo lo que la etiqueta desmentia: los residuos de un
modelo que YA lleva mu tienen media cero por construccion, asi que medirlos
aconsejaria `estimate_mu=False` en una serie con deriva significativa.

Uso:  python repro.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")

import numpy as np

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run3/"
CASOS = [("PGAS_m03",  R + "PGAS/PGAS_m03.pre"),
         ("ITCER_m02", R + "ITCER/ITCER_m02.pre")]


def main():
    if not os.path.exists(CASOS[0][1]):
        print("datos de la replica no disponibles"); return 0

    from art.mcp_server import _load_fitted, guided_identification
    from art.identification import boxcox_transform as bct, apply_differences as adiff
    import re

    f = getattr(guided_identification, "fn", guided_identification)
    roto = False

    for nom, p in CASOS:
        ts, m = _load_fitted(p)
        res = np.asarray(m.residuals.data, dtype=float)
        w = np.array(adiff(bct(ts.data, 0.0), ts.freq, 1, 0))

        txt = f(p, lam=0.0, d=1, D=0, pre_path=p)
        txt = txt[0].text if isinstance(txt, list) else str(txt)
        i = txt.find("¿Incluir media")
        bloque = txt[i:i + 700]
        mo = re.search(r"μ̄=([-+]?\d+\.\d+)", bloque)
        publicado = float(mo.group(1)) if mo else None

        print(f"=== {nom}")
        print(f"    media de ∇ln y            : {w.mean():+.6f}")
        print(f"    media de los residuos     : {res.mean():+.6f}")
        print(f"    lo que PUBLICA el bloque  : {publicado:+.6f}"
              if publicado is not None else "    (sin cifra)")
        cual = ("∇ln y" if publicado is not None and abs(publicado - w.mean()) < 1e-3
                else "residuos" if publicado is not None else "?")
        print(f"    o sea, mide               : {cual}")

        dice_residuos = "Deriva de residuos" in bloque
        explica = "NO sobre los residuos" in bloque
        print(f"    ¿la etiqueta dice «residuos»?  "
              f"{'SI  <- el bug' if dice_residuos else 'no'}")
        print(f"    ¿explica por que no lo son?    {'si' if explica else 'NO'}")
        roto |= dice_residuos or not explica
        print()

    # La identificacion ARMA SI es sobre residuos: esa etiqueta debe seguir.
    txt = f(CASOS[1][1], lam=0.0, d=1, D=0, pre_path=CASOS[1][1])
    txt = txt[0].text if isinstance(txt, list) else str(txt)
    arma_ok = "residuos de `ITCER_m02.pre`" in txt
    print(f"¿la identificacion ARMA conserva su etiqueta de residuos?  "
          f"{'si' if arma_ok else 'NO  <- se paso de frenada'}")
    roto |= not arma_ok

    print("\n" + ("BUG PRESENTE" if roto else
                  "ARREGLADO: cada bloque nombra lo que mide"))
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
