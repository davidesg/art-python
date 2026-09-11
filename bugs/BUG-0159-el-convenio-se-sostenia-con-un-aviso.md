---
id: BUG-0159
title: «Nunca se estima desde un `.pre`» se sostenía con un aviso y un alias que escondía la operación — por eso siguió dando problemas
status: fixed
severity: high
component: pipeline
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David
tags:
  - contrato-de-ficheros
  - covarianza
references:
  - BUG-0027
  - BUG-0090
  - BUG-0091
  - BUG-0158
---

## Summary

El convenio de ficheros está bien pensado y bien escrito. `pipeline.py` dedica
treinta líneas a explicarlo, distingue tres operaciones —`estimar`, `mirar`,
`lee_out`— y razona por qué son tres. Y **siguió dando problemas desde el
principio**, en palabras del analista.

La razón está en dos líneas del propio módulo:

```python
# estimar():
#   «Esta función **no lo prohíbe** … pero sella el modelo con `_art_origen`»
_load_fitted = estimar
```

**Un aviso no es una regla, y un alias que esconde la operación la deshace.**

1. `estimar()` aceptaba `.pre` y emitía un `RuntimeWarning`. Ningún carril lee
   los warnings de Python: no llegan al analista ni al modelo.
2. Y era alcanzable como **`_load_fitted`**, un nombre que se lee como «carga el
   modelo ajustado» —inofensivo, descriptivo, falso—. **Veinte herramientas de
   `mcp_server` la llamaban así**, y con ese nombre la regla dependía de que
   quien escribiera una herramienta nueva supiera que detrás había una
   estimación.

De las veinte, **tres sólo miraban** —`intervention_ladder`, `model_histogram`,
`compare_versions`— y estaban estimando sin necesitarlo.

## Impact

Estimar desde un `.pre` arranca EN el óptimo: el BFGS no tiene adónde ir, apenas
itera, y la covarianza se queda en la semilla. **Los valores salen exactos y las
desviaciones típicas no**, así que el fallo es invisible — el fichero parece
hacer round-trip.

Medido sobre `FOOD_UEM_2025_b01_ukr_n5`, el mismo modelo por las dos vías:

    .out  (estimación real, 34 iteraciones)   SE = 0,2315  0,2405  0,2430
    reajuste desde el fichero (12 iter.)      SE = 0,0835  0,0835  0,0840

Factor 2,8. Y no es hipotético: en el estudio de campo del nodo de intervención
esos SE **invirtieron el veredicto de significación** de dos ω del episodio de
Ucrania —t = −1,65 / −1,49 frente a −4,51 / −3,96— y llevaron a la conclusión
contraria sobre si el modelo adoptado cumplía la regla «no añadas un parámetro
que no sea significativo».

## Fix

**1 · `estimar()` RECHAZA un `.pre`**, con un mensaje que nombra el `.inp`
hermano si está al lado. El convenio dice que nunca se estima desde un `.pre`;
la función que estima tiene que negarse. Lo que el `.pre` sí permite —y queda
dicho— es **mirar** (residuos, figuras, diagnosis, previsión: todo depende de
los valores, que son exactos) y **saltar a `drtran` o `drvec`**.

**2 · Las tres que sólo miran pasan a `mirar()`.** `intervention_ladder` y
`model_histogram` directamente; `compare_versions` además lee ℓ, AIC y BIC del
`.out` (BUG-0158).

**3 · El alias se conserva** para no romper llamadores externos, pero hereda el
rechazo, y queda un comentario diciendo por qué el nombre era el problema.

**4 · La negativa se presenta como una regla, no como una avería.** El rechazo
es un `ErrorDeContrato` propio, y `_err` lo reconoce y enseña sólo el mensaje:

    ⛔ **No se puede hacer eso con este fichero.**

    No se estima desde un `.pre` (RC.pre). … Estima desde `RC.inp`. Si sólo vas
    a mirar residuos, figuras o diagnosis, usa `mirar()`; y si lo que quieres
    son las SE del modelo tal como se estimó, léelas del `.out`.

Sin esto la negativa llegaba al analista como un *traceback*, y un traceback se
lee como «el programa está roto», no como «eso no se hace así». Una regla que se
presenta como avería invita a buscarle la vuelta.

**5 · `meg_reformulate` y `meg_frequency` pasan a `mirar()`.** Las encontró la
propia negativa, al romper sus pruebas. Las dos reciben un `base_pre_path` —un
`.pre` **por diseño**: es el convenio de encadenar, y el nombre del parámetro lo
dice— y de ese modelo sólo toman la estructura y la serie. Los errores típicos
que imprimen son los del modelo reformulado, o los de los dos modelos del LR,
que se estiman aparte y desde su propio `.inp`. Estaban estimando el baseline
sin necesitarlo, en el sitio exacto donde el convenio manda pasar un `.pre`.

## Lo que esto enseña, y excede al defecto

Es la tercera vez que esta familia aparece —BUG-0027, BUG-0090, BUG-0091— y las
tres veces el arreglo fue **decirlo mejor**: un aviso más claro, un sello en el
modelo, un mensaje en la herramienta que imprime la SE. La doctrina mejoró y el
defecto siguió.

**Una propiedad que sólo se sostiene si todo el mundo se acuerda no es una
propiedad del sistema: es una costumbre.** Lo que la convierte en propiedad es
que la operación prohibida no exista, o que falle ruidosamente al intentarla.

## Validation

`estimar()` sobre un `.pre` levanta `ErrorDeContrato` nombrando el `.inp`
hermano y las dos salidas (`mirar()` y el `.out`); `mirar()` sobre el mismo
fichero funciona y da los mismos valores que estimar el `.inp`. Por la
superficie MCP la negativa llega sin traceback, y la herramienta que sólo mira
sigue aceptando el `.pre`.

**El censo del arreglo.** La negativa rompió **15 pruebas en 4 ficheros** — el
tamaño real de la costumbre. De ellas:

* **5** en `test_contrato_de_ficheros.py`, el fichero que *enuncia* la doctrina:
  afirmaban «estimar avisa». Ahora afirman «estimar se niega», y se añaden dos
  que el aviso no podía tener: que el rechazo **dice por dónde salir**, y que
  negar el `.pre` a quien estima **no lo cierra a quien sólo mira**.
* **8** alimentaban una herramienta que estima con un `.pre` del corpus. Todas
  tenían el `.inp` hermano al lado: el convenio era satisfacible y nadie lo
  estaba usando. Una de ellas —`test_estimate_and_diagnose_no_persist_by_default`—
  **seguía en verde con el fichero rechazado**, porque comprobaba la ausencia de
  la palabra «Guardado» y el texto de la negativa tampoco la lleva.
* **2** destaparon el defecto real de los dos MEG (punto 5 del arreglo).

Ese reparto es la medida de lo que valía el aviso: de los 15 sitios que
dependían del permiso, **ninguno** lo necesitaba.
