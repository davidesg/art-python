#!/usr/bin/env python3
"""BUG-0051 — se comparaban AIC de modelos con diferenciación distinta.

`_extract_spec` construía el diccionario de especificación SIN `ifadf`, la
diferenciación por frecuencia. Con eso se caía de todo lo que usa el spec:

  * la ECUACIÓN: un modelo con ifadf=[0,1,0] se escribía «∇[ln y_t]», igual que
    uno con ifadf=[0,0,0], cuando explica (1+B²)∇ln y;
  * el DIFF de versiones: el cambio no se anunciaba;
  * el ANIDAMIENTO: `_nested_relation` comparaba d y D, nunca ifadf ni lambda.

Consecuencia: `compare_versions` ponía lado a lado dos modelos que explican
VARIABLES DEPENDIENTES DISTINTAS, con distinto número efectivo de observaciones,
y publicaba ΔAIC y ΔBIC como si significaran algo. Sobre RATIO daba a `m06` una
ventaja de 14.4 puntos de AIC sobre `m03` con la σ̂ₐ prácticamente IGUAL y la
diagnosis de `m06` FALLANDO. Una mejora de ajuste real no puede dejar σ igual.

Y calculaba un LR de **-12.441**: un LR negativo entre modelos anidados es
imposible --el modelo más rico no puede ajustar peor-- y es la prueba de que las
verosimilitudes no están en la misma escala. Se imprimía como «mejora no
significativa, p=1.0000».

Uso:  python repro.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run2/RATIO/"


def main():
    from art.guion import _extract_spec, _build_equation
    from art.mcp_server import _load_fitted, _spec_diff, _nested_relation

    a, b = R + "RATIO_m03.pre", R + "RATIO_m06.pre"
    if not (os.path.exists(a) and os.path.exists(b)):
        print("datos de la replica no disponibles"); return 0

    _, ma = _load_fitted(a)
    _, mb = _load_fitted(b)
    sa = _extract_spec(ma, lam=0.0)
    sb = _extract_spec(mb, lam=0.0)

    print("1) ¿Lleva el spec la diferenciacion por frecuencia?")
    print(f"   m03 ifadf = {sa.get('ifadf', 'AUSENTE')}")
    print(f"   m06 ifadf = {sb.get('ifadf', 'AUSENTE')}")

    print("\n2) ¿Lo dice la ecuacion?")
    print(f"   m03: {_build_equation(sa, ma.series.freq)}")
    print(f"   m06: {_build_equation(sb, mb.series.freq)}")

    print("\n3) ¿Lo anuncia el diff?")
    ch = _spec_diff(sa, sb)
    print(f"   cambios: {', '.join(ch)}")
    dice_ifadf = any("ifadf" in c for c in ch)

    print("\n4) ¿Se declaran anidados?")
    rel = _nested_relation(sa, sb, ma._result.npar, mb._result.npar)
    print(f"   relacion = {rel}   (con transformaciones distintas debe ser 'none')")

    print("\n5) Los numeros que se comparaban:")
    print(f"   loglik  m03={ma._result.loglik:9.3f}   m06={mb._result.loglik:9.3f}")
    print(f"   AIC     m03={ma._result.aic:9.2f}   m06={mb._result.aic:9.2f}"
          f"   (Δ={mb._result.aic - ma._result.aic:+.2f})")
    import math
    s_a = math.sqrt(ma._result.sigma2); s_b = math.sqrt(mb._result.sigma2)
    print(f"   sigma_a m03={s_a:9.5f}   m06={s_b:9.5f}"
          f"   (Δ={s_b - s_a:+.5f})  ← practicamente IGUAL")
    # La herramienta declaraba m06 anidado en m03 ("A es mas rico, B en A") y
    # calculaba el LR en ESA direccion. Ese es el signo del sintoma.
    lr = 2.0 * (ma._result.loglik - mb._result.loglik)
    print(f"   LR = 2*(m03 - m06) = {lr:+.3f}   "
          f"{'← NEGATIVO: imposible entre anidados, y se publicaba como '
             'p=1.0000' if lr < 0 else ''}")

    ok = ("ifadf" in sa) and dice_ifadf and rel == "none"
    print("\n" + ("ARREGLADO: la transformacion viaja en el spec, se anuncia, y "
                  "el anidamiento la exige" if ok else "BUG PRESENTE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
