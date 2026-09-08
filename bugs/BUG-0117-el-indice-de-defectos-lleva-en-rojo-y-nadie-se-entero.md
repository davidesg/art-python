---
id: BUG-0117
title: El índice de defectos lleva tiempo en rojo — 7 errores en 6 informes, y ninguna prueba lo miraba
status: fixed
severity: medium
component: bugs
found_in: 0.1.12
fixed_in: 0.2.1
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


---

## Cierre (2026-09-08)

**119 informes, todos válidos.**

### Los cuatro de `fixed_in` vacío — la versión sale del historial

No se conjeturó: cada informe se cerró en un commit, y ese commit tiene su
`pyproject.toml`.

    0024, 0066, 0067   commit 3535010 (2026-09-02)   → 0.1.12
    0088               ya lo tenía escrito           → 0.1.12

El 0088 no necesitaba dato nuevo: lo tenía **escrito y anulado** por un
`fixed_in:` vacío en la línea de abajo. El YAML se queda con la última, así que
bastó quitar la repetición.

### Los dos de prosa — el matiz se movió, no se recortó

`«partially fixed — pair reported; the two calibration items remain»` y
`«closed — not a defect»` no eran descuidos: eran **matices reales que el
vocabulario no admite**.

Recortarlos a `fixed` habría perdido información y, peor, habría mentido: el
0011 **no está** enteramente arreglado. Así que el campo se queda con el término
del vocabulario —`in-progress` y `wontfix`— y el matiz va al cuerpo, donde cabe
entero y donde se lee:

  · **0011 → `in-progress`**, con lo hecho y lo que falta dicho por extenso.
  · **0020 → `wontfix`**, que es exactamente el estado que el vocabulario
    reserva para «se investigó, se entendió, y no hay nada que arreglar».
    `severity: none` no existe; pasa a `low`, que es convencional — lo que
    importa es el estado.

### Y la prueba, que es lo que faltaba de verdad

`tests/test_indice_de_defectos.py`. El validador existía desde hace tiempo y no
impidió que se acumularan seis informes rotos, porque **nadie lo corría**. Ahora
lo corre la suite, con cinco comprobaciones:

  · todos los informes válidos;
  · ningún identificador repetido (el choque de los dos BUG-0102);
  · `fixed` implica `fixed_in`;
  · **ninguna clave duplicada en el encabezado** — el caso del 0088, que
    `problems()` NO ve, porque para cuando mira ya sólo queda una;
  · ningún campo de vocabulario con prosa.

La cuarta es la que más me interesa: era un fallo **invisible al propio
validador**, y ahora no lo es.
