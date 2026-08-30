#!/usr/bin/env python3
"""BUG-0036 — dos veredictos de adecuación con el mismo nombre y sin regla.

`confirm_and_estimate` dicta su veredicto con `DiagnosisResult.residuals_ok`
(ruido blanco + normalidad + sin estacionalidad residual). La guarda de
`formal_tests` tenía su PROPIA lista de fallos. El mismo modelo salía
"APROBADO ✓" de la primera y "todavía NO es adecuado" de la segunda.

Y no era que una fuese un caso particular de la otra: divergían en las DOS
direcciones.

  * la guarda contaba los residuos EXTREMOS; `residuals_ok` no, y a propósito —
    los extremos gobiernan el bucle de intervenciones, no la adecuación;
  * `residuals_ok` cuenta la ESTACIONALIDAD RESIDUAL; la guarda no la miraba.

A un analista humano le irrita; a un LLM decidiendo solo le deja sin criterio.
Y empujaba a lo peor: añadir un parámetro no significativo sólo para hacer
desaparecer un extremo y cerrar la guarda.

Uso:  python repro.py
"""
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.diagnosis import diagnose
from art.describe import describe_formal_tests
from art.pipeline import _write_inp, _load_fitted
import tempfile, os


def serie_con_un_extremo(n=100, seed=0):
    """Paseo aleatorio con UN salto aislado, calibrado para el caso interesante:
    Q pasa, JB pasa, y queda un residuo por encima de |z|=3.

    Ese es el punto donde los dos veredictos se separaban. Un salto MÁS grande
    rompe también la JB y entonces los dos coinciden en rechazar — por eso el
    testigo hay que calibrarlo, no exagerarlo."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    w[60] += 3.6
    nivel = 100.0 + np.cumsum(w)
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="UNEXT")


def main():
    ts = serie_con_un_extremo()
    with tempfile.TemporaryDirectory() as td:
        ruta = os.path.join(td, "unext.inp")
        m = fue.Model(ts, d=1, boxlam=1.0, ma=[[0.0]], ma_free=[[True]],
                      mu=0.0, estimate_mu=False)
        _write_inp(ts, m, ruta)
        _, mf = _load_fitted(ruta)

        dg = diagnose(mf)
        print("lo que dice la DIAGNOSIS:")
        print(f"   ruido blanco (Q): {'sí' if dg.white_noise else 'NO'}"
              f"  p-mín={min(dg.q_pvalues):.4f}")
        print(f"   normalidad (JB):  {'sí' if dg.normal else 'NO'}"
              f"  JB={dg.jb_stat:.3f} p={dg.jb_pvalue:.4f}")
        print(f"   extremos |z|>3:   {len(dg.extreme)}")
        print(f"   -> residuals_ok = {dg.residuals_ok}   (el veredicto que se publica)")

        txt = describe_formal_tests(mf).summary
        bloquea = "todavía NO es adecuado" in txt
        avisa = "salvedad" in txt
        print("\nlo que dice FORMAL_TESTS sobre el MISMO modelo:")
        print(f"   ¿bloquea con 'todavía NO es adecuado'? {bloquea}")
        print(f"   ¿lo nombra como salvedad sin bloquear?  {avisa}")

        print()
        if dg.residuals_ok and bloquea:
            print("BUG-0036 REPRODUCIDO: la diagnosis aprueba y los contrastes")
            print("  formales dicen que el modelo no es adecuado. Dos predicados")
            print("  con el mismo nombre y ninguna regla que diga cuál manda.")
        elif dg.residuals_ok and avisa:
            print("BUG-0036 ARREGLADO: un solo predicado. El extremo se nombra")
            print("  como salvedad —está ahí y conviene saberlo— pero no bloquea,")
            print("  porque las nulas de esta etapa suponen ruido blanco y lo es.")
        elif not dg.residuals_ok and bloquea:
            print("(coherentes: la diagnosis falla y la guarda bloquea)")
        else:
            print("(!) esta corrida no produjo el testigo: sin extremo aislado.")


if __name__ == "__main__":
    main()
