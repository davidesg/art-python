#!/usr/bin/env python3
"""BUG-0048 — el ruido blanco entraba en la papeleta SIN pasar por la puerta.

Cada orden candidato pasa un filtro antes de entrar en la lista:
`_validate_ar(p, ...)` comprueba que la PACF respalda ese p, `_validate_ma(q,
...)` que la ACF respalda ese q. Las dos devuelven True de inmediato cuando el
orden es 0 --no hay «retardo p» que mirar-- y mientras (0,0,0,0) estaba excluido
de la enumeración eso no tenía consecuencia.

BUG-0044 lo admitió, con razón: «no hace falta ARMA» a veces es la respuesta. Lo
que no vio es que quedaba como el ÚNICO candidato que entra sin filtro. Y la
bonificación de parsimonia lo empuja hacia arriba: no paga parámetros y cobra el
bonus de «simple y con buen ajuste».

Resultado sobre ∇ln PGAS, cuya Q(15)=35.90 (p=0.0018) rechaza el ruido blanco de
forma contundente: el ruido blanco salía CUARTO, por delante del AR(2), pese a
que la similitud CRUDA favorece al AR(2). Los invierte el ajuste de parsimonia.

Uso:  python repro.py
"""
import sys, warnings
warnings.filterwarnings("ignore")

import numpy as np
from fue.diagnostics import ljung_box
from art.pipeline import _load_ts_model
from art.model_detection import suggest_orders
from art.identification import boxcox_transform as bct, apply_differences as adiff

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/"


def caso(inp, d, D, lam, etq, espera_rb):
    ts, _ = _load_ts_model(inp)
    w = np.array(adiff(bct(ts.data, lam), ts.freq, d, D))
    lb = ljung_box(w, lags=15, df_correction=0)
    pv = float(lb["pvalue"][-1])
    specs = suggest_orders(ts, d=d, D=D, lam=lam, top_n=8)
    pos = next((i for i, s in enumerate(specs, 1)
                if s.p == s.q == s.P == s.Q == 0), None)

    print(f"\n=== {etq}")
    print(f"    Q(15) = {lb['statistic'][-1]:6.2f}   p = {pv:.4f}   "
          f"→ el ruido blanco {'ES' if pv > 0.05 else 'NO es'} sostenible")
    for i, s in enumerate(specs, 1):
        m = "   ← RUIDO BLANCO" if s.p == s.q == s.P == s.Q == 0 else ""
        print(f"    {i}  ({s.p},{s.q})({s.P},{s.Q})  ajustada={s.similarity:.4f}"
              f"  cruda={s.raw_similarity:.4f}{m}")
    if espera_rb:
        ok = pos is not None
        print(f"    -> esperado: presente. {'OK' if ok else 'FALLO: se ha ido'}")
    else:
        ok = pos is None
        print(f"    -> esperado: ausente. "
              f"{'OK' if ok else f'BUG: sigue, en la posicion {pos}'}")
    return ok


def main():
    # El caso roto: la Q rechaza el ruido blanco y aun asi entraba, y por delante
    # de un AR(2) con MEJOR similitud cruda.
    a = caso(R + "PGAS.inp", 1, 0, 0.0,
             "PGAS  ∇ln  --  Q rechaza: el ruido blanco NO debe estar", False)

    # El caso dorado de BUG-0044, que no se puede romper al arreglar el otro:
    # aqui la Q no rechaza y el ruido blanco es la respuesta correcta.
    ts, m = None, None
    import fue
    from art.pipeline import _load_fitted
    from art.describe import _resid_start as rs
    ts_i, m_i = _load_fitted(R + "guiado/ITCER/ITCER_m10.pre")
    res = np.array(m_i.residuals.data)
    lb = ljung_box(res, lags=15, df_correction=0)
    rts = fue.TimeSeries(m_i.residuals.data, freq=ts_i.freq,
                         start=rs(m_i), name="resid")
    specs = suggest_orders(rts, d=0, D=0, lam=1.0, top_n=5)
    pos = next((i for i, s in enumerate(specs, 1)
                if s.p == s.q == s.P == s.Q == 0), None)
    print(f"\n=== ITCER  residuos de m10  --  el caso dorado de BUG-0044")
    print(f"    Q(15) = {lb['statistic'][-1]:6.2f}   p = {lb['pvalue'][-1]:.4f}"
          f"   → el ruido blanco ES sostenible")
    for i, s in enumerate(specs, 1):
        m_ = "   ← RUIDO BLANCO" if s.p == s.q == s.P == s.Q == 0 else ""
        print(f"    {i}  ({s.p},{s.q})({s.P},{s.Q})  ajustada={s.similarity:.4f}"
              f"  cruda={s.raw_similarity:.4f}{m_}")
    b = pos == 1
    print(f"    -> esperado: primero. "
          f"{'OK' if b else f'FALLO: posicion {pos}'}")

    print("\n" + ("ARREGLADO: el ruido blanco entra por la misma puerta que los "
                  "demas -- su propio contraste" if a and b else "BUG PRESENTE"))
    return 0 if (a and b) else 1


if __name__ == "__main__":
    sys.exit(main())
