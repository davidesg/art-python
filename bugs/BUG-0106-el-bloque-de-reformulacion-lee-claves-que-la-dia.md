---
id: BUG-0106
title: El bloque de REFORMULACION lee claves que la diagnosis no escribe (q_pass/jb_pass frente a white_noise/normal): nunca ve fallar la Q ni el JB, y dice 'el modelo se sostiene' sobre un REVISAR
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.0.dev0
fixed_in: 0.2.0.dev0
reported: 2026-09-06
reporter: David / sesión UEM_HCPI_0219 — m10, reformulación MEG en f=4
tags:
  - diagnosis
  - claves
  - contradiccion
  - meg_reformulate
references:
  - src/art/describe.py:1967-1968 (la diagnosis publica "white_noise" y "normal")
  - src/art/mcp_server.py:1050-1052 (_reformulacion_desde lee "q_pass" y "jb_pass": no existen)
  - src/art/mcp_server.py:1077-1081 (_conclusiones_desde lee las claves BUENAS, de ahí la discrepancia)
  - bugs/BUG-0105-... (el otro extremo del mismo desorden: n_extreme sí entra, y no debería)
  - bugs/BUG-0042-... (el pie de estado era un TERCER predicado de adecuación)
  - bugs/BUG-0106-repro/repro.py
---

## Summary

`_reformulacion_desde` —el bloque que le dice al analista si hay que seguir
iterando— consulta las claves `q_pass` y `jb_pass`. La diagnosis publica su
dict con las claves **`white_noise` y `normal`** (`describe.py:1967-1968`).
`d.get("q_pass")` devuelve `None`, `None is False` es `False`, y la rama de
fallo **no se ejecuta nunca**.

El bloque es por tanto **ciego a los dos contrastes que deciden la adecuación**.
Lo único que sí puede ver es `n_extreme`, que es la única clave que existe en
ambos sitios — y que, según BUG-0105, es justamente la que no debería estar ahí.
Entre los dos defectos, el bloque acaba reaccionando al único criterio
equivocado e ignorando los dos correctos.

En UEM_HCPI m10 (reformulación MEG en f=4), el informe dice:

    - Veredicto: **REVISAR ✗**
    - Ruido blanco (Q): ✓  OK
    - Normalidad (JB): ✗  JB=6.258, p=0.0438
    ...
    ## 4 · REFORMULACIÓN
    **No procede reformular:** el modelo se sostiene y nada en la diagnosis
    pide cambiarlo. Si se continúa, es por una razón que no está en estos datos.

Diez líneas entre «REVISAR ✗ / JB rechaza» y «el modelo se sostiene y nada pide
cambiarlo».

## Impact

Alto, y en la dirección peor de las dos posibles: **manda parar cuando hay que
seguir**. BUG-0105 hace que un modelo bueno parezca malo, lo cual cuesta una
iteración de más; esto hace que un modelo malo parezca bueno, y lo que cuesta
es adoptarlo.

La frase que emite no es neutra —«Si se continúa, es por una razón que no está
en estos datos»— y desautoriza explícitamente al analista que quiera seguir
mirando. En m10 el JB rechazaba **sin anómalos que lo explicaran** (asimetría
−0.13, curtosis +0.80), que es precisamente el síntoma que BUG-0043 identificó
como señal de λ o de un episodio sin modelar, no de intervenciones. El bloque
que debía encaminar ahí dijo que no había nada que hacer.

Afecta a toda salida que use este bloque, `meg_reformulate` incluido, es decir
la rama que el MEG existe para documentar.

## Reproduction

    cd art-python && python3 bugs/BUG-0106-repro/repro.py

    == Q=True, JB=False, sin anomalos  ->  reformulacion dice:
       '(vacio: no reporta ningun fallo)'
    == Q=False, JB=False, sin anomalos  ->  reformulacion dice:
       '(vacio: no reporta ningun fallo)'
    == CONTROL con las claves q_pass/jb_pass  ->  reformulacion dice:
       '**El modelo no se sostiene:** la Q rechaza el ruido blanco; el
        Jarque-Bera rechaza la normalidad. La iteración continúa.'

El control es la prueba de que **el defecto es el nombre de la clave, no la
lógica**: con `q_pass`/`jb_pass` la función hace exactamente lo que debe.

Caso real: `cases/UEM_HCPI_0219/work/UEM_HCPI_0219_m10_meg4.inp`.

## Root cause

Dos vocabularios para el mismo dato, sin un tipo que los reconcilie.
`_conclusiones_desde` (1077-1081) usa `white_noise`/`normal`;
`_reformulacion_desde` (1050-1052) usa `q_pass`/`jb_pass`. Ambos nombres
existen en el proyecto —`e.stats.q_pass` es real en las entradas del guion
(5485-5486)—, así que la confusión es entre el vocabulario del **guion** y el
de la **diagnosis**, que coinciden en `n_extreme` y divergen en el resto. Nada
falla ruidosamente porque `dict.get` devuelve `None` en silencio.

## Fix

1. Leer `white_noise`/`normal` en `_reformulacion_desde`, que son las claves
   que la diagnosis escribe. Un cambio de dos líneas.
2. Y para que no vuelva: que el dict de diagnosis sea un tipo con campos
   —dataclass o `TypedDict`— en vez de un `dict[str, Any]` consultado con
   `.get`, de modo que un nombre equivocado sea un error y no un `None`. Los
   tres predicados de adecuación (cabecera, conclusiones, reformulación)
   deberían además derivar de **una sola** función, que es la deuda que
   BUG-0036 y BUG-0042 dejaron abierta y que este defecto vuelve a cobrar.
3. Quitar `n_extreme` de la lista de fallos, por BUG-0105.

## Validation

`bugs/BUG-0106-repro/repro.py` sale con código 1 mientras
`_reformulacion_desde` no reporte fallo con `white_noise=False` o
`normal=False`, y vuelve a 0 cuando lea las claves correctas. Conviene además
un test que compruebe que los tres predicados de adecuación coinciden sobre la
misma diagnosis.

---

## Cierre (2026-09-07)

Reproducido exactamente:

    la diagnosis dice:   white_noise=False   normal=False
    lo que leía:         q_pass=None         jb_pass=None
    → REFORMULACIÓN: «quedan 2 residuos extremos» y nada más

Ciego a los dos contrastes que deciden la adecuación, y reaccionando al único
criterio que no debía mirar (BUG-0105). En el carril AUTÓNOMO, donde no hay
analista que note la contradicción.

**El arreglo no es renombrar las claves.** Renombrarlas dejaría dos funciones
leyendo el mismo dict por su cuenta, que es exactamente cómo se llegó aquí: el
mismo fichero tenía `_conclusiones_desde` leyendo `white_noise`/`normal` sesenta
líneas más abajo. `_reformulacion_desde` **delega** en ella, y hay una prueba que
lo fija — la misma familia de arreglo que BUG-0014 en `fue`, donde el segundo
generador de un objeto se había quedado atrás.

### Por qué sobrevivió a la suite, que es lo que más importa

**Había una prueba y estaba en verde.**
`test_la_reformulacion_sale_de_la_diagnosis_no_del_agente` alimentaba el bloque
con `{"q_pass": False, "jb_pass": True}` — **las claves que leía el código, no
las que la diagnosis escribe**. Estaba escrita contra la implementación en vez de
contra los datos reales, así que sólo comprobaba que dos errores coincidían.

Un doble usado en una prueba tiene que llevar las claves del PRODUCTOR, o la
prueba certifica el defecto en lugar de cazarlo. Corregida.

### La causa de fondo: dos vocabularios para los mismos dos hechos

    el dict de la diagnosis    "white_noise"   "normal"
    GuionStats                 q_pass          jb_pass

Los dos son legítimos en su sitio, y por eso nadie los unificó. Pero quien lee el
dict escribiendo `q_pass` **no obtiene un error**: obtiene `None`, que pasa en
silencio toda comparación `is False`. El defecto no se manifiesta como fallo sino
como una rama que nunca se ejecuta — que es la clase más difícil de ver.

Cerrado con una guarda estructural: `test_nadie_lee_del_dict_de_diagnosis_una_
clave_que_no_existe` extrae por AST las claves que `describe_diagnosis` escribe y
comprueba que todo `d.get(...)` de los tres consumidores use una de ellas.
