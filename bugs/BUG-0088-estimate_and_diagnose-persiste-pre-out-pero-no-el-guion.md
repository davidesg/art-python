---
id: BUG-0088
title: estimate_and_diagnose persiste .pre/.out pero no el guion — el guion obligatorio queda obsoleto en silencio
status: fixed
severity: medium
component: guion
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David / sesión FOOD_UEM — escalera Ucrania
tags: [guion, mcp_server, estimate_and_diagnose, confirm_and_estimate, documentacion]
references:
  - src/art/mcp_server.py:1787 (estimate_and_diagnose — sin guion)
  - src/art/mcp_server.py:1798-1803 (docstring: «the same trio confirm_and_estimate writes»)
  - src/art/mcp_server.py:4126 (confirm_and_estimate — con guion_path + guion_*)
  - src/art/mcp_server.py:3776 (_derive_guion_path: «El guion es OBLIGATORIO»)
  - src/art/mcp_server.py:4114 (save_guion en _record_model)
  - bugs/BUG-0088-repro/repro.py
---

## Summary

`estimate_and_diagnose(inp_path, output_path)` persiste el trío `.pre`/`.out` «igual
que `confirm_and_estimate`» (su docstring lo dice literalmente: *«the same trio
confirm_and_estimate writes, so a model estimated through this clean path is not left
without artefacts»*), pero **no escribe el guion**: no lleva `guion_path` y su cuerpo
no llama a `save_guion`. Mientras, `_derive_guion_path` declara el guion
**OBLIGATORIO** («documentar el proceso no es un adorno del método, es el método»).
Resultado: un modelo estimado por la vía limpia queda con artefactos y sin su entrada
de guion, y el guion se queda obsoleto **en silencio** — sin aviso ni recordatorio.

## Impact

El guion (el registro de decisiones que el método declara obligatorio) se desincroniza
sin que nadie lo note. En la sesión FOOD_UEM, la escalera de Ucrania (n=1…5) y las
intervenciones Covid/2023/10-2022 se construyeron por `estimate_and_diagnose` y por
`fue` directo; el guion quedó con 3 entradas viejas y hubo que reescribirlo a mano. El
analista que confíe en el guion como mapa del proceso ve un mapa que no refleja lo que
de verdad se hizo.

## Reproduction

`bugs/BUG-0088-repro/repro.py` — sintético, determinista, sin datos ni motor. Inspecciona
las firmas y cuerpos de las dos herramientas:

```
estimate_and_diagnose — parámetros de guion: NINGUNO
confirm_and_estimate  — parámetros de guion: [guion_path, guion_name, guion_decision,
                          guion_rationale, guion_problems, guion_next]
estimate_and_diagnose — llama a save_guion: False
FALLA (exit 1)
```

## Root cause

El guion solo lo escriben las herramientas guiadas (`confirm_and_estimate` →
`_record_model` → `save_guion`, más `record_version`, `guion_node`, `abandon`).
`estimate_and_diagnose` fue pensada como vía «limpia» de estimación + diagnóstico y
replica el trío de artefactos de `confirm_and_estimate`, pero se quedó **sin** la parte
del guion: sin parámetro `guion_path` y sin `save_guion`. El docstring incluso anuncia la
paridad de artefactos, reforzando la impresión de equivalencia que el guion desmiente.

## Fix

O bien `estimate_and_diagnose` acepta los mismos parámetros de guion y registra la
entrada cuando `output_path` está presente (la paridad que su docstring ya promete), o
bien, si se quiere mantener como herramienta de solo-diagnóstico, deja de persistir
`.pre`/`.out` (que es lo que crea la divergencia) o avisa explícitamente de que el guion
no se actualiza. Lo inconsistente hoy es persistir artefactos y no el registro.

## Validation

Con el arreglo, `estimate_and_diagnose(output_path=...)` deja la entrada de guion como
`confirm_and_estimate`, y el repro sale 0. Sobre la sesión FOOD_UEM, la escalera de
Ucrania habría quedado registrada peldaño a peldaño sin intervención manual.

---

## Fix (aplicado, 2026-09-05)

De las tres salidas que el reporte proponía se toma la primera —`estimate_and_diagnose`
acepta los mismos parámetros de guion y registra la entrada cuando hay
`output_path`— porque es la que mantiene la promesa del docstring. Lo
inconsistente era persistir los artefactos y no el registro; quitar los
artefactos habría quitado también la razón de ser de la herramienta, y avisar de
que el guion no se actualiza es documentar el defecto en vez de cerrarlo.

Dos detalles:

- **`guion_path` se DERIVA si no se da**, igual que en `confirm_and_estimate`. El
  guion está declarado obligatorio, así que no puede depender de que el llamante
  se acuerde de pedirlo.
- **`lam` se relee del modelo** (`m.boxlam`): esta herramienta no recibe la
  especificación, la carga del `.inp`.

Y si el registro falla, **se dice**. Documentar no puede tumbar una estimación
válida —por eso va en un `try`— pero tampoco puede fallar en silencio, que es
exactamente el defecto que este arreglo viene a cerrar: la salida lleva
`⚠ guion NO registrado (…). El modelo está en disco y el guion no lo refleja.`

## Validation — resultado

El repro sale 0. Se reescribió para comprobar el **efecto** y no la firma: la
versión anterior miraba los parámetros y si `save_guion` aparecía en el cuerpo,
y una firma con parámetros de guion que no escriben nada habría pasado igual.
Ahora estima de verdad y comprueba qué queda en disco:

```
artefactos y registro: ['R88_guion.json', 'R88_m00.out', 'R88_m00.pre']
.pre=True  .out=True  guion=True
entradas en el guion: 1  (PC1)
```

`tests/test_bug_0087_0088_umbral_y_guion.py`, 17 pruebas (compartidas con
BUG-0087), incluidas: que sin `output_path` no escribe nada —sin artefactos no
hay nada que registrar—, que dos llamadas encadenan versiones, que las dos vías
exponen los mismos parámetros, y que un fallo del registro se reporta en vez de
callarse.
