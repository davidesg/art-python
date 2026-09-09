---
id: BUG-0127
title: La figura de raíz unitaria duplicaba la tabla del texto y pintaba en verde el d=2 que la recomendación desaconseja
status: fixed
severity: medium
component: describe
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - doctrina
  - contexto
references:
  - BUG-0002
  - BUG-0122
  - BUG-0126
---

## Summary

`describe_unit_root` devolvía, además de su tabla en markdown, **la misma tabla
dibujada con matplotlib**, con las filas coloreadas por veredicto. Dos problemas,
y el segundo es el que la convierte en defecto.

**1. No enseñaba nada que no estuviera en el texto.** Las mismas nueve columnas,
los mismos ✓/✗, los mismos p-valores. 24.308 bytes de imagen para que el modelo
leyera lo que ya tenía en texto plano, y para que el analista viera peor lo que
el markdown enseña mejor en el terminal.

**2. Contradecía a la recomendación que la acompaña.** Pintaba **en verde** la
fila `d=2` —«estacionaria ✓»— mientras el texto, tres párrafos más arriba, dice:

> *«⚠ Punto de partida recomendado: d = 1, no 2. Un paso cada vez. […] saltar a
> d=2 contesta una pregunta que nadie ha hecho […] la estacionalidad todavía no
> se ha contrastado […] sesga el contraste hacia NO rechazar la raíz unitaria —
> que se lee como “diferencia otra vez”.»*

**El color decía lo contrario que la doctrina, y el color es lo que se mira
primero.** Sobre RATIO —una serie con estacionalidad de F=216— la figura invitaba
a `d=2` en verde; el análisis correcto se cierra en `d=1`, y el DCD sobre el
modelo estimado lo confirmó por los dos lados (LR=76,6 por abajo).

## Impact

**Medio, y en el peor sitio: el nodo `d`.** Sobrediferenciar es uno de los dos
errores que esta escuela persigue —el par DCD/MEG existe para eso— y el
instrumento lo estaba sugiriendo visualmente en el momento de decidirlo.

Agravante de contexto: la figura se disparaba también desde
`guided_identification`, que tiene **167 llamadas** en el registro. Es 24 KB por
llamada de una imagen que repite el texto.

## Reproduction

```python
from art.describe import describe_unit_root
d = describe_unit_root(ts, lam=0.0)      # serie con estacionalidad fuerte
# antes: d.figure_b64 es una tabla con la fila d=2 en verde
# y d.recommendation dice "punto de partida recomendado: d = 1, no 2"
```

## Root cause

La figura se añadió cuando la tabla en markdown no existía todavía, y se quedó.
Cuando la recomendación creció —con el aviso del BUG-0002 sobre la
sobrediferenciación y el sesgo del ADF ante estacionalidad— nadie volvió a mirar
si el dibujo seguía diciendo lo mismo. **Un concepto en dos sitios, y la copia
que se queda atrás**: la enfermedad que este registro tiene documentada siete
veces, aquí entre un texto y una imagen.

## Fix

Se retira la figura. `describe_unit_root` devuelve `figure_b64=None` y conserva
la tabla en markdown con sus ✓/✗ y su recomendación. El bloque eliminado deja en
su sitio el comentario con las dos razones, para que no vuelva.

## Validation

`describe_unit_root(ts).figure_b64 is None`, y el `summary` sigue trayendo la
tabla y la recomendación.

**Y la regla que sale de aquí, que sirve para juzgar las otras figuras del
censo:**

> Una figura se justifica cuando enseña algo que **no cabe en una tabla**: una
> forma, una serie, una nube, un correlograma. Si el modelo puede leer los
> mismos números en el texto, la imagen sólo gasta contexto — y al analista le
> sirve menos que el markdown.

Es la primera baja del censo de figuras (`Revision_Art/figuras/INFORME.md`).
