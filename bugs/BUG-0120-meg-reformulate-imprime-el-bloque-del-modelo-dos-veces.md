---
id: BUG-0120
title: meg_reformulate imprime el bloque del modelo estimado dos veces, idéntico, en dos secciones del mismo sobre
status: open
severity: low
component: mcp-tools
found_in: 0.2.0
fixed_in:
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
