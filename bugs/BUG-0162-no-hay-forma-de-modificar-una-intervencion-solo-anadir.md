---
id: BUG-0162
title: No hay forma de MODIFICAR una intervención — todos los constructores hacen append, y reformular depende de que el analista se acuerde de volver al `.pre` anterior
status: fixed
severity: high
component: interventions
found_in: 0.1.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — «no tengo claro cómo funciona cuando hay que reformular la intervención»
tags:
  - intervenciones
  - contrato-de-ficheros
  - superficie
references:
  - BUG-0090
  - BUG-0150
  - BUG-0159
  - BUG-0161
  - BUG-0164
---

## Summary

Reformular una intervención —cambiar la forma funcional, bajar el orden de ω— es
la operación más frecuente del nodo. **No existe.** Todos los constructores
hacen lo mismo:

```python
new_itvs = list(m_src.interventions or []) + [itv]     # mcp_server.py:7907
```

Append. No hay quitar, no hay sustituir, no hay cambiar el orden de una que ya
está.

## Cómo se reformula hoy

Por el convenio de ficheros: el analista vuelve al **`.pre` anterior a la
intervención** y construye la forma nueva desde ahí. Y funciona — es la cadena
`.inp(t−1) → .pre(t−1) → .inp(t)`, y es correcta.

El problema es que es **implícito**:

1. Ninguna herramienta lo dice. `guided_intervention` no menciona en ningún
   sitio que para reformular hay que apuntar al modelo de ANTES; el analista
   que apunta al modelo actual obtiene dos intervenciones sobre el mismo
   suceso, y el síntoma es un ω no significativo y una covarianza casi
   singular, no un error.
2. Depende de que ese `.pre` siga existiendo y de que se sepa cuál era. En una
   cadena de siete versiones, «el de antes de la intervención de 2008» no está
   escrito en ningún sitio: hay que reconstruirlo mirando los ficheros.

Es la misma enfermedad de BUG-0159 y BUG-0160: **una propiedad que se sostiene
porque todo el mundo se acuerda es una costumbre, no una propiedad del sistema.**

## Y la pieza que quita ya está escrita

`escalera.hereda_del_base(model, at_estudiado, ventana)` — de BUG-0150 — hace
exactamente esto:

> *«Lo que se retira es SÓLO la intervención que cae en la misma fecha —o dentro
> de `ventana` períodos—, que es el caso de rehacer la forma de un suceso ya
> intervenido. Devuelve `(heredadas, retiradas)` para que la salida pueda decir
> cuál se quitó: retirar una intervención en silencio es cambiar el modelo base
> sin avisar.»*

«El caso de rehacer la forma de un suceso ya intervenido» — está escrito en el
docstring. La función la usan `escalera_de_ockham` y `evalua_configuraciones`
para comparar candidatos **por dentro**, y la superficie no la ofrece.

Es la tercera cara del patrón de BUG-0090: **la capacidad está abajo, el nodo no
la nombra.** El analista tiene que reimplementarla a mano con ficheros, teniendo
la función delante.

## Impact

Alto. Reformular es la operación central del método iterativo —Box-Jenkins es un
ciclo de reformulación— y es la única que el nodo no sabe hacer. Las
consecuencias son de tres clases:

* **Silenciosa**: apuntar al fichero equivocado duplica la intervención sobre el
  mismo suceso. El modelo estima, la diagnosis pasa, y lo que queda es un ω no
  significativo que se lee como «esta forma no vale» cuando lo que pasa es que
  está dos veces.
* **De trazabilidad**: el guion registra la cadena de modelos, pero una
  reformulación hecha volviendo atrás aparece como una rama, no como una
  corrección. Se pierde justo la información que BUG-0110 quiere conservar.
* **De coste**: en el estudio de campo, 51 % de las intervenciones guiadas son
  multi-ω, y llegar a la forma buena casi siempre pasa por probar una y
  rehacerla.

## Repro

```python
import ast, pathlib
src = pathlib.Path("src/art/mcp_server.py").read_text()
# ningún sitio construye la lista de intervenciones quitando una
assert "hereda_del_base" in src, "la superficie no usa la pieza que retira"
```

Falla: `hereda_del_base` sólo aparece en `escalera.py` y `configuracion.py`.

## Fix

**`rehacer: bool = False`** en `suggest_intervention_form` y en
`guided_intervention`. Con él se llama a `hereda_del_base(m_src,
at_estudiado=at_0, ventana=max(1, n_omega))`, se construye la forma nueva sobre
las heredadas, y **se dice cuál se retiró**:

    ♻ **Se ha REHECHO la intervención de este suceso.** Retirada:
    `step[obs 71]` (1 ω). En su lugar va `step` con 3 ω en obs 71. El resto del
    modelo —las demás intervenciones, la estructura y μ— se hereda intacto.

El docstring de `hereda_del_base` ya decía por qué hace falta esa frase: retirar
una intervención en silencio es cambiar el modelo base sin avisar.

**Y no retirar cuando se pidió también se dice.** Si `rehacer=True` no encuentra
nada en la ventana, se ha AÑADIDO, no sustituido, y callarlo es el mismo defecto
por el otro lado.

**La otra mitad, que es la que evita el fallo silencioso.** Sin `rehacer`, si ya
hay una intervención de suceso en la ventana, se avisa:

    ⚠ **Ya había una intervención en este suceso** (`step[obs 71]`) y ésta se ha
    AÑADIDO encima. Dos intervenciones sobre el mismo suceso se reparten el
    efecto: el síntoma es un ω que deja de ser significativo, no un error.

    Si lo que querías era **reformular**, repite con `rehacer=True` […]. Si de
    verdad son **dos sucesos distintos** tan juntos, esto está bien: sigue.

No se prohíbe —puede que de verdad sean dos sucesos— pero deja de ser mudo. El
`.pre` anterior sigue siendo la vía canónica; esto la hace alcanzable sin
depender de la memoria.

## Lo que salió al probarlo: BUG-0164

Ejercitar la cadena real `m00.pre → m10 → rehacer` destapó que **las puertas del
nodo rechazaban un `.pre`** desde el arreglo de BUG-0159. Está levantado aparte y
arreglado; sin él nada de esto era alcanzable.

## Validation

`tests/test_bug_0162_rehacer_no_solo_anadir.py`. Los cuatro estados —añadir con
aviso, rehacer, rehacer sin nada que rehacer, y que el resto del modelo
sobreviva— y dos que son el argumento:

* **rehacer conserva las demás intervenciones.** Con una segunda intervención
  lejos del suceso, rehacer la de cerca no la toca. Es lo que hace legítimo el
  atajo frente a volver al `.pre` anterior, que las perdería todas las
  posteriores.
* **rehacer ≡ volver al `.pre` de antes.** Las dos rutas dan el mismo modelo.
  La comparación de los ω es **relativa y no absoluta**: arrancan de semillas
  distintas —una del óptimo de `m10`, otra del base— así que convergen al mismo
  óptimo, no a los mismos bits. Medido, 1,3e-4 sobre un ω de −606,7, o sea 2e-7
  relativo. Exigir bits idénticos habría convertido la prueba en una medida de
  la tolerancia del optimizador.
