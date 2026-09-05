"""BUG-0087 — el default de `umbral_vecino` dejaba pasar un vecino anómalo a >2σ.

`check_intervention_fit` aplicaba la regla de Treadway —«un vecino anómalo es
evidencia de que la REPRESENTACIÓN elegida es errónea»— con el umbral de los
outliers AUTÓNOMOS (3.0), no con el de la regla de la escuela (>2σ). Medido en
FOOD_UEM Ucrania (4/2022): con 1, 2 y 3 escalones el vecino «después» queda en
2.37 / 2.39 / 2.18 σ —más de 2σ— y el default lo daba por «funciona».

Sintético y determinista, sin datos ni motor. Comprueba el umbral EFECTIVO, no
el literal de la firma: lo que importa es el que se aplica.
"""
import inspect
import sys

sys.path.insert(0, "src")

from art.interventions import InterventionFitCheck, check_intervention_fit
from art.policy import THRESHOLDS

FALLOS = []

# ── A. cuál es el umbral que de verdad se aplica ──
print("== A. El umbral efectivo")
firma = inspect.signature(check_intervention_fit).parameters["umbral_vecino"].default
efectivo = THRESHOLDS.get("intervention_vecino") if firma is None else firma
print(f"  default de la firma      : {firma}")
print(f"  THRESHOLDS['intervention_vecino'] : "
      f"{THRESHOLDS.get('intervention_vecino')}")
print(f"  umbral EFECTIVO          : {efectivo}")
if efectivo is None:
    print("  FALLA: no hay umbral que aplicar")
    FALLOS.append("sin umbral")
elif efectivo > 2.0:
    print(f"  FALLA: {efectivo} deja ciego el tramo (2, {efectivo})σ")
    FALLOS.append(f"umbral {efectivo} > 2.0")
else:
    print("  OK: no queda punto ciego por encima de 2σ")

# ── B. la decisión, sobre los vecinos observados ──
print("\n== B. FOOD_UEM Ucrania 4/2022 — vecino «después» con n = 1, 2, 3")
for z in (2.3664, 2.3896, 2.1763):
    c = InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=243, fechas=[243],
        z_en_fechas=[0.0], z_antes=1.34, z_despues=z,
        umbral_vecino=efectivo, umbral_absorcion=1.5)
    print(f"  vecino = {z:+.2f}σ  →  funciona={c.funciona}  "
          f"vecino_anomalo={c.vecino_anomalo!r}")
    if c.funciona:
        FALLOS.append(f"vecino {z:.2f} dado por bueno")

# ── C. y un vecino tranquilo sigue siendo tranquilo ──
print("\n== C. Un vecino que de verdad no dice nada")
c = InterventionFitCheck(
    itv_index=0, itv_type="step", at_0based=243, fechas=[243],
    z_en_fechas=[0.0], z_antes=0.4, z_despues=1.1,
    umbral_vecino=efectivo, umbral_absorcion=1.5)
print(f"  vecino = +1.10σ  →  funciona={c.funciona}")
if not c.funciona:
    print("  FALLA: bajar el umbral no puede marcar cualquier cosa")
    FALLOS.append("falso positivo a 1.1 sigma")

# ── D. un solo umbral, no tres ──
print("\n== D. El umbral vive en un sitio")
import pathlib
literales = []
for f in ("src/art/interventions.py", "src/art/escalera.py",
          "src/art/configuracion.py", "src/art/mcp_server.py"):
    t = pathlib.Path(f).read_text()
    for pat in ("umbral_vecino: float = 3.0", "umbral_vecino: float = 2.5",
                "umbral_vecino=3.0", "umbral_vecino=2.5"):
        if pat in t:
            literales.append(f"{f}: {pat}")
if literales:
    print("  FALLA: quedan defaults literales:")
    for x in literales:
        print("   ", x)
    FALLOS.append("umbral repartido en literales")
else:
    print("  OK: ningún default literal; sale de `policy.THRESHOLDS`")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: la regla de Treadway ve el vecino a >2σ, y el umbral vive en la política.")
