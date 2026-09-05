"""BUG-0101 — el guion no tiene forma de saberse incompleto.

Sintético y determinista: tres modelos estimados en la carpeta, dos en el guion.

    python bugs/BUG-0101-repro/repro.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from art.guion import (Guion, GuionEntry, iteraciones, load_guion,  # noqa: E402
                       modelos_sin_registrar, save_guion)


def entrada(v, nombre, inp):
    return GuionEntry(version=v, name=nombre, inp_path=inp, timestamp="t",
                      spec={}, stats=None, equation="", decision="",
                      rationale="", problems_found="", next_version="")


d = tempfile.mkdtemp()
# Tres modelos ESTIMADOS: los tres tienen .inp y .out.
for n in ("m00", "m01", "m02_fact"):
    open(f"{d}/S_{n}.inp", "w").write("x")
    open(f"{d}/S_{n}.out", "w").write("x")
# Un borrador sin estimar: NO es una iteración.
open(f"{d}/S_borrador.inp", "w").write("x")

g = Guion(series="S", analyst="", created="2026-01-01")
g.entries += [entrada(1, "m00", f"{d}/S_m00.inp"),
              entrada(2, "m01", f"{d}/S_m01.inp")]
gp = f"{d}/S_guion.json"
save_guion(g, gp)

g = load_guion(gp)
print(f"iteraciones registradas: {len([i for i in iteraciones(g) if i.cerrada])}")
sueltos = [os.path.basename(x) for x in modelos_sin_registrar(g, gp)]
print(f"estimados fuera del registro: {sueltos}")

if sueltos != ["S_m02_fact.inp"]:
    print("FALLO: el registro no se sabe incompleto")
    sys.exit(1)
print("OK: el registro dice lo que le falta, y no confunde un borrador con una "
      "iteración")
