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
    # el pico positivo del escalón (obs serie 36) vive en el residuo 36 - (d + D*s)
    resid_start = m.d + m.D * ts.freq
    peaks = [(abs(z), o) for o, z in diag.extreme]
    peaks.sort(reverse=True)
    z_big, obs_1based = peaks[0]

    at_0 = obs_1based - 1                 # lo que hace el auto-select hoy
    correct_at = at_0 + resid_start       # lo que debería hacer

    def fecha(at: int) -> str:
        return f"{at % 12 + 1:02d}/{2000 + at // 12}"

    roto = False
    print(f"desfase d + D·s = {resid_start}")
    print(f"residuo más extremo: obs(1-based)={obs_1based}  z={z_big:+.2f}")
    print(f"fecha auto-select (bug): {fecha(at_0)}    (índice residuo {at_0})")
    print(f"fecha correcta          : {fecha(correct_at)}    (índice serie {correct_at})")
    if fecha(at_0) != fecha(correct_at):
        print("FALLO: la fecha sale sin el desfase de la diferencia  ← el bug")
        roto = True
    else:
        print("OK: fecha correcta")
    print("BUG PRESENTE" if roto else "ARREGLADO")
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
