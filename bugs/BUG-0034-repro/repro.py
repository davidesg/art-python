#!/usr/bin/env python3
"""BUG-0034 — encadenar ARMA sobre un modelo reformulado por el MEG destruye
el testigo MA_f y deja la forma SOBREDIFERENCIADA, en silencio.

`ifadf[f]=1` impone una raíz unitaria estacional en la frecuencia f. El modelo
que el MEG contrasta —el modelo S de estacionalidad estocástica— es esa raíz
MÁS el testigo MA_f libre (1 − 2λcos(ω)B + λ²B²). Sin el testigo, el mismo
`ifadf` es la forma AR-only, que sobrediferencia la estacional; el docstring de
`meg_reformulate` lo dice: "OVER-DIFFERENCES the seasonal (inflated σ, exploded
Q-test) and is only a diagnostic subproduct, NOT S".

El testigo NO vive en `ma_s`: `fue` guarda los factores anclados a una
frecuencia en bloques propios del `.inp` ("AR(2)/MA(2) operators with fixed
frequency"), que en el modelo son `m.ar_f` y `m.ma_f`. Y
`_build_arma_on_model` heredaba `interventions`, `ifadf` y `mu` sin mencionar
`ar_f` ni `ma_f` en ninguna parte: los perdía en TODO encadenamiento. Añadir un
MA regular a un modelo reformulado conservaba la raíz unitaria y perdía su
testigo.

Uso:  python repro.py
"""
import os
import tempfile
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.pipeline import _build_arma_on_model, _write_inp, _load_fitted
from art.diagnosis import diagnose


def serie_estacional_estocastica(n=120, seed=4):
    """Trimestral cuyo patrón estacional VAGA — amplitud que cambia año a año.
    Es el caso que el MEG declara estocástico."""
    rng = np.random.default_rng(seed)
    # amplitud del armónico f=1 como paseo aleatorio: estacionalidad estocástica
    a = np.cumsum(rng.standard_normal(n)) * 0.6
    b = np.cumsum(rng.standard_normal(n)) * 0.6
    t = np.arange(n)
    estacional = a * np.cos(np.pi / 2 * t) + b * np.sin(np.pi / 2 * t)
    nivel = 100.0 + np.cumsum(rng.standard_normal(n)) + estacional
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="SEASTOC")


def construye_S(ts, ruta):
    """El modelo S: ifadf[1]=1 (raíz unitaria estacional) + testigo MA_f libre.

    El testigo va en `ma_f`, el bloque de frecuencia fija — que es exactamente
    el que se perdía."""
    m = fue.Model(ts, d=1, boxlam=1.0, ifadf=[0, 1, 0],
                  ma_f=[fue.FixedFreqFactor(freq=1.0, coef=-0.5, free=True)],
                  mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, m_fit = _load_fitted(ruta)
    return m_fit


def describe(etq, m):
    r = np.asarray(m.residuals.data, float)
    dg = diagnose(m)
    n_ma_f = len(m.ma_f or [])
    print(f"  {etq}")
    print(f"     ifadf={list(m.ifadf or [])}  testigos MA_f={n_ma_f}"
          + (f"  coef={m.ma_f[0].coef:+.4f}" if n_ma_f else ""))
    print(f"     sd(a)={r.std(ddof=1):.4f}  logL={m.loglik:.2f}  AIC={m.aic:.2f}"
          f"  Q p-mín={min(dg.q_pvalues):.4f}")
    return n_ma_f, r.std(ddof=1), m.aic


def main():
    ts = serie_estacional_estocastica()
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, "S.inp")
        m_S = construye_S(ts, base)
        print("modelo S de partida (raíz unitaria estacional + testigo):")
        n0, sd0, aic0 = describe("S", m_S)

        print("\nañadir un MA(1) REGULAR encadenando (q=1, sin tocar Q):")
        m_new = _build_arma_on_model(m_S, p=0, q=1)
        ruta = os.path.join(td, "S_ma1.inp")
        _write_inp(ts, m_new, ruta)
        _, m_fit = _load_fitted(ruta)
        n1, sd1, aic1 = describe("S + MA(1)", m_fit)

        print()
        if n0 > 0 and n1 == 0:
            print("BUG-0034 REPRODUCIDO: el testigo estaba y desapareció al")
            print(f"  encadenar. sd(a) {sd0:.4f} -> {sd1:.4f}, AIC {aic0:.2f} -> {aic1:.2f}.")
            print("  El ifadf sigue activo: es la forma sobrediferenciada, y nada avisó.")
        elif n0 > 0 and n1 > 0:
            print("BUG-0034 ARREGLADO: el testigo sobrevive al encadenar")
            print(f"  ({n1} factor(es) MA_f), junto al ifadf al que pertenece.")
            print(f"  sd(a) {sd0:.4f} -> {sd1:.4f}, AIC {aic0:.2f} -> {aic1:.2f}.")
        else:
            print("(!) el modelo S de partida no llegó a tener testigo: sin testigo.")


if __name__ == "__main__":
    main()
