#!/usr/bin/env python3
"""BUG-0038 — el veredicto "considerar d+1" se publica sin sus salvedades
cuando el modelo no tiene AR regular.

`dcd_overdiff_regular` contrasta el orden de integración en f=0 y su veredicto
viene con dos advertencias que el paper exige y que ART tenía escritas:

  1. el crítico impreso (1.94) es el de la ley DESNUDA s=1; con deterministas
     RESONANTES con f=0 —una constante, un escalón— el pile-up sube de 0.6575 a
     0.927 y el crítico correcto es MAYOR;
  2. si θ̂ no se apila en la frontera, el LR se evalúa donde el perfil de
     verosimilitud de fue da un salto errático.

Las dos vivían DENTRO del bloque del par confirmatorio, y ese bloque sólo se
imprime cuando Shin-Fuller es aplicable — es decir, cuando el modelo tiene AR
regular libre.

Consecuencia: **un modelo sin AR regular recibe "considerar d+1 ✗" a pelo**, con
un crítico que se sabe subestimado y sin nada que lo diga. Ninguna de las dos
advertencias habla del par: las dos hablan del veredicto del DCD.

Testigo real: RATIO de la réplica del TFM. Modelo con dos raíces unitarias
estacionales, un escalón, y AR sólo estacional. LR=2.576 contra 1.94 impreso, sin
aviso → se lee como "falta una diferencia" y se toma d=2, que era incorrecto.

Uso:  python repro.py
"""
import os
import tempfile
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.describe import describe_formal_tests
from art.formal_tests import shin_fuller
from art.pipeline import _write_inp, _load_fitted


def serie(n=110, seed=5):
    """I(1) con un ESCALÓN — el determinista resonante con f=0."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    nivel = 100.0 + np.cumsum(w)
    nivel[55:] += 9.0                      # escalón permanente
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="ESCALON")


def main():
    ts = serie()
    with tempfile.TemporaryDirectory() as td:
        ruta = os.path.join(td, "escalon.inp")
        # SIN AR regular: sólo un MA regular y el escalón. Shin-Fuller no aplica.
        m = fue.Model(ts, d=1, boxlam=1.0,
                      ma=[[0.0]], ma_free=[[True]],
                      interventions=[fue.Intervention("step", at=55, omega=[0.0],
                                                      omega_free=[True])],
                      mu=0.0, estimate_mu=False)
        _write_inp(ts, m, ruta)
        _, mf = _load_fitted(ruta)

        try:
            shin_fuller(mf)
            hay_sf = True
        except Exception:
            hay_sf = False
        print(f"AR regular libre: {bool(mf.ar)}   Shin-Fuller aplicable: {hay_sf}")
        print(f"deterministas: {[(i.type, i.at) for i in (mf.interventions or [])]}")

        txt = describe_formal_tests(mf).summary
        bloque = [l for l in txt.splitlines()
                  if "sobre-diferenciación" in l or l.strip().startswith("- θ̂")
                  or l.strip().startswith("ℹ") or l.strip().startswith("⚠")]
        print("\nlo que ART publica sobre el orden de integración:")
        for l in bloque:
            print("   " + l.strip())

        tiene_aviso_critico = "DESNUDA" in txt
        tiene_aviso_par = "Sin par confirmatorio" in txt

        print()
        if not hay_sf and not tiene_aviso_critico:
            print("BUG-0038 REPRODUCIDO: veredicto sobre d sin la advertencia de")
            print("  que el crítico impreso está subestimado para este modelo.")
        elif not hay_sf and tiene_aviso_critico:
            print("BUG-0038 ARREGLADO: las advertencias acompañan al veredicto")
            print(f"  aunque no haya par confirmatorio (aviso del par: {tiene_aviso_par}).")
        else:
            print("(!) este testigo tiene Shin-Fuller aplicable: no aísla el defecto.")


if __name__ == "__main__":
    main()
