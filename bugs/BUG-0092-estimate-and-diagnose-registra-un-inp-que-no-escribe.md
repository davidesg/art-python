---
id: BUG-0092
title: `estimate_and_diagnose` registra en el guion un `.inp` que nunca escribe — la terna queda rota y el camino de vuelta del analista apunta a un fichero inexistente
status: fixed
severity: medium
component: guion
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-05
reporter: Claude — estudio del contrato de ficheros; defecto propio de 2026-09-04
tags: [contrato, guion, artefactos]
references:
  - docs/ESTUDIO-contrato-de-ficheros-y-semillas.md §4-V4 y §4-V5
  - src/art/mcp_server.py (estimate_and_diagnose, _persist_pre_out)
  - BUG-0088 (que introdujo el registro)
---

## Summary

Al cerrar BUG-0088 se añadió el registro del guion a `estimate_and_diagnose`,
con `inp_path=output_path`. Pero `_persist_pre_out` escribe **`.pre` y `.out`**
en ese basename y **no el `.inp`**. La entrada del guion apunta a un fichero que
no existe:

```
ficheros: ['S.inp', 'S_m00.out', 'S_m00.pre', 'FOOD_UEM_guion.json', 'figs']
guion.inp_path = S_m00.inp   ¿existe? False
hermanos: .pre=True  .out=True
```

Defecto propio: añadí el registro sin comprobar que la ruta registrada
resolviera.

## Impact

Rompe justo el camino que el guion existe para sostener. El analista vuelve a un
nodo para retomar desde ahí, y la ruta asociada no está. Y como el `.pre` y el
`.out` sí están, la carpeta *parece* completa.

En el corpus real, **4 de 15** entradas con `inp_path` apuntan a un fichero
ausente. Parte es higiene de sesión —modelos movidos— pero **el guion no lo
detecta ni lo dice**.

Contrasta con `confirm_and_estimate`, que hace lo correcto y es el patrón de
referencia:

```python
_write_inp(ts, m, output_path)      # escribe el .inp de ESTA versión
_, m = _load_fitted(output_path)    # y estima DESDE ÉL
```

## Fix (propuesto)

Dos partes.

1. **La terna se completa.** `estimate_and_diagnose` no construye una
   especificación nueva —estima una que ya existe— así que hay dos lecturas
   defendibles: copiar el `.inp` de origen a `output_path` (terna completa y
   autoconsistente), o registrar `inp_path` = el `.inp` de origen. La primera
   mantiene el invariante «cada entrada del guion apunta a un `.inp` cuyos
   hermanos son su `.pre` y su `.out`», que es el que hace navegable el grafo.
2. **El guion comprueba.** Al registrar, verificar que `inp_path` resuelve y
   avisar si no —igual que ahora se avisa cuando el registro falla—. Un mapa que
   apunta a ficheros ausentes sin decirlo es peor que no tenerlo.

## Validation

Que tras `estimate_and_diagnose(inp, out)` existan los tres ficheros del
basename de `out`, que `inp_path` del guion resuelva, y que registrar una ruta
que no resuelve produzca un aviso visible.

---

## Fix (aplicado, 2026-09-05)

**1. La terna se completa copiando el `.inp` fuente, byte a byte.** Nuevo
`_asegura_inp_de_la_terna(inp_path, output_path)`.

El detalle que decide la implementación: se **copia el fichero**, no se
reserializa el modelo. `estimate_and_diagnose` tiene delante el modelo ya
ajustado, y escribirlo con `_write_inp` bajo nombre de `.inp` pondría las
estimaciones donde van las semillas — la trampa de BUG-0027 dentro de un `.inp`,
que ya se pisó una vez en esta misma sesión (las SE salieron 2.6× de más). Una
copia literal no puede caer en ella, y hay una prueba que lo fija: reestimar el
`.inp` copiado no dispara el aviso de BUG-0090.

**2. No se pisa una especificación ajena.** Si el destino ya existe con otro
contenido, **no se toca** y se dice: un `.pre` o un `.out` se rehacen estimando,
pero una especificación perdida no se recupera. Se avisa además de que la terna
queda descuadrada, porque los otros dos sí se reescriben.

**3. El guion comprueba lo que registra.** `_record_to_guion` verifica la terna y
distingue dos gravedades:

- **falta el `.inp`** → ⚠ *«el `.inp` registrado no existe: desde este nodo no se
  puede reestimar»*. Es lo que rompe la operación que el guion existe para
  sostener.
- **falta el `.pre` o el `.out`** → una nota, sin alarma: se rehacen estimando.

No bloquea —registrar mal es mejor que no registrar— pero deja de ser silencioso.

## Validation — resultado

`bugs/BUG-0092-repro/repro.py` sale 0 y comprueba los cuatro puntos: la terna
completa, que el `inp_path` del guion resuelve, que la copia es byte a byte del
fuente, y que registrar una ruta ausente se dice.

```
== A. La terna del basename de salida     .inp: sí   .pre: sí   .out: sí
== B. inp_path = R92_m00.inp   ¿existe? True
== C. copia byte a byte del fuente: True
== D. nota: *guion: x v1*  ⚠ **el `.inp` registrado no existe** (...)
```

`tests/test_bug_0092_terna_completa.py`, 9 pruebas, incluida la que fija que la
copia es la especificación y no el ajuste, y la que comprueba que un `.inp`
ajeno no se pisa.

## Lo que NO arregla

Las **4 de 15** entradas del corpus real que apuntan al vacío siguen apuntando
al vacío: son registros históricos de modelos que se movieron. Lo que cambia es
que a partir de ahora se detecta al escribirlas. Reparar las viejas es otra
tarea, y probablemente no valga la pena.
