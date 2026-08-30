#!/usr/bin/env python3
"""BUG-0058 — la cascada de `abandon` pisaba razones y barria ramas ajenas.

Dos fallos en `guion.abandon`, los dos observados en el RUN 3 sobre RATIO.

(a) LAS RAZONES SE PISABAN. `e.why_abandoned = why.strip()` se ejecutaba para
    TODA version alcanzada, ya estuviera marcada o no. Abandonar una version
    sobrescribia la razon de cualquier callejon anterior que la cascada volviera
    a tocar. Se observo con cuatro versiones llevando literalmente el mismo
    texto. Es el fallo que mas duele: la propia docstring dice que sin la razon
    no se evita volver a entrar, que es lo unico para lo que sirve marcarlo.

(b) SE BARRIAN RAMAS QUE YA NO DESCENDIAN DEL CALLEJON. Un NODO de decision
    alcanzado por la cascada se RECOLOCA al tronco (BUG-0037) en lugar de
    abandonarse. Pero sus descendientes ya estaban recogidos en `alcanzadas` y
    se abandonaban igual, aunque tras la recolocacion cuelguen de una version
    viva.

Uso:  python repro.py
"""
import sys

from art.guion import Guion, GuionEntry, abandon


def arbol():
    """v1 tronco → v2 modelo → v3 NODO (conclusion) → v4 modelo bueno.

    Y v5, un callejon aparte que ya tiene SU razon escrita, colgando de v2.
    """
    g = Guion(series="X", analyst="", created="2026-08-29")
    def e(v, parent, kind, **kw):
        return GuionEntry(version=v, name=f"v{v}", inp_path="", timestamp="",
                          spec={}, stats=None, equation="", decision="",
                          rationale="", problems_found="", next_version="",
                          parent=parent, kind=kind, **kw)
    g.entries = [
        e(1, None, "model"),
        e(2, 1, "model"),
        e(5, 2, "model", status="dead-end",
          why_abandoned="RAZON PROPIA DE v5: el MA(2) no se sostiene, t=1.2"),
        e(3, 2, "node"),          # la conclusion que se saca de v2
        e(4, 3, "model"),         # el modelo bueno, colgado del NODO
    ]
    return g


def main():
    g = arbol()
    ab, rec = abandon(g, 2, "v2 no blanquea: Q p=0.001")
    por_v = {x.version: x for x in g.entries}

    print("Se abandona v2. El arbol era  v1 → v2 → {v5 (ya callejon), v3 NODO → v4}\n")
    print(f"  abandonadas: {ab}     recolocadas: {rec}\n")
    for v in sorted(por_v):
        x = por_v[v]
        print(f"  v{v} [{x.kind:5s}] parent={str(x.parent):4s} status={str(x.status):9s}")
        if x.why_abandoned:
            for l in x.why_abandoned.splitlines():
                print(f"        {l}")

    fallos = []
    if "RAZON PROPIA DE v5" not in (por_v[5].why_abandoned or ""):
        fallos.append("(a) se piso la razon propia de v5")
    if por_v[4].status == "dead-end":
        fallos.append("(b) v4 se abandono, aunque su padre v3 se recoloco al tronco")
    if por_v[3].parent != 1:
        fallos.append("(b) v3 no se recoloco al ancestro vivo")

    print("\n" + ("BUG PRESENTE:\n   " + "\n   ".join(fallos) if fallos else
                  "ARREGLADO: v5 conserva su razon, y v4 sobrevive con v3 recolocado a v1"))
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
