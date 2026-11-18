"""BUG-0108 — estimate_and_diagnose registraba como padre la versión anterior, y
guion_abandon en cascada se creía ese padre inventado.

Caso real (cases/UEM_HCPI_0226): v12 se construyó a mano desde v10, pero quedó
registrada como hija de v11; marcar v11 como callejón —correcto— se llevaba en
cascada v12, v14 y v15, la rama viva.

Cómo se cerró (07-09-2026), en dos mitades:
1. `estimate_and_diagnose` acepta `base_pre_path`, como `confirm_and_estimate`:
   el linaje se puede DECLARAR.
2. Cada entrada guarda CÓMO se supo su padre (`parent_origen`: «declarado» o
   «inferido»), y `guion_abandon` avisa, antes de tocar nada, cuando la cascada
   se apoya en un parentesco inferido.

El cierre dice también lo que NO hace: no arregla los guiones ya escritos (sus
entradas no llevan `parent_origen`), así que el caso real de arriba seguirá
como estaba. Antes este repro miraba ese guion viejo y salía 1 con el bug
cerrado; ahora comprueba las dos mitades del arreglo.
Exit 1 = bug presente; exit 0 = corregido.
"""
import inspect
import os
import sys
import tempfile
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))
warnings.filterwarnings("ignore")

from art import mcp_server as M
from art.guion import Guion, GuionEntry, GuionStats, save_guion

FALLOS = []

ead = getattr(M.estimate_and_diagnose, "fn", M.estimate_and_diagnose)
declara = "base_pre_path" in inspect.signature(ead).parameters
print(f"== 1. estimate_and_diagnose acepta base_pre_path : {declara}")
if not declara:
    FALLOS.append("estimate_and_diagnose no deja declarar el linaje")


def guion(origen_v3):
    def E(v, n, padre, origen):
        return GuionEntry(
            version=v, name=n, inp_path="", timestamp="t", spec={},
            stats=GuionStats(loglik=-1.0, aic=1.0, bic=2.0, sigma_a=0.1,
                             q_pass=True, jb_pass=True, n_extreme=0),
            equation="", decision="", rationale="", problems_found="",
            next_version="", parent=padre, parent_origen=origen)
    g = Guion(series="S", analyst="", created="2026-01-01")
    g.entries += [E(1, "m00", None, "declarado"), E(2, "m01", 1, "declarado"),
                  E(3, "m02", 2, origen_v3), E(4, "m03", 3, "declarado")]
    fd, p = tempfile.mkstemp(suffix="_guion.json")
    os.close(fd)
    save_guion(g, p)
    return p


ga = getattr(M.guion_abandon, "fn", M.guion_abandon)
t_inf = ga(guion("inferido"), 2, why="LR rechaza")[0].text
t_dec = ga(guion("declarado"), 2, why="LR rechaza")[0].text
avisa = "parentesco INFERIDO" in t_inf and "v3 (m02)" in t_inf and "cascade=False" in t_inf
calla = "parentesco INFERIDO" not in t_dec
print(f"== 2. la cascada avisa sobre un padre inferido      : {avisa}")
print(f"      y calla cuando todo el linaje es declarado      : {calla}")
if not avisa:
    FALLOS.append("guion_abandon cascadea sobre un padre inferido sin avisar")
if not calla:
    FALLOS.append("guion_abandon avisa también sobre un linaje declarado")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA (bug presente):", "; ".join(FALLOS))
    sys.exit(1)
print("OK: el linaje se puede declarar, y la cascada avisa cuando se apoya en uno inferido.")
