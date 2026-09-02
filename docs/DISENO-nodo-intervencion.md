# El nodo de intervención por episodios — problema, solución y plan

Documento de diseño. Abierto 2026-09-02. Es lo que cierra la versión 0.2.0.

---

## 1. El problema

### 1.1 Lo que la herramienta hace hoy

Todo el análisis de intervención de `art` cuelga de esto (`policy.decide_form`):

```python
has_consec = (target_obs - 1 in ext) or (target_obs + 1 in ext)
return "step" if has_consec else "pulse"
```

**Dos formas, elegidas por una comprobación de adyacencia.** Si el residuo de al
lado también es extremo → escalón; si no → impulso. No hay más.

Lo que eso implica:

- **No existe la noción de episodio.** Un suceso que dura tres períodos son tres
  atípicos sueltos, cada uno con su forma decidida por separado.
- **No se estima ninguna alternativa.** La forma se elige por una regla, no se
  contrasta. No hay especificaciones rivales que comparar.
- **No se calcula la ganancia a largo plazo**, así que la distinción
  permanente/transitorio —que es *la* pregunta del análisis de intervención— no
  se contesta con un contraste, se hereda de la etiqueta que puso la regla.

### 1.2 Lo que cuesta, medido

De las cuatro corridas de la réplica de Bolivia:

| | |
|---|---|
| Valor de encontrar la segunda intervención del episodio 2008-09 | **−16,24 AIC** en PGAS, **−1,09** en ITCER |
| Corridas que la encontraron | **1 de 8** |

Es la palanca de mayor valor medido de todo el proyecto, y se pierde ocho de
cada nueve veces.

### 1.3 Por qué es difícil de verdad

Porque **la forma no se identifica a ojo**. `fue` permite especificar la
intervención como una función lineal de transferencia (FLT), es decir modelizar
un suceso con varios parámetros; en cuanto `s` crece, la figura que se ve en el
gráfico deja de tener una lectura obvia. Dos impulsos en el nivel pueden
aparecer, en primeras diferencias, con un aspecto que no sugiere dos impulsos.

Ésa es la razón de que esto se enseñe con simulador (`SRC/LTF/`), y la razón de
que el simulador sea parte de la solución y no un accesorio.

---

## 2. El lenguaje homogeneizado: todo al nivel de la serie

**Convenio:** toda intervención se especifica **en el nivel de la serie**, sea
cual sea la `d` con la que se esté trabajando. Sin este convenio, «escalón»
significa una cosa en `d=0` y otra en `d=1`, y el analista no puede razonar.

### 2.1 El diccionario nivel ↔ primeras diferencias

Con $\nabla y_t = y_t - y_{t-1}$:

| En el NIVEL | En primeras diferencias | Suma en ∇ |
|---|---|---|
| escalón ω en T | **un impulso** ω en T | ω |
| impulso ω en T | **dos impulsos**: $+\omega$ en T, $-\omega$ en T+1 | **0** |
| dos impulsos ($\omega_0$ en T, $\omega_1$ en T+1) | **tres impulsos**: $+\omega_0$, $\omega_1-\omega_0$, $-\omega_1$ | **0** |

Y la lectura que importa: **un escalón en el nivel es un efecto permanente; un
impulso en el nivel es un efecto transitorio.** La suma de la respuesta en ∇ es
la ganancia a largo plazo, y **ganancia cero ⟺ transitorio**.

### 2.2 La familia anidada — la solución propuesta

En vez de *adivinar* la forma, se estima la general y se contrasta una
restricción. Especificando **N escalones consecutivos en el nivel** en
T, T+1, …, T+N−1 con pesos $\omega_0,\dots,\omega_{N-1}$:

- nivel en T: $\omega_0$
- nivel en T+1: $\omega_0+\omega_1$
- nivel en T+N−1 y en adelante: $\sum_i \omega_i$ ← **la ganancia a largo plazo**

Si $\sum_i \omega_i = 0$, el nivel vuelve a la línea base tras N−1 períodos:

> **N escalones en el nivel con ganancia cero ≡ N−1 impulsos en el nivel**,
> es decir, un episodio de duración N−1.

Comprobación con N=3: ganancia cero deja el nivel en $\omega_0$ en T,
$\omega_0+\omega_1$ en T+1, y 0 desde T+2 — dos períodos alterados y vuelta a
la base: **dos impulsos en el nivel.** ✓

**Por qué esta formulación es la correcta:**

1. **Una sola familia anidada.** No se elige entre formas rivales por una regla:
   se estima la general y se contrasta hacia dentro.
2. **La restricción es UNA combinación lineal**, $\sum\omega_i = 0$. Contraste
   con 1 grado de libertad — un Wald sobre $g=\alpha\cdot\omega$ con
   $V(g)=\alpha\,\text{COV}\,\alpha^{\top}$, o un LR contra el modelo
   restringido.
3. **Contesta la pregunta del análisis de intervención** (permanente vs
   transitorio) con un contraste en vez de con una etiqueta.
4. **El episodio sale como subproducto**: N no se postula, se lee del episodio
   detectado en los residuos.

### 2.3 Alcance: d = 0, 1

Nos concentramos ahí. Con `d=2`, un impulso en la serie transformada equivale a
una **rampa** en el nivel, el diccionario de §2.1 tiene otra fila y la lectura
cambia. El simulador en C ya valida `d < 0 || d > 1`; el puerto mantiene esa
restricción y **falla explícitamente** en `d=2` en vez de dar una figura que se
leería mal.

---

## 3. La trampa del signo — antes de escribir una línea

`fue` almacena el numerador de la FLT con ω **restada** en los retardos ≥ 1:

$$\omega(B) = \omega_0 - \omega_1 B - \omega_2 B^2 - \cdots$$

Se ve en `calcnu()` de `fue_api.c` y en `ltf.c` (`nu[r+k] = -omega[k] + …`). Es
la convención que nos costó BUG-0066: leímos la respuesta del ITCER como
cuasi-cancelación (−0,05) cuando en realidad **suma** −17,92.

**Consecuencia directa para este nodo:** la ganancia es

$$\nu(1)=\frac{\omega(1)}{\delta(1)}=\frac{\omega_0-\omega_1-\cdots-\omega_s}{1-\delta_1-\cdots-\delta_r}$$

y por tanto el contraste de ganancia cero usa
$\alpha=(1,-1,-1,\dots,-1)$ — **no** $\alpha=(1,1,\dots,1)$.

Escribir el contraste con la suma directa daría un número plausible y
sistemáticamente equivocado. Va aquí, en cabeza del documento, para que no se
descubra dos meses después.

---

## 4. Inventario: qué existe y dónde

| Pieza | Dónde | Estado |
|---|---|---|
| **Simulador FLT** — (b,r,s,K,d,ω,δ) → IRF y SRF, con diferenciación | `SRC/LTF/LTF-1.0.2/ltf.c` | En C. Misma convención `calcnu`. Ya valida d≤1 |
| **Ganancia ν(1)=ω(1)/δ(1) + error típico** por método delta (jacobiano por diferencias centrales sobre el vector libre) | `drtran/irf.py` | **Hecho, y bien.** `report_irf` ya imprime `t = gain/se_gain` |
| **Retardo medio** con guarda de monotonía | `drtran/irf.py` | Hecho |
| **Wald sobre combinación lineal de ω** ($g=\alpha\omega$, $V=\alpha\text{COV}\alpha^{\top}$) | `art/interventions.py` | Existe la maquinaria — ver §4.1 |
| **Agrupación en episodios** | — | **No existe** |
| **Ganancia en `art`** | — | **No existe** |
| **Especificaciones rivales estimadas y comparadas** | — | **No existe** |

### 4.1 Auditoría del Wald — RESUELTA (2026-09-02)

Los tres defectos previstos se confirmaron, se levantaron y se arreglaron:
**BUG-0071**, **BUG-0072**, **BUG-0073**. Repro determinista sin datos y sin
`fue` en `bugs/BUG-0071-repro/repro.py`; pruebas en
`tests/test_bug_0071_wald_es_la_ganancia.py`.

**BUG-0071 — el contraste no era ninguna cantidad reconocible.** Usaba
α=(1,−δ₁,−δ₂,…), metiendo el denominador dentro de un contraste sobre el
numerador. Con ω=(0,80, −0,30) y δ=(0,50): la ganancia vale 2,20, el numerador
ω(1) vale 1,10, y devolvía 0,95. Ni νₖ, ni suma parcial de la respuesta, ni
nada. Del commit inicial, nunca revisado. Corregido a α=(1,−1,…,−1), con el
signo fijado por la **posición** en el vector ω completo (fijar ω₀ desplazaba
todos los signos un hueco) y los ω fijos entrando como constante.

**BUG-0072 — no corría en el caso que nos ocupa.** La guarda exigía δ libres, de
modo que N escalones sin denominador —la forma general del episodio— no recibían
contraste conjunto, sin aviso. Guarda reducida a `k > 1`.

**BUG-0073 — el rótulo decía χ²(k) con df=1.** El p-valor estaba bien; el rótulo
invitaba a la tabla equivocada (χ²(1)=3,84 frente a χ²(3)=7,81 al 5%).

### 4.2 El hallazgo que simplifica F1

Buscando cómo portar el método delta de `drtran` apareció que **para este
contraste no hace falta**:

> La ganancia es ν(1) = ω(1)/δ(1). Para **H₀: ν(1) = 0** el denominador es
> irrelevante: un cociente es cero exactamente cuando lo es su numerador,
> siempre que δ(1) ≠ 0. El contraste de ganancia nula es por tanto un **Wald
> lineal EXACTO sobre ω**, sin aproximación.

El método delta sigue haciendo falta para **un intervalo** sobre la ganancia, o
para contrastar una ganancia distinta de cero — no para la pregunta
permanente/transitorio, que es la del nodo. F1 se reduce en consecuencia.

Y con δ(1) → 0 el modelo es inadmisible (ganancia no acotada): `gain` vuelve
NaN, y quien habla de eso es `admissibility_problems` en `diagnosis.py`.

### 4.3 Comprobación sobre serie sintética

Con `step` de tres ω sobre ruido blanco, n=240, efecto en T=120:

| nivel impuesto | ω(1) | Wald χ²(1) | p | lectura |
|---|---|---|---|---|
| `[6, 4, 0]` — dos impulsos | −0,142 | 2,51 | 0,113 | **transitorio** ✓ |
| `[6, 6, 6, …]` — escalón sostenido | +5,858 | 4071,4 | 0,0000 | **permanente** ✓ |

La premisa de §2.2 queda comprobada, y medida como **tasa** sobre 15
realizaciones y no sobre un sorteo: potencia ≥ 0,80 y tamaño ≤ 0,20.

*Nota de método:* la primera versión de esa prueba parametrizaba el caso
permanente como `[6,6,6]`, que deja el nivel en 6 tres períodos y vuelve a
cero — un episodio transitorio de tres, no un cambio de nivel. La prueba falló
con potencia 0,07 y tenía razón: el fallo estaba en la prueba. El escalón
permanente tiene que llegar al final de la serie.

## 5. Plan de trabajo

### F0 · El simulador FLT en Python — ✅ HECHO (2026-09-02)

`src/art/ltf.py`. Función pura
`respuesta_flt(omega, delta, b, K, d) → RespuestaFLT`, con `describe_ltf`
encima para la figura y la herramienta MCP `intervention_plot` — el
**gráfico de intervención**, que es el nombre de este tipo de gráfico.

**Validado al dígito contra el C.** `tests/ltf_referencia/harness.c` lleva el
bloque numérico de `ltf.c` **copiado verbatim** —copiado y no reescrito a
propósito: así una divergencia es del puerto y no de una re-derivación de lo que
el C «quería decir»— y de él sale
`tests/fixtures/ltf_c_reference.json`. **18 casos, 0 divergencias, igualdad
exacta al bit** (escalones, impulsos, episodios, FLT con y sin denominador,
retardo muerto, δ oscilante, ω negativo, respuesta casi no acotada, y todos
también en primeras diferencias).

**Y el diccionario de §2.1 quedó comprobado por una vía independiente**, no
sólo escrito en prosa. `tests/test_ltf_port.py` lo tiene como afirmaciones
ejecutables, y el simulador reproduce la tabla exactamente: con ω=(6,2,4), que
da ω(1)=0, el camino del nivel es 6, 4, 0, 0, … —dos impulsos en el nivel— y en
primeras diferencias +6, −2, −4, que es `+ω₀, ω₁−ω₀, −ω₁` con ω₀=6 y ω₁=4.

Detalle de lectura que el puerto deja claro y conviene retener: **`srf` con d=0
ES el camino del nivel**, y es la columna que contesta la pregunta del nodo. La
figura lleva cuatro paneles —IRF y SRF × nivel y diferencias— porque la pregunta
del analista, «¿lo que veo es compatible con esto?», sólo se contesta viendo la
misma respuesta en las dos escalas a la vez.

Guardas: `d≥2` levanta `ValueError` nombrando la rampa; también `K ≤ s` y `b<0`.
Con δ(1)=0 la ganancia vuelve NaN y la presentación dice **INADMISIBLE** en vez
de dibujar una convergencia que no existe.

### F0b · El gráfico de intervención superpuesto — ✅ HECHO (2026-09-02)

`art.ltf.superpone` y `describe_superposicion`. Pone la hipótesis **encima de
lo observado**, en el ENTORNO del suceso y no sobre la serie entera: sobre 120
residuos la estructura interna de un suceso es ilegible; recortada a ±8 se lee.

**Tres números que separan tres preguntas**, y que se leen sin mirar la figura
—así sirven también al carril autónomo, que era la duda al plantearlo:

| | qué contesta | cómo se lee mal si se confunde |
|---|---|---|
| `escala` | la **amplitud** | — |
| `r2` | la **forma** | un R² bajo NO es falta de tamaño: es otro perfil |
| `z_resto` | lo que queda sin explicar | el más interpretable de los tres |

Medido sobre un DGP de dos impulsos de nivel (9 y 6) con d=1:

| hipótesis | escala | R² | mayor resto | |
|---|---|---|---|---|
| ω=(9, 3, 6) — la correcta | **1,071** | 0,887 | z=+1,62 | cubre |
| ω=(9, 3, 3) — deja cola | 1,183 | 0,851 | z=+1,62 | cubre |
| ω=(1) — un escalón | 9,491 | 0,559 | z=+3,85 | no cubre |
| ω=(1,1) — un impulso | 7,065 | 0,618 | z=+3,85 | no cubre |

Sobre el modelo **ajustado** con el DGP verdadero, la escala sale **0,9919**.

**El límite, escrito como prueba y no como nota al pie.** La superposición **no
distingue (9,3,6) de (9,3,3)** —la correcta de la que deja cola permanente—:
0,887 contra 0,851. La diferencia está en la **ganancia a largo plazo**, que es
una propiedad del comportamiento futuro y no de la forma local. Eso lo dirime el
contraste ω(1)=0. El reparto es el bueno: **el gráfico descarta lo incompatible
barato, y el contraste ve lo que el gráfico no puede.**

**Nombre.** El tipo de gráfico se llama **gráfico de intervención**
(*intervention plot*), y con ese nombre las dos herramientas que había —la
hipótesis sola y la superpuesta— son la misma cosa: se funden en
**`intervention_plot`**, con `inp_path` opcional. Sin él dibuja la hipótesis;
con él y con `at`, la superpone.

### F1 · La ganancia y su contraste — *en buena parte hecha por la auditoría*

Lo que la auditoría (§4.1-4.2) ya dejó en pie:

- ✅ `omega_1` = ω(1) con la convención de signo correcta;
- ✅ `gain` = ω(1)/δ(1), NaN si δ(1) ≈ 0;
- ✅ el contraste de **ganancia nula**, exacto y sin método delta, para
  cualquier intervención con más de un ω, lleve denominador o no;
- ✅ la presentación que dice **permanente** o **transitorio** con el contraste
  y el valor de ω(1) delante, en vez de con una etiqueta heredada.

Lo que queda de F1:

- el **error típico de la ganancia** por método delta, portado de
  `drtran/irf.py`, para dar un **intervalo** sobre ν(1). No lo necesita el
  contraste, sí el informe;
- el **retardo medio** con su guarda de monotonía, que `drtran` ya tiene y que
  la escuela reporta siempre junto a la ganancia — la ganancia dice cuánto y el
  retardo medio dice cuándo;
- exponerlo por MCP.

### F2 · Episodios — ✅ HECHO (2026-09-02)

`src/art/episodes.py`: `agrupa_episodios(extreme, ventana, d) → [Episodio]`,
`describe_episodios` para la figura, `policy.decide_episodios` con
`THRESHOLDS["ventana_episodio"] = 2` **declarado**, y la herramienta MCP
`residual_episodes`.

Cada `Episodio` publica `duracion`, `duracion_nivel`, `n_extremos`, `huecos`,
`cohesion`, `n_escalones` y `at_0based(offset)`. La unión es por
**encadenamiento** —A-B y B-C dentro de ventana unen A, B y C— porque es la
lectura natural de «el mismo suceso»; y por eso el episodio publica los huecos y
la cohesión: para que una cadena larga se VEA. `parece_encadenado` avisa cuando
la duración pasa de 4 o la cohesión baja de 0,6, porque eso es más probable que
sea estructura no modelizada que un suceso.

**Lo que esto disuelve.** La dicotomía escalón/impulso deja de ser una **regla**
y pasa a ser un **contraste**. Un episodio aislado da dos escalones; si ω(1)=0
es un impulso de nivel (transitorio) y si no, un cambio de nivel (permanente),
y lo dice `test_intervention` y no una comprobación de adyacencia.

**Y el aviso donde el analista ya está mirando.** La razón medida de que 7 de 8
corridas no encontraran el segundo choque de 2008-09 es que **nada en la salida
decía que esos dos anómalos eran un suceso**. Una herramienta que nadie llama no
lo arregla, así que `residual_outlier_scan` lleva ahora un aviso en cabecera
cuando hay extremos que no están solos, con el tramo y la duración en el nivel.

#### La segunda conversión, que se descubrió comprobando

Los residuos están **diferenciados**, y por el diccionario de §2.1 **L impulsos
en el nivel se ven como L+d extremos**. Así que la duración medida sobre los
residuos NO es la duración del suceso:

    duración en el nivel = duración en residuos − d

Salió en la comprobación de punta a punta: sobre un DGP con dos impulsos de
nivel y d=1, el episodio salía de tres períodos y pedía **cuatro** escalones
donde hacen falta **tres**. El defecto tenía la forma exacta de BUG-0030 —«esta
función no recibía `d`, así que no podía hacer la conversión aunque quisiera»— y
por eso `agrupa_episodios` la recibe y `policy.decide_episodios` la propaga.

Es decir: **hay dos conversiones entre residuos y nivel, no una.** La posición
(el desfase `d + D·s`, BUG-0030/0067) y la **duración**. La segunda no estaba
escrita en ningún sitio hasta ahora.

Verificado de punta a punta: DGP con dos impulsos de nivel y d=1 →
`dur. resid. 3 · dur. nivel 2 · 3 escalones`.

## 2bis. La navaja de Ockham gobierna el nodo

Añadido el 2026-09-02, y **reordena F3**.

### El principio

**Lo más obvio primero.** El análisis de intervención sube por una escalera de
sofisticación, y sólo se sube un escalón cuando el de abajo no se sostiene.

El caso que lo enseña: se observa un escalón negativo enorme en primeras
diferencias de un índice de precios.

1. **Lectura de dominio.** Por dominio es poco usual que los precios bajen de
   forma permanente de esa manera. La forma simple ya es sospechosa.
2. **Información extramuestral.** Se busca lo que explicaría la forma SIMPLE:
   una reducción de impuestos, una caída considerable del precio de los
   combustibles, un cambio de metodología del índice.
3. **Sólo si no aparece**, se empieza a buscar un episodio — que es la forma más
   sofisticada. Dos impulsos en el nivel pueden dar esa configuración en
   primeras diferencias.

### La escalera

| escalón | forma | se sube cuando |
|---|---|---|
| **0** | nada — el anómalo no lo es | *(punto de partida)* |
| **1** | UNA intervención escalar | el residuo es extremo de verdad |
| **2** | **episodio**: L impulsos en el nivel | la 1 no tiene explicación extramuestral **y** no es adecuada |
| **3** | FLT con denominador | la respuesta decae y el 2 no lo recoge |

El escalón 0 no es retórico: la sobre-intervención en meses estacionales fue una
de las causas raíz del run 1 de SF_MEG. Intervenir la señal no es modelizarla.

### Lo que esto PROHÍBE, y es lo importante

**El AIC no arbitra la subida de escalón.** Compara *dentro* de un escalón, o
confirma una subida ya justificada por otra cosa. Una F3 que estime las
rivales y se quede con el mejor AIC sube siempre que ajuste mejor, y eso es
exactamente lo contrario de la navaja: el modelo más sofisticado casi siempre
ajusta mejor, porque tiene más parámetros.

Lo que justifica subir es (a) implausibilidad de dominio de la forma simple,
(b) ausencia de explicación extramuestral, o (c) inadecuación — no Δ AIC.

### La explicación tiene que explicar la FORMA, no sólo la fecha

Refinamiento que hace la regla operativa. Una bajada de impuestos explica un
escalón **permanente**. Una huelga de una semana explica un impulso
**transitorio**. Si el analista aporta una explicación de suceso permanente pero
el contraste de ganancia dice transitorio, **la explicación no aplica** y se
sube igual.

De modo que el registro extramuestral y el contraste de ganancia tienen que
**concordar**, y cuando no concuerdan eso es información y hay que enseñarla:

| explicación aportada | contraste de ganancia | lectura |
|---|---|---|
| permanente (impuesto, metodología) | rechaza ganancia nula | **concuerdan** → escalón 1, cerrado |
| permanente | no rechaza | **discrepan** → la explicación no cubre lo que hay: subir |
| transitoria (huelga, temporal) | no rechaza | **concuerdan** → impulso de nivel, cerrado |
| ninguna | cualquiera | subir al escalón 2 y mirar el episodio |

### Lo que esto exige de la herramienta, y hoy no existe

**Una pregunta cuya respuesta no está en los datos.** Todos los nodos actuales
leen evidencia de la serie. Éste necesita lo que el analista sabe del mundo:
«esto es una caída permanente del 4,2 % en un índice de precios en 2008Q4 —
¿hay un suceso conocido?». Es evidencia, y sólo la tiene el analista; encaja con
«evidencia ≠ juicio» pero **por un canal que la herramienta no tiene abierto**.

Va al guion como `evidencia` del nodo, que es exactamente para lo que está el
campo.

*Nota para el carril autónomo, y es medible:* un LLM puede **saber** que Bolivia
subió los carburantes en diciembre de 2010, o que España subió el IVA en 2012.
Es una asimetría real entre carriles —el guiado pregunta, el autónomo a veces ya
lo sabe y a veces lo inventa— y es contrastable. Interesa al nodo y al artículo.

### La lectura de dominio, que ART ya puede hacer

`policy.decide_domain` devuelve `price_index`. Con eso la herramienta puede
decir, sin preguntar a nadie, que **una caída permanente de nivel en un índice
de precios es poco usual**, y por tanto que la forma simple necesita respaldo
antes de aceptarse. Es una regla de dominio y su sitio es `policy`.

### Y el simulador es el árbitro de la compatibilidad

Cuál sea la configuración de nivel compatible con una forma observada en
diferencias no se decide de memoria: se dibuja. El `intervention_plot`
(F0) está exactamente para eso — poner la hipótesis al lado de lo observado
antes de estimar nada.

---

## 2ter. La regla de Treadway — cómo se sabe si funcionó

Aportada el 2026-09-02, y cierra el bucle: §2bis dice cómo ELEGIR la
representación, ésta dice cómo saber si la elegida **era la buena**.

> «Si intervienes en una fecha o fechas, no puedes tener de vecino un anómalo,
> ni antes ni después. Básicamente esa es evidencia de que la representación que
> has elegido es errónea. Una característica de que la intervención ha
> funcionado bien es que los residuos en fechas de intervención están en la
> media de los residuos, que debería ser cero. No es algo que bloquea, es
> diagnosis.»

### Las dos reglas salen de la misma ecuación

El modelo es `z_t = ν(B)ξ_t + N_t`. Sea `π(B) = θ(B)⁻¹φ(B)∇^d` el filtro que
blanquea. La derivada de la verosimilitud respecto de cada ω_j da el **regresor
filtrado** `x_t^(j) = π(B)·[B^j/δ(B)]·ξ_t`, y la condición de primer orden es

    Σ_t  a_t · x_t^(j) = 0     para todo j libre

**Los residuos quedan ortogonales a cada regresor filtrado de la intervención** —
las ecuaciones normales de una regresión, y lo son porque con ARMA y δ fijos la
intervención entra linealmente.

**De ahí la regla 2.** Para un impulso puro el regresor es `x_t = π_{t−T}` y la
condición queda `a_T = −Σ_{k≥1} π_k·a_{T+k}`. Sin ARMA y con d=0 se tiene
π(B)=1, luego **a_T = 0 EXACTAMENTE**: un ω libre absorbe esa observación
entera, igual que una variable ficticia en regresión. Con ARMA es una
combinación pequeña de los residuos siguientes.

**De ahí la regla 1.** La condición sólo obliga a ortogonalidad frente a los
regresores **que se han ajustado**. Si el suceso ocupa T y T+1 y sólo se ajusta
un impulso en T, la parte de T+1 no tiene dónde ir: cae entera en `a_{T+1}`.
**El vecino anómalo ES la parte no modelizada del mismo suceso.**

### Verificado, y el enunciado de la escuela es el preciso

Sobre ruido blanco con un impulso libre, d=0 y sin ARMA:

| | |
|---|---|
| residuo **crudo** en la fecha | **−3,5·10⁻⁸** — cero |
| media de los residuos | +0,017612 |
| z en la fecha | **−0,019097** = −media/sd |

Es decir: `a_T = 0` exacto, y el **tipificado se queda en la media de los
residuos**, no en cero. Por eso la escuela lo enuncia «están en la media» y no
«son cero» — con μ estimado la media es ~0 y coinciden, con μ fijado no. El
`InterventionFitCheck` publica los dos, el crudo y el tipificado.

### Las dos lecturas de un vecino anómalo

Las dos son errores de representación:

1. **La forma se queda corta** — hay episodio. Es el caso de §2.2.
2. **La fecha está desplazada** — y la verosimilitud casi no lo distingue
   (BUG-0030: ω = +4,347 mal colocado frente a −4,353 bien colocado, con
   Δ logL = 0,03). **Este contraste ve lo que el ajuste no.**

### Dónde vive

`interventions.check_intervention_fit(model)`, y se presenta dentro de
`test_interventions` —donde el analista ya está juzgando la intervención— y no
en una herramienta aparte: **un t significativo sobre ω no dice que la
representación sea la correcta**, y ésa es justo la pregunta que queda abierta
después del contraste. Demostrado de punta a punta: un impulso sobre un episodio
de dos períodos da residuo crudo −2,5·10⁻⁷ en su fecha y un vecino de **+6,49**
detrás.

---

### F3 · Las especificaciones rivales — ✅ HECHO (2026-09-02)

`src/art/escalera.py`: `escalera_de_ockham(model_base, episodio, dominio)` y
`describe_escalera`, con la herramienta MCP **`intervention_ladder`**.

Estima los peldaños **en orden** sobre el mismo modelo base:

| peldaño | forma | parámetros |
|---|---|---|
| **1a** | escalón en el nivel — efecto PERMANENTE | 1 |
| **1b** | impulso en el nivel — efecto TRANSITORIO | 1 |
| **2** | episodio: L+1 escalones en el nivel | L+1 |

1a y 1b cuestan **lo mismo** y **no están anidadas entre sí**: son las dos
lecturas simples, y cuál es la buena no lo decide el ajuste sino el dominio y lo
que se sepa del suceso.

#### Lo que la implementación PROHÍBE

`razones_para_subir` es una lista, y si está vacía **la escalera se queda
abajo aunque el peldaño 2 ajuste mejor**. Las razones son, en orden: Treadway
(vecino anómalo), inadecuación (Q o JB), duración del episodio > 1, y dominio
(caída permanente en un `price_index`). El AIC **no está** en la lista; sale en
el texto con su aviso al lado.

#### Medido

Episodio verdadero de dos impulsos de nivel (9 y 6), d=0:

| peldaño | AIC | ω(1) | vecino | adecuado | se sostiene |
|---|---|---|---|---|---|
| 1a escalón | 643,00 | +0,156 | después | ✗ | no |
| 1b impulso | 584,55 | +8,750 | después | ✗ | no |
| **2 episodio** | **540,22** | +0,045 (p=0,562) | ninguno | ✓ | **sí** |

Sube por tres razones —Treadway, inadecuación y duración— y el ΔAIC de 44,3
**no participa en la decisión**. El contraste de ganancia lee TRANSITORIO, que
es el DGP.

Escalón permanente verdadero, d=1:

| peldaño | AIC | ω(1) | vecino | adecuado | se sostiene |
|---|---|---|---|---|---|
| **1a escalón** | **535,59** | +8,750 | ninguno | ✓ | **sí** |
| 1b impulso | 582,11 | +3,984 | después | ✗ | no |
| 2 episodio | 536,88 | +9,531 | ninguno | ✓ | sí |

**Razones para subir: ninguna ⇒ recomendado 1a**, aunque el peldaño 2 también
se sostiene. Es la navaja funcionando cuando más fácil sería saltársela. Y
ω(1)=+8,75 recupera el escalón real de 9, lo que confirma que la intervención se
aplica **en el nivel** aunque el modelo lleve d=1.

#### La pregunta que no está en los datos

La presentación cierra preguntando por la **información extramuestral**, y
adapta la pregunta a la forma que la lectura simple sugiere. Es el único nodo de
`art` cuya evidencia no sale de la serie. La recomendación lo dice con todas las
letras: *si hay un suceso conocido que explique la FORMA simple, la simple gana
aunque ajuste peor*.

#### Un hallazgo lateral, de las pruebas

**Con `d=0` un escalón permanente NO aparece como atípico.** Sube la media y la
varianza de los residuos y ningún |z| pasa de 3: el escaneo de anómalos busca
espigas, no cambios de nivel. En ∇, en cambio, un escalón de nivel es UN impulso
—el diccionario de §2.1— y por eso se ve en la práctica, donde estas series se
trabajan diferenciadas. Queda anotado en las pruebas.

### F4 · El nodo en el protocolo

Cablear en `suggest_intervention_form` y en `guided_identification`, con su nodo
de guion (`node = {nodo, decidido, evidencia, alternativas}`) y las alternativas
rellenas de verdad — que es justo lo que las hace un argumento y no una etiqueta.

### Orden y dependencias

```
   §4.1 auditoría ✅ ──→ F1 (ganancia) ─ parcialmente hecha ─┐
F0 (simulador) ────────────────────────┐                     │
                                       ├─→ F3 (rivales) ──→ F4 (nodo)
F2 (episodios) ────────────────────────┘                     │
                                                             │
        (el contraste que F3 necesita YA está) ──────────────┘
```

La auditoría está despejada, y con ella **el contraste sobre el que se apoya F3
ya existe y está probado**. F0 y F2 son independientes y pueden ir en paralelo;
lo que resta de F1 (intervalo sobre la ganancia, retardo medio) no bloquea a
nadie. F3 necesita F0 —como oráculo de las formas— y F2. F4 cierra.
