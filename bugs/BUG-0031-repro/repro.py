#!/usr/bin/env python3
"""BUG-0031 — el carril autónomo no puede especificar un AR/MA ESTACIONAL.

`suggest_orders` busca sobre (p, q, P, Q) con P_max=Q_max=1 y devuelve specs
que llevan P y Q. `decide_orders` devuelve SÓLO `(p, q)`; `run_full` construye
el `ModelSpec` sin tocar `P` ni `Q`, que quedan en su valor por defecto 0.

Consecuencia: sobre una serie cuya identificación coloca EN PRIMER LUGAR un
modelo con P=1, el carril autónomo estima el mismo modelo SIN el operador
estacional — y los residuos no son ruido blanco.

El motor no tiene la culpa: `_make_model` ya sabe montar un AR estacional con
D=0 (pipeline.py:637-641, "Stationary stochastic seasonality on top of the
deterministic harmonics"). Lo que falta es el cable de la política al spec.

Uso:  python repro.py
"""
import sys, warnings
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.model_detection import suggest_orders
from art.policy import decide_orders, ClaudePolicy
from art.pipeline import run_full
from art.diagnosis import diagnose


def make_series(n=120, phi_s=0.7, seed=0):
    """Serie trimestral I(1) en logs cuyo ∇ln es un AR(1)_4 puro."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(n + 40)
    w = np.zeros(n + 40)
    for t in range(4, n + 40):
        w[t] = phi_s * w[t - 4] + a[t]
    w = w[40:]                       # quema el transitorio
    level = 100.0 * np.exp(np.cumsum(w) / 50.0)
    return fue.TimeSeries(level.tolist(), freq=4, start=(2000, 1), name="SEASAR")


def main(tmp_out):
    ts = make_series()

    # ── 1. La identificación SÍ encuentra el operador estacional ───────────
    specs = suggest_orders(ts, d=1, D=0, lam=0.0, top_n=5)
    top = specs[0]
    print("suggest_orders — ranking:")
    for s in specs:
        print(f"   p={s.p} q={s.q} P={s.P} Q={s.Q}  sim={s.similarity:.4f}")
    print(f"\n[1] identificación: el spec en cabeza lleva P={top.P} Q={top.Q}")

    # ── 2. La política lo tira ─────────────────────────────────────────────
    decided = decide_orders(specs)
    print(f"[2] decide_orders(specs) -> {decided}   (sólo el par regular)")
    try:
        from art.policy import decide_seasonal_orders
        print(f"    decide_seasonal_orders(specs) -> {decide_seasonal_orders(specs)}")
        cableado = True
    except ImportError:
        print("    no existe decide_seasonal_orders: P y Q se pierden aquí")
        cableado = False

    # ── 3. El modelo sale sin operador estacional ─────────────────────────
    # λ, d y D van FIJADOS y correctos, para que el único nodo que decide la
    # heurística sea el de los órdenes: así el defecto queda aislado en él.
    # (Con DefaultPolicy pura esta serie sintética decide además λ=1 y d=2, que
    # es otro asunto y enturbiaría el testigo.)
    pol = ClaudePolicy(lam=0.0, d=1, D=0, decision="A", n_harmonics=0)
    res = run_full(ts, tmp_out, decision_policy=pol)
    m = res.final_model
    n_ar_s = sum(len(b) for b in (m.ar_s or []))
    n_ma_s = sum(len(b) for b in (m.ma_s or []))
    dg = diagnose(m)
    qmin = min(dg.q_pvalues)
    print(f"[3] modelo autónomo: p={res.p} q={res.q} "
          f"| operadores estacionales estimados: AR_s={n_ar_s} MA_s={n_ma_s}")
    print(f"    Q min p = {qmin:.4f}   ruido blanco: {'sí' if qmin > 0.05 else 'NO'}")

    # ── 4. El motor sí sabe hacerlo — sólo falta el cable ─────────────────
    from art.pipeline import ModelSpec, build_and_fit
    spec = ModelSpec(lam=res.lam, d=res.d, D=res.D, p=top.p, q=top.q,
                     P=top.P, Q=top.Q, n_harmonics=res.n_harmonics,
                     interventions=list(res.interventions),
                     estimate_mu=res.estimate_mu, seasonal=False)
    fr = build_and_fit(ts, spec, tmp_out, 3.0)
    qmin_ok = min(fr.diag.q_pvalues)
    print(f"[4] el MISMO motor con P={top.P}: AIC {m.aic:.2f} -> {fr.model.aic:.2f}, "
          f"Q min p {qmin:.4f} -> {qmin_ok:.4f}")
    print(f"    ar_s = {[list(np.round(b, 4)) for b in (fr.model.ar_s or [])]}")

    print()
    if top.P + top.Q > 0 and n_ar_s + n_ma_s == 0:
        print("BUG-0031 REPRODUCIDO: la identificación encuentra el operador")
        print("  estacional, la política lo descarta y el motor nunca lo ve.")
        print(f"  Coste medido: AIC {m.aic:.2f} -> {fr.model.aic:.2f}, "
              f"Q p-min {qmin:.4f} -> {qmin_ok:.4f}")
    elif n_ar_s + n_ma_s > 0:
        print("BUG-0031 ARREGLADO: el carril autónomo monta el operador "
              f"estacional que la identificación pidió (AR_s={n_ar_s}, MA_s={n_ma_s}).")
        print(f"  AIC={m.aic:.2f}  Q p-min={qmin:.4f}")
    else:
        print("(!) esta corrida no colocó ningún P/Q en cabeza: sin testigo.")


if __name__ == "__main__":
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        main(os.path.join(td, "seasar.inp"))
