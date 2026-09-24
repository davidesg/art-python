# El dominio en los órdenes — un procedimiento, no una regla por disyuntiva

Documento de diseño. Abierto 2026-09-24, a partir de la charla sobre el
protocolo y del recuento de los nodos de órdenes de SF_MEG y de la réplica del
TFM. **No hay nada implementado**; las decisiones abiertas están en §10.

---

## 0. En una página

El dominio funciona en λ porque hay una regla declarada (`decide_domain` →
`decide_lambda`). En los órdenes ARIMA/SARIMA no funciona: sólo existe una regla,
la del empate AR(1)/MA(1) en precios, y todo lo demás lo decide la similitud y el
AIC. El LLM **tiene** el conocimiento —lo usa cuando improvisa— pero no lo aplica
de forma sistemática ni coherente entre corridas.

La solución no puede ser una regla por disyuntiva: AR(1)/MA(1), AR(2)/MA(2),
SAR/SMA, ARMA(1,1)/AR(2)… no se acaban, y cablear el criterio en reglas es
exactamente de lo que murieron los sistemas expertos. La propuesta es un
**procedimiento general** en cuatro piezas:

1. **Declarar las expectativas del dominio en el nodo `dominio`, antes de ver
   los órdenes.** Qué dinámica espera la teoría para esta clase de serie, y por qué.
2. **Una ficha de dinámica implícita**, calculada por el motor cuando hay
   empate: respuesta al impulso, raíces, forma de la previsión, persistencia de
   largo plazo y la diferencia *material* entre los candidatos.
3. **Una decisión con formato fijo**, que cita la expectativa declarada.
4. **Guardas y materialidad**: sólo ante un empate genuino, nunca contra la
   adecuación, y diciendo si la elección cambia la previsión o sólo la lectura.

La regla AR(1)/MA(1) deja de ser una regla y se convierte en el **ejemplo
resuelto** del procedimiento.

**Un matiz que ordena todo lo demás (§5):** un MA no se interpreta solo, se
interpreta con el operador de diferencias al que acompaña. La misma disyuntiva
se resuelve al revés según d y D: con d=1 un IPC pide AR(1) con φ>0; con d=2, un
MA(1) con 0<θ<1, que es una media estocástica de la inflación; con D=1, un SMA(1)
con 0<Θ<1, que es estacionalidad estocástica; con D=0, un SAR(1) con Φ>0. Las
expectativas se declaran sobre el **proceso en niveles**, no sobre «AR o MA».

---

## 1. El problema, medido

**Recuento sobre los guiones** de `SF_MEG/empirical/` y de la réplica del TFM
(`Tesis_Michael{,_DS}/replica/`), sin duplicados, 28 ago – 12 sep 2026:

| | n |
|---|---|
| nodos de órdenes | 97 |
| declaran un empate estadístico | 33 |
| dan un argumento económico (revisado a mano) | 11 |
| de ellos, persistencia de precios: la regla AR(1), que está declarada | 7 |

**Donde no hay regla, no hay coherencia.** PGAS, 9 análisis independientes:
AR(2) 4 veces, MA(2) 3, AR(1) 1, MA(1) 1. En la comparación nodo a nodo contra
el oráculo guiado, los órdenes de PGAS coinciden en **1 de 8** corridas
autónomas. Sólo dos análisis invocaron dominio, y **en direcciones opuestas**:

* «la fuerte persistencia y el ciclo boom-bust del precio del gas» → AR(2)
  (DeepSeek, run4);
* «una fórmula de indexación contractual a una cesta de fuelóleos con retardo …
  explica por qué el efecto es de MEMORIA FINITA (MA)» → MA(2) (Claude, run2).

Las dos historias son plausibles. Ése es el problema: elegida *después* de ver
qué modelo ajusta, la historia no es un criterio, es un camino más del jardín
que se bifurca.

**En SF_MEG** las disyuntivas AR(2)/MA(2) (DE_CPI y DE_CORE con MA(2); ES_CORE,
IE_CPI e IE_CORE con AR(2)) se resolvieron por similitud y AIC, sin un solo
argumento de dominio registrado.

**La heurística tampoco lo hace**: `policy.decide_orders` toma el primero del
ranking y no aplica ni siquiera la regla AR(1) (lo dice el propio texto de las
instrucciones: «todavía NO la aplica sola»).

### El caso que lo resume: PGAS

Misma serie (∇ln del precio de exportación del gas), mismo escalón en 2009T1,
μ=0, tres parámetros cada uno:

| | AR(2), oráculo guiado | MA(2), Claude |
|---|---|---|
| fichero | `guiado/PGAS/PGAS_m20.pre` | `run4/PGAS/PGAS_m04.pre` (= run2 m04) |
| coeficientes | φ = (0,765; −0,264) | θ: (1 + 0,788B + 0,276B²) |
| ℓ | −289,745 | −289,280 |
| AIC | 585,49 | **584,56** |

La verosimilitud prefiere el MA(2) por ΔAIC = 0,93; el oráculo eligió el AR(2).
El dato no puede separarlos, y la decisión que se tomó no quedó escrita como
decisión de dominio en ninguno de los dos lados.

---

## 2. Por qué no una regla por disyuntiva

* **No escala.** Las disyuntivas crecen con los órdenes, con la parte
  estacional y con las intervenciones. Cada regla nueva necesita su alcance, su
  condición de empate y su justificación, y ninguna cubre el caso siguiente.
* **Repite el fracaso de los sistemas expertos.** ARIMAID o Mélard-Pasteels
  cablearon el criterio en reglas y quedaron frágiles ante el caso no previsto.
  La apuesta de art es que el LLM disuelve ese cuello de botella; convertirlo en
  un aplicador de reglas lo devuelve al punto de partida.
* **La regla AR(1)/MA(1) ya es un procedimiento disfrazado.** Su texto no dice
  «elige AR(1)»: dice *traduce cada candidato a la dinámica que implica* (IRF
  geométrica frente a pesos de previsión que alternan) *y contrástala con lo que
  la teoría espera de un precio*. Lo que hay que declarar es ese movimiento, no
  su resultado en un caso.

---

## 3. La razón de fondo

Una serie temporal es **una** realización de un proceso. Con una muestra finita,
modelos distintos generan correlogramas casi iguales en los retardos donde hay
información, y difieren donde no la hay. El AIC elige entonces por diferencias
que están dentro del ruido muestral.

El dominio contesta una pregunta distinta: **qué proceso generador es plausible
para esta clase de serie.** Es lo que ya hace en λ. En los órdenes la elección
no es binaria y el espacio es mayor, así que el dominio hace *más* falta, no
menos.

---

## 4. El procedimiento

### 4.1 Declarar las expectativas, antes

El nodo `dominio` registra hoy la **clase** (`price_index`, `multiplicative`,
`ratio`, `generic`), que gobierna λ. Se amplía con las **expectativas
dinámicas** de esa clase, en texto razonado y en términos que el motor pueda
contrastar:

| dimensión | ejemplos de expectativa |
|---|---|
| persistencia | «alta: rigideces, indexación» / «baja: mercado con arbitraje» |
| ciclo | «posible, de 2–3 años: inventarios, cosechas» / «no esperado» |
| memoria finita | «sí, a k períodos: contratos indexados con retardo k» |
| reversión | «a la media tras choques» / «sin ancla» |
| estacionalidad | «de calendario (Semana Santa)» / «de oferta (cosechas)» |
| media | «la inflación tiene una media estocástica» / «oscila en torno a una media estable» |
| estacionalidad (tipo) | «estocástica: el patrón deriva» / «determinista: patrón fijo» |

Las dos últimas filas son las que §5 hace necesarias: con d=2 o D=1, la
disyuntiva de órdenes es en realidad una pregunta sobre *cuán estocástica es la
media o la estacionalidad*, y la expectativa tiene que estar dicha en esos
términos.

**Por qué antes.** Declarada antes de ver los candidatos, la expectativa
funciona como un preregistro: no se puede elegir la historia que mejor encaja
con el modelo que ya ganó. PGAS es el contraejemplo: con dos historias opuestas
disponibles, cualquier modelo tiene una justificación a posteriori.

**Lo que no es.** No es una predicción del orden («será un AR(2)»). Es una
afirmación sobre la dinámica del proceso, que después se contrasta con la de
cada candidato.

### 4.2 Detectar el empate

El procedimiento se activa cuando se cumplen **las tres** condiciones:

1. la identificación declara empate (hoy: `gap` de similitud < 0,05) **o** dos
   candidatos estimados quedan a ΔAIC < 2;
2. los dos candidatos tienen el mismo número de parámetros, o la diferencia no es
   significativa (LR, si están anidados);
3. los dos pasan la diagnosis (Q y JB).

Si falla la 3, no hay empate: manda la adecuación. Si falla la 2, manda el
contraste.

### 4.3 La ficha de dinámica implícita

Para cada candidato del empate, **el motor** calcula:

| | qué es | para qué |
|---|---|---|
| ψ₀…ψ_H | respuesta al impulso sobre la serie transformada | persistencia frente a memoria finita |
| raíces | reales o complejas; módulo; período | si hay ciclo, y de qué duración |
| pesos de previsión | sobre los niveles pasados; ¿alternan de signo? | la «historia» que cuenta el modelo |
| multiplicador de largo plazo | Σψ (efecto acumulado de un choque en el nivel) | cuánto importa la diferencia |
| diferencia de previsión | máx. \|ŷ_A − ŷ_B\| a horizontes 1…H, en unidades de σ | **materialidad** (§4.5) |
| lectura del par (∇, MA) | para cada MA que acompaña a una diferencia: 1−θ, y si 0<θ<1 | media o estacionalidad estocástica, y cuánto (§5) |
| distancia a la cancelación | módulo del MA frente a 1; si cae en la banda de cuasi-cancelación | si la pregunta es en realidad de d o D (§5.3) |

Piezas que ya existen: `ar_factorization` (raíces, módulo, período) y
`generate_forecast`. Lo que falta es el ψ, los pesos de previsión y ponerlo todo
en una sola ficha comparativa.

**El reparto de papeles no cambia.** El motor calcula la dinámica; el LLM la
*interpreta* contra la expectativa declarada. Es la misma división que en toda
la arquitectura: el LLM propone y razona, el motor juzga.

### 4.4 La decisión

Con formato fijo, en `guion_node`:

> Los datos prefieren **X** por ΔAIC = … (ΔBIC = …).
> **X** implica [dinámica]; **Y** implica [dinámica].
> La expectativa declarada en el nodo `dominio` era […].
> **Elijo …** porque …
> **Materialidad:** la diferencia de previsión a H = … es … σ.
> **Esto cambiaría si** … (qué evidencia revertiría la decisión).

Y un campo nuevo, `criterio ∈ {estadístico, dominio, uso}`, con una referencia a
la expectativa declarada cuando es `dominio`. Así estas decisiones se pueden
auditar y **contar**, que hoy exige leer 97 razones a mano.

### 4.5 Materialidad

Si las dinámicas apenas difieren, hay que decirlo: la elección es
**interpretativa** y casi no cambia la previsión. Es información para quien usa
el modelo, y protege de sobrevender el argumento de dominio.

---

## 5. El orden de integración cambia la lectura

Un MA no se interpreta solo: se interpreta **con el operador de diferencias al
que acompaña**. Por eso el mismo empate AR/MA se resuelve al revés según d y D,
y una regla escrita para d=1 —la del empate AR(1)/MA(1), cuyo alcance ya dice
«índice en logaritmos con d=1»— no cubre ni d=2 ni la parte estacional.

Convenio: Box-Jenkins, (1 − θB). art imprime el polinomio explícito, así que
(1 + 0,42B) es θ = −0,42.

### 5.1 El par (∇, MA) es una media estocástica

Si ∇y_t = (1 − θB)a_t con **0 < θ < 1**, la previsión del nivel es una media
móvil exponencial de los niveles pasados, con constante 1 − θ: los pesos
(1−θ)θ^(j−1) son todos positivos y suman 1. Es decir, **y tiene una media local
estocástica**, y 1 − θ es la fracción de cada choque que la mueve de forma
permanente.

* **θ → 1**: la media casi no se mueve. En el límite el MA cancela la diferencia:
  la media es determinista y la diferencia sobraba. Ésa ya no es una pregunta de
  dominio sino de d (o de D), y la contestan los contrastes de
  sobrediferenciación (DCD y Shin-Fuller en f=0; MEG/DCD_f por frecuencia
  estacional).
* **θ → 0**: la media es un paseo aleatorio puro.
* **θ < 0**: la «media exponencial» tendría constante mayor que 1, y los pesos
  alternan de signo: la previsión sobrepasa y corrige. No es una media, y para
  una serie persistente no es un proceso generador defendible.

Pesos de previsión sobre los niveles pasados, calculados (π₁, π₂, π₃, π₄…):

| modelo, con d=1 | π₁ … π₅ | lectura |
|---|---|---|
| MA(1), (1 − 0,70B) | 0,30; 0,21; 0,15; 0,10; 0,07 | media exponencial: media estocástica |
| MA(1), (1 + 0,42B) | 1,42; −0,60; 0,25; −0,11; 0,04 | alterna sin fin: sobrepasa y corrige |
| AR(1), φ = 0,40 | 1,40; −0,40; 0; 0; 0 | prolonga el último cambio: persistencia |

### 5.2 La misma disyuntiva, cuatro situaciones (un IPC)

El signo de la autocorrelación en el retardo decide **qué** dos candidatos
empatan; el dominio decide entre ellos.

| operador | autocorr. | empate típico | plausible en un IPC | por qué |
|---|---|---|---|---|
| d=1 (∇ln = inflación) | ρ₁ > 0 | AR(1) φ>0 frente a MA(1) θ<0 | **AR(1)** | persistencia de la inflación; el MA con θ<0 alterna |
| d=2 (cambio de la inflación) | ρ₁ < 0 | AR(1) φ<0 frente a MA(1) 0<θ<1 | **MA(1)** | la inflación tiene media estocástica y 1−θ mide cuánto; el AR con φ<0 hace oscilar la inflación |
| D=1 (∇₁₂) | ρ₁₂ < 0 | SAR(1) Φ<0 frente a SMA(1) 0<Θ<1 | **SMA(1)** | estacionalidad estocástica y 1−Θ mide cuánto; Θ→1 es estacionalidad determinista |
| D=0 | ρ₁₂ > 0 | SAR(1) Φ>0 frente a SMA(1) Θ<0 | **SAR(1)** | persistencia anual de las desviaciones; análogo exacto de d=1 |

El principio que unifica las cuatro filas: **con autocorrelación positiva en el
retardo, persistencia (AR con coeficiente positivo); con autocorrelación
negativa, una media estocástica (MA con 0<θ<1 emparejado con la diferencia de
ese retardo).** Lo implausible, en los cuatro casos, es la representación cuya
previsión alterna u oscila sin un mecanismo que lo explique.

Queda fuera un caso que no está resuelto: autocorrelación estacional negativa
con D=0 (un SMA con Θ>0 **sin** diferencia estacional con la que emparejarse). No
tiene lectura de media estocástica; puede ser sobreajuste de los armónicos o una
intervención sin tratar. Se deja abierto (§10).

### 5.3 Lo que implica para el procedimiento

1. **Las expectativas se declaran sobre el proceso en niveles**, no sobre la
   forma del modelo: «la inflación es persistente», «la inflación tiene una media
   estocástica», «la estacionalidad deriva». La ficha traduce cada candidato a
   esas propiedades **condicionando en (d, D)** (§4.3).
2. **θ o Θ cerca de 1 no se decide en el nodo de órdenes**: es una arista hacia
   atrás, al nodo d o al de estacionalidad, donde lo contesta un contraste. El
   nodo de órdenes puede devolver la búsqueda; es otro caso de que el protocolo
   es un grafo.
3. **La propia d es una pregunta de dominio.** Si la inflación de un IPC es
   estacionaria alrededor de una media estable (d=1) o tiene una media
   estocástica (d=2) tiene literatura propia —la persistencia de la inflación—,
   y la expectativa debería declararse en el nodo `dominio` y contrastarse con la
   DCD. **run9 de SF_MEG (IPC España) es el ejemplo de cómo debería verse**, y lo
   hizo el LLM sin que el protocolo se lo pidiera:
   * en el primer paso de d declaró la expectativa: *«d=2 sería sobrediferenciar
     una tasa de inflación»*;
   * tras estimar, la DCD de sobrediferenciación apuntó a d+1; estimó d=2 con el
     MA factorizado, (1 − 0,961B)(1 + 0,404B), θ̂₁ = 0,961 (e.t. 0,022), y la DCD
     rechazó θ₁ = 1 (LR = 8,2 frente al crítico 1,94);
   * y revisó la expectativa con la lectura de §5.1: *«la inflación subyacente es
     un nivel local que se actualiza despacio (1−θ₁ ≈ 4 % del choque por mes)»*.

   Las demás corridas sobre IPC España, ante una cuasi-cancelación parecida,
   eligieron d=1 por parsimonia (no he revisado si declararon alguna
   expectativa sobre la media). **Cautela:** run9 se hizo sobre la muestra con los
   meses erróneos del Excel del IPC (corregidos después en un CSV aparte); la
   cifra hay que volver a medirla sobre los datos oficiales.
4. **El embudo más ancho de SF_MEG es este mismo problema en la parte
   estacional.** Las frecuencias de frontera son las de factor MA estacional con
   λ² ≈ 0,91–0,95, cerca de la cancelación: la pregunta «¿cuán estocástica es la
   estacionalidad?» sin una expectativa declarada que la oriente.

---

## 6. Guardas

* **Sólo ante un empate genuino** (§4.2). Si el dato discrimina, manda el dato.
* **El dominio nunca pasa por encima de la adecuación.** Un modelo que falla Q o
  JB no entra en el empate, por mucha teoría que lo respalde.
* **Siempre las dos opciones**, con lo que prefiere cada criterio.
* **La expectativa se declara antes** y no se reescribe al ver los candidatos.
  Si hay que corregirla, es una reformulación del nodo `dominio`, con su razón,
  y el guion la registra como tal.

---

## 7. PGAS, recorrido con el procedimiento

**Nodo `dominio`** (hipotético, como debería haberse escrito):
*«`multiplicative`: precio de exportación del gas, indexado por contrato a una
cesta de fuelóleos. Expectativas: persistencia alta; memoria finita posible a
1–2 trimestres por el retardo de la indexación; ciclo de oferta no descartable,
pero sin mecanismo específico identificado.»*

**Empate** (§4.2): ΔAIC = 0,93, tres parámetros cada uno, los dos adecuados.

**Ficha:**

| | AR(2) | MA(2) |
|---|---|---|
| ψ₁, ψ₂, ψ₃ | 0,765; 0,321; 0,043 | 0,788; 0,276; 0 |
| raíces | complejas, módulo 0,51, período ≈ 8,6 trim. | — |
| mínimo de ψ (sobreajuste) | −0,05 | 0 |
| multiplicador de largo plazo Σψ | 2,00 | 2,06 |

**Lectura.** En los tres primeros retardos los dos modelos son casi el mismo; el
ciclo del AR(2) existe pero es débil (la corrección no pasa de −0,05), y el
efecto acumulado de un choque difiere un 3 %. **La elección es interpretativa.**

**Condicionada a d=1 (§5).** Es la fila d=1 de §5.2 con orden 2: ρ₁ > 0, y el MA(2)
tiene coeficientes positivos, el análogo del MA(1) con θ<0. Sus pesos de
previsión sobre los niveles alternan sin fin (1,79; −1,13; 0,40; 0,00; −0,11;
0,09; …), mientras los del AR(2) son finitos (1,77; −1,03; 0,26; 0; …). Por el
principio general, **el AR(2) es la lectura por defecto**. El MA(2) sólo es
defendible con un mecanismo de memoria finita *declarado antes*: la indexación
contractual con retardo, si existe, lo es. Con esa expectativa el MA(2) se
sostiene y además lo prefiere el dato; sin ella, el AR(2). Lo que el
procedimiento impide es encontrar la indexación después de ver que el MA(2)
ajusta mejor.

---

## 8. Cómo se mide

* **Coherencia entre corridas.** En PGAS, el reparto 4/3/1/1 debería
  concentrarse en un candidato, *o* dividirse de forma explicada por
  expectativas distintas declaradas antes.
* **Acuerdo con el oráculo** en los nodos de órdenes, hoy 14/24 en el TFM.
* **E1 (series sintéticas con proceso generador conocido):** la tasa de
  recuperación en las celdas de empate, con y sin el procedimiento, y sin
  empeorar fuera de ellas. Es el contraste que decide si esto sirve.
* **Coste:** una ficha por empate; unos 33 de 97 nodos la habrían necesitado.

---

## 9. Lo que no resuelve

**Un dominio mal declarado.** DeepSeek declaró «un precio de commodity es
reversivo a la media» y eligió d=0 sobre PGAS; el final tenía Q p-mín = 0,0015.
El procedimiento no lo impide. Lo que hace es que el error quede **escrito
antes**, donde se puede discutir, y el motor sigue juzgando la adecuación —que
fue lo que delató aquel caso.

**El conocimiento del LLM.** Las expectativas son tan buenas como la teoría que
el LLM conozca de esa clase de serie. Para clases poco comunes, la expectativa
honesta es «sin expectativa»; entonces no hay criterio de dominio y manda el
dato, aunque sea por poco.

---

## 10. Decisiones abiertas

1. **¿Es obligatorio declarar las expectativas en el nodo `dominio`?**
   Recomendado: sí. Lo medido en el estudio de atws: `rationale`, obligatorio,
   está en 881 de 924 nodos (95 %); `analyst`, opcional, en 0 de 125 (0 %).
   Un campo que la herramienta ofrece no se rellena.
2. **¿La ficha es una herramienta nueva o se genera sola al detectar el empate?**
   Recomendado: que se genere automáticamente dentro de la identificación o de la
   comparación de candidatos. Si depende de que el LLM la pida, no se usará de
   forma sistemática, que es justo el problema de §1.
3. **¿Cuál es el umbral de materialidad?** Propuesta inicial: la diferencia
   máxima de previsión a H = 2s (dos años), por debajo de 0,25 σ ⇒ «elección
   interpretativa». Es una convención; conviene calibrarla con E1.
4. **¿Qué hace el nodo de órdenes con un MA emparejado cerca de 1?** Propuesta:
   no lo decide; devuelve la búsqueda al nodo d o al de estacionalidad con la
   ficha adjunta (§5.3). Y queda por resolver el SMA con Θ>0 sin diferencia
   estacional (§5.2).

---

## 11. Qué cambiaría en el código (esbozo, no implementado)

| dónde | cambio |
|---|---|
| nodo `dominio` (instrucciones y `guion_node`) | exigir las expectativas dinámicas junto con la clase |
| `guion_node` | campo `criterio ∈ {estadístico, dominio, uso}` y referencia a la expectativa |
| identificación / comparación de candidatos | detectar el empate de §4.2 y adjuntar la ficha |
| nueva función de ficha | ψ, pesos de previsión, Σψ, diferencia de previsión, lectura del par (∇, MA) condicionada en (d, D) y distancia a la cancelación; reutiliza `ar_factorization`, `generate_forecast` y la banda de cuasi-cancelación de la DCD/MEG |
| `_INSTRUCTIONS` | la regla AR(1)/MA(1) pasa a ser el ejemplo resuelto del procedimiento |
| `policy.decide_orders` | sin cambio de fondo: la heurística no tiene dominio que declarar, y eso es lo que la separa del carril con LLM |

Las cifras de §1, §5 y §7 salen de los guiones y `.out` citados; el recuento de §1
se hizo con un script de lectura sobre `*/guion*.json`, deduplicado por
contenido, y la clasificación de «argumento económico» se revisó a mano.
