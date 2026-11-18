#!/usr/bin/env python3
"""BUG-0067 — el auto-select de suggest_intervention_form mapea la fecha del
residuo SIN el desfase de la diferencia (d + D·s).

Caso real: ES_CORE D=1 (∇∇₁₂, desfase 13). El residuo más extremo (obs 57 del
escaneo) se mapeó a 09/2006; la fecha correcta era 10/2007. El step cayó mal
(ω=+0.049, insignificante) y no capturó el anómalo.

Uso:  python repro.py     (sale 1 con el bug, 0 arreglado)
"""
import sys


def main() -> int:
    import numpy as np
    import fue
    from art.diagnosis import diagnose

    rng = np.random.default_rng(0)
    n = 60
    x = [0.05 * float(rng.standard_normal()) for _ in range(n)]
    for i in range(36, n):
        x[i] += 2.0                        # escalón permanente en obs 36 = 2003-01

    ts = fue.TimeSeries(x, freq=12, start=(2000, 1), name="SINT")
    m = fue.Model(ts, d=1, D=1, interventions=[])
    m.fit()

    diag = diagnose(m, z_threshold=2.0)
    peaks = sorted(((abs(z), o) for o, z in diag.extreme), reverse=True)
    z_big, obs = peaks[0]
    # Desde el arreglo, `diagnose` da los extremos en coordenadas de la SERIE
    # (y su fecha en `extreme_dates`). Antes este repro tomaba `obs` como índice
    # de residuo, le sumaba a mano el desfase y comparaba con su propia fórmula
    # —nunca llamaba a art—, así que salía 1 siempre que d + D·s > 0.
    desfase = m.d + m.D * ts.freq

    def fecha(at0):                                     # 0-based en la SERIE
        return f"{at0 % 12 + 1:02d}/{2000 + at0 // 12}"

    # El invariante de BUG-0067: la fecha de un extremo es la de su
    # observación en la SERIE, es decir el índice de residuo MÁS d + D·s. (El
    # mayor |z| no tiene por qué caer en el escalón: con d = D = 1 la doble
    # diferencia de un escalón deja dos picos, en él y doce meses después.)
    print(f"desfase d + D·s = {desfase}")
    malas = []
    for o, z in diag.extreme:
        esperada = fecha(o - 1 + desfase)
        dada = diag.extreme_dates.get(int(o), "")
        print(f"  residuo {o:3d}  z={z:+.2f}  art dice {dada:8s}  serie {esperada}")
        if dada != esperada:
            malas.append(o)
    roto = bool(malas) or not diag.extreme
    print("FALLO: la fecha no aplica el desfase de la diferencia  ← el bug" if roto
          else "OK: todas las fechas aplican el desfase")
    print("BUG PRESENTE" if roto else "ARREGLADO")
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
