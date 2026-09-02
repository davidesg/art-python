# Dónde está ART en la literatura

Memoria de trabajo para decidir el artículo. 2026-09-02.

No es el artículo: es el estudio previo. Qué es ART cuando se le quita el
dominio, con qué literaturas limita, qué hay ya hecho en cada una, y qué queda
que sea nuestro. Al final, las decisiones que no puedo tomar yo.

---

## 1. Qué es ART cuando se le quita el dominio

Un académico entiende `fue` porque `fue` es un estimador: entra una
especificación, sale una verosimilitud máxima. Tiene una definición matemática
y un artículo detrás. ART no es eso, y por eso no se entiende: **ART no calcula
nada**. Lo que ART hace es gobernar el orden en que se pregunta.

Despojado del dominio, ART es siete cosas:

**1. Un protocolo de nodos fijo.**
`dominio → λ → estacionalidad → d → órdenes → media → [modelo base] →
intervenciones → [reformulación] → contrastes formales`.
El orden no es arbitrario ni aprendido: está forzado por dependencias. No se
puede contrastar `d` antes de resolver la estacionalidad, porque la
estacionalidad residual infla el error típico y sesga el ADF hacia «vuelve a
diferenciar». El protocolo *es* el grafo de dependencias hecho secuencia.

**2. Un espacio de estados de especificaciones.**
Un estado es `(λ, d, D, p, q, P, Q, armónicos, intervenciones, μ)`. Los
movimientos son ediciones de esa tupla. No es un espacio de parámetros: es un
espacio de modelos.

**3. Un evaluador de estados EXTERNO al agente.**
Cada estado recibe una diagnosis calculada por un motor determinista: Q de
Ljung-Box, JB, ACF residual, residuos extremos, admisibilidad de las raíces. El
agente **no juzga** si el estado es bueno. Lo juzga el motor. Este es el hecho
arquitectónico central y del que cuelga todo lo demás.

**4. Búsqueda con vuelta atrás sobre ese espacio.**
`parent`, `status ∈ {exploring, adopted, dead-end}`, `safe_ancestor()`,
`abandon()` con poda en cascada de los descendientes. Primero en profundidad,
con los movimientos elegidos por el analista o por el LLM.

**5. Un registro que CONSERVA los callejones y su razón.**
`why_abandoned`. Está escrito en el propio código (`guion.py`):

> «lo que una iteración fallida produce de valor NO es el modelo que se
> descarta, es la RAZÓN por la que se descarta — que es lo único que impide
> volver a intentarlo.»

**6. Un decisor intercambiable.**
`Policy` como interfaz; `DefaultPolicy` (heurísticas puras, sin E/S) y
`ClaudePolicy` (el LLM). Mismo protocolo, mismos nodos, distinto decisor — y
`decided_by` lo registra nodo a nodo. Es lo que hace que dos recorridos sean
**comparables** (`guion_diff`) en lugar de dos listas parecidas.

**7. Una puerta de adecuación.**
Los contrastes formales (Shin-Fuller, DCD, MEG) sólo corren sobre un modelo
adecuado. No es una preferencia de estilo: es una restricción dura, y §2.6 dice
por qué.

Todo esto se expone como servidor MCP. `drtran` y `drvarma` repiten la
arquitectura sobre otros motores, lo cual es la prueba de que la arquitectura es
separable del dominio.

---

## 2. Las seis literaturas con las que limita

### 2.1 ARIMA automático y sistemas expertos Box-Jenkins — los ancestros directos

ARIMAID (*AIIE Transactions* 14(3), 1982) identificaba automáticamente modelos
ARIMA estacionales y no estacionales. Mélard & Pasteels (2000, *International
Journal of Forecasting*), «Automatic ARIMA modeling including interventions,
using time series expert software», es **el pariente más próximo que existe**:
sistema experto, Box-Jenkins, y con intervenciones. Hyndman & Khandakar (2008,
*JSS*) es el `auto.arima` que todo el mundo usa.

**La diferencia.** Todos ellos entregan **un modelo**. ART entrega **un modelo,
el argumento que lo sostiene, y el registro de lo que se rechazó y por qué**. Y
hay una diferencia de mecanismo: en los sistemas expertos el conocimiento está
cableado en reglas, y de eso murieron —el cuello de botella de adquisición de
conocimiento, la fragilidad ante el caso no previsto. La apuesta de ART es que
un LLM disuelve ese cuello de botella **a condición de no dejarle ser además el
juez de la adecuación**.

### 2.2 Búsqueda de especificación en econometría — el pariente estructural

Leamer (1978), *Specification Searches*. Hoover & Perez (1999). Hendry &
Krolzig, PcGets (*JEDC*, 2001). Y sobre todo **Autometrics** (Doornik, 2009, en
el Festschrift de Hendry): búsqueda en árbol multi-camino con poda por
contrastes, más *indicator saturation* (IIS/SIS) para detectar atípicos y
rupturas.

La analogía estructural es estrecha: árbol de especificaciones, contrastes
decidiendo la poda, vuelta atrás.

**La diferencia.** Autometrics busca *por ti* y reporta el modelo terminal; el
camino es interno y no sale. ART externaliza el camino y lo convierte en el
producto.

**Y donde ART pierde.** El IIS de Autometrics es exactamente nuestro nodo de
intervención, desde la otra tradición, y **mecánicamente es mejor que nosotros**:
saturamos, no buscamos. Lo tenemos medido — encontrar la segunda intervención
del episodio 2008-09 valía 7-15 puntos de AIC y sólo 1 de 8 corridas la
encontró. El IIS la habría encontrado siempre. Esto hay que decirlo en el
artículo: una debilidad medida y con la solución identificada es más fuerte que
una omisión.

### 2.3 Caminos que se bifurcan y multiverso — el encuadre del problema

Gelman & Loken (2013), «The garden of forking paths». Steegen et al. (2016),
análisis multiverso. Simonsohn et al., curva de especificación. Liu, Althoff &
Heer (CHI 2020), **«Paths Explored, Paths Omitted, Paths Obscured»** — sobre
puntos de decisión y reporte selectivo en análisis de datos de punta a punta:
literalmente nuestro problema.

Y el contemporáneo que hay que citar sí o sí: **Bertran, Fogliato & Wu (2026),
«Many AI Analysts, One Dataset: Navigating the Agentic Data Science
Multiverse»** (arXiv 2602.18710). Agentes LLM sobre el mismo dato produciendo
conclusiones que divergen sustancialmente.

**La diferencia, y aquí está la tesis del artículo.** El análisis multiverso
*enumera* los caminos. ART *registra el que se anduvo, con la evidencia en cada
bifurcación y la razón de muerte de cada rama abandonada*.

Y frente a Bertran et al.: sus agentes eligen la metodología libremente y las
conclusiones se dispersan. Nuestra medición, bajo protocolo fijo con evaluación
externalizada, encontró la dispersión **colapsada** — SF_MEG run 3, tres
realizaciones, 36 celdas, **0 oscilantes**, y el error residual atribuible al
instrumento y no al operador. No es una contradicción: es la hipótesis que ellos
dejan abierta y nosotros contestamos. **Lo que colapsa el multiverso no es el
modelo: es el protocolo.**

### 2.4 Procedencia y narrativa computacional — el pariente del guion

VisTrails (Freire, Silva, Callahan et al.): modelo de procedencia *basado en
cambios*, con un árbol de versiones donde cada nodo es una versión del flujo y
cada arista el cambio que lleva del padre al hijo. Las ramas abandonadas se
conservan. Estructuralmente el guion **es** un árbol de versiones de VisTrails
sobre especificaciones de modelos.

**La diferencia.** VisTrails registra *qué cambió*. El guion registra *qué
cambió, por qué, sobre qué evidencia, quién lo decidió, y por qué el callejón
está muerto*. `decided_by` no tiene equivalente en VisTrails y es el campo que
hace diffables dos recorridos como «el mismo protocolo con distinto decisor».

### 2.5 Design rationale — un párrafo, no una sección

IBIS (Rittel & Kunz, 1970) y QOC (MacLean, Young, Bellotti & Moran, 1991,
*Human-Computer Interaction*): registrar cuestiones, opciones y criterios,
incluidas las opciones rechazadas. Nuestro
`node = {nodo, decidido, evidencia, alternativas}` es una celda QOC. Merece
mención y reconocimiento de deuda; no merece sección propia.

### 2.6 Metodología error-estadística — la justificación de la puerta

Mayo & Spanos (2004), *Philosophy of Science*, «Methodology in Practice:
Statistical Misspecification Testing»; Spanos sobre la fiabilidad de la
inferencia bajo mala especificación.

Esto es lo que justifica la regla más dura de ART, y ya está escrito palabra por
palabra en el docstring de `policy.py`:

> «un contraste formal de hipótesis sobre un modelo inadecuado no es un
> contraste débil, no es un contraste. Su distribución bajo la nula supone que
> el modelo es correcto, así que sobre un modelo mal especificado el estadístico
> está contestando a una pregunta sobre otra cosa.»

Es el anclaje que convierte «primero el juicio, después los contrastes» de
costumbre de escuela en principio metodológico defendible. Para un tribunal de
econometría, esta cita vale más que las otras cinco juntas.

### 2.7 Búsqueda con LLM — el pariente de la mecánica

Tree of Thoughts (Yao et al., NeurIPS 2023): búsqueda sobre un árbol de estados
de razonamiento, con vuelta atrás. ReAct. El propio MCP.

**La diferencia, y es la más afilada de todas.** En ToT el LLM es a la vez el
que propone y **el que evalúa** («self-evaluating»). En ART el LLM propone
movimientos y **el motor evalúa estados**, con un criterio estadístico fijo y
determinista. Llamémoslo *evaluación de estado externalizada*, o búsqueda **no
autocalificada**.

Es una afirmación arquitectónica y es **contrastable**: predice exactamente el
colapso de varianza que medimos. Un buscador que se autocalifica hereda la
varianza del calificador; uno que no, no.

---

## 3. La pregunta del laberinto, contestada

La intuición es correcta, y se puede decir con precisión.

**No es un árbol de decisión en sentido ML.** CART, C4.5: la estructura se
*aprende* del dato minimizando impureza, la inferencia es un solo descenso de la
raíz a la hoja, no hay vuelta atrás, y el árbol *es* el modelo. El árbol de ART
no se aprende, no clasifica, y es el registro de una búsqueda, no un predictor.

**No es un árbol de decisión en sentido de análisis de decisiones.** Raiffa:
nodos de azar con probabilidades, utilidades en las hojas, se resuelve por
inducción hacia atrás. En ART no hay probabilidades en las ramas ni utilidad que
maximizar. El AIC es un criterio de comparación entre hermanos, no una función
objetivo que la búsqueda optimice globalmente.

**Sí es un árbol de búsqueda con vuelta atrás**, que es el término estándar, y
*dead end* es el término estándar para lo que llamas «death end» (Russell &
Norvig).

**Y la metáfora del laberinto está haciendo trabajo real, no es adorno.** Un
laberinto es un grafo *que no se ve desde arriba*: su topología sólo se conoce
andándola. Ésa es la descripción honesta de una búsqueda de especificación
Box-Jenkins — no sabes cuántos modelos admisibles hay ni dónde están los muros
hasta que la diagnosis te lo dice. En términos de búsqueda: **la función
sucesor no es enumerable a priori y el test de meta es externo y caro**.

El nombre técnico que le corresponde existe y es **búsqueda en línea** (*online
search*, Russell & Norvig): la búsqueda fuera de línea planifica sobre un modelo
conocido del espacio; la búsqueda en línea intercala cómputo y acción **porque
el espacio sólo se revela actuando**. Eso es el bucle de Box-Jenkins, exactamente.

Y el movimiento distintivo: ART **cartografía** el laberinto mientras lo anda, y
se queda el mapa, muros incluidos. El primo formal más cercano es la *lista
cerrada* de la búsqueda en grafos — con una diferencia que lo es todo: la lista
cerrada es una optimización que se tira al terminar; nuestra lista de callejones
es el resultado científico.

**La frase para el artículo:**

> ART no es un árbol de decisión. Es una búsqueda en línea, evaluada
> externamente, sobre un espacio de especificaciones parcialmente observable,
> cuyo producto es el mapa anotado y no solamente la salida.

---

## 4. Qué es la aportación — y qué no

**No es:** el método (Box & Jenkins, 1970); el motor (`fue`, verosimilitud
exacta de Treadway); el ARIMA automático (1982-2008); la idea de procedencia.

**Es, honestamente, tres cosas.**

**(a) Una arquitectura.** Protocolo de nodos + evaluación externalizada +
decisor intercambiable + mapa anotado. Enunciada con la precisión suficiente
para reimplementarse en otro dominio — y `drtran` y `drvarma` ya son la prueba
de que porta.

**(b) Un resultado empírico.** Bajo esta arquitectura, la varianza entre agentes
y entre repeticiones **en las conclusiones** colapsa, y el error residual es
atribuible al instrumento. Con números: dos LLM × 4 corridas (Bolivia), 3
realizaciones × 6 series (SF_MEG), diferencias nodo a nodo, y coste en tokens.

**(c) Un método para evaluar un asistente estadístico.** Comparación **nodo a
nodo** contra un oráculo guiado (`guion_diff`), preregistro, rúbrica congelada,
K realizaciones, instrumentación de coste. Probablemente la parte más
transferible de todo, y la que otro grupo puede usar mañana sobre otra
herramienta.

**Y una sección de debilidades medidas**, que es lo que dará credibilidad: el
nodo de intervención (7-15 AIC sobre la mesa, 1/8 corridas), donde el IIS de
Autometrics es mecánicamente superior; y que **12 de 25 defectos de una sesión
de depuración fueron la presentación contradiciendo al contenido, y ninguno un
estadístico mal calculado** — que es un hallazgo sobre dónde fallan de verdad
estas herramientas, y motiva la capa de ensamblado de veredictos.

---

## 5. La predicción fuera de muestra — tres cosas distintas

Corrección de una frase demasiado ancha en la primera versión de esta memoria.
SF_MEG **sí** tiene predicción fuera de muestra y su rutina de evaluación
(`sps/forecast_compare.py`): determinista vs estocástico a lo Abraham & Box
(1978), orígenes rodantes balanceados, H=24, con la trampa de la representación
invertible resuelta y verificación C↔Python al dígito. Lo que pasa es que bajo
el mismo nombre viven tres ejercicios distintos:

| | Qué contesta | Estado |
|---|---|---|
| **1. Especificaciones rivales** | ¿Predice mejor D o S en una frecuencia de frontera? | **Hecho** (SF_MEG, piloto ES_CPI) |
| **2. Contra un patrón externo** | ¿El modelo final de ART compite con `auto.arima` / X-13 / ETS? | **Nada** |
| **3. Dispersión entre realizaciones** | ¿El multiverso colapsa también en el espacio de PREDICCIÓN? | **Nada** — y es el que importa |

**Por qué el 3 no es «más evidencia» sino el contraste que puede falsar la
tesis.** Hoy el colapso está medido en **espacio de veredictos**: misma
clasificación de frecuencias, mismo `d`. Pero dos corridas pueden coincidir en
el veredicto y llegar a modelos finales distintos. Si esos modelos predicen
igual, el colapso es más fuerte de lo que afirmamos. **Si predicen igual incluso
cuando los veredictos difieren, el protocolo importa mucho menos de lo que
decimos** — y ése es el ataque que montará un evaluador. Conviene contestarlo
nosotros y con nuestros números.

La maquinaria ya existe: es `forecast_compare.py` con otra cosa en las dos
ranuras — el final de r1 contra el final de r2, en vez de D contra S. Extensión,
no obra nueva.

El **tipo 2** sigue sin existir y es el que pedirá reflexivamente cualquier
revista de predicción: desde Mélard y Hyndman, el listón de un artículo de
modelización automática es batir o empatar a un patrón. Hay que presupuestarlo.

---

## 6. Las cuatro decisiones — recomendación razonada

### 6.1 Público → **econometría/predicción**, citando fuerte a la literatura de IA

El lector que importa es el que motivó todo esto: el académico que usa la
herramienta y no la entiende. Es econometrista. Además, **los evaluadores
capaces de comprobar si la estadística está bien son econometristas** — un
tribunal de HCI dejaría pasar el Shin-Fuller y discutiría la interfaz, que es la
revisión que no queremos. Y la durabilidad: en IA este resultado compite con una
literatura que se mueve en meses; en econometría aplicada sigue vivo en 2031.

Diana: **IJF**, donde vive Mélard & Pasteels — un ancestro direccionable en la
propia revista vale mucho. Alternativas: *Journal of Forecasting*, *CSDA*.

Coste asumido: IJF pedirá el tipo 2 de §5.

Asimetría a explotar: **citar masivamente la literatura de IA y publicar en
econometría**. Traer noticias *hacia* la econometría se publica; traerlas hacia
la IA compite con todo el mundo.

### 6.2 Objeto → **la arquitectura, con ART de instancia**

Un artículo de herramienta caduca, y éste caducaría rápido: la versión sigue en
pruebas hasta que esté el nodo de intervención. La arquitectura no caduca.

Y tiene una propiedad rara: **está demostrada portable, no afirmada portable**.
`drtran` y `drvarma` son la misma arquitectura sobre otros motores. Tres
motores, un protocolo. Es evidencia de generalidad que casi ningún artículo de
este género puede enseñar, y ya está construida.

Forma: reclamación arquitectónica → instanciada en ART → evaluada con el método
→ resultado. El título **no** empieza por «ART:»; empieza por la afirmación, y
ART va en el subtítulo. El método de evaluación (§4c) va como sección de
métodos: solo es una nota metodológica, dentro es lo que hace creíble el
resultado.

### 6.3 Evidencia → **las dos, repartiendo el estadístico**

No compiten si se reparte bien, porque **miden cosas distintas del mismo
experimento**.

- **SF_MEG** aporta la medida de varianza: 3 realizaciones, 8 series, 48
  celdas, 0 oscilantes, preregistrado y con rúbrica congelada. Es el titular.
- **Bolivia** aporta lo que SF_MEG no tiene: **dos LLM de fabricantes
  distintos**, el oráculo guiado, el diff nodo a nodo y el coste.

Regla para no canibalizar: el artículo de SF_MEG es sobre **estacionalidad** y
su tabla principal es la clasificación; éste es sobre **el protocolo** y su
tabla principal es la *dispersión* de esa clasificación. Distinto estadístico
del mismo experimento, con cita cruzada y sin repetir tabla.

Si SF_MEG va más adelantado, **publicarlo primero** y citarlo aquí como
establecido, en vez de defenderlo dos veces.

**Atribución:** Bolivia es la réplica del TFM de un estudiante. Usarlo como
evidencia publicada tiene una dimensión de atribución que hay que resolver al
principio —informarle, y decidir agradecimiento o coautoría—, no al final.

### 6.4 El papel del LLM → **sujeto experimental, no autor**, y es una ventaja

La coautoría está descartada por política de revistas; la pregunta real es el
encuadre. Y la posición es buena: aquí **el LLM no es quien escribe, es lo que
se mide**. Eso obliga a fijarlo como aparato experimental — identificadores de
modelo, versiones, fechas, y el texto exacto de la instrucción (preregistrado,
ya lo tenemos).

Lo que va delante y no enterrado: que ART esté desarrollado y optimizado para
Claude **pero funcione con otros LLM con MCP no es una nota al pie, es el
control experimental**. Si sólo funcionara con Claude, el resultado sería sobre
Claude. Que funcione con DeepSeek es lo que autoriza a llamarlo arquitectura —
y por eso Bolivia, con dos fabricantes, no sobra aunque SF_MEG sea
estadísticamente más fuerte.

Uso de LLM en la redacción: sección de declaración, ya estándar.

---

## 7. Sobre las citas

Verificadas en esta sesión: Mayo & Spanos (2004), Gelman & Loken, Bertran et al.
(2026, arXiv 2602.18710), Mélard & Pasteels (2000, IJF), Doornik/Autometrics,
VisTrails, Yao et al. (ToT, NeurIPS 2023).

Pendientes de confirmar autoría antes de enviar: ARIMAID (*AIIE Transactions*
14(3), 1982) y Liu et al. (CHI 2020, arXiv 1910.13602). Título, revista y año
sí están comprobados en ambos.

---

## 8. Evidencia oportunista frente a evidencia diseñada

Decidido en la discusión del 2026-09-02, y es una corrección de encuadre que
afecta a toda la §6.3.

**El problema.** Bolivia y SF_MEG son datos **oportunistas**: los experimentos
se diseñaron para cazar defectos y evaluar la herramienta para nuestro propio
uso. Las mediciones que queríamos presentar como resultado —el colapso de la
dispersión, sobre todo— son subproductos de corridas hechas para otra cosa. Un
evaluador lo ve enseguida, y tiene razón.

**La solución estructural.** Bolivia y SF_MEG bajan de «Resultados» a **«Caso
aplicado»**. Los datos oportunistas son una ilustración excelente y una
afirmación causal pésima: enseñan la herramienta funcionando sobre un problema
real, que es mucho, pero no sostienen el porqué.

**Lo que salva el año de depuración.** El *debugging* fue el trabajo
exploratorio que localizó las celdas difíciles: raíces complejas del AR(2) que
Shin-Fuller no puede factorizar, episodios de dos intervenciones a ≤3 períodos,
frecuencias estacionales de frontera, μ sin ARMA libre. Eso no es evidencia —
es **dónde poner el diseño experimental**. Exploración ⟹ hipótesis; experimento
diseñado ⟹ evidencia. La rejilla de E1 se construye alrededor de esas celdas.

### 8.1 El comparador no es `auto.arima`

`auto.arima`/`pmdarima` no pueden añadir intervenciones: son una rejilla sobre
(p,d,q)(P,D,Q). Compararlos con ART es comparar un protocolo de modelización con
una búsqueda de órdenes. **No son un rival: son un suelo.**

Su incapacidad no los excluye, los sitúa: sobre una serie con intervención
**conocida**, la distancia entre `auto.arima` y ART *es* el valor del nodo de
intervención, medido. Requiere datos sintéticos, y por eso E1 va primero.

**El comparador real es el mismo LLM sin el protocolo.**

### 8.2 El salto metodológico: verdad conocida

Con series reales, el «acierto» lo define un oráculo experto y es discutible.
Con simulación lo define el proceso generador y no lo es. La maquinaria de
generación sintética determinista ya está escrita y ejercitada (cincuenta repros
de defectos).

### 8.3 Los experimentos

**E1 · Recuperación sobre verdad conocida.** Rejilla diseñada alrededor de las
celdas difíciles de §8. Métrica: tasa de recuperación por componente (λ, d, D,
órdenes, intervenciones) y distancia en espacio de especificación. Da
**corrección**, no acuerdo.

**E2 · Dispersión bajo replicación.** K corridas × tres brazos:

| brazo | qué recibe el LLM |
|---|---|
| **A** | ART completo: protocolo + evaluación externalizada + guion |
| **B** | motor crudo, sin protocolo, sin guion, sin puerta de adecuación |
| **C** | sandbox de Python (`statsmodels`) — el escenario de Bertran et al. |

Métrica: tasa de desacuerdo por pares **y por nodo** (generalización del «0 de
36 oscilantes»), más dispersión de la previsión a origen fijo.

**E3 · Ablación — el que carga con la tesis, y el primero que yo haría.**
Apagar piezas de una en una: sin puerta de adecuación; sin memoria de
callejones; con el LLM autoevaluándose al estilo ToT. Hoy *afirmamos* que la
evaluación externalizada causa el colapso; la ablación lo **enseña**. Es la
diferencia entre «construimos algo y funciona» y «sabemos qué pieza hace el
trabajo».

**E4 · Coste.** Tokens y llamadas por serie y por brazo. Ya instrumentado; se
pega a cualquiera de los anteriores casi gratis.

### 8.4 Métricas, explícitas

- **Recuperación:** acierto exacto por nodo, y por componente.
- **Dispersión:** desacuerdo por pares entre las K corridas, por nodo.
- **Adecuación:** fracción de modelos finales que pasan Q y JB. *Ya tenemos un
  negativo honesto que hay que reportar:* 11 de 18 finales fallaban en el run 3
  de SF_MEG.
- **Coste:** tokens, llamadas, tiempo.
- **Predicción:** RMSE/MAE a horizonte H, y su **dispersión entre corridas**
  (el tipo 3 de §5).

---

## 9. Estructura del documento

1. **Introducción** — la modelización aplicada es una búsqueda con
   bifurcaciones; los agentes LLM ya la hacen y dispersan; qué ocurre si se fija
   el protocolo.
2. **Trabajo relacionado** — las seis literaturas de §2, condensadas a cuatro
   hilos.
3. **La arquitectura** ← *la contribución*: protocolo de nodos, evaluación de
   estado externalizada, decisor intercambiable, mapa anotado, puerta de
   adecuación.
4. **Instanciación: ART**, con `drtran` y `drvarma` como evidencia de
   portabilidad.
5. **Metodología de evaluación** — brazos, métricas, preregistro, el problema
   del oráculo.
6. **Experimentos E1–E4** ← *la evidencia causal, sintética*.
7. **Caso aplicado: Bolivia y SF_MEG** ← *aquí es donde valen, y valen mucho*.
8. **Limitaciones** — el nodo de intervención frente al IIS de Autometrics; los
   fallos de adecuación; la ausencia de patrón externo.
9. **Conclusión.**

**Versión preliminar** (para visualizar el artículo y discutirlo): §1-5, §7, §8,
con Bolivia y SF_MEG haciendo de evidencia provisional.
**Versión depurada** (para enviar): §6 construida y con las afirmaciones
causales trasladadas a ella.
