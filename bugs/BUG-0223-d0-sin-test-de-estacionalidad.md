---
id: BUG-0223
title: Con d=0 (serie de cointegración) el paso 3 no contrasta la estacionalidad y aun así dice «Decisión A — sin armónicos»
status: open
severity: medium
component: mcp-tools
found_in: 0.2.3.dev0 @088933d
fixed_in:
reported: 2026-10-07
reporter: David / Claude — revisión del paper de dolarización (Ecuador), Fase 1, ratio BXE = X/M
tags:
  - guiado
  - estacionalidad
  - d=0
  - multivariante
  - cointegracion
references:
  - src/art/mcp_server.py (guided_identification, paso 3, `if d > 0:` ≈ l.5682)
  - src/art/mcp_server.py (_sin_estacionalidad_next)
  - src/art/describe.py (describe_seasonality → detect_seasonality)
---

## Summary

**La restricción `d > 0` es correcta en Box-Jenkins y se mantiene.** En la
identificación BJ, con d = 0 todavía no está establecida la estacionariedad
(ADF/KPSS están sesgados por la propia estacionalidad), y un F-HAC sobre unos
niveles que en realidad deambulan puede leer tendencia como armónicos:
estacionalidad espuria. Por eso el test se hace tras diferenciar.

Lo que NO contempla es el caso **posterior, de cointegración**: el ratio (o la
diferencia de logs) de componentes I(1) cointegrados con vector (1, −1) es
d = 0 **por construcción**, y su estacionalidad es la de los componentes. Ahí la
serie es estacionaria con estacionalidad, y hay que contrastarla en niveles.

El defecto concreto:

En el paso 3 de `guided_identification`, cuando el analista confirma **d = 0**,
el test HAC de estacionalidad **no se ejecuta** y la salida concluye igualmente
«Decisión A: `D=0`, sin armónicos cos/sin. No hay ruta B1/B2 que elegir» y manda
directo a ARMA. No es un resultado: es la rama por defecto de una bandera que
nunca se calcula. La serie del caso tiene estacionalidad fuerte (HAC F = 9.58,
p < 0.0001).

## Impact

- Cualquier serie **estacionaria en niveles** (ratios, tasas, saldos — justo las
  que interesan en cointegración) pierde la estacionalidad en silencio.
- Con `objetivo="multivariante"` contradice la propia regla de la suite (B1 es
  requisito: el mismo tratamiento estacional en todas las series del sistema);
  la nota de objetivo ni siquiera se imprime, porque va en la rama
  `hay_estacionalidad`.
- En modo autónomo el LLM seguiría la «Decisión A» y estimaría un modelo sin
  armónicos: residuos con picos en 4, 8, 12 que luego se intentarían arreglar
  con ARMA estacional.
- Además no hay herramienta suelta que lo cubra: `seasonal_analysis` sólo
  contrasta sobre ∇ (la figura dice «100·log, d=1»), así que con d=0 no hay
  forma de pedir el test sobre la serie en niveles.

## Reproduction

Datos: `/home/david/Dropbox/dolarization/Python/art_drvec/EXT/ext_q.csv`,
columna `BXE` (cociente exportaciones/importaciones de bienes y servicios,
Ecuador, trimestral 2003T1–2019T4, n = 68). Ecuador: X sin estacionalidad, M con
estacionalidad determinista fuerte (f=1 y f=2, t de 3.8 a 6.7), así que X/M la
hereda.

```
load_data(source_path=".../ext_q.csv", output_inp="BXE.inp", column="BXE",
          freq=4, start_year=2003, start_period=1)
guided_identification(inp_path="BXE.inp", lam=0, d=0,
                      domain="multiplicative", objetivo="multivariante")
```

Salida observada (paso 3, d = 0): sin bloque «Test HAC de estacionalidad»,
sin figura de estacionalidad, sin nota de objetivo multivariante, y

> ### Siguiente paso — no hay estacionalidad que enrutar
> Decisión A: `D=0`, sin armónicos cos/sin. No hay ruta B1/B2 que elegir…

Contraste con la misma serie:

```
seasonal_analysis(inp_path="BXE.inp")
→ F-test HAC conjunto: F = 9.58, p = 0.0000 · f=1 χ² = 24.5 · Decisión B1
```

y el m00 estimado con armónicos (d = 0) da cos f=1 = −4.08 (1.54), t = 2.65.

## Root cause

`mcp_server.py`, paso 3 de `guided_identification`:

```python
hay_estacionalidad = False
if d > 0:
    sea = describe_seasonality(ts)
    ...
    hay_estacionalidad = bool(sea.data.get("seasonal_detected", False))
...
+ ((_nota_objetivo(objetivo) + b1_note + b1_steps + b2_steps)
   if hay_estacionalidad
   else _sin_estacionalidad_next(inp_path, lam, d))
```

El test sólo corre con `d > 0`; con d = 0 la bandera se queda en `False` y la
rama «sin estacionalidad» se imprime como si se hubiera contrastado.
`describe_seasonality` → `detect_seasonality(ts)` contrasta sobre ∇ fijo, así
que tampoco se puede llamar con d = 0 tal cual.

## Fix

Con cautela, sin tocar la ruta BJ por defecto:

1. **Nunca** imprimir «Decisión A» sin haber contrastado: con d = 0 la salida
   debe decir «estacionalidad NO contrastada (d = 0)» y ofrecer el contraste.
2. Contraste en niveles **sólo bajo justificación de estacionariedad**: cuando
   `objetivo="multivariante"`/cointegración, o cuando el analista lo pide
   (`contrastar_en_niveles=True`). `detect_seasonality` acepta `d` (0 o 1) y la
   figura lo rotula. La salida advierte que el F en niveles sólo es válido si la
   serie es estacionaria, y remite al Shin-Fuller / DCD de subdiferenciación del
   modelo estimado para confirmarlo.
3. Con `objetivo="multivariante"` imprimir siempre la nota de objetivo (B1 como
   requisito) aunque el test no detecte, porque la regla es de sistema, no de
   la serie.
4. `seasonal_analysis` suelto: aceptar `d` (por defecto el del flujo).

## Validation

- Test: BXE con d = 0 → paso 3 incluye el bloque HAC, detecta f = 1 y ofrece
  B1/B2.
- Test: serie estacionaria sin estacionalidad (ruido blanco + μ) con d = 0 →
  Decisión A, pero con el test impreso.
- Test: `objetivo="multivariante"`, d = 0 → la nota B1-requisito aparece.
