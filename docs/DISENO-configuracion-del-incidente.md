# La configuración del incidente — por qué el dato no la identifica

Documento de diseño. Abierto 2026-09-03, durante el run 5 guiado sobre PGAS.
Es el sucesor de P5: no un arreglo del detector de episodios, sino el
replanteamiento de lo que ese nodo puede y no puede afirmar.

---

## 1. El mecanismo

Con `d=1`, el diccionario nivel ↔ diferencias tiene una consecuencia que la
herramienta no estaba tratando:

| en el NIVEL | en ∇ |
|---|---|
| **escalón** en T | UN spike en T |
| **impulso** en T | DOS spikes: +ω en T, **−ω en T+1** |

Así que **un spike observado en k puede ser el arranque de un suceso en k o la
COLA de uno que empezó en k−1.** Y si la serie deambula, el primer spike puede
quedar tapado por un vaivén de signo contrario mientras el segundo cruza el
umbral: se marca el segundo, la intervención cae un período tarde, y la
verosimilitud apenas lo distingue — es BUG-0030, con Δ logL = 0,03.

El detector actual agrupa **sólo los extremos**, de modo que sobre PGAS vio

```
∇ 2008Q3   +1.27     ← la subida, POR DEBAJO del umbral
∇ 2008Q4   +1.35
∇ 2009Q1   −2.91  ←  lo único que ve
∇ 2009Q2   −2.82  ←
```

y situó el suceso en 2009Q1, midiendo la caída contra una base ya inflada por
el pico previo.

---

## 2. La medida: el dato NO identifica la configuración

Se enumeraron todas las configuraciones `(arranque, nº de escalones)` con
arranque entre 2008Q1 y 2009Q1 y de 1 a 6 escalones, y se estimaron todas.

**Seis caen dentro de 2 puntos de AIC. Ninguna deja vecino anómalo.** Es decir,
**ni el AIC ni la regla de Treadway las separan.** Y discrepan en lo sustantivo:

| configuración | AIC | ΔAIC | ω(1) | SE | IC 95% | lectura |
|---|---|---|---|---|---|---|
| 2008Q3 × 4 | −147,24 | 0,00 | −0,2738 | 0,267 | [−0,797, **+0,250**] | transitorio |
| 2008Q4 × 3 | −146,79 | +0,46 | −0,4237 | 0,220 | [−0,856, **+0,008**] | transitorio |
| 2008Q1 × 6 | −146,78 | +0,47 | −0,0376 | 0,328 | [−0,680, **+0,604**] | transitorio |
| **2009Q1 × 2** | −146,10 | +1,14 | **−0,5830** | **0,139** | **[−0,855, −0,311]** | **PERMANENTE** |
| 2008Q2 × 5 | −145,91 | +1,33 | −0,1964 | 0,302 | [−0,787, **+0,395**] | transitorio |
| 2008Q3 × 5 | −145,29 | +1,95 | −0,2527 | 0,301 | [−0,842, **+0,337**] | transitorio |

La ganancia estimada va de **−0,04 a −0,58** —un factor de quince— entre modelos
que empatan en ajuste. Traducido: entre «no pasó nada permanente» y «el nivel
cayó un 44% para siempre».

### 2.1 La trampa: la ventana corta parece la más segura

**La configuración que la herramienta eligió es la del intervalo más estrecho y
la única que excluye el cero.** No es casualidad ni suerte: acortar la ventana
quita parámetros y aprieta la identificación **dentro** del modelo, mientras
empeora la línea base al dejar fuera el pico previo.

Las otras cinco incluyen el cero. **El veredicto «permanente» es un artefacto
de haber elegido la ventana corta**, y viene con la etiqueta de precisión más
convincente del conjunto.

### 2.2 La incertidumbre está en la configuración, no en el estimador

| | |
|---|---|
| error típico DENTRO de un modelo | 0,139 – 0,328 |
| desviación típica ENTRE configuraciones | **0,189** |
| rango entre configuraciones | **0,546** |

Son del mismo orden. **Reportar el error típico de un solo modelo subestima la
incertidumbre real a la mitad**, y lo hace precisamente en el número que el
analista va a interpretar.

### 2.3 Por qué el arranque manda

La ganancia estimada está casi determinada por la fecha de arranque:

    arranque más temprano  →  más del ascenso previo queda ABSORBIDO
                           →  la línea base sube
                           →  |ganancia| menor

La intervención mide siempre contra **lo que la precede**, y el arranque es
quien decide qué es «lo que la precede». Ésa es la razón estructural de que el
conjunto esté no identificado, y no se arregla con más datos de la misma
muestra.

---

## 3. Lo que esto le prohíbe a la herramienta

**No puede auto-seleccionar.** Elegir una de seis indistinguibles y reportar su
error típico es fabricar una precisión que no existe. Y es peor que no hacer
nada, porque la que sale elegida por AIC tiende a ser la de ventana corta, que
es la de la lectura equivocada con la etiqueta más segura.

**No puede reportar UN número para la ganancia.** Tiene que reportar el rango
sobre el conjunto identificado.

**Y no puede buscar sin límite.** Es la advertencia del analista: el diseño es
delicado porque **puede sobre-elaborar**. Una búsqueda libre sobre
`(arranque, longitud)` siempre encuentra algo mejor, y lo que encuentra es
ruido.

---

## 4. Diseño propuesto

### 4.1 El conjunto candidato, acotado por el MECANISMO

No una rejilla libre. Los límites salen del diccionario:

- **Arranques**: desde el primer extremo hacia atrás mientras los residuos ∇
  contiguos sigan **activos** —no necesariamente extremos, pero por encima de un
  umbral laxo declarado (p. ej. 1σ)— y como mucho hasta un tope corto. Sobre
  PGAS eso da {2008Q3, 2008Q4, 2009Q1}: el +1,27 de 2008Q3 está activo y lo que
  le precede no.
- **Longitudes**: las que cubren desde el arranque hasta el último extremo, más
  una (para permitir el retorno al nivel base). Ni una más.

Con eso el conjunto son unas 4-6 configuraciones, que es lo que hay, y no un
barrido.

### 4.2 Lo que se presenta

La tabla de §2 entera: cada configuración con su AIC, su ganancia, su IC y su
lectura. Con el **rango de la ganancia** como titular, y el aviso de §2.1 al
lado de la de ventana más corta cuando sea la de IC más estrecho.

### 4.3 Lo que resuelve el empate — y no es estadístico

**Dominio.** Sobre un índice de precios o un precio de exportación, una caída
permanente de nivel es poco usual, así que las lecturas transitorias parten con
ventaja. `policy.decide_domain` ya da la clase.

**Información extramuestral.** Es lo único que identifica de verdad: si consta
que el suceso empezó en tal trimestre y qué naturaleza tuvo, eso fija el
arranque, y con el arranque fijo el resto se estima. La herramienta pregunta y
espera respuesta — es el canal que ya abrió la escalera de Ockham.

**El simulador y la superposición** (F0/F0b) puntúan la compatibilidad de cada
candidato con el entorno observado antes de estimar nada.

### 4.4 La guarda contra sobre-elaborar

Regla explícita: **si más de N candidatos caen dentro de 2 puntos de AIC, la
herramienta NO elige.** Dice que la muestra no identifica la configuración,
publica el rango, y devuelve la pregunta extramuestral. Es el resultado
honesto, no un fallo.

---

## 5. Lo que queda por decidir

1. El umbral de «activo» para extender el arranque hacia atrás — 1σ es una
   propuesta, no una medida.
2. El tope de extensión hacia atrás.
3. `N` en la guarda de §4.4, y si 2 puntos de AIC es la banda adecuada.
4. Si el rango de la ganancia se publica siempre o sólo cuando el conjunto no
   está identificado.
