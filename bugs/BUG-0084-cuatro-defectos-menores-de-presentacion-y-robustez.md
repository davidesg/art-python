---
id: BUG-0084
title: Cuatro defectos menores de la sesión guiada — σ̂ ×100 en la figura de residuos, el R² de `intervention_plot` diluido por el ruido de la ventana, `confirm_and_estimate` no crea su directorio de salida, y la escalera dice que subió de peldaño mientras elige el más bajo
status: fixed
severity: low
component: describe/mcp-tools
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David / sesión guiada FOOD_UEM
tags: [presentation, calibration, robustness]
references:
  - src/art/pipeline.py:292 (_write_inp, el open sin mkdir)
  - src/art/interventions.py (intervention_plot, el R² de la ventana)
  - BUG-0033 (σ̂ₐ y el signo de porcentaje)
---

## 1 — σ̂ va ×100 en la figura de residuos, y no en la ecuación  (presentación)

Sobre el MISMO modelo, el mismo número sale con dos escalas:

| | m00 | m05_ep17b |
|---|---|---|
| ecuación | σ̂ₐ = **0.2284%** | σ̂ₐ = **0.2124%** |
| figura de residuos | σ̂_w = **22.84%** | σ̂_w = **21.24%** |
| `.out` | — | *Standard deviation: 0.212417* |

Factor 100 exacto. La ecuación es la correcta: la serie modelada es 100·log(índice),
así que 0.2124 en esas unidades ES 0.2124%. Y la figura de ∇ln del paso anterior
rotulaba `σ̂_w = 0.29%`, que también es correcto — comprobado sobre el dato, la
desviación típica de 100·∇log(FOOD) es **0.2897**. Es decir: dos figuras de la
misma sesión usan escalas distintas bajo el mismo rótulo, y la de residuos es la
que sobra ×100. Mismo par (número, signo de porcentaje) que BUG-0033, en la otra
dirección. El `σ_w̄` del mismo rótulo arrastra el error (1.45% donde debería ser
0.0145%).

## 2 — El R² de `intervention_plot` se diluye con el ruido de la ventana  (calibración)

La superposición separa amplitud (`escala`) de forma (`R²`), y eso es lo correcto.
Pero el R² se calcula sobre TODA la ventana (±10 observaciones), que contiene ~20
períodos de ruido ordinario ajenos al suceso. Ese ruido pone un techo al R² por
perfecto que sea el ajuste EN el incidente, y el veredicto binario («La FORMA no
encaja») se dispara con formas que sí encajan:

| hipótesis sobre el episodio 02/2017 | escala | R² | mayor resto | veredicto |
|---|---|---|---|---|
| 2 escalones, ganancia forzada a 0 (simétrica, INCORRECTA) | 0.690 | 0.606 | z=+1.90 | «no encaja» |
| 2 escalones, ganancia libre (CORRECTA) | **0.9996** | 0.638 | z=+1.90 | «no encaja» |

La forma correcta clava los dos picos —los restos en las dos fechas del suceso son
≈0— y el mayor resto que queda está SIETE meses después, sin relación. El R²
apenas distingue los dos casos (0.606 vs 0.638); la escala los separa
limpiamente (0.69 vs 1.00). Peor aún en 12/2004, donde el mayor resto (z=+2.65)
es **otro anómalo conocido** (03/2004) que cae dentro de la ventana: R²=0.452 con
escala 0.9974.

Sugerencia: calcular el R² sobre el SOPORTE de la hipótesis y sus vecinos
inmediatos, no sobre la ventana entera; o dejar el veredicto en manos del par
(escala, mayor resto), que es el que la propia herramienta describe como el que
separa las dos preguntas.

## 3 — `confirm_and_estimate` no crea su directorio de salida  (robustez)

`pipeline.py:292` abre `output_path` sin `mkdir -p`. Y la ruta que el propio nodo
guiado sugiere en su texto de «próximo paso» es `cases/<serie>/work/...`, un
directorio que no existe todavía. Primera llamada del ciclo:

```
FileNotFoundError: [Errno 2] No such file or directory:
'.../cases/UEM_FOOD/work/FOOD_UEM_m00.inp'
```

Una línea: `os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)`.

## 4 — La escalera dice que subió de peldaño mientras elige el más bajo  (mensaje)

Salida literal de `suggest_intervention_form(date="03/2017", form="auto")`:

```
- `1a` escalón en el nivel (permanente) · AIC -2001.27 · ... **◀ elegido**
- `1b` impulso en el nivel (transitorio) · AIC -1991.02 · ...
- `2`  episodio de 1 período(s) — 2 escalones · AIC -2001.12 · ...

Se subió de peldaño por:
  - **Inadecuación**: la lectura simple no deja ruido blanco (Q o JB rechazan).
```

Marca como elegido `1a`, que es el peldaño más bajo, y a continuación afirma que
subió de peldaño. O el mensaje describe una evaluación que no se aplicó, o la
elección no es la que dice. En cualquier caso el analista no puede saber cuál de
las dos cosas ocurrió.

---

## Fix (aplicado, 2026-09-04)

### §1 — σ̂ ×100 en la figura de residuos

El ×100 no estaba en art: `pyfug.graphics` rotula el pie de figura con
`{std*100:.2f}%`, y eso es correcto **si lo que recibe está en fracción**. Los
residuos de la suite no lo están —se estima sobre 100·log(y)— así que llegaban ya
en tanto por ciento y el ×100 los dejaba cien veces más grandes. Y la figura de
∇ln del paso anterior sí entregaba fracción: de ahí que las dos figuras de la
misma sesión usaran escalas distintas bajo el mismo rótulo.

Arreglado en art y no en `pyfug`, que es donde toca: la convención de `pyfug` es
«fracción», y quien la incumplía era la llamada. Nuevo
`describe._residuos_en_fraccion(model)`, aplicado en los dos sitios que pintan
residuos. **No cambia el dibujo**: `plot_combined` tipifica la serie antes de
pintarla, así que un factor constante sólo mueve el rótulo — que es justo lo que
estaba mal.

### §2 — el R² diluido por el ruido de la ventana

`Superposicion` gana `r2_soporte`, `z_resto_soporte` y `resto_max_en`, medidos
sobre el **soporte de la hipótesis más un vecino a cada lado**. El vecino no es
un margen de cortesía: es la regla de Treadway —lo que la forma no modeliza cae
entero ahí— así que tiene que entrar en la medida. `la_forma_explica` pasa a
leerse sobre el soporte.

Verificado sobre el caso del reporte, `12/2004×2` en FOOD_UEM:

| | reportado | ahora |
|---|---|---|
| escala | 0.9974 | 0.9970 |
| R² sobre la ventana | 0.452 | 0.419 |
| **R² sobre el soporte** | — | **0.898** |

El R² de la ventana **se sigue publicando**, etiquetado como lo que es: la
ventana está para mirarla. Y hay un aviso nuevo, `el_resto_grande_es_ajeno`, para
el caso que el reporte describe — el mayor resto de la ventana era **otro anómalo
conocido**, fuera del suceso. Cargárselo a la hipótesis que se prueba es un error
de atribución, y ahora la salida dice a cuántos períodos cae y que hay que mirarlo
aparte.

### §3 — el directorio de salida

`_write_inp` hace `os.makedirs(os.path.dirname(output_path), exist_ok=True)`. La
ruta que el propio nodo guiado sugiere en su «próximo paso» es
`cases/<serie>/work/…`, así que la PRIMERA llamada del ciclo reventaba sobre una
ruta que art acababa de proponer.

### §4 — la escalera decía que subió mientras elegía el más bajo

Ni el mensaje describía una evaluación que no se aplicó, ni la elección era otra:
lo que pasaba es un tercer caso que el texto no contemplaba. En
`escalera_de_ockham` hay tres ramas, y la tercera es *«había razones para subir y
el peldaño 2 tampoco se sostiene, así que se cae al bajo»*. El texto trataba esa
rama como si fuera la segunda.

Dos propiedades nuevas lo nombran —`Escalera.subio` y
`Escalera.ningun_peldano_se_sostiene`— y los dos textos (`describe_escalera` y
`_texto_escalera`) las usan:

> **Había razones para subir y aun así se recomienda `1a`, el peldaño bajo:**
>   - **Inadecuación**: la lectura simple no deja ruido blanco.
>
> El peldaño 2 tampoco se sostiene, así que **ninguna forma de esta escalera
> resuelve el suceso**. Lo recomendado es el menos malo. Antes de fijarlo, mira
> si el episodio está bien delimitado (`incident_configurations`) o si lo que
> queda no es un suceso sino estructura sin modelizar.

Que es el estado que el mensaje contradictorio ocultaba, y el que el analista
necesita saber.

## Validation

`tests/test_bug_0084_cuatro_menores.py`, 15 pruebas: tres para §1 —incluida la
que fija que dividir no cambia el dibujo—, cinco para §2, dos para §3 y cinco
para §4.
