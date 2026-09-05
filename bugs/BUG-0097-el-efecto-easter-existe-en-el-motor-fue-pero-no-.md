---
id: BUG-0097
title: El efecto Easter existe en el motor FUE pero no está expuesto en el flujo guiado — y si se añade a mano, model_equation descuadra la ecuación
status: fixed
severity: critical
component: mcp-tools
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-05
reporter: David / sesión SERV_UEM — regresor Semana Santa 2026-09-05
tags:
  - easter
  - semana-santa
  - render
  - exposicion
  - determinista
references:
  - src/fue/fue.c (motor FUE: genera el regresor "easter" para series mensuales; Easter() en nlatools.c)
  - src/art/pipeline.py:268 (serializador: escribe "easter" si la intervención es de tipo easter)
  - src/art/describe.py:840 (model_equation: _seq incluye el omega de TODAS las intervenciones, sin filtrar tipo)
  - src/art/describe.py:1108-1115 (render Dₜ: solo ramas cos/sin/alter y step/pulse/impulse/ramp/compimp — no hay easter)
  - src/art/mcp_server.py (ninguna herramienta expone "easter")
  - bugs/BUG-0097-repro/repro.py

---

## Summary

El efecto Semana Santa ("easter") está especificado y generado en el motor FUE
(fue.c: si la variable determinista se llama "easter" y la serie es mensual,
genera el regresor clásico TRAMO/SEATS — 1.0 en el mes del Domingo de
Resurrección, repartido 0.5 marzo + 0.5 abril cuando el Viernes Santo cae en
marzo). art-python lo serializa (pipeline.py:268 escribe "easter" en el .inp),
pero **no lo expone al analista**: no hay herramienta MCP para añadirlo, y
`model_equation` (describe.py) no tiene rama para `easter`, de modo que el
render de la ecuación **descuadra** la indexación de coeficientes.

## Impact

Doble. (1) El analista no puede añadir el efecto Semana Santa por el flujo
guiado: tiene que editar el .inp a mano y reestimar con estimate_and_diagnose.
(2) Peor: al hacerlo, la ecuación que se le muestra es **falsa**. Medido en
SERV_UEM (1/2002-12/2019): el modelo m12_easter estima easter ω=+0.2540
(t≈9.4, altamente significativo), SAR(2) φ=[0.3804, 0.3646], μ=0.1628; pero
model_equation imprime "(1 − 0.2540·B¹² − 0.3804·B²⁴)(∇Nₜ − 0.3646)" — el
0.2540 es el ω del easter mal ubicado como φ₁ del SAR, y el 0.3646 es φ₂ del
SAR mal ubicado como media. El analista lee un modelo que no existe.

## Reproduction

En SERV_UEM, sobre `services/work/SERV_UEM_m11_sar2.inp`:

1. Añadir a mano `easter` como 13º determinístico (n=13, omega order 0, semilla
   0.0) → `SERV_UEM_m12_easter.inp`.
2. `estimate_and_diagnose(inp_path=…m12…)`: el motor estima sin error,
   convergencia 23 iteraciones. El `.out` da easter ω=+0.2540 (0.0270), SAR(2)
   [0.3804, 0.3646], μ=0.1628, σ̂ₐ=0.1524%, AIC −150.99.
3. El bloque "MODELO ESTIMADO" que muestra model_equation NO contiene el easter
   y descuadra: "(1 − 0.2540·B¹² − 0.3804·B²⁴)(∇Nₜ − 0.3646)".

El easter absorbe los anómalos de abril (04/2013, 04/2017, 04/2019, 04/2015
desaparecen de |z|>3) — la evidencia de que el efecto es real y relevante.

## Root cause

`model_equation` (describe.py:840) construye `_seq` iterando sobre TODAS las
intervenciones (`for j, itv in enumerate(model.interventions or [])`) y añade
el omega de cada una, sin filtrar por tipo. Pero el render de la parte
determinista (describe.py:1108-1115) solo tiene ramas para `cos/sin/alter` y
para `step/pulse/impulse/ramp/compimp`. Como no hay rama para `easter`, el
cursor `pi` que consume `_seq` NO avanza sobre el omega del easter durante el
render de Dₜ, pero ese omega SÍ está en `_seq`. Resultado: todos los `pi.pop()`
posteriores (AR estacional, MA, μ) se desplazan una posición. La exposición
falla porque mcp_server.py no registra ninguna herramienta que construya una
intervención de tipo "easter".

## Fix

1. Añadir rama `elif t in ("easter", "trend")` en el render de Dₜ de
   model_equation (describe.py:1108), que consuma el omega vía `pi.pop()` y lo
   muestre como `ξₜ^{Easter}`. Cualquier tipo determinista nuevo debe tener su
   rama de render **y** su entrada en `_seq` — hoy `_seq` acepta todo y el
   render solo una parte, que es el desajuste.
2. Exponer el efecto: una herramienta MCP (o una opción en confirm_and_estimate
   / suggest_intervention_form) que añada `easter` como determinístico, en vez
   de exigir editar el .inp a mano.

## Validation

`bugs/BUG-0097-repro/repro.py` (determinista, sin datos ni motor) comprueba
que (a) el serializador reconoce "easter", (b) mcp_server.py no expone
"easter", y (c) model_equation no tiene rama de render para "easter" mientras
_seq sí la incluye — el desajuste que descuadra la ecuación. Exit 1 = bug
presente. Tras el fix: exit 0, y re-estimando m12_easter el bloque MODELO
ESTIMADO debe mostrar `easter` y la ecuación correcta (SAR(2) φ=[0.3804,
0.3646], μ=0.1628).


---

## Cierre (2026-09-06) — y era una clase, no un tipo

Verificado contra el motor, el binario y los ficheros. Tres cosas del informe se
confirman, una se corrige y aparecen dos más.

### Lo que NO estaba roto

**`fue` sí expone el easter**: tipo determinista 9, `Intervention("easter")`,
generador en `cast_us.py`, lector/escritor en `inp.py`, render en `report.py`.

**Y el `.pre` lo conserva**, por los dos caminos. Fue un defecto de `fue` C
—su BUG-0007, el escritor emitía siete de las nueve palabras deterministas— y
está arreglado en **fue-1.13.1**; el binario instalado lo tiene:

    por fue-python   ω −0.15500298 → .pre → −0.15500300     Δℓ = 6.8e-13
    por el binario C  ℓ(.inp) = 12.5911621836
                      ℓ(.pre) = 12.5911621836               idénticos

⚠ **El rótulo no distingue**: `fue-1.13` (sin el arreglo) y `fue-1.13.1` (con él)
se identifican los dos como `FUE 1.13`. Sólo se sabe estimando y mirando el `.pre`.

### El descuadre, medido — y peor que lo reportado

    .out (constancia fiel)             lo que se mostraba
    ω easter = −0.124799  SE 5.8981    Dₜ:   (vacío)
    φ₁       = −0.052053  SE 0.0746    (1 + 0.1248·B)(∇Nₜ + 0.0521) = aₜ
    μ        = +0.623733  SE 2.1745             (5.8981)      (0.0746)

El ω del easter impreso como φ₁, el φ₁ como media, la media desaparecida, y cada
error típico bajo el coeficiente equivocado. **Todo desplazado una posición.**

### Y el mismo agujero en un segundo sitio

`describe_seasonal_params` recorre la MISMA secuencia con su propio cursor y
tenía las mismas ramas y las mismas ausencias: un `easter` delante de un armónico
y los armónicos posteriores se leían corridos. Por eso el arreglo cierra la
CLASE y no el tipo.

### Fix

1. **Rama `easter`/`trend`** en el render de Dₜ, con su símbolo `ξₜ^{Easter}` y
   sin fecha — no son sucesos.
2. **Un `else` final** en los dos recorridos, que consume cualquier tipo, incluso
   uno que aún no exista.
3. **La red de seguridad**: si el cursor no ha agotado `_seq`, la ecuación lo
   DICE — *«se han colocado N de M parámetros… no los leas»*. Un aviso feo es
   mejor que una ecuación limpia que miente.
4. **La fecha inventada**: la spec del guion registraba
   `{'type':'easter','date':'01/2005'}` —un suceso que no ocurrió, el `at=0` del
   relleno convertido en fecha—. Ahora `SIN_FECHA = ("easter","trend")`.
5. **Expuesto**: `confirm_and_estimate(..., easter=True)`, con los deterministas
   y no por el nodo de intervenciones, que pide fecha y forma. Se niega en series
   no mensuales, que es donde el motor no lo construye.

### Verificación

    Dₜ:
    − 0.1248 ξₜ^{Easter}
     (5.8981)

    (2)  (1 + 0.0521·B) (∇Nₜ − 0.6237) = aₜ
             (0.0746)         (2.1745)

Cada valor y cada error típico, en su sitio. 15 pruebas en
`tests/test_easter_y_el_cuadre_de_la_ecuacion.py`.
