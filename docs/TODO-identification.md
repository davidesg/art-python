# TODO — el motor de identificación de órdenes (p, q)

**Estado:** abierto · **Abierto el** 2026-08-26 · **Origen:** réplica del TFM de
Bolivia, nodo A5 de `ln PGAS`

---

## Qué NO es esto

**No es un defecto.** Se investigó como tal y no lo es, y conviene dejarlo escrito
para que nadie vuelva a abrir el mismo camino:

- `_pattern_features` **extrae los rasgos correctamente**. Sobre `∇ln PGAS` da
  `acf_cutting_lag=2`, `pacf_cutting_lag=3`, `acf_initial_spikes=1` y
  `pacf_initial_spikes=2` — es decir, **ve** los dos retardos significativos de la
  PACF, que son la firma del AR(2).
- La ordenación que produce es **razonable**, no errónea: en esta serie **los dos
  patrones cortan a la vez**. La ACF corta tras el retardo 1 (lo que predice un
  MA(1)) *y* la PACF corta tras el 2 (lo que predice un AR(2)). Una métrica basada
  en FORMA no puede discriminar ahí, y ART **lo declara**: marca «decisión
  ambigua» (gap 0,007) y remite a estimar ambos y comparar por AIC/BIC y
  diagnosis. Esa guía es la correcta, y seguida resolvió el caso.

## El hueco real

Los prefiltros `_validate_ma` y `_validate_ar`
(`model_detection.py:197-215`) comprueban únicamente la **forma** — que el retardo
`q` sea significativo y que haya corte después — y **nunca la magnitud**. Pero un
MA(q) tiene una cota clásica sobre la primera autocorrelación:

```
    |rho_1|  <=  cos( pi / (q+2) )

        q=1 -> 0,500      q=2 -> 0,707      q=3 -> 0,809      q=4 -> 0,866
```

Cuando `|rho_1|` estimada la excede, hay evidencia contra ese MA(q) **de una clase
que la métrica de forma no puede ver por construcción**.

**Medido en `∇ln PGAS`** (n=83): `rho_1 = 0,575`, por encima de la cota 0,500 del
MA(1) — y ART clasifica `ARIMA(0,1,1)` **primero** (sim=0,878), con el AR(2)
correcto **cuarto** (sim=0,755). La estimación posterior confirmó el AR(2), con
φ₁=0,749 (t=7,2) y φ₂=−0,287 (t=−2,8), ambos claramente significativos.

## Qué hacer, y qué NO hacer

**NO** convertirlo en un rechazo duro. La violación no es estadísticamente
significativa: bajo un MA(1) con ρ₁=0,5, el error típico de Bartlett es
`sqrt((1-3ρ²+4ρ⁴)/n) = 0,0776`, así que 0,575 está a **z=0,97 (p=0,33)** de la
cota. Descartar el MA(1) por eso sería fingir una precisión que no hay.

**SÍ** usarlo como **desempate y como aviso**, que es donde vale:

1. Calcular `cos(pi/(q+2))` para cada candidato MA(q) propuesto y compararlo con
   la `rho_1` empírica.
2. Cuando la métrica declare **ambigüedad** —que es cuando el analista necesita
   ayuda— añadir esta evidencia al aviso: *«ρ̂₁=0,575 excede la cota 0,500 de un
   MA(1) (z=0,97, no significativo); es evidencia contra ese candidato que la
   similitud de forma no recoge»*. Con su `z`, para que se vea cuánta fuerza tiene.
3. Ordenar los candidatos empatados poniendo detrás los que violan su cota.

## Por qué importa más de lo que parece

Este es el nodo en el que ART es más débil, y el motivo es estructural: la
similitud compara **formas** de ACF/PACF, y hay información discriminante que no
es de forma sino de **magnitud**. La cota de la ρ₁ es el ejemplo más limpio, pero
la idea general —contrastar la admisibilidad teórica del candidato contra los
momentos observados, no sólo su silueta— es la línea por la que este motor puede
mejorar.

---

## Box-Cox: la agrupación, y por qué NO se levanta como bug

**Anotado el 2026-08-29** · Origen: RUN 2, defecto (a) del carril Claude.

El analista reportó que la correlación media-desviación del Box-Cox agrupa por
**años naturales**, y que sobre PGAS —que sube hasta 2012, cae hasta 2020 y
vuelve a subir— la relación nivel-dispersión se promedia hasta desaparecer
(0,150 frente a 0,173, Δ=0,024) pese a un rango de 5:1. Agrupando por **nivel**
la señal sale inequívoca: ×1,83 de desviación por ×2,32 de nivel.

**No se levanta como bug.** La agrupación por años naturales no es una convención
estándar en la literatura de Box-Jenkins, así que no hay un «correcto» del que
esto se desvíe: es una elección de implementación, discutible pero no equivocada.
Llamarla defecto exigiría antes decidir contra qué convención se juzga, y esa
discusión no está hecha.

**Lo que sí queda apuntado como idea.** Técnicamente ART podría **cambiar el
parámetro de agrupación cuando ve algo raro** — por ejemplo, cuando la serie no
es monótona y la correlación por años sale plana pese a un rango amplio,
reagrupar por nivel y contrastar las dos lecturas. No es un arreglo: es una
capacidad nueva, y habría que decidir cuándo se dispara y cómo se presenta sin
que parezca que la herramienta busca el resultado que quiere.

Se anota aquí para que no se pierda, y explícitamente **fuera** de la lista de
bugs.

---

## El AR(1) con bandera 0: un artificio del formato, no una especificación

**Anotado el 2026-08-29** · Origen: BUG-0057, y una observación del analista
humano que cambia el diagnóstico.

BUG-0057 salió de que `len(m.ar[0])` contaba operadores FIJADOS: un `.inp` con

```
** Number and orders of regular AR operators:
1 1
**
0.000000  0
```

declara un AR(1) con coeficiente 0 y bandera 0 (fijo). Se arregló contando sólo
los coeficientes libres. **Pero eso trata el síntoma.**

**Lo que hay que investigar.** Ese `1 1 / 0.000000 0` se usa como **artificio**
cuando no se estiman parámetros ARMA: es la forma de escribir «no hay AR» en un
formato que, en el motor C de `fue` y en la versión Python con *wheels*, no
admite decirlo de otro modo. **La versión Python pura no tiene ese problema de
especificación**, así que el artificio no es una propiedad del modelo sino de la
ruta de compilación por la que se escribió el fichero.

Consecuencias a comprobar, ninguna de ellas verificada todavía:

1. **¿Cuántos sitios de ART cuentan órdenes con `len(...)`?** Cada uno hereda el
   mismo error. BUG-0057 arregló el del incremento; hay que auditar el resto —
   `_extract_spec`, `_spec_diff`, `_nested_relation`, la ecuación, los grados de
   libertad de los contrastes.
2. **¿Cambia `npar` según el motor?** Si el artificio aparece por una ruta y no
   por otra, el mismo modelo podría contarse con distinto número de parámetros
   —y por tanto distinto AIC/BIC— según con qué `fue` se escribió el `.inp`. Eso
   sería grave y hay que medirlo, no suponerlo.
3. **¿Qué escribe ART?** Si es ART quien emite ese `1 1 / 0.0 0` al construir un
   modelo sin AR, la solución limpia es no emitirlo: `0` operadores.

Las soluciones posibles, en orden de menos a más invasiva:

* **Normalizar al leer**: al cargar un `.pre`/`.inp`, colapsar los factores cuyos
  coeficientes están todos fijados en cero. El modelo queda igual y el resto de
  la suite deja de tener que acordarse.
* **Normalizar al escribir**: que `_write_inp` no emita factores vacíos.
* **Una única función de conteo** —`ordenes_libres(model)`— y prohibir `len()`
  sobre los factores en el resto del código.

La tercera es la que evita que esto vuelva por un cuarto sitio.

---

## Recorrer varias series EN PARALELO: subóptimo, y qué hacer con ello

**Anotado el 2026-08-30** · Origen: RUN 3 de la réplica TFM Bolivia.

**No es un bug.** Es una forma de andar el protocolo que resulta peor, y hasta
ahora no estaba escrito en ninguna parte que lo fuera.

Un analista del RUN 3 recorrió los nodos **por lotes a través de las tres
series** —los tres `dominio` en el mismo segundo, los tres `lambda` en el mismo
segundo, y así cinco nodos— en lugar de terminar una serie antes de abrir la
siguiente, que es como había trabajado en el RUN 2. Mismo protocolo, mismo
analista, distinta forma de andarlo:

| | por series (R2) | por lotes (R3) |
|---|---|---|
| **primer modelo estimado en la posición** | **5** | **15** |
| modelos estimados | 18 | 14 |
| callejones explorados | 7 | 3 |
| nodos de protocolo decididos en lote | 0 | 8 |
| suma de ΔAIC | +17,89 | +33,73 |

El mecanismo: el método es un bucle cerrado y batear un nodo difiere toda la
realimentación. Quince decisiones antes del primer residuo son el 38% del
recorrido en circuito abierto. Y el daño llegó a lo concreto — un nodo
`intervenciones` cerrado con «sin intervenciones» en el mismo segundo que el de
otra serie, reabierto cinco nodos después al aparecer un anómalo de z=−4.04.

### Lo que ya se ha hecho

1. **La regla, escrita donde faltaba**: en `_INSTRUCTIONS` del servidor (sección
   «VARIAS SERIES: UNA DETRÁS DE OTRA») y en las instrucciones de las corridas.
   Con el mecanismo y con la objeción razonable respondida: la coordinación entre
   series que exige el objetivo multivariante se declara UNA VEZ con
   `objetivo=`, no batéandolo todo.
2. **La forma del recorrido, medible**:
   `replica/evaluacion_run3/forma_del_recorrido.py` la calcula de los sellos de
   tiempo de los guiones. El indicador más limpio es «nodos de protocolo
   decididos EN LOTE» (sellos compartidos por más de una serie): 8 en la corrida
   por lotes, 0 en las otras tres.

### Lo que queda por decidir

**¿Debería ART observarlo, y no sólo pedirlo?** Es una pregunta de diseño, no un
arreglo pendiente, y tiene un obstáculo real: cada serie tiene su propio guion en
su propio directorio, así que `guion_node` no ve a las hermanas. Opciones, de
menos a más intrusiva:

* **Nada en la herramienta.** La regla está escrita y la forma es medible a
  posteriori. Suficiente si el objetivo es evaluar corridas, no impedirlas.
* **Un aviso al cerrar la serie.** `guion_map` podría mirar los guiones hermanos
  del mismo directorio padre y decir si el recorrido se intercaló. Barato, y
  llega tarde a propósito: informa sin interrumpir.
* **Un aviso en caliente.** `guion_node` detecta que se está escribiendo el mismo
  nodo en otra serie con segundos de diferencia. Es el que de verdad corregiría
  la conducta, y el que más riesgo tiene de molestar en usos legítimos —trabajar
  a ratos en dos series no es batear.

La segunda parece el equilibrio, pero conviene decidirlo con una corrida más
delante: con la regla ya escrita, puede que no haga falta ninguna.
