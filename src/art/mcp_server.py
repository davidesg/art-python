"""
ART MCP Server — expone las funciones de análisis ART como herramientas MCP.

Uso con Claude Code:
    claude mcp add art -- python -m art.mcp_server

Los ficheros .inp / .out / .pre no son formatos intercambiables: son tres
momentos del mismo fichero. Se ESTIMA desde el .inp (semillas); los parámetros y
sus errores típicos se leen del .out; el .pre es el óptimo, y sirve de semilla al
escalón siguiente — reejecutarlo VERIFICA que los números no se mueven, no
estima. Ver el convenio completo en `_INSTRUCTIONS` y bugs/BUG-0027.

Protocolo agnóstico al LLM: cualquier cliente MCP puede usar este servidor.
"""

from __future__ import annotations

import os
import traceback

# El aviso `IncompleteFieldDefinitionWarning` sobre el campo `lifespan` lo emite
# `pydantic_settings` al CONSTRUIR FastMCP --no al importarlo, que es donde lo
# puse primero y por eso seguía saliendo--. Es una interacción entre versiones de
# dependencias, NO de este código, y no toca el protocolo: stdout sale limpio.
# Pero un servidor de stdio que escribe en stderr al arrancar puede leerse como
# un fallo. El filtro va a nivel de módulo, ACOTADO A ESE AVISO por mensaje y por
# módulo de origen: un filtro general taparía los que sí importan.
import warnings as _w
_w.filterwarnings("ignore", message=r".*lifespan.*incomplete definition.*")
_w.filterwarnings("ignore", module=r"pydantic_settings.*",
                  message=r".*incomplete definition.*")

from mcp.server.fastmcp import FastMCP

_INSTRUCTIONS = """
Eres el asistente de análisis de series temporales ART — A Real-Time Time-Series Analysis (metodología Box-Jenkins-Treadway).

══════════════════════════════════════════════════════
IDIOMA / LANGUAGE
══════════════════════════════════════════════════════
Responde SIEMPRE en el idioma del usuario (inglés por defecto si es ambiguo).
Estas instrucciones y las salidas de las herramientas pueden venir en español:
tradúcelas al idioma del usuario al presentarlas; no pegues texto en español a
un usuario que escribe en inglés.
── Always respond in the user's language (default to English if ambiguous). These
instructions and tool outputs may be in Spanish; translate them for the user —
never paste Spanish text to an English-speaking user.

══════════════════════════════════════════════════════
PREGUNTA INICIAL OBLIGATORIA
══════════════════════════════════════════════════════
Al iniciar cualquier análisis, SIEMPRE pregunta primero al usuario:

  "¿Cómo deseas proceder?
   1) Análisis GUIADO (paso a paso, con gráficos y confirmación en cada etapa)
   2) Análisis AUTÓNOMO (pipeline automático completo)"

Si el usuario elige autónomo → usa build_model o batch_build.
Si elige guiado → sigue el protocolo siguiente.

Si elige AUTÓNOMO, pregunta ADEMÁS —una sola vez, aquí:

  "¿Para qué es el modelo? Decide la ruta estacional cuando los contrastes
   no la deciden solos.
   1) UNIVARIANTE   — esta serie sola: describirla o preverla. Gana la ruta
      que mejor ajuste.                                          [por defecto]
   2) MULTIVARIANTE — entra en un sistema (VECM, transferencia, VARMA).
      Fuerza estacionalidad DETERMINISTA: si las series del sistema no llevan
      el mismo tratamiento, sus órdenes de integración no son comparables.
      Puede costar ajuste univariante.
   3) ESTRUCTURAL   — leer los componentes. Prefiere la determinista, que
      los deja explícitos con su amplitud."

  Un renglón de sesgo por opción y nada más: el desarrollo largo lo entrega
  el propio pipeline EN EL NODO ESTACIONAL, que es cuando la decisión se toma.
  Pásalo como objetivo= en build_model / batch_build. Si el usuario no
  contesta es "univariante", y DILO al presentar el modelo: un defecto
  silencioso no se puede discutir.

  POR QUÉ SÍ SE PREGUNTA AL ENTRAR, cuando la de d/D no (ver LLAMADA 3): no es
  una pregunta sobre los DATOS --que aún no has visto-- sino sobre el USO, que
  el analista ya sabe. No hay contradicción que arreglar. En GUIADO no se hace
  aquí: allí va en la LLAMADA 3, con la estacionalidad ya a la vista.

══════════════════════════════════════════════════════
VARIAS SERIES: UNA DETRÁS DE OTRA, NUNCA EN PARALELO
══════════════════════════════════════════════════════
Con más de una serie encima de la mesa, **termina una antes de abrir la
siguiente**. No decidas un nodo para varias series a la vez.

No es una preferencia de estilo. El método es un BUCLE CERRADO --decidir,
estimar, mirar los residuos, revisar-- y su potencia entera está en la
realimentación. Decidir «lambda» para tres series, luego «d» para las tres,
luego «estacionalidad» para las tres, aplana ese bucle en una pasada hacia
delante: se toman las decisiones antes de que exista el primer residuo que
podría corregirlas.

MEDIDO, sobre las mismas tres series y el mismo protocolo (réplica TFM Bolivia,
RUN 2 frente a RUN 3 del mismo analista, que cambió de forma de andar):

                          por series      por lotes
  primer modelo estimado  posición 4-5    posición 15
  modelos estimados       18-23           14
  callejones explorados   7-13            3
  suma de AIC             mejora          empeora en 16 puntos

Quince decisiones antes del primer residuo: el 38% del recorrido en circuito
abierto. Y el daño llega a lo concreto: en ese run el nodo «intervenciones» de
una serie se cerró con «sin intervenciones» EN EL MISMO SEGUNDO que el de otra,
y cinco nodos después aparecía un anómalo de z=-4.04 que obligó a reabrirlo. Los
dos únicos nodos reabiertos de la corrida fueron reparaciones de decisiones
tomadas en lote.

LA OBJECIÓN RAZONABLE, y su respuesta: si las series van a un sistema
multivariante hay que coordinarlas --todas con el mismo tratamiento estacional--
y parece que eso pide decidir a la vez. No lo pide. Esa coordinación se declara
UNA VEZ al entrar, con `objetivo="multivariante"`, y a partir de ahí cada serie
la respeta por su cuenta. Batear los nodos no coordina nada que el objetivo no
coordine ya, y cuesta la realimentación.

══════════════════════════════════════════════════════
DATOS DE ENTRADA — DOS CASOS
══════════════════════════════════════════════════════
CASO 1 — El usuario proporciona datos (Excel, CSV, lista de números):
  → Llama create_inp con los datos, nombre, frecuencia y fecha de inicio.
  → Este tool crea el .inp de datos. A partir de ahí continúa el análisis normal.
  → NO intentes escribir o interpretar el formato .inp manualmente.

CASO 2 — El usuario ya tiene un fichero .inp:
  → Úsalo directamente como inp_path en los tools de análisis.

RUTAS DE SALIDA (output_path):
  Dirige TODA salida de análisis en vivo (.inp/.pre/.out/.fuf/.html que generan
  confirm_and_estimate, suggest_intervention_form, build_model, generate_forecast)
  a `cases/<serie>/work/...`. Ese directorio NO se versiona. NUNCA escribas en
  `cases/<serie>/` raíz: ahí viven los artefactos del caso de estudio y los
  fixtures de test versionados, y los pisarías.

══════════════════════════════════════════════════════
EL CONVENIO DE FICHEROS — .inp / .out / .pre
══════════════════════════════════════════════════════
Los tres ficheros NACEN AQUÍ, en art, y suben con el modelo por la escalera
(mtram, sima, drvec). No son tres formatos: son TRES MOMENTOS del mismo fichero,
y confundirlos produce números que parecen buenos y no lo son.

  .inp   una ESPECIFICACIÓN. Los valores son SEMILLAS, un punto de partida.
         ES DESDE AQUÍ DESDE DONDE SE ESTIMA.
  .out   el registro completo de una estimación Y SU DIAGNOSIS: parámetros CON
         SUS ERRORES TÍPICOS, sigma con el suyo, la verosimilitud, y las
         matrices de covarianza y correlación. Se lee con get_out_report.
  .pre   ese mismo .inp con las estimaciones como nuevos valores iniciales: un
         ÓPTIMO, en forma reejecutable. Sirve de SEMILLA al escalón siguiente.

TRES REGLAS, y las tres se han incumplido en uso real:

1. LOS PARÁMETROS Y SUS ERRORES TÍPICOS SE LEEN DEL .out, NUNCA DE REEJECUTAR
   UN .pre. Correr fue sobre un .pre y comprobar que los números no se mueven es
   la VERIFICACIÓN del invariante, no una estimación. Y tiene una consecuencia
   medida (bugs/BUG-0027): al arrancar exactamente en el óptimo el optimizador
   para en niter=0, nunca actualiza el hessiano, y devuelve como covarianza la
   semilla del BFGS — todos los errores típicos idénticos y sin sentido, con
   converged=True y sin ningún aviso. Si necesitas errores típicos:
   get_out_report, o reestima desde el .inp.

   Y NO ES SÓLO LOS ERRORES TÍPICOS: ES TODA LA COVARIANZA (bugs/BUG-0061).
   Las CORRELACIONES ENTRE PARÁMETROS salen de la misma matriz, así que
   overparameterization_analysis leído sobre un .pre no da un número inflado —
   da un número DISTINTO y, peor, PIERDE PARES. Una varianza que sigue siendo la
   semilla no correlaciona con nada, de modo que los acoplamientos que la
   involucran se hunden hacia cero y no llegan al umbral.

   Medido sobre RATIO_m23: su .out (61 iteraciones) publica tres pares por
   encima de 0.7 --0.93, 0.98 y 0.80--; reejecutando su .pre salían dos, con
   valores 0.981 y 0.993, y el tercero DESAPARECÍA. Era el acoplamiento entre el
   MA(2) y el armónico coseno, o sea el menos visible de los tres y el que más
   falta hacía ver.

   La regla operativa, en una línea: PARA REESTIMAR SE USA EL .inp; el .pre sólo
   VERIFICA. Todo lo que se lea de la covarianza --errores típicos, t, y
   correlaciones de parámetros-- se lee del .out de la estimación real.

2. NUNCA ESCRIBAS UN .pre. Sólo el programa que estimó puede afirmar un óptimo,
   y el fichero no lleva marca de quién lo escribió. Un modelo cuyo .pre se
   fabricó a mano se queda además sin .out, o sea sin registro de diagnosis.

3. UN .pre QUE SE TOCA VUELVE A SER UN .inp. Editar la especificación deshace la
   afirmación de que esos valores son su óptimo — y está bien, es como se
   reformula: se cambia la especificación y se vuelve a estimar.

LA SECUENCIA, y el paso que se salta cuando algo va mal:

  serie en NIVEL, sin transformar
    --create_inp / load_data-->        .inp  (sólo los datos)
    --guided_identification-->         .inp  (estructura; parámetros a cero)
    --confirm_and_estimate-->          .out + .pre    <- aquí nace el óptimo
    --REFORMULAS LEYENDO EL .out-->    .inp  (nueva especificación)
    (se repite hasta que la diagnosis está limpia)
    --y sólo entonces-->               formal_tests

  El eslabón que se pierde es el cuarto. Reformular sin leer el .out es decidir
  sin la evidencia del paso anterior, y es lo que convierte una iteración en una
  conjetura.

CÓMO SE ENCADENAN LOS MODELOS, y qué papel juega el guion:

    .inp(t-1) --estimar--> .pre(t-1) --modificar--> .inp(t) --estimar--> .pre(t)

  Modificar un .pre lo convierte en un .inp, y por tanto en un MODELO NUEVO. Ésa
  es la unidad de iteración: cada .inp es una versión, y la flecha que va de una
  a la siguiente es una DECISIÓN.

  Los ficheros llevan los eslabones; el GUION lleva las razones. Su campo
  `parent` ES la arista .pre(t-1) -> .inp(t), y `decision`/`rationale` son el
  porqué de esa arista. Por eso el guion no es contabilidad paralela sino la capa
  semántica sobre la cadena de ficheros, y por eso se escribe solo: sin él la
  cadena conserva los enlaces y pierde los motivos — y sin los motivos no se
  puede volver atrás, sólo repetir.

  Encadenar desde un .pre ANTIGUO es volver atrás, y queda registrado como RAMA
  (pásalo en `base_pre_path`). guion_map dibuja el árbol; guion_abandon marca un
  callejón sin salida CON SU RAZÓN y dice a qué versión volver.

Detalle y mediciones: drtran-python/docs/LADDER_AS_OPTIMISATION.md

══════════════════════════════════════════════════════
CONSTRUCCIÓN DEL MODELO
══════════════════════════════════════════════════════
  confirm_and_estimate construye el fichero .inp del modelo desde cero a partir
  de los parámetros confirmados (λ, d, D, p, q, n_harmonics). Nunca busques ni
  edites ficheros .inp de modelo manualmente. Cada estimación produce el trío
  .inp/.out/.pre, como hace fue, y registra la versión en el guion.

  build_model es el MISMO motor en ambos modos (autónomo y guiado), y solo
  cambia quién decide:
   • Autónomo: build_model(inp, out) sin spec → la heurística decide todo.
   • Guiado (tras guided_identification): pasa la spec confirmada como
     argumentos — build_model(inp, out, lam=…, d=…, D=…, p=…, q=…,
     n_harmonics=…, decision=…). Lo que fijes se respeta; lo que omitas lo
     completa la heurística, y el ciclo de outliers corre automáticamente.
   Usa confirm_and_estimate + suggest_intervention_form si quieres confirmar
   CADA outlier paso a paso; usa build_model con spec si ya tienes el criterio
   y quieres que el ciclo se complete de una vez con tus decisiones fijadas.

══════════════════════════════════════════════════════
REGLA GENERAL — PRESENTAR SIEMPRE EL MODELO ESTIMADO
══════════════════════════════════════════════════════
CADA vez que estimas un modelo (confirm_and_estimate, suggest_intervention_form,
build_model, estimate_and_diagnose), la respuesta del tool trae la ECUACIÓN del
modelo dentro de un bloque de código (```), precedida de una marca
"[Claude: muestra ... TAL CUAL ...]", y la diagnosis. Preséntalos en ESTE ORDEN:
  1º PRIMERO la ECUACIÓN: copia el bloque de código ``` con "MODELO ESTIMADO:
     <modelo>" EXACTAMENTE como viene, verbatim. Es LA presentación autoritativa
     del modelo.
  2º LUEGO la IMAGEN del gráfico de residuos (titulado "A.<modelo>").
  3º comenta significatividad (|t|>2), Q-test, JB y el veredicto.
PROHIBIDO: NUNCA construyas tu propia tabla o ecuación de parámetros — puede
tener errores (signos, SE, convención). La del tool es la única autoritativa.
El título de la ecuación ("MODELO ESTIMADO: IPC_ES_m00") y el del gráfico
("A.IPC_ES_m00") comparten el nombre del modelo: así el analista asocia ecuación
y gráfico. En guiado el analista SOLO ve lo que muestras; sin la ecuación no
decide. Esquema (tesis): estimar → ECUACIÓN (verbatim) → gráfico → decisión.

══════════════════════════════════════════════════════
PROTOCOLO GUIADO — 4 ETAPAS
══════════════════════════════════════════════════════

─────────────────────────────────────────────────────
ETAPA 1 — IDENTIFICACIÓN (árbol de decisiones secuencial)
─────────────────────────────────────────────────────

⚠ USA SOLO guided_identification para toda la identificación.
  NO llames boxcox_analysis, identification_analysis, seasonal_analysis
  ni unit_root_analysis individualmente — son herramientas internas.

LLAMADA 1 — guided_identification(inp_path)   [lam=-1 por defecto]
  Devuelve: gráfico Box-Cox (media vs desviación típica)
  Lee con el usuario:
  • Nube con pendiente positiva → λ=0 (log)
  • Nube horizontal → λ=1 (original)
  • REGLA: series índice (IPC, IPI, IPP…) → SIEMPRE λ=0
  → ESPERA confirmación de λ.

LLAMADA 2 — guided_identification(inp_path, lam=X)   [d=-1 por defecto]
  Devuelve: serie transformada(λ) + ACF/PACF en nivel d=0
  Lee con el usuario:
  • ¿Tendencia visible o ACF muy lenta? → d=1 necesario
  • ¿Serie estacionaria? → posible d=0
  → Si quieres apoyo estadístico: llama unit_root_analysis por separado.
  → ESPERA decisión sobre d.

LLAMADA 3 — guided_identification(inp_path, lam=X, d=<nivel>)   [D=-1 por defecto]
  Devuelve: ∇^d y(λ) + ACF/PACF + test HAC como soporte (si d>0)
  Lee con el usuario:
  • ¿Picos en ACF/PACF a lags s, 2s, 3s? → hay estacionalidad
    – Regulares y estables → hipótesis B1 (D=0, armónicos deterministas)
    – Dominantes e irregulares → hipótesis B2 (D=1, diferencia estacional)
  • ¿Sin picos estacionales? → D=0 sin armónicos
  • ¿Todavía con tendencia? → repite con d+1
  • Hipótesis B1 es revisable al final mediante MEG (formal_tests)
    Las DOS líneas son DETERMINISTA (armónicos) y ESTOCÁSTICA (SARIMA
    multiplicativo). HSM --Hybrid Seasonal Models; MEG en la literatura
    española, Gallego 1995-- no es una tercera: es la forma canónica de Abraham
    y Box (1978) que las anida, resolviendo frecuencia por frecuencia.

    PUEDES OFRECER evaluar la NATURALEZA de la estacionalidad con el barrido
    HSM (`formal_tests`, `run_meg`), marcándolo "(experimental)". Hay analistas
    que quieren verificar frecuencias mixtas siempre; otros no tienen por qué,
    y no debe ser el camino por defecto.
    Y si preguntan qué significa "(experimental)", explícalo bien: los MODELOS
    son de 1978, la IDEA de ir frecuencia por frecuencia está en HEGY, y el DCD
    y el Shin-Fuller están PUBLICADOS. Lo nuevo son los valores críticos por
    Monte Carlo --que difieren por un margen marginal de los interpolados
    publicados-- y sobre todo LA IMPLEMENTACIÓN DE ART, que hoy tiene tres
    defectos abiertos (BUG-0009/0010/0011). Es una salvaguardia, no una
    advertencia de que el método sea dudoso.
    No decidas la especificación sólo con él: contrástalo con Shin-Fuller y con
    la acf/pacf.

  ⚠ SI HAY ESTACIONALIDAD, DI PARA QUÉ VA A SERVIR EL MODELO ANTES DE ELEGIR.
    B1 y B2 no son equivalentes aguas abajo, y la diferencia no se ve desde
    aquí:
      · para ANÁLISIS MULTIVARIANTE (transferencias en mtram, VARMA en sima)
        es preferible la estacionalidad DETERMINISTA (B1, armónicos). El
        preblanqueo filtra el output por el ARMA del INPUT, y si el output
        lleva estacionalidad ESTOCÁSTICA y el input no, ese filtro no la
        quita: la ccf sale poco informativa y --lo peligroso-- no sale vacía,
        sale con estructura por todas partes y la heurística le lee un orden
        igualmente.
      · para PREVISIÓN, a veces es preferible la ESTOCÁSTICA (B2): deja que el
        patrón estacional evolucione, y cuando de hecho evoluciona, previene
        mejor que unos armónicos fijos.
    Pregunta al analista cuál es el objetivo. No lo decidas tú, y NO lo
    preguntes antes de haber visto la ACF/PACF: hasta aquí nadie sabe si la
    serie es estacional, y una pregunta sobre estacionalidad al abrir el
    análisis pide una decisión sobre algo que todavía no existe.
  → ESPERA confirmación de d y D.

LLAMADA 4 — guided_identification(inp_path, lam=X, d=<confirmado>, D=<confirmado>)
  Devuelve: ACF/PACF de ∇^d ∇_s^D y(λ) + sugerencias ARMA
  Lee con el usuario:
  • Corte brusco PACF, decaimiento ACF → AR(p)
  • Corte brusco ACF, decaimiento PACF → MA(q)
  • Ambas decaen → ARMA(p,q)
  • Sin estructura → p=0, q=0

  ⚠ EL EMPATE AR(1) vs MA(1), Y CÓMO SE ROMPE. En un índice de precios en
    logaritmos con d=1 --la serie diferenciada ES la inflación-- la
    identificación empata a menudo: un único pico dominante en el retardo 1 de
    la acf Y de la pacf. Los dos candidatos generan rho1 > 0 en la serie
    diferenciada, y sólo los separan los retardos 2+ (el AR decae, el MA corta),
    que es justo donde la evidencia es más débil en muestras cortas o ruidosas.

    CUANDO EL AJUSTE TAMPOCO DISCRIMINA --ΔAIC < 2, igual parsimonia, los dos
    pasan Q y Jarque-Bera, acf/pacf residuales casi idénticas-- rompe el empate
    a favor de **AR(1)**, y DI POR QUÉ. No es preferencia estética:

      · AR(1) sobre la inflación tiene respuesta al impulso positiva y
        geométricamente decreciente: PERSISTENCIA / INERCIA inflacionaria, una
        regularidad con base teórica (precios escalonados Calvo/Taylor,
        indexación, expectativas adaptativas; Fuhrer, Stock-Watson,
        Pivetta-Reis). phi es una medida directa de esa inercia.
      · El MA(1) que compite con él lleva theta < 0, y eso es un IMA(1,1) con
        constante de suavizado (1-theta) > 1, fuera del rango válido de un
        EWMA. Sus pesos de previsión sobre los niveles pasados ALTERNAN de
        signo: con theta=-0.7 salen 1.700, -1.190, +0.833, -0.583, ... Previene
        sobrepasando la última observación y corrigiendo hacia atrás. Para un
        índice de precios eso no es un proceso generador defendible, aunque la
        acf de la serie diferenciada sea compatible con él.

    ALCANCE, y es estricto: sólo en series de precios/índices y sólo ante un
    empate GENUINO. Si los estadísticos SÍ discriminan, manda el ajuste. Y en
    cualquier caso PRESENTA LAS DOS: "los datos prefieren X por ΔAIC=..., la
    teoría prefiere Y porque..., decides tú". Un criterio teórico que no se
    enuncia deja de ser un criterio y pasa a ser un sesgo.
    (Verificado en IPC_ES 2002:01-2019:12: AR(1) phi=0.40 elegido sobre MA(1)
     theta=0.43 con ΔAIC=1.12 que nominalmente favorecía al MA. La regla está
     razonada en `art/policy.py:decide_orders`, que todavía NO la aplica sola.)
  → ESPERA confirmación de p, q.

DESPUÉS DE LLAMADA 4 — Modelo de referencia (si D=0):
  → confirm_and_estimate con p=0, q=0, n_harmonics=<freq//2-1>,
    output_path=cases/<serie>/work/<serie>_ref.inp
    (incluye ya la ecuación + diagnosis: PRESÉNTALAS — no llames
     model_equation_display por separado)
  → Evalúa ACF/PACF del modelo de referencia:
    1. Lags s, 2s, 3s limpios → representación armónica adecuada
    2. Lags 1,2,3 con estructura → ajusta p, q

─────────────────────────────────────────────────────
ETAPA 2 — ESTIMACIÓN DEL MODELO ARMA ELEGIDO
─────────────────────────────────────────────────────
  → Llama confirm_and_estimate con (λ, d, D, p, q) confirmados y
    **base_pre_path=<el .pre del modelo de referencia>**
    output_path: cases/<serie>/work/<serie>_v1.inp (NUNCA la raíz cases/<serie>/)

    ENCADENA SIEMPRE por base_pre_path cuando ya existe un .pre. Un .pre es un
    ÓPTIMO en forma re-ejecutable: encadenar hereda armónicos, intervenciones y
    la media YA estimados y solo añade el ARMA. Sin base_pre_path el modelo se
    reconstruye desde cero, se re-estima lo ya resuelto y la media se pierde
    (BUG-0014). Con base_pre_path, n_harmonics se ignora: los armónicos vienen
    del .pre.
    Este tool construye el INP, estima y devuelve la ECUACIÓN + diagnosis en una sola respuesta.
    NO llames model_equation_display por separado — la ecuación ya viene incluida.
  → PRESENTA la ecuación del modelo (verbatim) y MUESTRA el gráfico diagnóstico Treadway
  → Discute: ¿parámetros significativos (|t|>2)? ¿Q-test pasa? ¿JB pasa?

─────────────────────────────────────────────────────
ETAPA 3 — DIAGNOSIS E INTERVENCIONES
─────────────────────────────────────────────────────
  ⚠ TRATAR ANÓMALOS ES UN PUNTO DE DECISIÓN DEL ANALISTA, no algo que ART decida.
    En B1, esta decisión surge tras m00 (antes de ARMA): el escaneo de anómalos
    NO obliga a intervenir.
  → Si hay residuos extremos: menciónalos SIEMPRE y CALIBRA su distorsión sobre la
    ACF/PACF con preliminary_outlier_scan (da var_outlier %, ACF_max % y los
    retardos afectados; el gráfico muestra la contribución de cada anómalo a la ACF).
  → Con esa calibración, SUGIERE: si los anómalos son grandes y están "matando"
    (distorsionando fuertemente) la ACF/PACF → sugiere añadir intervenciones ANTES
    de ARMA; si la distorsión es leve → sugiere pasar a ARMA. Razona la sugerencia.
  → La decisión la toma el ANALISTA: ESPERA su confirmación antes de añadir cada
    intervención.
  → Añade una a una con suggest_intervention_form → MUESTRA diagnosis actualizada
  → Cuando el modelo parezca limpio: llama test_interventions para verificar
    que todas las intervenciones son significativas

─────────────────────────────────────────────────────
ETAPA 4 — CONTRASTES FORMALES
─────────────────────────────────────────────────────
  ⚠ EL MEG VA ANTES DE PODAR ARMÓNICOS ESTACIONALES. Es un ORDEN, no una
    preferencia, y es la trampa más fácil de este flujo (BUG-0010):
      · La hipótesis nula del MEG ES el armónico determinista en f. Si lo has
        podado, esa frecuencia no se puede contrastar: el barrido la devuelve
        como «sin contrastar» y te quedas sin veredicto.
      · Una t BAJA en un armónico es evidencia A FAVOR de que esa frecuencia sea
        estocástica, no de que no exista: un armónico de coeficiente fijo
        ajustado a una frecuencia cuya amplitud vaga promedia hacia cero. Podar
        por significación borra justo las frecuencias que el MEG necesita mirar.
      · Medido en IPC_ES: f=5 (|t|=0.29 y 1.27, la primera que cualquier filtro
        borra) llevaba la segunda evidencia más fuerte de estocasticidad, y f=3
        (|t|=5.4 y 2.1, intocable) es la que ES estocástica.
    La regla general de contrastar sobre un modelo parsimonioso NO alcanza a los
    parámetros que SON la hipótesis bajo contraste. Si la diagnosis de la ETAPA 3
    sugiere sobreparametrización en pares cos/sin, esa poda espera a después de
    esta etapa.
  → Llama formal_tests (Shin-Fuller, DCD, RV, MEG)
  → MEG: si detecta estocasticidad en alguna frecuencia → reformular con D=1
    (revisión de la hipótesis de trabajo B1)
  → Si el MEG devuelve alguna frecuencia «sin contrastar», NO lo trates como
    ausencia de problema: dilo, y vuelve a correrlo sobre la línea base pre-MEG
    (todas las frecuencias estacionales deterministas).
  → DCD: si no rechaza invertibilidad → reformular el factor MA

  → SOLO DESPUÉS: si quedan armónicos no significativos en frecuencias que el MEG
    declaró DETERMINISTAS, ahí sí procede seasonal_param_analysis +
    test_seasonal_simplification. Las que salieron ESTOCÁSTICAS no se podan: se
    reformulan con ifadf[f]=1.

══════════════════════════════════════════════════════
REGLAS GENERALES
══════════════════════════════════════════════════════
- En modo guiado, NUNCA llames boxcox_analysis, identification_analysis,
  seasonal_analysis ni unit_root_analysis individualmente para la identificación.
  USA guided_identification — integra los 4 análisis en el orden correcto.
- El gráfico listing ACF/PACF (segunda figura de guided_identification) es la
  herramienta principal. Discútelo ANTES de los tests.
- Los tests HAC, ADF, KPSS son herramientas de soporte, no árbitros.
  La decisión es siempre del analista a partir de los gráficos.
- NUNCA encadenes pasos sin mostrar el gráfico y esperar confirmación del usuario.
- confirm_and_estimate construye el INP del modelo — nunca busques ficheros .inp.
- Las decisiones finales (λ, d, D, p, q) son del USUARIO, no del modelo.
"""

mcp = FastMCP("ART — A Real-Time Time-Series Analysis", instructions=_INSTRUCTIONS)


# ---------------------------------------------------------------------------
# Contador de llamadas — opt-in por ART_CALL_LOG
# ---------------------------------------------------------------------------
# Para comparar DOS carriles que corren en clientes distintos (y en LLM
# distintos) hace falta una medida que no dependa del cliente. El precio en
# tokens sólo lo sabe cada cliente y sus tokenizadores no son comparables; lo
# que SÍ es común es el trabajo que pasa por el instrumento: cuántas llamadas,
# a qué herramienta, cuánto tardó y --lo que de verdad mueve el contexto del
# modelo-- cuántos BYTES devolvió cada una, separando texto de imagen.
#
# Sin la variable de entorno no se envuelve nada: cero coste y cero cambio de
# comportamiento en el uso normal.
_CALL_LOG = os.environ.get("ART_CALL_LOG", "").strip()

if _CALL_LOG:
    import functools as _ft
    import json as _json
    import time as _time

    # Un fichero por PROCESO de servidor: dos sesiones abiertas a la vez no se
    # mezclan, y cada corrida queda atribuible sin tener que acordarse de
    # cambiar la ruta a mano entre una y otra.
    _b, _e = os.path.splitext(os.path.expanduser(_CALL_LOG))
    _CALL_LOG = f"{_b}-{os.getpid()}{_e or '.jsonl'}"
    os.makedirs(os.path.dirname(os.path.abspath(_CALL_LOG)) or ".", exist_ok=True)

    def _pesa(res) -> tuple[int, int]:
        """Bytes de texto y de imagen devueltos. La imagen va en base64.

        No todas las tools devuelven la misma forma: unas dan `list[TextContent
        | ImageContent]`, otras un `str` pelado. Se pesan las dos.
        """
        txt = img = 0
        for it in (res if isinstance(res, list) else [res]):
            if isinstance(it, str):
                txt += len(it.encode("utf-8"))
                continue
            t = getattr(it, "text", None)
            if isinstance(t, str):
                txt += len(t.encode("utf-8"))
            d = getattr(it, "data", None)
            if isinstance(d, str):
                img += len(d)
        return txt, img

    _tool_orig = mcp.tool

    def _tool_contado(*a, **kw):
        deco = _tool_orig(*a, **kw)

        def envuelve(fn):
            @_ft.wraps(fn)
            def medido(*args, **kwargs):
                t0 = _time.perf_counter()
                err = None
                try:
                    res = fn(*args, **kwargs)
                    return res
                except BaseException as e:          # se re-lanza; sólo se anota
                    err, res = type(e).__name__, None
                    raise
                finally:
                    txt, img = _pesa(res) if err is None else (0, 0)
                    fila = {"t": _time.time(),
                            "tool": fn.__name__,
                            "ms": round((_time.perf_counter() - t0) * 1000, 1),
                            "bytes_texto": txt,
                            "bytes_imagen": img,
                            "error": err}
                    try:
                        with open(_CALL_LOG, "a", encoding="utf-8") as fh:
                            fh.write(_json.dumps(fila, ensure_ascii=False) + "\n")
                    except OSError:
                        pass                        # medir nunca rompe el análisis
            return deco(medido)
        return envuelve

    mcp.tool = _tool_contado

# Execution layer (model construction, .inp I/O, fit and the autonomous loop)
# lives in art.pipeline; the MCP tools below import its primitives + entry points.
from art.pipeline import (
    _load_ts_model, _write_bare_inp, _load_fitted, _obs_to_date,
    _write_inp, _build_arma_on_model, _make_model,
    ModelSpec, FitResult, build_and_fit, run_full,
)
# Decision rules + centralised thresholds (single source of truth).
from art import policy

_Z_USER = policy.THRESHOLDS["outlier_user"]  # user-facing scan default (3.5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(desc) -> list:
    """Convert a Description to MCP content list (text + optional image)."""
    from mcp.types import TextContent, ImageContent
    items = [TextContent(type="text", text=desc.summary + "\n\n---\n" + desc.recommendation)]
    if desc.figure_b64:
        items.append(ImageContent(type="image", data=desc.figure_b64, mimeType="image/png"))
    return items


def _err(msg: str) -> list:
    from mcp.types import TextContent
    return [TextContent(type="text", text=f"❌ Error: {msg}")]


def _warn(context: str, exc: "Exception | None" = None) -> None:
    """Log a non-fatal failure to stderr instead of swallowing it silently (§4).

    Used where a step degrades gracefully (an optional figure, a secondary .out,
    a formal test that does not apply) but the reason should still be visible in
    the server log rather than disappearing into a bare `except: pass`."""
    import sys
    detail = f": {type(exc).__name__}: {exc}" if exc is not None else ""
    print(f"⚠ [art] {context}{detail}", file=sys.stderr)


def _equation_for_prompt(ts, model) -> str:
    """The estimated-model equation wrapped for the prompt: a meta-directive to
    Claude + the authoritative equation in a code fence to be shown VERBATIM.

    model_equation is the authoritative presentation of the model; Claude must
    show this block as-is and must NOT rebuild its own parameter table (which can
    be wrong). The fences preserve the monospace decimal alignment.
    """
    try:
        from art.describe import model_equation as _model_eq
        eq = _model_eq(ts, model)
    except Exception as _eq_exc:
        return f"⚠ *[model_equation error: {_eq_exc}]*"
    # BUG-0027: la ecuación imprime cada coeficiente CON SU ERROR TÍPICO debajo,
    # que es la forma en que este sistema presenta un modelo. Si esos errores son
    # la semilla del BFGS y no el hessiano, presentarlos es peor que no
    # presentarlos: son pequeños y creíbles, y los t salen enormes y falsos.
    aviso = ""
    try:
        from art.diagnosis import (covariance_is_degenerate,
                                   degenerate_variance_indices,
                                   near_seed_variance_indices,
                                   near_seed_distances,
                                   AVISO_COV_DEGENERADA,
                                   AVISO_COV_CASI_SEMILLA)
        r = getattr(model, "_result", None)
        if covariance_is_degenerate(r):
            idx = degenerate_variance_indices(r)
            npar = int(getattr(r, "npar", 0) or 0)
            cuantos = ("TODOS los" if (not idx or len(idx) >= npar)
                       else f"{len(idx)} de los {npar}")
            aviso = (f"\n\n⚠ **{cuantos} errores típicos de arriba NO son válidos** "
                     f"(niter={getattr(r, 'niter', '?')}): " + AVISO_COV_DEGENERADA)
        else:
            # BUG-0041: la degeneración EXACTA (niter=0) ya se avisa arriba, pero
            # una dirección que se movió un 7% tampoco lleva información del
            # hessiano y no disparaba nada. Es sospecha, no veredicto, y se
            # publica con la distancia para que el lector juzgue.
            casi = near_seed_variance_indices(r)
            if casi:
                dist = near_seed_distances(r)
                etiquetas = _param_labels_safe(model)
                detalle = ", ".join(
                    f"{etiquetas[i] if i < len(etiquetas) else f'par {i+1}'} "
                    f"({dist.get(i, 0.0)*100:+.1f}%)" for i in casi)
                aviso = (f"\n\nℹ **Errores típicos sospechosos** "
                         f"(niter={getattr(r, 'niter', '?')}): {detalle} "
                         + AVISO_COV_CASI_SEMILLA)
    except Exception:
        pass
    return (
        "_[Claude: muestra al analista el bloque siguiente TAL CUAL; NO construyas "
        "tu propia tabla/ecuación de parámetros]_\n\n"
        "```\n" + eq + "\n```" + aviso
    )


def _show_fig(b64: str | None, label: str = "art") -> None:
    """Save figure to /tmp and open with xdg-open (non-blocking)."""
    if not b64:
        return
    import base64, subprocess, tempfile, threading
    data = base64.b64decode(b64)
    # Use a stable path per label so repeated calls replace the same window.
    path = f"/tmp/art_{label.replace(' ', '_').replace('/', '_')}.png"
    with open(path, "wb") as fh:
        fh.write(data)
    threading.Thread(
        target=lambda: subprocess.Popen(["xdg-open", path],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL),
        daemon=True,
    ).start()


def _persist_pre_out(m, output_path: str) -> str:
    """Write the fitted model's ``.pre`` (=.inp with the estimated parameters, to
    seed the next step) and ``.out`` (ASCII results) at *output_path*'s basename,
    mirroring fue's estimate→outputs convention.  Returns a short markdown note
    for the tool response.  Mirrors confirm_and_estimate's .pre/.out convention so
    the clean estimation path also produces the trio, without its ×100/μ=0 seeding
    (BUG-0001) — the source .inp already holds the spec (BUG-0003)."""
    output_path = os.path.expanduser(output_path)
    base = os.path.splitext(output_path)[0]
    pre_path, out_path = base + ".pre", base + ".out"
    try:
        m.write_pre(pre_path)
    except Exception as exc:
        return f"\n\n⚠ *No se pudo guardar el .pre: {exc}*"
    try:
        m.write_out(out_path)
    except Exception:
        return f"\n\n*Guardado: parámetros {pre_path}*"
    return f"\n\n*Guardado: parámetros {pre_path}  |  resultados {out_path}*"


# ---------------------------------------------------------------------------
# Helper: single-level series + ACF/PACF figure
# ---------------------------------------------------------------------------

def _plot_series_at_d(ts, lam: float, d: int) -> str | None:
    """
    Plot Box-Cox(lam) + d-fold differenced series via pyfug plot_combined.
    Returns base64 PNG or None on error.
    """
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        from art.identification import boxcox_transform, apply_differences, transform_label
        from art.describe import _fig_b64, _pyfug_ts

        try:
            from pyfug.graphics import plot_combined as _pyfug_combined
        except ImportError:
            return None

        data  = np.asarray(ts.data, dtype=float)
        freq  = ts.freq if ts.freq > 0 else 1
        start = getattr(ts, "start", (1, 1))

        z = boxcox_transform(data, lam)
        w = apply_differences(z, freq, d, 0)   # D=0: calls 2 and 3 never use seasonal diff

        off       = (int(start[1]) - 1) + d
        new_start = (int(start[0]) + off // freq, off % freq + 1)
        title     = transform_label(lam, d, 0, freq, name=ts.name or "")

        pf  = _pyfug_ts(w, freq, new_start, name=title)
        fig = _pyfug_combined(pf, title=title)
        b64 = _fig_b64(fig)
        plt.close(fig)
        return b64
    except Exception as e:
        _warn("figure encoding failed", e)
        return None

@mcp.tool()
def create_inp(
    data: list[float],
    output_path: str,
    name: str = "series",
    freq: int = 12,
    start_year: int = 2000,
    start_period: int = 1,
) -> str:
    """
    Create a .inp file from raw time series data.

    This is the FIRST tool to call when the user provides data from a
    spreadsheet, CSV, or any source other than an existing .inp file.
    The .inp produced is a minimal data container (no model structure) ready
    for boxcox_analysis, guided_identification, and the full guided workflow.

    Parameters
    ----------
    data         : list of numeric observations in chronological order
    output_path  : path where the .inp file will be written (e.g. ~/data/IPC.inp)
    name         : series name (e.g. "IPC", "PCE", "GDP")
    freq         : observation frequency — 1=annual, 4=quarterly, 12=monthly
    start_year   : year of the first observation (e.g. 2003)
    start_period : period of the first observation, 1-based
                   (month 1-12 for monthly; quarter 1-4 for quarterly; 1 for annual)

    Returns
    -------
    Confirmation string with the path, series name, n, freq, and start date.
    """
    try:
        import numpy as np
        import fue

        output_path = os.path.expanduser(output_path)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        ts = fue.TimeSeries(
            data=np.array(data, dtype=float),
            freq=freq,
            start=(start_year, start_period),
            name=name,
        )

        # Minimal model — no structure, no transformation
        m = fue.Model(
            ts,
            d=0, D=0, boxlam=1.0,
            ar=[], ar_free=None,
            ma=[], ma_free=None,
            ar_s=[], ar_s_free=None,
            ma_s=[], ma_s_free=None,
            interventions=[],
            ifadf=[0] * (max(freq // 2, 1) + 1),
            mu=0.0, estimate_mu=False,
        )
        _write_inp(ts, m, output_path)

        period_str = f"P{start_period}/{start_year}" if freq > 1 else str(start_year)
        return (
            f"✓ INP creado: {output_path}\n"
            f"  Serie: {name}  |  n={len(data)}  |  freq={freq}  |  inicio={period_str}\n"
            f"Siguiente paso: boxcox_analysis o guided_identification con este fichero."
        )
    except Exception:
        return f"❌ {traceback.format_exc()}"


# ---------------------------------------------------------------------------
# Tool: series info
# ---------------------------------------------------------------------------

@mcp.tool()
def series_info(inp_path: str) -> str:
    """
    Load a time series from an .inp file and return basic information.

    Parameters
    ----------
    inp_path : path to the .inp file

    Returns basic metadata: name, n, frequency, start date, Box-Cox lambda,
    differencing orders (d, D), ARMA structure.
    """
    try:
        ts, m = _load_ts_model(inp_path)
        p = sum(len(f) for f in (m.ar   or []))
        q = sum(len(f) for f in (m.ma   or []))
        P = sum(len(f) for f in (m.ar_s or []))
        Q = sum(len(f) for f in (m.ma_s or []))
        s = ts.freq
        itv_types = sorted({itv.type for itv in (m.interventions or [])})
        lines = [
            f"**Serie**: {ts.name or 'sin nombre'}",
            f"**n**: {ts.nobs}  |  **freq**: {s}  |  **inicio**: {ts.start}",
            f"**λ (Box-Cox)**: {m.boxlam}",
            f"**d={m.d}  D={m.D}**",
            f"**Spec ARIMA**: ({p},{m.d},{q})({P},{m.D},{Q})_{s}",
            f"**Intervenciones**: {', '.join(itv_types) if itv_types else 'ninguna'}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


# ---------------------------------------------------------------------------
# Tool: Box-Cox
# ---------------------------------------------------------------------------

@mcp.tool()
def boxcox_analysis(inp_path: str) -> list:
    """
    Analyse Box-Cox transformation for a time series (standalone use).

    NOTE: in guided analysis use guided_identification instead — it integrates
    Box-Cox, the identification listing, unit-root tests and seasonality test
    in the correct order (listing first, tests as support).

    Computes the mean-std scatter for lambda=0 (log) and lambda=1 (identity),
    recommends the transformation, and returns the comparison figure.

    Parameters
    ----------
    inp_path : path to the .inp file
    """
    try:
        from art.describe import describe_boxcox
        ts, _ = _load_ts_model(inp_path)
        desc = describe_boxcox(ts)
        _show_fig(desc.figure_b64, "boxcox")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Seasonal detection
# ---------------------------------------------------------------------------

@mcp.tool()
def seasonal_analysis(inp_path: str) -> list:
    """
    HAC F-test for seasonal patterns — support tool, standalone use only.

    NOTE: in guided analysis use guided_identification instead — seasonal_analysis
    is a support tool called internally after the identification listing.

    Tests all harmonic frequencies using a joint F-test with HAC Newey-West
    standard errors. Returns the seasonality plot and a recommendation for D.

    Parameters
    ----------
    inp_path : path to the .inp file
    """
    try:
        from art.describe import describe_seasonality
        ts, _ = _load_ts_model(inp_path)
        desc = describe_seasonality(ts)
        _show_fig(desc.figure_b64, "seasonality")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Unit root tests (Bloque L)
# ---------------------------------------------------------------------------

@mcp.tool()
def unit_root_analysis(inp_path: str, lam: float = 0.0,
                       max_d: int = 2) -> list:
    """
    ADF + KPSS unit root tests for d = 0, 1, ..., max_d — support tool.

    NOTE: in guided analysis use guided_identification instead — unit_root_analysis
    is a support tool called internally after the identification listing.

    Exploratory tool for the starting value of d. NOT a formal hypothesis test —
    for formal testing on an estimated model use formal_tests (Shin-Fuller 1998).

    Parameters
    ----------
    inp_path : path to the .inp file
    lam      : Box-Cox lambda (0.0 = log, 1.0 = none)
    max_d    : highest differencing order to test (default 2)
    """
    try:
        from art.describe import describe_unit_root
        ts, _ = _load_ts_model(inp_path)
        desc = describe_unit_root(ts, lam=lam, max_d=max_d)
        _show_fig(desc.figure_b64, "unit_root")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Identification
# ---------------------------------------------------------------------------

@mcp.tool()
def identification_analysis(inp_path: str, d: int = 2, D: int = 0,
                             lam: float = 0.0) -> list:
    """
    ACF/PACF identification listing + ARMA order suggestions — standalone use.

    NOTE: in guided analysis use guided_identification instead:
      - Call 1 (lam=-1): shows Box-Cox + listing (d=0,1,2) + unit-root + HAC
      - Call 2 (lam confirmed): shows ACF/PACF of ∇^d ∇_s^D y_t + suggestions
    identification_analysis is called internally by guided_identification.

    Compares the empirical ACF/PACF of the differenced series with theoretical
    ACF/PACF of candidate ARIMA models. Returns top-5 suggestions by similarity.

    Parameters
    ----------
    inp_path : path to the .inp file (series is used, model spec ignored)
    d        : regular differencing order (default 2)
    D        : seasonal differencing order (default 0)
    lam      : Box-Cox lambda (0.0=log, 1.0=identity, default 0.0)
    """
    try:
        from art.describe import describe_identification
        ts, _ = _load_ts_model(inp_path)
        desc = describe_identification(ts, d=d, D=D, lam=lam)
        _show_fig(desc.figure_b64, "identification")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Preliminary outlier scan (before ARMA identification)
# ---------------------------------------------------------------------------

@mcp.tool()
def preliminary_outlier_scan(inp_path: str, d: int, D: int,
                              lam: float = 0.0,
                              threshold: float = _Z_USER) -> list:
    """
    Scan the differenced series for extreme observations BEFORE choosing ARMA orders.

    "Lo más obvio primero": a large outlier in the differenced series distorts
    ACF/PACF coefficients (subestimated due to inflated variance). Treating the
    outlier BEFORE identification gives cleaner, more informative ACF/PACF.

    Returns the standardised ∇ᵈ∇ᴰ series with ±2σ bands and outliers marked,
    plus a recommendation on whether to add interventions before identifying (p, q).

    Parameters
    ----------
    inp_path  : path to the .inp file
    d         : confirmed regular differencing order
    D         : confirmed seasonal differencing order
    lam       : confirmed Box-Cox lambda (0.0=log, 1.0=identity)
    threshold : |z| threshold for flagging extremes (default 3.5)
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_prelim_scan
        ts, _m_cargado = _load_ts_model(inp_path)
        desc = describe_prelim_scan(ts, d=d, D=D, lam=lam, threshold=threshold)

        # BUG-0028: esta herramienta escanea la SERIE, y descarta el modelo a
        # propósito — su sitio es ANTES de que exista uno. Pero acepta cualquier
        # .inp/.pre sin poder saber qué quería quien la llama, y con un modelo ya
        # estimado analiza la serie cruda sin transformar y devuelve un falso
        # negativo tranquilizador. No se puede impedir; sí se puede avisar.
        aviso_modelo = ""
        try:
            _tiene_modelo = bool(
                (getattr(_m_cargado, "ar", None) or [])
                or (getattr(_m_cargado, "ma", None) or [])
                or (getattr(_m_cargado, "ar_s", None) or [])
                or (getattr(_m_cargado, "ma_s", None) or [])
                or (getattr(_m_cargado, "interventions", None) or [])
            )
            if _tiene_modelo:
                aviso_modelo = (
                    "\n\n⚠ **Este fichero lleva un MODELO, y esto ha escaneado la "
                    "SERIE**, no sus residuos. Si lo que buscas son los anómalos "
                    "del modelo estimado, la herramienta es "
                    f"`residual_outlier_scan(inp_path=\"{inp_path}\")`: un anómalo "
                    "sólo lo es *respecto de un modelo*, y antes de ajustar la "
                    "dinámica lo que parece anómalo puede ser justo lo que el "
                    "modelo predice. (bugs/BUG-0028)"
                )
        except Exception:
            pass

        next_opts = (
            aviso_modelo
            + "\n\n---\n\n**¿Qué hacemos?**\n\n"
            "**A) Añadir intervención** → `suggest_intervention_form(date=\"MM/YYYY\", form=\"auto\")`\n"
            "  Repite hasta que los residuos estén limpios, luego pasa a identificación ARMA.\n\n"
            "**B) Continuar con ARMA sin intervenciones**\n"
            "  → `guided_identification(..., pre_path=\"<modelo_actual>.pre\")`\n"
            "  ⚠ Si hay outliers significativos, las ACF/PACF estarán distorsionadas.\n\n"
            "**¿Dudas?** Para ver cuánto distorsiona cada outlier la ACF de los "
            "RESIDUOS de un modelo ya estimado:\n"
            "  `residual_outlier_scan(inp_path=\"<modelo_actual>.inp\")`\n"
            "  (BUG-0028: NO uses preliminary_outlier_scan para eso — ésta escanea "
            "la SERIE, y con un modelo estimado analizaría la serie cruda sin "
            "transformar, devolviendo un falso negativo tranquilizador.)"
        )

        text = desc.summary + "\n\n---\n" + desc.recommendation + next_opts
        items = [TextContent(type="text", text=text)]
        if desc.figure_b64:
            items.append(ImageContent(type="image",
                                      data=desc.figure_b64, mimeType="image/png"))
        return items
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Model equation display (Bloque O)
# ---------------------------------------------------------------------------

@mcp.tool()
def residual_outlier_scan(inp_path: str, threshold: float = _Z_USER) -> list:
    """
    Scan the RESIDUALS of an estimated model for outliers, with each one's
    contribution to every ACF lag.

    This is the calibration that decides whether to intervene before choosing
    ARMA orders — and it must run on the residuals, because an outlier is only
    an outlier *relative to a model*. Before the dynamics are fitted, what looks
    anomalous may be exactly what the model predicts.

    NOT to be confused with `preliminary_outlier_scan`, which scans the SERIES
    (before any model exists) and takes the transformation as arguments because
    there is no model yet to carry it. Passing a fitted model to that one
    silently scans the raw, untransformed series — see bugs/BUG-0028.

    Parameters
    ----------
    inp_path  : .inp of an estimated model (per the file convention, estimate
                from the .inp, not the .pre)
    threshold : |z| threshold for flagging (default 3.5)
    """
    try:
        import fue as _fue
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_prelim_scan, _resid_start
        ts, m = _load_ts_model(inp_path)
        m.fit()
        if m.residuals is None:
            return _err("el modelo no tiene residuos: ¿se estimó?")
        res_ts = _fue.TimeSeries(
            m.residuals.data, freq=ts.freq, start=_resid_start(m),
            name=f"Resid {ts.name or ''}".strip(),
        )
        desc = describe_prelim_scan(res_ts, d=0, D=0, lam=1.0, threshold=threshold)
        _show_fig(desc.figure_b64, "residual_scan")
        cab = (f"*Escaneo sobre los RESIDUOS de `{os.path.basename(inp_path)}` "
               f"(n={len(m.residuals.data)}), no sobre la serie.*\n\n")
        items = [TextContent(type="text", text=cab + desc.summary
                             + "\n\n---\n" + desc.recommendation)]
        if desc.figure_b64:
            items.append(ImageContent(type="image", data=desc.figure_b64,
                                      mimeType="image/png"))
        return items
    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def model_equation_display(inp_path: str) -> list:
    """
    Display the estimated model as two polynomial-operator equations.

    Shows the two-equation B-J-T form with estimated parameters and SE aligned
    below each coefficient (equivalent to the \\est{}{} LaTeX macro in the thesis).

    Equation 1 (level):  [transform] yₜ = Dₜ + Nₜ
      Dₜ shows all deterministic components: interventions, harmonics, mean.

    Equation 2 (noise):  ∇ᵈ∇ₛᴰ φ(B) Nₜ = θ(B) aₜ
      Polynomial operator form for the ARIMA stochastic model.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the estimated model
    """
    try:
        from mcp.types import TextContent
        ts, m = _load_ts_model(inp_path)
        m.fit()
        eq_text = _equation_for_prompt(ts, m)
        return [TextContent(type="text", text=eq_text)]
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Estimate and diagnose
# ---------------------------------------------------------------------------

@mcp.tool()
def estimate_and_diagnose(inp_path: str, output_path: str = "") -> list:
    """
    Fit the model specified in an .inp file and run diagnosis.

    Estimates the model by maximum likelihood (fue MVENC) and runs the
    full diagnosis: standardised residuals, ACF/PACF, Ljung-Box Q-test,
    Jarque-Bera normality test, and residual seasonality check.

    Parameters
    ----------
    inp_path    : path to the .inp file with the model specification
    output_path : if given, also persist the fitted model as the ``.pre``
                  (= .inp with the estimated parameters, to seed the next step)
                  and ``.out`` (ASCII results report) alongside this basename —
                  the same trio confirm_and_estimate writes, so a model estimated
                  through this clean path is not left without artefacts.  Empty
                  (default) keeps the old screen-only behaviour.
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        ts, m = _load_ts_model(inp_path)
        m.fit()
        try:
            eq_text = _equation_for_prompt(ts, m)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"
        desc = describe_diagnosis(m)
        _show_fig(desc.figure_b64, "diagnosis")
        text = eq_text + "\n\n---\n\n" + desc.summary + "\n\n---\n" + desc.recommendation
        if output_path:
            text += _persist_pre_out(m, output_path)
        items = [TextContent(type="text", text=text)]
        if desc.figure_b64:
            items.append(ImageContent(type="image",
                                      data=desc.figure_b64, mimeType="image/png"))
        hist_b64 = desc.data.get("hist_b64")
        if hist_b64:
            items.append(ImageContent(type="image",
                                      data=hist_b64, mimeType="image/png"))
        return items
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Residuals histogram (optional complement to estimate_and_diagnose)
# ---------------------------------------------------------------------------

@mcp.tool()
def model_histogram(inp_path: str) -> list:
    """
    Show the residuals histogram with normal overlay for a fitted model.

    Optional complement to the basic Treadway diagnostic module
    (estimate_and_diagnose / confirm_and_estimate).  The histogram is not
    part of the basic diagnostic module — request it explicitly when you
    want to inspect the distributional shape of the residuals.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the estimated model
    """
    try:
        from mcp.types import ImageContent
        from art.describe import describe_diagnosis
        ts, m = _load_fitted(inp_path)
        desc = describe_diagnosis(m)
        b64 = desc.data.get("hist_b64") or desc.figure_b64
        if b64 is None:
            return _err("No se pudo generar el histograma de residuos.")
        return [ImageContent(type="image", data=b64, mimeType="image/png")]
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Over-parameterization analysis (Bloque I)
# ---------------------------------------------------------------------------

@mcp.tool()
def overparameterization_analysis(inp_path: str, threshold: float = 0.7) -> list:
    """
    Check for over-parameterization by inspecting parameter correlation matrix.

    Computes the correlation matrix of all estimated parameters from the
    covariance matrix returned by fue (MVENC).  Parameter pairs with
    |corr| > threshold are flagged as potentially redundant.

    The correlation matrix is shown as a colour heatmap with the ARMA/mu
    block highlighted.  High-correlation pairs are listed with labels and
    a note on whether the high correlation is structural (expected) or
    indicates true redundancy.

    Run this after estimate_and_diagnose if the diagnosis text mentions
    sobreparametrización, or as a routine check before finalising the model.

    Parameters
    ----------
    inp_path  : path to .inp or .pre file with the estimated model
    threshold : |corr| threshold for flagging (default 0.7)
    """
    try:
        import io, base64
        import numpy as np
        import matplotlib.pyplot as plt
        from mcp.types import TextContent, ImageContent
        from art.diagnosis import _compute_param_corr, _build_param_labels
        from art.describe import _fig_b64

        _, m = _load_fitted(inp_path)
        corr, pairs, labels = _compute_param_corr(m, threshold=threshold)

        # BUG-0061. Esta herramienta lee la COVARIANZA, así que le afecta de
        # lleno la regla de la escalera: para reestimar se usa el `.inp`, NUNCA
        # el `.pre`. Un `.pre` arranca en el óptimo, el BFGS apenas itera y las
        # direcciones que no se mueven conservan la semilla (c·I) — cuya
        # correlación con todo lo demás es CERO.
        #
        # Medido sobre `RATIO_m23` de DS. Su `.out` (61 iteraciones, estimación
        # real) publica tres pares por encima de 0.7:
        #     corr[8][6]=0.93   corr[9][7]=0.98   corr[11][1]=0.80
        # Reejecutando su `.pre` (niter=5, 3 de 11 varianzas en la semilla) esta
        # herramienta devolvía 0.981 y 0.993 --números distintos-- y **perdía el
        # tercer par entero**, que era justo el acoplamiento menos visible entre
        # el MA(2) y el armónico coseno. Sin una palabra de aviso.
        aviso_cov = ""
        try:
            from art.diagnosis import (covariance_is_degenerate,
                                       degenerate_variance_indices)
            r = getattr(m, "_result", None)
            if covariance_is_degenerate(r):
                idx = degenerate_variance_indices(r)
                npar_r = int(getattr(r, "npar", 0) or 0)
                afectados = [labels[i] if i < len(labels) else f"par {i+1}"
                             for i in idx]
                es_pre = str(inp_path).endswith(".pre")
                aviso_cov = (
                    f"\n\n> ⚠ **La covarianza NO es de fiar aquí: "
                    f"{len(idx) or npar_r} de {npar_r} varianzas siguen siendo la "
                    f"semilla del BFGS** (niter={getattr(r, 'niter', '?')}). "
                    + (f"Afecta a: {', '.join(afectados)}. " if afectados else "")
                    + "Una varianza-semilla no correlaciona con nada, así que las "
                    "correlaciones que la involucran salen **cerca de cero** — y "
                    "los pares altos que deberían aparecer **no aparecen**. Este "
                    "listado puede estar incompleto.\n>\n"
                    + ("> **Estás leyendo un `.pre`.** Reejecutarlo arranca en el "
                       "óptimo y el optimizador casi no itera: por eso la "
                       "covarianza se queda en la semilla. Para reestimar se usa "
                       "el `.inp`, no el `.pre` — el `.pre` VERIFICA que los "
                       "parámetros no se mueven.\n>\n" if es_pre else "")
                    + "> Los números buenos están en el **`.out` de la estimación "
                    "real**, que trae su propia matriz de correlación y su bloque "
                    "«Correlations greater than or equal to 0.7»."
                )
        except Exception:
            pass

        if corr is None:
            return [TextContent(type="text",
                                text="No se pudo calcular la matriz de correlación "
                                     "(modelo no estimado o sin matriz de covarianza).")]

        n = corr.shape[0]

        # ── heatmap figure ────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(max(6, n * 0.42 + 1.5),
                                        max(5, n * 0.38 + 1.2)))
        im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r", aspect="auto")
        plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)

        # Tick labels — show all if ≤20 params, else abbreviated
        tick_labels = labels if n <= 20 else [
            lbl if i in (0, n - 1) or i % max(1, n // 10) == 0 else ""
            for i, lbl in enumerate(labels)
        ]
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(tick_labels, rotation=90, fontsize=7)
        ax.set_yticklabels(tick_labels, fontsize=7)

        # Highlight cells with |corr| > threshold
        for i in range(n):
            for j in range(n):
                if i != j and abs(corr[i, j]) > threshold:
                    ax.add_patch(plt.Rectangle(
                        (j - 0.5, i - 0.5), 1, 1,
                        fill=False, edgecolor="gold", lw=1.5
                    ))

        # Draw box around ARMA+mu block (last ARMA params)
        n_arma = (
            sum(len(f) for f in (m.ar or []))
            + sum(len(f) for f in (m.ar_s or []))
            + sum(len(f) for f in (m.ma or []))
            + sum(len(f) for f in (m.ma_s or []))
            + (1 if getattr(m, "estimate_mu", False) else 0)
        )

        if n_arma > 0:
            i0 = n - n_arma
            rect = plt.Rectangle((i0 - 0.5, i0 - 0.5), n_arma, n_arma,
                                  fill=False, edgecolor="black", lw=2.0, linestyle="--")
            ax.add_patch(rect)

        ax.set_title(f"Correlación de parámetros — {m.series.name if m.series else ''}\n"
                     f"(n_param={n}, umbral={threshold})", fontsize=10)
        fig.tight_layout()
        b64 = _fig_b64(fig)
        plt.close(fig)

        # ── text summary ──────────────────────────────────────────────────
        # Classify each pair:  "flt" = always structural, "arma" = check RV test,
        # "" = unknown/genuine overpar candidate
        def _classify(lbl_i: str, lbl_j: str) -> str:
            a, b_lbl = lbl_i.lower(), lbl_j.lower()
            # FLT transfer function: ω + δ always structural
            if ("ω(" in lbl_i or "δ(" in lbl_i) and ("ω(" in lbl_j or "δ(" in lbl_j):
                return "flt"
            if "ω(" in lbl_i and lbl_j.startswith("δ"):
                return "flt"
            if lbl_i.startswith("δ") and "ω(" in lbl_j:
                return "flt"
            # AR + MA mixed: may be structural if AR(2) with complex roots
            is_ar_i = lbl_i.startswith("AR")
            is_ma_i = lbl_i.startswith("MA")
            is_ar_j = lbl_j.startswith("AR")
            is_ma_j = lbl_j.startswith("MA")
            if (is_ar_i and is_ma_j) or (is_ma_i and is_ar_j):
                return "arma"
            return ""

        def _note_text(kind: str, lbl_i: str, lbl_j: str) -> str:
            if kind == "flt":
                return "FLT (ω,δ): estructural, sin acción"
            if kind == "arma":
                return "AR+MA: si AR(2) con φ₂<0 puede ser estructural → verificar test RV"
            return "Sobreparametrización probable → reducir modelo"

        lines = ["## Sobreparametrización — análisis de correlaciones de parámetros", ""]
        lines.append(f"Parámetros: **{n}**  |  Umbral: **|r| > {threshold}**")
        lines.append("")

        if not pairs:
            lines.append("✅ **Sin sobreparametrización detectada.** "
                         "Ningún par de parámetros supera el umbral de correlación.")
        else:
            lines.append(f"⚠ **{len(pairs)} par(es) con |r| > {threshold}:**")
            lines.append("")
            lines.append("| # | Param i | Param j | r | Diagnóstico |")
            lines.append("|---|---------|---------|---|------------|")
            for k, (i, j, r_val, lbl_i, lbl_j) in enumerate(pairs, 1):
                kind = _classify(lbl_i, lbl_j)
                note = _note_text(kind, lbl_i, lbl_j)
                lines.append(f"| {k} | {lbl_i} | {lbl_j} | {r_val:+.3f} | {note} |")
            lines.append("")

            flt_pairs   = [(li, lj, rv) for _, _, rv, li, lj in pairs if _classify(li, lj) == "flt"]
            arma_pairs  = [(li, lj, rv) for _, _, rv, li, lj in pairs if _classify(li, lj) == "arma"]
            true_pairs  = [(li, lj, rv) for _, _, rv, li, lj in pairs if _classify(li, lj) == ""]

            if flt_pairs:
                lines.append(f"**{len(flt_pairs)} par(es) FLT** — estructurales, no requieren acción.")
            if arma_pairs:
                lines.append(f"**{len(arma_pairs)} par(es) AR+MA** — verificar si AR(2) tiene raíces "
                              "complejas (φ₂ < 0). Si no, es sobreparametrización real.")
                lines.append("  → Aplicar `formal_tests` (test RV) para confirmarlo.")
            if true_pairs:
                lines.append("")
                lines.append("**Sobreparametrización confirmada — acción recomendada:**")
                for lbl_i, lbl_j, r_val in true_pairs:
                    lines.append(f"- Eliminar uno de: `{lbl_i}` / `{lbl_j}` "
                                 f"(|r|={abs(r_val):.3f}). "
                                 "Comparar AIC/BIC con `compare_versions`.")
            elif not true_pairs and not arma_pairs:
                lines.append("")
                lines.append("Todos los pares son estructurales. No se requiere acción.")

        lines += [
            "",
            "---",
            "**Matriz de correlación** — heatmap adjunto.",
            "Recuadro negro punteado = bloque ARMA+μ. Celdas con borde dorado = pares flagged.",
        ]

        text = "\n".join(lines) + aviso_cov      # BUG-0061
        items = [TextContent(type="text", text=text)]
        if b64:
            items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Formal tests
# ---------------------------------------------------------------------------

@mcp.tool()
def formal_tests(inp_path: str, run_meg: bool = True) -> list:
    """
    Run formal hypothesis tests on a fitted model.

    ⚠ MARCA ESTA RUTA COMO (EXPERIMENTAL) — Y SI TE PREGUNTAN QUÉ SIGNIFICA,
      EXPLÍCALO BIEN, PORQUE NO ES LO QUE PARECE.

    QUÉ ESTÁ PUBLICADO Y ESTABLECIDO (casi todo):
      · los MODELOS son antiguos: Abraham y Box (1978).
      · la IDEA de resolver la estacionalidad frecuencia por frecuencia está en
        HEGY (Hylleberg, Engle, Granger y Yoo).
      · el contraste DCD (Davis, Chen y Dunsmuir) está PUBLICADO.
      · el Shin-Fuller está PUBLICADO.

    QUÉ ES NUEVO (poco, y menos de lo que "experimental" sugiere):
      · los VALORES CRÍTICOS derivados por Monte Carlo, que difieren por un
        margen MARGINAL de los interpolados que están publicados.
      · y, sobre todo, LA IMPLEMENTACIÓN DE ART -- que es donde están los tres
        defectos abiertos de abajo. Eso es lo realmente nuevo aquí.

    Así que "(experimental)" es una SALVAGUARDIA, no una advertencia de que el
    método sea dudoso. El método está establecido; lo que aún no está avalado
    es esta implementación y el último decimal de los críticos.

    NOMBRE: la clase se llama HSM --Hybrid Seasonal Models-- que es como la
    nombra el artículo de referencia (SF_MEG). `MEG`, Modelos de Estacionalidad
    Generalizada (Gallego, 1995), es su nombre en la literatura española y el
    identificador que conserva el código; en prosa, di HSM.

    LAS DOS LÍNEAS DE ESTACIONALIDAD son:
      · DETERMINISTA   armónicos con coeficientes de previsión fijos
      · ESTOCÁSTICA    SARIMA multiplicativo, la diferencia anual 1-B^s entera

    HSM no es una tercera línea: es la FORMA CANÓNICA de Abraham y Box (1978),
    en la que cada frecuencia es independientemente una u otra, y que anida las
    dos líneas como casos especiales. Ellos ya distinguen componentes
    deterministas de "forecast-adaptive" y notan que un modelo puede ser
    adaptativo en unos parámetros y no en otros. ESA RUTA ES LA EXPERIMENTAL.

    Los tres defectos ABIERTOS y reproducidos de la implementación, todos en
    esta familia:

      BUG-0009  dcd_overdiff_regular pisa el testigo de Nyquist --comparten la
                ranura de MA regular y miden raíces OPUESTAS (B=+1 frente a
                B=-1)-- y recomienda d+1 sobre una d correcta.
      BUG-0010  podar un armónico no significativo anula el barrido MEG
                ENTERO, la excepción se traga, y el informe cierra diciendo
                que el modelo es adecuado mientras se pierde una frecuencia
                genuinamente estocástica.
      BUG-0011  dcd_overdiff_regular recomienda d+1 en toda especificación de
                un índice de precios, incluida la línea base que su propio
                docstring prescribe. Causa establecida: los armónicos
                deterministas compiten con el testigo, y la precondición del
                docstring nombra al competidor equivocado.

    PUEDES OFRECERLA. Preguntar al analista si quiere evaluar la NATURALEZA de
    la estacionalidad --determinista o estocástica, frecuencia por frecuencia--
    es una pregunta legítima y hay analistas que la quieren siempre. Ofrécela
    marcada "(experimental)", no como el camino por defecto.

    Lo que sí: no tomes una decisión de especificación apoyándote SÓLO en ella.
    Contrástala con Shin-Fuller y con la acf/pacf, y si el veredicto contradice
    al resto del informe, hoy es más probable que el fallo esté en esta
    implementación que en los otros instrumentos.

    Tests run (where applicable to the model structure):
    - Shin-Fuller (1998): Phi_1u test; H0: rho=1-4/n (near-unit-root); crit 5%≈1.75
    - DCD: non-invertibility of regular MA factors (H0: theta=1)          [exper.]
    - DCD_f: non-invertibility of seasonal MA factors (H0: lambda2=-1)    [exper.]
    - RV: fixed frequency for AR(2) factors
    - MEG: HSM sweep — stochastic vs deterministic seasonality, frequency by
      frequency (requires D=0 + harmonics). `meg` is the API name; the class is
      HSM (Hybrid Seasonal Models).                                       [exper.]

    Parameters
    ----------
    inp_path : path to .inp or .pre file
    run_meg  : whether to run MEG (slow, default True; EXPERIMENTAL, see above)
    """
    try:
        from mcp.types import TextContent
        from art.describe import describe_formal_tests
        from art.diagnosis import diagnose
        ts, m = _load_fitted(inp_path)
        desc = describe_formal_tests(m, run_meg=run_meg)

        # Ésta es la etapa de CIERRE: el analista da aquí el vistazo final, y
        # tiene que dárselo AL MODELO, no sólo a los contrastes. La ecuación con
        # sus parámetros y errores típicos es la forma en que este sistema
        # presenta un modelo, y no aparecía aquí — la capacidad existía
        # (`model_equation_display`) y nada la conectaba donde hace falta.
        # Se antepone la ecuación, se añade el veredicto de la diagnosis, y los
        # contrastes van detrás: primero QUÉ modelo, luego si es adecuado, luego
        # qué dicen los contrastes sobre su especificación.
        bloques = [_equation_for_prompt(ts, m)]
        try:
            dg = diagnose(m)
            qmin = min(dg.q_pvalues) if dg.q_pvalues else 1.0
            nex = len(dg.extreme or [])
            bloques.append(
                "**Diagnosis:** ruido blanco (Q) p-mín %.4f %s · normalidad (JB) "
                "%.3f p=%.4f %s · residuos |z|>3: %d"
                % (qmin, "✓" if qmin > 0.05 else "✗",
                   dg.jb_stat, dg.jb_pvalue, "✓" if dg.jb_pvalue > 0.05 else "✗",
                   nex))
        except Exception:
            pass
        bloques.append(desc.summary)
        if desc.recommendation:
            bloques.append("---\n" + desc.recommendation)
        return [TextContent(type="text", text="\n\n".join(bloques))]
    except Exception as e:
        return _err(traceback.format_exc())


@mcp.tool()
def ar_factorization(inp_path: str, sper: int = 0) -> list:
    """
    Factorize the estimated AR operator(s) of a fitted model and identify
    candidate seasonal AR_f factors.

    Each regular AR factor P(B) = 1 - c1 B - ... - cp B^p is factored (via
    numpy.roots) and characterized in the original ``Root`` format: the roots
    table and the real factors (1 - a[1] B) and complex factors
    (1 - a[1] B - a[2] B^2), each complex factor given its damping factor d, its
    frequency freq (cycles/obs) and its period per (obs/cycle).  For a
    directly-estimated AR(2) factor (both coefficients free), d and per carry
    delta-method standard errors (``d ± SE``, ``per ± SE``) from the factor's 2x2
    coefficient covariance — matching ABTreadway-Dperar2.xls / caracterizar_operadores.py.

    INTERPRETATION IS LEFT TO THE ASSISTANT: a complex factor whose period matches
    a seasonal cycle (per = s/k for an integer harmonic k) and whose damping d is
    near 1 is a candidate seasonal AR_f operator -- a stochastic-seasonal factor
    hidden inside an un-factored AR(p) -- to feed the MEG (DCD_f) and the dual
    Shin-Fuller AR_f test (paper SF_MEG, confirmatory pair). Because fue can
    estimate the AR operator factored or un-factored, factoring a freely estimated
    AR(p) exposes such factors.

    Parameters
    ----------
    inp_path : path to .inp or .pre file (fitted model)
    sper     : seasonal period; 0 (default) uses the series frequency
    """
    try:
        import numpy as np
        from art.roots import factor_ar, describe
        ts, m = _load_fitted(inp_path)
        s = int(sper) or int(getattr(ts, "freq", 12))
        factors = m.ar or []
        if not factors:
            return _result("The model has no regular AR operator to factorize.")
        # Reconstruct the fitted coefficients per AR factor: free values come from
        # model.params (ordering: omega, delta, AR regular, ...), fixed from model.ar.
        n_omega = sum(sum(itv.omega_free) for itv in (m.interventions or []))
        n_delta = sum(sum(itv.delta_free) for itv in (m.interventions or []))
        params = np.asarray(m.params, dtype=float)
        # Full parameter covariance (npar x npar, aligned with m.params), used to
        # attach delta-method SEs to directly-estimated AR(2) factors (BUG-0004).
        cov_full = None
        try:
            cov_full = np.asarray(m._result.cov_matrix, dtype=float)
            if cov_full.ndim == 1:
                kk = int(round(cov_full.size ** 0.5))
                cov_full = cov_full.reshape(kk, kk)
        except Exception:
            cov_full = None
        # BUG-0027: con la semilla EXACTAMENTE en el óptimo el optimizador para en
        # niter=0 y la covarianza que vuelve es la semilla del BFGS (c·I), no el
        # hessiano. Los ± del método delta que saldrían de ahí son ficción — y una
        # ficción creíble, porque el valor es pequeño. Mejor no darlos.
        from art.diagnosis import covariance_is_degenerate, AVISO_COV_DEGENERADA
        _cov_degenerada = covariance_is_degenerate(getattr(m, "_result", None))
        if _cov_degenerada:
            cov_full = None
        idx = n_omega + n_delta
        blocks = []
        for k, factor in enumerate(factors):
            free = (m.ar_free[k] if m.ar_free and k < len(m.ar_free)
                    else [True] * len(factor))
            coefs, coef_idx = [], []
            for j in range(len(factor)):
                if free[j]:
                    coefs.append(float(params[idx])); coef_idx.append(idx); idx += 1
                else:
                    coefs.append(float(factor[j])); coef_idx.append(None)
            if len(coefs) < 2:
                blocks.append(f"AR factor #{k}: first-order (1 - {coefs[0]:.5f} B) "
                              f"-- real root, no seasonal factor.")
                continue
            # 2x2 coefficient covariance for a directly-estimated AR(2) whose two
            # coefs are both free — enables d ± SE and per ± SE via the delta method.
            fcov = None
            if (len(coefs) == 2 and cov_full is not None
                    and coef_idx[0] is not None and coef_idx[1] is not None
                    and max(coef_idx) < cov_full.shape[0]):
                fcov = cov_full[np.ix_(coef_idx, coef_idx)]
            fac = factor_ar(coefs, sper=s, cov=fcov)
            blocks.append(f"AR factor #{k} (order {len(coefs)}):\n" + describe(fac))
        if _cov_degenerada:
            blocks.insert(0, "⚠ **Sin errores típicos** (BUG-0027): "
                             + AVISO_COV_DEGENERADA
                             + "\n\nLos factores y sus d/frecuencia/periodo que siguen "
                               "son correctos; lo que falta son los ±.")
        from mcp.types import TextContent
        return [TextContent(type="text", text="\n\n".join(blocks))]
    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def meg_reformulate(inp_path: str, freq: int, output_path: str,
                    base_pre_path: str = "", with_witness: bool = True,
                    guion_path: str = "", guion_name: str = "",
                    guion_decision: str = "",
                    guion_rationale: str = "") -> list:
    """
    Reformulate the model for STOCHASTIC seasonality at frequency `freq`, after the
    MEG (DCD_f / Shin-Fuller AR_f) has concluded stochastic there.

    Builds the model the MEG recommends, FROM THE LAST .pre, without editing files by
    hand. It loads the last fitted model (base_pre_path if given, else inp_path),
    activates the seasonal AR_f unit root at `freq` (ifadf[freq]=1: the operator
    1-2cos(w)B+B^2 for an interior frequency, or 1+B at the Nyquist f=s/2), removes the
    now-annihilated deterministic harmonics at `freq`, re-estimates, writes the
    reformulated .pre/.out to output_path and shows the model equation + diagnosis.

    with_witness=True (DEFAULT) also adds the free invertible MA_f testigo
    (1-2λcos(w)B+λ²B²), so the reformulated model is EXACTLY what the MEG/DCD_f
    contrasts — the AR_f unit root AND the MA_f witness together. This is the correct
    stochastic model S. After fitting, run `formal_tests` to read the witness DCD_f:
    LR>crit ⇒ genuine stochastic; λ→boundary (−1) ⇒ quasi-cancellation (frontier).

    with_witness=False gives the AR-only form (no witness): this OVER-DIFFERENCES the
    seasonal (inflated σ, exploded Q-test) and is only a diagnostic subproduct, NOT S.

    BUG-0053. `guion_path`/`guion_name`/`guion_decision`/`guion_rationale` work
    exactly as in `confirm_and_estimate`. Without them this tool wrote a model to
    disk that the guion never saw, and the lineage broke at the worst possible
    place: the reformulated model became an orphan, and whatever was chained on
    top of it was recorded as descending from the model BEFORE the
    reformulation. The one branch the MEG exercise exists to document was the one
    the map could not show.
    Use it only to inspect the bare over-differenced residuals.

    Multiple stochastic frequencies: call iteratively (strongest first), passing the
    previous output's .pre as base_pre_path, re-running formal_tests after each — the
    per-frequency MEG on the all-deterministic model has cross-frequency contamination.

    Parameters
    ----------
    inp_path      : source .inp/.pre (series data; also the model if base_pre_path="")
    freq          : seasonal frequency to make stochastic (1..s/2)
    output_path   : path to write the reformulated model (.pre/.out alongside)
    base_pre_path : the last .pre (the deterministic model); if empty, uses inp_path
    with_witness  : add the free MA_f testigo (default True → the correct S model)
    """
    try:
        from art.formal_tests import reformulate_stochastic
        from art.describe import describe_diagnosis
        src = base_pre_path or inp_path
        ts, m = _load_fitted(src)
        s = int(getattr(ts, "freq", 12))
        f = int(freq)
        if not (1 <= f <= s // 2):
            return _err(f"freq must be in 1..{s // 2} (got {freq})")
        mc = reformulate_stochastic(m, f, s, with_witness=with_witness)
        try:
            mc.fit()
        except Exception:
            return _err("Re-estimation of the reformulated model failed:\n"
                        + traceback.format_exc())
        # BUG-0035: esto escribía el `.pre` y el `.out` y NO el `.inp` de
        # `output_path`, así que la herramienta devolvía una ruta `.inp` que no
        # existía y el paso siguiente moría con FileNotFoundError. Todas las
        # demás herramientas de estimación escriben la terna, y el convenio
        # depende de ello: el `.inp` es la ESPECIFICACIÓN, el `.pre` el óptimo
        # reejecutable y el `.out` el registro. Sin `.inp` este eslabón no se
        # puede reestimar, que es de donde salen los errores típicos válidos
        # (BUG-0027).
        #
        # Y se reestima DESDE el `.inp` recién escrito antes de presentar: así
        # el nombre del modelo que sale en la ecuación es el del fichero que el
        # analista tiene delante, y no el heredado del modelo de origen — que es
        # por lo que la reformulación de RATIO salía rotulada `RATIO_m30`
        # estando en `RATIO_m40`.
        base = os.path.splitext(output_path)[0]
        pre_path = base + ".pre"
        try:
            _write_inp(ts, mc, output_path)
            ts, mc = _load_fitted(output_path)
        except Exception as e:
            _warn(f"no se pudo escribir/reestimar el .inp en {output_path}", e)
        try:
            mc.write_pre(pre_path)
            try:
                mc.write_out(base + ".out")
            except Exception as e:
                _warn(f"write_out({base}.out) failed", e)
        except Exception:
            pre_path = output_path
        eq = _equation_for_prompt(ts, mc)
        diag = describe_diagnosis(mc)
        kind = "(1 + B) [Nyquist]" if f == s // 2 else "(1 − 2cos·B + B²)"
        if with_witness:
            wit = ("(1 + θB)" if f == s // 2 else "(1 − 2λcos·B + λ²B²)")
            witness_line = (f" + testigo MA_f libre {wit} (modelo S completo que "
                            f"contrasta el MEG). Lee su DCD_f con `formal_tests`.")
        else:
            witness_line = (" SIN testigo MA_f → modelo AR-only SOBRE-DIFERENCIADO "
                            "(subproducto diagnóstico, NO es S; usa with_witness=True).")
        header = (f"## Reformulación MEG — estacionalidad ESTOCÁSTICA en f={f}\n\n"
                  f"Activado el AR_f de raíz unitaria `ifadf[{f}]=1` {kind}"
                  f"{witness_line} Eliminados los armónicos deterministas en f={f}. "
                  f"Re-estimado desde `{os.path.basename(src)}`.\n\n{eq}\n\n")
        diag.summary = (header + diag.summary
                        + f"\n\n*Modelo guardado en: {output_path}  |  "
                          f"semilla del siguiente paso: {pre_path}  |  "
                          f"resultados: {base}.out*")

        # BUG-0053. El modelo reformulado se escribía a disco y el guion no se
        # enteraba: quedaba huérfano, y lo que se encadenara encima se registraba
        # como descendiente del modelo ANTERIOR a la reformulación. La rama que
        # el ejercicio del MEG existe para documentar era justamente la que el
        # mapa no podía enseñar.
        #
        # Se registra `mc` --el reformulado, recargado de `output_path`--, no `m`,
        # que es el baseline: una entrada con la ruta de uno y la especificación
        # del otro sería peor que ninguna.
        if guion_path:
            try:
                nota = _record_to_guion(
                    mc, output_path, getattr(mc, "boxlam", 0.0), guion_path,
                    name=guion_name or f"MEG_f{f}",
                    decision=guion_decision or (
                        f"Reformulación MEG en f={f}: estacionalidad ESTOCÁSTICA "
                        f"(ifadf[{f}]=1, armónicos de f={f} eliminados"
                        + (", testigo MA_f libre" if with_witness else
                           ", SIN testigo — subproducto diagnóstico") + ")"),
                    rationale=guion_rationale,
                    base_pre_path=src,
                )
                diag.summary += f"\n\n{nota}"
            except Exception as e:
                _warn("no se pudo registrar la reformulación MEG en el guion", e)

        return _result(diag)
    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def meg_frequency(inp_path: str, freq: int, base_pre_path: str = "") -> list:
    """
    MEG for ONE given seasonal frequency, evaluated on the CHAINED baseline.

    Unlike `formal_tests` (which sweeps all frequencies), this runs the MEG /
    DCD_f contrast for exactly one frequency `freq`, ON TOP of the supplied
    baseline model — its AR/AR_s, μ, interventions and the OTHER harmonics are
    all kept. This is the correct chained MEG: from the baseline (e.g. harmonics
    + seasonal AR(1) + μ) it reformulates only f as stochastic (ifadf[freq]=1:
    the AR_f unit root 1−2cos(ω)B+B² for an interior f, or 1+B at the Nyquist;
    removes f's cos/sin harmonics; adds the free invertible MA_f testigo), then
    fits the free and the constrained (λ₂=−1) models and reports the DCD_f LR:

      LR = 2·[logL(free) − logL(λ₂=−1)]
      LR > crit  ⇒ witness invertible, seasonal unit root genuine ⇒ STOCHASTIC.
      LR ≤ crit  ⇒ witness at −1, cancels the AR_f unit root       ⇒ DETERMINISTIC.

    The witness coef is reported as the INVERTIBLE estimate (the engine flips
    |θ₂|>1 → 1/θ₂ inside the likelihood). If STOCHASTIC, adopt the form with
    `meg_reformulate(freq=…, base_pre_path=<this baseline>)`.

    Parameters
    ----------
    inp_path      : source .inp/.pre (series data; also the model if base_pre_path="")
    freq          : the single seasonal frequency to test (1..s/2)
    base_pre_path : the baseline .pre (AR_s+μ+harmonics); if empty, uses inp_path
    """
    try:
        from art.formal_tests import meg as _meg
        from art.describe import Description
        src = base_pre_path or inp_path
        ts, m = _load_fitted(src)
        s = int(getattr(ts, "freq", 12))
        f = int(freq)
        if not (1 <= f <= s // 2):
            return _err(f"freq must be in 1..{s // 2} (got {freq})")
        if getattr(m, "ifadf", None) and len(m.ifadf) > f and m.ifadf[f] == 1:
            return _err(f"freq={f} ya es estocástica (ifadf[{f}]=1) en el baseline "
                        f"`{os.path.basename(src)}` — no se puede re-testear.")
        try:
            results = _meg(m, frequencies=[f])
        except ValueError as _ve:      # baseline guard (_check_reformulable)
            return _err(str(_ve))
        r = results[0]

        # Surface the baseline's noise structure so the analyst confirms it is the
        # intended pre-MEG model — a baseline missing μ silently changes the verdict
        # (the μ=0 pitfall). The reformulation preserves whatever the baseline carries.
        from fue.forecast import _reconstruct_params as _rp
        mu_txt = ("**sin media μ** ⚠" if not getattr(m, "estimate_mu", False)
                  else f"μ={_rp(m, m.params)[8]:.4f}")
        n_arr  = sum(len(fac) for fac in (m.ar or []))
        n_ars  = sum(len(fac) for fac in (m.ar_s or []))
        n_harm = sum(1 for itv in (m.interventions or [])
                     if getattr(itv, "type", None) in ("cos", "sin", "alter"))

        is_nyquist = (f == s // 2)
        kind = "(1 + B) [Nyquist]" if is_nyquist else "(1 − 2cos·B + B²)"
        head = (f"## MEG en f={f}  (una frecuencia, encadenado sobre "
                f"`{os.path.basename(src)}`)\n\n"
                f"**Baseline:** {mu_txt} · AR({n_arr}) · AR_s({n_ars}) · {n_harm} armónicos "
                f"— el veredicto depende del ruido del baseline; usa el pre-MEG.\n\n"
                f"Reformula solo f={f} como estocástica (AR_f raíz unitaria "
                f"`ifadf[{f}]=1` {kind} + testigo MA_f libre), conservando "
                f"AR/AR_s, μ, intervenciones y los demás armónicos. Contrasta el "
                f"testigo con DCD_f (H₀: λ₂=−1, raíz unitaria estacional).\n")

        d = r.dcd_result
        if d is None:
            body = ("\n**Resultado: AMBIGUO** — la re-estimación del modelo "
                    "reformulado falló (no convergió). Revisa el baseline.")
            rec = "MEG f={0}: ambiguo (fallo de estimación).".format(f)
            return _result(Description(summary=head + body, figure_b64=None,
                                       recommendation=rec))
        # (un fallo de estimación no produce modelo, así que no hay nada que
        # registrar en el guion: se sale antes.)

        crit = d._crit
        pct = ("*** (1%)" if d.rejects_1pct else "** (5%)" if d.rejects_5pct
               else "* (10%)" if d.rejects_10pct else "(no rechaza)")
        verdict = ("**ESTOCÁSTICA**" if r.stochastic
                   else "**DETERMINISTA**")
        body = (
            f"\n| | valor |\n|---|---|\n"
            f"| MA_f testigo λ₂ (invertible) | {r.coef_ma_f:.6f} |\n"
            f"| H₀ (raíz unitaria) | λ₂ = −1 |\n"
            f"| logL(libre) | {d.loglik_free:.4f} |\n"
            f"| logL(λ₂=−1) | {d.loglik_constrained:.4f} |\n"
            f"| **LR = 2·Δ** | **{d.lr:.4f}** {pct} |\n"
            f"| crít DCD_f (n={d.n}, s={'2' if d.complex_pair and not is_nyquist else '1'}) "
            f"| 10%={crit['10%']}, 5%={crit['5%']}, 1%={crit['1%']} |\n\n"
            f"### Veredicto f={f}: {verdict}\n"
        )
        if r.stochastic:
            body += (f"\nLR={d.lr:.2f} > crít 5%={crit['5%']}: el testigo es invertible "
                     f"(λ₂ lejos de −1), la raíz unitaria estacional NO se cancela ⇒ "
                     f"**estacionalidad estocástica genuina en f={f}** (AR_f no "
                     f"estacionario).")
            rec = (f"f={f} ESTOCÁSTICA (MEG LR={d.lr:.2f} > {crit['5%']}). Adopta la "
                   f"forma con `meg_reformulate(freq={f}, base_pre_path=\"{src}\", "
                   f"output_path=…)` y reestima; después re-testea las demás "
                   f"frecuencias sobre el nuevo baseline.")
        else:
            body += (f"\nLR={d.lr:.2f} ≤ crít 5%={crit['5%']}: no se rechaza λ₂=−1; el "
                     f"testigo MA_f cuasi-cancela la raíz unitaria del AR_f ⇒ **f={f} "
                     f"determinista** (los armónicos cos/sin actuales son la "
                     f"especificación correcta).")
            rec = (f"f={f} DETERMINISTA (MEG LR={d.lr:.2f} ≤ {crit['5%']}). Mantén los "
                   f"armónicos cos/sin en f={f}; no reformules.")


        return _result(Description(summary=head + body, figure_b64=None,
                                   recommendation=rec))
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Seasonal parameters (Bloque G)
# ---------------------------------------------------------------------------

@mcp.tool()
def seasonal_param_analysis(inp_path: str) -> list:
    """
    Visualise estimated seasonal harmonic parameters (cos/sin) with ±2 SE bars.

    For each harmonic k=1..freq//2 present in the model, reports:
    - cos_k and sin_k coefficients with SE and t-ratio
    - Amplitude A_k = sqrt(cos_k² + sin_k²)
    - Which harmonics are significant (|t| > 2) and which could be dropped

    Bar chart figure: two panels (cos coefficients | sin coefficients),
    colour-coded by significance.

    ⚠ PRECONDITION — run the MEG FIRST (BUG-0010)
    ---------------------------------------------
    "Which harmonics could be dropped" is only answerable AFTER the MEG has run
    on the all-deterministic baseline. Two reasons, and the second is the one
    that bites:

    * The MEG's null model IS the deterministic harmonic at f. Drop it and there
      is nothing left to contrast: the sweep reports that frequency as
      **sin contrastar** and the analyst never gets a verdict for it.
    * **A low t-ratio at f is evidence FOR stochastic seasonality at f**, not
      evidence that f is absent. A fixed-coefficient harmonic fitted to a
      frequency whose amplitude wanders averages toward zero. So pruning by
      significance removes preferentially the frequencies the MEG most needs to
      look at, under the very hypothesis (deterministic) it exists to test.

    Measured on IPC_ES, the two criteria came out close to orthogonal in both
    directions at once: f=5 (|t| = 0.29 and 1.27 — the first pair any filter
    deletes) carried the second-highest MEG evidence of stochasticity, while
    f=3 (|t| = 5.4 and 2.1 — untouchable by any filter) is the one that IS
    stochastic.

    Parameters
    ----------
    inp_path : path to a fitted .inp or .pre file
    """
    try:
        from art.describe import describe_seasonal_params
        _, m = _load_fitted(inp_path)
        return _result(describe_seasonal_params(m))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Seasonal simplification (Bloque H)
# ---------------------------------------------------------------------------

@mcp.tool()
def test_seasonal_simplification(inp_path: str,
                                  freq_list: list[int] | None = None,
                                  alpha: float = 0.05) -> list:
    """
    Joint LR test for eliminating seasonal harmonics: H₀: cos_k = sin_k = 0.

    Fits a restricted model with the specified harmonics fixed to zero and
    computes LR = 2·(L_free − L_restricted) ~ χ²(df), where df = number of
    constrained parameters (2 per regular harmonic, 1 for Nyquist/alter).

    ⚠ RUN THE MEG FIRST. This tool prunes the deterministic harmonics, which are
    the MEG's null hypothesis: prune before testing and that frequency can no
    longer be contrasted at all. And the t-ratio is not neutral evidence here —
    a low |t| at f is evidence FOR stochastic seasonality at f, not for its
    absence. See `seasonal_param_analysis` for the measured IPC_ES case and
    `meg_frequency` for the test itself. (BUG-0010.)

    Typical workflow, AFTER the MEG has run on the all-deterministic baseline:
    - Pass the k values with |t| ≤ 2 in both cos and sin as freq_list —
      **excluding any frequency the MEG called stochastic**, which needs
      `ifadf[f]=1` rather than pruning.
    - If LR < χ²(df, 5%): remove those harmonics and refit.
    - If LR ≥ χ²(df, 5%): the harmonics are jointly significant — keep them.

    Parameters
    ----------
    inp_path  : path to a fitted .inp or .pre file
    freq_list : harmonic indices to test (None = test all harmonics jointly)
    alpha     : significance level (default 0.05)
    """
    try:
        from art.describe import describe_seasonal_simplification
        _, m = _load_fitted(inp_path)
        return _result(describe_seasonal_simplification(m, freq_list=freq_list,
                                                        alpha=alpha))
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Interventions
# ---------------------------------------------------------------------------

@mcp.tool()
def intervention_analysis(inp_path: str, threshold: float = _Z_USER) -> list:
    """
    Detect extreme residuals and assess their impact on ACF/PACF and tests.

    Identifies residuals with |z| > threshold and reports:
    - Date and standardised z-value of each extreme observation
    - Fraction of total variance explained (global ACF/PACF compression)
    - ACF lags most affected by the outlier's pair-contribution
    - Whether Jarque-Bera and Ljung-Box Q are unreliable

    Parameters
    ----------
    inp_path  : path to .inp or .pre file
    threshold : |z| threshold for flagging extremes (default 3.5)
    """
    try:
        from art.describe import describe_interventions
        _, m = _load_fitted(inp_path)
        return _result(describe_interventions(m, threshold=threshold))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Full report
# ---------------------------------------------------------------------------
# Tool: intervention significance testing (Phase 4b)
# ---------------------------------------------------------------------------

@mcp.tool()
def test_interventions(inp_path: str, alpha: float = 0.05) -> list:
    """
    Test H₀: ω=0 for every non-structural intervention in a fitted model.

    Runs a t-test on each free omega parameter of pulse, step, ramp, and
    similar interventions (cosine/sine harmonics and alter are structural
    and skipped by default). Identifies which interventions are non-significant
    and can be removed to simplify the model.

    For interventions with a transfer function (delta ≠ 0), also computes
    a Wald joint test H₀: g = α·ω = 0.

    Parameters
    ----------
    inp_path : path to a fitted .inp or .pre file
    alpha    : significance level for classification (default 0.05)
    """
    try:
        from mcp.types import TextContent
        from art.interventions import simplify_interventions, simplify_summary

        ts, m = _load_fitted(inp_path)
        results = simplify_interventions(m, alpha=alpha)

        if not results:
            return [TextContent(type="text",
                                text="*No hay intervenciones no-estructurales en el modelo.*")]

        try:
            eq_text = _equation_for_prompt(ts, m)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"

        summary   = simplify_summary(results, alpha=alpha)
        n_sig     = sum(1 for r in results if r.significant)
        n_nosig   = len(results) - n_sig

        text = (
            f"### Contraste de intervenciones — {m.series.name or 'modelo'}\n\n"
            + f"**{n_sig} significativas**, **{n_nosig} prescindibles**"
            + f" (α={alpha:.2f},  df={results[0].df})\n\n"
            + eq_text
            + "\n\n---\n\n" + summary
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------

@mcp.tool()
def full_report(inp_path: str, output_path: str,
                run_meg: bool = True,
                intervention_threshold: float = _Z_USER) -> str:
    """
    Generate a complete HTML report for a fitted model and save it to disk.

    The report is a self-contained HTML file with collapsible sections:
    1. Estimated model (parameters, SE, t-stats, AIC/BIC)
    2. Diagnosis (residuals, ACF/PACF, Q-test, Jarque-Bera)
    3. Formal tests (DCD, DCD_f, RV, MEG where applicable)
    4. Interventions (extreme residuals and ACF distortion warnings)

    Parameters
    ----------
    inp_path             : path to .inp or .pre file
    output_path          : path for the HTML output file
    run_meg              : run MEG test (default True, only if D=0 + harmonics)
    intervention_threshold : |z| threshold for outlier warnings (default 3.5)
    """
    try:
        from art.full_report import save_full_report
        _, m = _load_fitted(inp_path)
        output_path = os.path.expanduser(output_path)
        r = save_full_report(
            m, output_path,
            run_meg=run_meg,
            intervention_threshold=intervention_threshold,
        )
        verdict = "APROBADO ✓" if r.diagnosis.clean else "REVISAR ✗"
        return (
            f"Informe generado: {output_path}\n"
            f"Diagnosis: {verdict}\n"
            f"DCD: {len(r.dcd_results)} resultado(s)\n"
            f"MEG: {len(r.meg_results)} frecuencia(s)\n"
            f"Outliers ({intervention_threshold}): {r.interventions.has_outliers}"
        )
    except Exception as e:
        return f"❌ {traceback.format_exc()}"


# ---------------------------------------------------------------------------
# Tool: save identification report
# ---------------------------------------------------------------------------

@mcp.tool()
def save_identification_report(inp_path: str, output_path: str,
                                d: int = 2, D: int = 0,
                                lam: float = 0.0) -> str:
    """
    Generate and save a full HTML identification report to disk.

    The report contains the ACF/PACF listing for the differenced series
    (for d=0,1,2 or with seasonal differencing) and the top-5 ARMA order
    suggestions ranked by pattern similarity.

    Parameters
    ----------
    inp_path    : path to the .inp file (series is used, model spec ignored)
    output_path : path for the HTML output file
    d           : regular differencing order (default 2)
    D           : seasonal differencing order (default 0)
    lam         : Box-Cox lambda (0.0=log, 1.0=identity, default 0.0)
    """
    try:
        import art
        ts, _ = _load_ts_model(inp_path)
        output_path = os.path.expanduser(output_path)
        art.save_identification_report(ts, output_path, lam=lam)
        specs = art.suggest_orders(ts, d=d, D=D, lam=lam, top_n=5)
        top = specs[0] if specs else None
        if top:
            return (
                f"Informe guardado: {output_path}\n"
                f"Top sugerencia: ARIMA({top.p},{d},{top.q})"
                f"({top.P},{D},{top.Q})_{top.s}  similitud={top.similarity:.3f}"
            )
        return f"Informe guardado: {output_path} (sin sugerencias)"
    except Exception as e:
        return f"❌ {traceback.format_exc()}"


# ---------------------------------------------------------------------------
# Helpers — guided workflow
# ---------------------------------------------------------------------------

def _auto_scan_section(ts, m, lam: float, d: int, D: int,
                        p: int, q: int, P: int, Q: int,
                        inp_path: str, pre_path: str
                        ) -> "tuple[str, str | None]":
    """Auto-scan model residuals for outlier impact; return (text_section, b64).

    Calls describe_prelim_scan on residuals (d=0, D=0, lam=1.0) and appends
    an A/B choice: A) add intervention, B) proceed (ARMA or formal tests).
    Returns ("", None) on any error.
    """
    try:
        import fue as _fue
        from art.describe import describe_prelim_scan as _prelim_scan, _resid_start
        from art import policy
        if m.residuals is None:
            return "", None
        # m.residuals.start is unreliable (fue sets it to 1900); recompute it
        _rstart = _resid_start(m)
        _res_ts = _fue.TimeSeries(
            m.residuals.data, freq=ts.freq,
            start=_rstart, name=f"Resid {ts.name or ''}",
        )
        # outlier_autoscan (2.5): more sensitive than the user-facing 3.5 so that
        # marginal outliers are flagged during the cycle, not after formal diagnosis.
        _autoscan_z = policy.THRESHOLDS["outlier_autoscan"]
        scan = _prelim_scan(_res_ts, d=0, D=0, lam=1.0, threshold=_autoscan_z)
        # Count only FREE (estimated) ARMA parameters to distinguish m00 from final
        def _n_free(vals, free):
            if not vals:
                return 0
            if free is None:
                return len(vals)
            return sum(1 for f in (free[0] if isinstance(free[0], (list, tuple)) else free) if f)
        has_arma = any([
            _n_free(m.ar,   m.ar_free)   > 0,
            _n_free(m.ma,   m.ma_free)   > 0,
            _n_free(m.ar_s, m.ar_s_free) > 0,
            _n_free(m.ma_s, m.ma_s_free) > 0,
        ])
        level = scan.data.get("distortion_level", "none")
        n_out = scan.data.get("n_outliers", 0)
        var_o = scan.data.get("var_outlier_pct", 0.0)
        acf_o = scan.data.get("acf_max_pct", 0.0)

        # LATENT scan: it always runs, but only SURFACES a decision node when the
        # anomalies are large AND strongly distorting the ACF/PACF. Otherwise a
        # one-line mention and proceed (no figure) — keeps the flow uncluttered.
        if level != "strong":
            if n_out == 0:
                note = "anómalos revisados, ninguno significativo"
            else:
                lvl = "moderada" if level == "moderate" else "leve"
                note = (f"anómalos revisados ({n_out}): distorsión {lvl} "
                        f"(var_outlier={var_o:.1f}%, ACF_max={acf_o:.0f}%), no distorsionan "
                        "la ACF/PACF")
            nxt = ("procede a la identificación ARMA" if not has_arma
                   else "procede a contrastes formales")
            return ("\n\n---\n\n*✓ Escaneo de anómalos (latente): " + note + " → " + nxt
                    + ". Intervenir sigue siendo opción del analista.*"), None

        # Distortion STRONG → surface the decision node (calibration + A/B + figure).
        if has_arma:
            ab_choice = (
                "\n\n**PUNTO DE DECISIÓN (analista).** Anómalos grandes distorsionan con "
                "fuerza la ACF/PACF. Claude: presenta la distorsión calibrada y SUGIERE; "
                "decide el analista.\n\n"
                "**A) Añadir intervención** (si aún hay anomalías que distorsionan):\n"
                f"→ `suggest_intervention_form(inp_path=\"{pre_path}\", "
                "output_path=<próxima_versión.inp>, date=\"MM/YYYY\", form=\"auto\")`\n\n"
                "**B) Contrastes formales** (si los residuos están limpios):\n"
                "→ `formal_tests` / `simplify_interventions`"
            )
        else:
            ab_choice = (
                "\n\n**PUNTO DE DECISIÓN (analista): ¿tratar los anómalos ANTES de ARMA?**\n"
                "Anómalos grandes están distorsionando con fuerza la ACF/PACF. Claude: "
                "presenta la distorsión calibrada (var_outlier, ACF_max, retardos) y SUGIERE "
                "intervenir antes de ARMA; decide el analista.\n\n"
                "**A) Añadir intervención** — intervenciones ANTES de ARMA:\n"
                f"→ `suggest_intervention_form(inp_path=\"{pre_path}\", "
                "output_path=<próxima_versión.inp>, date=\"MM/YYYY\", form=\"auto\")`\n"
                "   Repite hasta que los residuos estén limpios.\n\n"
                "**B) Identificar ARMA** — si decides no intervenir:\n"
                f"→ `guided_identification(inp_path=\"{inp_path}\", "
                f"lam={lam}, d={d}, D={D}, pre_path=\"{pre_path}\")`"
            )
        section = "\n\n---\n\n" + scan.summary + "\n\n" + scan.recommendation + ab_choice
        return section, scan.figure_b64
    except Exception:
        return "", None


# ---------------------------------------------------------------------------
# Tool: guided identification (B1)
# ---------------------------------------------------------------------------

@mcp.tool()
def guided_identification(inp_path: str, lam: float = -1.0,
                           d: int = -1, D: int = -1,
                           pre_path: str = "",
                           objetivo: str = "univariante") -> list:
    """
    Sequential identification — ONE decision node per call.

    DECISION TREE — call in this sequence, one at a time:

    Call 1  lam=-1  (default)
      → Box-Cox scatter. Decide λ. WAIT for user.

    Call 2  lam=X  d=-1  (default)
      → Series(λ) + ACF/PACF at level d=0.
        ¿Trend? → next call with d=1.
        ¿No trend? → next call with d=0, D confirmed.
        Support: unit_root_analysis available if needed.
      WAIT for user.

    Call 3  lam=X  d=<level>  D=-1
      → Series(λ) differenced d times + ACF/PACF + HAC seasonality.
        Seasonal? + B1 (deterministic seasonality: harmonics, D=0):
          Confirm d and D=0, then:
            a) confirm_and_estimate(m00: harmonics only, p=0, q=0)
            b) preliminary_outlier_scan on m00 residuals
            c) [cycle: add steps → re-estimate → scan] until clean
            d) Call 4 with pre_path=<mNN.pre> (ARMA on clean residuals)
        Seasonal? + B2 (stochastic seasonality: seasonal differencing, D=1):
          → Call 4 with lam, d, D=1 (ARMA+P+Q on ∇∇_s series)
        ¿No seasonality? → D=0, no harmonics, Call 4 directly.
      WAIT for user to confirm d and D.

    Call 4  lam=X  d=<confirmed>  D=<confirmed>  [pre_path=<.pre>]
      B1 path (D=0, pre_path given):
        → ACF/PACF of clean model RESIDUALS from pre_path.
          PACF cuts → AR(p).  ACF cuts → MA(q).
          Also: mean significant? (μ̄/SE > 2) → estimate_mu=True
      B2 path (D=1, no pre_path):
        → ACF/PACF of ∇^d ∇_s y(λ).
          Also check lags s,2s,3s for seasonal P and Q.
      B1 no-outliers (D=0, no pre_path):
        → ACF/PACF of ∇^d y(λ) directly.
      WAIT for user to confirm p, q (and P, Q if D=1).

    Parameters
    ----------
    inp_path : path to series .inp file (all calls)
    lam      : Box-Cox lambda  (-1 = not yet decided → Call 1)
    d        : differencing order (-1 = not yet decided → Call 2)
    D        : seasonal differencing (-1 = not yet decided → Call 3)
    objetivo : what the model is FOR — "univariante" | "multivariante" |
               "estructural". Only bites at the seasonal node (Call 3), where it
               says what the purpose implies for the B1/B2 route. It was
               reachable only from `build_model`, so an analyst walking the nodes
               one at a time could not state the purpose at all — and the route
               is precisely where the purpose matters.
    pre_path : path to fitted .pre (Call 4, B1): ARMA identified on
               its residuals instead of the raw transformed series.
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_boxcox, describe_seasonality, describe_identification
        ts, _ = _load_ts_model(inp_path)

        # ── Call 1: Box-Cox scatter ────────────────────────────────────────
        if lam < 0:
            bc      = describe_boxcox(ts)
            rec_lam = bc.data["recommended_lambda"]

            # Index series rule: series without a natural zero base → always log.
            # La regla vive en `policy.decide_domain`, no aquí: tenerla sólo en
            # esta capa es lo que produjo BUG-0015 —el camino autónomo partía una
            # familia de ocho IPC entre logs y niveles—. Una copia, dos caminos.
            is_index = policy.decide_domain(ts) == "price_index"
            if is_index and rec_lam != 0.0:
                rec_lam   = 0.0
                index_note = (
                    f"\n\n> ⚠ **REGLA ÍNDICE APLICADA:** «{ts.name or 'serie'}» es una "
                    "serie índice sin base natural — se impone **λ=0 (log)** "
                    "independientemente de las estadísticas Box-Cox."
                )
            else:
                index_note = ""

            _show_fig(bc.figure_b64, "boxcox")
            text = (
                "## Paso 1 — Transformación Box-Cox\n\n"
                + bc.summary + "\n\n---\n" + bc.recommendation
                + index_note
                + f"\n\n**Próximo paso:** confirma λ y llama con `lam={rec_lam}` "
                "(o el valor que decidas) para ver la serie transformada."
            )
            items = [TextContent(type="text", text=text)]
            if bc.figure_b64:
                items.append(ImageContent(type="image",
                                          data=bc.figure_b64, mimeType="image/png"))
            return items

        # ── Call 2: Series at d=0 + ADF/KPSS unit root table ─────────────
        if d < 0:
            from art.describe import describe_unit_root
            b64     = _plot_series_at_d(ts, lam=lam, d=0)
            lam_str = "log" if lam == 0.0 else f"λ={lam}"
            _show_fig(b64, "series_d0")

            # BUG-0023: este nodo evalúa DESDE d=0, y en la escuela de
            # Box-Jenkins no se saltan dos decisiones sin pasar por los
            # instrumentos de especificación y diagnosis: de d=0 sólo se
            # puede ir a d=1 o quedarse en d=0. Además la estacionalidad
            # —que aún NO se ha contrastado, va en el paso 3— destroza la
            # potencia de ADF y KPSS y los sesga hacia «vuelve a
            # diferenciar». Capar la tabla en d=1 impide recomendar un d=2
            # que este mismo nodo no ofrece como continuación.
            urt       = describe_unit_root(ts, lam=lam, max_d=1)
            rec_d     = urt.data.get("recommended_d", 1)

            text = (
                f"## Paso 2 — Serie transformada ({lam_str}), nivel d=0\n\n"
                "Observa la serie y su ACF/PACF:\n"
                "- **Tendencia visible** o ACF que decae muy lentamente → diferencia necesaria → d=1\n"
                "- **Sin tendencia aparente** → posiblemente d=0 es suficiente\n\n"
                "---\n\n"
                + urt.summary + "\n\n"
                + f"**Recomendación ADF+KPSS:** d = {rec_d}. {urt.recommendation}\n\n"
                "---\n\n"
                "**Instrumentos de este nodo** (si quieres mirar más a fondo): "
                f"`unit_root_analysis(inp_path, lam={lam})` para la tabla ADF/KPSS "
                f"sola · `identification_analysis(inp_path, d=…, D=0, lam={lam})` "
                "para la ACF/PACF a un orden concreto sin avanzar el flujo.\n\n"
                "**Confirma d y llama al paso 3:**\n"
                f"- ¿Hay tendencia? → `guided_identification(inp_path, lam={lam}, d=1)`\n"
                f"- ¿Sin tendencia? → `guided_identification(inp_path, lam={lam}, d=0, D=0)`"
            )
            items = [TextContent(type="text", text=text)]
            if b64:
                items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
            return items

        # ── Call 3: Series at level d, D not yet decided ──────────────────
        if D < 0:
            b64     = _plot_series_at_d(ts, lam=lam, d=d)
            lam_str = "log" if lam == 0.0 else f"λ={lam}"
            sym     = {0: "", 1: "∇", 2: "∇²"}.get(d, f"∇^{d}")
            _show_fig(b64, f"series_d{d}")

            sea_text = ""
            sea_fig  = None
            d_next_text = ""
            hay_estacionalidad = False
            if d > 0:
                sea     = describe_seasonality(ts)
                _show_fig(sea.figure_b64, "seasonality")
                sea_fig  = sea.figure_b64
                sea_text = (
                    "\n\n**Test HAC de estacionalidad (soporte):**\n"
                    + sea.summary + "\n\n---\n" + sea.recommendation
                )
                # BUG-0023: el tope de un paso es RELATIVO al d actual, no una
                # prohibición de d=2. Evaluada ya d y DESCARTADA la
                # estacionalidad, la contaminación que invalidaba el ADF ha
                # desaparecido y preguntar por d+1 es legítimo: es la segunda
                # decisión de la escala, tomada con su instrumento delante y no
                # de un salto. Con estacionalidad detectada NO se ofrece — ahí
                # el ADF sigue sesgado hacia «vuelve a diferenciar» y lo que
                # toca primero es tratarla.
                hay_estacionalidad = bool(sea.data.get("seasonal_detected", False))
                if not hay_estacionalidad:
                    from art.describe import describe_unit_root as _dur
                    _urt2  = _dur(ts, lam=lam, max_d=d + 1)
                    _rec2  = int(_urt2.data.get("recommended_d", d))
                    # La pregunta del nodo es «¿hace falta UNA MÁS?», no
                    # «redecide d desde cero». `recommended_d` recorre la tabla
                    # entera y puede devolver un valor POR DEBAJO de la d
                    # actual: eso no contesta esta pregunta — apunta a
                    # sobrediferenciación, que es el otro lado y lo dictamina el
                    # DCD sobre el modelo estimado, no un ADF sobre la serie.
                    if _rec2 > d:
                        _veredicto = (
                            f"\n\n→ La evidencia apunta a **d={_rec2}**. "
                            f"Reentra con `guided_identification(inp_path, lam={lam}, d={d + 1})`.")
                    elif _rec2 < d:
                        _veredicto = (
                            f"\n\n→ **No hace falta otra diferencia** — pero ojo: la "
                            f"recomendación de la tabla es d={_rec2}, POR DEBAJO de la "
                            f"d={d} confirmada. Esa fila reabre una decisión ya tomada y "
                            f"no contesta la pregunta de este nodo. Si sospechas "
                            f"sobrediferenciación, quien lo dictamina es el DCD sobre el "
                            f"MODELO ESTIMADO (etapa de contrastes formales), no un ADF "
                            f"sobre la serie: el testigo apilado en θ=+1 es la señal.")
                    else:
                        _veredicto = (
                            f"\n\n→ La evidencia sostiene **d={d}**. No hace falta otra "
                            f"diferencia.")
                    d_next_text = (
                        f"\n\n---\n\n### ¿Hace falta una diferencia más? (d={d} → d={d + 1})\n\n"
                        "Sin estacionalidad que contamine el contraste, esta "
                        "pregunta ya es legítima y se responde con el mismo "
                        "instrumento:\n\n"
                        + _urt2.summary
                        + _veredicto
                        + "\n\nRecuerda que esto sigue siendo especificación inicial: "
                          "el contraste que decide sobre el modelo estimado es "
                          "Shin-Fuller, con el DCD de sobrediferenciación como par."
                    )

            n_harm = max(ts.freq // 2 - 1, 0)
            sname  = ts.name or "SERIE"
            from art import policy as _pol
            _az = _pol.THRESHOLDS["outlier_autoscan"]

            # B1 path: estimate harmonics-only first; treating anomalies is the
            # analyst's OPTION (never required), then ARMA identification.
            b1_steps = (
                "\n\n### Route B1 — Deterministic seasonality (D=0 + seasonal harmonics)\n\n"
                "Secuencia (tratar anómalos es OPCIONAL — lo decide el analista, "
                "nunca es obligatorio):\n\n"
                f"**1.** Estima m00 (armónicos estacionales, sin ARMA):\n"
                f"```\nconfirm_and_estimate(\n"
                f"    inp_path=\"{inp_path}\",\n"
                f"    output_path=\"cases/{sname}/work/{sname}_m00.inp\",\n"
                f"    lam={lam}, d={d}, D=0, p=0, q=0, n_harmonics={n_harm}\n)\n```\n"
                f"*({n_harm} pares cos/sin + alter Nyquist = {n_harm + 1} componentes estacionales)*\n\n"
                f"**2.** El escaneo de anómalos viene LATENTE en la salida de m00. "
                f"Solo si hay anómalos grandes que distorsionan FUERTEMENTE la ACF/PACF, "
                f"SUGIERE intervenir (`suggest_intervention_form`, una a una) — pero la "
                f"decisión es del analista. Si la distorsión es leve, ve directo a ARMA.\n\n"
                "**3.** Identifica ARMA sobre los residuos del modelo actual "
                "(m00, o el último `.pre` si el analista decidió intervenir):\n"
                f"```\nguided_identification(\n"
                f"    inp_path=\"{inp_path}\",\n"
                f"    lam={lam}, d={d}, D=0,\n"
                f"    pre_path=\"cases/{sname}/work/{sname}_<modelo>.pre\"\n)\n```"
            )

            # B2 path: go directly to ARMA identification on ∇∇_s series
            b2_steps = (
                "\n\n### Route B2 — Stochastic seasonality (D=1, seasonal differencing)\n\n"
                f"```\nguided_identification(\n"
                f"    inp_path=\"{inp_path}\",\n"
                f"    lam={lam}, d={d}, D=1\n)\n```\n"
                "Identifica p, q (regular) y P, Q (estacional) sobre ∇∇_s y(λ), "
                "luego llama a `confirm_and_estimate`."
            )

            b1_note = (
                "\n\n> **Hipótesis B1:** D=0 + armónicos es revisable. "
                "El contraste MEG (`formal_tests`) evalúa al final si alguna "
                "frecuencia requiere tratamiento estocástico."
            )

            text = (
                f"## Paso 3 — {sym}y({lam_str}), d={d}\n\n"
                "Observa la serie diferenciada y su ACF/PACF:\n\n"
                "**¿Estacionalidad?** (picos en ACF/PACF a lags s, 2s, 3s…)\n"
                "  - Picos regulares/estables → **B1** (D=0, armónicos deterministas)\n"
                "  - Picos muy dominantes o irregulares → **B2** (D=1, dif. estacional)\n"
                "  - Sin picos estacionales → D=0, sin armónicos, → Call 4 directo\n\n"
                "**¿Tendencia residual?** → considera d=" + str(d + 1)
                + sea_text + d_next_text
                # BUG-0043: `b1_note`, `b1_steps` y `b2_steps` se anexaban
                # SIEMPRE. Tras concluir «Decisión A — sin estacionalidad… sin
                # armónicos cos/sin», la misma respuesta imprimía la receta
                # completa de la ruta B1 con `n_harmonics=1` y la de B2 con D=1.
                # Una salida que se contradice a sí misma no es verbosa: es una
                # instrucción para hacer lo contrario de lo que acaba de concluir,
                # y quien la lee no tiene forma de saber cuál de las dos vale.
                + ((_nota_objetivo(objetivo) + b1_note + b1_steps + b2_steps)
                   if hay_estacionalidad
                   else _sin_estacionalidad_next(inp_path, lam, d))
            )
            items = [TextContent(type="text", text=text)]
            if b64:
                items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
            if sea_fig:
                items.append(ImageContent(type="image", data=sea_fig, mimeType="image/png"))
            return items

        # ── Call 4: ARMA identification ───────────────────────────────────
        # B1 with clean residuals: pre_path points to fitted model after outlier cycle
        # B2 or no-outlier B1: identify directly on transformed series
        if pre_path:
            import fue as _fue
            from art.describe import _resid_start as _rs
            _, m_pre = _load_fitted(pre_path)
            res_start = _rs(m_pre)
            res_ts = _fue.TimeSeries(
                m_pre.residuals.data, freq=ts.freq,
                start=res_start, name=f"Resid {ts.name or ''}"
            )
            ident      = describe_identification(res_ts, d=0, D=0, lam=1.0)
            data_label = f"residuos de `{os.path.basename(pre_path)}`"
        else:
            ident      = describe_identification(ts, d=d, D=D, lam=lam)
            data_label = f"∇^{d}∇_s^{D} y(λ={lam})"

        _show_fig(ident.figure_b64, "identification")
        top   = ident.data["suggestions"][0] if ident.data["suggestions"] else {}
        rec_p = top.get("p", 0)
        rec_q = top.get("q", 0)
        rec_P = top.get("P", 0)
        rec_Q = top.get("Q", 0)
        n_harm = max(ts.freq // 2 - 1, 0)

        # ── Mean significance check ───────────────────────────────────────────
        import numpy as _np
        from art.identification import boxcox_transform as _bct, apply_differences as _adiff
        # BUG-0013: this used to read `m_pre.residuals` whenever a .pre existed
        # -- the residuals of a model in which mu had ALREADY been fitted. It
        # therefore measured t ~ 0 and advised `estimate_mu=False` on series
        # whose drift is significant at t > 5 (observed on IPC_ES: t=-0.00
        # reported against a true t=5.40). The question is about the DATA, so
        # it is always asked of the differenced series.
        _series_for_mu = _np.array(_adiff(_bct(ts.data, lam), ts.freq, d, D))
        _mu_bar = float(_np.mean(_series_for_mu))
        _se_mu  = float(_np.std(_series_for_mu, ddof=1) / _np.sqrt(len(_series_for_mu)))
        _t_mu   = _mu_bar / _se_mu if _se_mu > 0 else 0.0
        _rec_mu = abs(_t_mu) > 2.0
        # A base that already carries a fitted mean settles it: chaining from
        # its .pre inherits that estimate (BUG-0014), so dropping it here would
        # throw away an optimum.
        _mu_in_base = bool(pre_path and getattr(m_pre, "estimate_mu", False))
        if _mu_in_base:
            _rec_mu = True
        # BUG-0063. Esto reutilizaba `data_label`, que con `pre_path` dice
        # «residuos de X.pre» — y es FALSO para este bloque. BUG-0013 hizo que la
        # media se midiera deliberadamente sobre la SERIE DIFERENCIADA y no sobre
        # los residuos, porque los residuos de un modelo que YA lleva μ estimada
        # tienen media cero por construcción, y eso aconsejaba `estimate_mu=False`
        # en series con deriva significativa.
        #
        # Medido en los dos casos que lo destaparon:
        #   PGAS_m03   media de ∇ln y = +0.0146   media de los residuos = +0.7015
        #   ITCER_m02  media de ∇ln y = −0.0072   media de los residuos = +0.000001
        # El segundo es la demostración: su residuo tiene media cero PORQUE μ está
        # dentro. El número publicado siempre fue el correcto; la etiqueta no.
        _label_mu = f"∇^{d}∇_s^{D} y(λ={lam})"
        _nota_mu = ("" if not pre_path else
                    f"\n*(Se mide sobre la serie diferenciada, NO sobre los "
                    f"residuos de `{os.path.basename(pre_path)}`: si ese modelo ya "
                    f"lleva μ, sus residuos tienen media cero por construcción y "
                    f"la pregunta se contestaría sola. Ver BUG-0013.)*")
        mu_decision = (
            f"\n\n**¿Incluir media (μ)?** Deriva de {_label_mu}: "
            f"μ̄={_mu_bar:.4f}, SE={_se_mu:.4f}, t={_t_mu:+.2f} → "
            + ("**Sí, `estimate_mu=True`** — el modelo base ya la lleva estimada "
               "y se hereda al encadenar por `base_pre_path`" if _mu_in_base
               else "**Sí, `estimate_mu=True`** (|t|>2)" if _rec_mu
               else "**No, `estimate_mu=False`** (|t|≤2, sin deriva)")
            + "\n*(En un índice de precios μ ES la tasa de inflación: si sale "
              "significativa, omitirla deja la deriva en los residuos.)*"
            + _nota_mu
        )

        if D == 1:
            # B2: regular + seasonal ARMA — check lags s, 2s for P, Q
            seasonal_note = (
                f"\n\n**Para P y Q (operadores estacionales, lag s={ts.freq}):**\n"
                f"- ACF en lag {ts.freq} significativo, PACF(lag {ts.freq}) decae → **Q=1** (SMA)\n"
                f"- PACF en lag {ts.freq} significativo, ACF(lag {ts.freq}) decae → **P=1** (SAR)\n"
                f"- Caso más común para mensuales con D=1: Q=1 → ARIMA×(0,1,1)_{ts.freq}\n"
                + mu_decision
            )
            next_call = (
                f"Llama a `confirm_and_estimate` con\n"
                f"`lam={lam}, d={d}, D=1, p=<p>, q=<q>, P=<P>, Q=<Q>"
                f", estimate_mu={'True' if _rec_mu else 'False'}`\n"
                f"*(Sugerencia: p={rec_p}, q={rec_q}, P={rec_P}, Q={rec_Q})*"
            )
        else:
            if pre_path:
                # BUG-0052. La lista de arriba se ha calculado sobre los
                # RESIDUOS de `pre_path`, que ya tienen su ARMA quitado: lo que
                # sugiere es un INCREMENTO, «qué añadir». Pero
                # `confirm_and_estimate(..., base_pre_path=...)` hereda
                # armónicos, intervenciones y media y **SUSTITUYE** el ARMA por
                # el (p,q) que se le pase. Tomada al pie de la letra, la
                # sugerencia reestimaba el MISMO modelo: sobre una base con
                # MA(1) cuyos residuos piden q=1, pasar q=1 no da un MA(2), da
                # otra vez el MA(1). Hay que sumar, y hay que decirlo.
                # BUG-0057. Contar `len(m.ar[0])` cuenta también los operadores
                # FIJADOS. Un `.inp` con `1 1` / `0.0000 0` declara un AR(1)
                # fijado en cero --presente en la estructura, no estimado-- y
                # eso se leía como «la base ya lleva p=1». Seguir la aritmética
                # estimaba un AR LIBRE donde el analista no había pedido
                # ninguno. El incremento se cuenta sobre lo que de verdad se
                # estima, así que sólo cuentan los coeficientes libres.
                def _libres(fac, libres):
                    if not fac:
                        return 0
                    if not libres:                 # sin banderas: todos libres
                        return len(fac[0])
                    return sum(1 for f in libres[0] if f)
                p_base = _libres(m_pre.ar, getattr(m_pre, "ar_free", None))
                q_base = _libres(m_pre.ma, getattr(m_pre, "ma_free", None))
                p_tot, q_tot = p_base + rec_p, q_base + rec_q
                hay_base = (p_base or q_base)
                nota_inc = (
                    f"\n\n> ⚠ **La lista de arriba es un INCREMENTO, no un total.** "
                    f"Se ha identificado sobre los residuos de "
                    f"`{os.path.basename(pre_path)}`, que ya lleva "
                    f"**p={p_base}, q={q_base}**: lo que ves es lo que FALTA por "
                    f"modelar, no el modelo entero.\n>\n"
                    f"> Y `base_pre_path` **sustituye** el ARMA, no lo añade. Si "
                    f"pasas la sugerencia tal cual reestimas el mismo modelo. Los "
                    f"órdenes que hay que pasar son los **totales**: "
                    f"p={p_base}+{rec_p}=**{p_tot}**, q={q_base}+{rec_q}=**{q_tot}**.\n>\n"
                    f"> La suma es la regla práctica del ciclo iterativo, no una "
                    f"identidad: MA(1)∘MA(1) no es exactamente un MA(2). Estima y "
                    f"mira si el coeficiente nuevo se sostiene."
                ) if hay_base else ""
                next_call = (
                    f"Llama a `confirm_and_estimate` añadiendo el ARMA al modelo "
                    f"de `{os.path.basename(pre_path)}` — **encadenando por "
                    f"`base_pre_path`**, que hereda armónicos, intervenciones y "
                    f"media ya estimados en lugar de reconstruir desde cero:\n"
                    f"`inp_path=\"{pre_path}\", base_pre_path=\"{pre_path}\", "
                    f"output_path=..._mFinal.inp, "
                    f"lam={lam}, d={d}, D=0, p=<p>, q=<q>"
                    f", estimate_mu={'True' if _rec_mu else 'False'}`\n"
                    f"*(Sugerencia: p={p_tot}, q={q_tot}"
                    + (f" — incremento {rec_p},{rec_q} sobre la base {p_base},{q_base}"
                       if hay_base else "") + ")*"
                    + nota_inc
                )
            else:
                next_call = (
                    f"Llama a `confirm_and_estimate` con\n"
                    f"`lam={lam}, d={d}, D=0, p=<p>, q=<q>, n_harmonics={n_harm}"
                    f", estimate_mu={'True' if _rec_mu else 'False'}`\n"
                    f"*(Sugerencia: p={rec_p}, q={rec_q})*"
                )
            seasonal_note = mu_decision

        text = (
            f"## Paso 4 — Identificación ARMA  (sobre {data_label})\n\n"
            "**Regla ACF/PACF:**\n"
            "- PACF corta en lag p, ACF decae → **AR(p)**\n"
            "- ACF corta en lag q, PACF decae → **MA(q)**\n"
            "- Ambas decaen → **ARMA(p,q)**\n"
            "- Sin estructura → p=0, q=0\n"
            + seasonal_note + "\n\n"
            + ident.summary + "\n\n---\n" + ident.recommendation
            + "\n\n**Instrumentos de este nodo:** la similitud compara FORMAS "
              "de ACF/PACF y no discrimina cuando las dos cortan — si marca "
              "ambigüedad, estima los candidatos empatados y decide por AIC/BIC "
              "y diagnosis, no por el orden de la lista. Con un factor AR de "
              "orden ≥2, `ar_factorization` dice si esconde un ciclo o una "
              "frecuencia estacional."
            + "\n\n**Próximo paso:** " + next_call
        )
        items = [TextContent(type="text", text=text)]
        if ident.figure_b64:
            items.append(ImageContent(type="image",
                                      data=ident.figure_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Guion helper — called by confirm_and_estimate and record_version
# ---------------------------------------------------------------------------

def _state_footer(model, inp_path: str, guion_note: str = "",
                  guion_path_hint: str = "") -> str:
    """El pie de estado: dónde estamos, qué falta, y qué puertas hay desde aquí.

    Por qué existe (docs/ARCHITECTURE_REVIEW.md §5.2). El método es una búsqueda
    iterativa: cada paso es una decisión tomada mirando instrumentos, y una
    decisión mala contamina TODO lo que viene después. Un analista humano sabe
    dónde está porque ha estado ahí y tiene los gráficos en pantalla. Un
    asistente no: su única memoria es un contexto que se resume, y que sigue
    citando sus propias afirmaciones anteriores, incluidas las equivocadas.

    Por eso esto es un PIE y no una herramienta: una herramienta hay que
    descubrirla y acordarse de llamarla; un pie aparece se pregunte o no. Es la
    diferencia entre que la doctrina esté disponible y que esté presente.

    Y por eso es CORTO. Documentar no debe engordar cada respuesta: cinco líneas,
    todas derivadas de lo que ya se calculó, ninguna cifra nueva.

    La línea que más trabajo hace es `etapa`. Los contrastes formales —MEG,
    Shin-Fuller, DCD— derivan sus nulas suponiendo residuos de ruido blanco, así
    que son la ÚLTIMA etapa. Mientras la diagnosis falle no son una puerta, y el
    pie no los ofrece: no basta con avisar después (BUG-0025), hay que no
    invitar antes.
    """
    import os as _os
    from art.diagnosis import diagnose as _diagnose

    try:
        diag_result = _diagnose(model)
    except Exception:
        return ""          # el pie nunca puede tumbar una salida válida

    # ── qué está decidido ────────────────────────────────────────────────
    lam = float(getattr(model, "boxlam", 0.0) or 0.0)
    piezas = ["log" if lam == 0.0 else (f"λ={lam:g}")]
    piezas.append(f"d={int(getattr(model, 'd', 0) or 0)}")
    D = int(getattr(model, "D", 0) or 0)
    if D:
        piezas.append(f"D={D}")
    ifadf = [i for i, v in enumerate(getattr(model, "ifadf", None) or []) if v]
    if ifadf:
        piezas.append("ifadf f=" + ",".join(str(i) for i in ifadf))
    itvs = list(getattr(model, "interventions", None) or [])
    n_arm = sum(1 for i in itvs if i.type in ("cos", "sin", "alter"))
    if n_arm:
        piezas.append(f"{n_arm} armónicos")
    def _orden(coefs, libres):
        """Cuenta coeficientes LIBRES, no presentes: fue guarda factores con
        ceros fijos que no son parámetros del modelo."""
        coefs = coefs or []
        libres = libres or []
        n = 0
        for k, f in enumerate(coefs):
            fl = libres[k] if k < len(libres) else [True] * len(f)
            n += sum(1 for j in range(len(f)) if (fl[j] if j < len(fl) else True))
        return n

    p_ord = _orden(getattr(model, "ar", None),   getattr(model, "ar_free", None))
    q_ord = _orden(getattr(model, "ma", None),   getattr(model, "ma_free", None))
    P_ord = _orden(getattr(model, "ar_s", None), getattr(model, "ar_s_free", None))
    Q_ord = _orden(getattr(model, "ma_s", None), getattr(model, "ma_s_free", None))
    if p_ord or q_ord:
        piezas.append(f"ARMA({p_ord},{q_ord})")
    if P_ord or Q_ord:
        piezas.append(f"estacional({P_ord},{Q_ord})")
    if getattr(model, "estimate_mu", False):
        piezas.append("μ")
    n_itv = len(itvs) - n_arm
    if n_itv > 0:
        piezas.append(f"{n_itv} intervención{'es' if n_itv > 1 else ''}")

    # ── qué falta ────────────────────────────────────────────────────────
    # BUG-0042: esta lista era un TERCER predicado de adecuación, distinto de
    # `DiagnosisResult.residuals_ok` (que publica el veredicto) y de la guarda de
    # `formal_tests` (que BUG-0036 unificó con el primero). Miraba Q, JB y
    # extremos, y NO la media residual ni la estacionalidad. Resultado: el pie
    # decía "nada — diagnosis limpia" y "etapa: contrastes formales" sobre
    # modelos cuyo veredicto era REVISAR ✗ y a los que `formal_tests` bloqueaba.
    #
    # Medido sobre la réplica: ITCER con media residual t=−2.17 y RATIO con
    # estacionalidad residual — los dos con el pie diciendo que estaba limpio.
    # BUG-0036 unificó dos de los tres predicados y éste se quedó fuera.
    #
    # Ahora la lista se construye de los MISMOS componentes que `.clean`, que es
    # el predicado que dicta el veredicto. Los extremos siguen apareciendo porque
    # son la información que gobierna el bucle de intervenciones, pero NO cuentan
    # para "limpio" — igual que en `residuals_ok`, y por la misma razón: una
    # intervención arregla un residuo que se porta mal, no una media que falta.
    q_ok  = bool(diag_result.white_noise)
    jb_ok = bool(diag_result.normal)
    centrado = bool(diag_result.centred)
    _seas = getattr(diag_result, "seasonal", None)
    seas_ok = not (_seas is not None and getattr(_seas, "seasonal_detected", False))
    n_ext = len(diag_result.extreme or [])
    falta = []
    if not q_ok:
        peor = min(diag_result.q_pvalues)
        falta.append(f"ruido blanco (Q p={peor:.4f})")
    if not jb_ok:
        falta.append(f"normalidad (JB p={diag_result.jb_pvalue:.4f})")
    if not centrado:
        falta.append(f"media residual (t={diag_result.mean_t:+.2f})")
    if not seas_ok:
        falta.append(f"estacionalidad residual "
                     f"(p={getattr(_seas, 'p_value', float('nan')):.4f})")
    # Los extremos van APARTE. Nombrarlos junto a lo que falta los convertía en
    # un bloqueo que no son: un modelo puede estar limpio y arrastrar un residuo
    # grande, y el pie decía a la vez "falta: 1 anómalo" y "etapa: contrastes
    # formales". Misma separación que BUG-0036 hizo en `formal_tests` — fallos
    # que bloquean, avisos que se nombran.
    nota = ""
    if n_ext:
        pe = max(diag_result.extreme, key=lambda t: abs(t[1]))
        nota = f"{n_ext} anómalo{'s' if n_ext > 1 else ''} (obs {pe[0]}, z={pe[1]:+.2f})"

    limpio = q_ok and jb_ok and centrado and seas_ok
    base = _os.path.splitext(inp_path)[0]

    # ── etapa y puertas ──────────────────────────────────────────────────
    if limpio:
        etapa = "contrastes formales — la diagnosis está limpia, es su etapa"
        puertas = ["formal_tests"]
        if n_itv:
            puertas.append("test_interventions")
        if (p_ord + q_ord + P_ord + Q_ord) >= 2:
            puertas.append("overparameterization_analysis")
    else:
        etapa = ("diagnosis / reformulación — los contrastes formales van DESPUÉS "
                 "y suponen residuos de ruido blanco")
        puertas = []
        if n_ext:
            # el escaneo sobre RESIDUOS, no sobre la serie (BUG-0028)
            puertas.append("residual_outlier_scan")
            puertas.append("suggest_intervention_form(date=..., form=\"auto\")")
        elif not jb_ok:
            puertas.append("suggest_intervention_form(date=..., form=\"auto\")")
        if not q_ok:
            puertas.append("guided_identification(pre_path=…pre)")
        if not jb_ok:
            puertas.append("model_histogram")
    # Un factor AR de orden >=2 puede esconder un ciclo -- o una frecuencia
    # estacional. Sólo se ve factorizando, y nada dirigía ahí.
    if any(len(f) >= 2 for f in (getattr(model, "ar", None) or [])):
        puertas.append("ar_factorization")
    puertas.append("get_out_report")
    # El mapa del laberinto: en cuanto hay más de una versión, poder verlo es
    # parte de poder volver. Construirlo y no mencionarlo lo dejaría huérfano,
    # que es lo que le pasa a todo lo que nada menciona.
    mapa = guion_path_hint

    ver = guion_note.replace("*guion:", "").replace("*", "").strip() or "sin registrar"
    serie = getattr(getattr(model, "series", None), "name", None) or "?"

    return (
        "\n\n── Estado ──  " + f"{serie} · {ver}"
        + "\n   decidido: " + " · ".join(piezas)
        # El anómalo se NOMBRA pero no ocupa línea propia: el pie tiene que
        # seguir cabiendo en cinco o seis líneas —crece en cada llamada— y una
        # nota que no bloquea no merece un renglón. Va entre paréntesis, detrás
        # de lo que sí falta o de su ausencia.
        + "\n   falta   : "
        + (" · ".join(falta) if falta else "nada — diagnosis limpia")
        + (f"  (nota: {nota})" if nota else "")
        + "\n   etapa   : " + etapa
        + "\n   puertas : " + " · ".join(puertas)
        + f"  ← sobre \"{base}.inp\""
        + (f"\n   mapa    : guion_map(\"{mapa}\")" if mapa else "")
    )


def _nota_objetivo(objetivo: str) -> str:
    """Qué implica el OBJETIVO del modelo para la ruta estacional.

    La elección entre B1 y B2 no está entera en los datos: los dos caminos son
    contrastables —el MEG sobre B1, el DCD_s sobre el MA estacional de B2— pero
    cuando los contrastes no deciden, decide para qué es el modelo. Y eso el dato
    no lo sabe.

    Se dice AQUÍ, en el nodo, y no en la documentación de un parámetro: es el
    momento en que la decisión se toma.
    """
    obj = (objetivo or "univariante").strip().lower()
    if obj == "multivariante":
        return (
            "\n\n> **Objetivo declarado: MULTIVARIANTE.** Con la serie destinada a "
            "un sistema —VECM, función de transferencia— la ruta **B1** no es una "
            "preferencia sino un requisito, y por dos razones distintas. Una: una "
            "raíz unitaria estacional dentro de una cointegración es otro "
            "problema, y bastante más duro. Dos, y es la que no admite "
            "negociación: **todas las series del sistema tienen que llevar el "
            "MISMO tratamiento estacional**, o sus órdenes de integración no son "
            "comparables y el sistema está mal planteado.\n>\n"
            "> Puede costarte ajuste univariante. Si es así, **dilo**: renunciar "
            "a un modelo mejor por una razón de uso es una decisión, y una "
            "decisión que no se anuncia no se puede discutir después."
        )
    if obj == "estructural":
        return (
            "\n\n> **Objetivo declarado: ESTRUCTURAL.** Se quiere leer los "
            "componentes, así que B1 los deja explícitos —un armónico por "
            "frecuencia, con su amplitud— mientras B2 los absorbe en una "
            "diferencia. Si el MEG dictamina estocástica alguna frecuencia, "
            "hazle caso igualmente: un componente legible pero falso no sirve."
        )
    return (
        "\n\n> **Objetivo: univariante** (por defecto). Nada fuerza la ruta: "
        "decide el par de contrastes —el MEG sobre B1, la no invertibilidad del "
        "MA estacional sobre B2— y, si no deciden, la parsimonia. Si esta serie "
        "va a entrar en un sistema multivariante, dilo con "
        "`objetivo=\"multivariante\"`: ahí la ruta deja de ser libre."
    )


def _sin_estacionalidad_next(inp_path: str, lam: float, d: int) -> str:
    """Qué toca cuando la decisión es A — y sólo eso (BUG-0043).

    Antes esta rama recibía las recetas de B1 y B2 igual que si hubiera
    estacionalidad, después de haber concluido que no la hay.
    """
    return (
        "\n\n### Siguiente paso — no hay estacionalidad que enrutar\n\n"
        "Decisión A: `D=0`, sin armónicos cos/sin. No hay ruta B1/B2 que elegir, "
        "así que se pasa directamente a la identificación ARMA:\n\n"
        "```\n"
        f"guided_identification(\n"
        f"    inp_path=\"{inp_path}\",\n"
        f"    lam={lam}, d={d}, D=0\n"
        ")\n```\n\n"
        "Y si quieres calibrar los anómalos antes de identificar —que es "
        "opcional y lo decide el analista— estima primero el modelo base con "
        "`confirm_and_estimate(..., p=0, q=0, n_harmonics=0, seasonal=False)` y "
        "mira el escaneo que trae su salida."
    )


def _param_labels_safe(model) -> list:
    """Etiquetas de los parámetros, o lista vacía si la diagnosis falla."""
    try:
        from art.diagnosis import diagnose
        return list(diagnose(model).param_labels or [])
    except Exception:
        return []


def _derive_guion_path(output_path: str, model) -> str:
    """Dónde vive el guion de esta serie, sin que nadie tenga que decirlo.

    El guion es OBLIGATORIO: documentar el proceso no es un adorno del método,
    es el método. Pero exigir que el llamante pase la ruta lo convierte en
    opcional de hecho — y lo que es opcional no se hace. Así que se deriva.

    Se prefiere un `guion.json` ya existente en el directorio (los que hay
    escritos siguen valiendo); si no, se nombra por la serie, que es lo único
    que no colisiona cuando varias comparten directorio de trabajo.
    """
    d = os.path.dirname(os.path.abspath(os.path.expanduser(output_path))) or "."
    viejo = os.path.join(d, "guion.json")
    if os.path.exists(viejo):
        return viejo
    serie = (getattr(getattr(model, "series", None), "name", None)
             or os.path.splitext(os.path.basename(output_path))[0])
    return os.path.join(d, f"{serie}_guion.json")


def _record_spec_nodes(result, overrides: dict, gpath: str) -> None:
    """Deja en el guion los nodos de ESPECIFICACIÓN que `run_full` decidió.

    Sin esto el guion empieza a contar la historia tarde: la primera entrada es
    ya un modelo estimado, y para entonces λ, d, la estacionalidad y los órdenes
    están decididos y sin rastro. Sobre PGAS de la réplica la divergencia entera
    entre carriles es λ — decidida antes del primer modelo.

    `decidido_por` sale de quién puso cada valor: lo que venga en `overrides` lo
    confirmó el analista (o el LLM en su nombre); lo demás lo decidió la
    heurística. Es el campo que hace comparables dos guiones: el recorrido es el
    mismo y los nodos son los mismos, y lo único que cambia es el decisor.
    """
    from art.guion import (Guion, GuionEntry, load_guion, save_guion, infer_parent)
    from datetime import datetime

    def quien(clave):
        return "analista+LLM" if clave in overrides else "heurística"

    bc = result.boxcox_data or {}
    seas = result.seasonality_data or {}
    sim = (f"similitud={result.orders_specs[0].similarity:.3f}"
           if result.orders_specs else "")
    orden_txt = f"ARMA({result.p},{result.q})"
    if getattr(result, "P", 0) or getattr(result, "Q", 0):
        orden_txt += f"×({result.P},{result.Q})_s"

    nodos = [
        ("dominio", result.domain, quien("domain"),
         "", "la CLASE de serie, que gobierna la regla de λ"),
        ("lambda", f"{result.lam:g}", quien("lam"),
         f"gap={bc.get('gap', float('nan')):+.3f}",
         "log si la dispersión crece con el nivel; identidad si no"),
        ("estacionalidad",
         f"{result.decision} · D={result.D} · {result.n_harmonics} armónico(s)",
         quien("D") if "D" in overrides else quien("decision"),
         (f"F-HAC={seas['f_hac']:.2f}" if isinstance(seas.get("f_hac"), (int, float)) else ""),
         "A sin estacionalidad; B1 determinista; B2 estocástica"),
        ("d", str(result.d), quien("d"), "",
         "orden de diferenciación regular"),
        ("ordenes", orden_txt, quien("p") if "p" in overrides else quien("q"),
         sim, "el spec en cabeza del ranking de correlograma"),
        ("media", "estimada" if result.estimate_mu else "fijada en 0",
         quien("estimate_mu"), "", "μ libre si la serie diferenciada deriva"),
    ]

    gp = os.path.expanduser(gpath)
    os.makedirs(os.path.dirname(gp) or ".", exist_ok=True)
    if os.path.exists(gp):
        g = load_guion(gp)
    else:
        serie = os.path.basename(gp).replace("_guion.json", "").replace("guion.json", "")
        g = Guion(series=serie or "serie", analyst="",
                  created=datetime.now().strftime("%Y-%m-%d"))

    for nombre, valor, por, evid, razon in nodos:
        version = (max(e.version for e in g.entries) + 1) if g.entries else 1
        g.entries.append(GuionEntry(
            version=version, name=nombre, inp_path="",
            timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            spec={}, stats=None, equation="",
            decision=f"{nombre} = {valor}", rationale=razon,
            problems_found="", next_version="",
            parent=infer_parent(g), kind="node",
            node={"nodo": nombre, "decidido": str(valor),
                  "evidencia": evid, "alternativas": ""},
            decided_by=por,
        ))
    save_guion(g, gp)


def _round_decision_text(rd) -> str:
    """Qué hizo esta ronda del bucle autónomo, en una línea para el guion.

    BUG-0032. Lo que da valor a una ronda intermedia no es el modelo —que se
    descarta— sino la RAZÓN por la que se pasó a la siguiente. Sin ella el mapa
    tiene nodos pero no aristas, y un nodo sin arista no dice por dónde se fue.
    """
    if getattr(rd, "stop_reason", "") == "clean":
        return (f"Ronda {rd.round_num}: la diagnosis sale limpia; el bucle para "
                f"y este es el modelo final.")
    if getattr(rd, "stop_reason", "") == "no_new":
        n = len(rd.diag.extreme) if rd.diag is not None else 0
        return (f"Ronda {rd.round_num}: quedan {n} extremo(s) pero ninguno NUEVO "
                f"que añadir; el bucle para sin diagnosis limpia.")
    if getattr(rd, "added", None):
        etq = ", ".join(f"{f.upper()} obs {at + 1}" for at, f in rd.added[:5])
        return (f"Ronda {rd.round_num}: la diagnosis marca "
                f"{len(rd.diag.extreme)} extremo(s) → se añade {etq}.")
    return f"Ronda {rd.round_num}."


def _round_problems_text(rd) -> str:
    """Lo que la diagnosis de esta ronda encontró — BUG-0032."""
    dg = getattr(rd, "diag", None)
    if dg is None:
        return ""
    partes = []
    fallos = [str(l) for l, pv in zip(dg.q_lags, dg.q_pvalues) if pv < 0.05]
    if fallos:
        partes.append(f"Q rechaza en los retardos {', '.join(fallos)} "
                      f"(p-mín={min(dg.q_pvalues):.4f})")
    if not dg.normal:
        partes.append(f"JB={dg.jb_stat:.1f} (p={dg.jb_pvalue:.4f})")
    if dg.extreme:
        partes.append("extremos: " + ", ".join(
            f"obs {o} (z={z:+.2f})" for o, z in dg.extreme[:4]))
    return " · ".join(partes)


def _record_to_guion(
    model,
    inp_path: str,
    lam: float,
    guion_path: str,
    name: str = "",
    decision: str = "",
    rationale: str = "",
    problems_found: str = "",
    next_version: str = "",
    figure_b64: str | None = None,
    base_pre_path: str = "",
) -> str:
    """
    Add a fitted model entry to guion.json (creates file if absent).
    Returns a one-line confirmation string for the caller.
    """
    from datetime import datetime
    from art.guion import (
        Guion, GuionEntry, load_guion, save_guion, infer_parent,
        _extract_spec, _extract_stats, _build_equation,
    )
    from art.diagnosis import diagnose

    guion_path = os.path.expanduser(guion_path)

    if os.path.exists(guion_path):
        guion = load_guion(guion_path)
    else:
        ts = model.series
        guion = Guion(
            series=ts.name or os.path.basename(inp_path),
            analyst="",
            created=datetime.now().strftime("%Y-%m-%d"),
        )

    version = (max(e.version for e in guion.entries) + 1) if guion.entries else 1
    if not name:
        name = f"PC{version}"
    # De qué versión desciende ésta. Encadenar desde un `.pre` antiguo ES volver
    # atrás, y hay que registrarlo como tal (guion.infer_parent).
    parent = infer_parent(guion, base_pre_path)

    diag_result = diagnose(model)
    spec  = _extract_spec(model, lam)
    stats = _extract_stats(model, diag_result)
    eq    = _build_equation(spec, model.series.freq)

    entry = GuionEntry(
        version=version,
        name=name,
        inp_path=inp_path,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        spec=spec,
        stats=stats,
        equation=eq,
        decision=decision,
        rationale=rationale,
        problems_found=problems_found,
        next_version=next_version,
        figure_b64=figure_b64,
        parent=parent,
    )
    # BUG-0043: la figura va a un fichero hermano, no dentro del guion.
    if entry.figure_b64:
        try:
            import base64 as _b64
            figs = os.path.join(os.path.dirname(guion_path) or ".", "figs")
            os.makedirs(figs, exist_ok=True)
            nombre = f"{guion.series or 'serie'}_v{entry.version}.png"
            with open(os.path.join(figs, nombre), "wb") as fh:
                fh.write(_b64.b64decode(entry.figure_b64))
            entry.figure_path = os.path.join("figs", nombre)
            entry.figure_b64 = None
        except Exception as e:
            _warn("no se pudo escribir la figura del guion; se deja empotrada", e)

    guion.entries.append(entry)
    save_guion(guion, guion_path)
    # Una línea, y corta: el registro es interno y la salida no debe crecer por
    # documentar. Quien quiera ver lo documentado llama a `export_guion`.
    padre = f" ← v{parent}" if parent is not None else ""
    return f"*guion: {name} v{version}{padre}*"


# ---------------------------------------------------------------------------
# Tool: confirm and estimate (B2)
# ---------------------------------------------------------------------------

@mcp.tool()
def confirm_and_estimate(inp_path: str, output_path: str,
                          lam: float = 0.0, d: int = 1, D: int = 0,
                          p: int = 0, q: int = 1,
                          n_harmonics: int = 5,
                          P: int = 0, Q: int = 0,
                          base_pre_path: str = "",
                          estimate_mu: bool = False,
                          seasonal: bool | None = None,
                          include_histogram: bool = False,
                          guion_path: str = "",
                          guion_name: str = "",
                          guion_decision: str = "",
                          guion_rationale: str = "",
                          guion_problems: str = "",
                          guion_next: str = "") -> list:
    """
    Build the .inp for the confirmed spec, estimate and show diagnosis immediately.

    Two modes:
    - Fresh model (base_pre_path=""): constructs from scratch using series in
      inp_path and the analyst-confirmed (lam, d, D, p, q, P, Q) spec.
    - Incremental (base_pre_path=<.pre>): loads all existing interventions and
      harmonics from the .pre, then replaces/adds only the ARMA part (p, q,
      P, Q) and mu. Use this to add ARMA to a model after the outlier cycle.

    Always returns:
      - Parameter table with SE and t-stats
      - Diagnosis verdict (Q-test, JB, outliers)
      - Residual ACF/PACF + histogram

    Parameters
    ----------
    inp_path        : source .inp/.pre (series data and name; spec ignored
                      unless base_pre_path is given)
    output_path     : path to write the new .inp
    lam             : Box-Cox lambda (0.0=log, 1.0=identity)
    d               : regular differencing order
    D               : seasonal differencing order (0=B1 harmonics, 1=B2 multiplicative)
    p               : regular AR order
    q               : regular MA order
    n_harmonics     : harmonic pairs cos/sin (D=0 fresh only; ignored when
                      base_pre_path is given — harmonics come from the .pre)
    seasonal        : on/off switch for the whole deterministic seasonal package
                      (cos/sin pairs + Nyquist alter). None (default) => derive from
                      n_harmonics>0, correct for freq>=4. Pass False for a
                      NON-seasonal series (no seasonal terms at all — avoids the
                      spurious Nyquist of BUG-0005). Pass True for a SEMI-ANNUAL
                      seasonal series (freq=2), whose only seasonal term is the
                      Nyquist alter while n_harmonics (pairs) is 0.
    P               : seasonal AR order. Works with D=0 TOO, and that is not a
                      corner case: a stationary stochastic seasonality riding on
                      top of the deterministic harmonics is the B1 route's own
                      way of absorbing what the harmonics leave behind. Both
                      RATIO finals of this project are exactly that — P=1 with
                      D=0 — and `_make_model` has built it all along
                      (pipeline.py, "Stationary stochastic seasonality on top of
                      the deterministic harmonics").
                      BUG-0050: this line used to read "(D=1 only)". It was
                      false, and expensively so: an analyst who believes it
                      concludes that a residual seasonal AR forces D=1, i.e.
                      route B2 — the one route `objetivo="multivariante"`
                      forbids. The documentation sent you to the forbidden route
                      to solve a problem the allowed route solves.
    Q               : seasonal MA order — same as P, D=0 included. NOTE: the
                      fixed-frequency operators (`ar_f`/`ma_f`, where the MEG's
                      MA_f witness lives) are NOT controlled by Q — they are
                      inherited from base_pre_path as structure, together with
                      `ifadf` (BUG-0034).
    base_pre_path   : if given, load interventions+harmonics from this .pre and
                      add only the ARMA spec. Typical use: final ARMA step after
                      outlier cycle in B1 flow.
    estimate_mu     : include mean parameter μ in estimation (default False).
                      Set True when the DRIFT of the differenced series has
                      |t| > 2 -- not the mean of residuals of a model that
                      already fitted a mu, which reads ~0 by construction
                      (BUG-0013). When base_pre_path carries a fitted mean it is
                      inherited, so pass True to keep it.
    include_histogram : return histogram PNG as third item (default False).
                      Keep False during the outlier cycle to save tokens; set True
                      for the final model only.
    guion_path      : (optional) path to guion.json — records this version
    guion_name      : version name (e.g. "PC3"); auto-assigned if empty
    guion_decision  : brief description of what this model tests or concludes
    objetivo        : what the model is FOR — "univariante" (forecasting the
                      series itself), "multivariante" (it enters a system: VECM,
                      transfer function) or "estructural" (read the components).

                      It is the one thing the data cannot supply, and it is asked
                      as a PURPOSE rather than as a method so that one answer
                      informs several nodes. It matters most at the seasonal
                      route: with seasonality detected the pipeline estimates
                      BOTH B1 (D=0 + harmonics) and B2 (D=1) and adjudicates them
                      with the MEG/DCD_f pair; `objetivo` breaks the tie when the
                      tests do not decide, and VETOES B2 under "multivariante" —
                      seasonal unit roots complicate cointegration and every
                      series of a system must carry the same seasonal treatment
                      or their integration orders are not comparable.
    guion_rationale : justification for the choices made
    guion_problems  : problems found in the diagnosis of this model
    guion_next      : description of the next version to try
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        import fue

        ts, _ = _load_ts_model(inp_path)
        output_path = os.path.expanduser(output_path)

        if base_pre_path:
            # Incremental: preserve interventions + harmonics from .pre; replace ARMA
            base_pre_path = os.path.expanduser(base_pre_path)
            _, m_base = _load_ts_model(base_pre_path)
            ts_b = m_base.series
            if ts.nobs != ts_b.nobs or ts.freq != ts_b.freq:
                raise ValueError(
                    f"Series mismatch between inp_path and base_pre_path: "
                    f"nobs {ts.nobs} vs {ts_b.nobs}, freq {ts.freq} vs {ts_b.freq}"
                )
            m = _build_arma_on_model(m_base, p=p, q=q, P=P, Q=Q,
                                     estimate_mu=estimate_mu)
            _write_inp(ts, m, output_path)
        else:
            m_fresh = _make_model(ts, lam=lam, d=d, D=D, p=p, q=q,
                                  n_harmonics=n_harmonics, P=P, Q=Q,
                                  estimate_mu=estimate_mu, seasonal=seasonal)
            _write_inp(ts, m_fresh, output_path)

        _, m = _load_fitted(output_path)

        # Parameter table
        if base_pre_path:
            n_itvs = len(m.interventions) if m.interventions else 0
            spec_str = (f"ARIMA({p},{d},{q}) + {n_itvs} interv. "
                        f"[desde {os.path.basename(base_pre_path)}]")
        elif D == 1 and (P > 0 or Q > 0):
            spec_str = f"SARIMA({p},{d},{q})({P},{D},{Q})_{ts.freq}"
        elif D == 1:
            spec_str = f"ARIMA({p},{d},{q}) D=1"
        else:
            spec_str = f"ARIMA({p},{d},{q}) armónicos={n_harmonics}"
        spec_line = f"**{spec_str}  λ={lam}**  —  {ts.name or 'series'}"

        # Model equation replaces the parameter table
        try:
            eq_text = _equation_for_prompt(ts, m)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"

        # Diagnosis
        diag = describe_diagnosis(m)

        # Mirror fue's estimate→outputs convention: a .pre (=.inp with the
        # estimated parameters as initial values, so the next step starts from
        # this optimum) and a .out (the ASCII results report).
        base     = os.path.splitext(output_path)[0]
        pre_path = base + ".pre"
        out_path = base + ".out"
        try:
            m.write_pre(pre_path)
            try:
                m.write_out(out_path)
                # BUG-0029: decir que el .out existe no basta — nadie lo abría.
                # Es el registro que hace SÓLIDO un paso: parámetros con sus
                # errores típicos, sigma, verosimilitud, covarianza y
                # correlación. Y es de donde se leen, nunca de reejecutar el
                # .pre (BUG-0027). Se nombra la herramienta que lo lee.
                pre_note = (f"\n\n*Modelo guardado en: {output_path}  |  "
                            f"semilla del siguiente paso: {pre_path}*"
                            f"\n\n*Parámetros, errores típicos y covarianza en "
                            f"`{out_path}` — se leen con "
                            f"`get_out_report(\"{output_path}\")`, no reestimando "
                            f"el `.pre`.*")
            except Exception:
                pre_note = (f"\n\n*Modelo guardado en: {output_path}  |  "
                            f"parámetros: {pre_path}*")
        except Exception:
            pre_note = f"\n\n*Modelo guardado en: {output_path}*"

        # El guion NO es opcional. Documentar el proceso es el principio del
        # que depende poder volver atrás: sin registro de qué se decidió, por
        # qué, y de qué versión desciende, una iteración fallida no deja más
        # rastro que la memoria de quien la hizo — y en un asistente esa memoria
        # se resume y desaparece. Si el llamante no da ruta, se deriva.
        guion_note = ""
        try:
            guion_note = _record_to_guion(
                model=m, inp_path=output_path, lam=lam,
                guion_path=guion_path or _derive_guion_path(output_path, m),
                name=guion_name, decision=guion_decision,
                rationale=guion_rationale, problems_found=guion_problems,
                next_version=guion_next,
                figure_b64=diag.figure_b64,
                base_pre_path=base_pre_path,
            )
        except Exception as e:
            # Documentar no puede tumbar una estimación válida.
            guion_note = f"*guion: no registrado ({type(e).__name__})*"

        scan_section, scan_b64 = _auto_scan_section(
            ts, m, lam=lam, d=d, D=D, p=p, q=q, P=P, Q=Q,
            inp_path=inp_path, pre_path=pre_path,
        )

        text = (
            spec_line + "\n\n"
            + eq_text
            + "\n\n---\n\n"
            + diag.summary + "\n\n---\n" + diag.recommendation
            + scan_section
            + pre_note
            + (f"\n\n{guion_note}" if guion_note else "")
            + _state_footer(m, inp_path=output_path, guion_note=guion_note,
                            guion_path_hint=guion_path or _derive_guion_path(output_path, m))
        )

        _show_fig(diag.figure_b64, "diagnosis")
        items = [TextContent(type="text", text=text)]
        if diag.figure_b64:
            items.append(ImageContent(type="image",
                                      data=diag.figure_b64, mimeType="image/png"))
        if scan_b64:
            items.append(ImageContent(type="image",
                                      data=scan_b64, mimeType="image/png"))
        if include_histogram:
            hist_b64 = diag.data.get("hist_b64")
            if hist_b64:
                items.append(ImageContent(type="image",
                                          data=hist_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: record_version — add fitted model to guion.json  (Bloque P)
# ---------------------------------------------------------------------------

@mcp.tool()
def record_version(inp_path: str,
                   guion_path: str,
                   name: str = "",
                   decision: str = "",
                   rationale: str = "",
                   problems_found: str = "",
                   next_version: str = "") -> list:
    """
    Load, fit and record a model version in guion.json.

    Loads the model from inp_path, fits it, extracts stats (loglik, AIC, BIC,
    Q-test, JB-test, extreme residuals) and appends an entry to guion.json.
    Creates guion.json if it does not exist.

    Parameters
    ----------
    inp_path       : .inp file with the estimated model
    guion_path     : path to guion.json (created if absent)
    name           : version name, e.g. "PC3"; auto-assigned ("PC{n}") if empty
    decision       : brief note on what this model tests or concludes
    rationale      : justification for the parameter choices
    problems_found : problems detected in the diagnosis
    next_version   : description of the next version to try
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import _fig_b64
        from art.diagnosis import diagnose, plot_diagnosis
        import matplotlib.pyplot as plt

        _, m = _load_fitted(inp_path)

        # Diagnosis figure
        diag_result = diagnose(m)
        try:
            fig = plot_diagnosis(diag_result, m)
            b64 = _fig_b64(fig)
            plt.close(fig)
        except Exception as e:
            _warn("diagnosis figure failed", e)
            b64 = None

        lam = float(getattr(m, "boxlam", 0.0) or 0.0)

        note = _record_to_guion(
            model=m, inp_path=inp_path, lam=lam,
            guion_path=guion_path, name=name,
            decision=decision, rationale=rationale,
            problems_found=problems_found, next_version=next_version,
            figure_b64=b64,
        )

        lines = [
            f"### Versión registrada en guion",
            note,
            "",
            f"**loglik** = {m._result.loglik:.3f}",
            f"**AIC** = {m._result.aic:.2f}" if m._result.aic else "",
            f"**Q-pass** = {diag_result.white_noise} | **JB-pass** = {diag_result.normal}",
            f"**Anomalías** = {len(diag_result.extreme)}",
        ]
        items = [TextContent(type="text", text="\n".join(l for l in lines if l))]
        if b64:
            items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: export_guion — render guion.json to HTML  (Bloque P)
# ---------------------------------------------------------------------------

@mcp.tool()
def guion_map(guion_path: str, version: int = 0, detalle: bool = False) -> list:
    """
    Show the analysis as a MAP: what descends from what, what was adopted, and
    which branches were dead ends — with the reason each was abandoned.

    This is the labyrinth view. The iterative method is a search with
    backtracking: it has dead ends, and a dead end is the method working, not
    failing. What a failed iteration produces of value is not the model that is
    discarded — it is the REASON, which is the only thing that stops the branch
    being tried again.

    With `version`, also shows the chain of decisions that led to it (its path
    from the root) and the nearest safe place to return to.

    Parameters
    ----------
    guion_path : path to guion.json
    version    : version to locate in the map (0 = just draw the whole map)
    detalle    : False (default) recorta los textos largos; True los da enteros.

    BUG-0064: el mapa volcaba `decidido`, `evidencia`, `razón`, `descartado` y
    `callejón` SIN LÍMITE, uno por línea. Con nodos bien razonados eso son ~945
    bytes por línea: el RATIO del RUN 3 salía en 52.921 bytes y se truncaba a
    fichero — justo la serie con más ramas, o sea donde más información había que
    ver. La intención estaba escrita en `_record_to_guion`: «el registro es
    interno y la salida no debe crecer por documentar. Quien quiera ver lo
    documentado llama a `export_guion`». El mapa es un MAPA.
    """
    try:
        from mcp.types import TextContent
        from art.guion import load_guion, path_to_root, safe_ancestor, descendants
        g = load_guion(os.path.expanduser(guion_path))
        if not g.entries:
            return [TextContent(type="text", text="Guion vacío.")]

        por_v = {e.version: e for e in g.entries}
        hijos: dict[int | None, list[int]] = {}
        for e in g.entries:
            hijos.setdefault(e.parent, []).append(e.version)

        # BUG-0064: el mapa orienta; `export_guion` documenta. Se corta por
        # palabra para no partir una cifra por la mitad, y se lleva la cuenta de
        # lo recortado para poder decirlo al final en vez de callarlo.
        _cortes = [0]

        def _rec(txt, n: int = 150) -> str:
            t = " ".join(str(txt or "").split())
            if detalle or len(t) <= n:
                return t
            corte = t[:n]
            esp = corte.rfind(" ")
            if esp > n * 0.6:
                corte = corte[:esp]
            _cortes[0] += 1
            return corte.rstrip(" ,.;:") + " […]"

        MARCA = {"adopted": "✓", "dead-end": "✗", "exploring": "·"}
        lines = [f"## Mapa del análisis — {g.series}", ""]

        def dibuja(v: int, sangria: str, ultimo: bool):
            e = por_v[v]
            rama = "└─ " if ultimo else "├─ "
            st = MARCA.get(e.status, "·")
            if getattr(e, "kind", "model") == "node" or e.stats is None:
                # Un nodo de decisión no tiene diagnosis que enseñar: lo que
                # tiene es QUÉ se decidió, sobre qué evidencia y quién lo
                # decidió. Se dibuja en la misma cadena porque el orden importa:
                # un nodo DESPUÉS de un modelo es una reformulación.
                nd = e.node or {}
                quien = f" [{e.decided_by}]" if e.decided_by else ""
                lines.append(f"{sangria}{rama}◆ n{e.version} {nd.get('nodo', e.name)}"
                             f" = {_rec(nd.get('decidido', ''), 190)}{quien}")
                if nd.get("evidencia"):
                    lines.append(f"{sangria}{'   ' if ultimo else '│  '}   "
                                 f"evidencia: {_rec(nd['evidencia'])}")
                if e.rationale:
                    lines.append(f"{sangria}{'   ' if ultimo else '│  '}   "
                                 f"razón: {_rec(e.rationale)}")
                if nd.get("alternativas"):
                    lines.append(f"{sangria}{'   ' if ultimo else '│  '}   "
                                 f"descartado: {_rec(nd['alternativas'])}")
            else:
                q = "Q✓" if e.stats.q_pass else ("Q✗" if e.stats.q_pass is not None else "Q?")
                jb = "JB✓" if e.stats.jb_pass else ("JB✗" if e.stats.jb_pass is not None else "JB?")
                lines.append(f"{sangria}{rama}{st} v{e.version} {e.name}  "
                             f"logL={e.stats.loglik:.2f}  {q} {jb}"
                             + (f"  ← {e.decision}" if e.decision else ""))
            if e.status == "dead-end" and e.why_abandoned:
                lines.append(f"{sangria}{'   ' if ultimo else '│  '}   "
                             f"↳ callejón: {_rec(e.why_abandoned)}")
            kids = sorted(hijos.get(v, []))
            for i, k in enumerate(kids):
                dibuja(k, sangria + ("   " if ultimo else "│  "), i == len(kids) - 1)

        raices = sorted(hijos.get(None, []))
        for i, r in enumerate(raices):
            dibuja(r, "", i == len(raices) - 1)

        lines += ["", "◆ nodo de decisión · ✓ adoptada · ✗ callejón sin salida · · en exploración"]
        if _cortes[0]:
            lines.append(
                f"⋯ {_cortes[0]} textos recortados para que el mapa quepa. "
                f"Enteros: `guion_map(..., detalle=True)` o `export_guion` "
                f"(que además los deja en HTML navegable).")
        # Un mapa que no dice qué se puede hacer con él es un dibujo. Las dos
        # operaciones del laberinto viven aquí, y sin nombrarlas quedarían
        # huérfanas — que es lo que le pasa a todo lo que nada menciona.
        n_muertas = sum(1 for e in g.entries if e.status == "dead-end")
        lines += [
            "",
            f"**Marcar un callejón:** `guion_abandon(guion_path, version, why=…)` "
            f"— exige la razón, y arrastra a sus descendientes: una decisión "
            f"contaminada contamina lo que viene después."
            + (f" ({n_muertas} marcado{'s' if n_muertas != 1 else ''} ya)" if n_muertas else ""),
            "",
            f"**Informe navegable:** `export_guion(\"{os.path.expanduser(guion_path)}\", "
            f"\"<salida>.html\")` — tabla de versiones con ecuación, ajuste y "
            f"diagnosis de cada una.",
        ]

        if version:
            if version not in por_v:
                lines.append(f"\n⚠ la versión {version} no está en este guion.")
            else:
                cad = path_to_root(g, version)
                seguro = safe_ancestor(g, version)
                lines += [
                    "",
                    f"### La versión {version} ({por_v[version].name})",
                    "",
                    "**Cadena de decisiones que llevó hasta ella:** "
                    + " → ".join(f"v{v} {por_v[v].name}" for v in cad),
                    "",
                    f"**Descendientes:** "
                    + (", ".join(f"v{d}" for d in descendants(g, version)) or "ninguno"),
                    "",
                    f"**Lugar seguro más cercano:** "
                    + (f"v{seguro} ({por_v[seguro].name})" if seguro is not None
                       else "ninguno — toda la rama está abandonada"),
                ]
                if seguro is not None and seguro != version:
                    lines.append(
                        f"\nPara volver ahí, encadena desde su `.pre` "
                        f"(`base_pre_path`): la vuelta atrás queda registrada como "
                        f"rama y no como continuación.")
        return [TextContent(type="text", text="\n".join(lines))]
    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def guion_node(guion_path: str, nodo: str, decidido: str,
               razon: str, evidencia: str = "",
               alternativas: str = "", decidido_por: str = "",
               parent: int = -1) -> list:
    """
    Record a DECISION NODE in the guion — a specification choice, not a model.

    Why this exists. A guion that records only MODELS starts the story late. By
    the time the first estimated model exists, λ has been decided, d has been
    decided, whether there is seasonality and of what kind has been decided, and
    the orders have been picked — and none of that leaves a trace. On PGAS of
    the Bolivia replication the ENTIRE divergence between the two lanes is λ,
    decided before any model existed: the guion could not show it.

    Nodes and models live in the SAME chain, because the order in which they
    happened is itself information: a node that comes AFTER a model is a
    reformulation, and that only shows if they are interleaved.

    `razon` is required. A decision recorded without its reason is a number, and
    a number cannot be argued with later — which is the whole point of writing
    it down. This is the same principle as `why` in guion_abandon.

    Parameters
    ----------
    guion_path   : path to guion.json (created if absent)
    nodo         : which node — "lambda", "d", "estacionalidad", "ordenes",
                   "media", "intervenciones", "reformulacion", "dominio"
    decidido     : the value chosen, as text ("0", "1", "B1 + 1 armónico",
                   "ARMA(0,2)×(1,0)₄", "escalón en 2009:1")
    razon        : WHY. Required.
    evidencia    : the statistics it was decided on ("gap=+0.161",
                   "ADF p=0.013, KPSS p=0.09", "F-HAC=50.2")
    alternativas : what was considered and discarded, and why
    decidido_por : "analista+LLM" (guided) | "LLM" (autonomous) | "heurística"
    parent       : version this node descends from (-1 = the last one recorded).

    WHEN TO SET `parent` EXPLICITLY. A node that records the REJECTION of a
    branch must not hang from the branch it rejects. If it does, abandoning that
    branch cascades onto the very reasoning that condemned it — and the cascade
    is right to do so for models, because a contaminated decision contaminates
    what follows, but a node that says "I tried this and it failed" is not
    downstream of the failure: it is the conclusion drawn from it, and it belongs
    to the surviving trunk. Point it at the version you are keeping (the safe
    ancestor), not at the one you are about to abandon.
    """
    try:
        from mcp.types import TextContent
        from art.guion import (Guion, GuionEntry, load_guion, save_guion,
                               infer_parent)
        from datetime import datetime

        if not razon or not razon.strip():
            return _err("`razon` es obligatoria: una decisión sin su razón es un "
                        "número, y un número no se puede discutir después.")

        gp = os.path.expanduser(guion_path)
        os.makedirs(os.path.dirname(gp) or ".", exist_ok=True)
        if os.path.exists(gp):
            g = load_guion(gp)
        else:
            serie = os.path.basename(gp).replace("_guion.json", "").replace("guion.json", "")
            g = Guion(series=serie or "serie", analyst="",
                      created=datetime.now().strftime("%Y-%m-%d"))

        version = (max(e.version for e in g.entries) + 1) if g.entries else 1
        entry = GuionEntry(
            version=version, name=nodo, inp_path="", 
            timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            spec={}, stats=None, equation="",
            decision=f"{nodo} = {decidido}",
            rationale=razon, problems_found="", next_version="",
            parent=(int(parent) if parent >= 0 else infer_parent(g)),
            kind="node",
            node={"nodo": nodo, "decidido": decidido,
                  "evidencia": evidencia, "alternativas": alternativas},
            decided_by=decidido_por,
        )
        g.entries.append(entry)
        save_guion(g, gp)
        return [TextContent(type="text", text=(
            f"◆ nodo n{version} registrado: **{nodo} = {decidido}**"
            + (f"  [{decidido_por}]" if decidido_por else "")
            + f"\n   razón: {razon}"
            + (f"\n   evidencia: {evidencia}" if evidencia else "")
            + (f"\n   descartado: {alternativas}" if alternativas else "")
            + f"\n\n*mapa:* `guion_map(\"{gp}\")`"))]
    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def guion_diff(guion_a: str, guion_b: str,
               etiqueta_a: str = "A", etiqueta_b: str = "B") -> list:
    """
    Compare two analyses NODE BY NODE, with the reasoning of each side.

    Comparing two final models says THAT they differ. Comparing two paths says
    WHERE and WHY, and that is the only comparison anything is learned from: a
    worse model whose chain of decisions is legible teaches more than a better
    one that came out of a box.

    Use it to contrast the guided lane (analyst + LLM deciding together) against
    the autonomous one (the LLM deciding alone) over the same series. The
    protocol is the same and the nodes are the same; the only thing that changes
    is who decided each one — so every divergence localises to a node and comes
    with both reasons attached.

    Pairing is by node NAME, not position: two paths may visit the same nodes in
    a different order, or one may come BACK to a node the other decided once —
    which is exactly what makes the method iterative — and aligning by position
    would turn that into noise.

    Parameters
    ----------
    guion_a, guion_b   : paths to the two guion.json files
    etiqueta_a/b       : names for the two columns ("guiado", "autónomo")
    """
    try:
        from mcp.types import TextContent
        from art.guion import load_guion, diff_nodes, nodes as _nodes, models as _models

        ga = load_guion(os.path.expanduser(guion_a))
        gb = load_guion(os.path.expanduser(guion_b))
        filas = diff_nodes(ga, gb, etiqueta_a, etiqueta_b)

        out = [f"## {ga.series} — {etiqueta_a} contra {etiqueta_b}, nodo a nodo", ""]
        if not filas:
            out += ["*Ninguno de los dos guiones registra nodos de decisión.*", "",
                    "Los nodos se registran con `guion_node(...)`. Sin ellos sólo "
                    "se pueden comparar los modelos finales, que dice QUE difieren "
                    "y no dónde."]
            return [TextContent(type="text", text="\n".join(out))]

        MARCA = {"coinciden": "=", "divergen": "≠"}
        for f in filas:
            m = MARCA.get(f["veredicto"], "·")
            out.append(f"**{m} {f['nodo']}**")
            out.append(f"- {etiqueta_a}: `{f['valor_a']}`"
                       + (f"  [{f['decidio_a']}]" if f["decidio_a"] else ""))
            if f["evidencia_a"]:
                out.append(f"    - evidencia: {f['evidencia_a']}")
            if f["razon_a"]:
                out.append(f"    - razón: {f['razon_a']}")
            out.append(f"- {etiqueta_b}: `{f['valor_b']}`"
                       + (f"  [{f['decidio_b']}]" if f["decidio_b"] else ""))
            if f["evidencia_b"]:
                out.append(f"    - evidencia: {f['evidencia_b']}")
            if f["razon_b"]:
                out.append(f"    - razón: {f['razon_b']}")
            out.append("")

        n_div = sum(1 for f in filas if f["veredicto"] == "divergen")
        n_sol = sum(1 for f in filas if f["veredicto"].startswith("sólo"))
        out += ["---", "",
                f"**{len(filas)} nodo(s) contrastado(s): {n_div} divergen"
                + (f", {n_sol} visitado(s) por un solo carril" if n_sol else "")
                + ".**"]
        if n_sol:
            out.append("")
            out.append("Un nodo que sólo visita un carril no es un hueco del "
                       "registro: es que un recorrido volvió sobre una decisión "
                       "y el otro no. Eso es el método iterando.")
        out += ["",
                f"**Modelos estimados:** {etiqueta_a} {len(_models(ga))}, "
                f"{etiqueta_b} {len(_models(gb))}  |  "
                f"**nodos:** {etiqueta_a} {len(_nodes(ga))}, {etiqueta_b} {len(_nodes(gb))}"]
        return [TextContent(type="text", text="\n".join(out))]
    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def guion_abandon(guion_path: str, version: int, why: str,
                  cascade: bool = True) -> list:
    """
    Mark a version as a DEAD END, with the reason — and cascade to what descends
    from it.

    `why` is required, and that is deliberate: a dead end recorded without its
    reason does not stop anyone walking into it again, which is the only thing
    marking it is for.

    The cascade is not tidiness either. A contaminated decision contaminates
    everything after it — that is precisely the property that forces going back
    instead of patching forward — so the descendants of an abandoned version are
    abandoned with it.

    Parameters
    ----------
    guion_path : path to guion.json
    version    : version to abandon
    why        : why this branch is a dead end (required)
    cascade    : also abandon its descendants (default True, and normally right)
    """
    try:
        from mcp.types import TextContent
        from art.guion import load_guion, save_guion, abandon, safe_ancestor
        gp = os.path.expanduser(guion_path)
        g = load_guion(gp)
        por_v = {e.version: e for e in g.entries}
        if version not in por_v:
            return _err(f"la versión {version} no está en {gp}")
        tocadas, recolocadas = abandon(g, version, why, cascade=cascade)
        save_guion(g, gp)
        seguro = safe_ancestor(g, version)
        txt = [f"Marcadas como callejón sin salida: "
               + ", ".join(f"v{v} ({por_v[v].name})" for v in tocadas),
               "", f"**Razón:** {why.strip()}", ""]
        if recolocadas:
            # BUG-0037: un nodo alcanzado por la cascada suele ser el argumento
            # que CONDENA al callejón, no algo construido encima de él.
            txt += [
                "**Nodos recolocados, no abandonados:** "
                + ", ".join(f"n{v} ({por_v[v].name})" for v in recolocadas)
                + (f" → ahora cuelgan de v{seguro}" if seguro is not None else ""),
                "",
                "Un nodo es un argumento escrito, y el que viene detrás de un "
                "modelo fallido suele ser el que lo descarta. Marcarlo como "
                "callejón borraría la razón justo cuando más falta hace, así que "
                "se recoloca en el tronco y conserva su estado.",
                "",
            ]
        if seguro is not None:
            txt.append(f"**Lugar seguro al que volver:** v{seguro} ({por_v[seguro].name}). "
                       f"Encadena desde su `.pre` con `base_pre_path` para que la "
                       f"vuelta atrás quede registrada como rama.")
        else:
            txt.append("No queda ningún ancestro sano: hay que rehacer desde el principio.")
        return [TextContent(type="text", text="\n".join(txt))]
    except ValueError as e:
        return _err(str(e))
    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def export_guion(guion_path: str, output_html: str) -> list:
    """
    Render guion.json to a self-contained, navigable HTML report.

    Generates a single HTML file with:
    - Summary table of all versions (loglik, AIC, BIC, Q✓, JB✓, anomalías)
    - One collapsible section per version with equation, spec, stats, figure,
      decision notes, and link to next version

    Parameters
    ----------
    guion_path  : path to guion.json
    output_html : path to write the .html file
    """
    try:
        from mcp.types import TextContent
        from art.guion import load_guion, export_guion_html

        guion_path  = os.path.expanduser(guion_path)
        output_html = os.path.expanduser(output_html)

        guion = load_guion(guion_path)
        html  = export_guion_html(guion)

        os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html)

        n = len(guion.entries)
        text = (
            f"### Guion exportado\n\n"
            f"- Serie: **{guion.series}**\n"
            f"- Versiones: **{n}**\n"
            f"- HTML guardado en: `{output_html}`\n\n"
            f"Abre el fichero en un navegador para navegar el historial de versiones."
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: compare_versions — side-by-side model comparison  (Bloque Q)
# ---------------------------------------------------------------------------

def _spec_diff(spec_a: dict, spec_b: dict) -> list[str]:
    """Return list of 'key: a→b' strings for each spec field that changed."""
    changes = []
    for key in ("lam", "d", "D", "p", "q", "P", "Q", "n_harmonics"):
        a, b = spec_a.get(key, 0), spec_b.get(key, 0)
        if a != b:
            changes.append(f"{key}: {a}→{b}")
    # BUG-0051: el cambio de ifadf era el único que no se anunciaba, y es de los
    # que cambian la variable dependiente.
    ia, ib = list(spec_a.get("ifadf") or []), list(spec_b.get("ifadf") or [])
    if ia != ib:
        changes.append(f"ifadf: {ia}→{ib}")
    itvs_a = {(iv.get("type", "?"), iv.get("date", "?"))
               for iv in spec_a.get("interventions", [])}
    itvs_b = {(iv.get("type", "?"), iv.get("date", "?"))
               for iv in spec_b.get("interventions", [])}
    for t, d in sorted(itvs_b - itvs_a):
        changes.append(f"+{t}({d})")
    for t, d in sorted(itvs_a - itvs_b):
        changes.append(f"−{t}({d})")
    return changes


def _nested_relation(spec_a: dict, spec_b: dict,
                     npar_a: int, npar_b: int) -> str:
    """
    Return "A_in_B", "B_in_A", or "none".

    A is nested in B if d,D match, p_a≤p_b, q_a≤q_b, P_a≤P_b, Q_a≤Q_b,
    n_h_a≤n_h_b, all interventions of A are in B, and npar_a < npar_b.
    """
    def a_in_b(sa, sb, na, nb):
        if na >= nb:
            return False
        # BUG-0051: dos modelos con transformaciones distintas de los datos no
        # están anidados, están en escalas distintas. Se compara TODO el operador
        # de diferenciación, ifadf y Box-Cox incluidos.
        if (sa.get("d")   != sb.get("d")   or sa.get("D") != sb.get("D") or
                sa.get("lam") != sb.get("lam") or
                list(sa.get("ifadf") or []) != list(sb.get("ifadf") or [])):
            return False
        for k in ("p", "q", "P", "Q", "n_harmonics"):
            if sa.get(k, 0) > sb.get(k, 0):
                return False
        itvs_a = {(iv.get("type"), iv.get("date"))
                   for iv in sa.get("interventions", [])}
        itvs_b = {(iv.get("type"), iv.get("date"))
                   for iv in sb.get("interventions", [])}
        return itvs_a <= itvs_b

    if a_in_b(spec_a, spec_b, npar_a, npar_b):
        return "A_in_B"
    if a_in_b(spec_b, spec_a, npar_b, npar_a):
        return "B_in_A"
    return "none"


@mcp.tool()
def compare_versions(inp_path_a: str, inp_path_b: str,
                     lam_a: float = 0.0, lam_b: float = 0.0,
                     guion_path: str = "") -> list:
    """
    Compare two estimated models: spec diff, stats table, nested LR test.

    Loads and fits both .inp files. Returns:
    - Spec comparison (what parameters changed)
    - Side-by-side stats: loglik, AIC, BIC, σ_a, Q-pass, JB-pass
    - Nested LR test if one model is a restricted version of the other
    - ACF/PACF comparison figure (residuals of both models)

    Parameters
    ----------
    inp_path_a  : .inp file for model A (baseline / more restricted)
    inp_path_b  : .inp file for model B (alternative / richer)
    lam_a       : Box-Cox lambda for model A (0.0 = log)
    lam_b       : Box-Cox lambda for model B (0.0 = log)
    guion_path  : (optional) guion.json — unused currently, reserved
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.guion import _extract_spec, _build_equation
        from art.diagnosis import diagnose
        from art.describe import _fig_b64
        from art.identification import _default_lags_fug
        from fue.diagnostics import acf as _fue_acf, pacf as _fue_pacf
        from fue.plots import _draw_acf_panel, _snap_cmax, _tj_spines
        import numpy as np
        import scipy.stats as sp_stats
        import matplotlib.pyplot as plt

        _, ma = _load_fitted(inp_path_a)
        _, mb = _load_fitted(inp_path_b)

        spec_a = _extract_spec(ma, lam=lam_a)
        spec_b = _extract_spec(mb, lam=lam_b)
        eq_a   = _build_equation(spec_a, ma.series.freq)
        eq_b   = _build_equation(spec_b, mb.series.freq)

        diag_a = diagnose(ma)
        diag_b = diagnose(mb)

        la, lb = ma._result.loglik, mb._result.loglik
        aic_a, bic_a = ma._result.aic, ma._result.bic
        aic_b, bic_b = mb._result.aic, mb._result.bic
        npar_a, npar_b = ma._result.npar, mb._result.npar
        import math
        sa = math.sqrt(ma._result.sigma2) if ma._result.sigma2 > 0 else 0.0
        sb = math.sqrt(mb._result.sigma2) if mb._result.sigma2 > 0 else 0.0

        name_a = os.path.basename(inp_path_a)
        name_b = os.path.basename(inp_path_b)

        # ── Spec diff ──────────────────────────────────────────────────────
        changes = _spec_diff(spec_a, spec_b)
        diff_str = (", ".join(changes)) if changes else "Sin cambios en la estructura"

        # ── ¿Están las dos verosimilitudes en la MISMA escala? ─────────────
        # BUG-0051. loglik, AIC y BIC sólo se comparan entre modelos que
        # explican la MISMA variable dependiente. Si el operador de
        # diferenciación difiere --d, D, ifadf o el Box-Cox-- cada uno explica
        # una transformación distinta de la serie, con distinto número efectivo
        # de observaciones, y su Δ no significa nada. Imprimir el número igual es
        # peor que no imprimirlo: se lee, y manda adoptar el modelo peor.
        _op = lambda sp: (sp.get("lam"), sp.get("d"), sp.get("D"),
                          tuple(sp.get("ifadf") or []))
        comparables = _op(spec_a) == _op(spec_b)
        aviso_escala = []
        if not comparables:
            aviso_escala = [
                "",
                "> ⚠ **loglik, AIC y BIC NO son comparables entre estos dos "
                "modelos.** El operador de diferenciación difiere "
                f"(`λ={spec_a.get('lam')}, d={spec_a.get('d')}, "
                f"D={spec_a.get('D')}, ifadf={list(spec_a.get('ifadf') or [])}` "
                f"frente a `λ={spec_b.get('lam')}, d={spec_b.get('d')}, "
                f"D={spec_b.get('D')}, ifadf={list(spec_b.get('ifadf') or [])}`), "
                "así que cada uno explica una variable dependiente distinta, con "
                "distinto número efectivo de observaciones. Sus verosimilitudes "
                "no están en la misma escala y su Δ se ha suprimido.",
                ">",
                "> Compáralos por lo que SÍ es comparable: la **diagnosis** "
                "(¿son adecuados?), σ̂ₐ **en unidades de la serie original**, y "
                "la previsión fuera de muestra. Y si lo que se quiere decidir es "
                "el orden de integración, ése es el trabajo de los contrastes "
                "formales (`formal_tests`), no del AIC.",
            ]

        # ── Nested LR test ─────────────────────────────────────────────────
        nested = _nested_relation(spec_a, spec_b, npar_a, npar_b)
        lr_lines = []
        if nested == "A_in_B":
            lr = 2.0 * (lb - la)
            df = npar_b - npar_a
            pval = sp_stats.chi2.sf(lr, df) if lr > 0 else 1.0
            # BUG-0051: un LR NEGATIVO entre modelos anidados es imposible --el
            # modelo más rico no puede ajustar peor--, así que no es una «mejora
            # no significativa»: es la prueba de que el anidamiento o la escala
            # están mal. Se dice, en vez de imprimir p=1.0000 y seguir.
            verdict = ("B mejora significativamente ✓" if pval < 0.05
                       else "mejora no significativa ✗")
            if lr < 0:
                verdict = ("**IMPOSIBLE**: un LR negativo entre modelos "
                           "anidados no existe. O no lo están, o sus "
                           "verosimilitudes no están en la misma escala. "
                           "No leas este contraste.")
            lr_lines = [
                f"**Test LR** (B es más rico, A ⊂ B):",
                f"LR = 2·({lb:.3f}−{la:.3f}) = **{lr:.3f}**, df={df}, p={pval:.4f} → {verdict}",
            ]
        elif nested == "B_in_A":
            lr = 2.0 * (la - lb)
            df = npar_a - npar_b
            pval = sp_stats.chi2.sf(lr, df) if lr > 0 else 1.0
            # BUG-0051: un LR NEGATIVO entre modelos anidados es imposible --el
            # modelo más rico no puede ajustar peor--, así que no es una «mejora
            # no significativa»: es la prueba de que el anidamiento o la escala
            # están mal. Se dice, en vez de imprimir p=1.0000 y seguir.
            verdict = ("A mejora significativamente ✓" if pval < 0.05
                       else "mejora no significativa ✗")
            if lr < 0:
                verdict = ("**IMPOSIBLE**: un LR negativo entre modelos "
                           "anidados no existe. O no lo están, o sus "
                           "verosimilitudes no están en la misma escala. "
                           "No leas este contraste.")
            lr_lines = [
                f"**Test LR** (A es más rico, B ⊂ A):",
                f"LR = 2·({la:.3f}−{lb:.3f}) = **{lr:.3f}**, df={df}, p={pval:.4f} → {verdict}",
            ]
        else:
            lr_lines = ["Modelos no anidados — test LR no aplicable."]

        # ── Stats comparison table ─────────────────────────────────────────
        def _fmt(v, fmt=".2f"):
            return f"{v:{fmt}}" if v is not None else "—"

        delta_loglik = lb - la
        delta_aic    = (bic_b or 0) - (bic_a or 0)  # use BIC for penalty
        delta_aic_v  = (aic_b or 0) - (aic_a or 0)

        # BUG-0051: con transformaciones distintas, el Δ de verosimilitud y de
        # los criterios se suprime. σ_a y npar se quedan: la primera está en
        # unidades de la serie y la segunda es un recuento.
        _d_ll  = f"{delta_loglik:+.3f}" if comparables else "— no comp."
        _d_aic = f"{delta_aic_v:+.2f}"  if comparables else "— no comp."
        _d_bic = f"{delta_aic:+.2f}"    if comparables else "— no comp."

        rows = [
            ("", f"**{name_a}**", f"**{name_b}**", "**Δ (B−A)**"),
            ("loglik", _fmt(la, ".3f"), _fmt(lb, ".3f"), _d_ll),
            ("AIC",    _fmt(aic_a), _fmt(aic_b), _d_aic),
            ("BIC",    _fmt(bic_a), _fmt(bic_b), _d_bic),
            ("σ_a",   f"{sa:.5f}", f"{sb:.5f}", f"{sb-sa:+.5f}"),
            ("npar",  str(npar_a), str(npar_b), f"{npar_b-npar_a:+d}"),
            ("Q✓",    "✓" if diag_a.white_noise else "✗",
                      "✓" if diag_b.white_noise else "✗", ""),
            ("JB✓",   "✓" if diag_a.normal else "✗",
                      "✓" if diag_b.normal else "✗", ""),
            ("Anomalías", str(len(diag_a.extreme)), str(len(diag_b.extreme)), ""),
        ]
        col_w = [max(len(r[i]) for r in rows) for i in range(4)]
        tbl = []
        for row in rows:
            tbl.append("| " + " | ".join(cell.ljust(col_w[i]) for i, cell in enumerate(row)) + " |")
        sep = "|" + "|".join("-" * (w + 2) for w in col_w) + "|"
        tbl.insert(1, sep)

        # ── ACF/PACF comparison figure ─────────────────────────────────────
        res_a = np.asarray(diag_a.residuals, dtype=float)
        res_b = np.asarray(diag_b.residuals, dtype=float)
        freq  = ma.series.freq
        lags  = _default_lags_fug(min(len(res_a), len(res_b)), freq)
        lag_x = np.arange(1, lags + 1)

        acf_a_arr  = np.asarray(_fue_acf(res_a,  lags=lags), dtype=float)
        acf_b_arr  = np.asarray(_fue_acf(res_b,  lags=lags), dtype=float)
        pacf_a_arr = np.asarray(_fue_pacf(res_a, lags=lags), dtype=float)
        pacf_b_arr = np.asarray(_fue_pacf(res_b, lags=lags), dtype=float)

        band_a = 1.96 / np.sqrt(len(res_a))
        band_b = 1.96 / np.sqrt(len(res_b))

        all_acf  = np.concatenate([acf_a_arr,  acf_b_arr])
        all_pacf = np.concatenate([pacf_a_arr, pacf_b_arr])
        cmax = _snap_cmax(all_acf, all_pacf)

        fig, axes = plt.subplots(3, 2, figsize=(14, 10))
        fig.suptitle(f"Comparación: {name_a}  vs  {name_b}", fontsize=11, fontweight="bold")

        # Row 0: standardized residuals
        for col, (res, name_lbl) in enumerate([(res_a, name_a), (res_b, name_b)]):
            ax = axes[0, col]
            r_std_v = res.std(ddof=1) if len(res) > 1 else 1.0
            r_z = (res - res.mean()) / r_std_v if r_std_v > 0 else res
            ax.axhline(0, color="black", lw=0.8)
            ax.axhline(+2, color="red", lw=0.6, ls="--")
            ax.axhline(-2, color="red", lw=0.6, ls="--")
            ax.plot(np.arange(len(r_z)), r_z, color="#333333", lw=0.8)
            ax.set_title(f"Residuos — {name_lbl}", fontsize=9)
            _tj_spines(ax)

        # Rows 1-2: ACF and PACF
        acf_pacf_panels = [
            (axes[1, 0], acf_a_arr,  band_a, f"ACF — {name_a}"),
            (axes[1, 1], acf_b_arr,  band_b, f"ACF — {name_b}"),
            (axes[2, 0], pacf_a_arr, band_a, f"PACF — {name_a}"),
            (axes[2, 1], pacf_b_arr, band_b, f"PACF — {name_b}"),
        ]
        for ax, vals, band, title in acf_pacf_panels:
            _draw_acf_panel(ax, lag_x, vals, band=band, cmax=cmax,
                            freq=freq, lags=lags, label=title)

        fig.tight_layout()
        b64 = _fig_b64(fig)
        plt.close(fig)

        # ── Compose text ───────────────────────────────────────────────────
        lines = [
            f"## Comparación de versiones",
            f"",
            f"**A**: `{name_a}` — `{eq_a}`",
            f"**B**: `{name_b}` — `{eq_b}`",
            f"",
            f"**Cambios (A→B)**: {diff_str}",
        ] + aviso_escala + [
            f"",
            "### Estadísticos",
        ] + tbl + [""] + lr_lines

        items = [TextContent(type="text", text="\n".join(lines))]
        if b64:
            items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: suggest intervention form (B3)
# ---------------------------------------------------------------------------

@mcp.tool()
def suggest_intervention_form(inp_path: str, output_path: str,
                               date: str = "",
                               form: str = "auto",
                               context_hint: str = "",
                               include_histogram: bool = False,
                               guion_path: str = "",
                               guion_name: str = "",
                               guion_decision: str = "",
                               guion_rationale: str = "",
                               guion_problems: str = "",
                               guion_next: str = "") -> list:
    """
    Add an intervention to the .inp, re-estimate and show updated diagnosis.

    Adds a pulse, step or ramp intervention at the given date, saves to
    output_path, re-estimates and returns the updated parameter table and
    diagnosis. Use this iteratively — one intervention at a time.

    Parameters
    ----------
    inp_path          : current .inp/.pre (with any previous interventions)
    output_path       : path to write the updated .inp
    date              : observation date "MM/YYYY" or "QN/YYYY" or "YYYY".
                        Leave empty ("") to auto-select the most extreme residual.
    form              : "pulse", "step", "ramp" or "auto" (heuristic)
    context_hint      : free-text note about the economic event (for logging)
    include_histogram : return histogram PNG (default False — saves tokens
                        during the outlier cycle; set True for final round)
    guion_path        : (optional) path to guion.json — records this version
    guion_name        : version name (e.g. "PC3"); auto-assigned if empty
    guion_decision    : brief description of what this model tests or concludes
    guion_rationale   : justification for the intervention choice
    guion_problems    : problems found in the diagnosis
    guion_next        : description of the next version to try
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        import fue, re

        inp_path    = os.path.expanduser(inp_path)
        output_path = os.path.expanduser(output_path)

        if not os.path.exists(inp_path):
            raise FileNotFoundError(f"File not found: {inp_path}")

        def _parse_date(d: str):
            d = d.strip()
            m_mo = re.match(r"^(\d{1,2})/(\d{4})$", d)
            m_q  = re.match(r"^[Qq](\d)/(\d{4})$", d)
            m_yr = re.match(r"^(\d{4})$", d)
            if m_mo:
                return int(m_mo.group(1)), int(m_mo.group(2))
            if m_q:
                return int(m_q.group(1)), int(m_q.group(2))
            if m_yr:
                return 1, int(m_yr.group(1))
            raise ValueError(f"Unrecognised date format: {d!r}. Use MM/YYYY, QN/YYYY or YYYY.")

        # Load current model to inspect residuals and build the new spec
        ts, m_src = _load_fitted(inp_path)

        freq  = ts.freq
        start = list(ts.start)
        s0y, s0p = start[0], (start[1] if freq > 1 else 1)

        # BUG-0067. Hay DOS espacios de índices en juego y este bloque los
        # mezclaba en tres sitios. Los residuos de un modelo diferenciado empiezan
        # `d + D·s` observaciones después que la serie, así que el «obs 19» del
        # escaneo de anómalos es la observación 20 de la serie.
        #
        # Medido sobre el ITCER de la réplica (d=1): el escaneo dice —bien—
        # «Q4/2008», y el auto-select colocaba la intervención en **Q3/2008**. Un
        # trimestre antes del desplome de Lehman, en silencio, y sobre el modelo
        # que se estima. Una fecha equivocada es un modelo equivocado.
        #
        # Se convierte UNA vez, aquí, y a partir de este punto todo va en índices
        # de la SERIE.
        _desfase = m_src.d + m_src.D * (freq if freq > 0 else 1)

        if not date.strip():
            # Auto-select most extreme residual not already covered by an intervention
            import numpy as np
            from art.diagnosis import diagnose
            from art import policy
            diag_auto = diagnose(m_src, z_threshold=policy.THRESHOLDS["intervention_autoselect"])
            existing_at = {itv.at for itv in (m_src.interventions or [])}
            # `obs` es 1-based sobre los RESIDUOS; `itv.at` es 0-based sobre la
            # SERIE. Comparar sin convertir daba por cubierta la intervención
            # equivocada.
            candidates = [(abs(z), obs) for obs, z in diag_auto.extreme
                          if (obs - 1 + _desfase) not in existing_at]
            if not candidates:
                return _err("No se encontraron residuos extremos sin intervención asignada. "
                            "Proporciona date manualmente.")
            _, obs_1based = max(candidates)
            at_0 = (obs_1based - 1) + _desfase
            # Convert obs index → calendar date string for the note
            total = (s0p - 1) + at_0
            if freq == 12:
                auto_date = f"{total % 12 + 1:02d}/{s0y + total // 12}"
            elif freq == 4:
                auto_date = f"Q{total % 4 + 1}/{s0y + total // 4}"
            else:
                auto_date = str(s0y + total)
            date_note = f"Fecha auto-detectada (residuo más extremo sin intervención): **{auto_date}**"
        else:
            period, year = _parse_date(date)
            at_0 = (year - s0y) * freq + (period - s0p)
            if at_0 < 0 or at_0 >= ts.nobs:
                raise ValueError(f"Date {date} gives obs={at_0+1}, outside series range [1, {ts.nobs}].")
            date_note = f"Fecha: **{date}**"

        if form == "auto":
            # Same step/pulse rule as the autonomous loop (policy.decide_form)
            from art.diagnosis import diagnose
            from art import policy
            diag_tmp = diagnose(m_src, z_threshold=policy.THRESHOLDS["intervention_form"])
            # BUG-0067: `decide_form` mira si un vecino también es extremo, así
            # que los dos argumentos tienen que estar en el MISMO espacio. Los
            # extremos vienen en índices de residuo y `at_0` está en la serie:
            # se suben los extremos, no se baja `at_0` --que es el que va a ir al
            # modelo--. En la rama de fecha manual el desajuste existía igual.
            extreme_obs = {obs + _desfase for obs, _ in diag_tmp.extreme}
            form = policy.decide_form(at_0 + 1, extreme_obs)

        # Create new Intervention with correct at= (0-based index)
        itv = fue.Intervention(
            type=form,
            at=at_0,
            omega=[0.0],
            omega_free=[True],
        )

        # Build updated model with the new intervention appended
        new_itvs = list(m_src.interventions or []) + [itv]
        m_new = fue.Model(
            ts,
            ar=m_src.ar, ar_free=m_src.ar_free,
            ma=m_src.ma, ma_free=m_src.ma_free,
            ar_s=m_src.ar_s, ar_s_free=m_src.ar_s_free,
            ma_s=m_src.ma_s, ma_s_free=m_src.ma_s_free,
            ar_f=m_src.ar_f, ma_f=m_src.ma_f,
            d=m_src.d, D=m_src.D, ifadf=m_src.ifadf,
            interventions=new_itvs,
            mu=m_src.mu0, estimate_mu=m_src.estimate_mu,
            boxlam=m_src.boxlam,
            # BUG-0007 (sibling): carry refactor so the written .inp and the mu0
            # seed (rescaled space) stay consistent before re-estimation.
            refactor=getattr(m_src, "refactor", 1.0) or 1.0,
        )

        # Write the updated .inp and re-estimate
        _write_inp(ts, m_new, output_path)
        _, m_fit = _load_fitted(output_path)

        diag = describe_diagnosis(m_fit)

        try:
            eq_text = _equation_for_prompt(ts, m_fit)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"

        context_str = f"  Contexto: {context_hint}" if context_hint else ""

        # El guion NO es opcional (ver confirm_and_estimate). Una intervención
        # añadida es una decisión del ciclo como cualquier otra, y de las que más
        # se revierten: si no queda registrada con su padre, la vuelta atrás
        # pierde el punto al que volver.
        guion_note = ""
        try:
            lam_fit = float(getattr(m_fit, "boxlam", 0.0) or 0.0)
            guion_note = _record_to_guion(
                model=m_fit, inp_path=output_path, lam=lam_fit,
                guion_path=guion_path or _derive_guion_path(output_path, m_fit),
                name=guion_name, decision=guion_decision,
                rationale=guion_rationale, problems_found=guion_problems,
                next_version=guion_next,
                figure_b64=diag.figure_b64,
                base_pre_path=inp_path,
            )
        except Exception as e:
            guion_note = f"*guion: no registrado ({type(e).__name__})*"

        # Persist the fitted model as .pre so the NEXT step starts from this
        # optimum (sequential construction: each estimate begins at the previous
        # likelihood optimum, not from scratch). The .pre stores estimated
        # parameters as initial values.
        _base = os.path.splitext(output_path)[0]
        new_pre_path = _base + ".pre"
        new_out_path = _base + ".out"
        try:
            m_fit.write_pre(new_pre_path)
            try:
                m_fit.write_out(new_out_path)
                pre_note = (f"  |  pre-estimaciones: {new_pre_path}  |  "
                            f"resultados: {new_out_path}")
            except Exception:
                pre_note = f"  |  pre-estimaciones: {new_pre_path}"
        except Exception:
            pre_note = ""
        lam_fit = float(getattr(m_fit, "boxlam", 0.0) or 0.0)
        d_fit   = int(getattr(m_fit, "d", 0) or 0)
        D_fit   = int(getattr(m_fit, "D", 0) or 0)
        p_fit   = len(m_fit.ar)   if getattr(m_fit, "ar",   None) else 0
        q_fit   = len(m_fit.ma)   if getattr(m_fit, "ma",   None) else 0
        P_fit   = len(m_fit.ar_s) if getattr(m_fit, "ar_s", None) else 0
        Q_fit   = len(m_fit.ma_s) if getattr(m_fit, "ma_s", None) else 0
        scan_section, scan_b64 = _auto_scan_section(
            ts, m_fit, lam=lam_fit, d=d_fit, D=D_fit,
            p=p_fit, q=q_fit, P=P_fit, Q=Q_fit,
            inp_path=inp_path, pre_path=new_pre_path,
        )

        text = (
            f"**Intervención añadida:** {form.upper()}  {date_note}{context_str}\n\n"
            + eq_text
            + "\n\n---\n\n"
            + diag.summary + "\n\n---\n" + diag.recommendation
            + scan_section
            + f"\n\n*Modelo actualizado en: {output_path}{pre_note}*"
            + (f"\n\n{guion_note}" if guion_note else "")
            + _state_footer(m_fit, inp_path=output_path, guion_note=guion_note,
                              guion_path_hint=guion_path or _derive_guion_path(output_path, m_fit))
        )

        _show_fig(diag.figure_b64, "diagnosis")
        items = [TextContent(type="text", text=text)]
        if diag.figure_b64:
            items.append(ImageContent(type="image",
                                      data=diag.figure_b64, mimeType="image/png"))
        if scan_b64:
            items.append(ImageContent(type="image",
                                      data=scan_b64, mimeType="image/png"))
        if include_histogram:
            hist_b64 = diag.data.get("hist_b64")
            if hist_b64:
                items.append(ImageContent(type="image",
                                          data=hist_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Helpers for autonomous pipeline (Block C)
# ---------------------------------------------------------------------------

def _format_dcd_meg(dcd_results, meg_results) -> str:
    """Short text summary of DCD and MEG results for use in build_model output."""
    lines = []
    if dcd_results:
        lines.append("**DCD (no invertibilidad MA):**")
        for r in dcd_results:
            inv = "Invertible ✓" if r.rejects_5pct else "No invertible ✗"
            lines.append(f"  Factor {r.factor_index+1}: LR={r.lr:.3f}  → {inv}")
    if meg_results:
        lines.append("**MEG (estacionalidad estocástica):**")
        for r in meg_results:
            tag = {"stochastic": "Estocástica ⚠", "deterministic": "Determinista ✓",
                   "ambiguous": "Ambiguo ?"}.get(r.status, r.status)
            lr_str = f"  LR={r.dcd_result.lr:.3f}" if r.dcd_result else ""
            lines.append(f"  freq={r.freq}: {tag}{lr_str}")
    return "\n".join(lines) if lines else "*Sin contrastes formales aplicables.*"


# ---------------------------------------------------------------------------
# Tool: autonomous model build (C1)
# ---------------------------------------------------------------------------

@mcp.tool()
def build_model(inp_path: str, output_path: str, max_rounds: int = 5,
                run_meg: bool = False,
                lam: float = -1.0, d: int = -1, D: int = -1,
                p: int = -1, q: int = -1, n_harmonics: int = -1,
                estimate_mu: int = -1,
                domain: str = "",
                decision: str = "",
                guion_path: str = "",
                guion_name: str = "",
                guion_decision: str = "",
                guion_rationale: str = "",
                objetivo: str = "univariante") -> list:
    """
    Box-Jenkins-Treadway pipeline for a single series — autonomous or guided.

    Runs ONE engine (pipeline.run_full): decides the spec, estimates, adds
    interventions for detected outliers and re-estimates until the diagnosis is
    clean or max_rounds. The only difference between modes is WHO supplies each
    decision:

      - Autonomous (all spec params left at their sentinel): the heuristic
        DefaultPolicy decides λ, d, D, harmonics, p, q and the mean.
      - Guided (any of lam/d/D/p/q/n_harmonics/estimate_mu/decision provided): those
        analyst/Claude-confirmed choices are honoured (ClaudePolicy) and the
        heuristic fills only what was left unspecified. Use after
        guided_identification to run the build with the confirmed spec while
        the outlier cycle proceeds automatically.

    Always returns parameters + residual diagnosis figure; DCD/MEG at the end.

    Parameters
    ----------
    inp_path      : source .inp file — only the series is used
    output_path   : path for the final estimated .inp
    max_rounds    : maximum intervention-addition rounds (default 5)
    run_meg       : run MEG stochastic seasonality test (slow; default False)
    lam           : confirmed Box-Cox λ (0/0.5/1); -1 = let the heuristic decide
    d, D          : confirmed differencing orders; -1 = heuristic
    p, q          : confirmed ARMA orders; -1 = heuristic
    n_harmonics   : confirmed cos/sin pairs (B1); -1 = heuristic
    estimate_mu   : free mean? 1 = yes, 0 = no, -1 = let the policy decide from
                    the drift of the differenced series (|t| > 2). For a price
                    index the mean IS the inflation rate, so -1 usually gives 1;
                    force 0 only when you mean "this series has no drift".
    domain        : what KIND of series this is — "price_index" or "generic".
                    "" (default) = infer from the name, which is WEAK evidence
                    and is why declaring it wins. A price index has no natural
                    zero (its base year is a convention), so it takes λ=0
                    whatever the Box-Cox statistic says; measured on eight CPI
                    indices the statistic split them 4/4 on a |gap| that never
                    exceeded 0.304. Declare it when the name does not say so —
                    "EMU" is a price index and does not look like one.
    decision      : confirmed "A"/"B1"/"B2"; "" = heuristic
    guion_path    : (optional) path to guion.json — records the final model
    guion_name    : version name (e.g. "PC1"); auto-assigned if empty
    guion_decision: brief description of the model or pipeline result
    guion_rationale: justification for the spec
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        from art.diagnosis import plot_diagnosis
        from art.formal_tests import dcd as _dcd
        import io, base64
        import matplotlib.pyplot as plt

        inp_path    = os.path.expanduser(inp_path)
        output_path = os.path.expanduser(output_path)
        ts, _ = _load_ts_model(inp_path)
        name = ts.name or os.path.basename(inp_path)

        # ── Build the decision policy from any analyst-confirmed choices ───
        overrides = {}
        if lam >= 0:         overrides["lam"] = lam
        if d >= 0:           overrides["d"] = d
        if D >= 0:           overrides["D"] = D
        if p >= 0:           overrides["p"] = p
        if q >= 0:           overrides["q"] = q
        if n_harmonics >= 0: overrides["n_harmonics"] = n_harmonics
        # BUG-0013: -1 leaves the mean to the policy's drift test, which is what
        # you want -- the analyst only overrides to force it on or off.
        if estimate_mu >= 0: overrides["estimate_mu"] = bool(estimate_mu)
        # BUG-0015: qué CLASE de serie es. Declarado gana a inferido del nombre.
        if domain:           overrides["domain"] = domain
        if decision:         overrides["decision"] = decision
        guided = bool(overrides)
        decision_policy = policy.ClaudePolicy(**overrides) if guided else None

        # ── Run the pipeline (decisions + outlier loop) ────────────────────
        result = run_full(ts, output_path, max_rounds=max_rounds,
                          decision_policy=decision_policy, objetivo=objetivo)
        lam, d, D = result.lam, result.d, result.D
        m_fit, diag = result.final_model, result.final_diag

        # ── Reconstruct the rich text log from the structured rounds ──────
        _mode = "guiado (spec confirmada)" if guided else "autónomo"
        log = [f"### Pipeline {_mode} — {name}"]
        lam_str = "log (λ=0)" if lam == 0.0 else "identidad (λ=1)"
        # El dominio se ANUNCIA. Su propio docstring lo promete —"recorded and
        # announced, never applied in silence"— y no se estaba imprimiendo: la
        # regla que decide λ dentro de la banda ambigua quedaba invisible, que es
        # justo la que hay que poder discutir (BUG-0040).
        _dom = {"price_index": "índice de precios",
                "multiplicative": "magnitud multiplicativa",
                "ratio": "cociente acotado",
                "generic": "genérica"}.get(result.domain, result.domain)
        _gap = result.boxcox_data.get('gap', 0)
        _manda = ("dominio" if (result.domain == "price_index"
                                or (result.domain in ("multiplicative", "ratio")
                                    and abs(_gap) < 0.10))
                  else "estadístico")
        log.append(f"**Dominio:** {_dom}  (inferido; lo declarado gana — "
                   f"`domain=…`)")
        log.append(f"**λ:** {lam_str}  (gap={_gap:+.3f} · decide el {_manda})")
        log.append(f"**Estacionalidad:** decisión={result.decision}  d={d}  D={D}  "
                   f"armónicos={result.n_harmonics}")
        sim_str = f"{result.orders_specs[0].similarity:.3f}" if result.orders_specs else "N/A"
        log.append(f"**Órdenes:** ARIMA({result.p},{d},{result.q})  similitud={sim_str}")

        # Las dos rutas estacionales, cuando las hubo. Se presentan las DOS y la
        # razón de la adjudicación: elegir entre B1 y B2 por convención sería el
        # único nodo del método resuelto por decreto, y aquí hay par de
        # contrastes (MEG sobre B1, MA estacional de B2) para decidirlo.
        if result.route:
            log.append(f"\n**Ruta estacional:** se estimaron LAS DOS "
                       f"(objetivo={result.objetivo})")
            for nombre in ("B1", "B2"):
                rr = result.branches.get(nombre)
                if not rr:
                    continue
                _rounds, _m, _dg, _itv = rr
                marca = "→ **adoptada**" if nombre == result.route else "  descartada"
                etiq = ("D=0 + armónicos" if nombre == "B1" else "D=1")
                log.append(f"  {marca}  {nombre} ({etiq}): AIC={_m.aic:.2f} · "
                           f"Q p-mín={min(_dg.q_pvalues):.4f} · "
                           f"{'diagnosis limpia' if _dg.residuals_ok else 'diagnosis NO limpia'}")
            log.append(f"  _{result.route_reason}_")
            log.append("  ⚠ Los AIC de las dos ramas NO son directamente "
                       "comparables: `D=1` consume `s` observaciones más, así que "
                       "las verosimilitudes están sobre muestras distintas. Quien "
                       "decide es el par de contrastes, no la diferencia de AIC.")

        def _round_fig_b64(diag_result, model, label: str) -> str:
            """Render a diagnosis figure and return as base64 PNG."""
            diag_result.label = label
            fig = plot_diagnosis(diag_result, model)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=110, bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode()

        round_figures: list[str] = []   # base64 PNG per round (Block D)
        for rd in result.rounds:
            rdiag = rd.diag
            q_fail = [str(l) for l, pv in zip(rdiag.q_lags, rdiag.q_pvalues) if pv < 0.05]
            q_str  = "✓" if rdiag.white_noise else f"✗ lags {', '.join(q_fail)}"
            jb_str = "✓" if rdiag.normal else f"✗ JB={rdiag.jb_stat:.1f}"
            n_ext  = len(rdiag.extreme)
            ext_str = (
                "  ".join(f"obs {obs} (z={z:+.2f})" for obs, z in rdiag.extreme[:4])
                if rdiag.extreme else "—"
            )
            log.append(
                f"\n**Ronda {rd.round_num}:**  Q: {q_str}  JB: {jb_str}  "
                f"extremos: {n_ext}"
            )
            if rdiag.extreme:
                log.append(f"  {ext_str}" + (" …" if n_ext > 4 else ""))

            round_figures.append(
                _round_fig_b64(rdiag, rd.model, f"Ronda {rd.round_num} — {name}"))

            if rd.stop_reason == "no_new":
                log.append("  Sin nuevas intervenciones que añadir.")
            elif rd.added:
                itv_labels = ", ".join(f"{f.upper()} obs {at+1}" for at, f in rd.added[:5])
                log.append(f"  → Añadidas: {itv_labels}")

        round_num = result.rounds[-1].round_num if result.rounds else 0
        log.append(f"\n**Rondas totales:** {round_num}")
        log.append(f"**Diagnosis final:** {'APROBADA ✓' if diag and diag.clean else 'REVISAR ✗'}")

        # ── Formal tests ──────────────────────────────────────────────────
        dcd_results = []
        meg_results = []
        if m_fit is not None:
            try:
                dcd_results = _dcd(m_fit)
            except Exception as e:
                _warn("DCD test not applicable / failed", e)
            if run_meg and m_fit.D == 0:
                try:
                    from art.formal_tests import meg as _meg
                    meg_results = _meg(m_fit)
                except Exception as e:
                    _warn("MEG test not applicable / failed", e)

        # ── Model equation and final description ──────────────────────────
        if m_fit is not None:
            try:
                eq_text = _equation_for_prompt(ts, m_fit)
            except Exception as _eq_exc:
                eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"
            diag_desc = describe_diagnosis(m_fit)
            diag_text = diag_desc.summary + "\n\n---\n" + diag_desc.recommendation
        else:
            eq_text   = "*Modelo no estimado.*"
            diag_text = "*Sin diagnosis disponible.*"

        formal_md = _format_dcd_meg(dcd_results, meg_results)

        # El carril autónomo documenta TAMBIÉN, y con más motivo: aquí no hay
        # analista que note el callejón. Un modelo autónomo sin registro es un
        # resultado del que nadie puede decir por qué salió así.
        #
        # BUG-0032: y documentar la CORRIDA no es documentar el CAMINO. El bucle
        # estima un modelo por ronda, lo diagnostica, y decide DESDE esa diagnosis
        # qué intervención añadir; registrar sólo el último colapsa la búsqueda
        # entera en un punto. El mapa salía con un solo nodo para tres rondas, y
        # la pregunta que el guion existe para contestar —dónde se torció— no
        # tenía dónde leerse.
        #
        # Cada entrada apunta a un fichero que contiene DE VERDAD ese modelo: el
        # `.pre` de la ronda. `output_path` se reescribe en cada vuelta, así que
        # apuntar ahí las entradas intermedias las haría registros falsos, que es
        # peor que no tenerlas.
        guion_note = ""
        if m_fit is not None:
            gpath = guion_path or _derive_guion_path(output_path, m_fit)
            # Los nodos de especificación van PRIMERO y en la misma cadena: son
            # anteriores a cualquier modelo, y sin ellos el guion no puede
            # enseñar dónde se decidió lo que después no se volvió a tocar.
            try:
                _record_spec_nodes(result, overrides, gpath)
            except Exception as e:
                _warn("no se pudieron registrar los nodos de especificación", e)
            # La rama estacional descartada va al mapa como callejón CON su
            # razón. Sin eso, el guion diría que se eligió B1 (o B2) y no que se
            # estimaron las dos y una perdió — que es información distinta, y la
            # que permite discutir la decisión después.
            if result.route and result.branches:
                perdedora = "B2" if result.route == "B1" else "B1"
                rr = result.branches.get(perdedora)
                if rr is not None and rr[1] is not None:
                    try:
                        stem, ext = os.path.splitext(output_path)
                        _record_to_guion(
                            model=rr[1], inp_path=f"{stem}_{perdedora}{ext}",
                            lam=result.lam, guion_path=gpath,
                            name=f"{guion_name or 'auto'}-{perdedora}",
                            decision=(f"Ruta estacional {perdedora} "
                                      f"({'D=0 + armónicos' if perdedora == 'B1' else 'D=1'}), "
                                      f"estimada y descartada"),
                            rationale=result.route_reason,
                            problems_found=_round_problems_text(rr[0][-1]) if rr[0] else "")
                        from art.guion import load_guion, save_guion, abandon
                        g = load_guion(gpath)
                        abandon(g, g.entries[-1].version,
                                why=(f"Rama estacional {perdedora}, estimada para "
                                     f"contrastarla contra {result.route} y "
                                     f"descartada por el par MEG/MA estacional. "
                                     f"{result.route_reason} No volver por aquí "
                                     f"sin un argumento nuevo: repetir la "
                                     f"comparación dará el mismo veredicto."),
                                cascade=False)
                        save_guion(g, gpath)
                    except Exception as e:
                        _warn(f"no se pudo registrar la rama {perdedora}", e)
            stem, _ext = os.path.splitext(output_path)
            ultima_ronda = result.rounds[-1].round_num if result.rounds else None
            for rd in result.rounds:
                es_ultima = (rd.round_num == ultima_ronda)
                try:
                    if es_ultima:
                        ruta, nombre = output_path, guion_name
                        decision_txt = guion_decision or _round_decision_text(rd)
                    else:
                        ruta = f"{stem}_r{rd.round_num}.pre"
                        rd.model.write_pre(ruta)
                        nombre = (f"{guion_name}-r{rd.round_num}" if guion_name
                                  else f"r{rd.round_num}")
                        decision_txt = _round_decision_text(rd)
                    guion_note = _record_to_guion(
                        model=rd.model, inp_path=ruta, lam=lam,
                        guion_path=gpath, name=nombre,
                        decision=decision_txt,
                        rationale=guion_rationale if es_ultima else "",
                        problems_found=_round_problems_text(rd),
                        figure_b64=(diag_desc.figure_b64 if es_ultima else None),
                    )
                except Exception as e:
                    guion_note = f"*guion: no registrado ({type(e).__name__})*"

        text = (
            "\n".join(log)
            + "\n\n" + eq_text
            + "\n\n---\n\n" + diag_text
            + "\n\n---\n\n### Contrastes formales\n\n" + formal_md
            + f"\n\n*Modelo guardado en: {output_path}*"
            + (f"\n\n{guion_note}" if guion_note else "")
            + (_state_footer(m_fit, inp_path=output_path, guion_note=guion_note,
                              guion_path_hint=guion_path or _derive_guion_path(output_path, m_fit))
               if m_fit is not None else "")
        )

        # ── Return: text + one figure per round (Block D) ─────────────────
        items: list = [TextContent(type="text", text=text)]
        for fig_b64 in round_figures:
            items.append(ImageContent(type="image", data=fig_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: batch build (C2)
# ---------------------------------------------------------------------------

@mcp.tool()
def batch_build(inp_paths: list[str], output_dir: str,
                max_rounds: int = 5, run_meg: bool = False,
                objetivo: str = "univariante") -> list:
    """
    Autonomous pipeline for multiple series. Builds one model per series.

    Calls build_model for each inp_path, saves individual .inp files and
    HTML diagnosis reports in output_dir. Returns a summary table and
    individual diagnosis figures.

    Parameters
    ----------
    inp_paths   : list of source .inp paths
    output_dir  : directory where output .inp files and HTML reports are saved
    max_rounds  : maximum intervention rounds per series (default 5)
    run_meg     : run MEG test (slow; default False)
    objetivo    : what the models are FOR -- "univariante" | "multivariante" |
                  "estructural". Applies to EVERY series in the batch, and that
                  is the point: a batch destined for a system (VECM, transfer
                  function, VARMA) must carry `objetivo="multivariante"`, which
                  vetoes the D=1 route so the series share one seasonal
                  treatment and their integration orders stay comparable.
                  Letting each series pick its own best-fitting route is what
                  produces a batch that cannot be assembled.
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        from art.formal_tests import dcd as _dcd

        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        summary_rows = []
        items: list = []

        for raw_path in inp_paths:
            inp = os.path.expanduser(raw_path)
            if not os.path.exists(inp):
                summary_rows.append({"name": os.path.basename(inp),
                                     "error": "fichero no encontrado"})
                continue

            try:
                ts, _ = _load_ts_model(inp)
                name  = ts.name or os.path.splitext(os.path.basename(inp))[0]
                out_inp = os.path.join(output_dir, f"{name}_auto.inp")

                # Same autonomous pipeline as build_model (single source of truth)
                result = run_full(ts, out_inp, max_rounds=max_rounds,
                                  objetivo=objetivo)
                lam, d, D     = result.lam, result.d, result.D
                p, q, n_harm  = result.p, result.q, result.n_harmonics
                m_fit, diag   = result.final_model, result.final_diag
                extra_itvs    = result.interventions
                round_num     = result.rounds[-1].round_num if result.rounds else 0

                # ── Formal tests ──────────────────────────────────────────
                dcd_results = []
                if m_fit is not None:
                    try:
                        dcd_results = _dcd(m_fit)
                    except Exception as e:
                        _warn("DCD test not applicable / failed", e)
                    if run_meg and m_fit.D == 0:
                        try:
                            from art.formal_tests import meg as _meg
                            _meg(m_fit)
                        except Exception as e:
                            _warn("MEG test not applicable / failed", e)

                # ── HTML report ───────────────────────────────────────────
                html_path = os.path.join(output_dir, f"{name}_auto_report.html")
                if m_fit is not None:
                    from art.diagnosis import save_diagnosis_report
                    save_diagnosis_report(m_fit, html_path)

                # ── Diagnosis image for batch output ──────────────────────
                if m_fit is not None:
                    diag_desc = describe_diagnosis(m_fit)
                    if diag_desc.figure_b64:
                        items.append(ImageContent(type="image",
                                                  data=diag_desc.figure_b64,
                                                  mimeType="image/png"))

                # ── DCD non-invertibility check ───────────────────────────
                dcd_flag = ""
                for r in dcd_results:
                    if not r.rejects_5pct:
                        dcd_flag = " ⚠DCD"
                        break

                summary_rows.append({
                    "name": name,
                    "lam": lam, "d": d, "D": D, "p": p, "q": q,
                    "n_harm": n_harm,
                    "n_itv": len(extra_itvs),
                    "rounds": round_num,
                    "clean": "✓" if (diag and diag.clean) else "✗",
                    "dcd": dcd_flag,
                    "html": os.path.basename(html_path),
                })

            except Exception as exc:
                summary_rows.append({"name": os.path.basename(inp),
                                     "error": str(exc)[:120]})

        # ── Summary table ──────────────────────────────────────────────────
        header = "| Serie | λ | d | D | p | q | arm. | interv. | rondas | ok | DCD |"
        sep    = "|-------|---|---|---|---|---|------|---------|--------|----|----|"
        rows   = [header, sep]
        errors = []
        for r in summary_rows:
            if "error" in r:
                errors.append(f"- {r['name']}: {r['error']}")
            else:
                rows.append(
                    f"| {r['name']} | {r['lam']:.0f} | {r['d']} | {r['D']} "
                    f"| {r['p']} | {r['q']} | {r['n_harm']} | {r['n_itv']} "
                    f"| {r['rounds']} | {r['clean']} | {r['dcd'] or '✓'} |"
                )

        n_ok  = sum(1 for r in summary_rows if r.get("clean") == "✓")
        n_tot = len(summary_rows) - len(errors)
        _obj = (objetivo or "univariante").strip().lower()
        obj_line = f"**Objetivo:** {_obj}" + (
            " *(por defecto — nadie lo declaró)*" if _obj == "univariante" else "")

        # Un lote cuyas series NO comparten D no se puede montar en un sistema.
        # Es la consecuencia exacta de dejar que cada serie elija su ruta, así
        # que se avisa aquí y no en la documentación de un parámetro.
        _Ds = {r["D"] for r in summary_rows if "D" in r}
        aviso_D = ""
        if len(_Ds) > 1 and _obj != "multivariante":
            aviso_D = (
                f"\n\n> ⚠ **Las series NO comparten D** ({', '.join(f'D={x}' for x in sorted(_Ds))}). "
                "Cada una ganó por su propio ajuste, que es lo correcto para uso "
                "univariante. Si este lote va a un sistema (VECM, transferencia, "
                "VARMA) sus órdenes de integración no son comparables: relánzalo "
                "con `objetivo=\"multivariante\"`.")

        summary_text = (
            f"## Batch build — {n_ok}/{n_tot} series limpias\n\n"
            + obj_line + "\n\n"
            + "\n".join(rows)
            + aviso_D
            + (("\n\n**Errores:**\n" + "\n".join(errors)) if errors else "")
            + f"\n\n*Informes HTML en: {output_dir}*"
        )
        items.insert(0, TextContent(type="text", text=summary_text))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Block R helpers — forecasting
# ---------------------------------------------------------------------------

def _forecast_date(start: tuple, nobs: int, freq: int, offset: int = 0) -> str:
    """Calendar label for obs index nobs-1+offset (0-based offset from obs nobs)."""
    y0, p0 = int(start[0]), int(start[1])
    total = (p0 - 1) + (nobs - 1) + offset
    if freq == 12:
        return f"{total % 12 + 1:02d}/{y0 + total // 12}"
    if freq == 4:
        return f"Q{total % 4 + 1}/{y0 + total // 4}"
    return str(y0 + total)


def _fuf_path(path: str) -> str:
    """Ensure fuf file path ends with .inp (required by fue.load_fuf)."""
    if not path.endswith(".inp") and not path.endswith(".pre"):
        path += ".inp"
    return path


def _forecast_table(ts, fr, horizon: int, boxlam: float = 0.0) -> str:
    """Markdown table of the forecast values so the LLM can read them directly.

    fr is a fue.ForecastResult: .level (point forecast, original scale),
    .level_std, .seasonal_diff (year-on-year %).  BUG-0008: level_std is the std
    of BoxCox_λ(y), NOT of the level — for λ=0 (log) models it is a RELATIVE s.e.
    (fraction of the level).  Convert to absolute level units with the delta
    method, se_abs = level_std · level^(1−λ) (λ=0 → ·level; λ=1 → unchanged), then
    the 95% band is level ± 1.96·se_abs.
    """
    yoy = getattr(fr, "seasonal_diff", None)
    has_yoy = yoy is not None and len(yoy) == len(fr.level)
    header = ("| # | Fecha | Previsión | IC 95% (±1.96·s.e.) "
              + ("| Δ% interanual " if has_yoy else "") + "|")
    sep    = ("|---|-------|-----------|---------------------"
              + ("|---------------" if has_yoy else "") + "|")
    rows = [header, sep]
    for h in range(horizon):
        date = _forecast_date(ts.start, ts.nobs + 1, ts.freq, h)
        lvl  = float(fr.level[h])
        se   = float(fr.level_std[h])
        se_abs = se * (lvl ** (1.0 - boxlam)) if lvl > 0 else se   # BUG-0008
        lo, hi = lvl - 1.96 * se_abs, lvl + 1.96 * se_abs
        row = f"| {h+1} | {date} | {lvl:.4f} | [{lo:.4f}, {hi:.4f}] "
        if has_yoy:
            row += f"| {float(yoy[h]):+.2f}% "
        rows.append(row + "|")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Tool: generate_forecast — fuf previsión desde modelo estimado  (Bloque R)
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_forecast(inp_path: str,
                      horizon: int,
                      output_fuf_path: str,
                      output_html: str) -> list:
    """
    Generate L-step-ahead forecasts from a fitted model.

    Loads the model from inp_path (fitted .pre), computes forecasts, writes a
    fuf file to output_fuf_path for future updates, and writes the full
    Treadway/Jenkins HTML forecast report (tables + charts) to output_html.

    Parameters
    ----------
    inp_path        : fitted model file (.pre)
    horizon         : number of periods ahead to forecast (e.g. 24)
    output_fuf_path : path to write the fuf input file (for update_and_forecast)
    output_html     : path to write the fue HTML forecast report (required)
    """
    try:
        from mcp.types import TextContent
        import fue as _fue
        from fue.report_forecast import write_forecast_report

        # 1. Fit from .pre → write fuf
        _, m = _load_fitted(inp_path)

        output_fuf_path = _fuf_path(os.path.expanduser(output_fuf_path))
        os.makedirs(os.path.dirname(os.path.abspath(output_fuf_path)), exist_ok=True)
        m.write_fuf(horizon=horizon, path=output_fuf_path)

        # 2. Reload as fuf model → forecast_fuf (correct fuf workflow)
        ts_fuf, m_fuf = _fue.load_fuf(output_fuf_path)
        fr = m_fuf.forecast_fuf()

        # 3. Write HTML report
        output_html = os.path.expanduser(output_html)
        os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
        write_forecast_report(m_fuf, fr, path=output_html,
                              title=ts_fuf.name or "", source=inp_path)

        last_date = _forecast_date(ts_fuf.start, ts_fuf.nobs, ts_fuf.freq, 0)
        end_date  = _forecast_date(ts_fuf.start, ts_fuf.nobs + 1, ts_fuf.freq, horizon - 1)

        table = _forecast_table(ts_fuf, fr, horizon, boxlam=m_fuf.boxlam)

        text = (
            f"## Previsiones — {ts_fuf.name or 'Serie'} "
            f"({last_date} → {end_date}, horizonte={horizon})\n\n"
            f"σ̂_a = {fr.sigma2**0.5:.6f}\n\n"
            + table + "\n\n"
            f"Archivo fuf: {output_fuf_path}\n"
            f"Informe HTML: {output_html}"
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: update_and_forecast — añade observaciones y actualiza previsiones
# ---------------------------------------------------------------------------

@mcp.tool()
def update_and_forecast(fuf_path: str,
                        new_values: list,
                        output_html: str,
                        output_fuf_path: str = "",
                        actual_dates: list = []) -> list:
    """
    Append new observations to a fuf file and update the forecast.

    Loads the fuf file, appends new_values to the series, re-runs the
    forecast (fixed parameters), compares actual observations against the
    previous forecast to report tracking errors, and writes the updated
    Treadway/Jenkins HTML report to output_html.

    Parameters
    ----------
    fuf_path         : existing fuf .inp file (from generate_forecast)
    new_values       : list of new observations in original scale
    output_html      : path to write the fue HTML forecast report (required)
    output_fuf_path  : where to save the updated fuf file (default: overwrites fuf_path)
    actual_dates     : (optional) date labels for new observations ("MM/YYYY")
    """
    try:
        from mcp.types import TextContent
        import fue as _fue
        import numpy as np
        from fue.report_forecast import write_forecast_report

        fuf_path = _fuf_path(os.path.expanduser(fuf_path))
        ts_old, m_old = _fue.load_fuf(fuf_path)
        L_old = m_old._fuf_horizon
        sig2  = m_old._fuf_sigma2

        fr_old  = m_old.forecast_fuf()
        n_new   = len(new_values)
        new_arr = np.array(new_values, dtype=float)

        # Tracking: actual vs previous forecast
        track_lines = []
        for i, actual in enumerate(new_arr):
            if i < len(fr_old.level):
                prev    = fr_old.level[i]
                err_pct = 100.0 * (actual - prev) / prev if prev != 0 else float("nan")
                date_lbl = (actual_dates[i] if actual_dates and i < len(actual_dates)
                            else _forecast_date(ts_old.start, ts_old.nobs + 1,
                                                ts_old.freq, i))
                track_lines.append(
                    f"  {date_lbl}: obs={actual:.4f}  prev={prev:.4f}  "
                    f"err={err_pct:+.2f}%"
                )

        # Build updated series and model (same spec, fixed params)
        new_data = list(ts_old.data) + list(new_arr)
        ts_new   = _fue.TimeSeries(new_data, freq=ts_old.freq,
                                   start=ts_old.start, name=ts_old.name)
        m_new = _fue.Model(
            ts_new,
            ar=m_old.ar, ar_free=m_old.ar_free,
            ma=m_old.ma, ma_free=m_old.ma_free,
            ar_s=m_old.ar_s, ar_s_free=m_old.ar_s_free,
            ma_s=m_old.ma_s, ma_s_free=m_old.ma_s_free,
            ar_f=m_old.ar_f, ma_f=m_old.ma_f,
            d=m_old.d, D=m_old.D, ifadf=m_old.ifadf,
            interventions=m_old.interventions,
            mu=m_old.mu0, estimate_mu=m_old.estimate_mu,
            boxlam=m_old.boxlam,
            # BUG-0007: carry the rescale factor (fuf models are refactor=100);
            # mu0 lives in the rescaled space, so a rebuild at the default
            # refactor=1 reads the drift 100x off and the level explodes.
            refactor=getattr(m_old, "refactor", 1.0) or 1.0,
        )
        fr_new = m_new.forecast_fuf(horizon=L_old, sigma2=sig2)

        out_path = _fuf_path(os.path.expanduser(output_fuf_path or fuf_path))
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        m_new.write_fuf(horizon=L_old, sigma2=sig2, path=out_path)

        output_html = os.path.expanduser(output_html)
        os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
        write_forecast_report(m_new, fr_new, path=output_html,
                              title=ts_new.name or "", source=fuf_path,
                              sps_name=os.path.basename(fuf_path))

        end_date = _forecast_date(ts_new.start, ts_new.nobs + 1, ts_new.freq, L_old - 1)

        track_block = ""
        if track_lines:
            track_block = "\nSeguimiento (actual vs. previsión anterior):\n" + "\n".join(track_lines) + "\n"

        table = _forecast_table(ts_new, fr_new, L_old, boxlam=m_new.boxlam)

        text = (
            f"## Previsiones actualizadas — {ts_new.name or 'Serie'} "
            f"(+{n_new} obs → {end_date})\n"
            + track_block
            + f"\nσ̂_a = {sig2**0.5:.6f}\n\n"
            + table + "\n\n"
            + f"Archivo fuf actualizado: {out_path}\n"
            + f"Informe HTML: {output_html}"
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: sps_dashboard — informe de seguimiento multi-serie
# ---------------------------------------------------------------------------

@mcp.tool()
def sps_dashboard(sps_dir: str, output_dir: str) -> list:
    """
    Generate a sequential prediction (SPS) dashboard for all series in a directory.

    Scans sps_dir for fuf .inp files, generates a fue HTML forecast report
    for each series in output_dir, and writes an index.html with a summary
    table linking to the per-series reports.

    Parameters
    ----------
    sps_dir    : directory containing fuf .inp files (one per series)
    output_dir : directory to write per-series HTML reports and index.html
    """
    try:
        from mcp.types import TextContent
        import fue as _fue
        from fue.report_forecast import write_forecast_report

        sps_dir    = os.path.expanduser(sps_dir)
        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        fuf_files = sorted(
            f for f in os.listdir(sps_dir)
            if f.endswith(".inp") and os.path.isfile(os.path.join(sps_dir, f))
        )
        if not fuf_files:
            return [TextContent(type="text",
                                text=f"No se encontraron archivos .inp en {sps_dir}")]

        entries = []
        for fname in fuf_files:
            fuf_p = os.path.join(sps_dir, fname)
            stem  = os.path.splitext(fname)[0]
            try:
                ts, m = _fue.load_fuf(fuf_p)
                fr    = m.forecast_fuf()

                html_p = os.path.join(output_dir, f"{stem}.html")
                write_forecast_report(m, fr, path=html_p,
                                      title=ts.name or stem,
                                      source=fuf_p,
                                      sps_name=stem)

                last = _forecast_date(ts.start, ts.nobs, ts.freq, 0)
                end  = _forecast_date(ts.start, ts.nobs + 1, ts.freq, fr.horizon - 1)
                entries.append({
                    "name": ts.name or stem,
                    "html": f"{stem}.html",
                    "last": last, "end": end,
                    "horizon": fr.horizon,
                    "level_1": fr.level[0],
                    "diff1_1": fr.diff1[0],
                    "sdiff_1": fr.seasonal_diff[0],
                    "error": None,
                })
            except Exception as exc:
                entries.append({"name": stem, "html": "", "error": str(exc)})

        # Write index.html
        idx_rows = []
        for e in entries:
            if e.get("error"):
                idx_rows.append(
                    f"<tr><td>{e['name']}</td>"
                    f"<td colspan='5' style='color:red'>{e['error']}</td></tr>"
                )
            else:
                sign1 = "+" if e["diff1_1"] >= 0 else ""
                signa = "+" if e["sdiff_1"] >= 0 else ""
                idx_rows.append(
                    f"<tr>"
                    f"<td><a href='{e['html']}'>{e['name']}</a></td>"
                    f"<td>{e['last']}</td><td>{e['end']}</td>"
                    f"<td>{e['level_1']:.4f}</td>"
                    f"<td>{sign1}{e['diff1_1']:.2f}%</td>"
                    f"<td>{signa}{e['sdiff_1']:.2f}%</td>"
                    f"</tr>"
                )
        index_html = (
            "<!DOCTYPE html><html lang='es'><meta charset='utf-8'>"
            "<title>SPS Index</title>"
            "<body style='font-family:sans-serif;max-width:900px;margin:40px auto'>"
            "<h1>SPS — Panel de seguimiento</h1>"
            "<table border='1' cellpadding='6' cellspacing='0' width='100%'>"
            "<tr><th>Serie</th><th>Último dato</th><th>Fin horizonte</th>"
            "<th>Prev₁</th><th>Δ período</th><th>Δ anual</th></tr>"
            + "".join(idx_rows)
            + "</table></body></html>"
        )
        with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)

        n_ok = sum(1 for e in entries if not e.get("error"))
        lines = [
            f"### SPS Dashboard — {n_ok}/{len(entries)} series",
            f"Directorio: {output_dir}",
            "",
        ]
        for e in entries:
            if not e.get("error"):
                lines.append(
                    f"- {e['name']}: {e['last']} → {e['end']}  "
                    f"prev₁={e['level_1']:.4f}  "
                    f"Δ={e['diff1_1']:+.2f}%  ΔA={e['sdiff_1']:+.2f}%"
                )
            else:
                lines.append(f"- {e['name']}: ERROR — {e['error']}")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tools: data ingestion (Excel / CSV → .inp)
# ---------------------------------------------------------------------------

@mcp.tool()
def preview_data(source_path: str, sheet: str = "") -> list:
    """
    Preview the contents of an Excel or CSV file before loading.

    Lists available sheets (Excel), column names, number of rows, detected
    date range and frequency. Use this before load_data to choose the right
    column and confirm that dates are parsed correctly.

    Parameters
    ----------
    source_path : path to .xlsx, .xls, or .csv file
    sheet       : sheet name (Excel only; default = first sheet)
    """
    try:
        import pandas as pd
        from mcp.types import TextContent

        source_path = os.path.expanduser(source_path)
        ext = os.path.splitext(source_path)[1].lower()

        # ── Load ──────────────────────────────────────────────────────────────
        if ext in (".xlsx", ".xls", ".ods"):
            xl = pd.ExcelFile(source_path)
            sheet_names = xl.sheet_names
            sname = sheet if sheet in sheet_names else sheet_names[0]
            df = xl.parse(sname, index_col=0, parse_dates=True)
        elif ext == ".csv":
            sheet_names = ["(CSV — sin hojas)"]
            sname = sheet_names[0]
            df = pd.read_csv(source_path, index_col=0, parse_dates=True)
        else:
            return _err(f"Formato no soportado: {ext}. Usa .xlsx, .xls, .ods o .csv")

        # ── Date detection ────────────────────────────────────────────────────
        idx = df.index
        if isinstance(idx, (pd.DatetimeIndex, pd.PeriodIndex)):
            date_ok = True
            d0 = idx[0]
            d1 = idx[-1]
            # Infer freq
            if hasattr(idx, "freqstr") and idx.freqstr:
                fs = idx.freqstr.upper()
                if fs.startswith(("A", "Y")):  freq_detected = 1
                elif fs.startswith("Q"):        freq_detected = 4
                elif fs.startswith("M"):        freq_detected = 12
                else:                           freq_detected = None
            else:
                # Guess from gap between first two obs
                freq_detected = None
                gap = None
                if len(idx) >= 2:
                    try:
                        gap = (idx[1] - idx[0]).days
                        if gap >= 340:  freq_detected = 1
                        elif gap >= 85: freq_detected = 4
                        elif gap >= 25: freq_detected = 12
                    except Exception as e:
                        _warn("seasonal frequency detection failed", e)
            freq_str = {1: "anual", 4: "trimestral", 12: "mensual"}.get(
                freq_detected, f"desconocida (gap≈{gap if gap is not None else '?'} días)"
            )
            date_info = (
                f"Índice de fechas detectado ✓\n"
                f"  Inicio : {d0}\n"
                f"  Fin    : {d1}\n"
                f"  Frecuencia inferida: {freq_str}"
                + (f" (freq={freq_detected})" if freq_detected else "")
            )
        else:
            date_ok = False
            date_info = (
                "⚠ El índice no contiene fechas reconocibles.\n"
                "  → En load_data deberás indicar freq, start_year y start_period."
            )

        # ── Column summary ────────────────────────────────────────────────────
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        col_lines = []
        for c in numeric_cols:
            s = df[c].dropna()
            col_lines.append(
                f"  {str(c):<30}  n={len(s)}  "
                f"rango=[{s.min():.4g}, {s.max():.4g}]"
                + ("  ⚠ tiene NaN" if df[c].isna().any() else "")
            )

        sheets_info = (
            f"Hojas disponibles: {', '.join(sheet_names)}\n"
            f"Hoja activa: «{sname}»\n"
        ) if ext != ".csv" else ""

        text = (
            f"## Preview: {os.path.basename(source_path)}\n\n"
            + sheets_info
            + f"Filas: {len(df)}   Columnas numéricas: {len(numeric_cols)}\n\n"
            + date_info + "\n\n"
            "**Columnas disponibles:**\n"
            + "\n".join(col_lines)
            + "\n\n---\n"
            "**Próximo paso:** `load_data(source_path, output_inp, column=\"<nombre>\", ...)`"
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def load_data(
    source_path: str,
    output_inp: str,
    column: str,
    series_name: str = "",
    sheet: str = "",
    freq: int = 0,
    start_year: int = 0,
    start_period: int = 1,
) -> list:
    """
    Load a time series from Excel or CSV and write a fue .inp file.

    If the file has a date index (DatetimeIndex), freq and start are inferred
    automatically. If not, you must provide freq, start_year and start_period.

    Parameters
    ----------
    source_path  : path to .xlsx, .xls, .ods or .csv file
    output_inp   : path for the output .inp file (e.g. "cases/IPC_ES/IPC_ES.inp")
    column       : column name to extract (exact match or 0-based integer index)
    series_name  : name for the series in the .inp (default: column name)
    sheet        : sheet name for Excel (default: first sheet)
    freq         : 1=annual, 4=quarterly, 12=monthly  (0 = auto-detect from dates)
    start_year   : start year if no date index (0 = auto-detect)
    start_period : start period within year if no date index (1-based)
    """
    try:
        import pandas as pd
        import fue
        from mcp.types import TextContent

        source_path = os.path.expanduser(source_path)
        output_inp  = os.path.expanduser(output_inp)
        if not output_inp.endswith(".inp") and not output_inp.endswith(".pre"):
            output_inp += ".inp"

        ext = os.path.splitext(source_path)[1].lower()

        # ── Load dataframe ────────────────────────────────────────────────────
        if ext in (".xlsx", ".xls", ".ods"):
            xl = pd.ExcelFile(source_path)
            sname = sheet if sheet in xl.sheet_names else xl.sheet_names[0]
            df = xl.parse(sname, index_col=0, parse_dates=True)
        elif ext == ".csv":
            sname = "(CSV)"
            df = pd.read_csv(source_path, index_col=0, parse_dates=True)
        else:
            return _err(f"Formato no soportado: {ext}")

        # ── Select column ─────────────────────────────────────────────────────
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if column.isdigit():
            idx_col = int(column)
            if idx_col >= len(numeric_cols):
                return _err(f"Índice de columna {idx_col} fuera de rango "
                            f"(hay {len(numeric_cols)} columnas numéricas)")
            col_name = numeric_cols[idx_col]
        elif column in df.columns:
            col_name = column
        else:
            return _err(
                f"Columna «{column}» no encontrada.\n"
                f"Columnas disponibles: {', '.join(str(c) for c in numeric_cols)}"
            )

        series = df[col_name].dropna()
        name   = series_name or str(col_name)

        # ── Build TimeSeries ──────────────────────────────────────────────────
        idx = series.index
        has_dates = isinstance(idx, (pd.DatetimeIndex, pd.PeriodIndex))

        if has_dates:
            ts = fue.TimeSeries.from_pandas(series.rename(name),
                                            freq=freq if freq > 0 else None)
            if freq > 0:
                ts = fue.TimeSeries(ts.data, freq=freq,
                                    start=ts.start, name=name)
            date_note = f"Fechas inferidas del índice."
        else:
            if freq <= 0 or start_year <= 0:
                return _err(
                    "El índice no contiene fechas. Proporciona:\n"
                    "  freq (1/4/12), start_year, start_period"
                )
            ts = fue.TimeSeries(
                series.to_numpy(dtype=float),
                freq=freq, start=(start_year, start_period), name=name
            )
            date_note = f"Fechas asignadas manualmente: inicio {start_year}/{start_period}, freq={freq}."

        # ── Write .inp ────────────────────────────────────────────────────────
        _write_bare_inp(ts, output_inp)

        freq_label = {1: "anual", 4: "trimestral", 12: "mensual"}.get(ts.freq, str(ts.freq))
        begyear, begtime = ts.start
        endtotal = (begtime - 1) + ts.nobs - 1
        if ts.freq == 12:
            end_str = f"{endtotal % 12 + 1:02d}/{begyear + endtotal // 12}"
            start_str = f"{begtime:02d}/{begyear}"
        elif ts.freq == 4:
            end_str = f"Q{endtotal % 4 + 1}/{begyear + endtotal // 4}"
            start_str = f"Q{begtime}/{begyear}"
        else:
            end_str = str(begyear + ts.nobs - 1)
            start_str = str(begyear)

        text = (
            f"## Serie cargada: {name}\n\n"
            f"Fuente : {os.path.basename(source_path)}"
            + (f"  (hoja: {sname})" if ext != ".csv" else "") + "\n"
            f"Columna: {col_name}\n"
            f"Período: {start_str} → {end_str}  "
            f"(n={ts.nobs}, {freq_label})\n"
            f"{date_note}\n\n"
            f"Archivo .inp: `{output_inp}`\n\n"
            "---\n"
            "**Próximo paso:**\n"
            f"```\nguided_identification(inp_path=\"{output_inp}\")\n```"
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: fue .out ASCII report
# ---------------------------------------------------------------------------

@mcp.tool()
def get_out_report(inp_path: str) -> list:
    """
    Return the full fue .out ASCII report for an estimated model.

    Produces the same output as the C 'fue' binary: parameter estimates with
    standard errors, AR/MA polynomials, sigma, log-likelihood, AIC/BIC,
    correlation matrix, residual statistics, outlier table, and ACF of residuals.

    Useful for detailed review of the estimated model beyond what the diagnosis
    summary shows.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the model specification
    """
    try:
        from mcp.types import TextContent
        ts, m = _load_ts_model(inp_path)
        m.fit()
        out_text = m.write_out()
        return [TextContent(type="text", text=f"```\n{out_text}\n```")]
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
