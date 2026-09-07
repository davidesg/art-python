"""BUG-0106 — _reformulacion_desde lee claves que la diagnosis no escribe.

describe.py:1967-1968 publica el dict de diagnosis con las claves
"white_noise" y "normal". _conclusiones_desde (mcp_server.py:1077-1081) las lee
bien. _reformulacion_desde (mcp_server.py:1050-1052) lee "q_pass" y "jb_pass",
que NO EXISTEN en ese dict: d.get(...) devuelve None, None is False es False, y
la rama de fallo no se ejecuta NUNCA.

Consecuencia: el bloque que le dice al analista si hay que seguir iterando es
CIEGO a los dos contrastes que deciden la adecuacion, y solo reacciona a
n_extreme -- el unico criterio que, ademas, no deberia estar ahi (BUG-0105).
"""
import sys

sys.path.insert(0, "src")

from art import mcp_server
from art import describe  # noqa: F401  (documenta de donde salen las claves)

FALLOS = []


class _D:
    def __init__(self, data):
        self.data = data


print("== Claves que ESCRIBE la diagnosis (describe.py:1967-1968)")
print("   'white_noise', 'normal'")
print("== Claves que LEE _reformulacion_desde (mcp_server.py:1050-1052)")
print("   'q_pass', 'jb_pass'")

# El caso de UEM_HCPI m10: Q pasa, JB RECHAZA (p=0.0438), sin anomalos.
diag = _D({"white_noise": True, "normal": False, "n_extreme": 0})
txt = mcp_server._reformulacion_desde(diag, "")
print("\n== Q=True, JB=False, sin anomalos  ->  reformulacion dice:")
print("   %r" % (txt or "(vacio: no reporta ningun fallo)"))
if "Jarque" not in txt:
    FALLOS.append("con el JB rechazando, la reformulacion no reporta fallo alguno")

# Y ni siquiera ve fallar la Q.
diag2 = _D({"white_noise": False, "normal": False, "n_extreme": 0})
txt2 = mcp_server._reformulacion_desde(diag2, "")
print("\n== Q=False, JB=False, sin anomalos  ->  reformulacion dice:")
print("   %r" % (txt2 or "(vacio: no reporta ningun fallo)"))
if "Q" not in txt2 and "Jarque" not in txt2:
    FALLOS.append("con la Q Y el JB rechazando, la reformulacion sigue sin reportar nada")

# Control: con las claves que SI lee, funciona -- prueba de que es el nombre.
diag3 = _D({"q_pass": False, "jb_pass": False, "n_extreme": 0})
txt3 = mcp_server._reformulacion_desde(diag3, "")
print("\n== CONTROL con las claves q_pass/jb_pass  ->  reformulacion dice:")
print("   %r" % (txt3 or "(vacio)"))
if "Q" in txt3 or "Jarque" in txt3:
    print("   -> con las otras claves SI funciona: el defecto es el NOMBRE, no la logica")

print("\n== RESULTADO")
for f in FALLOS:
    print("   FALLO: %s" % f)
print("   %d fallo(s)" % len(FALLOS))
sys.exit(1 if FALLOS else 0)
