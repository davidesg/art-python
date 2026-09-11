---
id: BUG-0156
title: La llamada 2 con escalera da DOS recomendaciones distintas en la misma salida — la escalera dice 1a y el veredicto Q2/2008×3
status: fixed
severity: high
component: interventions
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - intervenciones
  - escalera
references:
  - BUG-0086
  - BUG-0138
  - BUG-0150
---

## Summary

`guided_intervention(..., escalera=True)` devuelve, en la misma respuesta:

    escalera   recomienda `1a` — escalón en Q4/2008, UN parámetro, «la menos mala»
    Veredicto  recomienda `Q2/2008×3` — TRES parámetros, otra fecha

Dos recomendaciones incompatibles, sin decir cuál gobierna ni por qué difieren.
El analista tiene que arbitrar entre dos partes de la misma salida.

## Root cause

Son **dos instrumentos con dos preguntas distintas** cuyos resultados se
publican como si fueran uno:

| | pregunta | acota por |
|---|---|---|
| configuraciones | ¿qué arranque y cuántos escalones admite el dato? | el MECANISMO (extiende el arranque hacia atrás) |
| escalera | ¿qué sofisticación justifica el dato? | la NAVAJA (lo más simple mientras se sostenga) |

Que discrepen no es un error: es información. Que se publiquen sin decir que
son dos preguntas, sí.

Y hay una asimetría que agrava la discrepancia: la escalera recorre `1a`, `1b`
y el episodio de L+1 escalones **desde la fecha del episodio**, mientras las
configuraciones exploran arranques hacia atrás. Así que las dos no consideran
el mismo conjunto de formas, y la comparación entre sus ganadoras no es una
comparación.

## Impact

Es el nodo donde el analista elige la forma, y la salida le da dos respuestas.
Con BUG-0138 la escalera sólo aparece cuando se pide —o sea, cuando el analista
ya duda— y lo que recibe entonces es más duda.

Sobre ITCER el analista se quedó con la del veredicto, y las notas registran
que la escalera «no concuerda».

## Y en el carril del instrumento era peor

`suggest_intervention_form(form="auto")` corría la escalera **antes** de calcular
el árbitro, y después construía con la longitud y el arranque del árbitro:

```python
esc = escalera_de_ockham(m_src, ep, dominio=dom)      # juzga L+1 desde ep
rec = esc.recomendado or …
… n_esc, at_esc = _mejor.n_escalones, _mejor.arranque_resid - 1 + _desfase
form, n_omega = {…, "2": ("step", n_esc)}[rec]        # construye n_esc desde at_esc
if rec == "2": at_0 = at_esc
```

**El peldaño que se evaluaba no era el peldaño que se construía.** Y el
comentario del árbitro, dos párrafos más arriba, ya decía que la longitud la fija
el mecanismo — la escalera no se había enterado.

## Fix

**1 · La escalera parte del arranque del MECANISMO.** `escalera_de_ockham` acepta
`at`, `n_alto` y `fecha_arranque`. Con ellos los tres peldaños comparan la misma
fecha que las configuraciones, y **el peldaño alto ES la configuración
ganadora** — con lo que a la escalera le queda la única pregunta que sabe
contestar: ¿hace falta tanta forma?

Se aplica en las dos puertas. En la del instrumento el bloque del árbitro pasa a
ir **antes** de la escalera, que es lo que hace que el peldaño juzgado y el
construido sean el mismo. Los defaults no cambian: sin `at`, la escalera camina
desde el primer extremo como siempre.

**2 · El informe dice de dónde parte**, y dice la verdad en los dos casos:

    *Los peldaños parten de **Q2/2008**, el arranque que el MECANISMO admite, y
    **no** del primer extremo del episodio…*

    *Los peldaños parten de **Q1/2010**, que es a la vez el primer extremo del
    episodio y el arranque que el MECANISMO admite: los dos instrumentos miran
    la misma fecha.*

Por eso hay dos banderas y no una: `alineada_con_configuracion` (el llamante
pasó el arranque) y `desplazada_del_episodio` (…y además difiere). Con una sola
el texto afirmaba una diferencia que la mitad de las veces no existe.

**3 · El veredicto nombra la discrepancia y da el criterio.** Cuando la navaja se
queda abajo y el mecanismo admite más de un escalón:

    ⚠ **Los dos instrumentos no dicen lo mismo, y es información.** El mecanismo
    admite `Q1/2010×2` (2 parámetros); la navaja se queda en `1a` (1 parámetro).

    No lo arbitra el AIC. **El mecanismo acota la FORMA** —qué arranque y
    cuántos escalones cabe que tenga el suceso— **y la navaja acota la
    SOFISTICACIÓN** —cuánta de esa forma sostiene el dato—. Que la forma
    admisible sea más rica que la que la navaja sostiene es exactamente lo que
    hay que discutir: o el suceso es más simple de lo que el mecanismo permite,
    o falta la información extramuestral que lo justifique.

Y cuando coinciden **también se dice**. Decir sólo las discrepancias deja al
lector sin saber si el silencio significa acuerdo o que nadie miró.

**4 · Y apunta a la tercera lectura.** Si ninguna forma de una sola fecha
resuelve el suceso, lo que falta puede no ser una forma más rica sino una vuelta
diferida: dos intervenciones y su ganancia NETA (BUG-0157). Sin esa línea, la
discrepancia manda a buscar en la dirección equivocada.

## Validation

`tests/test_bug_0156_dos_instrumentos_dos_preguntas.py`, con tres testigos
sintéticos construidos para cada estado:

* **desplazamiento** — primer tramo pequeño (activo, no extremo) seguido de uno
  grande: el detector de episodios empieza en el segundo, el mecanismo extiende
  hacia atrás y empieza en el primero. Es la forma exacta de ITCER. Se comprueba
  que la escalera suelta arranca en el episodio, la alineada en la
  configuración, y que el informe dice cuál de las dos cosas pasa;
* **discrepancia** — el mecanismo admite `×2` y la navaja se queda en `1a` sin
  ninguna razón para subir: la salida tiene que nombrarlo y dar el criterio;
* **acuerdo** — la salida lo dice igual.

Y una prueba estructural sobre el orden del carril del instrumento: el bloque
del árbitro tiene que ir antes de la escalera, o se vuelve a juzgar un peldaño y
construir otro.
