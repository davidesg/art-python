#!/usr/bin/env python3
"""BUG-0068 — el lado AR del par se pierde con un AR de raices complejas.

Shin-Fuller aisla UNA raiz REAL (ec. 2.2-2.3: (m - rho)*A(m) con rho real). Un AR
cuyas raices son un par conjugado no admite esa forma, asi que el contraste no
existe sobre ese modelo — y quedarse solo con el DCD **pierde el par**, que es lo
que da valor a los contrastes de frontera: dos nulas OPUESTAS.

La salida de la escuela: si el AR(p) no ofrece una raiz real, se sobreajusta a
AR(p+1), se factoriza en AR(1)*AR(p), y se contrasta el AR(1).

Medido sobre 40 replicas por celda (n=83), condicionado a que el AR(2) salga
complejo, que es donde la pregunta se plantea:

    verdad                       AR(3)+SF -> d+1   DCD solo -> d+1   dAIC
    estacionario complejo 1.95        0/37              3/37       +1.10
    estacionario complejo 1.30        0/40              3/40       +0.62
    I(1) x complejo       1.95       14/16             13/16       -3.79
    I(1) x complejo       1.30       32/35             33/35      -23.64

Tamaño 0/77 y potencia 88-91%. Y el dAIC del propio sobreajuste dice en que
mundo se esta: con la verdad estacionaria la raiz añadida es espuria y se paga
(+0.6 a +1.1); con raiz unitaria el AR(p+1) mejora mucho (-3.8 a -23.6).

Uso:  python repro.py
"""
import sys, os, warnings
warnings.filterwarnings("ignore")

M20 = ("/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/guiado/"
       "PGAS/PGAS_m20.pre")


def main():
    if not os.path.exists(M20):
        print("datos de la replica no disponibles"); return 0

    import numpy as np, fue
    from art.formal_tests import shin_fuller, shin_fuller_sobreajuste
    from art.describe import describe_formal_tests

    ts, m = fue.load(M20); m.fit()
    r = np.roots([-c for c in reversed(m.ar[0])] + [1.0])
    print(f"AR(2) del benchmark: raices "
          f"{[complex(round(z.real,3), round(z.imag,3)) for z in r]}")
    print(f"   ¿alguna REAL?  {any(abs(z.imag) < 1e-8 for z in r)}")

    print("\n1) Shin-Fuller directo:")
    try:
        shin_fuller(m); print("   aplica (no es el caso que motiva la rama)")
        return 1
    except ValueError as e:
        print(f"   no aplica — {str(e)[:70]}…")

    print("\n2) Lado AR recuperado por sobreajuste:")
    so = shin_fuller_sobreajuste(m)
    print(f"   AR({so.p_original}) -> AR({so.p_ampliado})   convergido={so.convergido}")
    print(f"   raiz REAL aislada: phi={so.phi_real:.4f}")
    print(f"   Phi_1u={so.sf.phi_1u:.3f} (crit 5%={so.sf.crit_5pct:.2f}) -> "
          f"{'estacionario' if so.sf.stationary else 'raiz unitaria -> d+1'}")
    print(f"   dAIC={so.delta_aic:+.2f}  -> raiz "
          f"{'ESPURIA (no compra nada)' if so.la_raiz_parece_espuria else 'captura algo real'}")

    print("\n3) ¿Llega al informe, y marcada como diagnostico?")
    t = describe_formal_tests(m).summary
    ok = ("recuperado por SOBREAJUSTE" in t
          and "No adoptes este modelo" in t
          and "ΔAIC del sobreajuste" in t)
    print(f"   {'si' if ok else 'NO  <- el bug'}")
    # y no puede contradecirse
    coherente = "no existe en esta corrida" not in t
    print(f"   ¿coherente (no dice «no existe» y luego lo recupera)?  "
          f"{'si' if coherente else 'NO'}")

    bien = ok and coherente
    print("\n" + ("ARREGLADO: el par queda recuperado — DCD por el lado MA, "
                  "sobreajuste por el lado AR" if bien else "BUG PRESENTE"))
    return 0 if bien else 1


if __name__ == "__main__":
    sys.exit(main())
