---
id: BUG-0184
title: Regresión de BUG-0175 — encadenar desde un `.inp` dejaba huérfano al modelo; cada intervención quedaba como raíz del árbol, en los dos carriles
status: fixed
severity: high
component: guion
found_in: 0.2.1
fixed_in: 0.2.1
reported: 2026-09-12
reporter: Claude — revisando el guion del run 7 de IPC_ES
tags:
  - guion
  - linaje
  - regresion
references:
  - BUG-0175
  - BUG-0176
---

## Summary

BUG-0175 hizo que el padre de un modelo se reconociera por la **huella de su
`.pre`**: cada versión guarda `pre_sha`, el hijo guarda `base_pre_sha`, y
`infer_parent` exige que coincidan.

Pero no todas las puertas encadenan desde un `.pre`. `suggest_intervention_form`
y `meg_reformulate` encadenan desde el **`.inp`** del padre, y `_record_to_guion`
guardaba la huella de ese `.inp`. La huella de un `.inp` frente a la de un `.pre`
no coincide nunca: `infer_parent` concluía *«hay homónimos con huella y ninguno
cuadra»* —la rama que existe para no nombrar a un impostor— y devolvía `None`.

**Cada modelo con intervención quedaba como raíz del árbol**, en guiado y en
autónomo. Justo lo que BUG-0175 y BUG-0176 venían a proteger, roto por el
arreglo del primero.

## Reproduction

Visto al revisar el guion del run 7; estaba ya en el del run 6:

    run7  v7  m01  parent=None (declarado)   base = m00.inp
          v17 x01  parent=None (declarado)   base = x00.inp
          v18 x02  parent=None (declarado)   base = x01.inp
          v19 x03  parent=None (declarado)   base = x02.inp
    run6  v7, v19, v21, v22 — lo mismo

Y comparando `.pre` con `.pre`, los cuatro de run7 **cuadran**:

    m00.pre hoy = 575330c1   registrado por su entrada = 575330c1
    x00.pre hoy = c59f7ef7   registrado por su entrada = c59f7ef7
    …

Sintético, en la suite: modelo base con `confirm_and_estimate`, e intervención
sobre su `.inp` con `suggest_intervention_form`. Sin el arreglo, la intervención
sale con `parent=None`; con él, cuelga de la base.

## Por qué no lo cazaron los tests de BUG-0175

Sus dieciséis casos —y la verificación de punta a punta que se hizo aquel día—
encadenaban siempre desde un `.pre`, con `confirm_and_estimate(base_pre_path=…)`.
Nadie probó la puerta por la que pasan las intervenciones. Y `linaje_dudoso`
tampoco lo veía: comparaba la huella del `.inp` consigo misma y daba el enlace
por bueno.

## Impact

El mapa dibujaba cada modelo con intervención como el comienzo de un árbol
nuevo. Y `guion_abandon` arrastra a los descendientes siguiendo esos enlaces, así
que un padre ausente deja fuera de la cascada ramas que deberían caer con él.
*Publica un árbol falso y calla*, en el mismo registro que el arreglo pretendía
sanear. Entra, y va antes de la prueba guiada en Windows, que pasa por estas
mismas puertas.

## Fix

`pre_de_la_base(ruta)` en `guion.py`: el `.pre` con el que se compara la base,
venga como venga —si llega un `.inp`, su `.pre` hermano—. `_record_to_guion`
registra `base_pre_sha` con ella: se compara **`.pre` con `.pre`**, que es lo que
el padre registró.

`linaje_dudoso` acepta como «no ha cambiado» la huella del `.pre` o la del fichero
tal cual. Los guiones escritos entre BUG-0175 y éste guardaron la del `.inp`, y no
deben sonar a alarma por el convenio con que se escribieron. Tampoco se
retro-reparan: sus enlaces se quedan como `None`, que es lo que registraron.

## Validation

`tests/test_bug_0184_la_base_desde_un_inp.py`, sobre el camino real:

- intervención sobre el `.inp` del modelo base: cuelga de él. **Sin el arreglo el
  test da `parent=None`** —comprobado anulando `pre_de_la_base`—;
- la huella de la base es la del `.pre` del padre;
- lo que BUG-0175 protege se mantiene: si se reescribe el `.pre` de la base, se
  dice;
- un guion escrito con la huella del `.inp` no da falsa alarma.
