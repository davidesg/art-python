#!/usr/bin/env python3
"""BUG-0037 — la cascada de `guion_abandon` se lleva el nodo que registra el
rechazo.

`guion_node` encadena a la última entrada del guion. Cuando se prueba una rama,
se descarta y se escribe el nodo que explica POR QUÉ —que es la secuencia
natural—, ese nodo queda colgando del modelo que acaba de fallar. Al marcar el
modelo como callejón, la cascada arrastra al nodo.

Y arrastrarlo es lo contrario de lo que el mapa existe para hacer: lo que una
iteración fallida produce de valor no es el modelo que se tira, es la RAZÓN, y
marcarla como callejón la borra del tronco justo cuando más falta hace.

Uso:  python repro.py
"""
import os
import tempfile
import warnings
warnings.filterwarnings("ignore")

from art import mcp_server as M
from art.guion import (Guion, GuionEntry, GuionStats, load_guion, save_guion)


def main():
    td = tempfile.mkdtemp()
    gp = os.path.join(td, "S_guion.json")

    # tronco: un nodo de especificación
    M.guion_node(gp, nodo="lambda", decidido="0", razon="es un índice de precios")

    # una rama que se prueba: un modelo
    g = load_guion(gp)
    g.entries.append(GuionEntry(
        version=2, name="m20", inp_path="/x/m20.inp", timestamp="t", spec={},
        stats=GuionStats(loglik=-1.0, aic=4.0, bic=5.0, sigma_a=1.0,
                         q_pass=True, jb_pass=True, n_extreme=0),
        equation="", decision="candidato MA(1)", rationale="", problems_found="",
        next_version="", parent=1))
    save_guion(g, gp)

    # y el nodo que la RECHAZA, escrito justo después — la secuencia natural
    M.guion_node(gp, nodo="ordenes", decidido="AR(1)",
                 razon="estimé el MA(1) y lo descarto: pierde AIC, BIC y Q")

    print("antes de abandonar:")
    for e in load_guion(gp).entries:
        print(f"   v{e.version} {e.name:<8} kind={e.kind:<6} parent={e.parent} "
              f"status={e.status}")

    M.guion_abandon(gp, 2, why="rama hermana, descartada por AIC y BIC")

    print("\ndespués de abandonar la v2:")
    entradas = {e.version: e for e in load_guion(gp).entries}
    for e in entradas.values():
        print(f"   v{e.version} {e.name:<8} kind={e.kind:<6} parent={e.parent} "
              f"status={e.status}")

    nodo = entradas[3]
    print()
    if nodo.status == "dead-end":
        print("BUG-0037 REPRODUCIDO: el nodo que explica el rechazo quedó")
        print("  marcado como callejón. La razón desaparece del tronco.")
    elif nodo.parent == 2:
        print("(!) el nodo sobrevive pero sigue colgando del callejón.")
    else:
        print("BUG-0037 ARREGLADO: el nodo conserva su estado "
              f"({nodo.status}) y se recolocó en el tronco (parent={nodo.parent}).")
        print("  El modelo descartado sigue marcado, que es lo correcto; el")
        print("  argumento que lo descartó sobrevive, que es el punto del mapa.")


if __name__ == "__main__":
    main()
