---
id: BUG-0176
title: Reinscribir un modelo lo cuelga de la ÚLTIMA entrada del guion — el mapa publica que el modelo adoptado desciende de la sobreparametrización que lo rechazó, y que el FINAL desciende del descartado
status: fixed
severity: high
component: guion
found_in: 0.2.1
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 4 de IPC_ES, muestra extendida
tags:
  - guion
  - linaje
  - registro
references:
  - BUG-0108
  - BUG-0175
  - BUG-0177
---

## Summary

Volver a registrar un modelo ya registrado es corriente y legítimo: se hace para
ponerle nombre («m03» en vez de «PC4»), para colgarle el veredicto final, o para
marcarlo como adoptado. Pero `record_version` no admitía `base_pre_path`, así que
`infer_parent` caía en su rama de conjetura —«el padre es la última entrada»— y
la copia quedaba colgando de lo último que hubiera pasado por el guion.

El árbol que `guion_map` y `export_guion` publican pasa entonces a afirmar cosas
que no son.

## Reproduction

El run 4 de IPC_ES, tres veces en el mismo guion. Mismo `.inp`, mismo ℓ hasta el
último dígito:

    v 4 PC4         inp=m03.inp    parent=3  (declarado)   logL=-3.447235171246234
    v 7 m03         inp=m03.inp    parent=6  (INFERIDO)    logL=-3.447235171246234
    v11 m03z        inp=m03z.inp   parent=7  (declarado)   logL=-3.447235171256125
    v18 m12         inp=m12.inp    parent=17 (declarado)   logL=-41.903150352904504
    v19 m12         inp=m12.inp    parent=18 (INFERIDO)    logL=-41.903150352904504
    v20 FINAL_m03z  inp=m03z.inp   parent=19 (INFERIDO)    logL=-3.447235171256125

v7 **es** v4; v19 **es** v18; v20 **es** v11. Y el mapa dibujó:

* **m04b ARMA(1,1) → m03**: el modelo ADOPTADO descendiendo de la
  sobreparametrización que lo rechazó. Al revés de como ocurrió.
* **m12 → FINAL_m03z**: el modelo FINAL descendiendo del que se descartó por
  inadecuado, y además estimado sobre otra muestra (BUG-0177).

Sintético, en la suite: estimar `m01`, encadenar `m02` de él, y reinscribir `m01`
con `record_version`. Sin el arreglo, la reinscripción sale con `parent=2`.

## Impact

El guion existe para conservar la evidencia del recorrido —es lo que BUG-0110
persigue por otro lado—. Un árbol cuyas aristas son falsas no es evidencia. Y no
es un detalle de dibujo: `guion_abandon` **arrastra a los descendientes**, así que
un padre falso pone en la línea de fuego a ramas que no tienen nada que ver.

Contra la tabla de la congelación: *publica un número incorrecto y calla*. El
analista lo confirma como ENTRA.

## Root cause

`src/art/mcp_server.py`, `record_version`: no tenía parámetro `base_pre_path`,
de modo que su llamada a `_record_to_guion` pasaba `""` siempre. Con eso
`infer_parent` no tiene nada que emparejar y devuelve `guion.entries[-1].version`.

Es la familia de BUG-0108 —cerrado para `estimate_and_diagnose`— por la puerta
que quedó abierta.

## Fix

Dos piezas, una automática y una declarativa.

1. **La copia se reconoce sola.** Desde BUG-0175 cada entrada guarda el `pre_sha`
   del `.pre` que produjo. Mismo `.pre` byte a byte es el mismo modelo: en
   `_record_to_guion`, si no se declaró `base_pre_path` y el `pre_sha` coincide
   con el de una entrada anterior, esto es una reinscripción — hereda el padre
   del original, se marca `re_registro_de=<version>` y `parent_origen="re-registro"`.
2. **La puerta.** `record_version` gana `base_pre_path`, con lo que un modelo
   encadenado registrado a mano puede declarar de dónde sale en vez de que se
   adivine.

`guion_map` lo dice en la línea del nodo: `↻ re-registro de vN`. Dibujar una
copia como un paso más infla el recorrido.

**Lo que NO se arregla aquí.** El recuento de `iteraciones` sigue contando cada
reinscripción como una iteración —«19 iteraciones» donde hubo 16 modelos—. Es
otro número y otro síntoma; con `re_registro_de` ya en la entrada, descontarlas
es una línea, pero no entra en este defecto.

Un guion escrito antes de estos campos no se retro-repara: sin `pre_sha` no hay
con qué reconocer la copia. El del run 4 se queda como está y sale listado como
«sin contrastar» (BUG-0175).

## Validation

`tests/test_bugs_0176_0177_el_arbol_y_la_muestra.py`:

- un guion real de tres entradas —`m01`, `m02` encadenado, `m01` reinscrito—;
  la copia se reconoce por su huella, NO cuelga de `m02`, y hereda el padre del
  original;
- el mapa dice `re-registro de v1`;
- `record_version` acepta `base_pre_path`.
