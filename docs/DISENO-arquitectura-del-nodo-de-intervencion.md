# El nodo de intervención — revisión de arquitectura

2026-09-04. Escrito tras la sesión guiada sobre FOOD_UEM y las dos de la réplica
(PGAS, ITCER), y a partir de los seis defectos BUG-0079…0084.

El diagnóstico del analista fue: *«el nodo de intervenciones no está
funcionando; además hay muchas herramientas que no están expuestas o
correctamente cableadas»*. Lo que sigue mide esa afirmación.

---

## 1. Lo que hay, contado

44 herramientas MCP. Repartidas por nodo:

| nodo | nº | entrada secuenciada |
|---|---|---|
| datos | 5 | — |
| identificación | 6 | **`guided_identification`** ✓ |
| estimación | 6 | `confirm_and_estimate` |
| **INTERVENCIÓN** | **9** | **ninguna** |
| contrastes formales | 7 | `formal_tests` |
| guion | 5 | — |
| informes | 5 | — |

**Al nodo de intervención no le faltan herramientas: le sobra dispersión.** Es
el nodo con MÁS instrumentos de toda la suite y el único sin puerta de entrada.

---

## 2. El defecto, en tres hechos medidos

### 2.1 Ninguna de las nueve remite a otra

Se buscaron referencias cruzadas —`\`otra_herramienta(\`` en el docstring— entre
las nueve. **Cero.** Un analista que llame a `residual_episodes` no tiene forma
de saber que `incident_configurations` existe, ni cuál manda.

Compárese con identificación, donde `guided_identification` documenta la
secuencia entera («Call 1 … Call 4») y las demás se declaran *«support tool,
standalone use only»*.

### 2.2 Tres herramientas contestan «¿qué forma?» y dan respuestas distintas

| herramienta | qué propone |
|---|---|
| `residual_episodes` | L+1 escalones desde el primer EXTREMO |
| `incident_configurations` | el conjunto acotado por el mecanismo, y a veces se niega a elegir |
| `intervention_ladder` | los peldaños de Ockham, con sus razones |

Medido sobre ITCER, el mismo suceso:

- `residual_episodes` → **3 escalones desde Q4/2008**
- `incident_configurations` → **5 escalones desde Q2/2008** (y la anterior queda
  a 6,15 puntos de AIC, la peor de las tres que enumera)

Las dos son correctas *dentro de su criterio*, y **nada dice cuál gobierna**. La
primera sólo agrupa extremos, que es BUG-0083 y P5. La segunda extiende por el
mecanismo. El analista recibe dos respuestas y ningún árbitro.

Y hay un cuarto solapamiento en el escaneo: `intervention_analysis`,
`residual_outlier_scan` y `preliminary_outlier_scan` contestan casi lo mismo con
tres nombres.

### 2.3 El paso que cierra el nodo NO EXISTE

Ésta es la razón literal de que el nodo «no funcione». La secuencia completa es:

| | paso | herramienta | estado |
|---|---|---|---|
| 1 | ¿distorsiona la identificación? | `residual_outlier_scan` | ✓ |
| 2 | ¿es un suceso o son varios? | `residual_episodes` | ✓ |
| 3 | ¿qué configuraciones admite el dato? | `incident_configurations` | ✓ |
| 4 | ¿qué justifica subir de peldaño? | `intervention_ladder` | ✓ |
| 5 | ¿encaja la forma con lo observado? | `intervention_plot` | ✓ |
| 6 | **construir la forma identificada** | **—** | **✗ BUG-0079** |
| 7 | ¿funcionó? (Treadway + ganancia) | `test_interventions` | ✓ |

Seis de siete pasos instrumentados, y **el que aplica la conclusión no está**.
`suggest_intervention_form` sólo acepta `form ∈ {pulse, step, ramp, auto}`,
ninguna con orden, y `confirm_and_estimate` no tiene parámetros de intervención.

La capa de abajo está entera: `_make_model` acepta `(at, form, n_omega)`,
`_write_inp` escribe el orden y los coeficientes, `fue` lo estima. **Es cableado
que falta, no capacidad que falte.**

---

## 3. El patrón, que se repite fuera del nodo

BUG-0080 es el mismo defecto en otro sitio: `policy.decide_domain` declara que
su inferencia es una sugerencia y que *«lo declarado gana siempre»*, y `domain=`
sólo existe en `build_model`. Recorriendo los nodos uno a uno no hay forma de
declararlo — y sobre FOOD_UEM eso produjo *«Recomendación: identidad (λ=1)»*
sobre un índice de precios.

Es literalmente el problema que `objetivo` tuvo y que se arregló, en la misma
función y para el parámetro de al lado.

> **La capacidad está en la capa de abajo; la superficie no tiene puerta.**

Tres instancias medidas: la FLT (0079), el dominio (0080), y los nodos de
decisión que el carril guiado por MCP no registra en el guion salvo que el
operador llame a `guion_node` aparte.

---

## 4. Lo que se propone

### 4.1 `guided_intervention` — la puerta que falta

Paralela a `guided_identification`: **una entrada, la secuencia documentada, y
un solo veredicto por llamada**. Sustituye a la elección a ciegas entre nueve
instrumentos.

```
Llamada 1  (sin fecha)      → calibración: ¿cambia la identificación?
                              Si NO cambia, lo dice y AVISA de que intervenir
                              aquí es sobre-intervenir. FIN si el analista para.
Llamada 2  (fecha)          → episodio + configuraciones admitidas + la escalera,
                              en UNA respuesta y con UN veredicto. Si el dato no
                              identifica, lo dice y pide lo extramuestral.
Llamada 3  (forma elegida)  → CONSTRUYE, estima, verifica Treadway y ganancia,
                              y deja el nodo en el guion con sus alternativas.
```

La llamada 3 es la que hoy no existe, y es la que cierra el nodo.

### 4.2 El árbitro entre los instrumentos que solapan

`incident_configurations` gobierna sobre `residual_episodes` para la FORMA:
extiende por mecanismo y el otro sólo agrupa extremos. `residual_episodes` pasa
a ser lo que su nombre dice —agrupar— y deja de sugerir forma.

`intervention_analysis` y `preliminary_outlier_scan` se declaran de uso
independiente, como las de identificación, o se retiran.

### 4.3 `domain` en el carril guiado

Un parámetro más en `guided_identification` y en `confirm_and_estimate`, igual
que `objetivo`.

---

## 5. Lo que NO se propone, y por qué

**No unificar las nueve en una.** Los instrumentos sueltos valen para mirar algo
concreto sin avanzar el flujo, que es como se usan en la práctica. Lo que falta
es la puerta, no la fusión.

**No que la puerta decida.** `guided_intervention` secuencia y presenta; el
analista decide en cada llamada. Es lo que hace `guided_identification` y es la
línea que separa evidencia de juicio en toda la arquitectura.

---

## 6. Orden de trabajo propuesto

1. **BUG-0079** — la construcción de la FLT. Desbloquea el nodo entero y es el
   único que impide terminarlo.
2. **BUG-0083** — la marcha hacia delante del incidente. Sin ella, la mitad de
   los sucesos se enumeran truncados.
3. **`guided_intervention`** — la puerta, una vez que hay algo que cerrar.
4. **BUG-0080** — `domain` en el carril guiado.
5. **BUG-0081 y 0082** — los dos arreglos míos que no arreglaron.
6. **BUG-0084** — los cuatro menores, incluido el mensaje contradictorio de la
   escalera (P4, abierto desde el 2 de septiembre).

---

# Estado de la ejecución

2026-09-04, mismo día. Los seis primeros puntos del §6 hechos o en curso.

| # | trabajo | estado |
|---|---|---|
| 1 | BUG-0079 — construir la FLT | **hecho** |
| 2 | BUG-0083 — la marcha hacia delante | **hecho** |
| — | BUG-0085 — el factor de reescala (nuevo, intercalado) | **hecho** |
| — | BUG-0086 — la escalera arbitraba por AIC (nuevo, intercalado) | **hecho** |
| 3 | `guided_intervention` — la puerta | **hecho** |
| 4 | BUG-0080 — `domain` en el carril guiado | parcial |
| 5 | BUG-0081 y 0082 | pendiente |
| 6 | BUG-0084 | pendiente |

## §4.1 — la puerta, tal como quedó

`guided_intervention(inp_path, date, form, n_omega, output_path, …)`. El
enrutado de llamada sale de qué se ha rellenado, no de un parámetro de modo:

| | condición | qué hace |
|---|---|---|
| **1** | `date=""` | calibra el correlograma omitiendo los anómalos, dice si la identificación cambia, y si NO cambia avisa de que intervenir aquí es sobre-intervenir. Devuelve las fechas candidatas. |
| **2** | `date` sin `form` | episodio + configuraciones + escalera **en una respuesta**, con un veredicto y el árbitro dicho. Si el dato no identifica, lo dice y pide lo extramuestral. |
| **3** | `date` y `form` | construye, estima y verifica Treadway y la ganancia. Deja el nodo en el guion. |

**El analista habla en FECHAS de principio a fin.** Los dos espacios de índices
—serie y residuos, separados por `d + D·s`— se quedan dentro de la herramienta.
Ése era el mecanismo de BUG-0067, y exponerlo al analista es pedirle que lleve
la cuenta de una conversión que la herramienta ya sabe hacer.

Lo que la puerta **no** hace, y es deliberado (§5): no decide. Presenta y espera,
como `guided_identification`. Cada llamada termina en una decisión del analista.

## §2.1 — las referencias cruzadas

Se midieron cero entre las nueve del nodo. Las ocho herramientas sueltas llevan
ahora, en la primera línea de su docstring, la misma nota: qué son —un
instrumento suelto—, cuál es la secuencia completa, y que la lleva
`guided_intervention`. Hay un test que lo fija, para que una herramienta nueva
del nodo no vuelva a nacer huérfana.

## §4.2 — el árbitro

Resuelto en dos sitios y con el mismo criterio: **para la FORMA gobierna
`incident_configurations`**, que extiende el arranque por el mecanismo, sobre
`residual_episodes`, que sólo agrupa extremos. Está cableado en la ruta `auto` de
`suggest_intervention_form` (BUG-0079) y en la llamada 2 de la puerta, y dicho
en el veredicto para que el analista sepa cuál mandó.

## Lo que se aprendió arreglándolo

**El §2.3 se quedaba corto.** Decía que faltaba el paso 6 —construir la forma
identificada— y era cierto, pero al cablearlo aparecieron tres defectos más en
el mismo camino, y ninguno era una carencia de capacidad:

- la marcha del incidente sólo iba hacia atrás, así que la mitad de los sucesos
  se enumeraban truncados (BUG-0083);
- el clonador de modelos perdía el factor de reescala, así que la tabla de
  configuraciones se imprimía 1994 puntos de AIC por debajo del modelo del que
  salía (BUG-0085);
- y la escalera elegía entre las dos lecturas escalares por AIC, que es
  exactamente lo que su propio docstring prohíbe (BUG-0086).

Los tres son la misma forma de fallo que el §3 ya nombraba: **la capacidad está
abajo y la superficie miente sobre ella** — aquí no por falta de puerta, sino
porque un dato que la capa de abajo sabe (el orden, el final del episodio, la
escala, la no-comparabilidad de dos formas) no llegaba arriba. Merece nombre
propio en la próxima revisión.
