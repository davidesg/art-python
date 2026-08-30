"""BUG-0029: el `.out` y `get_out_report` son inalcanzables desde el flujo.

El `.out` guarda los parametros CON SUS ERRORES TIPICOS, sigma con el suyo, la
verosimilitud y las matrices de covarianza y correlacion completas -- todo lo que
hace falta para reformular. `get_out_report` existe para leerlo.

Nada en el servidor menciona ninguno de los dos. Todas las sugerencias de "paso
siguiente" encadenan por `.pre`, y la cabecera del modulo presenta `.inp` y
`.pre` como entradas intercambiables:

    "Todas las herramientas trabajan sobre ficheros .inp (modelo + serie) o .pre
     (modelo ya estimado). Sin estado en memoria -- cada llamada es idempotente."

De modo que quien siga el flujo nunca descubre el `.out`, encadena por el `.pre`,
y al reestimar sobre el optimo se lleva la covarianza degenerada de BUG-0027.

El convenio SI esta escrito, pero en el servidor de OTRO escalon
(`drtran-python/src/drtran/mcp_server.py:80-102`, con detalle en
`drtran-python/docs/LADDER_AS_OPTIMISATION.md`) -- no en art, que es donde los
tres ficheros NACEN.

    python3 bugs/BUG-0029-repro/repro.py
"""
import os
import re
import subprocess

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRV = os.path.join(RAIZ, "src", "art", "mcp_server.py")
src = open(SRV, encoding="utf-8").read()

def cuenta(patron, texto=src, flags=re.I):
    return len(re.findall(patron, texto, flags))

print("En %s:\n" % os.path.relpath(SRV, RAIZ))
filas = [
    ("menciones de `get_out_report`",            cuenta(r"get_out_report")),
    ("  ... de ellas, su propia definicion",     cuenta(r"def get_out_report")),
    ("sugerencias que dirigen al `.out`",        cuenta(r"lee el \.out|consulta el \.out|get_out_report\(")),
    ("avisos de no reestimar sobre el `.pre`",   cuenta(r"no reestim|nunca del \.pre|desde el \.inp")),
    ("menciones de que los ee vienen del `.out`",cuenta(r"errores? tipicos?.{0,40}\.out|\.out.{0,40}errores? tipicos?")),
    ("rutas `.pre` en las sugerencias",          cuenta(r'pre_path="|inp_path="[^"]*\.pre"')),
]
for etiqueta, n in filas:
    print("  %-44s %d" % (etiqueta, n))

print("\nLa cabecera del modulo, integra:")
cab = src.split('"""')[1]
for l in cab.splitlines():
    if ".inp" in l or ".pre" in l or "idempotente" in l:
        print("   |", l.strip())

# --- el convenio, y donde vive ----------------------------------------------
DRTRAN = "/home/david/Dropbox/SRC/drtran-python/src/drtran/mcp_server.py"
print("\nEl convenio SI esta escrito. Vive en:")
if os.path.exists(DRTRAN):
    t = open(DRTRAN, encoding="utf-8").read()
    i = t.find("EL CONVENIO DE FICHEROS")
    print("   %s (linea %d)" % (os.path.relpath(DRTRAN, "/home/david/Dropbox/SRC"),
                                t[:i].count("\n") + 1))
    for l in t[i:i + 900].splitlines()[:13]:
        print("   |", l)
else:
    print("   (drtran no encontrado en esta maquina)")

print("\n  ...y NO en art:", "get_out_report" in src and
      cuenta(r"CONVENIO DE FICHEROS") == 0)
