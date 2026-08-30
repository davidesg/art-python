#!/usr/bin/env python3
"""BUG-0040 — la taxonomía de dominio era BINARIA, y una magnitud multiplicativa
no tenía dónde caer.

`decide_domain` devolvía `"price_index"` o `"generic"`, y `decide_lambda` sólo
tenía regla para el primero:

    if domain == "price_index":
        return 0.0
    gap = boxcox_data.get("gap", 0.0)
    return 0.0 if gap >= 0 else 1.0

Así que un PRECIO —magnitud multiplicativa con cero natural, donde el log es
práctica estándar— caía en `"generic"` y su λ la decidía el SIGNO de `gap`, un
estadístico que sobre series cortas es ruido.

Es el arreglo de BUG-0015 quedándose corto: se añadió el dominio a la política,
pero con las dos únicas categorías que aquel caso necesitaba. El texto que art
imprime al analista dice «índice de precios **o magnitud multiplicativa**»; el
código no tenía la segunda.

Uso:  python repro.py
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.policy import decide_domain, decide_lambda, DOMINIOS, BANDA_AMBIGUA_BOXCOX
from art.describe import describe_boxcox


def precio(n=84, seed=1):
    """Precio positivo con recorrido de factor ~5 y `gap` casi nulo — el caso
    en que el estadístico no discrimina y el dominio tiene que hablar."""
    rng = np.random.default_rng(seed)
    ciclo = 200.0 * np.sin(np.linspace(0, 2.2 * np.pi, n))
    nivel = 300.0 + ciclo + 25.0 * rng.standard_normal(n)
    nivel = np.clip(nivel, 95.0, None)
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2004, 1), name="PRECIO")


def main():
    print(f"categorías disponibles: {DOMINIOS}")
    print(f"banda en que el estadístico NO discrimina: |gap| < {BANDA_AMBIGUA_BOXCOX}")
    print()

    # ── 1. la clasificación, sobre el dato y no sobre el nombre ─────────────
    ts = precio()
    y = np.asarray(ts.data, float)
    dom = decide_domain(ts)
    print("1) CLASIFICACIÓN")
    print(f"   serie positiva, recorrido {y.min():.1f}–{y.max():.1f} "
          f"(factor {y.max()/y.min():.2f}), nombre 'PRECIO' (no es prefijo de índice)")
    print(f"   dominio inferido = {dom}")
    print(f"   con la taxonomía binaria habría sido: generic")
    print()

    # ── 2. la regla, con el gap MEDIDO sobre el testigo real ───────────────
    # PGAS (precio de exportación del gas boliviano, 95→500 USD/t):
    # corr(media,std) = 0.150 en niveles y 0.173 en logs ⇒ gap = −0.023.
    GAP_PGAS = -0.023
    print("2) LA REGLA, con el gap medido sobre PGAS (gap = %+.3f)" % GAP_PGAS)
    lam_nueva   = decide_lambda({"gap": GAP_PGAS}, dom)
    lam_binaria = decide_lambda({"gap": GAP_PGAS}, "generic")
    print(f"   dominio='{dom}'  → λ = {lam_nueva:g}   (decide el dominio: el gap está dentro de la banda)")
    print(f"   dominio='generic'  → λ = {lam_binaria:g}   ← lo que hacía la taxonomía binaria")
    print()

    if dom == "multiplicative" and lam_nueva == 0.0 and lam_binaria == 1.0:
        print("BUG-0040 REPRODUCIDO y ARREGLADO: un precio se reconoce como")
        print("  magnitud multiplicativa y su λ la decide el dominio. Antes caía")
        print("  en 'generic' y la decidía el SIGNO de un gap de -0.023 — ruido.")
        print("  Medido: con λ=1 ninguno de los seis modelos estimados sobre PGAS")
        print("  alcanzó la adecuación, con el JB entre 46.7 y 8.9.")
    else:
        print(f"(!) sin testigo: dominio={dom}, λ nueva={lam_nueva:g}, binaria={lam_binaria:g}")

    # ── 3. el dominio NO es un decreto: fuera de la banda manda el dato ─────
    print()
    print("3) FUERA DE LA BANDA SIGUE MANDANDO EL DATO")
    for g in (-0.30, -0.05, +0.25):
        lam = decide_lambda({"gap": g}, "multiplicative")
        quien = "el dato" if abs(g) >= BANDA_AMBIGUA_BOXCOX else "el dominio"
        print(f"   gap={g:+.2f} sobre 'multiplicative' → λ={lam:g}   (decide {quien})")
    print()
    print("   Un índice, en cambio, es regla ABSOLUTA — su nivel es una convención:")
    for g in (-0.30, +0.25):
        print(f"   gap={g:+.2f} sobre 'price_index'   → λ={decide_lambda({'gap': g}, 'price_index'):g}")


if __name__ == "__main__":
    main()
