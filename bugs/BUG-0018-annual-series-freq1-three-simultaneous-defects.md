---
id: BUG-0018
title: Annual series (freq=1) never complete the flow — and the blocker was a FOURTH defect: seasonality detection divides by s-1 = 0
status: fixed
severity: high
component: pipeline
found_in: 0.1.4
fixed_in: 0.1.11 (unreleased)
reported: 2026-07-08
reporter: David / series anuales de precipitación (Ginebra, n=248, 1768-2015; "Joseph's Cycles")
tags:
  - annual
  - freq1
  - inp-builder
  - pyfug
  - blocker
references:
  - src/art/pipeline.py:503 (`_make_model`: `alter` añadido incondicionalmente)
  - src/art/pipeline.py:150 (`_write_inp`: rama freq=1 de la cabecera)
  - src/art/pipeline.py:34 (`_write_bare_inp`: segundo escritor, misma cabecera)
  - pyfug/graphics/combined.py:167 (`plot_combined`: `x_pad` sin definir si f==1)
  - TODO.md §Bugs conocidos (donde vivió este defecto un mes sin ficha)
  - BUG-0005 (el `alter` espurio cuando n_harmonics=0; este es su hermano anual)
---

## Summary

Cualquier serie de frecuencia anual (`freq=1`) se estima mal, se escribe mal y no
se puede diagnosticar. Son **tres defectos independientes que se dan a la vez**, y
como TODA serie anual es D=0 y pasa por `_make_model` / `_write_inp`, afectan por
igual al camino guiado (`confirm_and_estimate`) y al autónomo (`build_model`).

El motor `fue` estima bien: los tres fallos están en la capa ART y en pyfug.

**Se ficha el 12-ago-2026, un mes después de descubrirse**, porque vivía como
viñeta en `TODO.md` y no en el registro. Ese es su propio hallazgo: el defecto
que más usuarios potenciales excluye era el único sin ficha.

## Resolution (2026-08-12) — y el diagnóstico cambió al medirlo

**Los tres defectos que esta ficha nombra estaban ya arreglados.** Se comprobaron
uno a uno antes de tocar nada, y lo que bloqueaba las series anuales hoy era un
CUARTO que la ficha no menciona.

| defecto de la ficha | estado al medirlo |
|---|---|
| (1) `alter` = (−1)ᵗ espurio | **ya arreglado** — el guardia `if freq >= 2` del arreglo de BUG-0005 lo cubre también |
| (2) cabecera `.inp` en `_write_inp` | **ya arreglado** — escribe ` 248  1 1768 GE` |
| (2b) la misma cabecera en `_write_bare_inp` | **VIVO** — escribía ` 248 1768 1768 GE` |
| (3) `x_pad` en pyfug | **ya arreglado**, con el comentario que cita este TODO |
| **(4) `detect_seasonality` divide por cero** | **VIVO, y era el bloqueo real** |

### (4) El bloqueo real

`seasonal_detection.py:230`:

```python
num_harmonics = s - 1
...
f_stat = float(gamma @ np.linalg.inv(V_gamma) @ gamma) / num_harmonics
```

Para una serie anual `s = 1`, así que `num_harmonics = 0` y el F-test **divide
por cero**. No era un resultado degenerado: era una excepción lanzada antes de
que corriera ningún contraste, y se llevaba por delante el pipeline autónomo
entero — `run_full` → `describe_seasonality` → `ZeroDivisionError`, sin haber
estimado nada.

Arreglo: una serie anual **no tiene frecuencias estacionales**, así que el
contraste no falla, no aplica. Se devuelve pronto un resultado bien formado con
`seasonal_detected=False` y el mensaje que lo dice. Y es lo correcto aguas abajo:
`decide_seasonal_structure` lo lee como decisión **"A"** con `n_harmonics=0`, que
es lo que un modelo anual necesita. Verificado: `(D, decision, n_harmonics) ==
(0, "A", 0)`.

### (2b) Y el segundo escritor, que es la moraleja de la ficha

`_write_inp` ya escribía la cabecera bien; `_write_bare_inp` conservaba
`begtime = ts.start[1] if freq > 1 else begyear` con el comentario *"annual: year
repeated twice"*. **El arreglo no viajó de un escritor al otro** — que es
exactamente lo que esta ficha predijo al abrirse y el argumento para unificarlos.

Curiosidad medida: la cabecera mal escrita **no rompía el round-trip**, porque el
parser de fue la tolera en anual. Era latente, no visible: la peor clase.

### Estado tras el arreglo

```
pipeline OK: lam=1.0 d=0 D=0 p=0 q=2 mu=True n_harm=0 dec=A
  interventions: ninguna
  diagnosis OK, figura: sí
  formal_tests OK
anidados AR(p): {1: -2462.892, 2: -2441.978, 3: -2437.081} -> monótono
```

La última línea es el criterio que destapó el defecto (1) en su día: entre
modelos anidados logL no puede empeorar. Con el determinista espurio dentro daba
AR(14) peor que AR(7).

### Tests

`tests/test_bug_0018_annual_series.py`, 9 tests. Contra el código previo fallan
6; los 3 que pasan son los que cubren los defectos ya arreglados —guardias de
regresión para que no vuelvan—, y la cabecera va **parametrizada por escritor**
a propósito: `_write_inp` pasaba y `_write_bare_inp` no, que es el fallo de tener
dos.

### Lo que este caso enseña sobre el registro

La ficha se abrió el 12-ago describiendo lo que `TODO.md` decía desde el 8-jul.
En ese mes se arreglaron tres de sus cuatro defectos **sin que la anotación se
actualizara**, y el que quedaba nunca estuvo escrito. Un defecto que vive fuera
del registro no sólo no se prioriza: deja de ser cierto sin que nadie lo note.

## Impact

**Alto, y es el mayor excluyente de usuarios del paquete.** Series anuales son un
caso de uso entero — precipitación, PIB, cosechas, cualquier serie histórica larga
— y hoy no se puede completar ni un análisis. El defecto (3) además corta el flujo
justo después de estimar, así que el usuario ve el fallo con el modelo ya ajustado.

Efecto medido del defecto (1): un AR(14) anual con logL=−2202, **peor** que su
submodelo AR(7) con logL=−1058 — imposible entre modelos anidados salvo que el
ajuste no converja.

## Reproduction

Cualquier serie anual. Con la de precipitación de Ginebra (n=248, 1768–2015):

```python
build_model(inp_path="GE.inp", output_path="work/GE_v1.inp", max_rounds=1)
```

1. el modelo sale con un determinista `alter` que nadie pidió;
2. la cabecera del `.inp` dice `248  1768 1768 GE` en vez de `248  1 1768 GE`;
3. la diagnosis revienta con `UnboundLocalError: x_pad`.

## Root cause

Tres, independientes. **Asignados a paquete**, como en el registro de drtran.

### (1) Determinista `alter` = (−1)^t espurio — `art`, `pipeline.py:503`

En el bloque `D==0` de `_make_model`, la línea 497 pone correctamente
`max_pairs=0` para freq=1 (ningún par cos/sin), pero la 503 añade
**incondicionalmente** `fue.Intervention("alter", …)` — el armónico de Nyquist
f=s/2.

En una serie anual (s=1) **no hay Nyquist estacional**: `alter`=(−1)^t es una
oscilación bienal determinista libre que no debería existir. Absorbe señal de
periodo 2, distorsiona μ y el AR, y produce ajustes degenerados.

Es el hermano anual de BUG-0005, que era el mismo `alter` incondicional cuando
`n_harmonics=0`. Aquel se arregló para el caso no estacional y no para freq=1.

### (2) Cabecera `.inp` mal escrita — `art`, `pipeline.py:150`

En `_write_inp`, la rama `else` (freq=1) escribe

```python
f" {n}  {beg_year} {beg_year} {name}"
```

repitiendo el año en el campo del periodo inicial. Debe ser `f" {n}  1 {beg_year} {name}"`
(periodo inicial = 1 en anual, coherente con el `beg_period` de la línea 111).

**Y hay que arreglar los dos escritores a la vez:** `_write_bare_inp`
(`pipeline.py:34`) emite el mismo formato con la cabecera duplicada. Es el
segundo escritor de `.inp` que la revisión externa no vio y este defecto es la
demostración de por qué importa: un arreglo en uno no viaja al otro.

### (3) `UnboundLocalError: x_pad` — `pyfug`, `graphics/combined.py:167`

En `plot_combined`, `x_pad` solo se define dentro de `if f > 1:` (línea 146); para
`f == 1` se entra en el `else` (línea 155) sin definirla, y la 167
`ax_s.set_xlim(xs[0] - x_pad, …)` la usa → crash.

Bloquea `describe_diagnosis` y, por tanto, `estimate_and_diagnose` y
`confirm_and_estimate`, que la llaman tras estimar. **Está en pyfug, no en art ni
en fue**, y se registra aquí como se hizo con el arreglo de `nlags`: rompe ART y
ART es donde se ve.

## Fix

1. Envolver el bloque de deterministas estacionales de `_make_model`
   (líneas 500-503, o al menos el `append` de `alter`) en `if freq >= 2:`.
2. Sustituir `{beg_year} {beg_year}` por `1 {beg_year}` en `_write_inp`, **y
   revisar la misma cabecera en `_write_bare_inp`**. Mejor aún: unificar los dos
   escritores, que es tarea aparte ya anotada en TODO.
3. En pyfug, definir `x_pad` también en la rama `else` (p.ej. `x_pad = 0.3 / f`).

## Validation

- Estimar un ARMA anual y comprobar que `m.interventions` **no** contiene ningún
  `alter`, y que `logL(AR(p+k)) >= logL(AR(p))` entre anidados — el criterio que
  destapó (1).
- Round-trip write → load de una serie anual conserva `start` y `nobs`; cubre (2)
  **por los dos escritores**.
- Caso anual en `tests/test_golden_pipeline.py` que ejecute la diagnosis sin
  crash, hermano de `test_diagnosis_short_series_no_crash`; cubre (3).
- La revisión externa pide tests golden de más dominios y este es el primero: una
  serie anual entra en el fixture set.

## Workaround

Construir el `.inp` a mano (cabecera correcta, sin `alter`) y estimar vía
`model_equation_display` / `ar_factorization`, que reajustan internamente y no
invocan el gráfico que rompe.
