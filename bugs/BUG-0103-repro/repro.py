"""BUG-0103 — el modelo FACTORIZADO que ar_factorization prescribe no es
construible desde la superficie MCP, y nada advierte del salto lógico que la
propia salida invita a dar.

Dos comprobaciones independientes:

  A) ALGEBRA — un operador "solo en B^s" tiene sus s raices con el MISMO modulo
     y las frecuencias CLAVADAS en multiplos de 2*pi/s. Por tanto, leer unos
     modulos casi iguales en la salida de ar_factorization como "esto es en
     realidad un AR disperso en B^s" IMPONE esa igualdad en vez de contrastarla.
     La igualdad de modulos es la hipotesis, no el hallazgo.

  B) SUPERFICIE — fue.Model admite `ar` como LISTA DE FACTORES y `ar_f` como
     factores de segundo orden con frecuencia FIJA, que es exactamente lo que
     hace falta para estimar el modelo factorizado y para contrastar despues la
     restriccion de frecuencia estacional. confirm_and_estimate expone `p`
     ESCALAR: un unico operador sin factorizar de orden p. No hay parametro
     alguno en la superficie MCP para los factores ni para ar_f.
"""
import inspect
import sys

import numpy as np

sys.path.insert(0, "src")

FALLOS = []

# ---------------------------------------------------------------- A) ALGEBRA
print("== A) Un operador solo en B^6 impone modulo comun y frecuencias fijas")
Theta = 0.2290                      # phi_6 estimado en UEM_HCPI m02
theta = Theta ** (1 / 6)

# identidad: 1 - Theta B^6 = (1 - theta B)(1 + theta B + ... + theta^5 B^5)
prod = np.convolve([1.0, -theta], [theta ** k for k in range(6)])
assert np.allclose(prod, [1, 0, 0, 0, 0, 0, -Theta]), prod
print("   identidad (1-thB)(1+thB+...+th^5B^5) = 1 - Theta B^6 : OK")

raices = np.roots([-Theta, 0, 0, 0, 0, 0, 1.0])
mods = np.abs(raices)
angs = np.sort(np.abs(np.degrees(np.angle(raices))))
print("   modulos: min=%.6f max=%.6f  dispersion=%.2e" % (mods.min(), mods.max(), mods.ptp()))
print("   angulos: %s" % np.round(angs, 3))
if mods.ptp() > 1e-9:
    FALLOS.append("los modulos deberian ser identicos por construccion")
print("   -> 1 parametro frente a los 6 del AR(6) libre = 5 RESTRICCIONES")
print("      (un amortiguamiento comun a las 4 frecuencias + las 4 frecuencias fijadas)")

# lo que dice el AR(6) LIBRE del caso real (ar_factorization sobre m02):
libres = {"real f=0": 0.78014, "real Nyquist": 0.77315,
          "AR(2) per=3.03": 0.79, "AR(2) per=6.67": 0.78}
print("\n   AR(6) libre estimado (UEM_HCPI m02): amortiguamientos %s" % libres)
print("   B^6 los igualaria todos a theta = %.5f" % theta)
print("   periodo del AR(2) semianual: 6.67 estimado frente a 6.00 impuesto (+11.1%)")
print("   -> esa desviacion es CONTRASTABLE y el operador en B^6 la fija por decreto")

# ------------------------------------------------------------- B) SUPERFICIE
print("\n== B) El motor admite factores; la superficie MCP no los expone")
from fue.model import Model
from art import mcp_server

sig_model = inspect.signature(Model.__init__)
print("   fue.Model.__init__ : ar=%s  ar_f=%s"
      % ("ar" in sig_model.parameters, "ar_f" in sig_model.parameters))
doc_ar = inspect.getdoc(Model) or ""
print("   docstring de Model : 'Each inner list is one factor' -> %s"
      % ("one factor" in doc_ar))

sig_ce = inspect.signature(mcp_server.confirm_and_estimate)
p_ann = sig_ce.parameters["p"].annotation
print("   confirm_and_estimate: p=%s (escalar)  factores expuestos=%s  ar_f expuesto=%s"
      % (p_ann,
         any(k in sig_ce.parameters for k in ("ar", "ar_orders", "ar_factors")),
         "ar_f" in sig_ce.parameters))

if "ar" not in sig_model.parameters or "ar_f" not in sig_model.parameters:
    FALLOS.append("el motor deberia admitir factores y ar_f")
if any(k in sig_ce.parameters for k in ("ar", "ar_orders", "ar_factors", "ar_f")):
    print("   (la superficie YA expone factores: bug corregido)")
else:
    FALLOS.append(
        "confirm_and_estimate no puede construir el modelo factorizado: "
        "solo p escalar, ningun parametro para los factores ni para ar_f")

# ninguna otra herramienta MCP lo expone tampoco
otras = [n for n, f in vars(mcp_server).items()
         if callable(f) and not n.startswith("_")
         and any(k in inspect.signature(f).parameters
                 for k in ("ar_orders", "ar_factors", "ar_f"))
         if inspect.isfunction(f)]
print("   herramientas MCP que exponen factores/ar_f: %s" % (otras or "NINGUNA"))
if not otras:
    FALLOS.append("ninguna herramienta MCP permite especificar el modelo factorizado")

print("\n== RESULTADO")
for f in FALLOS:
    print("   FALLO: %s" % f)
print("   %d fallo(s)" % len(FALLOS))
sys.exit(1 if FALLOS else 0)
