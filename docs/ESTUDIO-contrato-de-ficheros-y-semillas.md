# Estudio crítico — el contrato de ficheros y el movimiento de semillas

2026-09-05. Encargado por el analista: *«hay contratos sobre cómo se mueven las
semillas en el grafo y cómo se convierten en `.inp` pero seguimos con problemas.
Haz un estudio crítico completo.»*

Todo lo que sigue está medido sobre el corpus real (FOOD_UEM en `/SRC/DVR` y la
réplica del run 5), no razonado.

---

## 1. El contrato declarado

    .inp(t−1)  →  .pre(t−1)  →  .inp(t)  →  .pre(t)

| fichero | qué es | para qué |
|---|---|---|
| `.inp` | una ESPECIFICACIÓN; sus valores son SEMILLAS | estimar y reestimar |
| `.out` | el registro de una estimación y su diagnosis | — |
| `.pre` | el `.inp` con las estimaciones como nuevos valores iniciales: un ÓPTIMO en forma reejecutable | modificar, para crear el `.inp` siguiente |

Con un invariante comprobable: **corre fue sobre un `.pre` y los números no se
mueven**. Y una regla: un `.pre` que se TOCA vuelve a ser un `.inp`.

---

## 2. La grieta: el invariante es sobre los VALORES, no sobre la CURVATURA

El invariante **se cumple**, y ahí está el problema. Medido sobre
`FOOD_UEM_m05_ep17b`:

| | ℓ | valores |
|---|---|---|
| estimado desde el `.inp` | 27.877243 | referencia |
| reestimado desde el `.pre` | 27.877243 | idénticos |

Pero las desviaciones típicas de los mismos 15 parámetros:

| | SE `.inp` | SE `.pre` | pre/inp |
|---|---|---|---|
| ω₀ | 0.049755 | 0.096436 | **1.938** |
| ω₁ | 0.022767 | 0.079061 | **3.473** |
| μ | 0.215293 | 0.108990 | **0.506** |

**Entre 0.46× y 3.47×, y en las dos direcciones.** No se puede ni firmar el
sesgo, así que no hay corrección posible ni forma de detectarlo mirando la
salida.

### El mecanismo, y por qué esto es arquitectura y no un descuido

La covarianza no es una propiedad del óptimo: es un **subproducto del CAMINO**
que recorre el optimizador. BFGS la acumula iteración a iteración. Arrancar ya
en el óptimo no acumula nada, así que la covarianza se queda en la semilla —
2/n, que es lo que BUG-0027 documentó.

De ahí la afirmación que ordena todo lo demás:

> **La curvatura no es recuperable de un fichero que sólo guarda el óptimo. El
> `.out` es la ÚNICA constancia fiel de las desviaciones típicas.**

Y el `.pre` es un fichero que **parece** que hace round-trip: mismos valores,
misma verosimilitud, misma ecuación. La corrupción es invisible por
construcción.

Verificado por el otro lado: las SE leídas de la matriz de covarianzas del
`.out` dan **out/inp = 1.000 en los 15 parámetros**. Exactas.

---

## 3. Lo que art hace BIEN, y que no hay que romper

**El patrón correcto está implementado**, en `confirm_and_estimate`:

```python
_write_inp(ts, m, output_path)      # escribe el .inp de ESTA versión
_, m = _load_fitted(output_path)    # y estima DESDE ÉL
```

Escribe el `.inp` y estima desde el fichero, no desde el modelo en memoria ni
desde el `.pre`. Por eso sus SE son correctas y por eso el `inp_path` que deja
en el guion resuelve. **Éste es el patrón de referencia.**

Y los dos escritores del formato coinciden: `art._write_inp` y `fue.write_pre`
escriben el mismo factor de reescala (verificado), y los 7 `.pre` del corpus
están todos a 100. La duplicación de escritores que BUG-0018 señaló no está
divergiendo hoy.

---

## 4. Las violaciones, medidas

### V1 — `_load_fitted` ajusta lo que le den, sin avisar

```python
def _load_fitted(path: str):
    """Load and fit a model from .pre or .inp file."""
```

El docstring **admite el `.pre` explícitamente**. No hay guarda, no hay aviso.

**17 herramientas** lo usan, y **14 acaban consumiendo la covarianza**:

    ar_factorization · compare_versions · confirm_and_estimate · formal_tests
    full_report · guided_identification · meg_frequency · meg_reformulate
    model_histogram · overparameterization_analysis · seasonal_param_analysis
    suggest_intervention_form · test_interventions · test_seasonal_simplification

Medido sobre `test_interventions`, cuya salida es *toda* razones t y un Wald:

```
FOOD_UEM_m06_flt17.inp    ω[0]=+0.5700  SE=0.1096  t=+5.200   Wald p=0.2679
FOOD_UEM_m06_flt17.pre    ω[0]=+0.5700  SE=0.0978  t=+5.825   Wald p=0.2600
```

Aquí el daño es del 12%; sobre `m05` el peor parámetro se va al **247%**. La
magnitud depende del modelo y del parámetro, lo que es **peor que un sesgo
constante**: no hay nada en la salida que lo delate.

Y el `.pre` está al lado del `.inp`, con el mismo nombre, a tres letras de
distancia. Yo mismo se lo pasé varias veces en esta sesión sin pensarlo.

### V2 — `get_out_report` no lee el `.out`

La única herramienta cuyo propósito declarado es devolver el registro de la
estimación **lo vuelve a fabricar**:

```python
ts, m = _load_ts_model(inp_path)
m.fit()                      # ← reestima
out_text = m.write_out()     # ← y genera el informe de nuevo
```

Y su docstring dice: *«inp_path : path to the .inp or **.pre** file»*. Es decir,
invita al camino equivocado en la herramienta donde más duele. Medido contra el
`.out` que está en el mismo directorio:

```
get_out_report(.inp)  vs el .out en disco  →  desviación   0.0%
get_out_report(.pre)  vs el .out en disco  →  desviación 247.3%
```

### V3 — art apunta al `.out` en sus propios avisos y no puede leerlo

`diagnosis.AVISO_COV_CASI_SEMILLA` le dice al analista:

> *«…conviene contrastarlos antes de apoyar una decisión en ellos: **el `.out`
> del modelo trae la covarianza completa**…»*

No existe ninguna herramienta que la lea. El aviso da una instrucción que la
herramienta no puede ejecutar, así que la ejecuta el LLM a mano — parseando
texto — o no se ejecuta.

### V4 — `estimate_and_diagnose` rompe la terna

Registra `inp_path=output_path` y **nunca escribe un `.inp` ahí**. Medido:

```
ficheros: ['S.inp', 'S_m00.out', 'S_m00.pre', 'FOOD_UEM_guion.json', 'figs']
guion.inp_path = S_m00.inp   ¿existe? False
hermanos: .pre=True  .out=True
```

Defecto mío, introducido ayer al cerrar BUG-0088: añadí el registro sin
comprobar que la ruta registrada resolviera.

### V5 — el guion apunta a ficheros que no existen

Sobre el corpus real: **4 de 15** entradas con `inp_path` apuntan a un fichero
ausente (ITCER m10, PGAS m10, PGAS m30, y el descartado). Parte es higiene de
sesión —modelos que se movieron— pero el guion no lo detecta ni lo dice, y es
justo el camino que el analista usa para volver atrás.

---

## 5. El patrón, que ya tiene dos apariciones

El §3 del documento de arquitectura del nodo de intervención lo llamó *«la
capacidad está en la capa de abajo; la superficie no tiene puerta»*. Lo de aquí
es su variante gemela, la que apareció al arreglar aquéllos:

> **Un dato que la capa de abajo conoce no llega arriba.**

Aquí el dato es **de qué fichero vengo**, y ningún tipo lo lleva: una ruta es un
`str`, y `.inp`, `.pre` y `.out` sólo se distinguen por tres letras que nadie
mira. El contrato es una convención de nombres sostenida por la disciplina del
que llama — y con 17 puntos de entrada, la disciplina no escala.

Es el mismo mecanismo que produjo BUG-0085 (el factor de reescala que se perdía
al clonar) y BUG-0079 (el orden de la FLT que no subía a la superficie).

---

## 6. Lo que se propone

### A — la guarda que responde su propia pregunta *(barato, ya)*

`_load_fitted` mira la extensión. Si es `.pre`, avisa **y dice si afecta a la
tarea**: para residuos y figuras no —dependen de los valores, que son exactos—;
para cualquier tabla de parámetros sí. Que el aviso traiga la respuesta es lo
que evita que el LLM gaste tokens averiguando si le concierne, que es
literalmente el coste que motivó este estudio.

### B — separar las dos operaciones *(estructural, después)*

Hoy `_load_fitted` significa dos cosas: «estima esto» y «déjame mirar esto». Son
contratos distintos:

- `estimar(inp)` — exige `.inp`, promete SE válidas;
- `mirar(inp|pre)` — acepta ambos, no promete SE.

Las 17 herramientas se reparten según lo que consuman: las 14 que tocan
covarianza van a la primera; `generate_forecast`, `intervention_analysis` y
`record_version` a la segunda. Toca muchos sitios, así que conviene hacerlo con
el contrato ya explícito y con A puesta.

### C — que el `.out` se pueda leer *(la pieza que falta)*

Un lector del `.out` (`art.outfile`) que devuelva parámetros, covarianza y
diagnosis. Con eso, de golpe:

- `get_out_report` **lee** el fichero en vez de fabricarlo;
- la ecuación con SE se rinde **sin estimar nada** (out/inp = 1.000, verificado);
- el aviso de V3 pasa a ser ejecutable;
- y la herramienta de evidencia que el analista pidió —volver a un nodo del
  guion y ver el último modelo con su diagnosis— **no necesita reestimar**.

### D — el `.out` merece su campo en el guion

Hoy el guion guarda `inp_path` y deriva los hermanos por nombre. Si el `.out` es
la única constancia fiel de la curvatura, es un artefacto de primera clase y no
un derivado: `out_path`, como `figure_path`. Y con una comprobación de que
resuelve, que es lo que V5 echa en falta.

---

## 7. Orden propuesto, y en qué quedó

| # | trabajo | bug | estado |
|---|---|---|---|
| 1 | **A** — la guarda de `_load_fitted` | BUG-0090 | **hecho** |
| 2 | **V4** — la terna rota de `estimate_and_diagnose` | BUG-0092 | **hecho** |
| 3 | **C** — el lector del `.out` | BUG-0091 | **hecho** |
| 4 | **D** — `out_path` en el guion | — | **hecho** |
| 5 | **B** — la separación de contratos | — | **hecho** |

### Lo que se aprendió por el camino

**El punto 1 destapó algo peor que el bug reportado.** `test_intervention` YA
detectaba la covarianza degenerada y levantaba un error cuyo mensaje nombra esta
situación exacta —«la estimación arrancó ya en el óptimo, que es lo que un `.pre`
es por diseño»— y `simplify_interventions` lo capturaba tres líneas más allá con
un `except Exception: pass`. Sobre un modelo estimado desde un `.pre`,
`test_interventions` respondía **«No hay intervenciones no-estructurales en el
modelo»** teniendo una delante. art sabía lo que pasaba y lo tiraba a la basura.

Es la tercera aparición en esta sesión de la misma lección: *una guarda que calla
convierte un fallo en una ausencia, y una ausencia se lee como «no hay nada que
ver»*.

**El punto 2 tenía una trampa en el arreglo.** Completar la terna significa dejar
un `.inp` junto al `.pre` y al `.out`, y la tentación es reserializar el modelo
que se acaba de ajustar. Eso escribiría las estimaciones donde van las semillas
—la trampa de BUG-0027 dentro de un `.inp`— y la siguiente estimación arrancaría
en el óptimo. Se copia el fichero **byte a byte**, y hay una prueba que comprueba
que reestimar la copia no dispara el aviso de BUG-0090.

**El punto 3 dio más de lo esperado.** El `.out` resultó llevar cada parámetro ya
como `valor (SE) [índice]`, así que las desviaciones típicas ni hay que
derivarlas de la covarianza. Se leen las dos y se comprueba que cuadran: si las
dos vías del mismo fichero no coinciden, una está mal leída — y esa comprobación
cruzada cazó un fallo del propio lector (`sigma2` devolvía 2.0, el dígito de la
etiqueta).

**El punto 4 confirmó V5 sobre el corpus.** Con el aviso puesto, el mapa del run
5 señala solo: *«Nodos sin su `.inp`: v3, v7 — desde ellos no se puede
reestimar»*. Son `PGAS m10` y `m30`. Y distingue dos gravedades, que no son la
misma: sin `.out` se puede reestimar desde el `.inp`; sin `.inp` el nodo es
irrecuperable.

### El punto 5: el contrato, declarado en el sitio que llama

`_load_fitted` significaba dos cosas —«estima esto» y «déjame mirar esto»— y con
el `.out` legible aparecieron tres:

| operación | acepta | promete | herramientas |
|---|---|---|---|
| `pipeline.estimar(inp)` | `.inp` (avisa con `.pre`) | desviaciones típicas válidas | 14 |
| `pipeline.mirar(inp\|pre)` | los dos, **sin avisar** | sólo los valores | 3 |
| `outfile.lee_out(out)` | el `.out` | el registro, sin tocar el motor | — |

Que sean tres no es ceremonia: hace que **el sitio que llama declare lo que
necesita**. Y de ahí sale el beneficio concreto, que es el que motivó todo esto:

> **`mirar` no avisa.** No promete nada que un `.pre` estropee —lo que se va a
> mirar depende de los VALORES, y en un `.pre` los valores son exactos— así que
> avisar ahí sería ruido. Y el ruido cuesta tokens: el LLM tiene que parar a
> averiguar si el aviso le concierne.

Verificado de extremo a extremo por la superficie MCP: `intervention_analysis`
sobre un `.pre` emite **0** avisos, `test_interventions` emite **1**.

Las tres que sólo miran —`generate_forecast`, `intervention_analysis`,
`record_version`— se comprobaron una a una: ninguna toca `std_errors`,
`cov_matrix`, `omega_se` ni la ecuación. Y hay una prueba que lo **mantiene**: si
alguna empieza a imprimir un error típico, falla y le toca cambiar de lado.

`_load_fitted` se conserva como alias de `estimar`: lo usan 17 herramientas y
renombrarlas todas de golpe mezclaría dos cambios en un commit. El contrato ya
está declarado en los nombres nuevos.

### Lo que queda abierto

**La portabilidad de las rutas.** `inp_path` y `out_path` son absolutos, así que
mover un directorio de casos rompe el guion — y parte de las 4 entradas rotas del
corpus vienen de ahí. Relativizarlas al guion (como `figure_path`) lo arreglaría,
pero afecta a los guiones ya escritos y merece su propia decisión.

**Las 14 herramientas siguen llamándose por el nombre histórico.** Migrarlas a
`estimar` es mecánico y sin riesgo, pero es un commit aparte.

---

## 8. Continuación

Este estudio se cerró el 2026-09-05 con los cinco puntos hechos. La revisión
previa a la etiqueta —`docs/REVISION-antes-de-0.2.0.md`— lo continúa un piso más
arriba y encuentra el mismo patrón en la superficie: **23 de las 46 herramientas
no aparecían en `_INSTRUCTIONS`**, incluidas las dos que esta sesión añadió.

Es la misma frase, con el sujeto cambiado: aquí *un dato que la capa de abajo
conoce no llega arriba*; allí *una herramienta que existe no se nombra donde el
agente mira*. Conviene leer los dos documentos seguidos.
