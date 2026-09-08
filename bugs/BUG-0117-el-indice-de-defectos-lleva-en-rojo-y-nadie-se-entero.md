---
id: BUG-0117
title: El índice de defectos lleva tiempo en rojo — 7 errores en 6 informes, y ninguna prueba lo miraba
status: open
severity: medium
component: bugs
found_in: 0.1.12
fixed_in:
reported: 2026-09-08
reporter: David / sesión de Windows — observación (f) del informe de defectos
tags:
  - registro
  - validacion
  - vocabulario
references:
  - src/art/bugs.py (STATUSES, SEVERITIES, Bug.problems)
  - bugs/BUG-0117-repro/repro.py
---

## Summary

`art-bug check` **ya estaba en rojo antes de la sesión del 8 de septiembre**, y
sigue: 7 errores en 6 informes de 115.

    BUG-0011  status 'partially fixed — pair reported; the two calibration items remain'
    BUG-0020  status 'closed — not a defect'
    BUG-0020  severity 'none (el defecto estaba en el pin)'
    BUG-0024  status 'fixed' pero fixed_in vacío
    BUG-0066  ídem
    BUG-0067  ídem
    BUG-0088  ídem

Son **dos clases distintas** y conviene no confundirlas, porque piden arreglos
opuestos.

### Clase 1 — prosa en un campo de vocabulario cerrado (0011, 0020)

«partially fixed — pair reported; the two calibration items remain» y «closed —
not a defect» **no son descuidos**: son matices reales que el vocabulario no
admite. Quien los escribió tenía algo que decir y no tenía dónde, así que lo
puso al lado y rompió el campo.

Recortarlos a `fixed` perdería información: 0011 NO está enteramente arreglado, y
0020 no era un defecto. El vocabulario tiene `in-progress` y `wontfix`, que
cubren los dos casos — pero el matiz («qué queda», «por qué no lo era») pertenece
al cuerpo, no al encabezado.

### Clase 2 — `fixed_in` vacío con `status: fixed` (0024, 0066, 0067, 0088)

Un informe que dice estar arreglado y no dice **dónde** no se puede releer: es
justo lo que hace falta para saber si un veredicto viene de una versión con el
defecto o sin él, que es el problema que BUG-0098 y `version_instrumento`
existen para resolver.

**0088 tiene además la clave DUPLICADA:**

    fixed_in: 0.1.12
    fixed_in:

El YAML se queda con la última, así que el dato correcto está escrito **y
anulado por una línea vacía debajo**. No es que falte: está tapado.

## Impact

Medio, y con un agravante: **si `art-bug check` está en CI, ya fallaba**, y un
verde que nadie mira o un rojo permanente valen lo mismo — nada. Un validador
que lleva tiempo en rojo deja de ser un validador y pasa a ser ruido de fondo.

Y no había ninguna prueba de la suite que lo mirara. `fue` sí la tiene
(`test_all_reports_valid`), y por eso allí el índice está limpio.

## Reproduction

`bugs/BUG-0117-repro/repro.py`: corre la misma validación que `art-bug check`,
sin motor y sin datos. Exit 1 mientras haya informes inválidos.

## Fix

1. **Los cuatro de `fixed_in` vacío**: rellenar con la versión en que se
   cerraron —está en el git log de cada uno— y quitar la línea duplicada de 0088.
2. **Los dos de prosa**: `in-progress` para 0011 y `wontfix` para 0020, con el
   matiz movido al cuerpo, donde cabe entero y donde se lee.
3. **Una prueba en la suite**, como la de `fue`. Sin ella esto vuelve: el
   validador existe desde hace tiempo y no impidió que se acumularan seis.
