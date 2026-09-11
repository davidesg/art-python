---
id: BUG-0160
title: Cinco avisos del método viven dentro de un `except Exception: pass` — si fallan desaparecen sin rastro, y uno de esos bloques ya estaba muerto
status: fixed
severity: medium
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: Claude (al arreglar BUG-0158)
tags:
  - avisos
  - silencio
  - contrato-de-ficheros
references:
  - BUG-0027
  - BUG-0028
  - BUG-0090
  - BUG-0124
  - BUG-0158
  - BUG-0159
---

## Summary

`_warn(contexto, exc)` existe en `mcp_server.py` desde §4 y su docstring dice
para qué: *«Log a non-fatal failure to stderr instead of swallowing it silently»*.
**Cinco bloques que componen un AVISO DEL MÉTODO no lo usaban** — terminaban en
`except Exception: pass`:

| sitio | qué aviso se pierde |
|---|---|
| `_equation_for_prompt` | «**estos errores típicos NO son válidos**» (BUG-0027) y la sospecha de covarianza-casi-semilla (BUG-0124) |
| `preliminary_outlier_scan` | «un anómalo sólo lo es *respecto de un modelo*» (BUG-0028) |
| `residual_outlier_scan` | «**estos anómalos no están solos**: llama a `residual_episodes`» |
| `overparameterization_analysis` | «los números buenos están en el `.out` de la estimación real» |
| `get_out_report` | el aviso de SE no fiables sobre un informe reestimado |

Son, uno por uno, las advertencias que el método existe para dar. Un aviso
envuelto en un `except` mudo es un aviso que puede desaparecer sin dejar rastro:
la salida sale igual de bien formada, sólo que sin la advertencia. Y como la
advertencia es justo lo que el analista **no sabe todavía**, su ausencia no se
nota.

## Impact

Ninguno de los cinco falla hoy sobre los casos probados — esto se midió, con un
módulo gemelo en el que los cinco `pass` se convirtieron en `raise`. **La
severidad no viene de una pérdida observada, sino de que el patrón ya demostró
matar un arreglo entero en este mismo módulo.**

El arreglo de BUG-0158 —leer ℓ, AIC y BIC del `.out` en vez de reestimar— murió
exactamente así:

```python
ne = len(getattr(r, "residuals", []) or []) or (o.nobs - 1)
```

`residuals` es un array de numpy: `res or []` evalúa su verdad y levanta
`ValueError: the truth value of an array … is ambiguous`, dentro de un
`try/except Exception: pass`. La rama del `.out` **no se ejecutó nunca**. La
herramienta siguió reestimando, y la suite siguió en verde, porque el número
recalculado coincide hasta el cuarto decimal con el leído.

Ese es el perfil de riesgo entero: el `except` mudo no hace que las cosas
fallen, hace que **fallen igual que funcionan**.

## Repro

Determinista, sobre el propio fuente — la misma forma que usa
`test_ninguna_herramienta_carga_y_ajusta_POR_SU_CUENTA` (BUG-0090):

```python
_bloques_mudos("src/art/mcp_server.py")   # AST: Try cuyo handler es sólo `pass`
                                          # y cuyo cuerpo contiene ⚠ / ℹ / «aviso»
```

    en HEAD  → 5 bloques
    con fix  → 0

## Fix

Los cinco pasan a `_warn("no se pudo componer el aviso del método en <fn>", _e)`.
El aviso al analista se sigue degradando con elegancia —no se rompe la
herramienta por no poder componer una advertencia— pero **el motivo aparece en
el log del servidor**, que es donde se mira cuando algo falta.

Y en `compare_versions`, el `except` que mató a BUG-0158 hace lo mismo: un
`.out` ilegible es una noticia, no un detalle.

## Lo que esto enseña

Tercera vez en dos días con la misma forma, y ya tiene nombre: **una propiedad
que sólo se sostiene si todo el mundo se acuerda es una costumbre, no una
propiedad del sistema.**

- BUG-0159: el convenio de ficheros estaba escrito, razonado y explicado — y se
  sostenía con un `RuntimeWarning` que ningún carril lee.
- BUG-0160: `_warn` estaba escrito, y su docstring decía exactamente esto — y
  cinco sitios no lo usaban.

En los dos casos la doctrina era correcta y estaba documentada. Lo que faltaba
era que **el sistema comprobara la propiedad**: una negativa en el primero, una
prueba sobre el AST en el segundo. Documentar una regla no la impone; a lo sumo
la enseña a quien ya fue a buscarla.

## Validation

`tests/test_bug_0160_avisos_dentro_de_un_except_mudo.py`. Además del censo sobre
el AST —en `mcp_server`, `pipeline` y `describe`—, comprueba que `_warn` sigue
escribiendo a **stderr** y no a stdout (un aviso de servidor en stdout
contaminaría la salida que lee el cliente), y que el aviso más caro de perder
—el de covarianza-semilla sobre un `.pre`— sigue saliendo después del cambio.
