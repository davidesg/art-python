---
id: BUG-0085
title: el factor de reescala se pierde al construir un `fue.Model` a mano — dos caminos de la misma suite producen modelos en escalas distintas, y el guion los apila en la misma columna
status: fixed
severity: high
component: pipeline/guion
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: Claude, comprobando el arreglo de BUG-0079 sobre ITCER
tags:
  - scale
  - guion
  - comparability
references:
  - src/art/pipeline.py:286 (_write_inp) y :397 (la nota sobre refactor)
  - BUG-0084 §1 (σ̂ ×100 en la figura de residuos — la otra cara de lo mismo)
---

## Summary

La suite estima sobre **100·log(y)**: `pipeline._RESCALE_FACTOR = 100.0`, y con
esa escala σ̂ₐ sale directamente en tanto por ciento, que es lo que hace legibles
las ecuaciones.

Pero `fue.Model` tiene **`refactor=1.0` por defecto**. Construir un modelo a mano
sin pasarlo produce un modelo en OTRA escala, y `_write_inp` lo registra
fielmente:

```
** ACF/PACF bands (0 Automatic) and reescaling factor:
   0 100.00      ← lo que escribe la cadena guiada
   0   1.00      ← lo que escribe _write_inp sobre un Model construido a mano
```

`_write_inp` hace `getattr(model, 'refactor', _RESCALE_FACTOR) or _RESCALE_FACTOR`:
el `getattr` encuentra `1.0`, que es *truthy*, así que la red del `or` no salta.
La convención de la suite sólo se aplica cuando el atributo falta, y nunca falta.

## Impact

**Los dos modelos son el mismo**, expresados en unidades distintas — σ̂ₐ=2.158 con
factor 100 es σ̂ₐ=0.021582 con factor 1, y los dos son 2.158%. Eso no es el
problema.

El problema es que **ℓ, AIC y BIC no son comparables entre escalas** —difieren en
`n·ln(100)`— y el guion los apila en la misma columna sin distinguirlos. Medido
sobre los guiones del run 5:

| | escala | ℓ | AIC |
|---|---|---|---|
| PGAS m00 | 100 | −315.208 | 630.416 |
| PGAS m10 | **1** | 77.622 | −147.244 |
| PGAS m20 | **1** | 101.926 | −193.851 |
| ITCER m00 | 100 | −203.122 | 406.244 |
| ITCER m10 | **1** | 200.608 | −389.216 |

Entre `m00` y `m10` de PGAS hay 778 puntos de AIC que son **puro cambio de
unidades**. El mapa del guion los pinta uno debajo de otro como si midieran lo
mismo.

*Nota sobre el análisis afectado:* las comparaciones que se hicieron —la escalera
de Ockham, las configuraciones del incidente, el LR entre m20 y m30— clonan
todas el mismo modelo base, así que fueron **dentro de una misma escala** y sus
conclusiones se sostienen. Lo que no vale es leer la columna del guion de arriba
abajo.

## Y es la otra cara de BUG-0084 §1

Aquel reporta σ̂ ×100 entre la ecuación y la figura de residuos sobre el MISMO
modelo. Éste reporta ×100 entre dos modelos. Los dos salen de que el factor de
reescala se aplica en unos sitios y no en otros, sin que nada lo declare al
leerlo.

## Fix (propuesto)

1. `_write_inp` aplica la convención de la suite salvo que el modelo declare
   otra cosa **explícitamente** — no por `getattr` con un defecto que nunca
   falta. Lo más simple: exigir `refactor` como argumento y no adivinarlo.
2. El **guion guarda el factor** junto a `loglik`/`aic`/`bic`, como ya guarda
   `npar` y la versión del instrumento (BUG-0077, P14). Sin él esas cifras no se
   pueden releer.
3. `guion_map` y `compare_versions` **avisan** cuando dos entradas no comparten
   escala, en vez de restarlas.
4. Y una guarda en `art`: construir un `fue.Model` sin `refactor` es un uso
   legítimo de la librería, pero dentro de la suite es casi siempre un
   descuido. Un aviso al escribir un `.inp` con factor distinto del convenido
   habría ahorrado esta sesión.

---

## Ampliación al arreglarlo: no era sólo mi uso de la API

El reporte decía que el descuido estaba en construir modelos a mano. Al ir a
arreglarlo aparecieron **tres fugas dentro de la propia suite**, y una de ellas
se estaba imprimiendo al analista:

**1. `configuracion.evalua_configuraciones`** clona el modelo base copiando una
lista blanca de atributos, y `refactor` no estaba en la lista. Medido sobre
FOOD_UEM, en la misma pantalla:

```
BASE   refactor=100.0  aic=   -8.197
  cand 12/2004×1  refactor=1.0  aic=-2002.007
  cand 12/2004×2  refactor=1.0  aic=-2002.440
```

1994 puntos de AIC entre el modelo base y las configuraciones que salen de él.
El ΔAIC y el orden eran correctos —todos los candidatos se clonaban igual, y la
escala se cancela en la diferencia— pero el AIC absoluto era inutilizable y la
ganancia salía en la escala equivocada: `ω(1)=+0.0045` en vez de `+0.45`, que es
el desplazamiento del nivel **en tanto por ciento**, que es para lo que está el
factor 100.

**2. `escalera._clona_con`** — la misma lista blanca, la misma omisión. La
escalera de Ockham comparaba sus peldaños entre sí (consistente) pero su AIC no
era el del modelo del que partía.

**3. `create_inp`** — el esqueleto del que arranca **todo** análisis nacía en
escala 1. Se corregía aguas abajo porque `pipeline` reconstruye el modelo con
`_RESCALE_FACTOR`, pero quien estimara el `.inp` recién creado obtenía otra cosa.

## Fix (aplicado, 2026-09-04)

**1. `refactor` entra en las dos listas blancas** de clonado
(`configuracion.py`, `escalera.py`), con la razón escrita al lado: no es un
extra, es lo que fija las unidades. Tras el arreglo, sobre el mismo caso:

```
BASE   refactor=100.0  aic= -8.197
  cand 12/2004×1  refactor=100.0  aic=-21.784  ω(1)=+0.880
  cand 12/2004×2  refactor=100.0  aic=-22.217  ω(1)=+0.452
```

Mismo ΔAIC (0.43, como debe: la escala se cancela en la diferencia), AIC ya
comparable con el base, y la ganancia legible como el porcentaje que es.

**2. `_write_inp(ts, model, path, refactor=None)`.** El `getattr` con red se
sustituye por un parámetro explícito. Si no se pasa se escribe **lo que declare
el modelo** —no se adivina, no se cambia el comportamiento en silencio— pero se
AVISA por `RuntimeWarning` cuando difiere de la convención, diciendo que los
ℓ/AIC/BIC no son comparables y cómo silenciarlo si es deliberado. Estimar en
escala 1 es un uso legítimo de la librería; hacerlo por descuido no.

**3. `create_inp` pasa `refactor=_RESCALE_FACTOR`.** La convención, explícita
desde el primer fichero.

**4. El guion guarda la escala.** `GuionStats.refactor`, poblado desde el modelo
en `_extract_stats`, junto a `npar` y la versión del instrumento (BUG-0077). Sin
él la columna no se puede releer.

**5. `guion_map` avisa cuando se mezclan escalas**, igual que ya avisaba cuando
se mezclan versiones del instrumento, y con el mismo cuidado: la guarda `except`
reporta el fallo en vez de callar. Distingue además «escalas mezcladas» de
«escala no registrada» (entradas anteriores a este campo).

**6. `compare_versions`** extiende la guarda de comparabilidad de BUG-0051 al
factor. Suprime el Δ, cuantifica el salto (`n·ln(factor)`) y —esto faltaba—
**suprime también el LR**. El LR es una diferencia de verosimilitudes: entre
escalas distintas el χ² sale enorme y con p≈0, un contraste que canta
«significativo» sobre un cambio de unidades. El remedio que sugiere es distinto
del de BUG-0051, porque el problema lo es: aquí no son dos modelos, es el mismo
mal anotado, y se arregla reestimando en la convención.

## Validation — resultado

`tests/test_bug_0085_factor_de_reescala.py`, 13 pruebas: los dos clonadores, que
el AIC del candidato cae en el rango del base (y no a n·ln(100) de distancia),
el aviso al escribir fuera de convención, el silencio al escribir dentro, el
`refactor=` explícito como forma de declarar la excepción, el round-trip del
fichero, `create_inp`, el campo del guion, las dos ramas del aviso del mapa, y
las dos de `compare_versions` (Δ suprimido y LR suprimido).

## Lo que esto NO deshace

Los guiones del run 5 quedan como están: son un registro histórico y sus
entradas siguen mezclando escalas. Lo que cambia es que **ahora se puede saber**
—las nuevas llevan el campo, y el mapa avisa de las que no. Las comparaciones
sustantivas de aquella sesión se sostienen porque todas clonaban el mismo modelo
base y caían dentro de una sola escala; lo que no vale es leer la columna de
arriba abajo.
