---
id: BUG-0173
title: No hay forma de EXTENDER la muestra de un modelo — el encadenado que el propio método pide se hace editando el `.inp` a mano
status: fixed
severity: medium
component: mcp-tools
found_in: 0.1.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — run 3 de SF_MEG, incidencia C-26
tags:
  - datos
  - contrato-de-ficheros
  - hueco
references:
  - BUG-0162
  - BUG-0170
---

## Summary

El diseño del run 3 era el del método: estimar sobre 2002-01…2019-12, y después
**extender la muestra** hasta 2026-05 incorporando los episodios nuevos (covid,
crisis energética) por el nodo de intervención, **encadenando por el `.pre`**.

No hay herramienta que lo haga. Hubo que editar a mano el número de
observaciones y el bloque de datos del `.inp`.

## Por qué importa más de lo que parece

Extender la muestra es una operación **del método**, no una comodidad:

* es como se valida un modelo contra lo que vino después;
* es como se incorpora un episodio nuevo sin rehacer la identificación;
* y es exactamente lo que el convenio de ficheros promete cuando dice que el
  `.pre` encadena modelos.

Que la única vía sea editar el fichero a mano tiene dos costes. El obvio: se
puede equivocar uno. Y el que no se ve: **lo que se edita a mano no queda en el
guion**, así que el recorrido pierde el punto donde la muestra cambió — que es
justo la información que hace falta para leer después por qué el modelo se movió.

## La familia

Es el tercer hueco de la misma forma encontrado en esta sesión, y conviene verlos
juntos porque el patrón es uno:

| | lo que no se podía |
|---|---|
| BUG-0162 | **modificar** una intervención (sólo añadir) |
| BUG-0170 | **añadir** un determinista a un modelo existente |
| BUG-0173 | **extender** la muestra de un modelo existente |

Las tres son lo mismo: el sistema sabe CONSTRUIR un modelo y sabe ENCADENAR
estructura, pero no sabe **modificar** lo que ya hay. El `.pre` transporta la
especificación hacia delante y cualquier cambio que no sea «añadir al final»
obliga a salirse del sistema.

Y en el mismo run apareció una cuarta cara: tampoco hay forma de **cambiar un
escalón por un impulso** — se quitó a mano de la especificación y se reconstruyó
con `guided_intervention`. (BUG-0162 abrió `rehacer=True` después de esa corrida.)

## Fix

`pipeline.extiende_muestra(pre_path, datos, output_inp)` y la herramienta
`extend_sample` que la publica. Conserva **todo**: deterministas con sus
posiciones, ARMA regular y estacional, operadores de frecuencia fija, `ifadf`,
μ, Box-Cox y `refactor`. Los valores estimados quedan como SEMILLAS, que es lo
que un `.pre` es.

**No reestima**, y lo dice: extender la muestra y reestimar son dos decisiones, y
la segunda es del analista. Y registra el cambio de muestra en el guion, que era
la mitad del defecto — lo editado a mano no dejaba rastro.

Sobre el caso que lo motivó, `ES_CPI_A_m06` → etapa B:

    +77 observaciones → n = 293, hasta 05/2026
    Especificación conservada entera: 10 deterministas, d=1, D=0, λ=0.0, μ=sí,
    ifadf=[0, 0, 0, 1, 0, 0, 0]

### Las dos negativas, que son lo que le da valor

* **Si la serie nueva no empieza donde la del modelo, se niega.** Extender por el
  principio desplaza el `at` de todas las intervenciones y cada suceso quedaría
  en otra fecha — que es BUG-0172 por otra puerta.
* **Si el tramo común no coincide, se niega**, diciendo cuántas observaciones
  difieren y dónde está la mayor. No es esta serie extendida: es otra, y heredar
  una especificación ajustada sobre otros datos no significa nada.

Las dos llegan como **regla y no como avería** —sin traceback—, que es la lección
de BUG-0159. Y extender con la misma longitud **no** es un error: cero
observaciones nuevas es el resultado legítimo de refrescar un fichero que aún no
las trae.

## Validation

Extender un `.pre` con n observaciones nuevas da un `.inp` con la misma
especificación —mismos deterministas, mismo ARMA, mismas intervenciones, mismo
`ifadf`— y n más observaciones. Y el guion registra el cambio de muestra.
