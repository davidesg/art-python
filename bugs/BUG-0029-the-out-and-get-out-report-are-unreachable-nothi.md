---
id: BUG-0029
title: The .out and get_out_report are unreachable — nothing routes to them, every next-step hint chains through .pre, and art's own instructions present .inp and .pre as interchangeable
status: fixed
severity: high
component: mcp-tools
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - file-convention
  - discoverability
  - out-report
references:
  - src/art/mcp_server.py:1-11 (la cabecera del módulo)
  - src/art/mcp_server.py:3937 (get_out_report — su única mención)
  - drtran-python/src/drtran/mcp_server.py:80-102 (el convenio, donde SÍ está escrito)
  - drtran-python/docs/LADDER_AS_OPTIMISATION.md (detalle y mediciones)
  - TODO.md:1001, 1074, 1082 («toca el convenio de ficheros», tres veces)
  - bugs/BUG-0027-… (la covarianza degenerada, que es la consecuencia medible)
  - bugs/BUG-0029-repro/repro.py
---

## Summary

El `.out` guarda los parámetros **con sus errores típicos**, `sigma` con el suyo,
la verosimilitud y las matrices de **covarianza y correlación completas** — todo
lo necesario para reformular. `get_out_report` existe para leerlo.

**Nada en el servidor de art menciona ninguno de los dos.** Medido:

| en `src/art/mcp_server.py` | |
|---|---|
| menciones de `get_out_report` | **1** — su propia definición |
| sugerencias que dirigen al `.out` | **0** |
| avisos de no reestimar sobre el `.pre` | **0** |
| menciones de que los errores típicos vienen del `.out` | **0** |
| rutas `.pre` en las sugerencias de paso siguiente | **3** |

Y la cabecera del módulo presenta los dos ficheros como **intercambiables**:

> *«Todas las herramientas trabajan sobre ficheros `.inp` (modelo + serie) o
> `.pre` (modelo ya estimado). Sin estado en memoria — cada llamada es
> idempotente.»*

Eso es lo contrario del convenio. `.inp` y `.pre` no son dos formatos de entrada
equivalentes: son **dos momentos distintos del mismo fichero**, y sólo uno de los
dos sirve para estimar. La frase «cada llamada es idempotente» invita
explícitamente a reejecutar sobre el `.pre`.

## El convenio SÍ existe — en otro escalón

Está escrito, y con precisión, en `drtran-python/src/drtran/mcp_server.py:80`:

```
EL CONVENIO DE FICHEROS, que es lo que hace subible la escalera:
  .inp  una ESPECIFICACIÓN. Los valores son SEMILLAS, un punto de partida.
  .out  el registro completo de una estimación Y SU DIAGNOSIS.
  .pre  ese mismo .inp con las estimaciones como nuevos valores iniciales:
        un ÓPTIMO, en forma reejecutable. Invariante comprobable: corre fue
        sobre un .pre y los números NO se mueven.
  Un .pre que se TOCA vuelve a ser un .inp — editar la especificación deshace
  la afirmación de que esos valores son su óptimo.
  … Lo que NO haces nunca es escribir un .pre: sólo el programa que estimó puede
  afirmar un óptimo, y el fichero no lleva marca de quién lo escribió.
```

y la secuencia, con el paso que aquí falta marcado:

```
  --fue estima-->                            .out + .pre   <- AQUÍ nace el óptimo
  --el analista reformula LEYENDO EL .out--> .inp
```

**`drtran` es un escalón POSTERIOR.** Los tres ficheros **nacen en art**, y art no
dice nada de esto. El escalón que hereda el convenio lo documenta; el que lo crea,
no.

`TODO.md` ya lo señala tres veces —líneas 1001, 1074 y 1082, «toca el convenio de
ficheros», «no debería hacerse sin leerlo»— siempre como obstáculo de otra ficha,
nunca como trabajo propio.

## Impact

Alta, y es la causa estructural de BUG-0027 en el uso real.

Quien siga el flujo que art sugiere —todas las rutas por `.pre`— nunca descubre
el `.out`, encadena reestimando sobre el óptimo, y recibe la covarianza
degenerada. Los errores típicos correctos estaban en el `.out` desde el momento
de la estimación.

**Medido en el uso**: en una réplica completa de tres series, con decenas de
modelos estimados, **no se abrió un solo `.out`**. Los errores típicos se
recalcularon a mano reestimando sobre `.pre` (obteniendo los degenerados), y
llegaron a publicarse cifras erróneas — la caracterización de un AR(2) se reportó
con la incertidumbre inflada ×2,2. El fichero con el valor correcto estaba en el
mismo directorio.

Peor: siguiendo la cadena sugerida se llegó a **escribir `.pre` a mano** (con
`_write_inp` + copia), que es lo que el convenio prohíbe expresamente — y el
modelo así producido se quedó **sin `.out`**, perdiendo su registro de diagnosis.

## Reproduction

```
python3 bugs/BUG-0029-repro/repro.py
```

Cuenta las menciones sobre el propio fuente y localiza el convenio en el otro
repositorio. No necesita datos.

## Fix

Nada de esto es difícil; es que no está.

1. **Escribir el convenio en la cabecera del servidor de art**, que es donde los
   tres ficheros nacen. Reemplazar la frase de «entradas intercambiables» por la
   distinción real: `.inp` especificación y semillas, `.out` registro de la
   estimación **y de dónde se leen parámetros y errores típicos**, `.pre` óptimo
   reejecutable que sirve de semilla al escalón siguiente y **no** para
   reestimar.
2. **Cablear `get_out_report`**: que `confirm_and_estimate` y
   `estimate_and_diagnose` lo nombren en su bloque de paso siguiente, junto al
   `.out` que acaban de escribir. Hoy la línea dice «*resultados: …out*» y ahí se
   acaba — no dice que se pueda leer, ni con qué.
3. **Que las sugerencias distingan el uso**: `.pre` cuando lo que se quiere es
   encadenar (semilla del escalón siguiente, `base_pre_path`), `.inp` cuando lo
   que se quiere es estimar.
4. **Portar `LADDER_AS_OPTIMISATION.md` a art**, o referenciarlo, para que el
   escalón que crea los ficheros tenga a mano la explicación y las mediciones.

Como red de seguridad, y ya implementado por BUG-0027: cuando la covarianza sale
degenerada el aviso remite al `.inp`. Pero eso corrige el síntoma tarde; la cura
es que la ruta correcta esté escrita donde se toma la decisión.

## Lo aplicado (2026-08-27)

1. **El convenio, escrito en `_INSTRUCTIONS`** — sección propia «EL CONVENIO DE
   FICHEROS», con los tres momentos del fichero, las **tres reglas** («los
   errores típicos se leen del `.out`, nunca de reejecutar un `.pre`», «nunca
   escribas un `.pre`», «un `.pre` que se toca vuelve a ser un `.inp`»), la
   secuencia completa marcando el eslabón que se pierde —*reformular leyendo el
   `.out`*— y la remisión a BUG-0027 con su medición.
2. **La cabecera del módulo, corregida.** Ya no dice que `.inp` y `.pre` sean
   entradas intercambiables ni que «cada llamada es idempotente», que era la
   invitación a reestimar sobre el óptimo.
3. **La línea de artefactos, cableada.** Donde decía «*resultados: x.out*» —y
   nadie lo abría— ahora dice qué hay dentro y con qué se lee:
   *«Parámetros, errores típicos y covarianza en `x.out` — se leen con
   `get_out_report(...)`, no reestimando el `.pre`»*, y nombra el `.pre` como
   *semilla del siguiente paso*, que es su función.
4. **El pie de estado** (ARCHITECTURE_REVIEW §5.2) ofrece `get_out_report` como
   puerta en toda salida, en cualquier etapa.

`tests/test_bug_0029_file_convention.py`, 12 casos: que el convenio y sus tres
reglas están enunciados, que nombran la herramienta y el defecto medido, que la
cabecera ya no dice «intercambiables», que la salida dirige al `.out` explicando
para qué sirve cada fichero, y que el `.out` efectivamente trae la covarianza y
los errores típicos que se estaban recalculando a mano.
