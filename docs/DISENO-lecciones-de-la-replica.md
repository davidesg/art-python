# Qué enseña la réplica sobre el diseño de `art`

Escrito el 2026-09-02, al cerrar cuatro corridas de la réplica del TFM de Bolivia
(dos LLM × cuatro runs) y con el ejercicio SF_MEG a la vista. 25 defectos
cerrados en la sesión (BUG-0040…0070), suite de 787 a 917 tests.

No es una lista de deseos: cada propuesta lleva el número que la sostiene.

---

## 1. La taxonomía de los defectos dice dónde está el problema

De los 25 defectos, **ninguno era un estadístico mal calculado**. Se reparten así:

| clase | n | ejemplos |
|---|---|---|
| **La presentación contradice al contenido** | ~12 | 0055 (titular retirado tres párrafos después), 0056 (la evidencia habla con voz de política), 0059 (el módulo borra el signo), 0060 (un error típico inválido con formato de válido), 0063 (rótulo heredado de otro bloque) |
| **Corrupción silenciosa al cruzar una frontera** | 5 | 0051 (`ifadf` se cae del spec), 0057 (`len()` cuenta operadores fijados), 0061 (covarianza leída de un `.pre`), 0065 (`float()` descarta la parte imaginaria) |
| **Capacidad ausente o lógica equivocada** | ~8 | 0044/0048 (el ruido blanco), 0046 (el objetivo en el lote), 0065 (la nula de SF), 0068 (el par con raíces complejas) |

**El motor está sano; lo que falla es el acto de habla.** Ésa es la conclusión de
diseño más importante, y contradice la intuición de que hay que revisar la
estadística. Hay que revisar cómo se dice.

Y hay una tercera categoría, transversal, que aparece tres veces: **una conclusión
atada a la condición equivocada** (0056, 0069, 0070). En los tres casos arreglar
un contraste **apagó el aviso de otro**, porque el aviso vivía dentro de un `if`
que no era el suyo.

---

## 2. Lo que de verdad mueve la aguja: la búsqueda de intervenciones

Medido sobre las ocho corridas de carril:

| corrida | ITCER interv. | ΔAIC | PGAS interv. | ΔAIC |
|---|---|---|---|---|
| benchmark guiado | 1 · ω(B) | — | 1 | — |
| runs 1, 2 y 4 (los dos carriles) | 1 | **+6,15 a +8,84** | 1 | −0,93 |
| **run 3 claude** | **2** | **−1,09** | **2** | **−16,24** |

**Encontrar la segunda intervención del episodio 2008-09 vale entre 7 y 15 puntos
de AIC, y sólo una de ocho corridas la encontró en las dos series.**

Y hay un matiz que cambia la recomendación: `run3 ds` y `run4 ds` **también**
pusieron dos intervenciones en PGAS y salieron peor (−0,31 y +6,66). Así que el
problema no es contar dos: es **encontrar las dos correctas, en la fecha y la
forma correctas**.

Es además el nodo donde la herramienta menos ayuda. `suggest_intervention_form`
propone la forma de UN residuo extremo; nadie propone que un episodio pueda
necesitar DOS, ni ofrece el contraste entre «una intervención con ω(B)» y «dos
intervenciones escalares».

### Propuesta 1 (la de mayor valor medido)

**Un nodo de intervención que trabaje por EPISODIOS, no por residuos.** Cuando dos
o más residuos extremos caen a distancia ≤ 2-3 períodos, son un episodio, y el
nodo debe ofrecer las especificaciones rivales y estimarlas:

* un escalón (o impulso) en el primer punto,
* dos intervenciones escalares, una por punto,
* una intervención con ω(B) de orden 1.

Las tres son anidadas o comparables (mismo `d`, misma serie), así que el LR y el
AIC deciden. Es exactamente lo que hizo a mano el analista del run 3 y le valió
los dos únicos ΔAIC negativos grandes del ejercicio.

**El ω(B) no es la prioridad que yo creía.** El run 3 lo demuestra: dos escalones
batieron al ω(B) del benchmark (379,91 contra 381,00) con los mismos tres
parámetros. Lo que falta no es la forma rica: es **buscar el segundo evento**.

---

## 3. Lo que funcionó, y por qué hay que repetir el patrón

**La marca `(✗…)` de BUG-0060 es la intervención más exitosa de la sesión.**
Marcar el valor inválido *en su sitio* —en vez de avisar debajo— fue recogido y
usado **12 veces** por un analista que no sabía que existía, y cambió una decisión
de nodo (la media del ITCER).

Compárese con `overparameterization_analysis`: **0 llamadas en 361**, hasta que su
aviso pasó a salir *inline* en la diagnosis.

### Propuesta 2

**Regla de diseño: una herramienta que hay que llamar aparte no existe.** Lo
esencial va dentro de la salida de algo que ya se llama. Y **el valor no leíble se
marca donde está**, nunca sólo se comenta debajo.

Candidatos inmediatos para la marca: los LR calculados sobre un modelo inadecuado,
las correlaciones que salen de una covarianza degenerada, el AIC entre
diferenciaciones distintas (ya suprimido por 0051, pero podría marcarse en vez de
desaparecer).

---

## 4. La puerta de adecuación es lo que salva, y hoy es sólo un aviso

El hallazgo más limpio del RUN 4: **dos carriles construyeron el mismo modelo d=0
inadecuado sobre PGAS. Uno lo adoptó como final y leyó su Shin-Fuller como
confirmación; el otro se negó a leerlo** —«NO ES LEGIBLE»— **y por eso se salvó de
un defecto de la herramienta que aún no sabíamos que existía** (BUG-0065).

En SF_MEG el mismo patrón, en grande: **11 de 18 finales con Q o JB fallidos, en
las tres realizaciones**, y las clasificaciones descansan sobre LR leídos ahí.

### Propuesta 3

**Que la adecuación sea una puerta y no un párrafo.** Hoy `formal_tests` imprime
el aviso y luego los números. La evidencia dice que el aviso no basta.

Opción conservadora, y coherente con lo que ya funcionó: **imprimir los veredictos
tachados**, como los errores típicos de 0060 — el número visible, marcado, y sin
línea de conclusión. Quien quiera leerlos que los desmarque a conciencia.

---

## 5. Eficiencia: el coste no está donde parece

Dos medidas de las cuatro corridas:

* **Las imágenes son el 93-96 % del tráfico.** Una llamada de identificación
  devuelve ~0,6 KB de texto y ~35 KB de base64.
* **El 97,5 % de la entrada son lecturas de caché.** El coste va con *turnos ×
  contexto*, no con lo que se pide en cada turno.

### Propuesta 4

**Figuras bajo demanda en el carril autónomo.** No hay ojo humano que mire el
gráfico: el LLM lee los números. La llamada devuelve los estadísticos y una línea
«figura disponible con `figura=True`». En el carril guiado la figura sigue por
defecto, porque ahí sí hay quien la mire y la escuela manda mirarla.

Ahorro esperado: del orden del 90 % del tráfico del carril autónomo.

### Propuesta 5

**Menos turnos en la parte que no tiene realimentación.** Los cuatro primeros
nodos —dominio, λ, d, estacionalidad— se deciden **antes de que exista el primer
residuo**, así que agruparlos no pierde nada: no hay nada que realimentar
todavía. Una llamada compuesta que devuelva los cuatro con su evidencia, y el
analista confirma o corrige.

**Ojo con la frontera**: agrupar *dentro* de una serie, en la fase sin
realimentación, es legítimo; agrupar *a través de series* es lo que costó 22
puntos de AIC en el RUN 3 de DS. La regla ya escrita («una serie detrás de otra»)
sigue en pie.

---

## 6. Arquitectura: el informe es el producto, y no está diseñado como tal

Doce defectos de presentación no son doce descuidos: son la consecuencia de
construir el informe **encadenando cadenas de texto dentro de `if` anidados**. De
ahí salen las tres patologías observadas:

* un titular que afirma más de lo que su cuerpo sostiene (0055, 0056, 0060);
* una conclusión que no se imprime porque el `if` que la envuelve es de otro
  contraste (0069, 0070);
* un rótulo heredado de otro bloque que describe mal su número (0063).

### Propuesta 6

**Una capa de ensamblado de veredictos.** Un tipo `Veredicto(afirmación,
salvedades[], remite_a)` y un renderizador con dos invariantes comprobables por
test:

1. **Un titular con salvedades no puede imprimirse desnudo** — o las lleva dentro,
   o baja de tono.
2. **Toda conclusión calculada aparece o se suprime con razón explícita.** Una
   conclusión computada y no impresa es un fallo por construcción, no un silencio
   aceptable.

Con esos dos invariantes, las tres patologías se vuelven imposibles en vez de
tener que cazarlas de una en una. Es la propuesta de mayor rendimiento a largo
plazo: **mata una clase entera, no un caso**.

---

## 7. Lo que hizo mejorar al carril autónomo, para seguir haciéndolo

El autónomo pasó de +10,63 a **−11,92** en suma de ΔAIC entre los runs 2 y 3. La
causa no fue un arreglo puntual: **exploró más** — 12 herramientas distintas
frente a 8, 13 callejones frente a 8, y tres tentativas de la rama B2 antes de
descartarla.

Lo que lo hizo posible:

* **`objetivo` como entrada** (0046): decide la ruta estacional cuando los
  contrastes no deciden, y hace que las series de un sistema sean montables.
* **Estimar las dos ramas y adjudicarlas** en vez de elegir por convención.
* **Los avisos en prosa**, que los tres analistas citan como lo mejor de la
  herramienta: *«los tres nodos en que fui contra la línea de recomendación son
  nodos en que fui a favor de un párrafo que estaba unas líneas más abajo»*.

### Propuesta 7

**Premiar la exploración, no penalizarla.** Los callejones con razón escrita son
el activo del método, no su coste. Concretamente: que `guion_map` muestre el
número de ramas exploradas junto al modelo final, y que el estado del análisis
distinga «cerrado tras explorar N ramas» de «cerrado sin alternativas».

Y su contrapartida: **la métrica de coste por punto premia al que se detiene
antes**. DS gastó un 45 % menos por punto en el RUN 3 recortando el recorrido, y
sus modelos empeoraron 15,8 puntos de AIC. Cualquier medida de eficiencia futura
tiene que normalizar por calidad, no al revés.

---

## 8. Lo que hay que arreglar del propio método de evaluación

* **La rúbrica satura.** Totales idénticos (11/13 y 7/13) en dos corridas mientras
  el fondo se movía 22 puntos de AIC. Para la próxima: puntuación **continua**
  —suma de ΔAIC con la adecuación como puerta— y no por puntos.
* **El guion no marca cuál es el final.** Me engañó tres veces, la última con un
  modelo que su propio autor había marcado como callejón. Un `final: true`.
* **Los tests pueden defender errores.** Uno exigía `shin_fuller(m).stationary is
  True` sobre una serie I(1) por construcción: fijaba como premisa el veredicto
  equivocado que BUG-0065 vino a corregir. **Un test no debe atar su premisa al
  veredicto de otro módulo.**
* **El contador de `bugs/` es compartido** y colisionó dos veces. Repartir rangos
  si hay ejercicios en paralelo.

---

## 9. Orden de ataque propuesto

| # | qué | por qué ahora |
|---|---|---|
| 1 | **Nodo de intervención por episodios** (§2) | 7-15 puntos de AIC medidos; es el mayor pozo abierto |
| 2 | **Capa de ensamblado de veredictos** (§6) | mata la clase de defecto más numerosa, en vez de cazarla caso a caso |
| 3 | **Adecuación como puerta, con veredictos tachados** (§4) | es lo que salvó a un carril de un defecto nuestro; hoy depende de la disciplina del analista |
| 4 | **Figuras bajo demanda en autónomo** (§5) | ~90 % del tráfico del carril, sin pérdida de información |
| 5 | **`final: true` en el guion** (§8) | barato, y evita el error que cometí tres veces |
| 6 | Llamada compuesta para los nodos sin realimentación (§5) | menos turnos, que es donde está el coste real |

Lo que **no** pondría todavía: el contraste de módulo a frecuencia libre (la
opción 3 de las raíces complejas). Es investigación, va ligado a SF_MEG, y la
rama de sobreajuste (0068) cubre el caso práctico mientras tanto.
