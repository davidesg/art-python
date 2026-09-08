"""BUG-0006 — la semilla estacional por defecto llevaba a un óptimo espurio.

El modelo AR(2)×(2,0,0)_12 del IPC de EE.UU. (mensual, 2002:01-2026:05, n=293)
caía, con la semilla estacional de signo equivocado, en un óptimo donde μ se
desploma a un valor absurdo, σ̂ₐ sube y el AIC empeora ~100 puntos — y aun así el
ajuste decía `converged=True, ifault=0` sin diagnóstico. La serie va empotrada
en `US_CPI.pre`, así que el repro es autónomo.

    cd bugs/BUG-0006-repro && python repro.py

ESTADO (2026-09-08): NO reproduce, ni en Linux ni en Windows. La semilla del
signo correcto está en art 0.2.0, y los dos arranques llegan al mismo óptimo.
Se conserva como GUARDIÁN: si un cambio futuro devuelve la divergencia entre
arranques, esto la caza. Sale 1 si los dos óptimos difieren.

Dos defectos DEL PROPIO REPRO, corregidos aquí (BUG-0118):

  1. la columna «Phi seed» mostraba el valor YA AJUSTADO. `m_seed = m1.ar_s`
     guardaba una REFERENCIA que `fit()` reescribe in situ, así que las dos
     filas enseñaban el óptimo y no las semillas — justo la columna que
     distingue los dos arranques, o sea la única que este repro existe para
     comparar. Hacía parecer que los dos arranques eran el mismo, que es la
     conclusión contraria a la que investiga.

  2. `report()` mezclaba unidades: multiplicaba σ_a por 100 y no tocaba μ, y no
     dividía ninguno por `refactor` (que vale 100). Su propio bloque «Expected»
     no casaba con lo que él mismo imprimía, y un lector cuidadoso veía una
     divergencia de ×100 donde no la había.
"""
import copy
import sys

import numpy as np

import fue
from art.pipeline import _make_model

ld = fue.load("US_CPI.pre")
ts = ld[0] if isinstance(ld, tuple) else ld.series
SPEC = dict(lam=0.0, d=1, D=0, p=2, q=0, n_harmonics=5, P=2, Q=0,
            estimate_mu=True)

#: Los valores de referencia, Y SUS UNIDADES, que NO son las mismas para los
#: dos. Ésta es la trampa que hizo falta deshacer a mano al verificar el caso en
#: Windows, y no estaba en ninguna parte:
#:
#:     μ̂  ≈ +0.0021   está en PROPORCIÓN            (en la escala del modelo, 0.2149)
#:     σ̂ₐ ≈  0.261    está en la escala REESCALADA  (en proporción, 0.002608)
#:
#: El modelo estima sobre `refactor`·log(y) —100 por convención de la suite— y
#: las cifras publicadas mezclan las dos escalas. Presentar las dos juntas sin
#: decirlo hace ver una divergencia de ×100 donde no la hay.
CORRECTO = dict(mu_prop=+0.0021, sigma_resc=0.261)
#: El óptimo espurio que se observaba, en esas mismas unidades mezcladas.
ESPURIO = dict(mu_prop=-0.144, sigma_resc=0.305)


def informe(etiqueta, m, semilla):
    """LAS DOS ESCALAS, siempre, y etiquetadas.

    El modelo estima sobre `refactor`·log(y) —100 por convención de la suite—.
    La versión anterior multiplicaba σ_a por 100, no tocaba μ y no dividía
    ninguno por `refactor`, así que su propio bloque «Expected» no casaba con lo
    que ella misma imprimía. Imprimir las dos y decir cuál es cuál cuesta una
    línea y quita toda la ambigüedad.
    """
    r = m._result
    p = np.asarray(r.params, float)
    phi, mu = p[-5:-1], p[-1]
    k = float(getattr(m, "refactor", 1.0) or 1.0)
    sig = float(np.sqrt(r.sigma2))
    print(f"  {etiqueta:16} semilla Φ⁰ = {np.round(semilla, 4).tolist()}")
    print(f"  {'':16} Φ̂ = {np.round(phi, 3).tolist()}")
    print(f"  {'':16} μ̂   reescalada {mu:+.6f}   proporción {mu / k:+.6f}")
    print(f"  {'':16} σ̂ₐ  reescalada {sig:.6f}   proporción {sig / k:.6f}")
    print(f"  {'':16} AIC {r.aic:.1f}   converged={r.converged} "
          f"ifault={r.ifault}   (refactor={k:g})")
    return mu / k, sig


print(f"IPC de EE.UU., n={ts.nobs}.  Cada cifra CON SU ESCALA.\n")

m1 = _make_model(ts, **SPEC)
semilla1 = copy.deepcopy(m1.ar_s)          # ANTES de fit(): fit() la reescribe
m1.fit()
mu1, s1 = informe("por defecto", m1, semilla1)
print()

m2 = _make_model(ts, **SPEC)
m2.ar = [[0.60, -0.17]]
m2.ar_s = [[-0.11, -0.09]]
semilla2 = copy.deepcopy(m2.ar_s)
m2.fit()
mu2, s2 = informe("identificada", m2, semilla2)

print(f"\nreferencia (artículo, Tabla 2):"
      f"  μ̂ ≈ {CORRECTO['mu_prop']:+.4f} (proporción)"
      f"   σ̂ₐ ≈ {CORRECTO['sigma_resc']:.3f} (reescalada)")
print(f"óptimo espurio de su día:      "
      f"  μ̂ ≈ {ESPURIO['mu_prop']:+.4f} (proporción)"
      f"   σ̂ₐ ≈ {ESPURIO['sigma_resc']:.3f} (reescalada)")
print("  ⚠ las dos cifras publicadas están en escalas DISTINTAS; comparar cada")
print("    una con la columna que le corresponde arriba.")

difieren = abs(mu1 - mu2) > 1e-4 or abs(s1 - s2) > 1e-4
if difieren:
    print("\nFALLO  los dos arranques llegan a ÓPTIMOS DISTINTOS: la divergencia")
    print("       ha vuelto. Comparar con el artículo para ver cuál es el bueno.")
    sys.exit(1)
print("\nOK  los dos arranques llegan al MISMO óptimo. No reproduce.")
