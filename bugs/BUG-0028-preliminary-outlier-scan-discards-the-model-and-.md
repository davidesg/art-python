---
id: BUG-0028
title: preliminary_outlier_scan discards the model and scans the raw series — the call ART itself prints for residual outlier analysis therefore analyses the wrong data and returns a confident false negative
status: fixed
severity: high
component: mcp-tools
found_in: 0.1.11
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - residuals
  - outliers
  - false-negative
references:
  - src/art/mcp_server.py:726 (`ts, _ = _load_ts_model(inp_path)` — descarta el modelo)
  - src/art/mcp_server.py (el bloque «¿Dudas?» que imprime la llamada rota)
  - bugs/BUG-0028-repro/repro.py
---

## Summary

`confirm_and_estimate` cierra su salida con esta sugerencia, literal:

> **¿Dudas?** Para ver cuánto distorsiona cada outlier la ACF, llama a:
> `preliminary_outlier_scan(inp_path="<modelo_actual>.pre", d=0, D=0, lam=1.0)`
> *(muestra contribución de cada outlier a cada lag de la ACF)*

Pero la herramienta hace (`mcp_server.py:726`):

```python
ts, _ = _load_ts_model(inp_path)     # <- se queda la serie, TIRA el modelo
desc = describe_prelim_scan(ts, d=d, D=D, lam=lam, threshold=threshold)
```

Con un `.pre` y `d=0, D=0, lam=1.0` lo que escanea es la **serie original, sin
transformar y sin diferenciar**. No los residuos.

Y **no falla**: devuelve un veredicto tranquilizador. Sobre un modelo cuyos
residuos llevan un anómalo de `z = +9,43`:

```
- Serie tipificada: n=96, μ̂=254.2060, σ̂=96.7760      <- media/sd de la serie CRUDA
- **Sin observaciones extremas.** Las ACF/PACF reflejan fielmente la estructura ARMA.
```

El escaneo de residuos **sí existe** — `confirm_and_estimate` lo produce, con su
panel de contribución de cada anómalo a cada retardo de la ACF — pero está
encerrado dentro de esa herramienta y **no hay forma de invocarlo por separado**.

## Impact

Alta. Es la herramienta a la que ART envía al analista para la calibración que
decide si intervenir antes de identificar (p,q), y responde sobre otra serie.

El modo de fallo es el peor posible: **silencioso, plausible y tranquilizador**.
La cabecera dice «Serie tipificada» sin decir *cuál*, así que nada delata la
sustitución; y el veredicto —«las ACF/PACF reflejan fielmente la estructura
ARMA»— es exactamente lo contrario de lo que ocurre.

Cuándo muerde con más fuerza: cuando el **nivel es suave** y el anómalo vive en
la diferencia o en la innovación. Ahí la desviación típica del nivel está
dominada por la tendencia, ningún punto destaca, y el falso negativo es seguro.
Es la configuración de una serie económica corriente.

**Medido en el caso real**: `RATIO_m20` (gasto público/PIB, modelo con armónicos +
SAR(1)₄ + intervención) tiene un residuo en `z = +3,76` y dos retardos de la ACF
fuera de banda que ese anómalo pone. La llamada recomendada respondió «Sin
observaciones extremas», con `μ̂=0.1628, σ̂=0.0297` — la media y la desviación del
propio ratio en niveles.

**Consecuencia observada en el uso**: al no obtener del instrumento lo que el
instrumento decía dar, el analista (aquí, el asistente) acabó calculando a mano
la contribución de cada anómalo a cada retardo y dibujando su propio gráfico —
reinventando, peor, algo que ART ya tiene construido. El defecto no sólo da una
respuesta falsa: **empuja fuera de la herramienta**.

## Reproduction

```
python3 bugs/BUG-0028-repro/repro.py
```

Sintético y determinista (semilla 31). Nivel suave con tendencia y un escalón en
la observación 60: invisible en niveles, `|z|` enorme en la diferencia.

```
residuos del modelo estimado:
   sigma = 419.2847    residuos |z|>3: 1    el mayor obs 60 con z=+9.43

la llamada que ART recomienda para los residuos:
   - Serie tipificada: n=96, μ̂=254.2060, σ̂=96.7760
   - **Sin observaciones extremas.** Las ACF/PACF reflejan fielmente la estructura ARMA.

   media/sd de la serie CRUDA : 254.2060 / 96.7760     <- coincide con la cabecera
   media/sd de los RESIDUOS   : 335.8027 / 419.2847
```

## Root cause

`preliminary_outlier_scan` está escrita para su uso legítimo —escanear la serie
**antes** de tener modelo, que es el nodo A4 del flujo guiado— y su firma
(`inp_path, d, D, lam`) lo refleja: recibe la transformación como argumentos
porque todavía no hay modelo que la lleve.

El defecto es que **el texto de sugerencia la reutiliza para un uso que no
soporta**. Pasarle un `.pre` no es un error detectable desde dentro: un `.pre` es
un `.inp` válido, la carga funciona, y `d=0, D=0, lam=1.0` es una combinación
legítima. La herramienta no puede saber que quien la llama quería los residuos.

## Fix

Dos piezas, y la segunda es la que importa:

1. **Corregir el texto**: la sugerencia no debe recomendar una llamada que no
   hace lo que anuncia.
2. **Exponer el escaneo de residuos**, que ya existe y está construido dentro de
   `confirm_and_estimate`. Un `residual_outlier_scan(pre_path, threshold)` que
   cargue el modelo, tome `model.residuals` y llame al mismo
   `describe_prelim_scan` con `d=0, D=0, lam=1` **sobre los residuos**, con el
   panel de contribución a la ACF. Es reordenar lo que ya hay.

Y una tercera, defensiva: que la cabecera diga **qué** serie se ha tipificado
(«serie original», «∇ᵈ∇ᴰ y(λ)», «residuos de `<modelo>`»). El defecto habría sido
visible al instante si la línea hubiera dicho de dónde salían esos números.


## Lo aplicado (2026-08-27)

Las tres piezas del §Fix, y una cuarta que salió al hacerlo.

1. **`residual_outlier_scan(inp_path, threshold)`** — el escaneo de residuos, que
   ya existía construido dentro de `_auto_scan_section` y no era invocable por
   separado. Carga el modelo, arma la serie de residuos con `_resid_start` y
   llama al mismo `describe_prelim_scan`, con su panel de contribución a la ACF.
2. **La sugerencia impresa, corregida.** Donde mandaba a
   `preliminary_outlier_scan(inp_path="<modelo>.pre", d=0, D=0, lam=1.0)` ahora
   manda a `residual_outlier_scan(inp_path="<modelo>.inp")`, y dice por qué la
   otra no vale aquí.
3. **La cabecera dice qué se ha escaneado.** «*Escaneo sobre los RESIDUOS de
   `X.inp` (n=…), no sobre la serie*». El defecto habría sido visible al instante
   si la línea hubiera dicho de dónde salían los números.
4. **Aviso defensivo en `preliminary_outlier_scan`.** No se puede impedir que le
   pasen un modelo —un `.pre` es un `.inp` válido y `d=0,D=0,lam=1` es legítimo—
   pero sí detectar que el fichero lleva ARMA o intervenciones y decirlo:
   *«este fichero lleva un MODELO, y esto ha escaneado la SERIE»*, con la
   herramienta correcta nombrada. Sólo salta cuando hay modelo: en su uso
   legítimo —antes de que exista uno— el aviso sería ruido y no aparece.

**Lo que NO se ha tocado:** `preliminary_outlier_scan` sigue escaneando la serie.
Hace lo que debe hacer, y su sitio es antes de que exista modelo. Lo que se
arregla no es su comportamiento sino que se confunda con el otro — porque un
anómalo sólo lo es *respecto de un modelo*, y hacen falta las dos.

Contraste, sobre el mismo modelo con un residuo en |z|=9,48:

| herramienta | qué reporta |
|---|---|
| `residual_outlier_scan` | 1 observación extrema, **z=+9,48** |
| `preliminary_outlier_scan` | «Sin observaciones extremas» + **aviso** de que ha escaneado la serie |

`tests/test_bug_0028_residual_scan.py`, 7 casos, incluido uno que comprueba que
las dos herramientas reportan **medias tipificadas distintas** — la prueba
directa de que ven series distintas.
