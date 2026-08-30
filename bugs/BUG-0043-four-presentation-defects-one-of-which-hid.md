---
id: BUG-0043
title: five presentation defects found by the clean-chat experiment — one of them hid the node the analyst needed (a failing JB with no outliers is a λ symptom, and the output sent them to add interventions)
status: fixed
severity: medium
component: describe/mcp-tools
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia — hallados por el experimento del chat limpio
tags:
  - presentation
  - diagnosis
  - guion
references:
  - src/art/describe.py (describe_diagnosis — recomendación; escaneo de anómalos)
  - src/art/mcp_server.py (guided_identification call 3; _record_to_guion)
  - src/art/guion.py (GuionEntry.figure_path)
  - tests/test_bug_0043_diagnosis_and_presentation.py
---

## Summary

Cinco defectos de presentación, todos salidos de correr el protocolo **sin
contexto previo**. Comparten forma: la salida dice algo que no es, o no dice lo
que sabe. Van juntos porque cuatro son de la misma función y el quinto se
encontró midiendo el mismo experimento.

## 1. Una JB que falla sin anómalos es un síntoma de λ, y no se decía

El consejo era `"los residuos no son normales sin outliers — revisa la
especificación"`, que no nombra nada. Y cuando **sí** había extremos, la rama que
disparaba era `"la no-normalidad (JB) está probablemente causada por los
outliers"` — que manda a **añadir intervenciones**.

Sobre un modelo en NIVELES de una magnitud positiva de recorrido amplio eso es
perseguir el síntoma: la heterocedasticidad que el log elimina se manifiesta a la
vez como asimetría y como residuos grandes. Los anómalos que uno "trata" son el
propio efecto de escala.

**Medido:** un carril autónomo con λ=1 sobre un precio (recorrido 95→500 USD/t)
estimó **seis modelos consecutivos sin alcanzar la adecuación**, con el JB
bajando de 46.7 a 8.9 y sin pasar nunca, añadiendo intervenciones ronda tras
ronda. El consejo que recibía era éste, y era el que le impedía volver al nodo
correcto. Cerró aceptando `JB=12.12 (p=0.0023)`.

**Fix.** La explicación por outliers se mantiene —es legítima— pero sobre un
modelo con λ≠0 y una serie positiva de recorrido ≥2 se le añade:

> pero OJO: este modelo está en niveles (λ=1) sobre una serie positiva que
> recorre un factor 5.3, y ahí el efecto de escala se manifiesta a la vez como
> asimetría (−0.66) y como residuos grandes. **Si el JB sigue fallando tras
> tratar los anómalos, el problema no son los anómalos: es λ.**

Y sin extremos que la expliquen, la recomendación nombra λ como primer
sospechoso, con la asimetría y la curtosis medidas.

## 2. La media descentrada no tenía rama

`.clean` incluye `centred`, pero la recomendación no lo miraba. Un modelo cuyo
ÚNICO fallo era la media cerraba con:

```
Reformulación necesaria: .
```

La razón vacía. Ahora la nombra, y se añade una red: si el modelo no es adecuado
y ninguna rama supo decir por qué, se dice **eso** en vez de imprimir un punto.

## 3. `freq=` vacío

```
hay estacionalidad residual en freq= — revisa si los armónicos…
```

Ocurre cuando el contraste CONJUNTO detecta y **ninguna frecuencia** es
significativa por separado — el caso real de RATIO: conjunto p=0.0492, f=1
p=0.0517, f=2 p=0.157. Que ninguna lo sea es información, no un hueco: es un
rechazo marginal repartido y no una frecuencia sin tratar. Ahora lo dice.

## 4. Porcentajes con denominador ≈0

`k=3 (−1162%)`, `k=4 (−1561%)`, `k=10 (+687%)`, impresos junto a `ACF_max=0%`.
El porcentaje es contribución/ACF total, así que donde la ACF ronda cero el
cociente se dispara sin significar nada.

El código **ya lo sabía** —excluía esos retardos del criterio de decisión, con el
comentario puesto— pero los publicaba igual. Ahora el porcentaje sólo se da donde
la ACF sale de la banda; en los demás se enseña la ACF, que es el dato honesto.
En ITCER esto reduce la línea de cuatro cifras a una: el `+55%` del retardo 1, que
era la única que decidía.

## 5. Recetas que contradicen la conclusión

Tras concluir «**Decisión A — sin estacionalidad**… sin armónicos cos/sin», la
misma respuesta imprimía la receta completa de la ruta B1 con `n_harmonics=1` y
la de B2 con `D=1`. Los bloques se anexaban incondicionalmente.

No es verbosidad: es una instrucción para hacer lo contrario de lo que se acaba
de concluir, y quien la lee no tiene cómo saber cuál de las dos vale. Ahora las
recetas sólo aparecen cuando hay estacionalidad que enrutar; si no, se da el paso
que toca —identificación ARMA directa— y nada más.

## 6. Y una que se encontró midiendo: el guion era 96% caché

El chat limpio reportó que `guion_map` reventaba el límite de salida. Medido, el
mapa ocupa 8–10 KB y está bien; lo que pesa es el FICHERO:

| guion | total | figuras | razonamiento |
|---|---|---|---|
| ITCER | 450.4 KB | 434.4 KB (96.4%) | 7.1 KB |
| PGAS | 656.1 KB | 633.5 KB (96.5%) | 9.5 KB |
| RATIO | 457.8 KB | 439.6 KB (96.0%) | 8.5 KB |

**El 96% son PNG en base64**, y crece ~110 KB por modelo. El guion es el registro
científico y se carga entero en cada operación del mapa; una figura es DERIVADA
—se rehace desde el `.inp`— así que empotrarla es meter caché en el registro.

Ahora la figura se escribe como fichero hermano (`figs/<serie>_v<N>.png`) y el
guion guarda la ruta. Medido sobre el mismo caso: **450 KB → 6.6 KB**.
`figure_b64` se conserva en el esquema para que los guiones ya escritos sigan
abriéndose, y `export_guion` prefiere la ruta cuando está.
