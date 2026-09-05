---
id: BUG-0087
title: El default de umbral_vecino (3.0) deja pasar un vecino anómalo a >2σ — la regla de Treadway no marca «no exitosa»
status: fixed
severity: high
component: interventions
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David / sesión FOOD_UEM — escalera Ucrania 4/2022
tags: [interventions, escalera, treadway, umbral, vecino]
references:
  - src/art/interventions.py:617-621 (la regla: «un vecino anómalo es evidencia de que la REPRESENTACIÓN es errónea»)
  - src/art/interventions.py:732-735 (check_intervention_fit, umbral_vecino=3.0)
  - src/art/interventions.py:696-704 (vecino_anomalo / funciona)
  - src/art/mcp_server.py:1177 (intervention_ladder, umbral_vecino=3.0)
  - src/art/mcp_server.py:5326 (guided_intervention, umbral_vecino=3.0)
  - src/art/policy.py:57-87 (THRESHOLDS — intervention_autoselect=2.0, mu_drift=2.0; no hay entrada de vecino)
  - bugs/BUG-0087-repro/repro.py
---

## Summary

`check_intervention_fit(model, umbral_vecino=3.0)` —y las herramientas que lo
usan, `intervention_ladder` y `guided_intervention`— aplican la regla de Treadway
(«un vecino anómalo es evidencia de que la representación elegida es errónea»)
con el umbral de los outliers **autónomos** (3.0) en vez del umbral de la regla
de la escuela (>2σ). Un vecino en el punto ciego (2, 3)σ se da por **funciona**
(intervención exitosa) cuando la regla exige marcar **no exitosa**.

## Impact

El nodo de intervención declara «exitosa» una intervención que deja un vecino
anómalo a >2σ, así que no sube de peldaño ni corrige la forma cuando debería.
Medido en FOOD_UEM Ucrania (4/2022): los tres peldaños (1, 2 y 3 escalones)
dejan el vecino «después» en 2.37 / 2.39 / 2.18 σ, y los tres se marcan
`funciona=True` con el default. El analista que confíe en el veredicto para ahí
con una forma que Treadway da por mala.

## Reproduction

`bugs/BUG-0087-repro/repro.py` — sintético, determinista, sin datos ni motor.
Muestra el default (3.0) y que un vecino a 2.18–2.39σ da `funciona=True` con
3.0 y `funciona=False` con 2.0:

```
default umbral_vecino = 3
  vecino después = +2.37σ  →  umbral 3.0: funciona=True  |  umbral 2.0: funciona=False
  vecino después = +2.39σ  →  umbral 3.0: funciona=True  |  umbral 2.0: funciona=False
  vecino después = +2.18σ  →  umbral 3.0: funciona=True  |  umbral 2.0: funciona=False
FALLA (exit 1)
```

Sobre el modelo real (`cases/UEM_FOOD_SERV_2025/food/work/FOOD_UEM_2025_b01_ukr_n3.pre`):
`check_intervention_fit(m)` devuelve `funciona=True, vecino_anomalo=None` con
`z_despues=+2.18`; con `umbral_vecino=2.0` devuelve `funciona=False,
vecino_anomalo='después'`.

## Root cause

`umbral_vecino` está hardcodeado a `3.0` en tres sitios
(`check_intervention_fit` interventions.py:733, `intervention_ladder`
mcp_server.py:1177, `guided_intervention` mcp_server.py:5326) y no existe en
`THRESHOLDS`. El 3.0 es el umbral de los outliers autónomos (policy.py:59); la
regla de Treadway sobre el vecino es más sensible y va en la línea de
`intervention_autoselect=2.0` y `mu_drift=2.0` (policy.py:62,67) — dos umbrales
que ya bajan a 2.0 precisamente porque un anómalo de vecino es la parte no
modelizada del suceso, que hay que ver, no suavizar.

## Fix

Añadir `THRESHOLDS["intervention_vecino"] = 2.0` y usarlo como default en los
tres sitios (o, como mínimo, bajar el default literal a 2.0). El cambio es un
número; el efecto es que la escalera vuelve a ver el vecino que hoy se le escapa.

## Validation

Con 2.0 el repro sale 0 (el vecino a >2σ se marca anómalo). Sobre FOOD_UEM
Ucrania, `check_intervention_fit` pasa de `funciona=True` a `funciona=False` en
los tres peldaños — que es justo lo que la regla de Treadway exige.

---

## Fix (aplicado, 2026-09-05)

`THRESHOLDS["intervention_vecino"] = 2.0`, y los **cuatro** sitios lo consumen.
Eran cuatro y no tres: `configuracion.evalua_configuraciones` tenía un **2.5**,
un tercer número para el mismo concepto. Ahora no queda ningún default literal —
hay un test que lo fija.

El idioma es el que ya usaba `ventana` en este nodo: `umbral_vecino=0` significa
«el de la política». El analista sigue pudiendo declararlo.

**El argumento del umbral — corregido.** La primera versión de este arreglo lo
justificaba por analogía con `intervention_autoselect` y `mu_drift`, que ya
estaban en 2.0. El analista señaló que la regla se puede comprobar
matemáticamente, y tenía razón: la analogía sobraba.

Preguntar «¿queda masa del suceso en el vecino?» es preguntar **si hace falta un
ω más**, y eso es el contraste de puntuación. La condición de primer orden deja
`Σ_t a_t·x_t^(j) = 0` con `x_t^(j) = π(B)[B^j/δ(B)]ξ_t`, así que

    LM = (Σ_t a_t·x_t^(k+1))² / (σ̂² Σ_t (x_t^(k+1))²)   ~   χ²(1)

y **sin ARMA el regresor filtrado es una ficticia**: la suma colapsa en un
término y `LM = a²/σ̂² = z²`. El residuo tipificado del vecino ES el contraste.

    z = 2.0  →  χ²(1) = 4.00  →  p = 0.0455
    z = 3.0  →  χ²(1) = 9.00  →  p = 0.0027

Comprobado sobre 200 réplicas (ruido blanco, suceso de dos períodos, un solo ω
ajustado, LR contra el de dos):

| sin ARMA | tamaño | potencia |
|---|---|---|
| `z > 2` | **5.0%** | **75.0%** |
| `z > 3` | 1.0% | 36.0% |
| LR al 5% | 5.5% | 75.0% |

razón z²/LR: mediana **1.001**, [p10 0.996, p90 1.012].

**Y esto agranda el reporte**: el 3.0 no dejaba «un punto ciego en (2,3)σ»,
partía la potencia por la mitad —36% frente a 75%— incluso en el caso ideal.

*(Con ARMA la equivalencia se rompe y el vecino crudo se queda corto; eso es
BUG-0089, que sale de este mismo experimento.)*

## Validation — resultado

El repro sale 0, reescrito para comprobar el umbral **efectivo** (el que se
aplica) y no el literal de la firma, más un bloque que verifica que no quedan
defaults literales repartidos.

`tests/test_bug_0087_0088_umbral_y_guion.py`, 17 pruebas (compartidas con
BUG-0088): los tres vecinos de Ucrania, que un vecino a 1.1σ sigue pasando, y
que el analista puede seguir declarando el suyo.

**Radio de impacto, medido.** Sobre los `.pre` de FOOD_UEM y de la réplica
(run 5): **14 intervenciones evaluadas, 1 veredicto cambia** (7%).

Y el que cambia es el que corresponde:

```
FOOD_UEM_m03_i1.pre   itv[11] step   z_ant=+2.43  z_des=-1.19   True -> False
```

`m03_i1` es el escalón permanente de 03/2017, y el vecino que ahora ve es el
**+2.43σ de 02/2017** — exactamente la cola sub-umbral que motivó BUG-0083 y que
`incident_configurations` acabó resolviendo como `02/2017×2`. Con 3.0 la regla de
Treadway no la veía; con 2.0 la señala, que es lo que la regla existe para hacer.
