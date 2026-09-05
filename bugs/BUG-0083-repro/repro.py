"""BUG-0083 — la marcha del incidente sólo va HACIA ATRAS.

`arranques_candidatos` anda hacia atras desde el PRIMER extremo mientras los
vecinos sigan activos, pero el final queda clavado en el ULTIMO extremo POR
ENCIMA DEL UMBRAL. Si la cola del suceso se queda por debajo del umbral, la
configuracion larga NUNCA se construye — y el informe dice luego «el dato SI
identifica la configuracion» porque solo habia una candidata.

Los dos casos son el mismo mecanismo con el extremo en un sitio distinto:
  * cola enmascarada DELANTE  -> lo pilla (es el caso que motivo el disenio)
  * cola enmascarada DETRAS   -> no lo pilla

Determinista y sintetico.
"""
import sys
sys.path.insert(0, "src")
from art.configuracion import arranques_candidatos

UMBRAL_EXTREMO = 2.5     # el que decide que es "extremo"
ACTIVO         = 1.5     # el que decide que vecino sigue "activo"

def extremos(z):
    return [i for i, v in enumerate(z) if abs(v) >= UMBRAL_EXTREMO]

# Caso 1 — ARRANQUE enmascarado ANTES del extremo   (FOOD_UEM 02-03/2017)
z1 = [0.2, -0.4, 0.3, 2.40, -3.80, -0.1, 0.3, -0.2]
#                        ^activo  ^extremo
# Caso 2 — COLA enmascarada DESPUES del extremo     (FOOD_UEM 12/2004-01/2005)
z2 = [0.2, -0.4, 0.3, -0.1, 3.56, -2.20, 0.3, -0.2]
#                            ^extremo ^activo

for nombre, z, esperado in [
        ("cola DELANTE  (02-03/2017)", z1, 2),
        ("cola DETRAS   (12/2004-01/2005)", z2, 2)]:
    ext = extremos(z)
    cands = arranques_candidatos(z, ext, d=1, umbral_activo=ACTIVO)
    longs = [n for _, n in cands]
    ok = esperado in longs
    print(f"{nombre}")
    print(f"   z          = {z}")
    print(f"   extremos   = {ext}   (|z| >= {UMBRAL_EXTREMO})")
    print(f"   candidatas = {cands}   longitudes {longs}")
    print(f"   la de longitud {esperado} se enumera: {'SI' if ok else 'NO  <-- FALLA'}\n")

ext2 = extremos(z2)
c2 = arranques_candidatos(z2, ext2, d=1, umbral_activo=ACTIVO)
if 2 not in [n for _, n in c2]:
    print("La configuracion de 2 escalones no se construye cuando la cola queda")
    print("por debajo del umbral. Con una sola candidata, el informe concluye")
    print("«el dato SI identifica la configuracion» sin haber comparado nada.")
    sys.exit(1)
