---
id: BUG-0089
title: FALENCIA (no defecto): la regla de Treadway es EXACTA antes de especificar el ARMA y conservadora después — lo que resulta ser una justificación medida del orden del protocolo, «lo más obvio primero»
status: wontfix
severity: low
component: interventions
found_in: 0.1.12
fixed_in:
reported: 2026-09-05
reporter: Claude, derivando el umbral de BUG-0087 a petición del analista
tags: [interventions, treadway, escalera, potencia, derivacion, metodo, limitacion]
references:
  - docs/DISENO-nodo-intervencion.md §2ter (la derivación, y el experimento)
  - src/art/interventions.py (check_intervention_fit — usa el residuo crudo)
  - src/art/escalera.py (escalera_de_ockham — YA estima los dos peldaños)
  - src/art/policy.py (THRESHOLDS["intervention_vecino"])
  - bugs/BUG-0089-repro/repro.py
  - BUG-0087 (el umbral, del que sale esto)
---

## Cómo hay que leer esto

*Reclasificado el 2026-09-05 tras dos observaciones del analista. La primera:
arreglarlo «podría llevar a sobre-intervenir». La segunda, que es la que le da
la vuelta al hallazgo:*

> «Lo interesante es que es una razón para intervenir **antes** de especificar el
> ARMA. Treadway utilizaba la regla de lo más obvio primero. […] Quizás quedaría
> como una falencia más que un bug.»

**No es un defecto: es una propiedad, y explica el orden del método.** El
diagnóstico del vecino es *exacto* —contraste al 5% con la potencia máxima
disponible— precisamente en el estado en el que el protocolo te pone cuando
haces las intervenciones primero, y se degrada si ya has ajustado el ARMA.

Lo que aquí se documenta, entonces, no es algo que arreglar sino **una
justificación estadística medida de la ordenación de la escuela**, que hasta
ahora se sostenía como convención. Y una nota de dónde se aplica el diagnóstico
fuera de esa ordenación.

## Summary

La regla de Treadway sale de la condición de primer orden —los residuos quedan
ortogonales a cada regresor filtrado de la intervención— y preguntar «¿queda masa
del suceso en el vecino?» es preguntar **si hace falta un ω más**. Eso es el
contraste de puntuación:

    LM = (Σ_t a_t·x_t^(k+1))² / (σ̂² Σ_t (x_t^(k+1))²)  ~  χ²(1)
    x_t^(j) = π(B)·[B^j/δ(B)]·ξ_t

**Sin ARMA el regresor filtrado es una ficticia** (π(B)=1): la suma colapsa en un
término, `LM = a²/σ̂² = z²`, y el residuo tipificado del vecino **es** el
contraste. Ahí `check_intervention_fit` hace exactamente lo correcto.

**Con ARMA el regresor es la forma del filtro π**, la suma no colapsa, y mirar un
solo residuo deja de ser el estadístico. Sigue siendo *un* estadístico —y su
umbral de 2.0 sigue siendo el suyo— pero es otro, con menos potencia.

## Impact

Medido, 200 réplicas: ruido con un suceso de DOS períodos en el nivel, se ajusta
UN ω, y se compara el veredicto del vecino con el LR contra el modelo de dos ω.

| sin ARMA | tamaño | potencia |
|---|---|---|
| `z > 2` | **5.0%** | **75.0%** |
| LR al 5% | 5.5% | 75.0% |

razón z²/LR: mediana **1.001** [p10 0.996, p90 1.012] — el mismo contraste.

| AR(1) φ=0.6 | tamaño | potencia |
|---|---|---|
| `z > 2` | 1.5% | **47.0%** |
| `z > 3` | 0.0% | 5.5% |
| LR al 5% | 4.5% | **77.5%** |

razón z²/LR: mediana **0.527** [p10 0.078, p90 9.834].

Es decir: con un AR(1) moderado, **una de cada tres formas que se quedan cortas
pasa por buena**. El caso con ARMA no es el excepcional: es el normal.

Y hay un agravante de oportunidad: **`escalera_de_ockham` ya estima el peldaño
de k ω y el de k+1**, así que el LR está calculado justo donde se toma la
decisión. No hace falta estimar nada nuevo — hace falta usarlo.

## Reproduction

`bugs/BUG-0089-repro/repro.py [K]` — simulación, K réplicas por celda (40 por
defecto, 200 en las cifras de arriba). Sale 1 mientras el vecino crudo pierda
más de 10 puntos de potencia frente al LR.

## Root cause

`InterventionFitCheck.vecino_anomalo` compara `|z|` del residuo contiguo contra
un umbral. Eso codifica el caso π(B)=1 —correcto y exacto ahí— como si fuera
general. El módulo lo tenía escrito y no lo usó: el docstring de §2ter ya decía
que «con ARMA es una combinación pequeña de los residuos siguientes», y la
combinación no se calcula.

## Lo que las cifras dicen del MÉTODO

Puestas en el orden del protocolo, las dos tablas de arriba dejan de ser «un
estadístico bueno y uno malo» y pasan a ser esto:

| cuándo se aplica el diagnóstico | el vecino crudo es | tamaño | potencia |
|---|---|---|---|
| **antes** del ARMA (p=q=0) | el contraste EXACTO | 5.0% | 75.0% |
| **después** del ARMA (AR(1) φ=0.6) | una aproximación conservadora | 1.5% | 47.0% |

Y art **ya hace lo primero**, en la ruta B1 de `guided_identification`:

```
a) confirm_and_estimate(m00: harmonics only, p=0, q=0)
b) preliminary_outlier_scan on m00 residuals
c) [cycle: add steps → re-estimate → scan] until clean
d) Call 4 with pre_path=<mNN.pre>   (ARMA on clean residuals)
```

El ARMA se especifica en el paso (d), **sobre residuos ya limpios de sucesos**.
Es decir: el orden que la escuela enuncia como «lo más obvio primero» coloca al
analista, sin que nadie lo buscara por esta razón, justo donde su propio
diagnóstico de intervención es exacto. Eso es un argumento a favor del orden que
no estaba escrito, y ahora está medido.

**Dónde NO se cumple, y hay que decirlo.** El orden sólo está garantizado en B1
(estacionalidad determinista). Las rutas B2 —D=1, estocástica— y «sin
estacionalidad» van directas a la llamada 4 con ARMA, así que ahí el diagnóstico
del vecino se aplica DESPUÉS y es el conservador. No es un fallo del
diagnóstico: es que el orden es otro, y conviene que la salida lo diga en vez de
presentar el mismo veredicto con la misma confianza en los dos casos.

## Por qué NO se «arregla» subiendo la potencia

*Objeción del analista, y es la que decide.*

**Más potencia no es automáticamente mejor aquí.** El vecino anómalo no es un
contraste cuyo único objetivo sea detectar: es una **puerta que autoriza añadir
parámetros**. Alimenta `razones_para_subir`, y subir de peldaño es añadir un ω.

Y la sobre-intervención es el modo de fallo que **no se detiene solo** —cada
intervención encoge σ̂, con lo que el siguiente residuo sube de |z| y pide su
turno—; es la razón de que la llamada 1 de `guided_intervention` exista y avise.
Pasar del 47% al 77.5% sería abrir esa puerta un tercio más, en todas las
intervenciones a la vez, y **justo en el tramo del flujo donde el protocolo ya
ha decidido no estar**.

Este reporte no puede decidirlo: mide la potencia contra la alternativa «falta un
ω», que es la pregunta estadística, no contra la pregunta del método, que es
«¿merece la pena otro parámetro?». BUG-0086 ya dejó dicho que la estadística
sola no arbitra la segunda.

## Lo que se hizo, y lo que no

**Se hizo** — publicar el p-valor del contraste junto al z:
`¿hace falta un ω más? p=0.0152 (χ²(1) sobre el peor vecino; umbral |z|>2 ⇔
p<0.0455)`. Quita la arbitrariedad de la cifra, vale en los dos casos y —lo que
importa aquí— **no cambia ningún veredicto**: es información, no una puerta más
abierta. Y cuando el modelo lleva ARMA, la salida dice que ese p es conservador.

**No se hace** — sustituir el estadístico:

- usar el LR en la escalera, que ya lo tiene estimado;
- calcular el LM exacto filtrando ξ por π(B).

Las dos suben la potencia, y eso es exactamente lo que aquí no se quiere.
Quedan escritas por si algún día la medición de abajo dice otra cosa.

## Qué haría falta para reabrirlo

**No** «que la potencia llegue al 77.5%». Ése era el criterio de la primera
versión de este reporte y medía el contraste, no la decisión.

Haría falta, sobre un corpus real con formas conocidas y no en simulación: que
el número de intervenciones **no aumente** salvo donde el analista habría puesto
una, y que la forma final coincida con el oráculo más veces que hoy. Mientras eso
no esté medido, esto se queda como **falencia documentada**, y `repro.py` sirve
para lo que sirve: dejar constancia de que los dos estadísticos difieren, cuánto,
y en qué punto del flujo importa.
