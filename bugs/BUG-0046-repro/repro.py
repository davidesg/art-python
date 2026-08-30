#!/usr/bin/env python3
"""BUG-0046 — el OBJETIVO del modelo no era declarable en el lote.

`run_full` acepta `objetivo` y lo usa para adjudicar la ruta estacional: en
`multivariante` VETA la ruta B2 (D=1) para que todas las series lleven el mismo
tratamiento y sus órdenes de integración sean comparables.

`build_model` lo expone. **`batch_build` NO**: su firma era

    batch_build(inp_paths, output_dir, max_rounds=5, run_meg=False)

y llamaba `run_full(ts, out_inp, max_rounds=max_rounds)` — siempre con el
defecto. Justo la entrada del lote, que es como se preparan las series de un
sistema, era la única que no podía declarar que van a un sistema.

Consecuencia observable: se lotean dos series estacionales, una con
estacionalidad estocástica y otra con estacionalidad determinista. Cada una gana
por su propio ajuste, salen con D distinta, y el lote NO se puede montar en un
VECM. Antes del arreglo no había forma de pedir lo contrario ni aviso de que
hubiera pasado.

Uso:  python repro.py
"""
import sys, os, tempfile, warnings, inspect
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.pipeline import run_full


def serie_estocastica(n=120, seed=1):
    """Trimestral con RAÍZ UNITARIA ESTACIONAL: el patrón evoluciona.

    ln y = paseo aleatorio + paseo aleatorio ESTACIONAL (∇_4 s = e). El segundo
    sumando es lo que exige D=1: una estacionalidad que no se queda quieta.
    """
    rng = np.random.default_rng(seed)
    tend = np.cumsum(rng.standard_normal(n)) / 60.0
    s = np.zeros(n + 4)
    e = rng.standard_normal(n + 4) / 40.0
    for t in range(4, n + 4):
        s[t] = s[t - 4] + e[t]
    return fue.TimeSeries((100.0 * np.exp(tend + s[4:])).tolist(),
                          freq=4, start=(2000, 1), name="ESTOC")


def serie_determinista(n=120, amp=0.06, seed=2):
    """Trimestral con estacionalidad FIJA: un armónico + paseo aleatorio."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    estacional = amp * np.cos(2 * np.pi * t / 4.0)
    tend = np.cumsum(rng.standard_normal(n)) / 60.0
    return fue.TimeSeries((100.0 * np.exp(tend + estacional)).tolist(),
                          freq=4, start=(2000, 1), name="DETER")


def main():
    import art.mcp_server as M

    # ── 1. La firma: ¿es declarable el objetivo en cada entrada? ───────────
    print("¿'objetivo' alcanzable desde cada entrada del carril autónomo?")
    faltan = []
    for nombre in ("build_model", "batch_build"):
        f = getattr(M, nombre)
        f = getattr(f, "fn", f)                 # desenvuelve el @mcp.tool()
        ok = "objetivo" in inspect.signature(f).parameters
        print(f"  {nombre:16s} {'sí' if ok else 'NO  ← el agujero'}")
        if not ok:
            faltan.append(nombre)

    # ── 2. El daño: dos series, un lote, D distintas ──────────────────────
    tmp = tempfile.mkdtemp(prefix="bug0046_")
    print("\nMismo par de series, dos objetivos:\n")
    print("  serie   univariante   multivariante")
    print("  " + "-" * 36)
    Ds = {}
    for obj in ("univariante", "multivariante"):
        Ds[obj] = []
        for ts in (serie_estocastica(), serie_determinista()):
            out = os.path.join(tmp, f"{ts.name}_{obj}.inp")
            r = run_full(ts, out, max_rounds=1, objetivo=obj)
            Ds[obj].append((ts.name, r.D))
    for i, (nombre, _) in enumerate(Ds["univariante"]):
        print(f"  {nombre:7s}   D={Ds['univariante'][i][1]:<11d} "
              f"D={Ds['multivariante'][i][1]}")

    d_uni = {d for _, d in Ds["univariante"]}
    d_mul = {d for _, d in Ds["multivariante"]}
    print(f"\n  univariante   → D en {sorted(d_uni)}"
          f"{'  ← NO comparables' if len(d_uni) > 1 else ''}")
    print(f"  multivariante → D en {sorted(d_mul)}"
          f"{'  ← un solo tratamiento' if len(d_mul) == 1 else ''}")

    roto = bool(faltan) or (len(d_uni) > 1 and len(d_mul) > 1)
    print("\n" + ("BUG PRESENTE" if roto else "ARREGLADO: el objetivo llega al "
                                              "lote y unifica el tratamiento"))
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
