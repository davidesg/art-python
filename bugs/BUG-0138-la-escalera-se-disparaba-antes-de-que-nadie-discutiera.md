---
id: BUG-0138
title: La escalera de Ockham se disparaba siempre en el carril guiado — tres estimaciones antes de que nadie hubiera discutido la forma, y la figura que llevaba la sugerencia no se enseñaba
status: fixed
severity: medium
component: mcp-tools
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-10
reporter: David
tags:
  - intervenciones
  - carril-guiado
references:
  - BUG-0135
  - BUG-0086
---

## Summary

La llamada 2 de `guided_intervention` —«¿qué forma admite el dato?»— hacía tres
cosas: identificaba las configuraciones, **corría la escalera de Ockham** y daba
el veredicto. La escalera **estima tres modelos rivales**, y se disparaba
siempre.

Decisión del analista en el censo de figuras, sobre el papel de cada figura del
nodo:

> *«La superposición lleva la sugerencia y la escalera es el argumento si es
> necesario. El analista pregunta qué forma es la que mejor se adapta a los
> datos; la herramienta le dice una forma. El analista replica con otra forma y
> la herramienta presenta este gráfico como argumento. En modo automático es
> fundamental como información, pero en modo guiado es más argumental.»*

Y hay una razón técnica que lo respalda, y sólo se ve comparando las dos figuras:

| | superposición | escalera |
|---|---|---|
| responde a | «¿qué forma se adapta?» | «¿por qué ésta y no la que propongo yo?» |
| cuesta | **nada** — no estima, dibuja una hipótesis | **tres estimaciones** |
| admite una forma que el analista invente | **sí** — se le pasan los ω | **no** — sólo su menú 1a/1b/2 |
| separa amplitud de forma | **sí**, con dos números | no |

**Para la réplica del analista —«¿y si es otra forma?»— contesta la
superposición, no la escalera**, que sólo sabe comparar sus tres peldaños. Y sin
embargo la figura que la llamada 2 devolvía era la de la escalera: **la que
lleva la sugerencia no se enseñaba**.

## Fix

`guided_intervention(..., escalera: bool = False)`.

**Por defecto** (carril guiado): configuraciones + veredicto, **con la
superposición de la forma sugerida como figura**, y una línea que ofrece el
argumento con su llamada exacta:

> **¿No te convence esta forma?** La escalera de Ockham es el argumento: estima
> las rivales EN ORDEN y dice qué justifica subir de peldaño —Treadway,
> inadecuación, dominio—, con el AIC mirando y sin arbitrar. Cuesta tres
> estimaciones, así que se pide.

**Con `escalera=True`**: el comportamiento de antes, y la figura vuelve a ser la
de los peldaños.

**El carril autónomo no se toca.** Allí la escalera sigue corriendo siempre, por
`suggest_intervention_form(form="auto")`, y es lo correcto: no hay quien
discuta, así que su información **es** el criterio.

## Validation

```
sin escalera (por defecto)   1 imagen · escalera en el texto: NO · la ofrece: SÍ
con escalera=True            1 imagen · escalera en el texto: SÍ
```

Las configuraciones y el veredicto están en los dos.

## Lo que este cambio pone en su sitio

**La decisión antes que el cálculo**, que es lo que el carril guiado dice ser.
Antes se estimaban tres modelos para contestar a una objeción que el analista no
había hecho todavía.
