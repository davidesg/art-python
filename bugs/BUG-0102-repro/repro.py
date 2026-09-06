"""BUG-0102 — el registro puede contradecir a su fichero, y nada lo dice.

Dos mitades, sintéticas y sin motor:

  (A) una entrada declara N intervenciones y su `.inp` lleva otras: el detector
      tiene que verlo;
  (B) una cifra que NO CONSTA —de un guion escrito por una versión anterior—
      no puede reventar al presentarla.

    python bugs/BUG-0102-repro/repro.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from art.guion import (Guion, GuionEntry, GuionStats, cifra,  # noqa: E402
                       entradas_que_no_cuadran, load_guion, save_guion)

INP = """** Frequency of time series: either 1(A), 4(Q) or 12(M):
 12
** Number of observations and starting date of time series:
 120  1 2005 S
** Number of deterministic variables (including seasonal components):
{n}
**
{nombres}
**
"""


def escribe_inp(ruta, deterministas):
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write(INP.format(n=len(deterministas),
                            nombres="\n".join(deterministas)))


fallos = 0
with tempfile.TemporaryDirectory() as d:
    # (A) el fichero lleva CUATRO, el registro declara UNA
    escribe_inp(f"{d}/S_m01.inp", ["cos 1", "sin 1", "alter",
                                   "step 35", "step 181", "step 222",
                                   "step 243"])
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries.append(GuionEntry(
        version=1, name="m01", inp_path=f"{d}/S_m01.inp", timestamp="t",
        spec={"interventions": [{"type": "step", "date": "07/2020"}]},
        stats=None, equation="", decision="", rationale="",
        problems_found="", next_version=""))
    gp = f"{d}/S_guion.json"
    save_guion(g, gp)
    r = entradas_que_no_cuadran(load_guion(gp))
    if r == [(1, "m01", 4, 1)]:
        print("A) OK  el descuadre se ve:", r[0])
    else:
        print("A) FALLO  no lo detecta:", r); fallos += 1

    # y una entrada que SÍ cuadra no puede dar falso positivo
    g.entries[0].spec = {"interventions": [{"type": "step"}] * 4}
    save_guion(g, gp)
    if entradas_que_no_cuadran(load_guion(gp)) == []:
        print("A) OK  sin falso positivo cuando cuadra")
    else:
        print("A) FALLO  falso positivo"); fallos += 1

# (B) una cifra que no consta
if cifra(None) == "—" and cifra(-869.34) == "-869.34" and \
        cifra(0.0123, ".5f") == "0.01230":
    print("B) OK  lo que no consta se presenta como «—», no revienta")
else:
    print("B) FALLO", cifra(None), cifra(-869.34)); fallos += 1

st = GuionStats()                      # todo por defecto: un registro antiguo
if st.loglik is None and cifra(st.loglik) == "—":
    print("B) OK  un guion anterior se presenta sin inventar ceros")
else:
    print("B) FALLO"); fallos += 1

sys.exit(1 if fallos else 0)
