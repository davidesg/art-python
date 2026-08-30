#!/usr/bin/env python3
"""BUG-0032 — el carril autónomo registra el DESTINO, no el CAMINO.

`build_model` corre un bucle de rondas: estima, diagnostica, y decide DESDE esa
diagnosis qué intervención añadir antes de volver a estimar. Cada ronda deja un
modelo y una diagnosis en `result.rounds`. Al terminar, escribía **una sola**
entrada en el guion — la del modelo final.

Consecuencia: `guion_map` dibujaba un mapa de UN nodo para una búsqueda de tres
pasos, y la pregunta que el guion existe para contestar —por dónde se fue, y por
qué— no tenía dónde leerse.

Testigo real: RATIO de la réplica del TFM. Tres rondas, dos intervenciones
añadidas, y un guion con una entrada.

Uso:  python repro.py
"""
import sys, warnings, json, os, tempfile
warnings.filterwarnings("ignore")

import numpy as np
import fue
from art.pipeline import run_full
from art.policy import ClaudePolicy


def serie_con_dos_anomalos(n=100, seed=3):
    """Trimestral I(1) con DOS impulsos grandes y separados, que obligan al
    bucle a dar más de una vuelta."""
    rng = np.random.default_rng(seed)
    w = rng.standard_normal(n)
    w[30] += 9.0        # primer anómalo
    w[70] -= 8.0        # segundo, lo bastante lejos para que sea otra ronda
    level = 100.0 + np.cumsum(w)
    return fue.TimeSeries(level.tolist(), freq=4, start=(2000, 1), name="DOSANOM")


def main():
    ts = serie_con_dos_anomalos()
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "dosanom.inp")
        res = run_full(ts, out, decision_policy=ClaudePolicy(lam=1.0, d=1, D=0,
                                                            decision="A",
                                                            n_harmonics=0))
        print(f"rondas que dio el bucle: {len(res.rounds)}")
        for rd in res.rounds:
            n_ext = len(rd.diag.extreme) if rd.diag else 0
            add = ", ".join(f"{f.upper()} obs {at+1}" for at, f in (rd.added or []))
            print(f"  ronda {rd.round_num}: extremos={n_ext}  "
                  f"añade=[{add or '—'}]  motivo_parada={rd.stop_reason or '—'}")

        # Lo que build_model escribía en el guion: UNA entrada, la última.
        print(f"\nmodelos que el bucle estimó y diagnosticó: {len(res.rounds)}")
        print("entradas que el guion recibía (antes del arreglo): 1")
        print(f"entradas que el guion debe recibir:               {len(res.rounds)}")

        if len(res.rounds) > 1:
            print("\nBUG-0032 REPRODUCIDO: la búsqueda tiene "
                  f"{len(res.rounds)} pasos y el mapa tenía 1 nodo.")
            print("  Lo que se perdía no es el modelo intermedio —que se")
            print("  descarta— sino la RAZÓN de pasar al siguiente, que es lo")
            print("  único que impide volver a probar la misma rama.")
        else:
            print("\n(!) esta corrida sólo dio una ronda: sin testigo.")


if __name__ == "__main__":
    main()
