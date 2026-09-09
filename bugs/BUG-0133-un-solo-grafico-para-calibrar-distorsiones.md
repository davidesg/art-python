---
id: BUG-0133
title: Dos figuras para la misma pregunta, y la de calibración se renderizaba para tirarla — un solo gráfico de calibración de distorsiones, con tres criterios
status: fixed
severity: medium
component: describe
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-09
reporter: David
tags:
  - figuras
  - intervenciones
references:
  - BUG-0130
  - BUG-0131
  - BUG-0132
---

## Summary

El nodo de intervención tenía **dos figuras para la misma pregunta**:

* el **escaneo** de tres paneles —serie, ACF y PACF con la parte del anómalo—, y
* la **calibración del correlograma** de dos paneles —observada contra
  calibrada, con el retardo que cambia de veredicto resaltado.

Y `residual_outlier_scan` **calculaba la segunda entera, con su render de
matplotlib, y descartaba la imagen** quedándose sólo con su tabla: `cal_b64` se
asignaba y no se usaba nunca.

Decisión del analista, en el censo de figuras: **una sola figura para todo**, y
que sea el escaneo de tres paneles —el **gráfico de calibración de
distorsiones**—, porque contesta las dos preguntas del nodo:

> *«Te ayuda a decidir si intervenir antes de ARMA, o ARMA antes de intervenir. Y
> después te ayuda a explicar si las ACF/PACF sucias y con Q demasiado grande es
> por un anómalo o porque falta estructura.»*

La tabla de calibración **se conserva**: es donde el veredicto por retardo se lee
mejor.

## Qué se añade para que sirva para todo

**Tres criterios de qué omitir**, con la misma figura:

| criterio | llamada |
|---|---|
| por **umbral** | `threshold=3.0` (por defecto) |
| por **observación** | `omitir=["Q2/2020"]` |
| por **incidente** | `omitir=["Q4/2008", "Q1/2009", "Q2/2009"]` |

Con `omitir` el umbral no interviene: se quita exactamente lo que se pide, lo
marque o no. Es lo que el nodo necesita cuando ya tiene el episodio delimitado.
Sobre `RATIO_m10`, quitar el episodio entero deja `PACF(6)` en **−0,088** frente
a **−0,135** quitando sólo los dos extremos: la señal AR que el anómalo fabricaba
era del episodio completo, no de su punta.

## Lo que hubo que arreglar para que fuera coherente

Al lanzarla en los tres modos aparecieron cuatro incoherencias, y todas eran la
misma: **el criterio no viajaba**.

1. **El título mentía**: decía `umbral ±3.5σ` y pintaba sus líneas rojas cuando
   se calibraba por incidente.
2. **La tabla calibraba por umbral mientras la figura calibraba por incidente** —
   dos calibraciones distintas en la misma pantalla.
3. **El veredicto salía de la tabla**, o sea contestaba a la pregunta que no era.
4. **Llamaba «extrema» a una observación con z = +0,09**, porque se omitía por
   pertenecer al episodio.

Arreglado: `describe_prelim_scan` publica los índices **ya resueltos**
(`data["omitidos"]`) y la tabla los usa —traducir la fecha dos veces sería la
misma cuenta en dos sitios—; `calibra_correlograma` acepta `omitir=`; y la
redacción distingue «omitidas» de «extremas».

## Presentación

* **La marca de lo omitido**: con `omitir`, las observaciones del episodio pueden
  estar en z≈0 y sus etiquetas se apilaban sobre el eje. Ahora se **sombrea el
  tramo** y se rotula una sola vez con el rango de fechas.
* **La banda ±2σ se ve siempre**: sin las líneas del umbral el eje se encogía y
  la banda salía del cuadro, y entonces las dos figuras no se podían comparar.
* **El pie se interpreta solo**: `omitiendo: −18% (la Q baja poco: falta
  estructura)`.

## Cableado

`guided_intervention` llamada 1 devuelve **la figura del escaneo** —con la Q al
pie— y **la tabla** de calibración con su veredicto. Una imagen por llamada.
`residual_outlier_scan` deja de renderizar la figura que descartaba.

## Validation

```
umbral     imágenes=1  pie: Q(15) = 20.8 · omitiendo: -39% (mixto) · calibrado por umbral |z| > 3.0
incidente  imágenes=1  pie: Q(15) = 20.8 · omitiendo: -18% (la Q baja poco: falta estructura) · el episodio 2008-09 (3 obs.)
```

`guided_intervention` llamada 1: 1 imagen, con tabla, veredicto y ruta.
