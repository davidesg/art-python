---
id: BUG-0155
title: `evento_naturaleza` sólo admite permanente|transitorio y no lo dice — se aprende por el error, y le falta «recuperación parcial»
status: fixed
severity: medium
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - intervenciones
  - esquema
references:
  - BUG-0116
  - BUG-0157
---

## Summary

Dos cosas, y la segunda es la de fondo.

**1 · No dice qué admite.** `guided_intervention(..., evento_naturaleza=…)`
acepta `"permanente"`, `"transitorio"` o vacío. La descripción de la
herramienta no lo enumera, así que el valor válido se aprende **por el mensaje
de error**. Es un parámetro de ENUM sin su enumeración: la descripción de
`incident_configurations` sí lo dice (`mcp_server.py:2090`), la de la puerta no.

**2 · El enum no cubre lo que el analista tiene que decir.** En ITCER el suceso
de 2008-09 es una caída seguida de una recuperación PARCIAL: el nivel no vuelve
—no es transitorio— y tampoco se queda donde cayó —no es el permanente que el
contraste rotula—. El analista describió «recuperación parcial» y no hay forma
de declararlo.

Consecuencia concreta: el aviso «la explicación extramuestral no concuerda con
el contraste» se dispara comparando lo que el analista dice con un contraste
que sólo tiene dos casillas, y el analista no tenía la suya.

## Impact

`evento_naturaleza` existe para que el registro extramuestral entre en la
decisión — es el único nodo de `art` cuya evidencia no está en los datos. Un
enum que no cubre el caso convierte esa entrada en una elección entre dos
respuestas equivocadas.

## Fix

**1 · El enum viaja en el ESQUEMA, y no como prosa.** El parámetro se publicaba
como `{"type": "string"}` a secas — ni descripción ni valores:

```json
"evento_naturaleza": {"default": "", "title": "Evento Naturaleza", "type": "string"}
```

Ahora es un `Literal`, que FastMCP convierte en un `enum` de verdad:

```json
"evento_naturaleza": {"default": "", "type": "string",
  "enum": ["", "permanente", "transitorio", "recuperacion_parcial"]}
```

Es la diferencia entre documentar una regla y que el sistema la tenga: con el
enum el cliente **no puede construir la llamada mal**. Y se hizo en las dos
puertas, no sólo en la que fallaba.

**2 · Tres lecturas, no dos.**

    permanente             el nivel se queda desplazado
    transitorio            vuelve a la línea base
    recuperacion_parcial   vuelve EN PARTE — ni una cosa ni la otra

La tercera se añade **ahora** y no antes porque ahora existe el instrumento que
la mide: la ganancia NETA de dos intervenciones (BUG-0157). Una casilla que nada
puede contrastar sería peor que no tenerla — sería pedirle al analista una
declaración que el sistema no sabe usar.

**3 · Y declararla manda al sitio correcto en vez de fingir un veredicto.**
`la_tercera_lectura_no_cabe_en_este_contraste` hace que `concuerda` sea `None`,
con su razón dicha:

    ℹ **Declaras la tercera lectura, y este contraste tiene dos casillas.** Con
    una sola intervención, ω(1)=0 dice «el nivel volvió» y ω(1)≠0 dice «no
    volvió del todo» — y lo segundo es compatible con la recuperación parcial
    **y** con el permanente puro: no las separa.

    Lo que las separa es la **ganancia NETA**: modeliza la caída y la vuelta
    como **dos intervenciones** —encadenando por `base_pre_path`— y contrasta
    H₀ Σᵢωᵢ(1)=0 con `test_interventions(..., ganancia_neta=[i, j])`.

**4 · Y si un cliente ignora el enum, el error ENUMERA.** Se aprendía por el
mensaje de error; el mensaje al menos tiene que enseñar — las tres opciones, y
que la descripción del suceso va en `fuente`, que es el error exacto que se
cometió en ITCER.

**5 · No se castiga al analista por una tilde.** `recuperación parcial`,
`Recuperacion-Parcial` y `recuperacion_parcial` son la misma declaración. El
esquema hace que un cliente conforme mande el valor exacto; el normalizador es
para los que no.

## Validation

`tests/test_bug_0155_la_tercera_lectura.py`. Comprueba el enum **en el esquema
publicado** —no en el fuente— para las dos puertas; que el error enumera las tres
y dice dónde va la descripción; que la frase entera del suceso, que es lo que se
escribió en la corrida, se rechaza nombrando `fuente`; que declarar la tercera no
afirma concordancia y manda a la ganancia neta; y que los dos avisos vecinos
—éste y el de la vuelta diferida de BUG-0157— no se confunden entre sí.

Y lo que no debe cambiar: `naturaleza` sin `fuente` sigue sin valer. La tercera
casilla no relaja la regla de que no se afirma nada extramuestral sin decir por
qué se sabe.
