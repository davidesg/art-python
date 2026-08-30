#!/usr/bin/env python3
"""BUG-0039 — el MA de retardo ESTACIONAL no tenía contraste de no
invertibilidad, y su ley existe.

ART tenía dos regímenes de valores críticos para el DCD:

    raíz real  (s=1)  1.00 / 1.94 / 4.41   — MA regular, tendencia, Nyquist
    par complejo (s=2) ~1.11 / 2.04 / 4.52 — frecuencias interiores (ma_f)

Falta el tercero. Un MA de retardo estacional `(1 − Θ·Bˢ)` en su frontera pone
**s raíces sobre el círculo a la vez** —las s raíces s-ésimas de la unidad—, y
su ley no es ninguna de las dos.

Consecuencia: un modelo airline `∇∇ₛ y = (1 − θB)(1 − ΘBˢ) a` **no se podía
refutar**. Si Θ̂ se apila en la frontera, la `(1 − ΘBˢ)` cancela a la `(1 − Bˢ)`
que se aplicó y la diferencia estacional sobraba — la estacionalidad era
determinista. Es el diagnóstico central del modelo estacional de Box-Jenkins, y
no estaba.

La ley existe y está en la literatura del propio proyecto: Davis, Chen y
Dunsmuir, "Inference for Seasonal Moving Average Models With a Unit Root",
Tabla 3.2 — cuantiles asintóticos del GLR, que es el MISMO estadístico que
calcula `dcd()`.

Uso:  python repro.py
"""
import os
import tempfile
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.pipeline import _write_inp


def airline(n=120, seed=3, estocastica=True):
    """Trimestral con estacionalidad ESTOCÁSTICA (amplitud que vaga, la ∇ₛ hace
    falta) o DETERMINISTA (amplitud fija, la ∇ₛ sobra)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    amp = np.cumsum(rng.standard_normal(n)) * 0.7 if estocastica else np.full(n, 6.0)
    nivel = 100.0 + np.cumsum(rng.standard_normal(n)) + amp * np.cos(np.pi / 2 * t)
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="AIR")


def ajusta(ts, ruta):
    m = fue.Model(ts, d=1, D=1, boxlam=1.0, ma_s=[[0.4]], ma_s_free=[[True]],
                  mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, mf = fue.load(ruta)
    mf.fit()
    return mf


def main():
    with tempfile.TemporaryDirectory() as td:
        try:
            from art.formal_tests import dcd_s, _dcd_crit_s, _DCD_CRIT_MA
        except ImportError:
            print("BUG-0039 REPRODUCIDO: no existe `dcd_s`. Un modelo airline no")
            print("  tiene contraste de no invertibilidad para su MA estacional,")
            print("  así que su ∇ₛ no se puede refutar.")
            return

        print("valores críticos, los tres regímenes al 5%:")
        print(f"   raíz real   (s=1)   {_DCD_CRIT_MA['5%']:.2f}   ← ley desnuda")
        print(f"   MA estacional s=4   {_dcd_crit_s(4)['5%']:.2f}")
        print(f"   MA estacional s=12  {_dcd_crit_s(12)['5%']:.2f}")
        print("   (Davis, Chen y Dunsmuir, Tabla 3.2 — cuantiles del GLR)")
        print()
        print("Aplicar la ley desnuda a un MA estacional sobre-rechazaría el cero")
        print("unitario: declararía GENUINA una ∇ₛ que sobra.")
        print()

        for etq, estoc in (("estacionalidad ESTOCÁSTICA (la ∇ₛ hace falta)", True),
                           ("estacionalidad DETERMINISTA (la ∇ₛ sobra)", False)):
            ts = airline(estocastica=estoc)
            mf = ajusta(ts, os.path.join(td, f"air{int(estoc)}.inp"))
            res = dcd_s(mf)
            if not res:
                print(f"{etq}: sin MA estacional que contrastar")
                continue
            r = res[0]
            c5 = r._crit["5%"]
            veredicto = ("invertible → la ∇ₛ es GENUINA" if r.lr >= c5
                         else "en la frontera → la ∇ₛ SOBRA")
            con_ley_desnuda = ("invertible" if r.lr >= _DCD_CRIT_MA["5%"]
                               else "en la frontera")
            print(f"{etq}")
            print(f"   Θ̂={r.coef_free:+.4f}  LR={r.lr:.3f}  crít 5%={c5:.2f}  →  {veredicto}")
            if (r.lr >= c5) != (r.lr >= _DCD_CRIT_MA["5%"]):
                print(f"   ⚠ con la ley DESNUDA (1.94) habría dicho: {con_ley_desnuda}"
                      f" — veredicto OPUESTO")
            print()

        print("BUG-0039 ARREGLADO: el MA de retardo estacional tiene su contraste")
        print("  con la ley que le corresponde, y el modelo airline se puede refutar.")


if __name__ == "__main__":
    main()
