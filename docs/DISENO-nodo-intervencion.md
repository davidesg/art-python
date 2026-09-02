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

### 4.1 Auditoría pendiente ANTES de construir

El Wald de `test_intervention` tiene dos cosas que hay que resolver, y caen
justo en medio de lo que vamos a construir:

**(a) El contraste no es la ganancia.** Usa
`alpha_vec = [1.0] + [-d for d in free_dl[:k-1]]`, es decir
$\alpha=(1,-\delta_1,-\delta_2,\dots)$ — los coeficientes del **denominador**
puestos sobre el numerador. Eso no es $\omega(1)$, no es la ganancia, y no
reconozco qué cantidad es. Hay que decidir si es un contraste deliberado con
una lectura que se nos escapa, o un error.

**(b) Sólo dispara si hay δ libres.** La guarda es
`if k > 1 and any(f for f in dlf)`. Para el caso de §2.2 —N escalones **sin**
denominador— el Wald **no se ejecuta nunca**. Es exactamente el contraste que
necesitamos y hoy no está disponible.

**(c) La etiqueta miente.** `summary()` imprime `Wald χ²({len(self.omega)})`
mientras el cálculo usa `df=1` (correctamente, porque `g` es escalar). El número
está bien y el rótulo mal — la clase de defecto que fue 12 de 25 en la sesión
anterior.

Los tres se levantan como defectos numerados con repro sintético, según el
convenio de `bugs/`.

---

## 5. Plan de trabajo

### F0 · El simulador FLT en Python — *primero, y es la clave*

Puerto de `generate_plots` a `art/ltf.py`: función pura
`(b, r, s, K, d, ω, δ) → (irf, srf)`, con el trazado encima y separado. Falla
explícitamente en `d≥2`.

**Por qué va primero aunque no sea lo más vistoso:** se convierte en el
**oráculo de contraste** de todo lo demás. Cualquier afirmación del tipo «un
episodio de dos impulsos se ve así» pasa a ser comprobable contra una figura
generada, y las pruebas de F1-F3 se escriben contra ella en vez de contra mi
aritmética. Además da al analista lo que hoy no tiene: **dibujar la hipótesis al
lado del patrón observado** y ver si son compatibles — evidencia, no veredicto,
que es la filosofía de la casa.

Validación: al dígito contra el binario en C sobre una batería de casos.

### F1 · La ganancia y su contraste

`nu(1) = ω(1)/δ(1)` con la convención de signo de §3, su error típico y el
contraste de ganancia cero.

- Caso sin δ (el de §2.2): **lineal en ω**, Wald con $\alpha=(1,-1,\dots,-1)$.
  Reutiliza la maquinaria de `interventions.py` una vez resuelta la auditoría §4.1.
- Caso con δ: **razón**, método delta. Se porta de `drtran/irf.py`, que ya lo
  tiene resuelto y verificado.

Entregable: la función, y el bloque de presentación que dice **permanente** o
**transitorio** con el contraste detrás y no con una etiqueta heredada.

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
F0 (simulador) ──┬─→ F1 (ganancia) ──┐
                 │                    ├─→ F3 (rivales) ──→ F4 (nodo)
      F2 (episodios) ─────────────────┘
   §4.1 auditoría ──→ F1
```

F0 y F2 son independientes y pueden ir en paralelo. La auditoría §4.1 bloquea
F1. F3 necesita F1 y F2. F4 cierra.
