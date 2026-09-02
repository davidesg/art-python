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
encima para la figura y la herramienta MCP `simulate_intervention_shape`.

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

### F2 · Episodios

Agrupar residuos extremos separados ≤ `w` períodos en un episodio con su
extensión. `w` es **parámetro declarado**, no número mágico enterrado; por
defecto 2-3 y expuesto al analista.

Sustituye la comprobación de adyacencia de `decide_form`. Salida: lista de
episodios con su duración, no lista de atípicos sueltos.

### F3 · Las especificaciones rivales

Para un episodio de duración k, presentar la familia anidada estimada:

- **general:** k+1 escalones en el nivel;
- **restringida:** ganancia cero ⟹ k impulsos en el nivel;
- y la lectura escalar simple, para el caso k=1.

Estimadas todas, con su AIC, su ganancia y su contraste, y **comparables** —
que es lo que hoy no hay. Aquí es donde se recuperan los 7-15 puntos de AIC.

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
