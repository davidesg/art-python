---
id: BUG-0225
title: Paso 1 (Box-Cox): «la escala original ya tiene varianza homogénea (corr=0.305)» con corr = −0,305, y «la dispersión CAE con el nivel → se pasa»
status: fixed
severity: low
component: describe
found_in: 0.2.3.dev0 @088933d
fixed_in: 0.2.3.dev0
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO del IPC de España (P02, Econometría Aplicada UCM)
tags:
  - box-cox
  - texto
  - guiado
references:
  - src/art/describe.py:235
  - bugs/BUG-0225-repro/repro.py
---

## Summary

Con IPC_ES las correlaciones media-dt son −0,305 (nivel) y −0,495 (log). El texto:
- «La escala original ya tiene varianza homogénea (corr=0.305)» — pierde el signo, y una
  correlación de 0,3 en valor absoluto no es «homogénea»;
- «la dispersión CAE con el nivel → se pasa» en las dos líneas: «se pasa» no dice de qué.

## Impact

Es la primera pantalla del carril guiado y la primera decisión que se enseña (apartado 2 de la P02); el alumno copia la frase.

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0225-repro/repro.py` (recorre el carril guiado de `IPC_ES.inp`, 2002:01-2019:12, desestacionalizado, en un directorio temporal), bloque **0225**. Guion real del caso: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/IPC_ES/IPC_ES_guion.json` del repositorio del curso.

## Root cause

`describe.py:235` formatea `corr_raw` sin signo y usa una plantilla de «homogénea» para cualquier correlación que no sea positiva.

## Fix

Citar la correlación con su signo y decir lo que significa: «la dispersión no crece con el nivel (corr = −0,31): el gráfico no pide logaritmos». Cambiar «se pasa» por algo legible («no pide transformar»).

## Validation

Repro, bloque 0225: el texto lleva −0.305 y no dice «homogénea» ni «se pasa».

## Resolution (2026-10-08)

`describe.py` (Box-Cox): the per-scale reading says what is meant —"la dispersión CRECE con el nivel → esta escala no la estabiliza" / "CAE → esta escala transforma de más"— and the closing sentence quotes both correlations WITH their sign ("En la escala original la dispersión no crece con el nivel (corr = −0.305), y el log no la hace más estable (corr = −0.495): el gráfico no pide logaritmos. Si el dominio los pide, decide el dominio."). The "log reduces" sentence also keeps the sign.

Repro: `bugs/BUG-0225-repro/repro.py`. Tests: `tests/test_bug_0225_0231_guiado_ipc_es.py`.
