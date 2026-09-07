"""BUG-0108 — el padre que registra estimate_and_diagnose es falso, y la cascada de
guion_abandon lo convierte en destructivo.

confirm_and_estimate tiene `base_pre_path`: sabe de que modelo encadena y puede
registrar el linaje bien. estimate_and_diagnose NO tiene ningun parametro
equivalente, asi que registra como padre la ULTIMA entrada del guion, que no
tiene por que ser el modelo del que sale el .inp.

Eso importa porque hay .inp que SOLO se pueden construir a mano -- los AR
factorizados y los AR(2) de frecuencia fija, que la superficie MCP no expone
(BUG-0103). Cada uno de esos modelos entra en el guion con un padre inventado.

Y el linaje falso hace destructivo un abandono correcto: guion_abandon arrastra
a los descendientes por diseno --una decision contaminada contamina lo que
viene despues-- de modo que marcar un callejon puede barrer la rama viva.
"""
import inspect
import sys

sys.path.insert(0, "src")

from art import mcp_server

FALLOS = []

sig_ce = inspect.signature(mcp_server.confirm_and_estimate)
sig_ed = inspect.signature(mcp_server.estimate_and_diagnose)

print("== Parametros de linaje")
print("   confirm_and_estimate  : base_pre_path=%s" % ("base_pre_path" in sig_ce.parameters))
print("   estimate_and_diagnose : base_pre_path=%s  parent=%s  guion_parent=%s"
      % ("base_pre_path" in sig_ed.parameters,
         "parent" in sig_ed.parameters,
         "guion_parent" in sig_ed.parameters))

if not any(k in sig_ed.parameters for k in ("base_pre_path", "parent", "guion_parent")):
    FALLOS.append("estimate_and_diagnose no puede declarar de que modelo desciende")

print("\n== Caso real: cases/UEM_HCPI_0226 (guion de 15 entradas)")
print("   v10 e07_fact   <- v9   (correcto)")
print("   v11 e08_noarf4 <- v10  (correcto)")
print("   v12 e09_ffix4  <- v11  (FALSO: se construyo a mano desde v10, e07_fact)")
print("   v14 e11_meg2   <- v12 ; v15 e12_ffix2 <- v14")
print("   -> v11 es un callejon (LR=9.78, 2 g.l., p=0.0075) y hay que marcarlo,")
print("      pero guion_abandon(11) EN CASCADA se lleva v12, v14 y v15,")
print("      que son la rama viva y no descienden de el.")
FALLOS.append("un abandono correcto con cascada barre la rama viva por un padre falso")

print("\n== RESULTADO")
for f in FALLOS:
    print("   FALLO: %s" % f)
print("   %d fallo(s)" % len(FALLOS))
sys.exit(1 if FALLOS else 0)
