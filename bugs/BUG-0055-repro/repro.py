#!/usr/bin/env python3
"""BUG-0055 — un titular que el propio bloque retira tres parrafos mas abajo.

El DCD de sobrediferenciacion imprimia en negrita

    → considerar d+1 ✗

y a continuacion, en el mismo bloque:

  * «el critico correcto ahi es mayor, asi que un LR apenas por encima del
    impreso NO es evidencia de d+1»;
  * «Sin par confirmatorio. El veredicto de arriba es UN SOLO lado»;

y el contraste siguiente remataba con «d confirmado por abajo ✓».

El contenido correcto estaba. La JERARQUIA VISUAL trabajaba en su contra: un
titular invita a leer solo el titular, y quien lo hace se va a d=2 sin motivo.
Paso en esta replica -- se adopto un d=2 sobre RATIO que hubo que retractar.

Uso:  python repro.py
"""
import sys, os, warnings, re
warnings.filterwarnings("ignore")

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run2/PGAS/"


def main():
    if not os.path.exists(R + "PGAS_m04.pre"):
        print("datos de la replica no disponibles"); return 0

    from art.mcp_server import _load_fitted
    from art.describe import describe_formal_tests

    _, m = _load_fitted(R + "PGAS_m04.pre")
    t = describe_formal_tests(m).summary
    i = t.find("DCD sobre-diferenciación")
    bloque = t[i:i + 1400]
    titular = bloque.splitlines()[1] if len(bloque.splitlines()) > 1 else ""

    print("TITULAR:")
    print("   " + titular.strip())
    print("\nAVISOS EN EL MISMO BLOQUE:")
    for l in bloque.splitlines()[2:]:
        ls = l.strip()
        if ls.startswith(("ℹ", "⚠")):
            print("   " + ls[:150])

    afirma_sin_matiz = ("considerar d+1" in titular and
                        "NO es concluyente" not in titular and
                        "un solo lado" not in titular)
    print("\n¿el titular afirma d+1 sin matiz?  "
          f"{'SI  ← el bug' if afirma_sin_matiz else 'no'}")
    print("\n" + ("BUG PRESENTE" if afirma_sin_matiz else
                  "ARREGLADO: el titular lleva sus salvedades dentro"))
    return 1 if afirma_sin_matiz else 0


if __name__ == "__main__":
    sys.exit(main())
