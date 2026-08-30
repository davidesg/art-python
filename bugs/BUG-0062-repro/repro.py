#!/usr/bin/env python3
"""BUG-0062 — un operador fuera de la region admisible se presentaba como bueno.

Un AR con raiz DENTRO del circulo unidad no es estacionario; un MA con raiz
dentro no es invertible. Las dos cosas invalidan la lectura del modelo, y ninguna
se anunciaba.

El caso: `RATIO_m04sma1` estima un MA estacional Theta_4 = -2.0989 --raiz de
modulo 0.831 en B-- tras 45 iteraciones y con `fue` declarando «Check for
invertibility: constrained search» en la cabecera de su propio `.out`. Se
imprimia como cualquier otro resultado; solo la diagnosis rota (Q) delataba que
algo iba mal, que es enterarse por el sintoma equivocado.

Barriendo los 214 modelos de la replica salen DOS casos, y no significan lo
mismo:
  * DENTRO   Theta_4 = -2.0989, |raiz| = 0.831  -> no invertible, inutilizable.
  * FRONTERA MA(4) con dos raices de modulo 1.000000 y d=1  -> el MA cancela la
             diferencia: firma de SOBREDIFERENCIACION, no operador roto.

Uso:  python repro.py
"""
import sys, os, glob, warnings
warnings.filterwarnings("ignore")

BASES = ("/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica",
         "/home/david/Dropbox/TFM_UCM/Tesis_Michael_DS/replica")


def main():
    from art.mcp_server import _load_fitted
    from art.diagnosis import admissibility_problems
    from art.describe import model_equation

    tot, malos = 0, []
    for b in BASES:
        for p in sorted(glob.glob(b + "/*/*/*.pre")):
            try:
                ts, m = _load_fitted(p)
            except Exception:
                continue
            tot += 1
            pr = admissibility_problems(m)
            if pr:
                malos.append((p, m, ts, pr))

    if not tot:
        print("datos de la replica no disponibles"); return 0

    print(f"{tot} modelos barridos, {len(malos)} fuera de la region admisible\n")
    ok = True
    for p, m, ts, pr in malos:
        nom = "/".join(p.split("/")[-3:])
        print(f"=== {nom}")
        for etq, mod, donde in pr:
            print(f"    {etq}: |raiz| = {mod:.6f}   ({donde})")
        eq = model_equation(ts, m)
        avisa = ("OPERADOR NO ADMISIBLE" in eq) or ("OPERADOR EN LA FRONTERA" in eq)
        print(f"    ¿lo avisa la ecuacion?  {'si' if avisa else 'NO  <- el bug'}")
        # el mensaje tiene que corresponder al caso
        if any(d == "dentro" for _, _, d in pr):
            ok &= "NO ADMISIBLE" in eq and "NO INVERTIBLE" in eq
        if any(d == "frontera" for _, _, d in pr):
            ok &= "FRONTERA" in eq and "SOBREDIFERENCIACION" in eq.upper().replace("Ó","O")
        ok &= avisa
        print()

    print("BUG PRESENTE" if not ok else
          "ARREGLADO: se avisa en la ecuacion, y DENTRO y FRONTERA llevan "
          "diagnosticos distintos")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
