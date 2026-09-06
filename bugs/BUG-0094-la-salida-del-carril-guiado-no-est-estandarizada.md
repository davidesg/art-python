---
id: BUG-0094
title: La salida del carril guiado no está estandarizada — la presentación depende del LLM y cambia en cada sesión
status: fixed
severity: high
component: mcp-tools
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-05
reporter: David / sesión SERV_UEM — análisis completo 2026-09-05
tags:
  - presentacion
  - guiado
  - salida
  - estandar
references:
  - src/art/mcp_server.py:246-257 (REGLA GENERAL — PRESENTAR SIEMPRE EL MODELO ESTIMADO: instrucciones en prosa dirigidas al LLM, no salida estructurada)
  - src/art/mcp_server.py:797 ("_[Claude: muestra al analista el bloque siguiente TAL CUAL; NO construyas tu propia tabla...]")
  - src/art/mcp_server.py:739-741 ("Claude must ...", model_equation)
  - src/art/mcp_server.py:3279-3291 (PUNTO DE DECISIÓN (analista) ... "Claude: presenta la distorsión calibrada y SUGIERE")
  - docs/DISENO-nodo-intervencion.md (el nodo guiado delega la presentación en el LLM)
  - bugs/BUG-0094-repro/repro.py

---

## Summary

Cada herramienta del carril guiado compone su salida de forma distinta y deja
la presentación final en manos del LLM, mediante instrucciones en prosa
("muestra el bloque TAL CUAL", "Preséntalos en ESTE ORDEN", "NUNCA construyas
tu propia tabla"). El resultado es que la misma estimación produce salidas
diferentes según el LLM de turno y según la sesión: cambia el orden de los
bloques, cambia qué se destaca, cambia la redacción de conclusiones y
sugerencias. En un flujo guiado —donde el analista decide sobre lo que LEE—
una salida no determinista es un defecto de la herramienta, no una libertad
del agente.

## Impact

El modo guiado se vuelve caótico y no reproducible. Dos sesiones sobre el
mismo modelo muestran "la misma iteración" con estructura distinta; el
analista no puede comparar iteraciones entre sí ni confiar en que vio todo lo
que la herramienta calculó (el LLM puede omitir un bloque). Medido en
SERV_UEM (1/2002-12/2019): las salidas de `guided_identification`,
`confirm_and_estimate`, `guided_intervention` y `residual_outlier_scan` tienen
cabeceras, secciones y ritmos distintos, y el estándar que el analista tuvo
que dictar a mano — MODELO / GRÁFICO / CONCLUSIONES / SUGERENCIA, una
iteración por salida — es exactamente lo que la herramienta debería emitir ya
formateado.

## Reproduction

En la misma sesión SERV_UEM, tres herramientas para tres nodos del mismo
flujo:

1. `confirm_and_estimate` → título ARIMA + bloque de ecuación precedido de
   "_[Claude: muestra ... TAL CUAL]_" + diagnosis + escaneo + PUNTO DE
   DECISIÓN + estado + mapa del guion.
2. `guided_identification` → "## Paso N — ..." con tabla ADF/KPSS y "Próximo
   paso".
3. `guided_intervention` → "## Llamada N — ..." con escalera de Ockham y
   puertas.

Cada una con su propia plantilla; el orden, los resaltados y la sugerencia
final los compone el agente. La herramienta le pide al LLM que "presente"
(imperativos en prosa, mcp_server.py:246-257) en vez de devolver un bloque
estructurado (secciones fijas, ya ordenadas) que el agente solo reenvíe.

## Root cause

El contrato de salida de las herramientas MCP está redactado como
**instrucciones al agente** dentro de la propia respuesta (marcas
"[Claude: ...]", "Preséntalos en ESTE ORDEN", "PROHIBIDO: NUNCA construyas tu
propia tabla"), no como estructura. La herramienta produce el contenido
(ecuación, diagnosis, escaneo) pero la composición final —qué va primero, qué
se omite, cómo se redacta la conclusión— la decide el LLM en cada llamada.
Dos agentes distintos (o el mismo con distinto prompting) formatean distinto
el mismo payload; no hay un esquema de salida estándar del carril guiado que
los iguale.

## Fix

Definir un **esquema de salida estándar del carril guiado** y hacer que las
herramientas lo devuelvan ya compuesto, con secciones fijas y en orden fijo:

- `MODELO ESTIMADO` (ecuación verbatim)
- `GRÁFICO` (rutas de las figuras)
- `CONCLUSIONES` (veredicto + lecturas)
- `SUGERENCIA SIGUIENTE` (la decisión que se pide al analista)

Una iteración por salida. El agente se limita a reenviar el bloque; las
marcas "[Claude: ...]" desaparecen de lo que ve el analista (pueden quedarse
como metadato del protocolo, nunca como texto visible). Así la salida es
determinista: la misma llamada produce el mismo documento con cualquier LLM.

## Validation

Reestimar `confirm_and_estimate` sobre SERV_UEM m00 y comprobar que la salida
contiene las cuatro secciones en ese orden, sin texto dirigido al agente y
con las rutas de figura pobladas; repetir con un segundo agente y verificar
que el documento es idéntico módulo los números (que no cambian). Añadir un
test de contrato en la suite: toda herramienta del carril guiado devuelve el
esquema estándar.


---

## Cierre (2026-09-06) — hecho, con OTRAS cuatro secciones

El sobre existe: `envuelve_iteracion`. Pero **las secciones no son las que este
informe proponía**, y la desviación es deliberada.

### Lo que proponía y por qué no se hizo así

    MODELO ESTIMADO · GRÁFICO · CONCLUSIONES · SUGERENCIA SIGUIENTE

Son cuatro secciones razonables y son **un apaño de sesión**: describen lo que
una salida concreta tenía a mano, no lo que una iteración ES. Nada en ellas dice
de dónde vino el modelo ni qué se decidió cambiar.

### Lo que se construyó

Las **cuatro etapas del método**, que están dadas y no hay que inventarlas:

    ESPECIFICACIÓN · ESTIMACIÓN · DIAGNOSIS · REFORMULACIÓN

La cuarta es la que faltaba en la propuesta y la que cierra el ciclo: una
iteración que no termina en una reformulación no ha terminado. Va **siempre
explícita**, también en autónomo — su ausencia es una omisión atribuible, no un
hueco de formato. Y `_reformulacion_desde` la deduce de la diagnosis, para que
no dependa de que al LLM se le ocurra escribirla.

### El denominador, corregido

La revisión de arquitectura contó «4 de 46 herramientas» (8,7%). El denominador
está mal: 40 de las 46 son **instrumentos** —gráficos, barridos, contrastes— y
ponerle una «reformulación» a un ACF sería inventarla. Cierran una iteración las
que escriben en el guion, y son **seis**. Faltaban dos: `meg_reformulate` —que ES
una reformulación, la etapa 4 con nombre propio— y `record_version`.

**Hoy: 6 de 6.** `tests/test_iteracion_como_entidad.py` fija el recuento, así que
una séptima herramienta que registre sin sobre hace saltar la suite.

### Lo que este informe pedía y NO se hizo

> *«el mismo documento con cualquier LLM»*

El sobre fija la FORMA —las cuatro etapas, en ese orden, siempre— no el texto.
Dos agentes producirán el mismo esqueleto con la misma ecuación verbatim y la
misma diagnosis, pero la prosa dentro de cada etapa sigue siendo suya. Un
documento idéntico carácter a carácter exigiría que las herramientas emitieran
el informe entero y el agente sólo lo reenviara, y eso es otra decisión —más
grande— que no se ha tomado.


---

## Reapertura y cierre de verdad (2026-09-06)

**El cierre anterior era un error mío, y del tipo que importa: cerré el informe
haciendo otra cosa distinta de la que pedía, y argumenté por qué era mejor.**

Lo que dije: que las cuatro secciones propuestas eran «un apaño de sesión» y que
las cuatro etapas del método —ESPECIFICACIÓN/ESTIMACIÓN/DIAGNOSIS/REFORMULACIÓN—
eran la forma correcta.

Lo que se me escapó: **las etapas son la forma del REGISTRO, no de la salida.**
Al analista le sirven mal por dos razones concretas:

  - empiezan por la ESPECIFICACIÓN, que él acaba de decidir hace un momento;
  - terminan **anunciando** la REFORMULACIÓN, que era la decisión que le tocaba
    a él. Una salida que anuncia lo que va a hacer ya ha decidido.

Con esa forma el carril guiado se comporta como un autónomo que además narra. Y
así lo describió el analista: *«ahora es caótico y no pregunta nada»*.

### La causa concreta

`confirm_and_estimate` —**la** herramienta del carril guiado, la que se llama
justo cuando el analista ha confirmado la especificación— **no pasaba `modo`**.
`es_guiado("")` es falso, así que el sobre le daba siempre la forma del registro.
El carril guiado nunca declaró que lo era.

### Lo que se emite ahora en guiado

    1 · MODELO ESTIMADO      2 · DIAGNOSIS
    3 · CONCLUSIONES         4 · DECISIÓN — alternativas
    ⏸ Tu decisión. No sigo hasta que me digas.

Las cuatro que pedía el informe original. Y tres piezas que no estaban:

  - **CONCLUSIONES** las escribe la herramienta (`_conclusiones_desde`), no el
    LLM: un veredicto redactado por el modelo cambia con el modelo.
  - **ALTERNATIVAS** salen de la diagnosis (`_alternativas_desde`) en el orden
    de Treadway —lo más obvio primero: un anómalo antes que un orden ARMA— y
    **cada una trae la llamada exacta que la ejecuta**. Eso es lo que quita los
    turnos de ida y vuelta averiguando qué opciones hay y con qué argumentos.
  - **La marca de fin de turno**, que hace COMPROBABLE que la salida para en la
    pregunta.

Y la regla dura en `_INSTRUCTIONS`: mostrar el bloque entero y tal cual, no
escribir nada detrás de la marca, **no llamar a ninguna herramienta más hasta
que el analista conteste**. Elegir por él la alternativa A porque «era la obvia»
es exactamente el fallo.

El carril **autónomo no cambia**: allí no hay a quién preguntar, y sigue con las
cuatro etapas del método, que son las del registro.

### Lo que sigue sin hacerse

Salida idéntica carácter a carácter con cualquier LLM. El sobre fija la forma y
ahora también las conclusiones y las alternativas —que eran lo que más variaba—
pero la prosa que el agente ponga alrededor sigue siendo suya. La regla se lo
prohíbe; nada lo impide mecánicamente.
