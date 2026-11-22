# El carril autónomo como constructor de univariantes para sima. Estudio (22-nov-2026)

## Para qué

La ruta V de sima necesita un modelo univariante por serie antes de entrar al
VARMA (la vara de medir y las condiciones iniciales). La propuesta es que los
construya un agente con art en el carril autónomo, con dos sesgos de selección:

1. estacionalidad determinista casi siempre (`objetivo="multivariante"`, que
   art ya tiene);
2. AR puro preferido a ARMA o MA, salvo que el MA sea muy claro (art no lo
   tiene: fue una instrucción al agente).

Este estudio mide lo que cuesta y apunta lo que estorbó.

## La medición

Dos series del VAR monetario de EE. UU., mensuales, 1990-01 a 2007-12 (216
observaciones). Un agente por serie, una detrás de otra, con el protocolo
autónomo entero (sin `build_model`), art 0.2.6.

| serie | tiempo | tokens | llamadas a art | estimaciones | final |
|---|---|---|---|---|---|
| IPC (estacional, dos intervenciones) | 3 min 12 s | 131.000 | 21 | 6 | REVISAR: paró por la regla de parada |
| WTI (sin estacionalidad, una intervención) | 2 min 16 s | 111.000 | 19 | 4 | APROBADO, con contrastes formales |

Un sistema de cuatro series: entre 9 y 13 minutos y alrededor de medio millón
de tokens. La serie fácil cuesta casi lo mismo que la difícil: el coste fijo
por serie pesa más que el análisis.

Los modelos:

- **IPC**: ln, d = 1, 11 armónicos, AR(2) con media, impulso en 09/2005 (2 ω)
  y escalón en 09/2006 (2 ω). Q(39) p = 0,0055, por r(11) = +0,24.
- **WTI**: ln, d = 1, AR(1) sin media, escalón de dos pasos en 08/1990.
  Q(39) p = 0,10; Jarque-Bera p = 0,37.

Frente a los modelos guiados del analista para las mismas series, la
estructura coincide (transformación, d, estacionalidad, orden AR) y lo que
difiere son las intervenciones: qué fechas y con qué forma.

## El sesgo hacia AR puro

Decidió el modelo en las dos series: en las dos art listaba primero un MA(1)
en empate declarado con el AR, y el agente tomó el AR dejando la razón en el
nodo. En el WTI estimó los dos candidatos antes de elegir, como manda la
regla del empate; en el IPC eligió sin estimar el MA(1).

**Pendiente de decidir**: si el sesgo pasa a ser de art (un valor más del
propósito, o un parámetro del nodo de órdenes que reordene el empate) o sigue
siendo una instrucción del que llama. Como instrucción funciona, pero no
queda escrito en la salida de art ni se aplica igual cada vez.

## Arreglado con este estudio

- **BUG-0262**: `guided_identification` no tenía `modo`; sus figuras viajaban
  como imagen en cada llamada. Ahora, con `modo="autonomo"`, se guardan junto
  al modelo.
- **BUG-0263**: el protocolo del carril autónomo no llegaba a un cliente que
  trunca las instrucciones (49.000 caracteres; la sección empieza hacia el
  19.000). Ahora hay `protocolo_autonomo()` y el principio de las
  instrucciones la nombra.

No se ha medido todavía cuánto baja el coste con los dos arreglos.

## Apuntado y sin arreglar

Lo que sigue lo observaron los agentes durante las dos corridas. **No está
comprobado aparte ni tiene repro**: cada punto es un candidato a parte, no un
parte. Los marcados con (2) aparecieron en las dos corridas.

1. **Mensajes contradictorios sobre intervenciones.** La diagnosis dice
   «añade las intervenciones antes de juzgar la Q» y la puerta de
   intervenciones, sobre el mismo modelo, «intervenir aquí es
   sobreintervenir». En el IPC, además, el escaneo latente marcaba r(36) como
   enmascarado y la tabla de la puerta decía que ningún veredicto cambiaba.
2. **Quién escribe los nodos del guion (2).** `guided_identification` con
   `guion_path` escribe sola dominio, λ, d, estacionalidad y órdenes; media e
   intervenciones piden un `guion_node` a mano. La sección del autónomo sigue
   diciendo que se llame a `guion_node` tras cada nodo, lo que los duplicaría.
3. **La puerta de intervenciones no registra un «no intervengo».** Esa
   decisión hay que apuntarla a mano.
4. **`guion_adopt` deja los antecesores «explorando» (2)** y sugiere
   `guion_abandon`, que abandona en cascada y se llevaría el modelo adoptado.
5. **`objetivo` en `confirm_and_estimate` (2).** Las instrucciones dicen que
   no se le pase porque no lo lee; los agentes dicen que el esquema lo acepta.
6. **El camino del nivel de un impulso.** En el impulso de 09/2005 del IPC se
   imprimió un camino acumulado (+0,78; +1,52; +1,52…) junto a la frase de que
   el efecto permanente es cero por construcción.
7. **La forma de una intervención que los datos no identifican (2).** La
   llamada pide información de fuera de la serie. Un agente la pone de su
   conocimiento general; es donde los modelos autónomos se apartan de los del
   analista.
8. **Una correlación aislada en el retardo 11.** Ninguna herramienta del
   protocolo la trata con parsimonia; en el IPC el análisis solo pudo acabar
   por la regla de parada, y sin contrastes formales.
9. **Las figuras de la identificación van solo al directorio temporal** si no
   se fija `ART_FIG_DIR`. Con BUG-0262, en autónomo quedan además junto al
   modelo; en guiado siguen solo allí.
10. **`domain` hay que repetirlo en cada llamada.**
11. **No existe un modo que no dibuje.** En autónomo las figuras se dibujan y
    se guardan aunque nadie las mire: es tiempo, no tokens.

## Lo que queda fuera

La reforma de cómo art pasa la información a los agentes (el peso de las
instrucciones y de las salidas) no se toca aquí. Los dos arreglos son los
mínimos para que el carril se pueda recorrer sin leer el código fuente.
