"""BUG-0105 — el recuento de residuos extremos entra en el veredicto de adecuacion
sin calibrar por n y CONTRADICE al Jarque-Bera que el mismo informe acaba de aprobar.

A) CALIBRACION. Bajo especificacion correcta, |z|>3 no es un suceso raro con las n
   habituales: es lo normal. Con n=215 se esperan 0.58 y hay un 44% de probabilidad
   de ver al menos uno. La MEDIANA del maximo |z| es 2.95 -- por debajo del umbral,
   pero tan cerca que el umbral marca a mas de la mitad de los modelos correctos.

B) CONTRADICCION. `_conclusiones_desde` mete n_extreme en la lista de FALLOS sin
   mirar si el JB paso. El JB es el contraste de las colas: si NO rechaza, ya ha
   dictaminado que las colas son compatibles con la normal. Volver a senalar una
   observacion de la cola como prueba de inadecuacion contradice el veredicto que
   acaba de emitirse tres lineas mas arriba.
"""
import os
import sys

import numpy as np
from scipy.stats import norm

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "src"))

FALLOS = []

print("== A) Calibracion: |z|>3 bajo especificacion CORRECTA")
for n in (100, 215, 400):
    p = 2 * norm.sf(3.0)
    print("   n=%3d : esperados %.2f   P(al menos uno)=%.3f" % (n, n * p, 1 - (1 - p) ** n))
rng = np.random.default_rng(0)
m = np.abs(rng.standard_normal((200_000, 215))).max(1)
print("   n=215 : maximo |z| simulado -> mediana=%.2f  p90=%.2f  P(max>3.08)=%.3f"
      % (np.median(m), np.percentile(m, 90), (m > 3.08).mean()))
if np.median(m) < 3.0:
    print("   -> la MEDIANA del maximo (%.2f) esta por debajo del umbral 3.0:" % np.median(m))
    print("      el umbral marca a mas de la mitad de los modelos bien especificados")
# Lo anterior es la aritmética de la normal: el defecto era usar el 3 fijo. El
# arreglo (cierre del 07-09-2026) es un umbral calibrado por n, el cuantil 90
# del máximo: art.mcp_server.umbral_extremo. Se comprueba que existe y que
# coincide con la simulación.
try:
    from art.mcp_server import umbral_extremo
    c = umbral_extremo(215)
    print("   umbral calibrado de art con n=215: %.2f  (p90 simulado %.2f)"
          % (c, np.percentile(m, 90)))
    if abs(c - np.percentile(m, 90)) > 0.05:
        FALLOS.append("umbral_extremo(215)=%.2f no es el p90 del maximo (%.2f)"
                      % (c, np.percentile(m, 90)))
except ImportError:
    FALLOS.append("umbral |z|>3 no calibrado por n: falso positivo del 44%% con n=215")

print("\n== B) Contradiccion en el mismo informe")
from art import mcp_server


class _D:
    def __init__(self, data):
        self.data = data


# Q y JB APROBADOS, un solo residuo extremo -- el caso de UEM_HCPI m09
diag = _D({"white_noise": True, "normal": True, "q_pass": True, "jb_pass": True,
           "n_extreme": 1, "q_fails": []})
txt = mcp_server._conclusiones_desde(diag)
print("   diagnosis: white_noise=True  normal=True  n_extreme=1")
print("   conclusiones -> %s" % txt.splitlines()[0])
if "NO se sostiene" in txt:
    FALLOS.append("con la Q y el JB aprobados, un unico |z|>3 dicta 'El modelo NO se sostiene'")

print("\n== RESULTADO")
for f in FALLOS:
    print("   FALLO: %s" % f)
print("   %d fallo(s)" % len(FALLOS))
sys.exit(1 if FALLOS else 0)
