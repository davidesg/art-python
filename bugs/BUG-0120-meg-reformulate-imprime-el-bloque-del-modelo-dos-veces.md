---
id: BUG-0120
title: meg_reformulate imprime el bloque del modelo estimado dos veces, idéntico, en dos secciones del mismo sobre
status: fixed
severity: low
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-08
reporter: David / sesión de Windows — observación (e) del informe de defectos
tags:
  - presentacion
  - sobre
  - duplicacion
references:
  - src/art/mcp_server.py (meg_reformulate — _esp_meg y ecuacion)
  - BUG-0094 (el sobre de las cuatro etapas)
---

## Summary

La salida de `meg_reformulate` contiene el bloque «MODELO ESTIMADO» **dos veces
y carácter a carácter idéntico**, en dos secciones consecutivas del mismo sobre.
Verificado:

    «MODELO ESTIMADO:» aparece 2 veces
    ¿los dos bloques son idénticos?  True
    secciones donde caen:  2 y 3

## Root cause

Al envolver `meg_reformulate` en el sobre de las cuatro etapas (BUG-0094), la
ecuación quedó en **dos sitios a la vez**: dentro de `_esp_meg` —la cabecera que
la función ya componía, y que incluía el bloque— y otra vez en el argumento
`ecuacion=`, que es su sitio en el sobre.

O sea que es un residuo del propio arreglo del 0094: se añadió el campo correcto
sin quitar el texto que ya lo llevaba.

## Impact

Bajo. No dice nada falso —los dos bloques son el mismo— pero duplica el bloque
más largo de la salida en la herramienta que se llama una vez por frecuencia
durante el barrido MEG, que es el uso iterativo que la documentación describe.

Y hay un coste que no es de espacio: una salida que repite invita a leer por
encima, que es justo lo contrario de lo que el sobre pretende (BUG-0094).

## Fix

Quitar la ecuación de `_esp_meg` y dejarla sólo en `ecuacion=`. La cabecera de
`_esp_meg` sigue diciendo lo suyo —qué se activó, en qué frecuencia, con o sin
testigo, desde qué `.pre`—, que es la ESPECIFICACIÓN y su sitio es la etapa 1.

Conviene comprobar de paso si el mismo residuo quedó en las otras herramientas
que se envolvieron a la vez.


---

## Cierre (2026-09-08)

Quitado el `{eq}` de la cabecera. La ecuación se queda sólo en `ecuacion=`, que
es la etapa 2; la cabecera sigue diciendo lo suyo —qué se activó, en qué
frecuencia, con o sin testigo, desde qué `.pre`—, que es la ESPECIFICACIÓN y su
sitio es la etapa 1. Comprobado que la etapa 1 no queda vacía.

## Y la comprobación de las otras cinco envueltas

El informe pedía mirar si el mismo residuo había quedado en las demás. **Primero
lo comprobé mal**: un `grep` de la variable que va en `ecuacion=` buscándola en
los otros campos. Dijo que las seis estaban limpias — **incluida
`meg_reformulate`, que era la que fallaba**.

El motivo es que allí la ecuación entra por **dos niveles de indirección**:

    ecuacion=eq                     ← uno
    especificacion=_esp_meg  →  _esp_meg = header  →  header = f"...{eq}..."

y la comprobación sólo recorría uno. Lo único que discrimina es **contar en la
salida real**, así que se ejecutan las seis:

    confirm_and_estimate        MODELO ESTIMADO × 1
    estimate_and_diagnose       × 1
    meg_reformulate             × 2  ⚠  → 1 tras el arreglo
    suggest_intervention_form   × 1
    build_model                 × 1
    record_version              × 0

**`meg_reformulate` era la única.**

### El cero de `record_version` NO es un defecto

Sale con cero porque usa la **ecuación estructural** del guion y no la del
prompt. Es deliberado: abre con `_mirar` —acepta un `.pre`— y la del prompt
imprime cada coeficiente con su error típico debajo, que desde un `.pre` no son
fiables (BUG-0090/0091). Usar allí la del prompt contradiría el contrato que esa
herramienta respeta.

Queda fijado en una prueba **para que un futuro «arreglo» de la asimetría no lo
rompa**: la asimetría es correcta y tiene su razón escrita.
