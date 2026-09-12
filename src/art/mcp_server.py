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
import re
import traceback
from typing import Literal

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
from art.identification import desfase_observaciones as _desfase_obs

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
   1) Análisis GUIADO   — tú decides cada nodo; yo te enseño la evidencia, te
      propongo alternativas y paro en cada decisión.
   2) Análisis AUTÓNOMO — yo hago de analista: recorro el mismo protocolo,
      decido cada nodo con su razón por escrito, y te entrego el recorrido
      y el modelo."

Si elige GUIADO → sigue el protocolo guiado.
Si elige AUTÓNOMO → sigue «EL CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA», más
abajo. Recorres los MISMOS nodos que en guiado; lo único que cambia es quién
ocupa la silla del analista.

AUTÓNOMO NO ES build_model. build_model es un atajo heurístico de una llamada
—un auto-ARIMA con las reglas de la escuela—: no sobreparametriza, no mira
Semana Santa, no pasa los contrastes formales ni reformula. Un «autónomo» que
se reduce a esa llamada es un híbrido entre el guiado y un auto-ARIMA: lo peor
de los dos (BUG-0180). Úsalo sólo si el usuario pide expresamente un ajuste
automático sin análisis.

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

  PRESÉNTALAS TAL CUAL: LAS TRES, CON ESOS NOMBRES. No las reformules ni
  añadas otras —«previsión», «ambos», «sin preferencia»—: cada opción es un
  VALOR de `objetivo` (univariante · multivariante · estructural) y art no
  entiende ningún otro. Prever una serie sola es «univariante». Y la razón de
  ser de la lista es la opción 2: es la única que VETA algo —la raíz unitaria
  estacional—, y una lista sin ella no pregunta lo que tiene que preguntar
  (BUG-0183).

  Un renglón de sesgo por opción y nada más: el desarrollo largo lo entrega
  el propio pipeline EN EL NODO ESTACIONAL, que es cuando la decisión se toma.
  Pásalo como objetivo= en guided_identification —la llamada del nodo
  estacional— y en build_model / batch_build si los usas. Ninguna otra
  herramienta lo recibe: a confirm_and_estimate, formal_tests o
  meg_reformulate no se lo pases, porque no lo leen. Si el usuario no contesta
  es "univariante", y DILO al presentar el modelo: un defecto silencioso no se
  puede discutir.

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

  build_model es el ATAJO HEURÍSTICO, no un modo:
   • Sin spec: build_model(inp, out) → la heurística decide todo en una
     llamada. Ajuste automático, no análisis.
   • Con spec (tras guided_identification): build_model(inp, out, lam=…, d=…,
     D=…, p=…, q=…, n_harmonics=…, decision=…). Lo que fijes se respeta; lo
     que omitas lo completa la heurística, y el ciclo de outliers corre solo.
   Usa confirm_and_estimate + suggest_intervention_form para confirmar CADA
   outlier paso a paso —es lo que hace el analista, humano o LLM—; build_model
   con spec, si ya tienes el criterio y quieres cerrar el ciclo de una vez.

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
LO QUE PUEDES PEDIR — los RECURSOS del servidor
══════════════════════════════════════════════════════

Además de las herramientas, este servidor expone documentación que puedes LEER
cuando la necesites. Llega ENTERA, y no ocupa nada mientras no la pidas:

    art://protocolo            este mismo texto, para releerlo a mitad de un
                               análisis largo
    art://defectos             el registro de defectos: qué se ha roto, por qué,
                               y qué sigue abierto
    art://defectos/BUG-0103    un informe concreto, entero
    art://docs                 índice de los documentos de diseño
    art://doc/<NOMBRE>         uno de ellos, entero

CUÁNDO CONSULTAR `art://defectos` — y esto importa más de lo que parece. Cada
informe lleva su causa MEDIDA y la razón por la que se arregló así, o sea que el
registro es **la memoria de por qué el método es como es**.

Míralo antes de proponer una simplificación que parezca obvia: capar un
operador, podar un armónico, fiarte de un error típico, intervenir un residuo
grande. Muchas de esas ideas son razonables a primera vista y están documentadas
como error, con la medición que lo demuestra.

No es hipotético. En una sesión de este mes se propuso sustituir un AR(6) por un
operador disperso porque los módulos de las raíces salían casi iguales — y la
razón por la que eso invierte la lógica del contraste estaba escrita en
`art://defectos/BUG-0103`, que entonces no se podía pedir.

La descripción de una herramienta puede llegarte RECORTADA: el protocolo la
empuja en cada llamada y algunos clientes la truncan. Un recurso no. Si algo de
lo que lees en una descripción parece cortado, o si necesitas el detalle de un
parámetro que sólo ves nombrado, **pídelo aquí**.

══════════════════════════════════════════════════════
NUNCA SE CAPA UN AR SIN FACTORIZAR Y CONTRASTAR ANTES
══════════════════════════════════════════════════════

Si la PACF enseña un pico en el retardo 6, la respuesta NO es estimar
(1 − φ₆B⁶) ni un AR disperso (1 − φ₁B − φ₆B⁶). Es estimar el **AR(6) COMPLETO**
y mirar después qué se sostiene.

POR QUÉ, y no es cuestión de gusto:

  · Un operador en B^N impone que las N raíces tengan **el mismo módulo** y las
    frecuencias **clavadas** en 2πk/N. Eso son N−1 restricciones; el disperso
    (1 − φ₁B − φ_NB^N) son N−2. **Ninguna contrastada.**
  · Un AR(6) puede ser perfectamente un AR(1)×AR(5) con amortiguamientos
    DISTINTOS. Capando de entrada eso deja de ser alcanzable.
  · Y lo peor: **capar de entrada elimina la posibilidad de contrastar
    Shin-Fuller**. La ruta MEG/DCD_f necesita factores con su `d ± SE` y su
    `periodo ± SE`, y un operador ya restringido no los tiene.

QUE UNOS MÓDULOS SALGAN CASI IGUALES ES LA HIPÓTESIS, NO EL HALLAZGO. Es
exactamente el aspecto que tendría un operador en B^N — por eso engaña.
`ar_factorization` avisa cuando ocurre.

Ni el BIC ni las t autorizan a saltárselo: comprar parsimonia imponiendo
restricciones sin contrastar da un modelo estimable, plausible y más simple, que
es la clase de error que sobrevive.

EL PROCEDIMIENTO, en orden:

  1. estimar el AR(p) COMPLETO, sin restringir → base-line;
  2. `ar_factorization` sobre él → factores con d y periodo;
  3. estimar el modelo FACTORIZADO (reparametrización exactamente identificada:
     misma verosimilitud, mismos grados de libertad) → cada factor con su ±SE;
  4. restringir a frecuencia fija el factor cuyo periodo lo admita, y
     contrastarlo por **razón de verosimilitudes**, 1 g.l. por factor;
  5. MEG/DCD_f sobre los que pasen.

Los pasos 3 y 4 se construyen HOY a mano, porque la superficie no expone los
operadores factorizados (art/bugs/BUG-0103). Que sea incómodo no autoriza a
saltárselos: es la diferencia entre contrastar una restricción e imponerla.

══════════════════════════════════════════════════════
EN GUIADO, EL QUE DECIDE ES EL ANALISTA — REGLA DURA
══════════════════════════════════════════════════════

GUIADO NO ES «AUTÓNOMO CONTANDO LO QUE HACE». Es el analista tomando cada
decisión. Si tú decides y luego lo narras, el carril guiado no existe.

Las herramientas del carril guiado devuelven un bloque con CUATRO secciones:

    1 · MODELO ESTIMADO      2 · DIAGNOSIS
    3 · CONCLUSIONES         4 · DECISIÓN — alternativas

y terminan en «⏸ Tu decisión. No sigo hasta que me digas.»

QUÉ HACES CON ESE BLOQUE:

  1. LO MUESTRAS ENTERO Y TAL CUAL. No lo resumas, no lo reordenes, no lo
     reescribas «más claro». Está estandarizado precisamente para que el
     analista sepa dónde mirar sin releerlo entero cada vez.
  2. TU TURNO TERMINA EN ESA MARCA. No escribas nada detrás. Ni un resumen, ni
     «como puedes ver», ni tu recomendación no pedida.
  3. NO LLAMES A NINGUNA HERRAMIENTA MÁS hasta que el analista conteste. Elegir
     por él la alternativa A porque «era la obvia» es exactamente el fallo.
  4. El analista contesta con una letra —«A», «la B»— o con lo suyo propio.
     ENTONCES ejecutas esa alternativa, y sólo ésa.

QUÉ SÍ PUEDES AÑADIR, y sólo si te lo piden: una respuesta a la pregunta que
haga el analista. Si te pide tu opinión, dala en una o dos frases y vuelve a
parar.

POR QUÉ ES REGLA Y NO SUGERENCIA: cuando la salida no está estandarizada y no
termina en una pregunta, el analista tiene que interrumpir el chat para poder
decidir, y se van varios turnos aclarando qué opciones había y con qué
argumentos se ejecutan. Las alternativas vienen ya con su llamada exacta para
que eso no haga falta.

══════════════════════════════════════════════════════
EL CARRIL AUTÓNOMO — TÚ ERES EL ANALISTA
══════════════════════════════════════════════════════
Construyes el modelo DECIDIENDO TÚ SOLO CADA NODO. No hay analista humano que
confirme: cuando art te ofrezca un punto de decisión, decides y sigues.

Eso NO significa ir rápido. Significa que la responsabilidad de cada decisión
es tuya y que tienes que dejarla razonada por escrito.

Esta sección consolida lo que se midió en el estudio con varios LLM haciendo de
analista (réplica del TFM y SF_MEG, 31 series, 283 nodos decididos por el LLM).
Hasta 0.2.1 vivía en el enunciado de cada ejercicio y no aquí, y sin enunciado
el autónomo se reducía a una llamada a build_model (BUG-0180).

LOS NODOS — los mismos que en guiado, en el mismo orden, UNO POR VEZ:
  1. dominio        qué CLASE de serie es. Antes de λ: la clase gobierna la
                    regla de la transformación.
  2. lambda         guided_identification(inp_path)
  3. d              guided_identification(inp_path, lam=X)
  4. estacionalidad guided_identification(inp_path, lam=X, d=Y, objetivo=…)
  5. media          ¿μ libre o fijada en cero?
  6. modelo base    confirm_and_estimate(..., modo="autonomo") sin ARMA. Mira
                    el escaneo de anómalos que viene en la salida.
  7. intervenciones si los anómalos distorsionan la identificación, ANTES de
                    (p,q). Una cada vez.
  8. ordenes        guided_identification(..., pre_path=<último .pre>)
  9. contrastes     formal_tests(...), SÓLO con la diagnosis limpia.
 10. reformulación  si un contraste manda cambiar algo, vuelve al nodo que
                    corresponda. Volver atrás es el método funcionando.

NUNCA DECIDAS NODOS EN LOTE. Decidir λ, d y la estacionalidad de una tacada
aplana el bucle en una pasada hacia delante: tomas las decisiones antes de que
exista el residuo que podría corregirlas. En el estudio bastó escribir esta
regla para que los nodos en lote cayeran de 8 a 0.

EL CARRIL SE DECLARA EN CADA LLAMADA: modo="autonomo" en confirm_and_estimate,
estimate_and_diagnose y build_model. Sin él la salida es la del guiado y
termina en ⏸. Si en autónomo te llega un ⏸ es que te lo dejaste: NO preguntes
al usuario —no hay nadie esperando—; repite la llamada con modo="autonomo".

REGLAS:
  - La recomendación de art es EVIDENCIA, no una orden. Si el correlograma dice
    una cosa y la lista otra, manda lo que puedas defender, y di por qué.
  - Lee los párrafos, no sólo la línea de la recomendación: varias salidas
    matizan su propia sugerencia unas líneas más abajo.
  - Un empate se resuelve ESTIMANDO, no eligiendo. A menos de ~0,05 de
    similitud o ~2 de AIC, estima los dos, decide con los dos delante y marca
    el perdedor como callejón.
  - Un contraste formal sobre un modelo inadecuado no es un contraste débil:
    no es un contraste.
  - Los anómalos se calibran, no se eliminan.
  - No añadas un parámetro no significativo para cerrar un criterio.
  - NO USES RAMPAS. Una rampa en el nivel es una tendencia determinista desde
    su fecha: la previsión hereda esa pendiente para siempre y la banda no
    recoge incertidumbre sobre ella. Si ves un cambio en la tasa media de
    crecimiento, la pregunta es de ORDEN DE INTEGRACIÓN: vuelve al nodo d y
    contrasta la alternativa estocástica, o acota la ventana muestral. En
    autónomo suggest_intervention_form la rechaza (BUG-0182).
  - CON OBJETIVO MULTIVARIANTE, LA ESTACIONALIDAD QUEDA DETERMINISTA. El MEG
    puede clasificar una frecuencia como estocástica, pero no reformules: ni
    D=1 ni ifadf[f]=1. formal_tests y meg_reformulate no conocen el objetivo,
    así que esta regla la llevas tú (BUG-0183).

DOCUMENTACIÓN — obligatoria. Después de CADA nodo:

    guion_node(guion_path, nodo="<dominio|lambda|d|estacionalidad|media|
               ordenes|intervenciones|reformulacion>",
               decidido="<el valor>", razon="<POR QUÉ>",
               evidencia="<los estadísticos concretos>",
               alternativas="<qué descartaste y por qué>",
               decidido_por="LLM")

  Pasa guion_path y guion_name a confirm_and_estimate y a
  suggest_intervention_form. Una rama descartada se marca con
  guion_abandon(guion_path, version, why=…): lo que una iteración fallida
  produce de valor no es el modelo que se tira, es el motivo.

AL TERMINAR: el modelo final (su terna .inp/.pre/.out), los nodos que más te
costó decidir, y aquellos en que fuiste EN CONTRA de lo que recomendaba art,
con la evidencia.

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

  LA PUERTA DEL NODO ES guided_intervention. Igual que guided_identification en
  la etapa 1: una entrada, la secuencia documentada, y UN veredicto por llamada.
  El nodo tiene nueve instrumentos y elegir a ciegas entre ellos es cómo se
  sobre-interviene.

    Llamada 1  guided_intervention(inp)                    ¿HAY QUE INTERVENIR?
      Calibra el correlograma OMITIENDO los anómalos y dice si la identificación
      cambia: qué órdenes AR (PACF) y MA (ACF) entran o salen. Si NO cambia nada,
      lo dice y avisa de que intervenir ahí es sobre-intervenir. Devuelve las
      fechas candidatas. ESPERA al analista: qué fecha, o parar.

    Llamada 2  guided_intervention(inp, date=…)            ¿QUÉ FORMA?
      Episodio + configuraciones que el dato admite + escalera de Ockham, en UNA
      respuesta y con un veredicto. Si el dato NO identifica la configuración, lo
      dice y pide lo extramuestral en vez de elegir por AIC. ESPERA al analista.

    Llamada 3  guided_intervention(inp, date=…, form=…, n_omega=…, output_path=…)
      CONSTRUYE la forma elegida, estima, y verifica Treadway (¿queda un vecino
      anómalo?) y la ganancia (Wald sobre ω(1)=0: ¿permanente o transitorio?).

  ⚠ EL CRITERIO DE PARADA. Cada intervención encoge σ̂, con lo que el siguiente
    residuo sube de |z| y pide su turno: la escalada NO se detiene sola. Se para
    cuando la calibración deja de decir que los anómalos cambian la
    identificación — que es lo que contesta la llamada 1.

  ⚠ EL CONVENIO DE SIGNO de la FLT. fue guarda ω(B) = ω₀ − ω₁B − ⋯ (Box-Jenkins,
    el mismo para TODO operador): los retardos RESTAN, así que la ganancia es
    ω₀−ω₁−⋯ y NO la suma. No hagas la resta a mano: la respuesta trae el CAMINO
    DEL NIVEL que producen esos ω. Si no es el que tenías en la cabeza, el signo
    estaba mal — y lo ves antes de estimar.

  INSTRUMENTOS SUELTOS del nodo, para mirar algo concreto sin avanzar el flujo:
    residual_outlier_scan       los anómalos de un modelo ya estimado + la
                                calibración ACF/PACF
    preliminary_outlier_scan    los anómalos de una serie aún sin modelo
    residual_episodes           cómo se agrupan los extremos en sucesos
    incident_configurations     qué configuraciones del incidente admite el dato
                                — GOBIERNA sobre residual_episodes para la FORMA:
                                extiende el arranque por el mecanismo, el otro
                                sólo agrupa extremos
    intervention_ladder         los peldaños de Ockham con sus razones
    intervention_plot           superpone una respuesta impulso sobre los datos
    intervention_analysis       los anómalos antes de decidir nada
    suggest_intervention_form   añade UNA intervención con forma y orden dados
    test_interventions          si las que ya están se sostienen (t, Wald, Treadway)

  → Si prefieres el paso a paso clásico: suggest_intervention_form una a una
    (con n_omega para una FLT de varios ω) → MUESTRA la diagnosis actualizada.
  → Cuando el modelo parezca limpio: test_interventions.

RAMPA — INSTRUMENTO DE USUARIO AVANZADO (BUG-0182). Una rampa en el nivel
es un escalón pasado por 1/(1−B): ganancia infinita, tendencia determinista
desde su fecha. Con d=1 es un escalón en la tasa de crecimiento; sobre un
índice de precios, fijar para siempre un cambio en la inflación tendencial.
La previsión hereda esa pendiente sin fecha de caducidad y la banda no
recoge incertidumbre sobre ella. Si la fecha sale de mirar los datos, los
contrastes de orden de integración posteriores no tienen sus críticos
habituales (Zivot-Andrews). Proponla sólo si el analista la pide o la
defiende, y enséñale el aviso con sus cifras: sale en la propia salida.

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
EL GUION — EL GRAFO, Y CÓMO SE VUELVE ATRÁS
══════════════════════════════════════════════════════
El método iterativo es una búsqueda CON VUELTA ATRÁS: tiene callejones sin
salida, y un callejón es el método funcionando, no fallando. Lo que una
iteración fallida produce de valor NO es el modelo que se descarta: es la RAZÓN,
que es lo único que impide volver a intentarlo.

El guion se escribe SOLO en cada estimación. No hay que pedirlo.

  guion_map(guion, version=N)   EL MAPA. Quién desciende de quién, qué se adoptó,
                                qué es callejón y por qué, y cuál es el ancestro
                                seguro al que volver. Avisa además cuando el
                                registro no se puede releer entero: entradas con
                                otra versión del instrumento, con otra ESCALA de
                                ℓ/AIC, o sin sus artefactos en disco.
  guion_evidencia(guion, N)     LA EVIDENCIA de ese nodo, y es la pareja del
                                mapa: el mapa dice A DÓNDE volver, esto dice QUÉ
                                HAY allí. Ecuación con sus errores típicos
                                LEÍDOS DEL .out, la diagnosis registrada (Q con
                                sus retardos y p-valores, JB, anómalos), y las
                                figuras (residuos + ACF/PACF, e histograma).
                                ⚠ NO REESTIMA. Si necesitas ver el último modelo
                                para decidir el camino siguiente, ES ESTA — no
                                vuelvas a estimar: cuesta llamadas y tokens, y
                                el registro ya lo tiene todo.
  guion_node(...)               registra un nodo de DECISIÓN (λ, d, estacional,
                                órdenes): lo que se decidió y por qué, antes de
                                que exista el primer modelo.
  guion_abandon(...)            marca un callejón con su razón; poda en cascada.
  guion_diff(a, b)              compara DOS recorridos nodo a nodo. Es lo que
                                hace comparables dos análisis en vez de dos
                                listas parecidas.
  export_guion(guion)           todo el recorrido en HTML navegable.
  record_version(...)           registra a mano un modelo estimado por otra vía.

══════════════════════════════════════════════════════
INSTRUMENTOS DE APOYO — no avanzan el flujo
══════════════════════════════════════════════════════
Se usan para mirar algo concreto. Ninguno sustituye a un nodo del protocolo.

  DATOS      load_data · preview_data · series_info · create_inp
             verify_optimum — VERIFICA el óptimo de un `.pre` perturbando UNA
             desviación típica y comparando ℓ; saca las SE de la semilla del
             BFGS sin salir de la cuenca. **Nunca pongas las semillas a 0 para
             esto: puede caer en otro óptimo y destruye el convenio del `.pre`.**
             extend_sample — MÁS observaciones sobre el MISMO modelo, para
             validarlo contra lo que vino después o incorporar un episodio
             nuevo sin rehacer la identificación. No reestima.
  MODELO     estimate_and_diagnose (estima un .inp y persiste .inp/.pre/.out +
             guion) · model_equation_display · model_histogram
  REGISTRO   get_out_report — LEE el .out de un modelo estimado; es de donde
             salen los errores típicos, NUNCA de reejecutar un .pre
  COMPARAR   compare_versions (avisa y suprime el Δ si no son comparables:
             distinto operador de diferenciación o distinta escala)
  ESTRUCTURA ar_factorization · overparameterization_analysis ·
             seasonal_param_analysis · test_seasonal_simplification
  ESTACIONAL meg_frequency (una frecuencia) · meg_reformulate (aplica ifadf[f]=1)
  INFORMES   full_report · sps_dashboard · save_identification_report
  PREVISIÓN  generate_forecast · update_and_forecast — LEE «EL CONVENIO DEL
             FUF» más abajo antes de usarlas: la previsión tiene contrato
             propio, distinto del de la estimación.

══════════════════════════════════════════════════════
EL CONVENIO DEL FUF — LA PREVISIÓN TIENE CONTRATO PROPIO
══════════════════════════════════════════════════════
Prever NO es estimar, y el fichero con el que se prevé no es el mismo con el
que se estima. `fuf` es un PROGRAMA aparte —no una función de fue— con su
propio trío, paralelo al de `fue`:

  fue <modelo> -f <H>    →  forecast_<modelo>.inp   el fuf: parámetros FIJOS,
                                                    horizonte y σ² dentro
  fuf <forecast_modelo>  →  forecast_<modelo>.out   el REGISTRO de la previsión
                            …_forecast.png          la figura
                            …<modelo>.html          el informe

LO QUE HAY QUE SABER, Y NO SE DEDUCE MIRANDO:

1. UN FUF ES UN `.inp` MÁS UNA SECCIÓN. Lleva dentro
   `** Forecast horizon and estimated innovation variance` con L y σ². Por eso
   la extensión es `.inp` y no `.fuf`: `fue.load()` lo detecta por esa clave y
   `load_fuf` la exige. El prefijo `forecast_` NO es decorativo — es lo único
   que distingue por el nombre un fuf de una especificación, y `load_fuf` lo
   quita para recuperar el nombre del modelo.

2. LOS PARÁMETROS VAN FIJOS. `forecast_fuf` no reestima: lee los valores como
   están y calcula los residuos en una pasada. Eso es lo que hace comparables
   dos previsiones hechas en momentos distintos, y es la razón de que el fuf
   guarde σ² en vez de recalcularlo.

3. PREVER NO ES UN NODO DEL MÉTODO. Se prevé DESPUÉS de adoptar un modelo, y
   una previsión no se mete en el guion como una iteración: no hay decisión
   que registrar porque no se ha elegido nada.

4. LA BANDA QUE VES NO ES LA QUE DEVUELVE EL MOTOR. `level_std` está en
   unidades Box-Cox, no de nivel; art aplica el método delta —se = level_std ·
   nivel^(1−λ)— antes de dar el IC 95%. En un modelo en logaritmos, leer
   `level_std` como si fuese absoluto es un error de escala (BUG-0008).

5. LO QUE ART NO HACE HOY, Y CONVIENE QUE SEPAS: no escribe el `.out` de la
   previsión —`write_fuf_out`, el registro— ni nombra el fuf con el prefijo
   `forecast_`. Deja el fuf y el HTML. Si necesitas el registro en el formato
   de la escuela, hoy hay que pasar por el programa `fuf`.

6. COMPARAR MODELOS POR PREVISIÓN NO ES UNA HERRAMIENTA DE ART. Elegir entre
   dos modelos por su error fuera de muestra —varios orígenes, parámetros
   fijos, RMSE por horizonte, Diebold-Mariano— no está en la suite: hoy se
   hace con arneses a mano. No lo mejores improvisando uno y presentando el
   resultado como si saliera de art.

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
- En GUIADO, NUNCA encadenes pasos sin mostrar el gráfico y esperar confirmación
  del usuario. En AUTÓNOMO los encadenas tú, un nodo cada vez y registrándolo.
- confirm_and_estimate construye el INP del modelo — nunca busques ficheros .inp.
- En GUIADO las decisiones (λ, d, D, p, q) son del USUARIO, no tuyas. En
  AUTÓNOMO son tuyas, y por eso cada una va razonada en el guion.
"""

# EL ENUM VIAJA EN EL ESQUEMA — BUG-0155.
#
# `evento_naturaleza` se publicaba como `{"type": "string"}` a secas: ni
# descripción ni valores. El único sitio donde estaban era la prosa del
# docstring, que el cliente puede recortar (BUG-0116), así que el valor válido
# se aprendía POR EL MENSAJE DE ERROR — y en la corrida de ITCER el analista
# metió la frase entera y se la rechazaron.
#
# Un `Literal` no es prosa: FastMCP lo convierte en `"enum": [...]` y el cliente
# no puede ni construir la llamada mal. Es la diferencia entre documentar una
# regla y que el sistema la tenga.
_Naturaleza = Literal["", "permanente", "transitorio", "recuperacion_parcial"]

#: EL CARRIL, en el esquema — BUG-0181. `guiado`: decide el analista humano y la
#: salida para en ⏸ a esperarle. `autonomo`: el LLM ES el analista —recorre los
#: mismos nodos y decide él— y la salida no para, porque no hay nadie a quien
#: esperar. Va como enum y no como texto libre por lo mismo que `_Naturaleza`
#: (BUG-0155): un valor que el cliente puede escribir mal es un valor que acaba
#: cayendo en el defecto sin que nadie lo vea.
_Modo = Literal["guiado", "autonomo"]

#: PARA QUÉ ES EL MODELO, en el esquema — BUG-0183. Viajaba como texto libre y
#: la política convertía en silencio cualquier valor desconocido en
#: «univariante»: un asistente que ofreció «Previsión / Estructural / Ambos» y
#: pasó lo que eligió el usuario obtenía un objetivo que nadie había elegido. Y
#: el único valor que VETA algo —«multivariante», que prohíbe la raíz unitaria
#: estacional porque rompe la comparabilidad de los órdenes de integración— es
#: justo el que se perdió.
_Objetivo = Literal["univariante", "multivariante", "estructural"]


def _modo_del_sobre(modo: str) -> str:
    """Lo que `envuelve_iteracion` recibe: «guiado» para, «autónomo» sigue."""
    return "guiado" if (modo or "guiado") == "guiado" else "autónomo"

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

    def _pesa_entrada(args, kwargs) -> int:
        """Bytes de los ARGUMENTOS — ORDEN 0.3.

        Se medía sólo lo que sale. Pero el coste de una llamada tiene dos
        mitades y la de entrada es la que el analista controla: una ruta larga,
        un `omitir` con cincuenta índices, un `label` de tres líneas. Sin ella
        no se puede decir si un carril es más caro por lo que pide o por lo que
        recibe.
        """
        try:
            return len(_json.dumps([args, kwargs], ensure_ascii=False,
                                   default=str).encode("utf-8"))
        except Exception:                        # pragma: no cover
            return 0

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
    _res_orig = mcp.resource

    def _contado(deco_orig, clase):
        """El MISMO envoltorio para herramientas y recursos — ORDEN 0.3.

        `mcp.resource` no se envolvía, así que **el uso de recursos no era
        medible**: la hipótesis de MATERIAL §6 es que es cero, y no había forma
        de comprobarlo. Y el bloque entero vivía DESPUÉS de los `@mcp.resource`,
        así que aunque se hubiera envuelto habría llegado tarde. Por eso ahora
        va inmediatamente detrás de crear el servidor.
        """

        def _decorador(*a, **kw):
            deco = deco_orig(*a, **kw)
            return _envuelve(deco, clase)
        return _decorador

    def _envuelve(deco, clase):
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
                            "clase": clase,
                            "tool": fn.__name__,
                            "ms": round((_time.perf_counter() - t0) * 1000, 1),
                            "bytes_recibidos": _pesa_entrada(args, kwargs),
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

    mcp.tool = _contado(_tool_orig, "tool")
    mcp.resource = _contado(_res_orig, "resource")



# ---------------------------------------------------------------------------
# RECURSOS — lo que el modelo PIDE, frente a lo que se le empuja
# ---------------------------------------------------------------------------
#
# La documentación de art se entregaba por un solo canal: la descripción de cada
# herramienta, que el protocolo empuja EN CADA LLAMADA. Son 75.548 caracteres en
# 46 herramientas y un cliente real entregó al modelo el 23%, o sea que se
# perdían ~58.000 caracteres por sesión — entre ellos la documentación de
# `easter`, la de `ar_f_freqs` y la de Shin-Fuller (BUG-0116).
#
# Acortar no era el arreglo: el texto hace falta. Lo que estaba mal era el
# canal. MCP tiene un primitivo para esto —los recursos, que se piden cuando
# hacen falta y llegan enteros— y art usaba CERO.
#
# Lo que va aquí es lo que se consulta, no lo que se decide: la referencia, el
# procedimiento y la memoria de POR QUÉ las cosas se hacen así.

@mcp.resource("art://defectos")
def _r_defectos() -> str:
    """El registro de defectos de ART: qué se ha roto, por qué, y qué sigue
    abierto. Cada informe lleva su causa MEDIDA y la razón del arreglo.

    Consúltalo antes de proponer una simplificación que parezca obvia —capar un
    operador, podar un armónico, fiarte de un error típico—: puede estar ya
    documentada como error, con su medición."""
    from art.recursos import indice_de_defectos
    return indice_de_defectos()


@mcp.resource("art://defectos/{bug_id}")
def _r_defecto(bug_id: str) -> str:
    """Un informe entero, por identificador (`BUG-0097` o `0097`)."""
    from art.recursos import informe_de_defecto
    return informe_de_defecto(bug_id)


@mcp.resource("art://docs")
def _r_docs() -> str:
    """Índice de los documentos de diseño: el contrato de ficheros, el nodo de
    intervención, la arquitectura, las lecciones de la réplica."""
    from art.recursos import indice_de_documentos
    return indice_de_documentos()


@mcp.resource("art://doc/{nombre}")
def _r_doc(nombre: str) -> str:
    """Un documento de diseño entero, por nombre y sin extensión."""
    from art.recursos import documento
    return documento(nombre)


@mcp.resource("art://protocolo")
def _r_protocolo() -> str:
    """El protocolo completo y la doctrina del método, entero.

    Es el mismo texto que el servidor entrega como `instructions`, expuesto
    también aquí para poder RELEERLO a mitad de un análisis sin depender de que
    siga en la ventana."""
    return _INSTRUCTIONS



# Execution layer (model construction, .inp I/O, fit and the autonomous loop)
# lives in art.pipeline; the MCP tools below import its primitives + entry points.
from art.pipeline import (
    # Las tres operaciones del contrato de ficheros (estudio §6-B):
    #   estimar   exige `.inp`, promete SE válidas    → 14 herramientas
    #   mirar     acepta `.pre`, no promete SE        → 3 herramientas
    #   lee_out   el registro, sin motor (art.outfile)
    # El sitio que llama declara lo que necesita, y por eso `mirar` no avisa:
    # no promete nada que un `.pre` estropee.
    _load_ts_model, _write_bare_inp, _load_fitted, mirar as _mirar, _obs_to_date,
    _write_inp, _build_arma_on_model, _make_model,
    ModelSpec, FitResult, build_and_fit, run_full,
    _RESCALE_FACTOR,
)
# Decision rules + centralised thresholds (single source of truth).
from art import policy

_Z_USER = policy.THRESHOLDS["outlier_user"]  # user-facing scan default (3.5)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Registro de figuras escritas en esta sesión: huella del CONTENIDO → ruta.
#
# BUG-0081. `_result` publicaba `_ULTIMA_FIGURA`, una global mutable, en vez de
# la ruta de la figura que esa llamada está devolviendo: con llamadas
# intercaladas, la respuesta de una herramienta citaba el fichero de otra. Y la
# nota de la ruta existe precisamente para cuando la ventana no aparece, así que
# la red de seguridad fallaba igual que aquello que venía a cubrir.
#
# Se indexa por contenido y no por etiqueta porque es lo único que identifica a
# la figura sin cambiar las ~40 llamadas: `_result` sólo tiene el `figure_b64`.
_FIGURAS: dict[str, str] = {}
_FIGURAS_TOPE = 256


#: True cuando el módulo corre COMO SERVIDOR MCP — lo pone `main()`, que es el
#: único sitio por donde se entra en ese modo. Existe porque `_show_fig` tenía
#: que distinguir tres contextos y sólo conocía dos: la suite y el apagado
#: explícito. El tercero es éste, y ahí la ventana del escritorio no debe
#: abrirse (BUG-0111). Importar el módulo como biblioteca lo deja en False, que
#: es lo correcto: un guion o un cuaderno sí quieren ver la figura.
_BAJO_SERVIDOR = False


def _huella_figura(b64: str) -> str:
    import hashlib
    return hashlib.sha1(b64.encode("ascii", "ignore")).hexdigest()[:12]


def _registra_figura(b64: str, path: str) -> None:
    if not (b64 and path):
        return
    _FIGURAS[_huella_figura(b64)] = path
    while len(_FIGURAS) > _FIGURAS_TOPE:
        _FIGURAS.pop(next(iter(_FIGURAS)))


def _imagen(b64: str, etiqueta: str = "art"):
    """Convierte una figura en `ImageContent` **y la escribe**.

    Único sitio del módulo donde nace un `ImageContent`, y por eso escribir no
    se puede olvidar: el olvido era el defecto.

    BUG-0122. Veintitrés sitios construían el `ImageContent` a mano, y quince de
    las veintiocho herramientas que devuelven figura no llamaban a `_show_fig`
    en ninguna rama: su figura viajaba SÓLO como imagen en la respuesta. Sin
    fichero, sin ventana y sin ruta que citar — y la herramienta reportando
    éxito. `_result` tampoco la salvaba: BUSCA la huella en `_FIGURAS` por si
    otro la escribió, y si nadie lo hizo se calla y no cita ninguna.

    Se vio en vivo en el escaneo de anómalos del m00 de RATIO (réplica de
    Bolivia, run5 guiado): el panel que descompone la ACF en «parte debida al
    outlier» —la evidencia del punto de decisión— llegó sin ventana y sin ruta,
    justo cuando el analista tenía que decidir si intervenir antes del ARMA.

    `_show_fig` discrimina por CONTENIDO (BUG-0081), así que llamarla de más no
    duplica nada: la misma figura da el mismo fichero.
    """
    from mcp.types import ImageContent
    _show_fig(b64, etiqueta)
    return ImageContent(type="image", data=b64, mimeType="image/png")


def _result(desc) -> list:
    """Convert a Description to MCP content list (text + optional image).

    BUG-0078: la nota con la RUTA de la figura va aquí, que es por donde pasan
    todas las herramientas. Sin ella, cuando la ventana del visor no aparece no
    hay nada a lo que agarrarse — y la herramienta reporta éxito igual.

    BUG-0081: la ruta se busca por el CONTENIDO de esta figura, no en la global
    `_ULTIMA_FIGURA`. Si esta figura no se escribió, no se cita ninguna: mejor
    ninguna nota que una que apunta al fichero de otra serie.
    """
    from mcp.types import TextContent, ImageContent
    txt = desc.summary + "\n\n---\n" + desc.recommendation
    if desc.figure_b64:
        # BUG-0122: ESCRIBIRLA, no sólo buscarla. Buscar la huella supone que
        # alguien la escribió antes, y quince herramientas no lo hacían nunca.
        _ruta = _escribe_fig(desc.figure_b64) or _FIGURAS.get(
            _huella_figura(desc.figure_b64), "")
        if _ruta:
            # LA RUTA VA ANTES DE LA MARCA DE FIN DE TURNO, no detrás.
            #
            # Dos arreglos correctos que chocaban: BUG-0113 exige que la ruta se
            # DIGA —sin ella, con el visor apagado y un cliente que no renderice,
            # el analista se queda sin nada—, y BUG-0094 exige que la salida
            # guiada TERMINE en la pregunta, porque esa marca es lo que hace
            # comprobable que la herramienta para y no decide por él.
            #
            # Añadirla al final rompía el segundo: la última línea pasaba a ser
            # una nota de fichero, y el turno dejaba de cerrar donde debía. La
            # ruta es parte de la evidencia, así que su sitio está DENTRO del
            # sobre, delante de la decisión.
            txt = _con_nota_figura(txt, _ruta)
    items = [TextContent(type="text", text=txt)]
    if desc.figure_b64:
        items.append(_imagen(desc.figure_b64, "result"))
    return items


def dominio_declarado(domain: str) -> str:
    """El dominio que declara el analista, validado. `""` si no declaró — BUG-0178.

    UNA COPIA, DOS CAMINOS — y aquí eran tres puertas y dos copias. `domain`
    decide λ (`policy.decide_lambda`: un índice va en log SIEMPRE, su base es
    una convención), así que un valor que la política no reconoce no es un
    detalle de forma: cae a `decide_domain`, el estadístico decide, y sobre un
    índice de precios eso da λ=1 donde la regla dice λ=0.

    `guided_identification` y `confirm_and_estimate` ya rechazaban lo no
    reconocido. `build_model` —la puerta del carril AUTÓNOMO— no, y ahí el
    valor entraba, se anunciaba como si se hubiera aplicado y el modelo salía
    en niveles. Es exactamente la lección de BUG-0015 repetida: la regla vive
    en `policy`, y tenerla sólo en unas capas es lo que parte una familia de
    series entre logs y niveles.

    Levanta `ValueError` para que cada puerta lo convierta en su `_err`.
    """
    d = (domain or "").strip()
    if d and d not in policy.DOMINIOS:
        raise ValueError(f"domain={d!r} no es un dominio reconocido. "
                         "Usa uno de: " + ", ".join(policy.DOMINIOS))
    return d


def objetivo_declarado(objetivo: str) -> str:
    """El objetivo, validado — BUG-0183. Mismo patrón que `dominio_declarado`.

    `policy.decide_seasonal_route` cae a «univariante» ante cualquier valor que
    no reconoce, y así se queda para quien la llame directamente. Pero por las
    puertas de art no puede entrar un objetivo que nadie eligió: se rechaza
    diciendo cuáles valen.
    """
    o = (objetivo or "").strip().lower()
    if not o:
        return policy.OBJETIVO_POR_DEFECTO
    if o not in policy.OBJETIVOS:
        raise ValueError(
            f"objetivo={objetivo!r} no es un objetivo de art. Usa uno de: "
            + ", ".join(policy.OBJETIVOS) + ". «multivariante» es el que "
            "fuerza estacionalidad determinista; no hay objetivo «previsión»: "
            "prever una serie sola es «univariante».")
    return o


def aviso_rampa(model) -> str:
    """Lo que una RAMPA le hace a la previsión, con sus números — BUG-0182.

    Una rampa en el nivel es un escalón pasado por un integrador,
    R_t = S_t/(1−B): el límite δ=1 de la forma racional ω/(1−δB). Su ganancia
    es infinita y su efecto sobre el nivel crece sin cota — es una TENDENCIA
    DETERMINISTA desde la fecha. Con d=1 equivale a un escalón en la tasa de
    crecimiento: sobre un índice de precios, a fijar para siempre un cambio en
    la inflación tendencial.

    La función de previsión la hereda sin fecha de caducidad, y la banda no
    recoge ninguna incertidumbre sobre ella: es determinista y entra como
    conocida. En el run 6 de IPC_ES una rampa de −0,204 %/mes en 07/2008 fijó la
    inflación de largo plazo en 0,94 % anual, un −8,8 % de nivel a diez años
    frente al modelo sin ella, con una banda un tercio de la que daría la
    alternativa estocástica a esa distancia.

    Devuelve "" si el modelo no lleva rampas.
    """
    try:
        from art.interventions import _intervention_param_start
        itvs = list(getattr(model, "interventions", None) or [])
        rampas = [(i, it) for i, it in enumerate(itvs)
                  if str(getattr(it, "type", "")).lower() == "ramp"]
        if not rampas:
            return ""
        import numpy as _np
        r = getattr(model, "_result", None)
        # NUNCA `x or []` sobre algo que puede ser un array de numpy: su verdad
        # es ambigua y revienta — BUG-0158 y BUG-0174 fueron exactamente esto.
        _p = getattr(r, "params", None) if r is not None else None
        params = [float(x) for x in _np.ravel(_p)] if _p is not None else []
        freq = int(getattr(model.series, "freq", 1) or 1)
        lam = getattr(model, "boxlam", None)
        refac = float(getattr(model, "refactor", 1.0) or 1.0)
        en_pct = (lam is not None and float(lam) == 0.0 and refac == 100.0)
        u = "%" if en_pct else " (unidades de la serie transformada)"
        filas = []
        for i, it in rampas:
            om = None
            _omf = getattr(it, "omega_free", None)
            omf = [bool(x) for x in _np.ravel(_omf)] if _omf is not None else [True]
            if params and (not omf or omf[0]):
                k = _intervention_param_start(model, i)
                if k < len(params):
                    om = float(params[k])
            _om = getattr(it, "omega", None)
            if om is None and _om is not None and _np.size(_om) > 0:
                om = float(_np.ravel(_om)[0])
            try:
                yr, per = model.series._obs_to_date(int(it.at) + 1)
                fecha = f"{per:02d}/{yr}" if freq > 1 else str(yr)
            except Exception:
                fecha = f"obs {int(it.at) + 1}"
            if om is None:
                filas.append(f"   · rampa en {fecha}: ω aún sin estimar")
            else:
                anual = (f" ≈ {om * freq:+.2f}{u} al año" if freq > 1 else "")
                filas.append(f"   · rampa en {fecha}: ω = {om:+.4f}{u} por "
                             f"periodo{anual}, desde esa fecha y PARA SIEMPRE")
        return ("\n\n> ⚠ **RAMPA EN EL NIVEL — cambia la previsión a largo plazo "
                "sin fecha de caducidad** (BUG-0182).\n>\n"
                + "\n".join("> " + f for f in filas) + "\n>\n"
                "> Una rampa es un escalón pasado por 1/(1−B): ganancia infinita, "
                "efecto sobre el nivel sin cota. Es una **tendencia determinista** "
                "desde la fecha; con d=1, un escalón en la tasa de crecimiento. La "
                "función de previsión hereda esa pendiente indefinidamente y la "
                "**banda no recoge incertidumbre sobre ella**, porque entra como "
                "conocida.\n>\n"
                "> Si la fecha salió de mirar los datos —el residuo mayor, el perfil "
                "de ℓ—, los contrastes de orden de integración posteriores no tienen "
                "sus críticos habituales (Zivot-Andrews): una rampa puede hacer "
                "desaparecer una raíz unitaria por construcción. Antes de "
                "adoptarla, contrasta la alternativa estocástica en el nodo d.\n>\n"
                "> Instrumento de usuario avanzado: el carril autónomo no la admite.")
    except Exception as exc:                            # pragma: no cover
        _warn("no se pudo describir la rampa del modelo", exc)
        return ("\n\n> ⚠ **El modelo lleva una RAMPA** (BUG-0182): tendencia "
                "determinista desde su fecha, heredada por la previsión sin "
                "fecha de caducidad.")


def _err(msg: str) -> list:
    """El error, presentado. Un incumplimiento del CONTRATO va sin traceback.

    Las herramientas devuelven `_err(traceback.format_exc())`, que es lo
    correcto para un fallo inesperado: la traza es la información. Pero para un
    incumplimiento del convenio —estimar desde un `.pre`— la traza ENTIERRA el
    mensaje, que es justo lo que el analista necesita leer: qué pasó, por qué, y
    qué fichero usar en su lugar. Un rechazo ilegible es peor que el aviso que
    vino a sustituir (BUG-0159).
    """
    from mcp.types import TextContent
    # El traceback prefija el nombre del módulo: «art.pipeline.ErrorDeContrato».
    m = re.search(r"^(?:[\w.]+\.)?ErrorDeContrato:\s*(.+)\Z", msg, re.S | re.M)
    if m:
        return [TextContent(type="text",
                            text="⛔ **No se puede hacer eso con este fichero.**"
                                 f"\n\n{m.group(1).strip()}")]
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
    except Exception as _e:               # BUG-0160: no se calla
        _warn("no se pudo componer el aviso del método en _equation_for_prompt", _e)
    # Y el ORIGEN, que es la causa y no el síntoma. Lo de arriba detecta que la
    # covarianza se parece a la semilla —una heurística, y sobre FOOD_UEM m06 no
    # salta porque las SE sólo se mueven un 12%—; esto sabe de qué fichero vino
    # el modelo, que es exacto (BUG-0090).
    try:
        from art.pipeline import aviso_se_no_fiable
        aviso += aviso_se_no_fiable(model)
    except Exception as _ae:
        _warn("aviso de origen del modelo", _ae)

    # Y LO QUE SÍ SE PUEDE CALCULAR — BUG-0168.
    #
    # Todo lo de arriba dice que un error típico no sirve, que es lo único que
    # se puede afirmar: cuánto se desvía la covarianza del BFGS depende del
    # camino del optimizador, no de una cantidad estimable. Publicar un factor
    # ahí es inventarse un sesgo, y el LLM lo repite como si fuera una medida.
    #
    # Pero sin ARMA el estimador de μ es la media muestral y su error típico es
    # σ̂/√n, con solución cerrada. Ahí no hay sesgo que estimar: hay dos números
    # y se comparan. Es la asimetría que había que corregir — se publicaba lo
    # incalculable y se callaba lo calculable.
    try:
        from art.diagnosis import se_exacta_de_la_media
        _se_mu = se_exacta_de_la_media(model)
        if _se_mu is not None:
            _r = getattr(model, "_result", None)
            # μ es el ÚLTIMO parámetro en el orden de `fue` (ω/δ de cada
            # intervención, AR, AR_s, MA, MA_s, AR_f, MA_f, μ). Se toma por la
            # posición y no por la etiqueta: `_param_labels_safe` devuelve []
            # justo en el caso que importa —la media sola— y la comparación se
            # perdía, que es la mitad útil del aviso.
            _pub = None
            try:
                import numpy as _np
                _se = _np.asarray(_r.std_errors, dtype=float)
                if _se.size:
                    _pub = float(_se[-1])
            except Exception:
                pass
            aviso += (
                f"\n\nℹ **Sin ARMA, el error típico de μ tiene forma cerrada**: "
                f"σ̂/√n = **{_se_mu:.6f}**"
                + (f", frente a **{_pub:.6f}** publicado arriba."
                   if _pub is not None else ".")
                + " Es el único de esta familia que se puede calcular en vez de "
                  "sospechar — el estimador de μ es la media muestral y no pasa "
                  "por el optimizador. Úsalo.")
    except Exception as _se:
        _warn("error típico exacto de la media", _se)
    return (
        "_[Claude: muestra al analista el bloque siguiente TAL CUAL; NO construyas "
        "tu propia tabla/ecuación de parámetros]_\n\n"
        "```\n" + eq + "\n```" + aviso
    )


# BUG-0078. La versión anterior no podía fallar de forma visible: mandaba
# stdout y stderr del visor a /dev/null, lanzaba el proceso en un hilo daemon
# del que nadie recogía el resultado, usaba una ruta estable POR ETIQUETA —así
# que dos herramientas con la misma etiqueta se pisaban el fichero— y nunca
# decía dónde había escrito. Cuando la ventana no aparecía no había nada a lo
# que agarrarse, y la herramienta reportaba éxito igual.
_ULTIMA_FIGURA: str = ""


def _escribe_fig(b64: str | None, label: str = "art") -> str:
    """Escribe la figura y devuelve su ruta, o "". **NO abre ventana.**

    BUG-0126: escribir y ENSEÑAR eran la misma función, y por eso la misma
    figura abría tres ventanas — la herramienta pedía la ruta, `_result` la
    pedía otra vez para la nota, y `_imagen` una tercera al construir la
    salida. Escribir es idempotente y se puede pedir tantas veces como haga
    falta; abrir una ventana no. Ahora la ventana la abre UN solo sitio.

    Devolver la ruta es la mitad del arreglo: quien llama puede decirla, y
    cuando el visor no aparece el analista tiene el fichero.

    **No abre ventana bajo pytest** ni con `ART_NO_VIEWER` en el entorno. La
    versión con `Popen` en hilo daemon fallaba tan deprisa que casi nunca
    llegaba a abrir nada; al hacerla síncrona —para poder detectar sus fallos—
    la suite empezó a abrir una ventana por figura, cientos y en blanco.
    """
    global _ULTIMA_FIGURA
    if not b64:
        return ""
    import base64, os, subprocess
    data = base64.b64decode(b64)
    etq = label.replace(" ", "_").replace("/", "_")
    # BUG-0081. El discriminante era `os.getpid()`, y el servidor MCP es UN
    # proceso durante toda la sesión: dentro de una sesión no discriminaba nada.
    # Dos series por los mismos nodos guiados escribían el mismo
    # `art_boxcox_<pid>.png`, y el analista abría el diagrama de la otra serie
    # mientras leía los números de ésta, sin aviso de nada.
    #
    # Ahora discrimina el CONTENIDO. Es más fuerte que (etiqueta, serie): no
    # colisiona nunca, y conserva la propiedad que se quería —misma figura,
    # mismo fichero, ventana reemplazada en vez de multiplicada— porque una
    # figura idéntica da la misma huella.
    import tempfile
    # BUG-0082. `ART_FIG_DIR` saca las figuras del temporal COMPARTIDO. La suite
    # sembraba `/tmp` de PNG en blanco con el mismo patrón de nombre que la
    # salida real: 49 ficheros de 651 bytes indistinguibles del producto, y
    # costó una sesión averiguar que art no renderizaba en blanco.
    # `/tmp` no existe en Windows: el directorio temporal lo da el sistema.
    dest = os.environ.get("ART_FIG_DIR") or tempfile.gettempdir()
    # MISMA FIGURA, MISMO FICHERO — y eso incluye dos ETIQUETAS distintas.
    #
    # BUG-0122. El nombre lleva la etiqueta delante de la huella, así que la
    # misma figura pedida dos veces con etiquetas distintas se escribía dos
    # veces: `art_nodo_1_<huella>.png` y `art_art_<huella>.png`. Es el BUG-0119
    # otra vez —la misma figura con dos nombres—, y aquí además rompía la nota,
    # porque quien la citaba se quedaba con el nombre que no era.
    #
    # La reutilización se limita al MISMO directorio: `ART_FIG_DIR` (BUG-0082)
    # existe para sacar las figuras de un temporal compartido, y un fichero
    # escrito en otro sitio no cumple lo que se pidió.
    previa = _FIGURAS.get(_huella_figura(b64), "")
    if (previa and os.path.exists(previa)
            and os.path.normpath(os.path.dirname(previa)) == os.path.normpath(dest)):
        path = previa
    else:
        path = os.path.join(dest, f"art_{etq}_{_huella_figura(b64)}.png")
        try:
            os.makedirs(dest, exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data)
        except Exception:
            return ""
    _ULTIMA_FIGURA = path
    _registra_figura(b64, path)

    # NO se abre ventana bajo pytest ni si se pide lo contrario. Sin esta
    # guarda, la suite abre una ventana por cada figura que genera: son cientos,
    # y las de prueba van en blanco. El fichero se escribe igual, que es lo que
    # una prueba necesita comprobar.
    #
    # BUG-0111: y TAMPOCO bajo servidor MCP, que era el tercer contexto que
    # faltaba en esta guarda. Ahí la figura ya viaja como ImageContent —la
    # ventana es un extra, según dice el docstring de `_abrir_visor`—, así que
    # pedirle al shell que la abra no aporta nada, y en algunos anfitriones no
    # es inocuo: el de Windows intercepta la petición y la convierte en un
    # diálogo de «¿adjunto este fichero a la sesión?» que saca al analista del
    # panel en el que trabaja, una vez por figura.
    return path


def _show_fig(b64: str | None, label: str = "art") -> str:
    """Escribe la figura **y la enseña**. Devuelve la ruta, o "".

    BUG-0126. Es el ÚNICO sitio que abre una ventana, y dentro del servidor lo
    llama sólo `_imagen` — o sea, una ventana por imagen devuelta, ni más ni
    menos. Todo lo demás usa `_escribe_fig`, que escribe y calla.

    Se conserva con este nombre y esta semántica porque fuera del servidor
    —cuadernos, guiones, la biblioteca— «enseñar una figura» es exactamente lo
    que se quiere pedir.
    """
    path = _escribe_fig(b64, label)
    if not path:
        return ""
    global _ULTIMO_VISOR_ERROR
    _ULTIMO_VISOR_ERROR = ""
    import sys
    if not _visor_procede(_BAJO_SERVIDOR, os.name, os.environ,
                          "pytest" in sys.modules):
        return path
    _ULTIMO_VISOR_ERROR = _abrir_visor(path)
    return path


def _visor_procede(bajo_servidor: bool, so: str, entorno,
                   bajo_pytest: bool) -> bool:
    """¿Se le pide al shell que abra la figura? Decide, no actúa.

    Va aparte por la misma razón que `_abrir_visor`: `_show_fig` no llega hasta
    aquí bajo pytest, y sin separar la DECISIÓN del EFECTO no había forma de
    probarla más que leyendo el fuente.

    BUG-0121. La guarda del BUG-0111 apagaba la ventana bajo servidor MCP **en
    todas las plataformas**, y el defecto que la motivó era del anfitrión de
    WINDOWS: allí `os.startfile` lo intercepta la aplicación de escritorio y lo
    convierte en un diálogo «¿adjunto este fichero a la sesión?». En POSIX nadie
    intercepta `xdg-open`.

    El razonamiento que generalizó el arreglo —«bajo servidor la ventana es un
    extra, la figura ya viaja como ImageContent»— es FALSO en los anfitriones
    que no pintan el ImageContent. Ahí la ventana no es un extra: es el único
    canal por el que el analista ve la figura, y el 0111 se lo cerró. La mitad
    guiada de un análisis son figuras.

    Las llaves, de más fuerte a más débil:
      ART_NO_VIEWER / pytest  apagan siempre;
      ART_VIEWER              enciende donde el 0111 apagaría, para el anfitrión
                              de Windows que no intercepte, o el que sí y aun
                              así prefiera la ventana.
    """
    if bajo_pytest or entorno.get("ART_NO_VIEWER"):
        return False
    if bajo_servidor and so == "nt" and not entorno.get("ART_VIEWER"):
        return False
    return True


def _abrir_visor(path: str) -> str:
    """Lanza el visor sobre `path`. Devuelve el motivo del fallo, o "".

    Va aparte de `_show_fig` para poder ejercitarla: `_show_fig` no llega aquí
    bajo pytest —no abriría ventanas en la pantalla de nadie— y sin separarlas
    el camino de fallo quedaba sin probar, que es justamente el que este bug
    venía a arreglar.

    CAPTURA la salida del visor. No levanta excepción: no poder abrir una
    ventana no debe tumbar un análisis, pero tampoco debe pasar inadvertido.

    Y es **multiplataforma**, que no lo era. La versión anterior llamaba a
    `xdg-open` sin más, que existe sólo en Linux/freedesktop: en Windows y en
    macOS esta vía no ha funcionado nunca, y nadie se enteró porque el
    `FileNotFoundError` se lo tragaba el hilo daemon con la salida a
    `/dev/null` — el mismo defecto que este bug viene a arreglar.

    Conviene tener presente que **ésta no es la vía principal**. La figura viaja
    además como `ImageContent` en la respuesta MCP, y eso lo renderiza el
    cliente en cualquier sistema. La ventana del escritorio es un extra.
    """
    import subprocess, sys
    if sys.platform.startswith("win"):
        try:
            os.startfile(path)          # type: ignore[attr-defined]
            return ""
        except Exception as e:
            return f"{type(e).__name__}: {e}"
    abridor = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        pr = subprocess.run([abridor, path], capture_output=True,
                            text=True, timeout=5)
        if pr.returncode != 0:
            return (pr.stderr or pr.stdout or
                    f"{abridor} salió con código {pr.returncode}").strip()
    except FileNotFoundError:
        return f"{abridor} no está instalado"
    except subprocess.TimeoutExpired:
        # El visor arrancó y se quedó en primer plano: es lo NORMAL con muchos
        # visores, y no es un fallo.
        pass
    except Exception as e:
        return f"{type(e).__name__}: {e}"
    return ""


_ULTIMO_VISOR_ERROR: str = ""


def _con_nota_figura(texto: str, ruta: str) -> str:
    """Añade la nota de la figura DONDE corresponde, que no es siempre al final.

    Dos arreglos correctos chocaban aquí: BUG-0113 exige que la ruta se DIGA
    —sin ella, con el visor apagado bajo servidor y un cliente que no renderice,
    el analista se queda sin figura, sin ventana y sin ruta— y BUG-0094 exige
    que la salida GUIADA termine en la marca de decisión, porque esa marca es lo
    que hace comprobable que la herramienta para en vez de decidir por él.

    Pegar la nota al final rompía el segundo: la última línea pasaba a ser un
    nombre de fichero y el turno dejaba de cerrar donde debía. La ruta es
    evidencia, así que su sitio está DENTRO del sobre, delante de la decisión.

    Estaba escrito a mano en tres sitios y cada uno lo hacía a su manera, que es
    como se llegó al choque. Aquí hay uno.
    """
    if not ruta:
        return texto
    nota = _nota_figura(ruta)
    i = texto.rfind(FIN_DE_TURNO_GUIADO)
    if i < 0:
        return texto + nota
    return texto[:i].rstrip() + "\n" + nota + "\n\n" + texto[i:]


def _nota_figura(path: str) -> str:
    """La línea que dice dónde quedó la figura, y si el visor falló."""
    if not path:
        return ""
    nota = f"\n\n*Figura: `{path}`*"
    if _ULTIMO_VISOR_ERROR:
        nota += (f"  ⚠ *no se pudo abrir sola ({_ULTIMO_VISOR_ERROR}); "
                 "ábrela desde esa ruta.*")
    return nota


def _asegura_inp_de_la_terna(inp_path: str, output_path: str) -> str:
    """Deja el `.inp` de la versión junto a su `.pre` y su `.out`.

    El convenio hace de cada versión una terna con el mismo basename: el `.inp`
    que se estimó, el `.pre` con el óptimo y el `.out` con el registro. Cuando
    `output_path` no es el fichero de origen, el `.inp` de esa terna no existe y
    el guion queda apuntando al vacío (BUG-0092).

    Se copia el fichero **tal cual**. Reserializar el modelo ajustado escribiría
    las estimaciones donde van las semillas, que es la trampa de BUG-0027.

    Si el destino ya existe con OTRO contenido no se toca: un `.pre` o un `.out`
    se rehacen estimando, pero una especificación perdida no se recupera.
    """
    import shutil
    src = os.path.expanduser(inp_path)
    dst = os.path.expanduser(output_path)
    if os.path.abspath(src) == os.path.abspath(dst):
        return ""                                   # ya es la misma terna
    try:
        if os.path.exists(dst):
            with open(src, "rb") as a, open(dst, "rb") as b:
                if a.read() == b.read():
                    return ""
            return (f"\n\n⚠ *`{os.path.basename(dst)}` ya existe con otro "
                    f"contenido y NO se ha tocado: una especificación perdida no "
                    f"se recupera. El `.pre` y el `.out` sí se han reescrito, así "
                    f"que esta terna queda descuadrada — comprueba a qué `.inp` "
                    f"corresponde.*")
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        shutil.copyfile(src, dst)
        return ""
    except Exception as e:
        _warn("copia del .inp de la terna", e)
        return (f"\n\n⚠ *No se pudo dejar el `.inp` junto a los artefactos "
                f"({type(e).__name__}: {e}). El guion apuntará a un fichero que "
                f"no existe.*")


# ---------------------------------------------------------------------------
# EL SOBRE DE LA ITERACIÓN — las cuatro etapas, siempre, en orden
# ---------------------------------------------------------------------------

#: Las cuatro etapas del proceso iterativo consciente, con los nombres de la
#: escuela. No las inventa esta capa: son las de la metodología —Box y Jenkins
#: en su forma extendida— y las que el guion ya registra entrada a entrada.
#: Las cuatro etapas del MÉTODO. Es lo que el REGISTRO guarda —una iteración es
#: una vuelta por ellas— y lo que el carril autónomo emite, porque allí no hay
#: nadie a quien preguntar.
ETAPAS_ITERACION = ("ESPECIFICACIÓN", "ESTIMACIÓN", "DIAGNOSIS", "REFORMULACIÓN")

#: Las cuatro secciones de la SALIDA GUIADA, que no son las mismas y no deben
#: serlo. Las de arriba miran hacia el registro: de dónde vino el modelo. Éstas
#: miran hacia el analista, que ya sabe de dónde vino porque lo decidió él, y lo
#: que necesita es lo que tiene delante y qué se le pregunta.
#:
#: La cuarta es la que convierte el carril en guiado: **no dictamina, ofrece
#: alternativas y para**. Una salida que anuncia la reformulación ya ha decidido,
#: y entonces el guiado es un autónomo que además cuenta lo que hace.
SECCIONES_GUIADO = ("MODELO ESTIMADO", "DIAGNOSIS", "CONCLUSIONES",
                    "DECISIÓN — alternativas")

#: La marca que cierra una salida guiada. Está para que sea COMPROBABLE que el
#: turno termina en la pregunta: la suite la busca, y el LLM tiene instrucción
#: de no escribir nada después de ella.
FIN_DE_TURNO_GUIADO = "⏸ **Tu decisión.** No sigo hasta que me digas."


def es_guiado(modo: str) -> bool:
    return "guiad" in (modo or "").lower()


def _reformulacion_desde(diag, guion_next: str = "") -> str:
    """La 4ª etapa, deducida de la diagnosis y de lo que declare el analista.

    No la inventa: recoge lo que la diagnosis ya ha dictaminado —qué contraste
    falla y qué implica— y lo que el analista haya escrito en `guion_next`. Si
    no hay nada, devuelve "" y el sobre pone «no procede reformular» de forma
    explícita, que es lo que obliga a pronunciarse (BUG-0094).
    """
    partes = []
    try:
        # UNA SOLA LECTURA DE LA DIAGNOSIS, y aquí estaba el defecto: esta
        # función leía `q_pass`/`jb_pass` y la diagnosis publica `white_noise`/
        # `normal` (describe.py). `d.get("q_pass")` devolvía None, `None is
        # False` es False, y **la rama de fallo no se ejecutaba nunca**: el
        # bloque era ciego a los dos contrastes que deciden la adecuación y
        # sólo veía `n_extreme`, que es justo el que no debería mirar
        # (BUG-0105). Sobre un modelo con Q y JB rechazando, la etapa 4 del
        # carril AUTÓNOMO decía «no procede reformular: el modelo se sostiene»
        # (BUG-0106).
        #
        # Se delega en `_conclusiones_desde`, que ya lee las claves correctas,
        # en vez de repetir la lectura: dos funciones consultando el mismo dict
        # con nombres distintos es exactamente cómo se llegó aquí.
        d = getattr(diag, "data", None) or {}
        if d.get("white_noise") is False or d.get("normal") is False:
            partes.append(_conclusiones_desde(diag).split("\n\n")[0]
                          + " La iteración continúa.")
    except Exception as e:                                   # pragma: no cover
        _warn("lectura de la diagnosis para la reformulación", e)
    if guion_next.strip():
        partes.append(f"**Siguiente versión declarada:** {guion_next.strip()}")
    return "\n\n".join(partes)


#: Dispersión relativa de los módulos por debajo de la cual la factorización
#: TIENE EL ASPECTO de un operador en B^N y conviene avisarlo.
#:
#: Medido sobre 12 réplicas de cada hipótesis, n=300, AR(6):
#:
#:     el proceso ES (1−Θ·B⁶)      mediana  7.8%   rango  2.8%–26.0%
#:     amortiguamientos LIBRES     mediana 57.3%   rango 22.8%–83.7%
#:
#: Las dos se solapan entre el 23% y el 26%, así que ningún umbral separa
#: limpiamente — y no hace falta que lo haga, porque **esto no dictamina, avisa**.
#: La asimetría decide dónde ponerlo: un falso positivo cuesta un párrafo que el
#: analista salta; un falso negativo cuesta imponer N−1 restricciones sin
#: contrastar, que es el error que el aviso existe para evitar. Por eso va
#: generoso.
#:
#: El caso real que lo motivó —UEM_HCPI_0219, módulos 1.2684 a 1.2934— está en
#: el 1.9%: muy dentro.
UMBRAL_MODULOS_PARECIDOS = 0.20


def umbral_extremo(n: int, prob: float = 0.90) -> float:
    """El |z| a partir del cual un residuo extremo es NOTICIA, dado n.

    Bajo especificación correcta el máximo de n normales crece con n, así que un
    umbral fijo deja de significar lo mismo:

        n=100  c=3.28   con el 3 fijo, P(al menos uno) = 0.24
        n=215  c=3.49                                    0.44
        n=500  c=3.71                                    0.74

    Con n=500 y umbral 3, **tres de cada cuatro** modelos correctamente
    especificados tendrían un «residuo extremo». No es que el 3 esté mal
    calibrado: es que a partir de cierto n el criterio se invierte y marca lo
    normal (BUG-0105).

    `c` es el cuantil `prob` del máximo: P(máx|z| < c) = (2Φ(c)−1)ⁿ = prob.
    """
    from math import erf, sqrt
    n = max(int(n or 0), 1)
    objetivo = (1.0 + prob ** (1.0 / n)) / 2.0
    lo, hi = 1.0, 10.0
    for _ in range(200):                      # bisección: sin dependencias
        c = (lo + hi) / 2.0
        if 0.5 * (1.0 + erf(c / sqrt(2.0))) < objetivo:
            lo = c
        else:
            hi = c
    return round((lo + hi) / 2.0, 2)


def _conclusiones_desde(diag) -> str:
    """La 3ª sección: qué DICE la diagnosis, no qué números dio.

    Existe porque el bloque de diagnosis es una lista de contrastes y el
    analista tiene que poder leer el veredicto sin recomponerlo. Y porque un
    veredicto escrito por la herramienta es el mismo en todas las sesiones,
    mientras que uno redactado por el LLM cambia con el LLM.
    """
    d = getattr(diag, "data", None) or {}
    fallos, bien = [], []
    (fallos if d.get("white_noise") is False else bien).append(
        "la Q " + ("RECHAZA el ruido blanco" if d.get("white_noise") is False
                   else "no rechaza el ruido blanco"))
    (fallos if d.get("normal") is False else bien).append(
        "el Jarque-Bera " + ("RECHAZA la normalidad" if d.get("normal") is False
                             else "no rechaza la normalidad"))
    # LOS ANÓMALOS NO DICTAN LA ADECUACIÓN, y estaban en la lista de fallos.
    # La adecuación la deciden la Q y el Jarque-Bera —es lo que dice
    # `result.clean`— y meter aquí `n_extreme` producía informes que se
    # contradecían a sí mismos: «Veredicto APROBADO ✓ · Q ✓ · JB ✓» y diez
    # líneas más abajo «El modelo NO se sostiene: queda 1 residuo extremo»
    # (BUG-0105).
    #
    # El dato no se tira: se pone donde SÍ informa.
    n_ext = int(d.get("n_extreme") or 0)
    nobs = int(d.get("nobs") or 0)

    L = []
    if fallos:
        L.append("**El modelo NO se sostiene:** " + "; ".join(fallos) + ".")
        qf = d.get("q_fails") or []
        if qf:
            L.append("Retardos donde la Q falla: " + "; ".join(str(x) for x in qf)
                     + ". *Dónde falla dice QUÉ falta: un retardo estacional "
                       "pide estructura estacional, uno bajo pide orden regular.*")
    else:
        L.append("**El modelo se sostiene:** " + "; ".join(bien) + ".")

    if n_ext:
        if d.get("normal") is False:
            # Con el JB rechazando, los extremos dicen DÓNDE está la
            # no-normalidad: ahí el dato dirige la reformulación.
            L.append(f"Los {n_ext} residuo(s) extremo(s) son el sitio por donde "
                     f"mirar la no-normalidad. *Un JB que falla SIN anómalos "
                     f"apunta a λ, no a intervenciones (BUG-0043).*")
        else:
            # Con el JB aprobado, la mención va calibrada por n o no va: un
            # umbral fijo convierte lo esperable en alarma.
            c = umbral_extremo(nobs) if nobs else None
            nota = (f"{n_ext} residuo(s) con |z|>3, que con n={nobs} es lo "
                    f"esperable —el umbral calibrado sería {c:.2f}—"
                    if c else f"{n_ext} residuo(s) con |z|>3")
            L.append(f"*El Jarque-Bera no rechaza: {nota}. No es un fallo de "
                     f"adecuación; interviene sólo si el suceso se sostiene por "
                     f"sí mismo.*")
    return "\n\n".join(L)


#: |t| a partir del cual la correlación de los residuos con el regresor de
#: Semana Santa deja de ser ruido. Medido sobre 10 réplicas de cada hipótesis
#: (n=240, mensual, con el paquete estacional determinista ya puesto):
#:
#:     SIN easter        |t| mediana 0,35   máximo  1,30
#:     CON un +2%        |t| mediana 9,89   mínimo  9,82
#:
#: Un factor de 7 entre el peor caso de cada lado, y con un efecto pequeño. El
#: umbral va en 3, que es el convencional y queda muy dentro del hueco.
UMBRAL_EASTER = 3.0


def _falta_el_easter(model, ts) -> float:
    """|t| de la correlación entre los residuos y el regresor de Semana Santa.

    Es un contraste de puntuación de andar por casa, y sirve porque el efecto de
    Semana Santa **no se manifiesta como anómalos**: es sistemático, así que no
    deja residuos |z|>3 y `intervention_hints` no lo ve. Lo que deja es
    estructura —la Q rechaza en 12, 24, 36 y la estacionalidad residual salta—,
    que es la MISMA firma que la estacionalidad corriente.

    Lo que lo distingue es que **se mueve**: cae en marzo o en abril según el
    año, así que ningún armónico de periodo fijo lo absorbe. Correlacionar los
    residuos con el regresor que el motor sabe construir separa las dos cosas —
    medido, incluso con el paquete estacional ya puesto.

    Devuelve 0.0 cuando no procede (no mensual, sin residuos, o ya lo lleva).
    """
    import numpy as _np
    try:
        if ts is None or int(getattr(ts, "freq", 0)) != 12:
            return 0.0
        if any(i.type == "easter" for i in (getattr(model, "interventions", None) or [])):
            return 0.0
        r = _np.asarray(getattr(getattr(model, "_result", None), "residuals", None),
                        dtype=float)
        if r.size < 36:
            return 0.0
        from fue.cast_us import _build_indicator
        import fue as _fue
        ind = _build_indicator(
            _fue.Intervention("easter", at=0, omega=[1.0], omega_free=[False]),
            int(ts.nobs), 12, int(ts.start[1]), int(ts.start[0]))[1:]
        if ind.size < r.size or not _np.any(ind):
            return 0.0
        ind = ind[-r.size:]
        c = float(_np.corrcoef(r, ind)[0, 1])
        if not _np.isfinite(c) or abs(c) >= 1.0:
            return 0.0
        return abs(c) * _np.sqrt(r.size - 2) / _np.sqrt(1.0 - c * c)
    except Exception:
        return 0.0


def _alternativas_desde(diag, model=None, ts=None, inp_path: str = "",
                        guion_path: str = "") -> list:
    """La 4ª sección: las opciones REALES, cada una con su llamada.

    El orden es el de Treadway —lo más obvio primero—: un residuo extremo se
    atiende antes que un orden ARMA, porque un anómalo sin tratar contamina la
    estimación de todo lo demás.

    Cada alternativa lleva la llamada exacta que la ejecuta. No es comodidad: es
    lo que evita los turnos de ida y vuelta averiguando qué se puede hacer y con
    qué argumentos, que es donde se va el presupuesto en el carril guiado.
    """
    d = getattr(diag, "data", None) or {}
    alts = []
    ruta = f'"{inp_path}"' if inp_path else "<inp>"

    def _fecha(obs):
        # `obs` es el índice 1-BASED SOBRE LOS RESIDUOS (diagnosis: `i + 1`);
        # `_at_to_date` quiere el 0-based SOBRE LA SERIE. Falta el desfase —lo
        # que se comió la diferenciación, raíces estacionales incluidas—. Con
        # d=1 y sin raíces los dos errores se cancelaban y por eso no se veía;
        # con una raíz interior la fecha salía 2 meses pronto, con D=1 un año,
        # y la alternativa trae la LLAMADA lista para ejecutar (BUG-0185).
        # Sin modelo no se sabe el desfase: se dice el índice antes que fechar
        # mal.
        if model is None:
            return f"obs {obs}"
        try:
            from art.guion import _at_to_date
            from art.identification import desfase_observaciones
            _s = ts if ts is not None else model.series
            return _at_to_date(int(obs) - 1 + desfase_observaciones(model),
                               int(_s.start[0]), int(_s.start[1]), int(_s.freq))
        except Exception:
            return f"obs {obs}"

    # 1 · lo más obvio: un residuo extremo — PERO calibrado por n.
    # Ofrecer «intervenir» como opción A sobre un modelo cuya Q y JB pasan es
    # invitar a sobre-intervenir: con n=215 un |z|>3 es lo esperable, no una
    # señal. Sólo se ofrece si supera el umbral calibrado o si algo más falla
    # (BUG-0105).
    pistas = d.get("intervention_hints") or []
    _nobs = int(d.get("nobs") or 0)
    if pistas and _nobs:
        _c = umbral_extremo(_nobs)
        _limpio = (d.get("white_noise") is not False
                   and d.get("normal") is not False)
        if _limpio:
            pistas = [h for h in pistas if abs(float(h.get("z") or 0)) > _c]
    if pistas:
        pista = max(pistas, key=lambda h: abs(float(h.get("z") or 0)))
        f = _fecha(pista.get("obs"))
        alts.append(
            f"**Intervenir {f}** (|z| = {abs(float(pista.get('z') or 0)):.2f}"
            + (f", forma sugerida: {pista['form']}" if pista.get("form") else "")
            + f"). Un anómalo sin tratar contamina la estimación de todo lo "
              f"demás, y por eso va primero.\n"
              f"   `suggest_intervention_form(inp_path={ruta}, date=\"{f}\")` "
              f"→ y luego `guided_intervention(...)`")

    # 2 · dónde falla la Q dice qué falta
    if d.get("white_noise") is False:
        qf = " ".join(str(x) for x in (d.get("q_fails") or []))
        estacional = ts is not None and any(
            f" {k}" in qf for k in (str(int(ts.freq)), str(int(ts.freq) * 2)))
        p_act = len((model.ar or [[]])[0]) if getattr(model, "ar", None) else 0
        q_act = len((model.ma or [[]])[0]) if getattr(model, "ma", None) else 0
        if estacional:
            alts.append(
                "**Añadir estructura ESTACIONAL** — la Q falla en un retardo "
                "estacional, que es donde se ve lo que los armónicos no "
                "absorben.\n"
                f"   `confirm_and_estimate(inp_path={ruta}, P=1, ...)`, o "
                f"`meg_frequency(...)` si sospechas raíz unitaria estacional")
        else:
            alts.append(
                f"**Subir el orden regular** — hoy AR({p_act}) MA({q_act}). "
                f"El correlograma de los residuos dice cuál de los dos.\n"
                f"   `confirm_and_estimate(inp_path={ruta}, p={p_act + 1}, "
                f"q={q_act}, ...)`  ó  `q={q_act + 1}`\n"
                f"   `identification_analysis(inp_path={ruta})` para mirarlo "
                f"antes de elegir")

    # 2bis · LA SEMANA SANTA, que nadie ofrecía nunca.
    #
    # `easter` existe desde BUG-0097 y la ruta desde BUG-0103, pero el carril no
    # lo mencionaba en ningún nodo y su documentación cae fuera de lo que el
    # cliente entrega al modelo (BUG-0116). En la sesión que lo destapó salió
    # porque el analista leyó el fuente. Una opción que aparece CUANDO HACE
    # FALTA vale más que cualquier párrafo que hay que haber leído antes.
    t_ea = _falta_el_easter(model, ts)
    if t_ea > UMBRAL_EASTER:
        alts.append(
            f"**Añadir el efecto de SEMANA SANTA** — los residuos correlacionan "
            f"con su regresor a |t| = {t_ea:.1f}. No aparece como anómalos "
            f"porque es sistemático, y ningún armónico lo absorbe porque **se "
            f"mueve entre marzo y abril**.\n"
            f"   `confirm_and_estimate(inp_path={ruta}, easter=True, ...)` "
            f"— es un determinista, no una intervención: no lleva fecha, y sólo "
            f"existe en series mensuales")

    # 3 · normalidad sin ruido: casi siempre son anómalos, no la distribución
    if d.get("normal") is False and d.get("white_noise") is not False:
        alts.append(
            "**Mirar los anómalos antes que la distribución** — la Q pasa y el "
            "Jarque-Bera no: eso suele ser un puñado de sucesos, no una "
            "distribución distinta.\n"
            f"   `residual_outlier_scan(inp_path={ruta})`")

    # 4 · si nada falla, ADOPTAR es una decisión y hay que poder tomarla
    if not alts:
        alts.append(
            "**Adoptar este modelo** y cerrar el nodo. Nada en la diagnosis "
            "pide cambiarlo.\n"
            f"   `record_version(inp_path={ruta}, decision=\"adoptado\", "
            f"rationale=\"...\")`")
        alts.append(
            "**Sobreparametrizar para comprobarlo** — añadir un parámetro y ver "
            "si sale no significativo es la forma de saber que no falta nada.\n"
            f"   `overparameterization_analysis(inp_path={ruta})`")

    # 5 · siempre: volver atrás. El camino es un grafo, no un árbol.
    alts.append(
        "**Volver a un nodo anterior** — el recorrido es un laberinto y "
        "retroceder es el método funcionando, no un fallo.\n"
        + (f"   `guion_map(guion_path=\"{guion_path}\")`" if guion_path
           else "   `guion_map(guion_path=<guion>)`"))
    return alts


def envuelve_iteracion(*, nombre: str,
                       modo: str = "",
                       especificacion: str = "",
                       ecuacion: str = "",
                       diagnosis: str = "",
                       reformulacion: str = "",
                       conclusiones: str = "",
                       alternativas: "list[str] | None" = None,
                       figuras_b64: "list[str] | None" = None,
                       rutas_figuras: "list[str] | None" = None,
                       extra: str = "") -> str:
    """Una iteración, con la MISMA forma siempre (BUG-0094).

    Por qué existe
    --------------
    El proceso es iterativo y cada iteración tiene una salida. Si esa salida no
    está mínimamente estandarizada, pasan dos cosas: es caótica, y —lo que
    importa— **desobliga al analista**. Si la forma varía, no se le puede exigir
    que haya leído un bloque, porque quizá no estaba; ni preguntarle por qué
    decidió sin mirar la diagnosis. Con forma fija, la ausencia de una sección
    es una omisión atribuible.

    Es la misma lógica del guion, que obliga porque siempre lleva `decision` y
    `rationale`.

    Y la variabilidad era GRATUITA: **en el fondo ya está estandarizado**. De la
    tesis (§1.1.1.2, §2.3), sobre la forma extendida de Box-Jenkins:

        «un proceso iterativo consciente … (1) especificación inicial, basada
        fundamentalmente en los datos, (2) estimación eficiente de los modelos
        por el criterio de Máxima Verosimilitud Exacta No Condicionada (MVENC),
        (3) diagnosis estadística de los modelos estimados (métodos formales e
        informales) y, en su caso, (4) reformulación.»

    Ésas son las cuatro secciones. No se uniforma el CONTENIDO —cada nodo llena
    lo suyo— se uniforma **a qué etapa pertenece cada bloque**.

    La cuarta va SIEMPRE, también cuando el modelo se sostiene. El «y en su
    caso» de la cita es sobre si hay que reformular, no sobre si hay que
    pronunciarse: una iteración que no dice qué haría después no ha terminado.

    Guiado y autónomo
    -----------------
    El sobre es el MISMO en los dos carriles: el guion también lo es, y por la
    misma razón. La única diferencia es que en autónomo **la figura no viaja** —
    se escribe igual, porque el guion la necesita, pero se cita por su ruta.

    No es un detalle de comodidad. Medido sobre las tres realizaciones del run 3
    (483 llamadas): **el 97.4% de los bytes que salen del servidor son
    imágenes**, y en un bucle agéntico cada byte se reenvía en todos los turnos
    siguientes. Estimado en tokens, no mandarlas ahorra entre el **41% y el
    45%** del presupuesto. En autónomo nadie las mira.

    Cuando de verdad hagan falta, `guion_evidencia` las recupera del registro.

    Parameters
    ----------
    nombre          : el modelo de esta iteración
    especificacion  : de dónde sale este modelo — qué se decidió y por qué
    ecuacion        : el bloque verbatim de la ecuación estimada
    diagnosis       : Q, JB, anómalos; los métodos formales e informales
    reformulacion   : qué falla y qué se propone. Vacío ⇒ «no procede», dicho
    figuras_b64     : carril GUIADO. Viajan como ImageContent
    rutas_figuras   : carril AUTÓNOMO. Sólo se citan
    extra           : lo que no es una etapa (guion, estado, mapa)
    """
    # El CARRIL va en la cabecera, no enterrado: es una propiedad de la
    # iteración —quién decidió— y quien lee la salida tiene que saberlo antes de
    # nada. Lo pilló una prueba dorada que exigía el modo en la primera línea.
    L = [f"# Iteración — {nombre}" + (f"  ·  {modo}" if modo else ""), ""]

    # ── CARRIL GUIADO: otra salida, y por una razón de fondo ──────────────
    # Las cuatro etapas del método son la forma del REGISTRO. Al analista le
    # sirven mal: empiezan por la especificación —que decidió él, hace un
    # momento— y terminan anunciando la reformulación, que es la decisión que le
    # tocaba a él. Con esa forma el guiado se comporta como un autónomo que
    # además narra lo que ya ha resuelto.
    #
    # Aquí la salida termina en la PREGUNTA, con alternativas y con la llamada
    # exacta que ejecuta cada una. Eso quita dos costes que se pagaban en cada
    # nodo: el analista interrumpiendo el chat para poder decidir, y los turnos
    # de ida y vuelta aclarando qué opciones había.
    if es_guiado(modo):
        L += [f"## 1 · {SECCIONES_GUIADO[0]}", ""]
        L += [ecuacion.strip() if ecuacion.strip()
              else "*No se ha estimado ningún modelo en esta iteración.*", ""]

        L += [f"## 2 · {SECCIONES_GUIADO[1]}", ""]
        L += [diagnosis.strip() if diagnosis.strip()
              else "*Sin diagnosis: no hay modelo estimado que diagnosticar.*"]
        if rutas_figuras:
            L += ["", "*Figuras:*"] + [f"  · `{r}`" for r in rutas_figuras if r]
        L.append("")

        L += [f"## 3 · {SECCIONES_GUIADO[2]}", ""]
        L += [conclusiones.strip() if conclusiones.strip()
              else "*Sin conclusión: la diagnosis no dictamina nada.*", ""]

        L += [f"## 4 · {SECCIONES_GUIADO[3]}", ""]
        if especificacion.strip():
            L += [f"*Punto de partida: {especificacion.strip()}*", ""]
        opciones = [a for a in (alternativas or []) if str(a).strip()]
        if opciones:
            for i, alt in enumerate(opciones):
                L.append(f"**{chr(65 + i)})** {str(alt).strip()}")
                L.append("")
        else:
            # Sin alternativas no hay decisión que tomar, y hay que DECIRLO:
            # callarlo deja al analista sin saber si es que no hay opciones o
            # es que nadie las buscó.
            L += ["*No se han derivado alternativas de esta diagnosis. "
                  "Dime tú por dónde seguir, o pide `guion_map` para ver el "
                  "recorrido y volver a un nodo anterior.*", ""]
        if extra.strip():
            L += ["---", "", extra.strip(), ""]
        L += [FIN_DE_TURNO_GUIADO]
        return "\n".join(L)

    L += [f"## 1 · {ETAPAS_ITERACION[0]}", ""]
    L += [especificacion.strip() if especificacion.strip()
          else "*Sin cambios de especificación en esta iteración.*", ""]

    L += [f"## 2 · {ETAPAS_ITERACION[1]}", ""]
    L += [ecuacion.strip() if ecuacion.strip()
          else "*No se ha estimado ningún modelo en esta iteración.*", ""]

    L += [f"## 3 · {ETAPAS_ITERACION[2]}", ""]
    L += [diagnosis.strip() if diagnosis.strip()
          else "*Sin diagnosis: no hay modelo estimado que diagnosticar.*"]
    if rutas_figuras:
        L += ["", "*Figuras (no viajan en este carril; el registro las tiene):*"]
        L += [f"  · `{r}`" for r in rutas_figuras if r]
    L.append("")

    L += [f"## 4 · {ETAPAS_ITERACION[3]}", ""]
    # SIEMPRE explícita. Una iteración que no se pronuncia no ha terminado.
    L += [reformulacion.strip() if reformulacion.strip()
          else "**No procede reformular:** el modelo se sostiene y nada en la "
               "diagnosis pide cambiarlo. Si se continúa, es por una razón que "
               "no está en estos datos.", ""]

    if extra.strip():
        L += ["---", "", extra.strip()]
    return "\n".join(L)


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
            # la convención de la suite, explícita desde el primer fichero:
            # sin ella el esqueleto nacía en escala 1 (BUG-0085).
            refactor=_RESCALE_FACTOR,
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
        _escribe_fig(desc.figure_b64, "boxcox")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: qué configuraciones del incidente admite el dato
# ---------------------------------------------------------------------------

@mcp.tool()
def incident_configurations(inp_path: str,
                            at: int = 0,
                            threshold: float = 2.5,
                            umbral_activo: float = 1.0,
                            evento_desde: str = "",
                            evento_naturaleza: _Naturaleza = "",
                            evento_fuente: str = "",
                            aportada_por: str = "") -> list:
    """
    
    **Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar qué configuraciones del incidente admite el dato sin avanzar el flujo.
    Enumera las CONFIGURACIONES del incidente compatibles con el dato, y dice
    si el dato las identifica o no.

    EL PROBLEMA. Con d=1 un spike observado en ∇ puede ser el ARRANQUE de un
    suceso o la COLA de uno que empezó un período antes: un impulso de nivel en
    T da +ω en T y −ω en T+1. Si la serie deambula, el primer spike puede quedar
    tapado y sólo cruzar el umbral el segundo — y la intervención cae un período
    tarde, con Δ logL de 0,03 entre la fecha buena y la mala (BUG-0030).

    Y el arranque no es un detalle de fecha: DECIDE LA LÍNEA BASE. Arrancar
    antes absorbe parte del movimiento previo y encoge la ganancia estimada.

    LO QUE ESTA HERRAMIENTA NO HACE, y es su razón de ser: **no elige cuando el
    dato no identifica**. Medido sobre una serie real, tres configuraciones
    dentro de 2 puntos de AIC, ninguna dejando vecino anómalo, con ganancias de
    −0,27 a −0,58 y el veredicto permanente/transitorio invertido entre ellas.
    Publicar una y su error típico sería fabricar una precisión que no existe.

    LA TRAMPA que avisa: la configuración de arranque MÁS TARDÍO tiende a tener
    el intervalo MÁS ESTRECHO y a ser la única que excluye el cero. No es suerte
    — acortar la ventana quita parámetros y aprieta la identificación dentro del
    modelo mientras empeora la línea base. La lectura más segura es la más
    sospechosa.

    EL CONJUNTO ESTÁ ACOTADO POR EL MECANISMO, no por rejilla: se anda hacia
    atrás desde el primer extremo mientras los residuos contiguos sigan ACTIVOS
    (|z| ≥ `umbral_activo`), y cada arranque determina UNA longitud. No hay
    barrido, que es lo que sobre-elaboraría.

    INFORMACIÓN EXTRAMUESTRAL — LÉASE ANTES DE RELLENARLA.
    Es lo único que identifica de verdad, y **la herramienta no la sabe ni debe
    inventarla**: entra por estos parámetros y queda registrada con quién la
    aportó. Si eres un LLM y no te consta el suceso, **deja los campos vacíos**;
    no rellenes `evento_fuente` con un recuerdo. `naturaleza` sin `fuente` se
    rechaza: afirmar que un suceso fue permanente exige decir por qué se sabe.

    Parameters
    ----------
    inp_path          : .inp de un modelo estimado SIN la intervención
    at                : obs 1-based (espacio de RESIDUOS) dentro del episodio a
                        analizar. 0 = el de mayor |z|. **Se analiza UN episodio
                        por llamada**: las configuraciones son de un suceso, no
                        del conjunto de anómalos de la serie
    threshold         : |z| para marcar un residuo como extremo
    umbral_activo     : |z| a partir del cual un residuo contiguo cuenta como
                        parte del suceso aunque no sea extremo (1,0)
    evento_desde      : fecha declarada de inicio, "QN/AAAA" — fija el arranque
    evento_naturaleza : LAS TRES LECTURAS de un suceso en el nivel (o "" para
                        que decida el contraste):
                          `permanente`           el nivel se queda desplazado
                          `transitorio`          vuelve a la línea base
                          `recuperacion_parcial` vuelve EN PARTE
                        La explicación tiene que explicar la FORMA, no sólo la
                        fecha. La tercera no la decide esta llamada: es la
                        ganancia NETA de dos intervenciones (BUG-0155/0157)
    evento_fuente     : qué se está citando. Obligatorio si hay `naturaleza`
    aportada_por      : "analista" | "LLM"
    """
    try:
        import numpy as np
        from art.configuracion import (arranques_candidatos,
                                       evalua_configuraciones,
                                       describe_configuraciones,
                                       InfoExtramuestral)
        from art.policy import decide_domain
        # BUG-0164. De este modelo sólo se toman la ESTRUCTURA, la serie y
        # los RESIDUOS; las SE de la tabla son las de cada configuración,
        # estimada aparte sobre este base. Así que le toca
        # `mirar`, no `estimar` — y con `estimar` rechazando el `.pre`
        # (BUG-0159) esta puerta se quedó cerrada para el encadenado, que
        # es el modo NORMAL de usarla.
        ts, m = _mirar(inp_path)
        # `_load_fitted` y no `_load_ts_model` + `fit()` a mano: esa vía no sella
        # el origen del fichero, y con ella el aviso de BUG-0090 es
        # inalcanzable — el contrato tenía tres puertas y una cuarta abierta.
        if m.residuals is None:
            return _err("el modelo no tiene residuos: ¿se estimó?")
        r = np.asarray(m.residuals.data, dtype=float)
        sd = r.std(ddof=0)
        z = (r - r.mean()) / sd if sd > 0 else r
        ext = [(i + 1, float(z[i])) for i in range(len(z))
               if abs(z[i]) > threshold]
        if not ext:
            return _err(f"no hay residuos con |z| > {threshold:g}.")
        d_reg = int(getattr(m, "d", 0))

        # AGRUPAR EN EPISODIOS PRIMERO. Sin esto, dos sucesos separados por años
        # se toman como UNO y la enumeración le busca el arranque a un engendro
        # de dieciocho trimestres: sobre PGAS m10 salía «Q1/2015 × 23 escalones».
        # Las configuraciones son de UN suceso, no del conjunto de anómalos.
        from art.policy import decide_episodios
        eps = decide_episodios(ext, d=d_reg)
        if at:
            ep = next((e for e in eps if e.inicio <= int(at) <= e.fin), None)
            if ep is None:
                return _err(f"at={at} no cae en ningún episodio: "
                            + ", ".join(f"{e.inicio}–{e.fin}" for e in eps))
        else:
            ep = max(eps, key=lambda e: e.z_max)
        otros = [e for e in eps if e is not ep]
        idx_ep = [o - 1 for o, _ in ep.extremos]
        cands = arranques_candidatos(z, idx_ep, d=d_reg,
                                     umbral_activo=umbral_activo)
        try:
            info = InfoExtramuestral(desde=evento_desde.strip(),
                                     naturaleza=evento_naturaleza.strip(),
                                     fuente=evento_fuente.strip(),
                                     aportada_por=aportada_por.strip())
        except ValueError as ve:
            return _err(str(ve))
        try:
            dom = decide_domain(ts)
        except Exception:
            dom = "generic"
        conj = evalua_configuraciones(
            m, cands, d=d_reg, dominio=dom, info=info,
            freq=int(ts.freq or 4),
            start_year=int(getattr(ts, "start", (2000, 1))[0]),
            start_per=int(getattr(ts, "start", (2000, 1))[1]),
            umbral_activo=umbral_activo)
        desc = describe_configuraciones(conj)
        if otros:
            aviso = ("\n\n---\n\n*Hay **" + str(len(otros)) + "** episodio(s) "
                     "más en estos residuos, sin analizar aquí: "
                     + ", ".join(f"obs {e.inicio}" + ("" if e.aislado
                                 else f"–{e.fin}") + f" (|z|máx {e.z_max:.2f})"
                                 for e in otros)
                     + ". Se analiza UN episodio por llamada — pásale `at` para "
                       "ir a otro.*")
            desc = type(desc)(summary=desc.summary + aviso,
                              figure_b64=desc.figure_b64,
                              recommendation=desc.recommendation,
                              data={**desc.data,
                                    "otros_episodios": [
                                        dict(inicio=e.inicio, fin=e.fin,
                                             z_max=e.z_max) for e in otros]})
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: la escalera de Ockham
# ---------------------------------------------------------------------------

@mcp.tool()
def intervention_ladder(inp_path: str,
                        at: int = 0,
                        ventana: int = 0,
                        threshold: float = 3.0,
                        umbral_vecino: float = 0.0) -> list:
    """
    
    **Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar los peldaños de Ockham de un suceso sin avanzar el flujo.
    ESCALERA DE OCKHAM — estima las especificaciones rivales de un suceso EN
    ORDEN de sofisticación, y dice qué justifica subir de peldaño.

      peldaño 1   UNA intervención escalar. Dos lecturas del MISMO coste —un
                  parámetro cada una— y no anidadas entre sí:
                    1a  escalón en el nivel  → efecto PERMANENTE
                    1b  impulso en el nivel  → efecto TRANSITORIO
      peldaño 2   EPISODIO: L+1 escalones en el nivel, con el contraste de
                  ganancia ω(1)=0 que separa transitorio de permanente.

    LO QUE ESTA HERRAMIENTA PROHÍBE, y es su razón de ser: **el AIC no arbitra
    la subida de peldaño**. Compara dentro de uno, o confirma una subida ya
    justificada. Una escalera que se quedase con el mejor AIC subiría siempre,
    porque el modelo más sofisticado casi siempre ajusta mejor — tiene más
    parámetros. Eso es lo contrario de la navaja.

    LO QUE SÍ JUSTIFICA SUBIR, en este orden:
      1. **Treadway** — la forma de abajo deja un anómalo de vecino. Evidencia
         objetiva: la parte no modelizada del suceso cae entera ahí.
      2. **Inadecuación** — la forma de abajo no deja ruido blanco.
      3. **Dominio** — la lectura simple es implausible para esta clase de
         serie (una caída PERMANENTE en un índice de precios es poco usual).
      4. **Ausencia de explicación extramuestral** — y ésta la herramienta NO
         la sabe: la pregunta y espera respuesta del analista.

    LA EXPLICACIÓN TIENE QUE EXPLICAR LA FORMA, no sólo la fecha. Una bajada de
    impuestos explica un escalón permanente; una huelga, un impulso
    transitorio. Si el analista aporta una explicación de suceso permanente y el
    contraste de ganancia dice transitorio, no cubre lo que hay y se sube igual.

    Parameters
    ----------
    inp_path      : .inp de un modelo estimado **SIN** la intervención en
                    cuestión — sus residuos son justo lo que ella debe explicar
    at            : obs 1-based (espacio de RESIDUOS) donde arranca el suceso.
                    0 = tomar el episodio de mayor |z| que detecte el escaneo
    ventana       : ventana de agrupación en episodios; 0 usa la de la política
    threshold     : |z| para marcar un residuo como extremo
    umbral_vecino : |z| a partir del cual un vecino cuenta como anómalo.
                    0 = el de la política (2.0). Estaba clavado a 3.0 —el de los
                    anómalos sueltos— y daba por exitosa una intervención que
                    deja un vecino a 2.4σ (BUG-0087).
    """
    try:
        import numpy as np
        from art.episodes import describe_episodios
        from art.escalera import escalera_de_ockham, describe_escalera
        from art.policy import decide_episodios, decide_domain, THRESHOLDS
        ts, m = _mirar(inp_path)
        # `_load_fitted` y no `_load_ts_model` + `fit()` a mano: esa vía no sella
        # el origen del fichero, y con ella el aviso de BUG-0090 es
        # inalcanzable — el contrato tenía tres puertas y una cuarta abierta.
        if m.residuals is None:
            return _err("el modelo no tiene residuos: ¿se estimó?")
        r = np.asarray(m.residuals.data, dtype=float)
        sd = r.std(ddof=0)
        z = r / sd if sd > 0 else r
        ext = [(i + 1, float(z[i])) for i in range(len(z))
               if abs(z[i]) > threshold]
        if not ext:
            return _err(f"no hay residuos con |z| > {threshold:g}: no hay "
                        "suceso que escalonar.")
        d_reg = int(getattr(m, "d", 0))
        v = int(ventana) or THRESHOLDS["ventana_episodio"]
        eps = decide_episodios(ext, ventana=v, d=d_reg)
        if at:
            ep = next((e for e in eps if e.inicio <= int(at) <= e.fin), None)
            if ep is None:
                return _err(f"at={at} no cae en ningún episodio detectado: "
                            + ", ".join(f"{e.inicio}–{e.fin}" for e in eps))
        else:
            ep = max(eps, key=lambda e: e.z_max)
        try:
            dom = decide_domain(ts)
        except Exception:
            dom = "generic"
        esc = escalera_de_ockham(m, ep, dominio=dom,
                                 umbral_vecino=umbral_vecino or 0.0)
        desc = describe_escalera(esc)
        _escribe_fig(desc.figure_b64, "escalera")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: gráfico de intervención
# ---------------------------------------------------------------------------

def _con_convenio(desc, omega, delta=None, b: int = 0,
                  entrada: str = "escalon"):
    """Añade a la descripción el operador leído EN EL NIVEL.

    El convenio de signo de fue —Box-Jenkins, los retardos restan— es
    consistente y no se toca. Lo que cuesta es que obliga a una resta mental
    cada vez que se escribe o se lee un ω, y esa resta se falla: en la sesión de
    la réplica se falló dos veces seguidas construyendo una hipótesis a mano.

    La regla ya estaba escrita en tres docstrings. Escribirla una cuarta vez no
    arregla nada; **calcularla**, sí. Así que donde el analista mete ω, la
    respuesta le devuelve el camino del nivel que ha pedido de verdad — y un
    signo cambiado se ve en el acto, antes de estimar nada.
    """
    if not omega or len(omega) < 2:
        return desc                      # con un solo ω no hay resta que fallar
    try:
        from art.ltf import operador_en_palabras
        from art.describe import Description
        bloque = operador_en_palabras(list(omega), list(delta or ()), b=b,
                                      entrada=entrada)
        return Description(summary=desc.summary + "\n\n---\n\n" + bloque,
                           figure_b64=desc.figure_b64,
                           recommendation=desc.recommendation,
                           data=desc.data)
    except Exception as e:
        _warn("lectura del operador en el nivel", e)
        return desc


@mcp.tool()
def intervention_plot(omega: list[float],
                      delta: list[float] | None = None,
                      b: int = 0,
                      inp_path: str = "",
                      at: int = 0,
                      ventana: int = 8,
                      K: int = 24,
                      entrada: str = "escalon",
                      sobre: str = "residuos",
                      label: str = "") -> list:
    """
    
    **Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar una respuesta impulso concreta sobre los datos sin avanzar el flujo.
    GRÁFICO DE INTERVENCIÓN — la forma de una intervención, sola o superpuesta
    a lo observado.

    Dos modos, según se pase `inp_path` y `at`:

      SIN inp_path  → dibuja la HIPÓTESIS SOLA: respuesta al impulso y al
                      escalón, en el nivel y en primeras diferencias, con la
                      ganancia a largo plazo. Para razonar sobre una forma antes
                      de tener modelo.
      CON inp_path
      y `at`        → SUPERPONE esa hipótesis sobre lo observado en el ENTORNO
                      del suceso, y devuelve tres números que dicen si encaja.

    POR QUÉ EXISTE. La forma de una intervención no se identifica a ojo: `fue`
    permite modelizar un suceso con varios parámetros (FLT), y en cuanto `s`
    crece la figura deja de tener lectura obvia. Se usa ANTES de estimar — si la
    forma ya se ve incompatible, estimarla gasta un modelo para confirmar lo que
    el gráfico decía gratis.

    EL CONVENIO. Toda intervención se especifica **en el nivel de la serie**,
    sea cual sea la d con la que se trabaje:

      · escalón en el nivel  → efecto PERMANENTE  → un impulso en ∇
      · impulso en el nivel  → efecto TRANSITORIO → dos impulsos en ∇ que suman 0
      · N escalones en el nivel con ganancia NULA ≡ N−1 impulsos en el nivel,
        es decir un EPISODIO de duración N−1

    LA CONVENCIÓN DE SIGNO, que es donde se cae. fue guarda el numerador con el
    convenio de Box-Jenkins, el mismo para TODO operador —AR, MA, δ y ω—: los
    coeficientes de retardo entran **restando**.

        ω(B) = ω₀ − ω₁B − ω₂B² − ⋯ − ω_sB^s

    Así que la ganancia es (ω₀−ω₁−⋯−ω_s)/(1−δ₁−⋯−δ_r) y **NO la suma de los ω**.
    Pásalos tal como salen del `.out`, sin cambiarles el signo.

    **No hace falta que hagas la resta.** La respuesta trae el CAMINO DEL NIVEL
    que producen los ω que has pasado, que es lo que quieres decir cuando
    escribes una hipótesis. Si el camino no es el que tenías en la cabeza, el
    signo estaba mal — y lo ves antes de estimar nada. Ejemplo real de la
    réplica: ω = (0.5700, +0.7236) tiene coeficientes que uno «sumaría» a
    +1.29, y su ganancia es **−0.15**.

    LOS TRES NÚMEROS del modo superpuesto separan tres preguntas, y se leen sin
    mirar la figura — así sirven también al carril autónomo:

      escala       cuánto hay que multiplicar la forma para que encaje. Cerca de
                   1 con ω estimados: la amplitud era la que se creía. Muy
                   lejos: se está estirando una forma que no da.
      R²           qué fracción del entorno explica la forma YA escalada. Bajo
                   con escala buena ⇒ el problema no es la amplitud, es el
                   PERFIL.
      mayor resto  el pico que sobrevive a quitar la forma, en desviaciones
                   típicas. Si tras ajustar sigue habiendo un 4, la hipótesis no
                   cubre lo que hay.

    DÓNDE NO LLEGA: la superposición **no** distingue una forma correcta de otra
    que deja una cola permanente pequeña — el R² apenas se mueve, porque la
    diferencia está en la GANANCIA A LARGO PLAZO, propiedad del comportamiento
    futuro y no de la forma local. Eso lo dirime el contraste ω(1)=0 de
    `test_interventions`. El gráfico descarta lo incompatible barato; el
    contraste ve lo que el gráfico no puede.

    Parameters
    ----------
    omega    : ω₀…ω_s del numerador, en el orden del `.out`
    delta    : δ₁…δ_r del denominador; vacío o None si no hay
    b        : retardo muerto en períodos
    inp_path : (superposición) .inp de un modelo estimado SIN la intervención
               que se hipotetiza — sus residuos son justo lo que ella debe
               explicar
    at       : (superposición) posición 1-based donde arranca el suceso
    ventana  : (superposición) períodos a mostrar antes y después del soporte
    K        : (hipótesis sola) hasta qué retardo simular
    entrada  : "escalon" usa la respuesta al escalón —el camino del nivel, que
               es el lenguaje homogeneizado del nodo—; "impulso" usa la IRF
    sobre    : (superposición) "residuos" (por defecto) o "serie"
    label    : etiqueta para el título

    Alcance: d = 0 y d = 1. Con d=2 un impulso en la serie transformada es una
    RAMPA en el nivel y el diccionario de arriba tiene otra fila.
    """
    try:
        from art.ltf import describe_ltf, describe_superposicion, _fecha_de
        if not inp_path:
            # BUG-0136: la entrada decide qué es ν(1) — desplazamiento del
            # nivel con escalón, área acumulada con impulso.
            desc = describe_ltf(omega, delta or (), entrada=entrada,
                                b=b, K=K, etiqueta=label)
            desc = _con_convenio(desc, omega, delta, b, entrada)
            _escribe_fig(desc.figure_b64, "intervention_plot")
            return _result(desc)

        import numpy as np
        if not at:
            return _err("con `inp_path` hay que dar `at`: dónde arranca el "
                        "suceso, 1-based, en el índice de aquello sobre lo que "
                        "se mira (ver `sobre`).")
        ts, m = _mirar(inp_path)
        # `_mirar` y no `_load_ts_model` + `fit()` a mano: esa vía no sella
        # el origen del fichero, y con ella el aviso de BUG-0090 es
        # inalcanzable — el contrato tenía tres puertas y una cuarta abierta.
        if sobre == "residuos":
            if m.residuals is None:
                return _err("el modelo no tiene residuos: ¿se estimó?")
            y = np.asarray(m.residuals.data, dtype=float)
            d_eff = int(getattr(m, "d", 0))
        elif sobre == "serie":
            y = np.asarray(ts.data, dtype=float)
            d_eff = 0
        else:
            return _err(f"sobre={sobre!r}: 'residuos' o 'serie'.")
        # EL CALENDARIO CRUZA LA FRONTERA — BUG-0140. `describe_superposicion`
        # recibe `observado` como una lista pelada; el `start`/`freq` los tiene
        # el servidor, y el desfase depende de SOBRE QUÉ se mira: cero sobre la
        # serie, `d + D·s` sobre residuos (BUG-0067).
        _f = int(getattr(ts, "freq", 1) or 1)
        # BUG-0172: la cuenta incluye `ifadf`; escrita a mano se quedaba corta.
        from art.identification import desfase_observaciones as _desf_obs
        _desf = _desf_obs(m) if sobre == "residuos" else 0
        _cuando = _fecha_de(int(at), _f, getattr(ts, "start", ()), _desf)
        desc = describe_superposicion(
            y, int(at), omega, delta or (), b=b, d=d_eff,
            ventana=int(ventana), entrada=entrada,
            freq=_f, start=getattr(ts, "start", ()), desfase=_desf,
            etiqueta=label or (f"{os.path.basename(inp_path)} — around "
                               f"{_cuando or f'obs {at}'}"))
        desc = _con_convenio(desc, omega, delta, b, entrada)
        _escribe_fig(desc.figure_b64, "intervention_plot")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: episodios — agrupar los extremos en SUCESOS
# ---------------------------------------------------------------------------

@mcp.tool()
def residual_episodes(inp_path: str,
                      ventana: int = 0,
                      threshold: float = 3.0) -> list:
    """
    
    **Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar cómo se agrupan los extremos en sucesos sin avanzar el flujo.
    Agrupa los residuos extremos de un modelo estimado en EPISODIOS.

    LA PREGUNTA DE ESTE NODO no es «cuántos atípicos hay» sino **«esto es un
    suceso o son varios»**. Un choque puede durar más de un período, y tratado
    como atípicos sueltos se modeliza mal: sobre la réplica, encontrar la
    segunda intervención del episodio 2008-09 valía **16,24 puntos de AIC**, y
    sólo 1 de 8 corridas la encontró.

    QUÉ DEVUELVE. Los episodios con su tramo, duración, cohesión y la
    ESPECIFICACIÓN GENERAL que le corresponde a cada uno: un episodio de
    duración L son **L+1 escalones en el nivel** desde su inicio. Con ganancia
    ω(1)=0 equivalen a L impulsos en el nivel (efecto TRANSITORIO); con ganancia
    distinta de cero, a un cambio de nivel PERMANENTE. Cuál de las dos cosas lo
    dice el contraste —`test_interventions`—, no la forma del grupo.

    Esto sustituye a la dicotomía escalón/impulso decidida por adyacencia: deja
    de ser una REGLA y pasa a ser un CONTRASTE.

    Parameters
    ----------
    inp_path  : .inp de un modelo estimado
    ventana   : hueco máximo entre extremos consecutivos para que sean el mismo
                suceso. 0 = usar la de la política (2). 1 = estrictamente
                adyacentes; 3 admite dos períodos tranquilos dentro.
    threshold : |z| a partir del cual un residuo es extremo

    Juzga la agrupación sobre el gráfico antes de estimar nada. Para ver qué
    FORMA implica un episodio, el `intervention_plot` la dibuja.
    """
    try:
        import numpy as np
        from art.episodes import describe_episodios
        from art.policy import decide_episodios, THRESHOLDS
        ts, m = _mirar(inp_path)
        # `_mirar` y no `_load_ts_model` + `fit()` a mano: esa vía no sella
        # el origen del fichero, y con ella el aviso de BUG-0090 es
        # inalcanzable — el contrato tenía tres puertas y una cuarta abierta.
        if m.residuals is None:
            return _err("el modelo no tiene residuos: ¿se estimó?")
        r = np.asarray(m.residuals.data, dtype=float)
        sd = r.std(ddof=0)
        z = r / sd if sd > 0 else r
        ext = [(i + 1, float(z[i])) for i in range(len(z))
               if abs(z[i]) > threshold]
        v = int(ventana) or THRESHOLDS["ventana_episodio"]
        d_reg = int(getattr(m, "d", 0))
        eps = decide_episodios(ext, ventana=v, d=d_reg)
        from art.identification import desfase_observaciones as _desf_obs
        off = _desf_obs(m)                                    # BUG-0172
        desc = describe_episodios(r, eps, ventana=v, umbral=threshold, offset=off)
        _escribe_fig(desc.figure_b64, "episodios")
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
        _escribe_fig(desc.figure_b64, "seasonality")
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
        _escribe_fig(desc.figure_b64, "unit_root")
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
        _escribe_fig(desc.figure_b64, "identification")
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
    
    **Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar los anómalos de una serie aún sin modelo sin avanzar el flujo.
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
            # QUÉ CUENTA COMO «llevar un modelo». La comprobación miraba si
            # había algún factor ARMA, y eso dejó de discriminar en cuanto
            # `_write_inp` empezó a escribir el AR(1) fijado en cero que esquiva
            # el segfault del binario (fue/BUG-0013): con él, una serie pelada y
            # un modelo estimado se parecen. Un factor fijo en cero no es
            # estructura —no entra en la verosimilitud ni en `npar`— y por eso
            # `tiene_estructura_arma` lo descarta.
            #
            # Pero la estructura tampoco basta: un modelo de sólo `d=1` no tiene
            # NINGÚN término y sigue siendo un modelo estimado, con sus residuos,
            # que es exactamente el caso en que este aviso hace falta. Lo que lo
            # distingue no es su contenido sino que se ESTIMÓ, y de eso queda
            # constancia al lado: el `.out` y el `.pre` de su terna.
            from art.pipeline import tiene_estructura_arma
            _base = os.path.splitext(os.path.expanduser(inp_path))[0]
            _estimado = any(os.path.exists(_base + ext)
                            for ext in (".out", ".pre"))
            _tiene_modelo = bool(
                _estimado
                or tiene_estructura_arma(_m_cargado)
                or (getattr(_m_cargado, "interventions", None) or [])
                or getattr(_m_cargado, "estimate_mu", False)
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
        except Exception as _e:               # BUG-0160: no se calla
            _warn("no se pudo componer el aviso del método en preliminary_outlier_scan", _e)

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
            items.append(_imagen(desc.figure_b64, "preliminary_outlier_scan"))
        return items
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Model equation display (Bloque O)
# ---------------------------------------------------------------------------

@mcp.tool()
def residual_outlier_scan(inp_path: str, threshold: float = _Z_USER,
                          omitir: list | None = None,
                          motivo: str = "") -> list:
    """
    
    **Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar los anómalos de un modelo ya estimado sin avanzar el flujo.
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

    QUÉ SE CALIBRA — tres criterios, una sola figura (BUG-0133):

    * por UMBRAL (por defecto)   `threshold=3.0`
    * por OBSERVACIÓN            `omitir=["Q2/2020"]`
    * por INCIDENTE              `omitir=["Q4/2008", "Q1/2009", "Q2/2009"]`

    Con `omitir` el umbral no interviene: se quita exactamente lo que se pide,
    lo marque o no. Es lo que el nodo de intervención necesita antes de elegir
    la forma — «¿cómo queda el correlograma sin este suceso?» — y evita tener
    dos figuras para la misma pregunta.

    Parameters
    ----------
    inp_path  : .inp of an estimated model (per the file convention, estimate
                from the .inp, not the .pre)
    threshold : |z| threshold for flagging (default 3.5)
    omitir    : fechas ("Q2/2020") o índices 0-based a omitir en la calibración.
                Si se da, sustituye al umbral como criterio.
    motivo    : qué se está omitiendo, para la cabecera («el episodio 2008-09»)
    """
    try:
        import fue as _fue
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_prelim_scan, _resid_start
        ts, m = _mirar(inp_path)
        # `_mirar` y no `_load_ts_model` + `fit()` a mano: esa vía no sella
        # el origen del fichero, y con ella el aviso de BUG-0090 es
        # inalcanzable — el contrato tenía tres puertas y una cuarta abierta.
        if m.residuals is None:
            return _err("el modelo no tiene residuos: ¿se estimó?")
        res_ts = _fue.TimeSeries(
            m.residuals.data, freq=ts.freq, start=_resid_start(m),
            name=f"Resid {ts.name or ''}".strip(),
        )
        desc = describe_prelim_scan(res_ts, d=0, D=0, lam=1.0,
                                    threshold=threshold,
                                    omitir=omitir, motivo=motivo)
        cab = (f"*Escaneo sobre los RESIDUOS de `{os.path.basename(inp_path)}` "
               f"(n={len(m.residuals.data)}), no sobre la serie.*\n\n")

        # Si hay extremos cerca unos de otros, DECIRLO aquí. La razón medida de
        # que 7 de 8 corridas no encontraran el segundo choque del episodio
        # 2008-09 —16,24 puntos de AIC— es que nada en la salida decía que esos
        # dos anómalos eran UN suceso. Una herramienta que nadie llama no lo
        # arregla; el aviso donde el analista ya está mirando, sí.
        try:
            import numpy as _np
            from art.policy import decide_episodios as _de
            _r = _np.asarray(m.residuals.data, dtype=float)
            _sd = _r.std(ddof=0)
            _z = _r / _sd if _sd > 0 else _r
            _ext = [(i + 1, float(_z[i])) for i in range(len(_z))
                    if abs(_z[i]) > threshold]
            _eps = [e for e in _de(_ext, d=int(getattr(m, 'd', 0)))
                    if not e.aislado]
            if _eps:
                _t = ", ".join(f"{e.inicio}–{e.fin} ({e.duracion_nivel} períodos en el nivel)"
                               for e in _eps)
                cab += (f"⚠ **{len(_eps)} de estos anómalos no están solos: "
                        f"{_t}.** Un suceso que dura varios períodos modelizado "
                        "como atípicos sueltos se ajusta mal. Llama a "
                        "`residual_episodes` antes de decidir la forma.\n\n")
        except Exception as _e:               # BUG-0160: no se calla
            _warn("no se pudo componer el aviso del método en residual_outlier_scan", _e)
        # LA CALIBRACIÓN DEL CORRELOGRAMA — las DOS funciones.
        # La PACF decide el orden AR y la ACF el orden MA; calibrar sólo una
        # deja media identificación a ciegas, y no porque una prediga a la otra
        # sino porque NO la predice: pueden cambiar de veredicto en sentidos
        # opuestos en el mismo retardo.
        cal_txt, cal_b64 = "", None
        try:
            from art.calibracion import calibra_correlograma, describe_calibracion
            # BUG-0133. La tabla tiene que calibrar por el MISMO criterio que
            # la figura. Antes la figura omitía el incidente y la tabla seguía
            # con el umbral: dos calibraciones distintas en la misma pantalla, y
            # el veredicto —«cambia / no cambia la identificación»— salía de la
            # que no era, contestando a una pregunta que nadie había hecho.
            #
            # Los índices los publica `describe_prelim_scan` ya resueltos, que
            # es quien sabe traducir la fecha: hacerlo aquí otra vez sería la
            # misma cuenta en dos sitios.
            _om = ({int(i) for i in (desc.data or {}).get("omitidos", [])}
                   if omitir is not None else None)
            _f = int(getattr(ts, "freq", 1) or 1)
            _cal = calibra_correlograma(
                m._result.residuals, umbral=threshold, omitir=_om,
                freq=_f, start=getattr(ts, "start", ()),
                desfase=_desfase_obs(m))                      # BUG-0172
            # BUG-0133: sólo la TABLA. La figura de esta llamada es la del
            # escaneo, que es el gráfico de calibración de distorsiones.
            _d = describe_calibracion(_cal, nombre=os.path.basename(inp_path),
                                      con_figura=False)
            cal_txt = "\n\n---\n\n" + _d.summary + "\n\n" + _d.recommendation
            cal_b64 = _d.figure_b64
        except Exception as _ce:
            cal_txt = f"\n\n*[calibración del correlograma no disponible: {_ce}]*"

        # P8: la figura que ABRE VENTANA es la de calibración, no la vieja de
        # contribución a la ACF. Antes era al revés: la nueva —dos paneles, PACF
        # arriba y ACF abajo, con los retardos que cambian de veredicto— llegaba
        # como ImageContent pero SIN `_show_fig`, así que nunca abría ventana;
        # y la vieja, que sólo enseña la ACF, sí la abría. El analista tenía en
        # pantalla justo la que sobra, y no veía la calibración de la PACF —que
        # es la mitad que decide el orden AR.
        #
        # La vieja se retira: está enteramente contenida en la nueva, que además
        # da la PACF y el veredicto por retardo.
        # La figura del ESCANEO es la que vuelve a mandar: lleva la serie —donde
        # el analista ve DÓNDE está el suceso— más la ACF y ahora también la
        # PACF, con la parte que ponen los anómalos en rojo. Ayer la retiré
        # entera para poner una de dos paneles sin los datos, y perder el panel
        # de la serie fue un retroceso: lo que faltaba era añadir la PACF.
        _escribe_fig(desc.figure_b64, "escaneo")
        items = [TextContent(type="text", text=cab + desc.summary
                             + "\n\n---\n" + desc.recommendation + cal_txt)]
        if desc.figure_b64:
            items.append(_imagen(desc.figure_b64, "residual_outlier_scan"))
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
        ts, m = _load_fitted(inp_path)
        # `_load_fitted` y no `_load_ts_model` + `fit()` a mano: esa vía no sella
        # el origen del fichero, y con ella el aviso de BUG-0090 es
        # inalcanzable — el contrato tenía tres puertas y una cuarta abierta.
        eq_text = _equation_for_prompt(ts, m)
        return [TextContent(type="text", text=eq_text)]
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Estimate and diagnose
# ---------------------------------------------------------------------------

@mcp.tool()
def estimate_and_diagnose(inp_path: str, output_path: str = "",
                          base_pre_path: str = "",
                          guion_path: str = "",
                          guion_name: str = "",
                          guion_decision: str = "",
                          guion_rationale: str = "",
                          guion_problems: str = "",
                          guion_next: str = "",
                          include_histogram: bool = False,
                          modo: _Modo = "guiado") -> list:
    """
    Fit the model specified in an .inp file and run diagnosis.

    Estimates the model by maximum likelihood (fue MVENC) and runs the
    full diagnosis: standardised residuals, ACF/PACF, Ljung-Box Q-test,
    Jarque-Bera normality test, and residual seasonality check.

    **base_pre_path — DECLARA DE QUÉ MODELO SALE ÉSTE.** This tool re-reads an
    `.inp` as it stands, so it has no other way of knowing the lineage: without
    it the guion records the LAST entry as the parent, which need not be the
    real one. That matters because `guion_abandon` propagates to descendants BY
    DESIGN — a false parent turns a correct abandonment into a destructive one.
    Pass it whenever the `.inp` was built from another model, which is the usual
    case for hand-built factorised or fixed-frequency AR models.

    Parameters
    ----------
    inp_path    : path to the .inp file with the model specification
    modo        : "guiado" (por defecto) | "autonomo". En GUIADO la salida
                  termina en ⏸ y espera al analista. En AUTÓNOMO el analista
                  eres tú —el LLM—, así que no hay a quién esperar y la salida
                  NO para: pásalo en cada llamada del carril autónomo
                  (BUG-0180, BUG-0181).
    include_histogram : devolver además el histograma de residuos (por defecto
                  False, igual que en `confirm_and_estimate`). El histograma NO
                  es parte del módulo básico de diagnosis: se pide (BUG-0129).
    output_path : if given, also persist the fitted model as the ``.pre``
                  (= .inp with the estimated parameters, to seed the next step)
                  and ``.out`` (ASCII results report) alongside this basename —
                  the same trio confirm_and_estimate writes, so a model estimated
                  through this clean path is not left without artefacts.  Empty
                  (default) keeps the old screen-only behaviour.
    guion_*     : lo mismo que en `confirm_and_estimate`. Con `output_path` la
                  entrada de guion **se escribe igual que allí**, y `guion_path`
                  se deriva si no se da: el guion es obligatorio, no opcional.

                  BUG-0088. Esta herramienta persistía el trío `.pre`/`.out`
                  —el docstring lo prometía con esas palabras— y NO el guion.
                  Un modelo estimado por esta vía quedaba con artefactos y sin
                  su entrada, y el guion se desincronizaba **en silencio**. En
                  la sesión FOOD_UEM la escalera de Ucrania entera se construyó
                  así y hubo que reescribir el guion a mano.

                  De las tres salidas que el reporte proponía, ésta es la que
                  mantiene la promesa del docstring: lo inconsistente era
                  persistir los artefactos y no el registro, y quitar los
                  artefactos habría quitado también la razón de ser de la
                  herramienta.
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        ts, m = _load_fitted(inp_path)
        # `_load_fitted` y no `_load_ts_model` + `fit()` a mano: esa vía no sella
        # el origen del fichero, y con ella el aviso de BUG-0090 es
        # inalcanzable — el contrato tenía tres puertas y una cuarta abierta.
        try:
            eq_text = _equation_for_prompt(ts, m)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"
        desc = describe_diagnosis(m)
        _escribe_fig(desc.figure_b64, "diagnosis")
        text = envuelve_iteracion(
            nombre=os.path.splitext(os.path.basename(output_path or inp_path))[0],
            # El carril lo declara quien llama. Estaba fijo en «guiado», y en
            # AUTÓNOMO cada estimación mandaba al LLM parar y esperar a un
            # analista que no existe (BUG-0181).
            modo=_modo_del_sobre(modo),
            especificacion=(f"`{os.path.basename(inp_path)}` estimado tal como "
                            f"está: esta vía no construye especificación, la "
                            f"relee." + aviso_rampa(m)),
            ecuacion=eq_text,
            diagnosis=desc.summary + "\n\n---\n" + desc.recommendation,
            conclusiones=_conclusiones_desde(desc),
            alternativas=_alternativas_desde(
                desc, model=m, ts=getattr(m, "series", None),
                inp_path=output_path or inp_path,
                guion_path=guion_path),
            reformulacion=_reformulacion_desde(desc, guion_next),
        )
        if output_path:
            # LA TERNA, COMPLETA (BUG-0092). `_persist_pre_out` escribe el `.pre`
            # y el `.out` en el basename de `output_path`, y el `.inp` no estaba:
            # la entrada del guion apuntaba a un fichero inexistente, que es justo
            # el camino por el que el analista vuelve a un nodo.
            #
            # Se COPIA el `.inp` fuente byte a byte, no se reserializa el modelo
            # ajustado. Escribir un modelo ajustado bajo nombre de `.inp` es la
            # trampa de BUG-0027 —los valores estimados pasarían por semillas y
            # la siguiente estimación arrancaría en el óptimo—, y la copia
            # literal no puede caer en ella.
            text += _asegura_inp_de_la_terna(inp_path, output_path)
            text += _persist_pre_out(m, output_path)
            # El registro va con los artefactos, no aparte. `lam` sale del
            # propio modelo: aquí no se pasa la especificación, se relee.
            try:
                nota = _record_to_guion(
                    model=m, inp_path=output_path,
                    lam=float(getattr(m, "boxlam", 0.0)),
                    guion_path=guion_path or _derive_guion_path(output_path, m),
                    name=guion_name, decision=guion_decision,
                    rationale=guion_rationale, problems_found=guion_problems,
                    next_version=guion_next, figure_b64=desc.figure_b64,
                    hist_b64=(desc.data or {}).get("hist_b64"),
                    # DE QUÉ MODELO SALE ÉSTE. Sin esto `infer_parent` caía en
                    # «la última entrada del guion», que no tiene por qué ser el
                    # padre: un `.inp` construido a mano —los AR factorizados y
                    # los AR(2) de frecuencia fija, que la superficie MCP no
                    # expone (BUG-0103)— entra por aquí con un padre INVENTADO.
                    #
                    # Y el linaje falso hace destructiva la única operación que
                    # da valor al guion: `guion_abandon` arrastra descendientes
                    # POR DISEÑO, así que marcar un callejón correcto podía
                    # barrer la rama viva (BUG-0108).
                    base_pre_path=base_pre_path)
                if nota:
                    text += f"\n\n{nota}"
            except Exception as _ge:
                # Documentar no puede tumbar una estimación válida — pero
                # tampoco puede fallar en silencio, que es el defecto que este
                # arreglo viene a cerrar.
                _warn("registro del guion en estimate_and_diagnose", _ge)
                text += (f"\n\n⚠ *guion NO registrado "
                         f"({type(_ge).__name__}: {_ge}). El modelo está en "
                         f"disco y el guion no lo refleja.*")
        # BUG-0129. Tres sitios y tres respuestas sobre la misma pregunta:
        # `confirm_and_estimate` tiene `include_histogram=False` («default
        # False — saves tokens»), `model_histogram` existe para pedirlo aparte
        # y su docstring dice «the histogram is not part of the basic
        # diagnostic module — request it explicitly», y aquí se mandaba
        # SIEMPRE. 34 KB por iteración que nadie pidió.
        #
        # Y las rutas no se decían: los ficheros se escriben, pero esta vía
        # compone su sobre a mano y el BUG-0113 —«di dónde está la figura»—
        # sólo cubrió el carril guiado y `_result`.
        items = [TextContent(type="text", text=text)]
        _rutas = []
        if desc.figure_b64:
            _rutas.append(_escribe_fig(desc.figure_b64, "diagnosis"))
            items.append(_imagen(desc.figure_b64, "diagnosis"))
        if include_histogram:
            hist_b64 = (desc.data or {}).get("hist_b64")
            if hist_b64:
                _rutas.append(_escribe_fig(hist_b64, "histograma"))
                items.append(_imagen(hist_b64, "histograma"))
        _nota = "".join(_nota_figura(r) for r in _rutas if r)
        if _nota:
            items[0] = TextContent(type="text",
                                   text=_con_nota_figura(text, _rutas[0])
                                   if len(_rutas) == 1 else text + _nota)
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
        ts, m = _mirar(inp_path)
        desc = describe_diagnosis(m)
        b64 = desc.data.get("hist_b64") or desc.figure_b64
        if b64 is None:
            return _err("No se pudo generar el histograma de residuos.")
        return [_imagen(b64, "model_histogram")]
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
        except Exception as _e:               # BUG-0160: no se calla
            _warn("no se pudo componer el aviso del método en overparameterization_analysis", _e)

        if corr is None:
            return [TextContent(type="text",
                                text="No se pudo calcular la matriz de correlación "
                                     "(modelo no estimado o sin matriz de covarianza).")]

        n = corr.shape[0]

        # SIN HEATMAP — BUG-0137.
        #
        # Aquí había un mapa de calor de la matriz de correlación, con recuadro
        # en el bloque ARMA+μ y borde dorado en los pares marcados. Se retira
        # por decisión del analista en el censo de figuras: «no es necesaria; la
        # tabla hace su trabajo y avisa. Esto es sobre-elaborar».
        #
        # Y es correcto: la tabla de arriba da los pares, su r y su diagnóstico
        # —estructural o redundante—, que es lo que se hace con ellos. El
        # heatmap enseñaba el mismo dato en dos dimensiones sin cambiar ninguna
        # decisión. 212 líneas de matplotlib DENTRO del servidor, y 1 llamada en
        # 1.114 registradas.
        #
        # Lo que quedó anotado del censo y no se arreglaba aquí —las etiquetas
        # no distinguían dos parámetros distintos: `ω(S)` aparecía dos veces,
        # una por intervención, sin la fecha— está arreglado en BUG-0141. La
        # tabla de abajo dice ahora `ω(S,Q4/2008)`, que es la misma fecha del
        # `.inp` y del `.out`.
        b64 = None

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
            items.append(_imagen(b64, "overparameterization_analysis"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Formal tests
# ---------------------------------------------------------------------------

@mcp.tool()
def formal_tests(inp_path: str, run_meg: bool = True,
                 subdiferenciacion: bool = False) -> list:
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
    subdiferenciacion : contrastar además el lado **d−1** — ¿sobraba la última
               diferencia? **Por defecto NO, y es deliberado.** El par
               confirmatorio en f=0 lo forman Shin-Fuller sobre el AR y el DCD
               con testigo de sobrediferenciación, complementarios como ADF y
               KPSS en la especificación inicial; ése se corre siempre.

               El lado d−1 **se pide, no se ofrece**: correr una batería de
               contrastes que nadie pidió y presentar su ✓ es pre-testing, y el
               veredicto no tiene el tamaño que aparenta. Pídelo cuando haya
               MOTIVO: la serie parece estacionaria en nivel, es un precio
               relativo, o se está en un estudio de cointegración.

               Y cuando lo pidas, lee BUG-0167: con un AR de orden 1 el brazo
               nulo gasta su única raíz en la unitaria y el LR mide dinámica
               perdida, no frontera.
    """
    try:
        from mcp.types import TextContent
        from art.describe import describe_formal_tests
        from art.diagnosis import diagnose
        ts, m = _load_fitted(inp_path)
        desc = describe_formal_tests(m, run_meg=run_meg,
                                     subdiferenciacion=subdiferenciacion)

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
        # ¿PARECE ESTO UN OPERADOR EN B^s? Y si lo parece, decirlo con la
        # advertencia de que PARECERLO NO ES SERLO.
        #
        # Un operador (1 − Θ·B^N) tiene sus N raíces con el MISMO módulo y en
        # ángulos CLAVADOS a 2πk/N. Por tanto unos módulos casi iguales en la
        # factorización libre son exactamente su firma — y ahí está la trampa:
        # es la firma de la HIPÓTESIS, no la prueba de que se cumpla. Leerlos
        # así IMPONE la restricción en vez de contrastarla.
        #
        # Pasó en UEM_HCPI_0219 y quedó registrado en el nodo v4 del guion: el
        # asistente propuso sustituir un AR(6) por (1 − φ₁B − φ₆B⁶) porque los
        # seis módulos salían entre 1.2684 y 1.2934, y hubo que corregirlo a
        # mano. El propio caso da la medida de lo que se estaba imponiendo: la
        # factorización LIBRE daba periodos 3.03 y 6.67 frente a los 3.00 y 6.00
        # que el operador en B⁶ fija por decreto — un 11.1% de desvío en el
        # segundo (BUG-0103).
        try:
            mods = []
            for k, factor in enumerate(factors):
                r = np.roots([1.0] + [-float(c) for c in factor])
                mods.extend(float(abs(x)) for x in r if abs(x) > 1e-12)
            if len(mods) >= 4:
                disp = (max(mods) - min(mods)) / max(np.mean(mods), 1e-12)
                if disp < UMBRAL_MODULOS_PARECIDOS:
                    N = len(mods)
                    blocks.insert(0,
                        f"⚠ **Los {N} módulos son casi iguales** "
                        f"({min(mods):.4f}–{max(mods):.4f}, dispersión relativa "
                        f"{disp:.1%}), que es **exactamente el aspecto que "
                        f"tendría un operador en B^{N}**.\n\n"
                        f"**Eso es la hipótesis, no el hallazgo.** Un "
                        f"(1 − Θ·B^{N}) impone un amortiguamiento ÚNICO común a "
                        f"todas las frecuencias y las clava en 2πk/{N}; aquí las "
                        f"frecuencias están LIBRES y pueden desviarse. Sustituir "
                        f"el operador completo por uno en B^{N} son "
                        f"{N - 1} restricciones, y por uno disperso "
                        f"(1 − φ₁B − φ_{N}B^{N}) son {N - 2} — **ninguna "
                        f"contrastada**.\n\n"
                        f"**No lo impongas: contrástalo.** Estima primero el "
                        f"modelo FACTORIZADO —misma verosimilitud, mismos grados "
                        f"de libertad, reparametrización exactamente "
                        f"identificada— para que cada factor reciba su `d ± SE` y "
                        f"su `periodo ± SE`; con eso se ve si los "
                        f"amortiguamientos son de verdad iguales y si los "
                        f"periodos admiten la frecuencia estacional. La "
                        f"restricción se contrasta después, por razón de "
                        f"verosimilitudes y con sus grados de libertad "
                        f"(art/bugs/BUG-0103).")
        except Exception as _e:                              # pragma: no cover
            _warn("dispersión de módulos en ar_factorization", _e)

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
        # BUG-0159. `src` es casi siempre un `.pre` — es el convenio de
        # encadenar, y `base_pre_path` lo dice en el nombre. De este modelo sólo
        # se toma la ESTRUCTURA y la serie; el modelo REFORMULADO se estima aparte, y de
        # ahí salen los errores típicos que se imprimen. Así que aquí toca
        # `mirar`, no `estimar`. Mientras estimar desde un `.pre` sólo avisaba,
        # la diferencia no se veía; cuando pasó a negarse, se vio.
        ts, m = _mirar(src)
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
        # LA ECUACIÓN NO VA AQUÍ. Esta cabecera es la ESPECIFICACIÓN —qué se
        # activó, en qué frecuencia, con o sin testigo, desde qué `.pre`— y su
        # sitio es la etapa 1 del sobre. La ecuación va en `ecuacion=`, que es
        # la etapa 2.
        #
        # Llevaba `{eq}` al final, de cuando esta función componía su salida a
        # mano. Al envolverla en el sobre (BUG-0094) se añadió el campo correcto
        # y NO se quitó el texto que ya lo llevaba: el bloque «MODELO ESTIMADO»
        # salía DOS VECES, idéntico, en las secciones 2 y 3 del mismo informe.
        # Un residuo del propio arreglo (BUG-0120).
        header = (f"## Reformulación MEG — estacionalidad ESTOCÁSTICA en f={f}\n\n"
                  f"Activado el AR_f de raíz unitaria `ifadf[{f}]=1` {kind}"
                  f"{witness_line} Eliminados los armónicos deterministas en f={f}. "
                  f"Re-estimado desde `{os.path.basename(src)}`.")
        # El sobre de las cuatro etapas también aquí. `meg_reformulate` ES una
        # reformulación —la etapa 4 con nombre propio— y era una de las dos
        # herramientas que CIERRAN una iteración y emitían sin él. La otra es
        # `record_version`. Las 40 restantes no son iteraciones: son
        # instrumentos, y ponerle una «reformulación» a un ACF sería inventarla.
        _esp_meg = header
        _diag_meg = diag.summary + "\n\n---\n" + diag.recommendation
        _extra_meg = (f"*Modelo guardado en: {output_path}  |  "
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
                _extra_meg += f"\n\n{nota}"
            except Exception as e:
                _warn("no se pudo registrar la reformulación MEG en el guion", e)

        diag.summary = envuelve_iteracion(
            nombre=os.path.splitext(os.path.basename(output_path))[0],
            especificacion=_esp_meg,
            ecuacion=eq,
            diagnosis=_diag_meg,
            reformulacion=_reformulacion_desde(diag, ""),
            extra=_extra_meg,
        )
        diag.recommendation = ""   # ya va dentro del sobre, en DIAGNOSIS
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
        # BUG-0159. `src` es casi siempre un `.pre` — es el convenio de
        # encadenar, y `base_pre_path` lo dice en el nombre. De este modelo sólo
        # se toma la ESTRUCTURA y la serie; los dos modelos del LR —libre y λ₂=−1— se estiman aparte, y de
        # ahí salen los errores típicos que se imprimen. Así que aquí toca
        # `mirar`, no `estimar`. Mientras estimar desde un `.pre` sólo avisaba,
        # la diferencia no se veía; cuando pasó a negarse, se vio.
        ts, m = _mirar(src)
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
    
    **Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar los anómalos antes de decidir nada sin avanzar el flujo.
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
        _, m = _mirar(inp_path)
        return _result(describe_interventions(m, threshold=threshold))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Full report
# ---------------------------------------------------------------------------
# Tool: intervention significance testing (Phase 4b)
# ---------------------------------------------------------------------------

@mcp.tool()
def test_interventions(inp_path: str, alpha: float = 0.05,
                      ganancia_neta: list = []) -> list:
    """
    
    **Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar si las intervenciones ya puestas se sostienen sin avanzar el flujo.
    Test H₀: ω=0 for every non-structural intervention in a fitted model.

    Runs a t-test on each free omega parameter of pulse, step, ramp, and
    similar interventions (cosine/sine harmonics and alter are structural
    and skipped by default). Identifies which interventions are non-significant
    and can be removed to simplify the model.

    Para cualquier intervención con más de un ω libre, además el Wald conjunto
    de GANANCIA NULA, H₀: ω(1) = ω₀−ω₁−⋯−ω_s = 0 — que es lo que separa un
    efecto transitorio de uno permanente (BUG-0071/0072).

    Y LA REGLA DE TREADWAY, que es diagnosis y no bloqueo: si intervienes en una
    fecha no puedes tener un anómalo de vecino, ni antes ni después; y que la
    intervención haya funcionado se ve en que los residuos EN LAS FECHAS
    intervenidas están en la media de los residuos. Un vecino anómalo tiene dos
    lecturas, las dos errores de representación: la FORMA se queda corta (hay
    episodio) o la FECHA está desplazada.

    LA GANANCIA NETA DE UN EPISODIO REPARTIDO (`ganancia_neta`). Un suceso con
    VUELTA DIFERIDA no cabe en una sola intervención: entre la caída y el rebote
    hay períodos tranquilos, así que `residual_episodes` los separa y ninguna
    forma del catálogo abarca los dos. La forma que sí lo hace son dos escalones
    —uno por tramo— y entonces la pregunta ya no es la ganancia de cada uno sino
    la SUMA: H₀ Σᵢ ωᵢ(1) = 0, un Wald χ²(1) exacto sobre la covarianza conjunta.
    Pasa los índices 0-based: `ganancia_neta=[0, 1]`.

    Da TRES lecturas, no dos — la del medio es la que el catálogo no sabía
    nombrar, y es la que los episodios reales suelen tener:

        no se rechaza                  el nivel VOLVIÓ        transitorio
        se rechaza, |neta| < |caída|   volvió EN PARTE        recuperación PARCIAL
        se rechaza, neta ≈ caída       no volvió              permanente

    Sin esto la caída sale rotulada «PERMANENTE» sin haber mirado el rebote, y
    ése es un veredicto sobre su propio tramo que se lee como el del suceso
    (BUG-0157). Un impulso pesa 0 en la suma: su efecto en el nivel es cero por
    construcción, no por estimación (BUG-0076).

    Parameters
    ----------
    inp_path      : path to a fitted .inp or .pre file
    alpha         : significance level for classification (default 0.05)
    ganancia_neta : índices 0-based de dos o más intervenciones del MISMO
                    suceso, para contrastar su ganancia neta. Vacío = no se hace.
    """
    try:
        from mcp.types import TextContent
        from art.interventions import simplify_interventions, simplify_summary

        ts, m = _load_fitted(inp_path)
        fallos: list = []
        results = simplify_interventions(m, alpha=alpha, fallos=fallos)

        if not results:
            # BUG-0090: «no hay» y «no se pudo» son cosas distintas, y decir la
            # primera cuando pasa la segunda borra la razón. Sobre un modelo
            # estimado desde un `.pre` esto respondía «No hay intervenciones»
            # teniendo una delante.
            if fallos:
                det = "\n".join(
                    f"- `{t}` [{i}]: {motivo}" for i, t, motivo in fallos)
                try:
                    from art.pipeline import aviso_se_no_fiable
                    extra = aviso_se_no_fiable(m)
                except Exception:
                    extra = ""
                return [TextContent(type="text", text=(
                    f"⚠ **Hay {len(fallos)} intervención(es) y NINGUNA se pudo "
                    f"contrastar.**\n\n{det}\n\nNo es que no haya "
                    f"intervenciones: es que el contraste no se puede hacer "
                    f"sobre este modelo." + extra))]
            return [TextContent(type="text",
                                text="*No hay intervenciones no-estructurales en el modelo.*")]

        try:
            eq_text = _equation_for_prompt(ts, m)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"

        summary   = simplify_summary(results, alpha=alpha)
        n_sig     = sum(1 for r in results if r.significant)
        n_nosig   = len(results) - n_sig

        # La regla de Treadway. Va AQUÍ, donde el analista ya está juzgando la
        # intervención, y no en una herramienta aparte: un contraste que dice
        # que ω es significativa no dice que la REPRESENTACIÓN sea la correcta,
        # y ésa es justamente la pregunta que queda abierta después del t.
        treadway = ""
        try:
            from art.interventions import check_intervention_fit
            chks = check_intervention_fit(m)
            if chks:
                malas = [c for c in chks if not c.funciona]
                cab = (f"**{len(chks) - len(malas)} de {len(chks)}** intervenciones "
                       "pasan la regla de Treadway")
                treadway = ("\n\n---\n\n### ¿Funcionó la intervención? "
                            "(regla de Treadway)\n\n" + cab + "\n\n```\n"
                            + "\n".join(c.summary() for c in chks) + "\n```\n")
                if malas:
                    treadway += (
                        "\nUn vecino anómalo es **evidencia de que la "
                        "representación elegida es errónea**. Dos lecturas: la "
                        "FORMA se queda corta —mira `residual_episodes`— o la "
                        "FECHA está desplazada, que la verosimilitud casi no "
                        "distingue (BUG-0030: Δ logL = 0,03). El "
                        "`intervention_plot` superpone la hipótesis sobre el "
                        "entorno y lo resuelve antes de reestimar.\n")
        except Exception as _tw:
            treadway = f"\n\n*[regla de Treadway no disponible: {_tw}]*\n"

        # EL CONVENIO DE SIGNO, CALCULADO EN VEZ DE RECORDADO.
        #
        # fue guarda ω(B) = ω₀ − ω₁B − ⋯, el convenio de Box-Jenkins, el mismo
        # para todo operador. Es consistente y no se toca. Lo que cuesta es que
        # obliga a una resta mental cada vez que se lee un ω, y esa resta se
        # falla: en la sesión de la réplica se falló dos veces seguidas al
        # construir una hipótesis a mano, y el `.inp` necesitó que un −0.7236
        # entrara como +0.7236. Un ω(B) = 0.5700 + 0.7236·B tiene coeficientes
        # que uno «sumaría» a −0.15 y una ganancia de +1.29.
        #
        # El remedio no es repetir la regla —está en tres docstrings y aun así
        # se falla— sino CALCULARLA: al lado de los coeficientes va el camino
        # del nivel, que es lo que el analista quiere decir. Sólo para las que
        # tienen más de un ω: con uno solo no hay resta que fallar.
        convenio = ""
        try:
            from art.ltf import operador_en_palabras
            _bloques = []
            for _r in results:
                if len(_r.omega) < 2:
                    continue
                _et = f"{_r.itv_type}[obs {_r.itv_at + 1}]"
                _bloques.append(f"**`{_et}`**\n\n"
                                + operador_en_palabras(
                                    list(_r.omega),
                                    entrada=getattr(_r, 'entrada', 'escalon')))
            if _bloques:
                convenio = ("\n\n---\n\n### Los ω, leídos en el nivel\n\n"
                            + "\n\n".join(_bloques) + "\n")
        except Exception as _cv:
            convenio = f"\n\n*[lectura del operador no disponible: {_cv}]*\n"

        # La salida de esta herramienta es ENTERA razones t y un Wald, así que
        # si el modelo vino de un `.pre` no hay nada aquí que se salve.
        try:
            from art.pipeline import aviso_se_no_fiable
            origen_txt = aviso_se_no_fiable(m)
        except Exception:
            origen_txt = ""
        # BUG-0157 — el contraste del EPISODIO, cuando el analista lo pide.
        neta_txt = ""
        if ganancia_neta:
            try:
                from art.interventions import net_gain
                g = net_gain(m, [int(i) for i in ganancia_neta], alpha=alpha)
                neta_txt = (
                    "\n\n---\n\n### Ganancia NETA del episodio\n\n"
                    "*El suceso repartido en varias intervenciones se juzga por "
                    "la SUMA de sus ganancias: H₀ Σᵢ ωᵢ(1) = 0. La ganancia de "
                    "cada tramo por separado es un veredicto sobre ese tramo, "
                    "no sobre el suceso.*\n\n```\n" + g.summary(alpha) + "\n```\n")
                if g.recuperado is not None and 0.10 < g.recuperado < 0.90:
                    neta_txt += (
                        f"\n**Recuperación PARCIAL.** No es «transitorio» ni "
                        f"«permanente»: el nivel devuelve el "
                        f"{g.recuperado*100:.0f} % y se queda "
                        f"{g.neta:+.4f} por debajo de la línea base. Es la "
                        f"lectura que hay que declarar, y la que el catálogo de "
                        f"formas de una sola fecha no sabe expresar.\n")
            except Exception as _ng:
                neta_txt = (f"\n\n⚠ *No se pudo contrastar la ganancia neta de "
                            f"{list(ganancia_neta)}: {_ng}*\n")

        text = (
            f"### Contraste de intervenciones — {m.series.name or 'modelo'}\n\n"
            + f"**{n_sig} significativas**, **{n_nosig} prescindibles**"
            + f" (α={alpha:.2f},  df={results[0].df})"
            + origen_txt
            + ("".join(f"\n\n⚠ **`{t}` [{i}] no se pudo contrastar:** {motivo}"
                       for i, t, motivo in fallos) if fallos else "")
            + "\n\n"
            + eq_text
            + "\n\n---\n\n" + summary
            + neta_txt
            + convenio
            + treadway
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
                nxt = ("procede a la identificación ARMA" if not has_arma
                       else "procede a contrastes formales")
                return ("\n\n---\n\n*✓ Escaneo de anómalos (latente): " + note
                        + " → " + nxt + ".*"), None

            # BUG: la versión anterior AFIRMABA "no distorsionan la ACF/PACF"
            # con distorsión «moderada», mientras `residual_outlier_scan` sobre
            # el MISMO modelo decía «puede merecer la pena intervenir · punto de
            # decisión del analista». Dos veredictos opuestos con los mismos
            # números, y el que cerraba la decisión era el que iba embutido aquí.
            #
            # Ya no se afirma nada: se CALIBRA. La pregunta «¿distorsiona?» es
            # «¿cambia algún retardo de dentro a fuera de banda, en la ACF o en
            # la PACF?», y eso se calcula.
            try:
                from art.calibracion import calibra_correlograma
                _f = int(getattr(ts, "freq", 1) or 1)
                cal = calibra_correlograma(
                    m._result.residuals, umbral=_autoscan_z,
                    freq=_f, start=getattr(ts, "start", ()),
                    desfase=_desfase_obs(m))              # BUG-0172
            except Exception:
                cal = None
            lvl = "moderada" if level == "moderate" else "leve"
            cab = (f"anómalos revisados ({n_out}): distorsión {lvl} "
                   f"(var_outlier={var_o:.1f}%, ACF_max={acf_o:.0f}%)")
            if cal is None:
                cuerpo = (cab + " — no se pudo calibrar el correlograma; "
                          "llama a `residual_outlier_scan` antes de fijar órdenes")
            elif cal.cambia_la_identificacion:
                ar = ", ".join(f"PACF({d.lag})" for d in cal.flips_ar)
                ma = ", ".join(f"ACF({d.lag})" for d in cal.flips_ma)
                que = " y ".join(x for x in (ar, ma) if x)
                cuerpo = (f"⚠ {cab} — **SÍ cambian la identificación**: al "
                          f"calibrarlos, {que} cambia(n) de veredicto dentro/"
                          "fuera de banda. Los órdenes que elegirías ahora no "
                          "son los del proceso → `residual_outlier_scan` "
                          "para verlo, e interviene ANTES de identificar")
            else:
                cuerpo = (cab + " — calibrado: **ningún retardo cambia de "
                          "veredicto** en la ACF ni en la PACF, así que no "
                          "deciden los órdenes. Intervenir aquí sería "
                          "sobre-intervenir; sigue siendo opción del analista "
                          "por adecuación o por el suceso en sí")
            # El siguiente paso depende del veredicto, no del sitio del flujo:
            # decir "interviene ANTES de identificar → procede a identificar"
            # sería la misma contradicción que este arreglo viene a quitar.
            if cal is not None and cal.cambia_la_identificacion:
                nxt = "NO fijes p y q todavía"
            else:
                nxt = ("procede a la identificación ARMA" if not has_arma
                       else "procede a contrastes formales")
            return ("\n\n---\n\n*Escaneo de anómalos (latente): " + cuerpo
                    + " → " + nxt + ".*"), None

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
                           objetivo: _Objetivo = "univariante",
                           domain: str = "") -> list:
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
    domain   : what KIND of series this is — "price_index" | "multiplicative" |
               "ratio" | "generic". Empty = inferred by `policy.decide_domain`.
               **Lo declarado gana**, que es lo que la política dice de sí misma
               y no podía cumplirse: el parámetro sólo existía en `build_model`,
               así que un analista recorriendo los nodos uno a uno no tenía
               forma de declararlo (BUG-0080). Muerde en el nodo Box-Cox
               (Call 1), que es donde el dominio decide: un índice va en log
               SIEMPRE —su base es una convención y un modelo en niveles no
               tiene escala interpretable—, y una magnitud multiplicativa o un
               cociente van en log salvo que el dato lo desmienta.
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
        # Por las puertas de art no entra un objetivo que nadie eligió: la
        # política lo convertía en «univariante» en silencio (BUG-0183).
        try:
            objetivo = objetivo_declarado(objetivo)
        except ValueError as _exc_obj:
            return _err(str(_exc_obj))
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_boxcox, describe_seasonality, describe_identification
        ts, _ = _load_ts_model(inp_path)

        # ── Call 1: Box-Cox scatter ────────────────────────────────────────
        if lam < 0:
            bc      = describe_boxcox(ts)
            rec_lam = bc.data["recommended_lambda"]

            # La regla vive en `policy`, no aquí: tenerla sólo en esta capa es lo
            # que produjo BUG-0015 —el camino autónomo partía una familia de ocho
            # IPC entre logs y niveles—. Una copia, dos caminos.
            #
            # BUG-0080, dos cosas. (a) **Lo declarado gana**, que es lo que la
            # política afirma de sí misma y no podía cumplirse: `domain=` sólo
            # existía en `build_model`. (b) La copia que había aquí implementaba
            # sólo la rama del índice, así que las otras dos categorías de
            # BUG-0040 —`multiplicative` y `ratio`, que van en log salvo que el
            # dato lo desmienta— no llegaban al carril guiado ni declarándolas.
            # Se enruta por `decide_lambda`, que las tiene todas.
            try:
                dom_decl = dominio_declarado(domain)
            except ValueError as exc:
                return _err(str(exc))
            dom = dom_decl or policy.decide_domain(ts)
            lam_pol = policy.decide_lambda(bc.data, domain=dom)
            index_note = ""
            if lam_pol != rec_lam:
                _origen = ("declarado por el analista" if dom_decl
                           else "inferido por `decide_domain`")
                _por_que = {
                    "price_index":
                        "un índice no tiene base natural —2016=100 es una "
                        "convención— así que sólo los cambios relativos "
                        "significan algo, y un modelo en niveles no tiene "
                        "escala interpretable. λ=0 **siempre**, diga lo que "
                        "diga el estadístico",
                    "multiplicative":
                        "una magnitud positiva que se mueve en proporción va "
                        "en log por defecto, y el `gap` cae dentro de la banda "
                        "en la que el estadístico no discrimina",
                    "ratio":
                        "un cociente acotado va en log por defecto, y el `gap` "
                        "cae dentro de la banda en la que el estadístico no "
                        "discrimina",
                }.get(dom, "lo decide el dominio")
                index_note = (
                    f"\n\n> ⚠ **REGLA DE DOMINIO APLICADA** — dominio "
                    f"`{dom}` ({_origen}).\n>\n"
                    f"> Se impone **λ={lam_pol:g}** sobre el "
                    f"λ={rec_lam:g} del estadístico: {_por_que}."
                )
                rec_lam = lam_pol
            elif dom_decl:
                index_note = (
                    f"\n\n> Dominio `{dom}` declarado por el analista. "
                    f"Coincide con el estadístico: **λ={rec_lam:g}**."
                )
            elif dom != "generic":
                index_note = (
                    f"\n\n> Dominio `{dom}` inferido por `decide_domain` — "
                    "coincide con el estadístico. Si no es el que corresponde, "
                    "declara `domain=` y vuelve a llamar: **lo declarado "
                    "gana**."
                )

            # La EVIDENCIA del estadístico va verbatim; su RECOMENDACIÓN, no,
            # cuando el dominio la anula: dejar «Confirma λ=1.0» encima de una
            # nota que impone λ=0 son dos instrucciones contrarias en la misma
            # pantalla, y la de arriba es la que se lee primero.
            _rec_bc = bc.recommendation
            if index_note.startswith("\n\n> ⚠"):
                _rec_bc = (f"*(La recomendación del estadístico —«{_rec_bc.strip()}»— "
                           "queda anulada por la regla de dominio: ver abajo.)*")
            # BUG-0113: la ruta se RECOGE y se dice. `_show_fig` la devuelve
            # justo para esto, y este carril no pasa por `_result()`, que es
            # donde vive la red del BUG-0078.
            _ruta_fig = _escribe_fig(bc.figure_b64, "boxcox")
            text = (
                "## Paso 1 — Transformación Box-Cox\n\n"
                + bc.summary + "\n\n---\n" + _rec_bc
                + index_note
                + f"\n\n**Próximo paso:** confirma λ y llama con `lam={rec_lam}` "
                "(o el valor que decidas) para ver la serie transformada."
                + _nota_figura(_ruta_fig)
            )
            items = [TextContent(type="text", text=text)]
            if bc.figure_b64:
                items.append(_imagen(bc.figure_b64, "guided_identification"))
            return items

        # ── Call 2: Series at d=0 + ADF/KPSS unit root table ─────────────
        if d < 0:
            from art.describe import describe_unit_root
            b64     = _plot_series_at_d(ts, lam=lam, d=0)
            lam_str = "log" if lam == 0.0 else f"λ={lam}"
            _ruta_fig = _escribe_fig(b64, "series_d0")          # BUG-0113

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
                + _nota_figura(_ruta_fig)                     # BUG-0113
            )
            items = [TextContent(type="text", text=text)]
            if b64:
                items.append(_imagen(b64, "guided_identification"))
            return items

        # ── Call 3: Series at level d, D not yet decided ──────────────────
        if D < 0:
            b64     = _plot_series_at_d(ts, lam=lam, d=d)
            lam_str = "log" if lam == 0.0 else f"λ={lam}"
            sym     = {0: "", 1: "∇", 2: "∇²"}.get(d, f"∇^{d}")
            _ruta_fig = _escribe_fig(b64, f"series_d{d}")        # BUG-0113

            sea_text = ""
            sea_fig  = None
            _ruta_sea = ""
            d_next_text = ""
            hay_estacionalidad = False
            if d > 0:
                sea     = describe_seasonality(ts)
                _ruta_sea = _escribe_fig(sea.figure_b64, "seasonality")   # BUG-0113
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
                # BUG-0113: este nodo puede traer DOS figuras; se citan las dos,
                # y en el mismo orden en que van los ImageContent de abajo.
                + _nota_figura(_ruta_fig) + _nota_figura(_ruta_sea)
            )
            items = [TextContent(type="text", text=text)]
            if b64:
                items.append(_imagen(b64, "guided_identification"))
            if sea_fig:
                items.append(_imagen(sea_fig, "guided_identification"))
            return items

        # ── Call 4: ARMA identification ───────────────────────────────────
        # B1 with clean residuals: pre_path points to fitted model after outlier cycle
        # B2 or no-outlier B1: identify directly on transformed series
        if pre_path:
            import fue as _fue
            from art.describe import _resid_start as _rs
            # BUG-0164. De este modelo sólo se toman la ESTRUCTURA, la serie y
            # los RESIDUOS; de él salen residuos, μ y los órdenes del base,
            # y ninguna razón t. Así que le toca
            # `mirar`, no `estimar` — y con `estimar` rechazando el `.pre`
            # (BUG-0159) esta puerta se quedó cerrada para el encadenado, que
            # es el modo NORMAL de usarla.
            _, m_pre = _mirar(pre_path)
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

        _ruta_fig = _escribe_fig(ident.figure_b64, "identification")   # BUG-0113
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
            + _nota_figura(_ruta_fig)                              # BUG-0113
        )
        items = [TextContent(type="text", text=text)]
        if ident.figure_b64:
            items.append(_imagen(ident.figure_b64, "guided_identification"))
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
    # TÉRMINOS, no pares: cuenta cada cos, cada sin y el alter por separado.
    # Es la cuenta de `seasonal_detection` (freq-1), no la de `n_harmonics`
    # (pares, freq//2-1). Mensual completo: 11 aquí, 5 allí (hallazgo #7).
    n_terminos_arm = sum(1 for i in itvs if i.type in ("cos", "sin", "alter"))
    if n_terminos_arm:
        piezas.append(f"{n_terminos_arm} términos armónicos")
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
    n_itv = len(itvs) - n_terminos_arm
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
            instrumento=_version_instr(),
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
        etq = ", ".join(_etiqueta_itv(t) for t in rd.added[:5])
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


def _etiqueta_itv(t) -> str:
    """Etiqueta de una intervención decidida: `(at, forma)` o `(at, forma, nω)`.

    Los `n_omega > 1` se enseñan porque son la diferencia entre un cambio de
    nivel y un EPISODIO: "STEP(3) obs 61" dice que el suceso duró dos períodos,
    y "STEP obs 61" que el nivel se desplazó. Con el par antiguo no se podía
    distinguir, y ése era el defecto.
    """
    at, forma = t[0], t[1]
    n = int(t[2]) if len(t) > 2 else 1
    marca = f"({n})" if n > 1 else ""
    return f"{forma.upper()}{marca} obs {at + 1}"


def _texto_escalera(esc, rec: str) -> str:
    """Una línea por peldaño y las razones, para la salida de la herramienta."""
    L = ["", "---", "", "**Escalera de Ockham** — peldaños estimados:", ""]
    for p in esc.peldanos:
        if not p.estimado:
            L.append(f"- `{p.nivel}` {p.nombre} — *no estimable: {p.error}*")
            continue
        marca = "**◀ elegido**" if p.nivel == rec else ""
        est = ("se sostiene" if p.se_sostiene else
               f"deja vecino ({p.treadway[0].vecino_anomalo})" if p.deja_vecino
               else "inadecuado")
        w1 = f"ω(1)={p.omega_1:+.4f}" if p.omega_1 is not None else ""
        L.append(f"- `{p.nivel}` {p.nombre} · AIC {p.aic:.2f} · {w1} · "
                 f"{est} {marca}")
    # `esc.subio` y no `rec == "2"`: el predicado tiene UNA definición, en
    # `Escalera`. Re-derivarlo aquí era tenerlo en dos sitios que pueden
    # divergir —`rec` llega como parámetro y el llamante lo calcula como
    # `esc.recomendado or esc.nivel_simple or "1a"`— y es la misma familia que
    # los cuatro `umbral_vecino` de BUG-0087.
    if esc.razones_para_subir and esc.subio:
        L += ["", "Se subió de peldaño por:"]
        L += [f"  - {r}" for r in esc.razones_para_subir]
    elif esc.ningun_peldano_se_sostiene:
        # BUG-0084 §4. Decía «Se subió de peldaño por: …» marcando como elegido
        # `1a`, que es el más bajo. O el mensaje describía una evaluación que no
        # se aplicó, o la elección no era la que decía, y el analista no podía
        # saber cuál de las dos. Lo que pasa de verdad es esto:
        L += ["", f"**Había razones para subir y aun así se recomienda "
              f"`{rec}`, el peldaño bajo:**"]
        L += [f"  - {r}" for r in esc.razones_para_subir]
        L += ["", "El peldaño 2 tampoco se sostiene, así que **ninguna forma de "
              "esta escalera resuelve el suceso**. Lo recomendado es el menos "
              "malo. Antes de fijarlo, mira si el episodio está bien delimitado "
              "(`incident_configurations`) o si lo que queda no es un suceso "
              "sino estructura sin modelizar."
              " Y hay una **tercera** lectura, que el catálogo de formas de "
              "una sola fecha no "
              "sabe nombrar: un suceso con **vuelta DIFERIDA** —la caída y la "
              "recuperación separadas por períodos tranquilos— no cabe en "
              "ninguna de estas formas, porque `1b` obliga a que el nivel vuelva "
              "en T+1. Si el vecino queda a los DOS lados, es la lectura "
              "que toca: dos intervenciones, y el contraste de su ganancia "
              "**NETA** (`test_interventions(..., ganancia_neta=[i, j])`, "
              "BUG-0157)."]
    else:
        L += ["", "**No hubo razón para subir**: la lectura simple absorbe su "
              "fecha, no deja vecino y el modelo es adecuado. El AIC no arbitra "
              "la subida — subir aquí sería añadir parámetros a un problema "
              "resuelto."]
    L += ["", "❓ " + esc.pregunta_extramuestral]
    return "\n".join(L)


def _alternativas_escalera(esc, rec: str) -> str:
    """Los peldaños DESCARTADOS con su razón, para el `alternativas` del guion.

    Es lo que convierte un nodo en un argumento en vez de una etiqueta: sin
    esto el guion dice qué se eligió y no qué se descartó ni por qué, que es
    justo lo que hace falta para no volver a intentarlo.
    """
    partes = []
    for p in esc.peldanos:
        if p.nivel == rec:
            continue
        if not p.estimado:
            partes.append(f"{p.nivel} ({p.nombre}): no estimable")
            continue
        pega = (f"deja vecino {p.treadway[0].vecino_anomalo}" if p.deja_vecino
                else "no deja ruido blanco" if not p.adecuado
                else "se sostiene, pero no había razón para subir a él")
        partes.append(f"{p.nivel} ({p.nombre}): AIC {p.aic:.2f}, {pega}")
    return " · ".join(partes)


def _exige_la_misma_serie(ts_a, ts_b, ruta_a: str, ruta_b: str) -> None:
    """El `.pre` que se encadena tiene que ser de ESTA serie.

    El guardián comparaba `nobs` y `freq`, que es comparar la FORMA y no el
    CONTENIDO. Dos series mensuales de la misma longitud pasaban — y en el
    propio TFM hay tres. Medido con dos series sintéticas de 120 datos
    mensuales: el guardián las daba por buenas con `max|A−B| = 152,3`.

    Lo que ocurre después no avisa. `_build_arma_on_model` se queda con los
    deterministas del `.pre` —los armónicos, la media, las intervenciones, con
    sus fechas— y `_write_inp` escribe los datos del `.inp`: un modelo cuya
    parte determinista es de otra serie, estimado sobre ésta, y registrado en el
    guion como si fuera el paso siguiente del recorrido de ésta.

    El margen para distinguirlas es amplio y no hay que afinarlo: el encadenado
    legítimo reproduce la serie a 5·10⁻⁷ —la precisión con la que el `.inp` la
    escribe, no ruido— y el ilegítimo estaba a 152. Se compara en RELATIVO
    porque la tolerancia tiene que valer igual para una serie en unidades y para
    otra en millones.

    También se compara `start`: dos series de igual longitud y frecuencia que
    empiezan en fechas distintas están desalineadas, y las fechas de las
    intervenciones del `.pre` —que son índices— apuntarían a otro mes.
    """
    import numpy as _np
    if ts_a.nobs != ts_b.nobs or ts_a.freq != ts_b.freq:
        raise ValueError(
            f"Series mismatch between inp_path and base_pre_path: "
            f"nobs {ts_a.nobs} vs {ts_b.nobs}, freq {ts_a.freq} vs {ts_b.freq}"
        )
    if tuple(ts_a.start or ()) != tuple(ts_b.start or ()):
        raise ValueError(
            f"El `.pre` empieza en {ts_b.start} y la serie en {ts_a.start}: "
            f"están desalineadas, y las fechas de las intervenciones del `.pre` "
            f"apuntarían a otro periodo.\n  serie : {ruta_a}\n  .pre  : {ruta_b}"
        )
    a = _np.asarray(getattr(ts_a, "data", []), float)
    b = _np.asarray(getattr(ts_b, "data", []), float)
    if a.size == 0 or b.size == 0 or a.size != b.size:
        return                      # sin datos que comparar, no se inventa nada
    escala = max(float(_np.max(_np.abs(a))), 1e-12)
    dif = _np.abs(a - b) / escala
    if float(_np.max(dif)) > 1e-5:
        i = int(_np.argmax(dif))
        raise ValueError(
            f"El `.pre` NO es de esta serie: difieren desde el dato {i} "
            f"({a[i]:.6g} frente a {b[i]:.6g}; discrepancia relativa máxima "
            f"{float(_np.max(dif)):.3g}, y el encadenado legítimo queda por "
            f"debajo de 1e-5).\n  serie : {ruta_a}\n  .pre  : {ruta_b}\n"
            f"Encadenar el `.pre` de otra serie da un modelo con los "
            f"deterministas de aquélla —armónicos, media, intervenciones y sus "
            f"fechas— estimado sobre ésta."
        )


def _version_instr() -> str:
    """La versión del instrumento, para que el guion se pueda releer."""
    try:
        from art.guion import version_instrumento
        return version_instrumento()
    except Exception:
        return ""


def _record_node_to_guion(guion_path: str, nodo: str, decidido: str,
                          razon: str, evidencia: str = "",
                          alternativas: str = "",
                          decidido_por: str = "analista+LLM") -> str:
    """Escribe un NODO de decisión en el guion. Versión interna de `guion_node`.

    Existe para que una herramienta que TOMA una decisión pueda dejarla escrita
    sin obligar al operador a llamar aparte — y sobre todo para que
    `alternativas` venga rellena de verdad, con lo que se estimó y descartó, en
    vez de quedarse vacía porque nadie se acordó.
    """
    from art.guion import (Guion, GuionEntry, load_guion, save_guion,
                           infer_parent)
    from datetime import datetime
    gp = os.path.expanduser(guion_path)
    os.makedirs(os.path.dirname(gp) or ".", exist_ok=True)
    if os.path.exists(gp):
        g = load_guion(gp)
    else:
        serie = os.path.basename(gp).replace("_guion.json", "").replace("guion.json", "")
        g = Guion(series=serie or "serie", analyst="",
                  created=datetime.now().strftime("%Y-%m-%d"))
    version = (max(e.version for e in g.entries) + 1) if g.entries else 1
    g.entries.append(GuionEntry(
        version=version, name=nodo, inp_path="",
        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        spec={}, stats=None, equation="",
        decision=f"{nodo} = {decidido}", rationale=razon,
        problems_found="", next_version="",
        parent=infer_parent(g), kind="node",
        instrumento=_version_instr(),
        node={"nodo": nodo, "decidido": decidido, "evidencia": evidencia,
              "alternativas": alternativas},
        decided_by=decidido_por,
    ))
    save_guion(g, gp)
    return f"◆ nodo n{version} — **{nodo} = {decidido}**"


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
    hist_b64: str | None = None,
    base_pre_path: str = "",
    dominio: str = "",
) -> str:
    """
    Add a fitted model entry to guion.json (creates file if absent).
    Returns a one-line confirmation string for the caller.
    """
    from datetime import datetime
    from art.guion import (
        Guion, GuionEntry, load_guion, save_guion, infer_parent,
        _extract_spec, _extract_stats, _build_equation,
        sha_del_fichero, pre_hermano, pre_de_la_base,
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
    # La huella del `.pre` semilla, LEÍDA AHORA: es lo que convierte el linaje
    # en algo contrastable en vez de una ruta que cualquiera puede reescribir
    # (BUG-0175). Se toma antes de inferir el padre porque es lo que decide
    # cuál de los homónimos lo es.
    # …y la del `.pre` de esa base aunque llegue un `.inp`: se compara con el
    # `pre_sha` que registró el padre, y con otro fichero no cuadra nunca
    # (BUG-0184).
    base_pre_sha = (sha_del_fichero(pre_de_la_base(base_pre_path))
                    if base_pre_path else "")
    pre_sha = sha_del_fichero(pre_hermano(inp_path))
    parent = infer_parent(guion, base_pre_path, base_pre_sha)
    # Y CÓMO se supo. Sin `base_pre_path` el padre es «la última entrada», que
    # es una conjetura razonable y a veces falsa (BUG-0108).
    parent_origen = "declarado" if base_pre_path else "inferido"

    # ¿ES ESTO UN MODELO NUEVO O EL MISMO OTRA VEZ? — BUG-0176.
    # Mismo `.pre` byte a byte es el mismo modelo. Reinscribirlo —para ponerle
    # nombre, para colgarle el veredicto— es legítimo; colgarlo de la última
    # entrada, no: así el árbol dibujó en el run 4 que el modelo adoptado
    # descendía de la sobreparametrización que lo rechazó, y que el FINAL
    # descendía del descartado. Una copia hereda el padre del original.
    re_registro_de = None
    if pre_sha and not base_pre_path:
        for e in guion.entries:
            if e.pre_sha and e.pre_sha == pre_sha:
                re_registro_de = e.version
                parent = e.parent
                parent_origen = "re-registro"
                break

    diag_result = diagnose(model)
    spec  = _extract_spec(model, lam)
    # El dominio es un dato del ANALISTA, no del modelo: no se puede recuperar
    # releyendo el `.inp`. Si no queda aquí, la razón por la que λ vale lo que
    # vale se pierde (BUG-0080).
    if dominio:
        spec["dominio"] = dominio
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
        # De dónde salió: el `.pre` que se usó como semilla. Es el dato con el
        # que se dedujo `parent`, y hasta ahora se consumía y se tiraba.
        base_pre_path=base_pre_path or "",
        # De dónde salió Y con qué contenido; y qué `.pre` deja esta versión
        # para que sus hijos puedan demostrar que vienen de ELLA (BUG-0175).
        base_pre_sha=base_pre_sha,
        pre_sha=pre_sha,
        re_registro_de=re_registro_de,
        parent_origen=parent_origen,
        instrumento=_version_instr(),
    )
    # BUG-0043: la figura va a un fichero hermano, no dentro del guion.
    # Y son DOS: la diagnosis de esta escuela son residuos + ACF/PACF +
    # histograma, y el Jarque-Bera se lee sobre el tercero. `describe_diagnosis`
    # los genera los dos y sólo se guardaba el primero.
    def _guarda_fig(b64, sufijo=""):
        # EL NOMBRE LLEVA LA HUELLA DE LA IMAGEN, y no es cosmético.
        #
        # La misma figura se escribe DOS veces: aquí, como hermana del guion —el
        # registro, que viaja con él— y en `ART_FIG_DIR` vía `_show_fig`, que es
        # la ruta que se cita cuando el visor no abre (BUG-0078). Las dos copias
        # tienen razón de ser y ninguna sobra.
        #
        # Lo que faltaba es que se supieran la misma: mismo SHA-256 y nombres
        # que no se parecían en nada, lo que indujo a enviar la figura dos veces
        # a la conversación creyéndolas distintas (BUG-0119). `_show_fig` ya
        # nombra la suya `art_<etq>_<huella>.png`; poniendo la misma huella aquí,
        # los dos nombres comparten un token visible y se reconocen a simple
        # vista sin tener que compararlas.
        import base64 as _b64
        figs = os.path.join(os.path.dirname(guion_path) or ".", "figs")
        os.makedirs(figs, exist_ok=True)
        nombre = (f"{guion.series or 'serie'}_v{entry.version}{sufijo}"
                  f"__{_huella_figura(b64)}.png")
        with open(os.path.join(figs, nombre), "wb") as fh:
            fh.write(_b64.b64decode(b64))
        return os.path.join("figs", nombre)

    if entry.figure_b64:
        try:
            entry.figure_path = _guarda_fig(entry.figure_b64)
            entry.figure_b64 = None
        except Exception as e:
            _warn("no se pudo escribir la figura del guion; se deja empotrada", e)
    if hist_b64:
        try:
            entry.hist_path = _guarda_fig(hist_b64, "_hist")
        except Exception as e:
            _warn("no se pudo escribir el histograma del guion", e)

    # BUG-0092. El guion es el mapa por el que se vuelve atrás, y una entrada
    # que apunta a un fichero ausente rompe justo esa operación. Medido sobre el
    # corpus real: 4 de 15 entradas apuntaban al vacío, y el guion no lo decía.
    #
    # No bloquea —registrar mal es mejor que no registrar— pero lo dice, y dice
    # qué falta de la terna: un `.pre` o un `.out` que faltan se rehacen
    # estimando; un `.inp` que falta deja el nodo irrecuperable.
    aviso_terna = ""
    try:
        _b = os.path.splitext(entry.inp_path or "")[0]
        if _b:
            _falta = [ext for ext in (".inp", ".pre", ".out")
                      if not os.path.exists(_b + ext)]
            # Una RONDA intermedia del carril autónomo registra su `.pre` a
            # propósito: no es una versión con especificación propia, es un
            # paso del ciclo. Exigirle un `.inp` sería pedirle lo que no tiene.
            if (entry.inp_path or "").lower().endswith(".pre"):
                _falta = [x for x in _falta if x != ".inp"]
            # El `.out` se REGISTRA, no se deriva: derivarlo es suponer que está.
            # Y es la única constancia fiel de las SE, así que su ausencia
            # cambia lo que se puede hacer desde este nodo (BUG-0090/0091).
            if ".out" not in _falta:
                entry.out_path = _b + ".out"
            if ".inp" in _falta:
                aviso_terna = (f"  ⚠ **el `.inp` registrado no existe** "
                               f"(`{os.path.basename(entry.inp_path)}`): desde "
                               f"este nodo no se puede reestimar")
            elif _falta:
                aviso_terna = (f"  *(sin {', '.join(_falta)}; se rehacen "
                               f"estimando el `.inp`)*")
    except Exception as _te:
        _warn("comprobación de la terna al registrar en el guion", _te)

    guion.entries.append(entry)
    save_guion(guion, guion_path)
    # Una línea, y corta: el registro es interno y la salida no debe crecer por
    # documentar. Quien quiera ver lo documentado llama a `export_guion`.
    padre = f" ← v{parent}" if parent is not None else ""
    return f"*guion: {name} v{version}{padre}*" + aviso_terna


# ---------------------------------------------------------------------------
# Tool: confirm and estimate (B2)
# ---------------------------------------------------------------------------

def _orden_ar(p):
    """Normaliza el orden AR. Acepta 3, "3", [1,1,2] o "[1,1,2]".

    BUG-0112. `p` estaba SIN anotar —porque admite un entero o una lista de
    órdenes por factor, y no hay una anotación obvia para las dos—, y sin
    anotación FastMCP publicaba `"type": "string"`. Un cliente conforme al
    esquema mandaba entonces una cadena, y `pipeline._arma_starts` la comparaba
    con un entero: `TypeError: '>' not supported between 'str' and 'int'`.

    O sea que **no se podía fijar ningún orden AR desde el servidor** — ni
    `p=1`, ni la forma factorizada `[1,1,2,2]` que expuso BUG-0103—, que es el
    nodo central del carril guiado. La anotación por sí sola arregla el
    esquema; esta función arregla además el caso del cliente laxo, y es lo que
    el docstring de la herramienta ya prometía al documentar las dos formas.
    """
    import json as _json
    if isinstance(p, str):
        p = p.strip()
        if not p:
            return 0
        p = _json.loads(p) if p.startswith("[") else int(p)
    if isinstance(p, (list, tuple)):
        return [int(x) for x in p]
    return int(p)


@mcp.tool()
def confirm_and_estimate(inp_path: str, output_path: str,
                          lam: float = 0.0, d: int = 1, D: int = 0,
                          p: int | list[int] = 0, q: int = 1,
                          ar_seeds: list | None = None,
                          ar_f_freqs: list | None = None,
                          n_harmonics: int = 5,
                          P: int = 0, Q: int = 0,
                          base_pre_path: str = "",
                          estimate_mu: bool = False,
                          seasonal: bool | None = None,
                          easter: bool = False,
                          include_histogram: bool = False,
                          domain: str = "",
                          guion_path: str = "",
                          guion_name: str = "",
                          guion_decision: str = "",
                          guion_rationale: str = "",
                          guion_problems: str = "",
                          guion_next: str = "",
                          modo: _Modo = "guiado") -> list:
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
    p               : regular AR order — an INT or a LIST OF ORDERS PER FACTOR.
                      `fue` estimates the regular AR as a PRODUCT of factors, and
                      that is how this school reads an operator: each factor has
                      its own damping and period.

                          6          one operator of order 6
                          [1,1,2,2]  four factors — the FACTORISED model

                      The factorised form is an EXACTLY IDENTIFIED
                      reparametrisation of the same model: same likelihood, same
                      degrees of freedom. Its point is not a better fit — it is
                      that each factor gets its `d ± SE` and `period ± SE`,
                      without which you cannot test whether a factor admits the
                      seasonal frequency.

                      **Never replace an AR(p) by a capped or sparse operator on
                      the strength of similar moduli.** That IMPOSES p−1
                      untested restrictions and forecloses Shin-Fuller. Estimate
                      the full operator, factorise it, then test.
    ar_seeds        : starting values per factor, e.g. [[0.78],[-0.77],[.9,-.6]].
                      `ar_factorization` computes them; pass them when splitting
                      an estimated operator into factors so the fit starts at the
                      optimum it already found. Ignored unless `p` is a list of
                      matching length.
    ar_f_freqs      : frequencies k of FIXED-FREQUENCY AR(2) factors, e.g. [4,2]
                      for s=12. Each is (1 − φ₁B − φ₂B²) with the frequency
                      NAILED to 2πk/s: only φ₂ is estimated and φ₁ is derived.
                      This is the CONTRASTABLE version of «this factor is
                      seasonal» — nested in the free factor, so a likelihood
                      ratio with 1 d.f. decides it. Without it the only way to
                      claim a factor is seasonal was to impose it.
    q               : regular MA order
    n_harmonics     : harmonic pairs cos/sin (D=0 fresh only; ignored when
                      base_pre_path is given — harmonics come from the .pre)
    easter          : add the EASTER (Semana Santa) calendar regressor. MONTHLY
                      series only — the engine builds it itself: 1.0 in the month
                      of Easter Sunday, split 0.5 March + 0.5 April when Good
                      Friday falls in March. It is a deterministic term like the
                      harmonics, NOT an intervention: it has no date and no form,
                      so it does not go through the intervention node. Add it when
                      the residuals show recurring April/March anomalies that move
                      with the calendar.
                      **Funciona TAMBIÉN con `base_pre_path`** (BUG-0170): se
                      AÑADE sobre los deterministas heredados del `.pre`, y si el
                      `.pre` ya lo trae se hereda sin duplicarse. Antes se
                      aceptaba el argumento y se descartaba en silencio, con lo
                      que no quedaba NINGUNA vía para añadirlo a un modelo ya
                      construido sin volver al `.inp` fresco y perder todas las
                      intervenciones. `n_harmonics` sigue viniendo del `.pre`.
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
    domain          : what KIND of series this is — "price_index" |
                      "multiplicative" | "ratio" | "generic". Se REGISTRA en el
                      guion (no se puede recuperar releyendo el `.inp`: es un
                      dato del analista) y se CONTRASTA con la λ que se pasa.
                      Declarar `price_index` con λ=1 es una contradicción y la
                      herramienta la dice — es exactamente el fallo que motivó
                      BUG-0080: art recomendó «identidad (λ=1)» sobre un índice
                      de precios y el carril guiado no ofrecía la corrección.
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
    modo            : "guiado" (por defecto) | "autonomo". En GUIADO quien
                      confirma la especificación es el analista humano y la
                      salida termina en ⏸ para que decida él. En AUTÓNOMO quien
                      la confirma eres tú —el LLM hace de analista—: no hay a
                      quién esperar y la salida NO para. Pásalo en cada llamada
                      del carril autónomo (BUG-0180, BUG-0181).
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        import fue

        # BUG-0112. La anotación arregla el esquema publicado; esto arregla lo
        # que llegue de un cliente que no lo respete. Va lo primero: a partir
        # de aquí `p` es un int o una list[int] y nadie aguas abajo tiene que
        # preguntárselo.
        try:
            p = _orden_ar(p)
        except (TypeError, ValueError):
            return _err(f"orden AR no valido: {p!r}. Se espera un entero "
                        f"(p=2) o una lista de ordenes por factor (p=[1,1,2]).")

        ts, _ = _load_ts_model(inp_path)
        output_path = os.path.expanduser(output_path)

        if base_pre_path:
            # Incremental: preserve interventions + harmonics from .pre; replace ARMA
            base_pre_path = os.path.expanduser(base_pre_path)
            _, m_base = _load_ts_model(base_pre_path)
            ts_b = m_base.series
            _exige_la_misma_serie(ts, ts_b, inp_path, base_pre_path)
            # BUG-0170: `easter` llega hasta aquí. Antes se aceptaba el
            # argumento y se descartaba en silencio al encadenar.
            m = _build_arma_on_model(m_base, p=p, q=q, P=P, Q=Q,
                                     estimate_mu=estimate_mu, easter=easter)
            _write_inp(ts, m, output_path)
        else:
            m_fresh = _make_model(ts, lam=lam, d=d, D=D, p=p, q=q,
                                  n_harmonics=n_harmonics, P=P, Q=Q,
                                  estimate_mu=estimate_mu, seasonal=seasonal,
                                  easter=easter, ar_seeds=ar_seeds,
                                  ar_f_freqs=ar_f_freqs)
            _write_inp(ts, m_fresh, output_path)

        _, m = _load_fitted(output_path)

        # LA λ QUE VALE ES LA DEL MODELO, no la del argumento (revisión externa,
        # hallazgo #1). Con `base_pre_path` —el camino que las propias
        # instrucciones mandan usar por defecto— `lam` se IGNORA para construir
        # el modelo, porque la transformación viene del `.pre`. Y se seguía
        # mostrando y registrando desde el argumento, cuyo defecto es 0.0.
        #
        # Resultado medido: un modelo en NIVELES encadenado desde su `.pre`
        # quedaba en el guion como λ=0 y su ecuación se imprimía como ∇[ln y].
        # Un registro falso, en el camino recomendado.
        #
        # Los otros cinco llamantes de `_record_to_guion` ya leían del modelo;
        # éste era el único discrepante — y es la puerta principal del carril
        # guiado.
        lam = float(getattr(m, "boxlam", lam) if getattr(m, "boxlam", None)
                    is not None else lam)

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
        # BUG-0080. El dominio y la λ tienen que contarse la misma historia. Un
        # índice va en log SIEMPRE —su base es una convención—, así que
        # `domain="price_index"` con λ=1 no es una preferencia: es una
        # contradicción, y es literalmente el caso que abrió el bug (art
        # recomendó «identidad» sobre el HICP de alimentos de la UEM y el carril
        # guiado no ofrecía dónde corregirlo). No se bloquea —el analista manda—
        # pero se dice.
        aviso_dom = ""
        try:
            _dd = dominio_declarado(domain)
        except ValueError as exc:
            return _err(str(exc))
        if _dd:
            if _dd == "price_index" and lam != 0.0:
                aviso_dom = (
                    f"\n\n> ⚠ **Dominio `{_dd}` con λ={lam:g}.** Un índice no "
                    "tiene base natural —2016=100 es una convención— así que "
                    "sólo los cambios relativos significan algo: un modelo en "
                    "NIVELES de un índice no tiene escala interpretable, y "
                    "contra una entrada en log da una semielasticidad donde los "
                    "demás dan una elasticidad. La regla índice dice **λ=0 "
                    "siempre**. Se estima lo que has pedido, pero mira esto "
                    "antes de seguir (BUG-0015, BUG-0080).")
            elif _dd in ("multiplicative", "ratio") and lam != 0.0:
                aviso_dom = (
                    f"\n\n> Dominio `{_dd}` con λ={lam:g}. El log es el punto "
                    "de partida para una magnitud que se mueve en proporción, "
                    "pero **aquí el dato sí puede desmentirlo**: si el `gap` "
                    "salió fuera de la banda ambigua, λ=1 está justificado. "
                    "Queda anotado en el guion.")
        spec_line = f"**{spec_str}  λ={lam}**  —  {ts.name or 'series'}"
        if _dd:
            spec_line += f"  ·  dominio `{_dd}`"

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
                hist_b64=(diag.data or {}).get("hist_b64"),
                base_pre_path=base_pre_path,
                dominio=(domain or "").strip(),
            )
        except Exception as e:
            # Documentar no puede tumbar una estimación válida.
            guion_note = f"*guion: no registrado ({type(e).__name__})*"

        scan_section, scan_b64 = _auto_scan_section(
            ts, m, lam=lam, d=d, D=D, p=p, q=q, P=P, Q=Q,
            inp_path=inp_path, pre_path=pre_path,
        )

        text = (
            envuelve_iteracion(
                nombre=os.path.splitext(os.path.basename(output_path))[0],
                # Se llama cuando el analista ha confirmado la especificación.
                # Sin modo declarado el sobre le daba la forma del REGISTRO y el
                # guiado se comportaba como un autónomo que además narra
                # (BUG-0094); de ahí que se fijase «guiado».
                #
                # Pero fijarlo daba por hecho que QUIEN CONFIRMA ES SIEMPRE UN
                # HUMANO. En el carril autónomo confirma el LLM, con esta misma
                # herramienta —así lo hicieron las 31 series del estudio de
                # 0.1.x—, y desde 06-sep cada llamada le mandaba parar a
                # esperar a nadie (BUG-0181). El carril lo declara quien llama;
                # por defecto sigue siendo guiado, que es el lado seguro.
                modo=_modo_del_sobre(modo),
                conclusiones=_conclusiones_desde(diag),
                alternativas=_alternativas_desde(
                    diag, model=m, ts=ts, inp_path=output_path,
                    guion_path=guion_path or _derive_guion_path(output_path, m)),
                especificacion=(
                    spec_line + aviso_dom
                    + (f"\n\n*Encadenado desde "
                       f"`{os.path.basename(base_pre_path)}`: se conservan sus "
                       f"intervenciones y armónicos, y se sustituye el ARMA.*"
                       if base_pre_path else "")
                    # Encadenar desde un `.pre` hereda sus intervenciones, y
                    # una rampa heredada sigue fijando la previsión (BUG-0182).
                    + aviso_rampa(m)),
                ecuacion=eq_text,
                # La diagnosis de esta escuela son los métodos formales Y los
                # informales: el veredicto de Q y JB, y el escaneo de anómalos
                # que se mira en el gráfico.
                diagnosis=(diag.summary + "\n\n---\n" + diag.recommendation
                           + scan_section),
                # La 4ª etapa sale de lo que la propia diagnosis pide. Si no
                # pide nada, `envuelve_iteracion` lo dice explícitamente.
                reformulacion=_reformulacion_desde(diag, guion_next),
                extra=pre_note
                      + (f"\n\n{guion_note}" if guion_note else "")
                      + _state_footer(
                          m, inp_path=output_path, guion_note=guion_note,
                          guion_path_hint=guion_path
                          or _derive_guion_path(output_path, m)),
            )
        )

        # BUG-0113: mismo caso que el carril guiado — este sobre se compone a
        # mano (BUG-0094) y no pasa por `_result()`, asi que la ruta hay que
        # recogerla y decirla aqui.
        _ruta_fig = _escribe_fig(diag.figure_b64, "diagnosis")
        text = _con_nota_figura(text, _ruta_fig)
        items = [TextContent(type="text", text=text)]
        if diag.figure_b64:
            items.append(_imagen(diag.figure_b64, "confirm_and_estimate"))
        if scan_b64:
            items.append(_imagen(scan_b64, "confirm_and_estimate"))
        if include_histogram:
            hist_b64 = diag.data.get("hist_b64")
            if hist_b64:
                items.append(_imagen(hist_b64, "confirm_and_estimate"))
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
                   next_version: str = "",
                   base_pre_path: str = "") -> list:
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
    base_pre_path  : el `.pre` del que SALE este modelo, si se encadenó de uno.
                     Sin esto el padre es «la última entrada registrada», que es
                     una conjetura y en el run 4 fue falsa tres veces: declara
                     de dónde viene y el árbol lo dibuja bien (BUG-0176).
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import _fig_b64
        from art.diagnosis import diagnose, plot_diagnosis
        import matplotlib.pyplot as plt

        _, m = _mirar(inp_path)

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
            figure_b64=b64, base_pre_path=base_pre_path,
        )

        # `record_version` CIERRA una iteración —escribe la entrada del guion—
        # y emitía en su propia forma. Con el sobre, lo que el analista ve al
        # registrar tiene la misma forma que lo que vio al estimar.
        cifras = [
            f"**loglik** = {m._result.loglik:.3f}",
            f"**AIC** = {m._result.aic:.2f}" if m._result.aic else "",
            f"**Q-pass** = {diag_result.white_noise} | **JB-pass** = {diag_result.normal}",
            f"**Anomalías** = {len(diag_result.extreme)}",
        ]
        # La ecuación ESTRUCTURAL, la del guion, no la del prompt. `record_version`
        # MIRA —abre con `_mirar`, que acepta un `.pre`— y la ecuación del prompt
        # imprime cada coeficiente con su error típico debajo. Desde un `.pre`
        # esos errores no son fiables (BUG-0090/0091: la covarianza es un
        # subproducto del camino del optimizador, no del óptimo), así que
        # imprimirlos aquí sería contradecir el contrato que esta herramienta
        # respeta. La estructural dice la FORMA sin inventar precisión.
        try:
            from art.guion import _build_equation, _extract_spec
            eq_rv = _build_equation(_extract_spec(m, lam), m.series.freq)
        except Exception as _e:
            eq_rv = f"⚠ *[equation error: {_e}]*"
        texto = envuelve_iteracion(
            nombre=name or os.path.splitext(os.path.basename(inp_path))[0],
            especificacion=(f"Registro de `{os.path.basename(inp_path)}` tal como "
                            f"está: esta vía no construye especificación, la "
                            f"deja constancia."),
            ecuacion=eq_rv,
            diagnosis="\n".join(l for l in cifras if l),
            reformulacion=(next_version or
                           "No consta: `next_version` vacío al registrar."),
            extra=f"### Versión registrada en guion\n\n{note}",
        )
        items = [TextContent(type="text", text=texto)]
        if b64:
            items.append(_imagen(b64, "record_version"))
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
        from art.guion import (load_guion, path_to_root, safe_ancestor,
                               descendants, iteraciones, modelos_sin_registrar,
                               entradas_que_no_cuadran, linaje_dudoso,
                               comparaciones_entre_muestras,
                               cifra as _cifra)
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
                # Una reinscripción no es un paso más del método: es el mismo
                # modelo otra vez, con otro nombre o con el veredicto encima
                # (BUG-0176). Dibujarla sin decirlo infla el recorrido.
                rr = (f"  ↻ re-registro de v{e.re_registro_de}"
                      if getattr(e, "re_registro_de", None) else "")
                nn = (f"  n={e.stats.nobs}" if getattr(e.stats, "nobs", None) else "")
                lines.append(f"{sangria}{rama}{st} v{e.version} {e.name}  "
                             f"logL={_cifra(e.stats.loglik)}{nn}  {q} {jb}{rr}"
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

        # LA CUENTA DE ITERACIONES. Un modelo estimado cierra una iteración; los
        # nodos que lo preceden son su etapa 1. Sin esto, «¿cuántas iteraciones
        # tuvo este análisis?» tenía tres respuestas defendibles sobre el mismo
        # corpus y el código no elegía ninguna.
        its = iteraciones(g)
        cerradas = [i for i in its if i.cerrada]
        por_nodo: dict[str, int] = {}
        for i in cerradas:
            por_nodo[i.nodo or "—"] = por_nodo.get(i.nodo or "—", 0) + 1
        detalle_nodos = " · ".join(f"{k}: {v}" for k, v in por_nodo.items())
        lines += ["", f"**{len(cerradas)} iteraciones**"
                      + (f" — {detalle_nodos}" if detalle_nodos else "")]
        abiertas = [i for i in its if not i.cerrada]
        if abiertas:
            lines.append(f"   {len(abiertas)} especificada(s) sin estimar.")

        # ¿ESTÁ COMPLETO EL REGISTRO? El guion no tenía forma de saberse
        # incompleto, y se sabe incompleto: en UEM_FOOD_SERV_DS —un caso que
        # salió bien— hay 13 modelos con terna completa en disco y 9 en el
        # guion, y el que falta al final es el modelo FINAL (AIC −44,77 frente
        # al −41,13 del último registrado). Esto no lo impide; lo hace visible.
        try:
            sueltos = modelos_sin_registrar(g, os.path.expanduser(guion_path))
            if sueltos:
                lines += ["", f"⚠ **{len(sueltos)} modelo(s) estimado(s) en la "
                              f"carpeta y NO en el registro.** Tienen `.inp` y "
                              f"`.out`, así que se estimaron; el guion no los "
                              f"tiene, así que el recorrido que cuenta está "
                              f"incompleto:"]
                for r in sueltos[:12]:
                    lines.append(f"   · {os.path.basename(r)}")
                if len(sueltos) > 12:
                    lines.append(f"   · … y {len(sueltos) - 12} más")
                lines.append("   Regístralos con `record_version` si forman "
                             "parte del recorrido.")
        except Exception as e:
            _warn("no se pudo reconciliar el guion con su carpeta", e)

        # ¿DICE EL REGISTRO LO QUE DICE SU FICHERO? El guion es el registro y el
        # `.inp` es la evidencia; que discrepen no es un descuadre de formato,
        # es que lo que se lee en el mapa no es lo que se estimó.
        try:
            descuadres = entradas_que_no_cuadran(g)
            if descuadres:
                lines += ["", "⚠ **El registro CONTRADICE a su fichero** en "
                              f"{len(descuadres)} entrada(s). Lo que ves aquí "
                              "no es lo que se estimó:"]
                for v, nom, en_f, en_r in descuadres:
                    lines.append(f"   · v{v} {nom}: el `.inp` lleva {en_f} "
                                 f"intervención(es) y el guion registra {en_r}")
                lines.append("   Reléelo con `get_out_report` y vuelve a "
                             "registrarlo con `record_version` (BUG-0102).")
        except Exception as e:
            _warn("no se pudo comprobar el registro contra sus ficheros", e)

        # ¿SE SOSTIENE EL ÁRBOL QUE ACABA DE DIBUJARSE? Un enlace padre→hijo se
        # guardaba como la RUTA del `.pre` semilla, y una ruta no identifica un
        # contenido: reescrito ese fichero, el hijo seguía declarando un linaje
        # que ya no era cierto y el mapa lo dibujaba igual (BUG-0175). El mapa
        # ES el árbol; si sus enlaces no se contrastan, hay que decirlo AQUÍ.
        try:
            dudosos = linaje_dudoso(g)
            graves = [(v, m) for v, m in dudosos if m != "sin contrastar"]
            if graves:
                lines += ["", "⚠ **El árbol dibuja enlaces que no se sostienen** "
                              f"({len(graves)}). El `.pre` del que dice venir "
                              "una versión no es el que hay:"]
                for v, motivo in graves[:12]:
                    lines.append(f"   · v{v}: {motivo}")
                if len(graves) > 12:
                    lines.append(f"   · … y {len(graves) - 12} más")
                lines.append("   Un `.pre` reescrito deja de ser el que se "
                             "encadenó. Comprueba de qué modelo desciende de "
                             "verdad antes de seguir desde ahí (BUG-0175).")
            sin = [v for v, m in dudosos if m == "sin contrastar"]
            if sin:
                lines += ["", f"· {len(sin)} enlace(s) sin huella: el guion es "
                              "anterior a que se registrara, así que su linaje "
                              "no está comprobado — ni desmentido."]
        except Exception as e:
            _warn("no se pudo contrastar el linaje del guion", e)

        # ¿SE PUEDEN COMPARAR LAS CIFRAS QUE ACABAN DE DIBUJARSE? ℓ, AIC y BIC
        # son sumas sobre las observaciones. Entre muestras distintas no miden
        # lo mismo, y el mapa las pone una debajo de otra —que es una invitación
        # a leerlas como una mejora (BUG-0177).
        try:
            entre = comparaciones_entre_muestras(g)
            if entre:
                lines += ["", "⚠ **Hay saltos de MUESTRA en el árbol** "
                              f"({len(entre)}). Donde la n cambia, `logL`, AIC y "
                              "BIC dejan de ser comparables con el padre — la "
                              "diferencia no es ajuste, es tamaño:"]
                for hijo, nh, padre, npd in entre[:12]:
                    lines.append(f"   · v{hijo} (n={nh}) frente a v{padre} "
                                 f"(n={npd})")
                if len(entre) > 12:
                    lines.append(f"   · … y {len(entre) - 12} más")
        except Exception as e:
            _warn("no se pudo comprobar la muestra de cada entrada", e)

        # El guion guarda VEREDICTOS, y un veredicto sólo significa algo junto al
        # instrumento que lo produjo. Si alguna entrada se calculó con otra
        # versión, el mapa lo dice — porque si no, presenta como estado actual
        # algo que puede venir de una versión con un defecto ya corregido.
        try:
            actual = _version_instr()
            viejos = sorted({e.instrumento for e in g.entries
                             if getattr(e, "instrumento", "") and
                             e.instrumento != actual})
            sin = [e.version for e in g.entries
                   if not getattr(e, "instrumento", "")]
            if viejos or sin:
                lines += ["", "⚠ **No todo se calculó con el mismo instrumento.**"]
                if viejos:
                    lines.append(f"   actual: `{actual}` · también hay: "
                                 + ", ".join(f"`{v}`" for v in viejos))
                if sin:
                    lines.append(f"   sin registrar: v"
                                 + ", v".join(str(v) for v in sin)
                                 + " — anteriores a que el guion guardara la versión")
                lines.append("   Los veredictos `Q✓`/`JB✓` de esas entradas son "
                             "los que dio SU instrumento, no el de ahora. Los "
                             "p-valores están guardados: `export_guion` los "
                             "vuelca para releerlos.")
        except Exception as _vi:
            # Un `pass` aquí ya ocultó un NameError durante el desarrollo. Una
            # guarda que calla convierte un fallo en una ausencia, y una
            # ausencia se lee como «no hay nada que avisar».
            lines += ["", f"*[aviso de instrumento no disponible: "
                      f"{type(_vi).__name__}: {_vi}]*"]

        # Y la otra cosa que hace incomparable una columna de ℓ/AIC: la ESCALA.
        # La suite estima sobre 100·log(y) y `fue.Model` trae refactor=1.0 por
        # defecto, así que un modelo construido a mano entra en el guion con una
        # ℓ que difiere en n·ln(100) de la de sus hermanos. Mismo modelo, otras
        # unidades — y el mapa los apilaba en la misma columna (BUG-0085).
        try:
            escalas = sorted({round(float(e.stats.refactor), 6)
                              for e in g.entries
                              if e.stats is not None
                              and getattr(e.stats, "refactor", None)})
            sin_esc = [e.version for e in g.entries
                       if e.stats is not None
                       and not getattr(e.stats, "refactor", None)]
            if len(escalas) > 1:
                lines += ["", "⚠ **No todo está en la misma ESCALA.** Factores "
                          "de reescala presentes: "
                          + ", ".join(f"`{x:g}`" for x in escalas) + ".",
                          "   ℓ, AIC y BIC difieren en n·ln(factor) entre "
                          "escalas: son el mismo ajuste en otras unidades. "
                          "**No restes entradas de escalas distintas** — ni "
                          "por AIC ni por LR. La convención de la suite es "
                          f"`{_RESCALE_FACTOR:g}`, que es la que hace que σ̂ₐ "
                          "se lea en tanto por ciento."]
            elif sin_esc:
                lines += ["", "*Escala no registrada en v"
                          + ", v".join(str(v) for v in sin_esc)
                          + " — anteriores a que el guion la guardara "
                          "(BUG-0085). Se presumen de la convención, pero no "
                          "está comprobado.*"]
        except Exception as _es:
            lines += ["", f"*[aviso de escala no disponible: "
                      f"{type(_es).__name__}: {_es}]*"]

        # Y la tercera cosa que hace irreleíble un nodo: que no quede el `.out`.
        # La covarianza no es una propiedad del óptimo sino del CAMINO del
        # optimizador, así que el `.pre` no puede llevarla: sin `.out`, los
        # errores típicos de ese nodo no se recuperan sin reestimar desde el
        # `.inp` (BUG-0090, BUG-0091). No es lo mismo «puedo releerlo» que
        # «tengo que rehacerlo», y el mapa es donde se decide a dónde volver.
        try:
            sin_out, sin_inp = [], []
            for e in g.entries:
                if e.is_node or not (e.inp_path or ""):
                    continue
                _b = os.path.splitext(e.inp_path)[0]
                if not os.path.exists(_b + ".inp"):
                    sin_inp.append(e.version)
                elif not (getattr(e, "out_path", None)
                          and os.path.exists(e.out_path)) \
                        and not os.path.exists(_b + ".out"):
                    sin_out.append(e.version)
            if sin_inp:
                lines += ["", "⚠ **Nodos sin su `.inp`:** v"
                          + ", v".join(str(v) for v in sin_inp)
                          + ". Desde ellos **no se puede reestimar** — el "
                          "fichero que los produjo no está donde el guion dice."]
            if sin_out:
                lines += ["", "*Nodos sin su `.out`: v"
                          + ", v".join(str(v) for v in sin_out)
                          + ". Se pueden reestimar desde su `.inp`, pero sus "
                          "errores típicos no se pueden LEER: el `.out` es la "
                          "única constancia fiel de la covarianza.*"]
        except Exception as _ao:
            lines += ["", f"*[aviso de artefactos no disponible: "
                      f"{type(_ao).__name__}: {_ao}]*"]
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
        # ¿SE PUEDE FIAR UNO DE ESTA CASCADA? Arrastra a los descendientes por
        # diseño, y eso sólo es correcto si el parentesco es cierto. Una entrada
        # cuyo padre se INFIRIÓ —porque nadie pasó `base_pre_path`— puede colgar
        # de quien no le toca, y entonces la cascada barre una rama viva
        # (BUG-0108). Se avisa ANTES de tocar nada.
        aviso_linaje = ""
        if cascade:
            from art.guion import descendants as _desc
            dudosas = [v for v in _desc(g, version)
                       if getattr(por_v.get(v), "parent_origen", "") == "inferido"]
            if dudosas:
                aviso_linaje = (
                    "\n\n⚠ **La cascada se apoya en un parentesco INFERIDO** en "
                    + ", ".join(f"v{v} ({por_v[v].name})" for v in dudosas)
                    + ". Esas entradas no declararon de qué modelo salían, así "
                      "que su padre es «la última entrada del guion» y puede no "
                      "ser el real. Compruébalo antes de darlas por muertas: si "
                      "alguna no desciende de v"
                    + str(version)
                    + ", repite con `cascade=False` (BUG-0108).")
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
        return [TextContent(type="text", text="\n".join(txt) + aviso_linaje)]
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

        # COMPARAR NO ES ESTIMAR — BUG-0158.
        #
        # Esto llamaba a `_load_fitted`, o sea que reestimaba los dos modelos
        # teniendo el `.out` delante. Dos costes, y el segundo es el grave:
        #
        #   · 25,4 ms frente a 2,9 leyendo el `.out`, para el MISMO AIC al
        #     cuarto decimal;
        #   · y si lo que se compara es un `.pre` —o un `.inp` escrito por
        #     `_write_inp` tras ajustar, que es el caso normal en una cadena de
        #     versiones—, el optimizador arranca en el óptimo, apenas itera y la
        #     covarianza se queda en la semilla. Medido sobre FOOD_UEM: SE de
        #     0,0835 frente a los 0,2315 del `.out`, factor 2,8. La herramienta
        #     cuyo trabajo es comparar dos modelos era la que más fácilmente
        #     publicaba errores típicos inválidos, justo cuando el analista los
        #     mira para decidir si poda un parámetro.
        #
        # `mirar` para lo que depende de los VALORES —residuos, diagnosis,
        # figuras, que en un `.pre` son exactos— y el `.out` para lo que depende
        # de la ESTIMACIÓN: ℓ, AIC, BIC y las desviaciones típicas.
        _, ma = _mirar(inp_path_a)
        _, mb = _mirar(inp_path_b)

        spec_a = _extract_spec(ma, lam=lam_a)
        spec_b = _extract_spec(mb, lam=lam_b)
        eq_a   = _build_equation(spec_a, ma.series.freq)
        eq_b   = _build_equation(spec_b, mb.series.freq)

        diag_a = diagnose(ma)
        diag_b = diagnose(mb)

        # ℓ, AIC y BIC del REGISTRO cuando lo hay. El `.out` publica la
        # verosimilitud con precisión completa —el campo se llama `logelf`: la
        # calculada con `elf` en la última iteración— y `art.outfile` ya la
        # parsea. Verificado contra `fue.aic`: coinciden al cuarto decimal.
        def _criterios(m, ruta):
            r = getattr(m, "_result", None)
            try:
                from art.outfile import hay_out, lee_out
                if hay_out(ruta):
                    o = lee_out(ruta)
                    if o.loglik is not None and o.npar and o.nobs:
                        import math as _m
                        # `residuals` es un ARRAY. Escrito `res or []`, numpy
                        # evalúa su verdad y levanta ValueError — que el
                        # `except` de abajo se tragaba entero. El arreglo de
                        # BUG-0158 quedó así de código MUERTO desde el primer
                        # día: la herramienta seguía recalculando y ninguna
                        # prueba lo veía, porque el número recalculado es el
                        # mismo. Lo destapó la prueba del centinela.
                        res = getattr(r, "residuals", None)
                        ne = int(np.size(res)) if res is not None else 0
                        ne = ne or (o.nobs - 1)
                        return (o.loglik, -2 * o.loglik + 2 * o.npar,
                                -2 * o.loglik + o.npar * _m.log(ne), o.npar,
                                True)
            except Exception as _e:
                # Y no se calla: un `.out` ilegible es una noticia, no un
                # detalle. Callarlo es lo que dejó el fallo de arriba invisible.
                _warn(f"no se pudieron leer los criterios del `.out` de "
                      f"{os.path.basename(ruta)}", _e)
            return (r.loglik, r.aic, r.bic, r.npar, False)

        la, aic_a, bic_a, npar_a, _reg_a = _criterios(ma, inp_path_a)
        lb, aic_b, bic_b, npar_b, _reg_b = _criterios(mb, inp_path_b)
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

        # El operador no es lo único que rompe la comparabilidad: el FACTOR DE
        # REESCALA también. La suite estima sobre 100·log(y) y `fue.Model` trae
        # 1.0 por defecto, así que un modelo construido a mano tiene una ℓ que
        # difiere en n·ln(100) — mismo ajuste, otras unidades (BUG-0085). Aquí
        # el remedio es distinto del de BUG-0051: no son modelos distintos, es
        # el MISMO modelo mal anotado, y se arregla reestimando en la
        # convención.
        _ra = float(getattr(ma, "refactor", None) or 1.0)
        _rb = float(getattr(mb, "refactor", None) or 1.0)
        if abs(_ra - _rb) > 1e-9:
            comparables = False
            import math as _math
            _n = min(len(ma._result.residuals), len(mb._result.residuals))
            aviso_escala += [
                "",
                "> ⚠ **Los dos modelos están en ESCALAS distintas** "
                f"(factor de reescala `{_ra:g}` frente a `{_rb:g}`). ℓ, AIC y "
                f"BIC difieren en n·ln(factor) ≈ **{abs(_n * _math.log(_rb / _ra)):.0f}** "
                "puntos de ℓ que son puro cambio de unidades, no de ajuste. Su "
                "Δ se ha suprimido.",
                ">",
                "> Esto no son dos modelos distintos: es el mismo mal anotado. "
                f"La convención de la suite es `{_RESCALE_FACTOR:g}` (hace que "
                "σ̂ₐ se lea en tanto por ciento). Reestima el que se salga y "
                "vuelve a compararlos.",
            ]

        # ── Nested LR test ─────────────────────────────────────────────────
        nested = _nested_relation(spec_a, spec_b, npar_a, npar_b)
        lr_lines = []
        if nested and not comparables:
            # El LR es una DIFERENCIA de verosimilitudes: si no son comparables,
            # tampoco lo es su diferencia. Y aquí duele más que en el ΔAIC,
            # porque el χ² saldría enorme y con p≈0 — un contraste que dice
            # «significativo» sobre un cambio de unidades (BUG-0051, BUG-0085).
            lr_lines = ["", "**Contraste LR:** suprimido — los dos modelos "
                        "están anidados pero sus verosimilitudes no son "
                        "comparables (ver el aviso de arriba). Un LR sobre "
                        "escalas distintas mide unidades, no ajuste."]
            nested = None
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

        # SIN FIGURA — BUG-0137.
        #
        # Aquí había SEIS paneles: residuos, ACF y PACF de cada modelo, lado a
        # lado. 1515 × 1076 px y 106 KB — la figura más pesada del sistema— para
        # cero llamadas en 1.114 registradas.
        #
        # Y no servía en ninguno de los dos casos posibles. Cuando los modelos
        # se parecen, los seis paneles son indistinguibles: comparando el m41 y
        # el m31 de RATIO, que difieren en σ_a en 0,0012, las dos columnas se
        # superponen. Y cuando difieren, dos paneles con la misma escala
        # obligan a ir y venir con la vista.
        #
        # Lo que decide una comparación de versiones está entero en la tabla que
        # esta misma salida ya imprime — loglik, AIC, BIC, npar y su Δ— más el
        # aviso de si los modelos están anidados. Cuatro números y una
        # advertencia. El dibujo era sobre-elaborar.
        b64 = None

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
            items.append(_imagen(b64, "compare_versions"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: guided_intervention — la PUERTA del nodo de intervención
# ---------------------------------------------------------------------------

@mcp.tool()
def guided_intervention(inp_path: str,
                        escalera: bool = False,
                        date: str = "",
                        form: str = "",
                        n_omega: int = 0,
                        n_delta: int = 0,
                        rehacer: bool = False,
                        output_path: str = "",
                        threshold: float = 3.0,
                        umbral_activo: float = 1.0,
                        umbral_vecino: float = 0.0,
                        dominio: str = "",
                        evento_desde: str = "",
                        evento_naturaleza: _Naturaleza = "",
                        evento_fuente: str = "",
                        aportada_por: str = "",
                        guion_path: str = "",
                        guion_name: str = "",
                        guion_decision: str = "",
                        guion_rationale: str = "",
                        guion_problems: str = "",
                        guion_next: str = "",
                        modo: _Modo = "guiado") -> list:
    """
    Sequential INTERVENTION — ONE decision node per call.

    La entrada del nodo de intervención, paralela a `guided_identification`. El
    nodo tiene nueve instrumentos y era el único de la suite sin puerta: el
    analista tenía que elegir a ciegas entre ellos y ninguno remitía a otro.
    Esta herramienta los SECUENCIA y presenta un veredicto por llamada. **No
    decide**: el analista decide en cada paso, igual que en identificación.

    DECISION TREE — call in this sequence, one at a time:

    Call 1   date=""   (default)
      → ¿HAY QUE INTERVENIR? Calibra el correlograma OMITIENDO los anómalos y
        dice si la identificación cambia: qué órdenes AR (PACF) y MA (ACF)
        entran o salen. **Si no cambia nada, lo dice y avisa de que intervenir
        aquí es sobre-intervenir** — cada intervención encoge σ̂ y promueve al
        siguiente anómalo, así que la escalada no para sola.
        Devuelve además las fechas candidatas con su |z|.
      WAIT for user: qué fecha, o parar.

    Call 2   date="Q3/2008"   form=""
      → ¿QUÉ FORMA ADMITE EL DATO? En UNA respuesta:
          · el EPISODIO — cuántos períodos del nivel altera el suceso;
          · las CONFIGURACIONES que el dato admite, acotadas por el mecanismo,
            con su ganancia ω(1) y su lectura permanente/transitorio;
          · la ESCALERA de Ockham con lo que justifica subir de peldaño.
        Y un veredicto único, con el árbitro explícito: para la FORMA gobierna
        `incident_configurations` sobre `residual_episodes`, porque extiende el
        arranque por el mecanismo y el otro sólo agrupa extremos.
        Si el dato NO identifica la configuración, lo dice y pide lo
        extramuestral en vez de elegir por AIC.
      WAIT for user: qué forma y de CUÁNTOS ESCALONES.

    Call 3   date="Q3/2008"   form="step"   n_omega=5   output_path=...
             (n_omega = cuántos escalones; 5 escalones ⇔ ω(B) de orden 4)
      → CONSTRUYE la forma elegida, estima, y verifica:
          · Treadway — ¿queda un anómalo de vecino? ¿el residuo en la fecha
            está en la media?
          · ganancia — Wald sobre ω(1)=0: ¿permanente o transitorio?
        Deja el nodo en el guion. Éste es el paso que faltaba (BUG-0079).

    Parameters
    ----------
    inp_path      : .inp del modelo estimado **SIN** la intervención
    date          : "" → Call 1. "MM/YYYY", "QN/YYYY" o "YYYY" → Call 2 ó 3
    form          : "" → Call 2. "step"|"pulse"|"impulse"|"ramp" → Call 3
    modo          : "guiado" (por defecto) | "autonomo". En AUTÓNOMO la rampa
                    se rechaza (BUG-0182); se pasa tal cual a
                    `suggest_intervention_form`, que es quien la construye.
    n_delta       : nº de coeficientes δ del denominador. 0 = sin denominador.
                    Con `form="impulse"` y `n_delta=1` es la FORMA RACIONAL
                    ω₀/(1−δB) — salta y decae, dos parámetros (BUG-0161).
    rehacer       : REFORMULAR la intervención de este suceso en vez de añadir
                    otra. Retira la que cae cerca de `date` y pone la nueva en
                    su lugar — cambiar la forma, bajar el orden de ω o mover la
                    fecha. Es la operación central del ciclo (BUG-0162).
    n_omega       : **cuántos ω**, que es lo mismo que cuántos ESCALONES en el
                    nivel — la lengua en la que habla todo este nodo:
                    `incident_configurations` dice «N escalones», la escalera
                    dice «N escalones», y la Call 2 te devuelve el `n_omega` ya
                    calculado. 0 = lo decide la escalera.

                    La equivalencia, por si vienes del operador: **N escalones
                    ⇔ ω(B) de orden N−1**. Así que `n_omega=2` son DOS escalones
                    y un ω(B) = ω₀ − ω₁B.

                    ⚠ Esta línea documentaba el parámetro como si fuera el
                    grado del polinomio, y no lo es: cuenta coeficientes. Un
                    analista al que Treadway le ordenaba subir de peldaño pasaba
                    `n_omega=1` creyendo pedir la escalera de dos, recibía un
                    escalón simple, y la cabecera se lo confirmaba en las
                    unidades equivocadas. No se le ignoraba: se le había
                    documentado otra cosa (BUG-0093).
    output_path   : obligatorio en la Call 3 — dónde se escribe el modelo nuevo
    threshold     : |z| para marcar un residuo como extremo
    umbral_activo : |z| a partir del cual un vecino cuenta como parte del suceso
                    aunque no sea extremo (Call 2)
    umbral_vecino : |z| a partir del cual un vecino cuenta como anómalo
                    (Treadway, Call 2). 0 = el de la política (2.0)
    dominio       : clase de serie ("price_index", "generic"…). Vacío = la
                    infiere `policy.decide_domain`. Lo declarado gana.
    evento_*      : lo extramuestral, que sólo sabe el analista. `evento_fuente`
                    es obligatoria si se declara `evento_naturaleza`: no se
                    afirma que un suceso fue permanente sin decir por qué se
                    sabe. `evento_naturaleza` son TRES lecturas y no dos —
                    `permanente`, `transitorio`, `recuperacion_parcial`— y la
                    descripción del suceso va en `evento_fuente`, no ahí.
    guion_*       : registro del nodo, como en el resto de la suite
    """
    try:
        import numpy as np
        from art.policy import THRESHOLDS, decide_domain, decide_episodios

        # BUG-0164. De este modelo sólo se toman la ESTRUCTURA, la serie y
        # los RESIDUOS; las desviaciones típicas que se publican son las de
        # los candidatos, estimados cada uno aparte. Así que le toca
        # `mirar`, no `estimar` — y con `estimar` rechazando el `.pre`
        # (BUG-0159) esta puerta se quedó cerrada para el encadenado, que
        # es el modo NORMAL de usarla.
        ts, m = _mirar(inp_path)
        # `_load_fitted` y no `_load_ts_model` + `fit()` a mano: esa vía no sella
        # el origen del fichero, y con ella el aviso de BUG-0090 es
        # inalcanzable — el contrato tenía tres puertas y una cuarta abierta.
        if m.residuals is None:
            return _err("el modelo no tiene residuos: ¿se estimó?")

        freq = int(ts.freq or 1)
        d_reg = int(getattr(m, "d", 0))
        # BUG-0172: sin el consumo de `ifadf`, los episodios salían fechados
        # 2-4 meses tarde sobre un modelo reformulado.
        from art.identification import desfase_observaciones as _desf_obs
        desfase = d_reg - int(getattr(m, "d", 0) or 0) + _desf_obs(m)
        dom = dominio.strip() or (decide_domain(ts) if True else "generic")

        r = np.asarray(m.residuals.data, dtype=float)
        sd = r.std(ddof=0)
        z = r / sd if sd > 0 else r

        def fecha_de_resid(obs_1based: int) -> str:
            """obs 1-based en RESIDUOS → fecha de calendario.

            Los dos espacios de índices otra vez (BUG-0067): los residuos de un
            modelo diferenciado empiezan `d + D·s` observaciones después.
            """
            t0 = (obs_1based - 1) + desfase
            s0 = list(ts.start)
            total = (s0[1] - 1 if freq > 1 else 0) + t0
            if freq == 12:
                return f"{total % 12 + 1:02d}/{s0[0] + total // 12}"
            if freq == 4:
                return f"Q{total % 4 + 1}/{s0[0] + total // 4}"
            return str(s0[0] + total)

        def resid_de_fecha(d_str: str) -> int:
            """fecha → obs 1-based en RESIDUOS. Lanza si cae fuera."""
            import re
            t = d_str.strip()
            mo = re.match(r"^(\d{1,2})/(\d{4})$", t)
            q = re.match(r"^[Qq](\d)/(\d{4})$", t)
            yr = re.match(r"^(\d{4})$", t)
            if mo:
                per, year = int(mo.group(1)), int(mo.group(2))
            elif q:
                per, year = int(q.group(1)), int(q.group(2))
            elif yr:
                per, year = 1, int(yr.group(1))
            else:
                raise ValueError(f"fecha no reconocida: {d_str!r}. "
                                 "Usa MM/AAAA, QN/AAAA o AAAA.")
            s0 = list(ts.start)
            at_0 = (year - s0[0]) * freq + (per - (s0[1] if freq > 1 else 1))
            obs = at_0 - desfase + 1
            if obs < 1 or obs > len(z):
                raise ValueError(
                    f"{d_str} cae en la observación {at_0 + 1} de la serie, que "
                    f"está fuera del rango de residuos [1, {len(z)}] "
                    f"({fecha_de_resid(1)}–{fecha_de_resid(len(z))}). El modelo "
                    f"consume {desfase} observación(es) al diferenciar.")
            return obs

        # ═════════════════ LLAMADA 3 — construir y verificar ═════════════════
        if date.strip() and form.strip():
            if not output_path.strip():
                return _err(
                    "la llamada 3 CONSTRUYE el modelo, así que necesita "
                    "`output_path`: dónde escribir el `.inp` con la "
                    "intervención. (Si lo que querías era ver las formas que el "
                    "dato admite, llama sin `form`.)")
            _sif = getattr(suggest_intervention_form, "fn",
                           suggest_intervention_form)
            partes = _sif(inp_path, output_path, date=date, form=form,
                          rehacer=rehacer,
                          n_omega=n_omega, n_delta=n_delta,
                          guion_path=guion_path, guion_name=guion_name,
                          guion_decision=guion_decision,
                          guion_rationale=guion_rationale,
                          guion_problems=guion_problems,
                          guion_next=guion_next, modo=modo)
            texto = "\n".join(getattr(c, "text", "") for c in partes)
            if texto.startswith("❌"):
                return partes
            _ti = getattr(test_interventions, "fn", test_interventions)
            ver = _ti(output_path)
            from mcp.types import TextContent
            cab = TextContent(type="text", text=(
                "## Llamada 3 — la forma construida, estimada y verificada\n\n"
                f"Se construye **{form}** de **{max(1, int(n_omega))} "
                f"escalón(es) en el nivel** "
                f"(ω de orden {max(1, int(n_omega)) - 1}) en **{date}** "
                f"sobre `{os.path.basename(inp_path)}` → "
                f"`{os.path.basename(output_path)}`.\n"))
            sep = TextContent(type="text", text=(
                "\n---\n\n**¿Funcionó? — Treadway y la ganancia.** "
                "Dos preguntas distintas, y las dos son diagnosis, no bloqueo:\n"
                "el **residuo en la fecha** debe estar en la media (cero) si la "
                "forma absorbió el suceso; y el **vecino** no debe quedar "
                "anómalo, porque lo que la forma no modeliza cae entero ahí.\n"))
            return [cab] + partes + [sep] + ver

        # ═════════════════ LLAMADA 2 — qué forma admite el dato ═════════════
        if date.strip():
            try:
                obs = resid_de_fecha(date)
            except ValueError as ve:
                return _err(str(ve))

            ext = [(i + 1, float(z[i])) for i in range(len(z))
                   if abs(z[i]) > threshold]
            if not ext:
                return _err(
                    f"no hay residuos con |z| > {threshold:g}: no hay suceso "
                    "que analizar. Baja `threshold` o vuelve a la llamada 1.")
            eps = decide_episodios(ext, ventana=THRESHOLDS["ventana_episodio"],
                                   d=d_reg)
            ep = next((e for e in eps if e.inicio <= obs <= e.fin), None)
            if ep is None:
                cerca = ", ".join(
                    f"{fecha_de_resid(e.inicio)}"
                    + ("" if e.aislado else f"–{fecha_de_resid(e.fin)}")
                    for e in eps)
                return _err(
                    f"{date} (obs {obs} de los residuos) no cae en ningún "
                    f"episodio detectado con |z| > {threshold:g}. Los que hay: "
                    f"{cerca}. Si el suceso que buscas tiene el arranque por "
                    "debajo del umbral, baja `threshold`.")

            L = [f"## Llamada 2 — qué forma admite el dato en {date}", ""]

            # ── el episodio ──
            from art.episodes import describe_episodios
            L += [f"### El suceso", "",
                  f"Episodio **{fecha_de_resid(ep.inicio)}"
                  + ("" if ep.aislado else f"–{fecha_de_resid(ep.fin)}") + "**"
                  f" — {ep.n_extremos} extremo(s), "
                  f"|z| máx {ep.z_max:.2f}, "
                  f"**{ep.duracion_nivel} período(s) alterado(s) en el "
                  f"nivel**.", ""]
            if d_reg:
                L += [f"*La duración se cuenta en el NIVEL, no en los residuos: "
                      f"éstos están diferenciados {d_reg} vez(ces), así que L "
                      f"impulsos del nivel se ven como L+{d_reg} extremos.*", ""]
            if ep.parece_encadenado:
                L += ["⚠ **El episodio parece encadenado** (largo o con "
                      "huecos). Una cadena así es más probable que sea "
                      "estructura no modelizada —estacionalidad, un cambio de "
                      "régimen— que un suceso. Míralo antes de intervenir.", ""]

            # ── las configuraciones: el ÁRBITRO de la forma ──
            from art.configuracion import (InfoExtramuestral,
                                           arranques_candidatos,
                                           describe_configuraciones,
                                           evalua_configuraciones)
            try:
                info = InfoExtramuestral(desde=evento_desde.strip(),
                                         naturaleza=evento_naturaleza.strip(),
                                         fuente=evento_fuente.strip(),
                                         aportada_por=aportada_por.strip())
            except ValueError as ve:
                return _err(str(ve))
            cands = arranques_candidatos(z, [o - 1 for o, _ in ep.extremos],
                                         d=d_reg, umbral_activo=umbral_activo)
            conj = evalua_configuraciones(
                m, cands, d=d_reg, dominio=dom, info=info, freq=freq,
                start_year=int(list(ts.start)[0]),
                start_per=int(list(ts.start)[1] if freq > 1 else 1),
                umbral_vecino=umbral_vecino, umbral_activo=umbral_activo)
            # BUG-0154: sin su veredicto, porque esta llamada publica el suyo
            # unas líneas más abajo. Una conclusión, una vez, donde se decide.
            d_cfg = describe_configuraciones(conj, veredicto=False)
            L += ["---", "", d_cfg.summary, ""]

            # ── la escalera: SÓLO SI SE PIDE — BUG-0138 ──
            #
            # Decisión del analista en el censo de figuras: «la superposición
            # lleva la sugerencia y la escalera es el argumento si es
            # necesario». El analista pregunta qué forma se adapta; la
            # herramienta le dice una. Si replica con otra, ENTONCES la escalera
            # es el argumento.
            #
            # Cuesta TRES ESTIMACIONES, y hasta ahora se disparaban siempre —
            # antes de que nadie hubiera discutido nada. En carril autónomo
            # sigue siendo obligatoria: ahí no hay quien discuta, y su
            # información ES el criterio. La corre
            # `suggest_intervention_form(form="auto")`, que no se toca.
            esc = None
            d_esc = None
            if escalera:
                from art.escalera import describe_escalera, escalera_de_ockham
                # ALINEADA CON LA CONFIGURACIÓN — BUG-0156.
                #
                # La escalera caminaba desde el primer extremo del episodio
                # mientras las configuraciones exploran arranques hacia atrás
                # por el mecanismo. Sobre ITCER eso ponía los peldaños en
                # Q4/2008 y la configuración ganadora en Q2/2008: dos
                # recomendaciones en la misma salida que ni siquiera hablaban
                # del mismo suceso, y el analista arbitrando entre ellas.
                #
                # Con el arranque del mecanismo los tres peldaños comparan la
                # MISMA fecha, el peldaño alto ES la configuración ganadora, y
                # a la escalera le queda la única pregunta que sabe contestar:
                # ¿hace falta tanta forma?
                _mj = conj.mejor
                _al = {}
                if _mj is not None and _mj.estimado:
                    _al = dict(at=_mj.arranque_resid - 1 + desfase,
                               n_alto=_mj.n_escalones,
                               fecha_arranque=_mj.fecha)
                esc = escalera_de_ockham(m, ep, dominio=dom,
                                         umbral_vecino=umbral_vecino, **_al)
                d_esc = describe_escalera(esc)
                L += ["---", "", d_esc.summary, ""]

            # ── EL VEREDICTO ÚNICO, con el árbitro dicho ──
            L += ["---", "", "## Veredicto", ""]
            mejor = conj.mejor
            if conj.vivos and mejor is not None and not conj.identificado:
                rg = conj.rango_ganancia
                L += ["**El dato no identifica la configuración.** No elijas "
                      "por AIC: aporta `evento_desde` y `evento_naturaleza` "
                      "con su `evento_fuente`, o publica el rango de la "
                      "ganancia en vez de un número"
                      + (f" (**{rg[0]:+.4f}** a **{rg[1]:+.4f}**)" if rg else "")
                      + ".", ""]
            if mejor is not None and mejor.estimado:
                L += [f"- **Forma** — la gobierna la configuración, que extiende "
                      f"el arranque por el MECANISMO: `{mejor.etiqueta}`, es "
                      f"decir {mejor.en_palabras}.", ""]
                # DOS INSTRUMENTOS, DOS PREGUNTAS — BUG-0156.
                #
                # La escalera y las configuraciones se publicaban juntas y cada
                # una con su recomendación, sin decir cuál gobierna. Sobre
                # ITCER: la escalera `1a` —un parámetro— y el veredicto
                # `Q2/2008×3` —tres—. El analista tenía que arbitrar entre dos
                # partes de la misma salida.
                #
                # No se resuelve eligiendo una: que discrepen es INFORMACIÓN, y
                # cada una contesta lo suyo. El mecanismo acota la FORMA —qué
                # arranque y cuántos escalones admite el dato—; la navaja acota
                # la SOFISTICACIÓN —cuánta forma se sostiene—. Lo que hay que
                # decir es eso, y que la discrepancia se discute, no se arbitra
                # por AIC.
                if esc is not None and esc.recomendado:
                    _alto = esc.por_nivel("2")
                    _n_esc = (_alto.n_omega if _alto is not None
                              else mejor.n_escalones)
                    if esc.recomendado != "2" and mejor.n_escalones > 1:
                        L += [
                            "- ⚠ **Los dos instrumentos no dicen lo mismo, y es "
                            "información.** El mecanismo admite "
                            f"`{mejor.etiqueta}` ({mejor.n_escalones} "
                            f"parámetro(s)); la navaja se queda en "
                            f"`{esc.recomendado}` (1 parámetro).", "",
                            "  No lo arbitra el AIC. **El mecanismo acota la "
                            "FORMA** —qué arranque y cuántos escalones cabe "
                            "que tenga el suceso— **y la navaja acota la "
                            "SOFISTICACIÓN** —cuánta de esa forma sostiene el "
                            "dato—. Que la forma admisible sea más rica que la "
                            "que la navaja sostiene es exactamente lo que hay "
                            "que discutir: o el suceso es más simple de lo que "
                            "el mecanismo permite, o falta la información "
                            "extramuestral que lo justifique.", "",
                            "  *Y si lo que falla es que ninguna forma de una "
                            "sola fecha resuelve el suceso, mira si hay vuelta "
                            "diferida: eso son dos intervenciones y su "
                            "ganancia NETA, no una forma más rica "
                            "(BUG-0157).*", ""]
                    elif esc.recomendado == "2" and _n_esc == mejor.n_escalones:
                        L += ["- ✓ **Los dos instrumentos coinciden**: el "
                              "mecanismo admite esta forma y la navaja la "
                              "sostiene. No hay nada que arbitrar.", ""]
                if esc is not None and esc.nivel_simple:
                    L += [f"- **Lectura escalar** — `{esc.nivel_simple}` por la "
                          f"firma del residuo: {esc.criterio_simple}. *El AIC no "
                          "arbitra entre las dos lecturas del peldaño 1: no "
                          "están anidadas y cuestan lo mismo.*", ""]
                if esc is None:
                    L += ["- **¿No te convence esta forma?** La escalera de "
                          "Ockham es el argumento: estima las rivales EN ORDEN "
                          "y dice qué justifica subir de peldaño —Treadway, "
                          "inadecuación, dominio—, con el AIC mirando y sin "
                          "arbitrar. Cuesta tres estimaciones, así que se pide:",
                          "", "```",
                          f'guided_intervention(inp_path="{inp_path}",',
                          f'                    date="{date}", escalera=True)',
                          "```", ""]
                elif esc.razones_para_subir:
                    L += ["- **Razones para subir de peldaño**: "
                          + str(len(esc.razones_para_subir)) + " (arriba).", ""]
                else:
                    L += ["- **Nada justifica subir de peldaño.** La navaja "
                          "manda quedarse abajo aunque el peldaño 2 ajuste "
                          "mejor.", ""]
                _no = mejor.n_escalones
                L += ["", "**Siguiente llamada** — construir y verificar:", "",
                      "```",
                      f'guided_intervention(inp_path="{inp_path}",',
                      f'                    date="{mejor.fecha}", form="step",',
                      f'                    n_omega={_no},',
                      '                    output_path="<...>.inp")',
                      "```"]
            else:
                L += ["Ninguna configuración llegó a estimarse. Mira los "
                      "errores de la tabla."]

            from art.describe import Description
            # LA FIGURA DE ESTA LLAMADA — BUG-0138.
            #
            # Sin escalera, la figura es la SUPERPOSICIÓN de la forma sugerida
            # sobre lo observado: es la que contesta la pregunta del analista
            # —«¿qué forma se adapta a los datos?»— y no cuesta ninguna
            # estimación, porque dibuja una hipótesis, no un ajuste.
            #
            # Con `escalera=True` la figura pasa a ser la de los peldaños, que
            # es la del argumento.
            _fig2 = None
            if d_esc is not None:
                _fig2 = d_esc.figure_b64
            elif mejor is not None and getattr(mejor, "model", None) is not None:
                try:
                    from art.ltf import describe_superposicion
                    _itv = [i for i in (mejor.model.interventions or [])
                            if i.type in ("step", "pulse", "impulse", "compimp")]
                    if _itv:
                        _om = list(_itv[-1].omega or [])
                        _ent = ("impulso" if _itv[-1].type in
                                ("pulse", "impulse", "compimp") else "escalon")
                        # el calendario, con el desfase de los residuos — BUG-0140
                        _f = int(getattr(ts, "freq", 1) or 1)
                        # BUG-0149. Dos datos que esta llamada no pasaba:
                        #
                        # `d` — lo observado son RESIDUOS EN ∇ y `superpone`
                        # tomaba d=0, así que simulaba la respuesta en el NIVEL.
                        # Un escalón permanente en el nivel no vuelve nunca a
                        # cero, y el soporte se define como el último índice con
                        # respuesta ≠ 0: salían 17 trimestres de sombra y la
                        # escala por mínimos cuadrados se iba a ≈0 —la línea
                        # plana que el analista vio—.
                        #
                        # `at` — se pasaba `ep.inicio`, la fecha del extremo que
                        # ABRIÓ el episodio, no el arranque de la configuración
                        # que se dibuja. Para `Q2/2008×3` son dos períodos: la
                        # hipótesis caía sobre datos que no le corresponden.
                        # `Candidato.arranque_resid` ya trae la posición buena,
                        # 1-based en residuos, que es el índice de `at`.
                        _fig2 = describe_superposicion(
                            m._result.residuals,
                            at=int(getattr(mejor, "arranque_resid", ep.inicio)),
                            omega=_om, entrada=_ent,
                            d=int(getattr(m, "d", 0)),
                            freq=_f, start=getattr(ts, "start", ()),
                            desfase=_desfase_obs(m),      # BUG-0172
                            etiqueta=f"{mejor.etiqueta} — {mejor.en_palabras}",
                        ).figure_b64
                except Exception as _se:
                    _warn(f"guided_intervention: superposición no disponible: {_se}")

            # Y la recomendación de esta llamada es LO QUE TOCA HACER, no la
            # conclusión otra vez: la sección «Veredicto» de arriba ya la
            # enuncia y `d_cfg.recommendation` la reenunciaba con las mismas
            # palabras (BUG-0154). Se conserva lo que d_cfg añade y el veredicto
            # no lleva: el aviso de cuando el dato NO identifica, que es una
            # orden de no elegir por AIC.
            _rec2 = (f"**Construye la forma del veredicto**: `date="
                     f'"{mejor.fecha}"`, `form="step"`, '
                     f"`n_omega={mejor.n_escalones}` — y verifica el ajuste."
                     if (mejor is not None and mejor.estimado
                         and conj.identificado)
                     else d_cfg.recommendation)
            return _result(Description(summary="\n".join(L),
                                       figure_b64=_fig2,
                                       recommendation=_rec2,
                                       data=dict(llamada=2,
                                                 identificado=conj.identificado,
                                                 n_construidas=len(conj.vivos),
                                                 escalera=bool(esc is not None),
                                                 nivel_simple=(esc.nivel_simple
                                                               if esc is not None
                                                               else None))))

        # ═════════════════ LLAMADA 1 — ¿hay que intervenir? ═════════════════
        from art.calibracion import calibra_correlograma, describe_calibracion
        _f = int(getattr(ts, "freq", 1) or 1)
        cal = calibra_correlograma(
            m._result.residuals, umbral=threshold,
            freq=_f, start=getattr(ts, "start", ()),
            desfase=_desfase_obs(m))                          # BUG-0172
        # BUG-0133: de aquí sale la TABLA con su veredicto por retardo. La
        # FIGURA de esta llamada es la del escaneo de tres paneles —el gráfico
        # de calibración de distorsiones—, que enseña además dónde está el
        # suceso y lleva la Q al pie. Tener las dos era duplicar.
        d_cal = describe_calibracion(cal, nombre=os.path.basename(inp_path),
                                     con_figura=False)

        L = ["## Llamada 1 — ¿hay que intervenir aquí?", "",
             "La pregunta NO es «¿hay anómalos?» sino «¿cambian la "
             "identificación?». Se calibra el correlograma **omitiendo** los "
             "anómalos —no sustituyéndolos— y se mira qué órdenes entran o "
             "salen: la **PACF** decide el orden AR y la **ACF** el MA, y "
             "pueden cambiar de veredicto en sentidos opuestos en el mismo "
             "retardo.", "", "---", "", d_cal.summary, ""]

        cambia = bool(getattr(cal, "flips_ar", []) or getattr(cal, "flips_ma", []))
        L += ["---", "", "## Veredicto", ""]
        if cambia:
            L += ["**Los anómalos SÍ cambian la identificación.** Intervenir "
                  "está justificado: sin hacerlo se estaría eligiendo el orden "
                  "de los operadores sobre un correlograma contaminado.", ""]
        else:
            L += ["**Los anómalos NO cambian la identificación.** Ningún "
                  "retardo cambia de veredicto al omitirlos, ni en la ACF ni "
                  "en la PACF.", "",
                  "⚠ **Intervenir aquí es sobre-intervenir.** Y no se detiene "
                  "solo: cada intervención encoge σ̂, con lo que el siguiente "
                  "residuo sube de |z| y pide su turno. El criterio de parada "
                  "es éste — cuando la calibración deja de decir que los "
                  "anómalos cambian la identificación, se para.", ""]

        ext = [(i + 1, float(z[i])) for i in range(len(z))
               if abs(z[i]) > threshold]
        if ext:
            eps = decide_episodios(ext, ventana=THRESHOLDS["ventana_episodio"],
                                   d=d_reg)
            # El `|` de |z| parte la celda en Markdown: la barra vertical es
            # el separador de columnas. Se escapa.
            L += ["### Fechas candidatas", "",
                  "| suceso | \\|z\\| máx | períodos en el nivel | fecha para "
                  "la llamada 2 |", "|---|---|---|---|"]
            for e in sorted(eps, key=lambda x: -x.z_max):
                rng = fecha_de_resid(e.inicio) + (
                    "" if e.aislado else f"–{fecha_de_resid(e.fin)}")
                L.append(f"| {rng} | {e.z_max:.2f} | {e.duracion_nivel} | "
                         f"`{fecha_de_resid(e.inicio)}` |")
            L += ["", "**Siguiente llamada** — una fecha, un episodio:", "",
                  "```",
                  f'guided_intervention(inp_path="{inp_path}",',
                  f'                    date="{fecha_de_resid(max(eps, key=lambda x: x.z_max).inicio)}")',
                  "```"]
        else:
            L += [f"*No hay residuos con |z| > {threshold:g}.*"]

        from art.describe import Description, describe_prelim_scan, _resid_start
        _fig = None
        try:
            import fue as _fue
            _res_ts = _fue.TimeSeries(data=m._result.residuals, freq=ts.freq,
                                      start=_resid_start(m), name="Resid")
            _fig = describe_prelim_scan(_res_ts, d=0, D=0, lam=1.0,
                                        threshold=threshold).figure_b64
        except Exception as _fe:
            _warn(f"guided_intervention: figura del escaneo no disponible: {_fe}")
        return _result(Description(summary="\n".join(L),
                                   figure_b64=_fig,
                                   recommendation=d_cal.recommendation,
                                   data=dict(llamada=1,
                                             cambia_identificacion=cambia)))
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: suggest intervention form (B3)
# ---------------------------------------------------------------------------

@mcp.tool()
def suggest_intervention_form(inp_path: str, output_path: str,
                               date: str = "",
                               form: str = "auto",
                               n_omega: int = 0,
                               n_delta: int = 0,
                               rehacer: bool = False,
                               context_hint: str = "",
                               include_histogram: bool = False,
                               guion_path: str = "",
                               guion_name: str = "",
                               guion_decision: str = "",
                               guion_rationale: str = "",
                               guion_problems: str = "",
                               guion_next: str = "",
                               modo: _Modo = "guiado") -> list:
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
    n_delta           : nº de coeficientes δ del DENOMINADOR. **0 = sin
                        denominador** (el comportamiento de siempre).
                        `n_delta=1` con `form="impulse"` da la **forma
                        racional** ω₀/(1−δB): una respuesta que salta y DECAE,
                        en DOS parámetros donde N escalones gastan N. δ es la
                        tasa de decaimiento y tiene lectura sustantiva —«el
                        efecto se disipa a un 57 % por período»— que ω₀ no
                        tiene. La semilla va en 0.0: medido, una semilla cerca
                        de la raíz unidad manda el ajuste a un óptimo espurio
                        248 puntos de AIC peor (BUG-0161). Si δ sale con raíz
                        dentro del círculo unidad la respuesta es EXPLOSIVA y
                        la diagnosis lo dice.
    rehacer           : **REFORMULAR en vez de añadir.** Retira la intervención
                        de suceso que caiga a ±`n_omega` períodos de `date` y
                        pone ésta en su lugar; el resto del modelo se hereda
                        intacto. Sin esto, reformular obligaba a volver a mano
                        al `.pre` anterior a esa intervención, y apuntar al
                        fichero equivocado la dejaba DOS VECES sobre el mismo
                        suceso — con un ω no significativo por síntoma, no un
                        error (BUG-0162). Si no se pide y ya había una
                        intervención ahí, se avisa.
    n_omega           : nº de coeficientes ω del numerador. **0 = automático**
                        (1 con forma explícita; lo que decida la escalera con
                        `form="auto"`). Con `form="step"` y `n_omega=N` se
                        construye la FLT de N escalones consecutivos en el
                        nivel que `incident_configurations` identifica como
                        «fecha×N» — antes no había forma de construirla desde
                        aquí, aunque el motor la soportaba (BUG-0079).
    modo              : "guiado" (por defecto) | "autonomo". En AUTÓNOMO
                        `form="ramp"` se RECHAZA (BUG-0182): una rampa en el
                        nivel es una tendencia determinista desde su fecha, y
                        fija para siempre la pendiente de la previsión. Es
                        instrumento de usuario avanzado, del carril guiado.
    form              : "pulse", "step", "ramp" — o **"auto"**, que corre la
                        ESCALERA DE OCKHAM: estima los peldaños en orden (1a
                        escalón permanente, 1b impulso transitorio, 2 episodio
                        de L+1 escalones) y sube sólo cuando algo lo justifica
                        —Treadway, inadecuación, duración del episodio o
                        dominio—. **El AIC no arbitra la subida.** Deja el nodo
                        de decisión en el guion con las alternativas descartadas
                        y la razón de cada descarte.
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
    # LA RAMPA NO ES DEL CARRIL AUTÓNOMO — BUG-0182.
    #
    # En el run 6 de IPC_ES el LLM, haciendo de analista, resolvió una
    # discrepancia SF/DCD en f=0 metiendo una rampa en 07/2008: fijó la
    # inflación de largo plazo en 0,94 % anual PARA SIEMPRE, con una banda que
    # no recoge esa incertidumbre, y leyó después el DCD con los críticos de
    # siempre sobre una fecha elegida mirando los datos. La razón era buena —
    # ¿raíz unitaria en la inflación o ruptura en su media?— y el método no:
    # decidir el orden de integración a golpe de término determinista. Esa
    # pregunta se contesta en el nodo d, y con el analista humano delante.
    if (form or "").strip().lower() == "ramp" and modo == "autonomo":
        return _err(
            "form=\"ramp\" no se admite en el carril AUTÓNOMO (BUG-0182). Una "
            "rampa en el nivel es una tendencia determinista desde su fecha: la "
            "función de previsión hereda esa pendiente sin fecha de caducidad y "
            "la banda no recoge incertidumbre sobre ella. Si lo que ves es un "
            "cambio en la tasa media de crecimiento, esa es una pregunta sobre "
            "el ORDEN DE INTEGRACIÓN: vuelve al nodo d y contrasta la "
            "alternativa estocástica (d+1, con su testigo MA), o acota la "
            "ventana muestral al régimen que quieras modelizar. Si de verdad "
            "hace falta una rampa, es una decisión del carril guiado.")

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
        # BUG-0164. De este modelo sólo se toman la ESTRUCTURA, la serie y
        # los RESIDUOS; las SE que se imprimen son las del modelo NUEVO,
        # reestimado abajo desde su propio `.inp`. Así que le toca
        # `mirar`, no `estimar` — y con `estimar` rechazando el `.pre`
        # (BUG-0159) esta puerta se quedó cerrada para el encadenado, que
        # es el modo NORMAL de usarla.
        ts, m_src = _mirar(inp_path)

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
        # BUG-0172. Éste es el grave: de aquí sale DÓNDE se coloca la
        # intervención que el analista pide. Sobre `ES_CPI_B_m11` —dos
        # frecuencias reformuladas— una pedida para 03/2022 se ponía en 07/2022.
        from art.identification import desfase_observaciones as _desf_obs
        _desfase = _desf_obs(m_src)

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

        # BUG-0079. `n_omega` explícito manda sobre todo lo demás: es la puerta
        # que faltaba para construir la FLT que el diagnóstico identifica.
        n_omega = max(1, int(n_omega)) if n_omega else 1
        _n_omega_pedido = int(n_omega) if n_omega else 0
        escalera_txt = ""
        escalera_alt = ""
        if form == "auto":
            # LA ESCALERA DE OCKHAM (F3), no la vieja comprobación de adyacencia.
            # `decide_form` devolvía "step" o "pulse" mirando si un vecino era
            # extremo — dos formas elegidas por una regla, sin estimar ninguna
            # alternativa. La escalera ESTIMA los peldaños en orden y sube sólo
            # cuando algo lo justifica: Treadway, inadecuación, duración del
            # episodio o dominio. El AIC no arbitra.
            from art.diagnosis import diagnose
            from art import policy
            from art.escalera import escalera_de_ockham
            diag_tmp = diagnose(m_src, z_threshold=policy.THRESHOLDS["intervention_form"])
            # BUG-0067: los extremos vienen en índices de RESIDUO y `at_0` está
            # en la serie. Se suben los extremos, no se baja `at_0`, que es el
            # que va al modelo.
            eps = policy.decide_episodios(diag_tmp.extreme, d=int(m_src.d))
            obs_res = at_0 + 1 - _desfase
            ep = next((e for e in eps if e.inicio <= obs_res <= e.fin), None)
            if ep is None:
                # fecha fuera de todo episodio detectado: se cae a la regla
                # simple, que para un suceso aislado es la respuesta correcta
                extreme_obs = {obs + _desfase for obs, _ in diag_tmp.extreme}
                form = policy.decide_form(at_0 + 1, extreme_obs)
                escalera_txt = ("\n\n*La fecha no cae en ningún episodio "
                                "detectado; forma decidida por la regla simple.*")
            else:
                try:
                    dom = policy.decide_domain(ts)
                except Exception:
                    dom = "generic"
                # EL ÁRBITRO (arquitectura §4.2). La longitud del peldaño 2 la
                # da `incident_configurations` —que extiende el arranque por el
                # MECANISMO mientras los vecinos sigan activos— y no
                # `ep.n_escalones`, que cuenta sólo extremos y por tanto trunca
                # los sucesos asimétricos (BUG-0083, P5). Sobre ITCER los dos
                # criterios daban 3 escalones desde Q4/2008 y 5 desde Q2/2008,
                # y el primero quedaba a 6,15 puntos de AIC del segundo. Eran
                # dos respuestas a la misma pregunta sin árbitro.
                n_esc, at_esc, nota_cfg = ep.n_escalones, at_0, ""
                _al_esc: dict = {}
                try:
                    import numpy as _np
                    from art.configuracion import (arranques_candidatos,
                                                   evalua_configuraciones)
                    _r = _np.asarray(m_src._result.residuals, dtype=float)
                    _z = (_r - _r.mean()) / (_r.std(ddof=0) or 1.0)
                    _cands = arranques_candidatos(
                        _z, [o - 1 for o, _ in ep.extremos], d=int(m_src.d))
                    _conj = evalua_configuraciones(
                        m_src, _cands, d=int(m_src.d), dominio=dom,
                        freq=int(ts.freq or 4),
                        start_year=int(getattr(ts, "start", (2000, 1))[0]),
                        start_per=int(getattr(ts, "start", (2000, 1))[1]))
                    _mejor = _conj.mejor
                    if _mejor is not None and _mejor.estimado:
                        n_esc = _mejor.n_escalones
                        at_esc = _mejor.arranque_resid - 1 + _desfase
                        _al_esc = dict(at=at_esc, n_alto=n_esc,
                                       fecha_arranque=_mejor.fecha)
                        if not _conj.identificado:
                            nota_cfg = (
                                f"\n\n⚠ **El dato no identifica la "
                                f"configuración**: {len(_conj.empatados)} caen "
                                f"dentro de {_conj.banda_aic:g} puntos de AIC. "
                                "Se toma la de mejor ajuste, pero mira "
                                "`incident_configurations` antes de fijarla — "
                                "las empatadas pueden discrepar en si el efecto "
                                "es permanente o transitorio.")
                        elif (n_esc, at_esc) != (ep.n_escalones, at_0):
                            nota_cfg = (
                                f"\n\n*La forma la fija el MECANISMO y no sólo "
                                f"los extremos: {_mejor.en_palabras}. El "
                                f"detector de episodios, que agrupa sólo "
                                f"extremos, habría dado {ep.n_escalones} "
                                "escalones desde su primer extremo.*")
                except Exception as _ce:
                    nota_cfg = f"\n\n*[configuraciones no disponibles: {_ce}]*"

                # Y LA ESCALERA VA DESPUÉS, ALINEADA CON EL ÁRBITRO — BUG-0156.
                #
                # Estaba antes, así que juzgaba L+1 escalones desde el primer
                # extremo del episodio mientras el código de abajo CONSTRUYE
                # `n_esc` escalones desde `at_esc`. El peldaño que se evaluaba
                # no era el peldaño que se construía — y el comentario del
                # árbitro, dos párrafos más arriba, ya decía que la longitud la
                # fija el mecanismo. Sólo que la escalera no se había enterado.
                esc = escalera_de_ockham(m_src, ep, dominio=dom, **_al_esc)
                # El respaldo era `"1b"` —el impulso transitorio— y eso es la
                # forma menos conservadora de las dos: afirma que el suceso
                # revierte. Cuando la escalera no recomienda, lo que queda es la
                # lectura que dio la firma del residuo (BUG-0086).
                rec = esc.recomendado or esc.nivel_simple or "1a"

                form, n_omega = {"1a": ("step", 1), "1b": ("impulse", 1),
                                 "2": ("step", n_esc)}[rec]
                if rec == "2":
                    at_0 = at_esc
                escalera_txt = _texto_escalera(esc, rec) + nota_cfg
                escalera_alt = _alternativas_escalera(esc, rec)

        # Lo que el analista pide explícitamente manda sobre lo que la
        # escalera decida: `n_omega` es una declaración, no una sugerencia.
        if _n_omega_pedido:
            n_omega = _n_omega_pedido

        # EL DENOMINADOR — BUG-0161.
        #
        # δ(B) estaba cableado de punta a punta —`_write_inp` lo escribe,
        # `art.outfile` lo lee, `test_intervention` calcula δ(1) y la ganancia,
        # `art.ltf` lo dibuja— y NADIE lo construía: cero sitios en todo
        # `src/art/`, y 0 de 216 `.inp` del corpus con un δ. La tubería estaba
        # puesta y no tenía grifo, así que la respuesta que DECAE —la forma
        # racional, dos parámetros donde N escalones gastan N— quedaba fuera del
        # catálogo no por haberse evaluado sino por no saberse montar.
        #
        # LA SEMILLA VA EN 0.0, Y ESO ESTÁ MEDIDO. Sobre un testigo con δ=0,6:
        #
        #     semilla 0,0 / 0,5 / −0,5  →  δ̂=0,5692  AIC 1616,41  ~14 iter.
        #     semilla 0,9               →  δ̂=0,7070  AIC 1864,56  500 iter.,
        #                                  gradiente sin anular
        #
        # Una semilla cerca de la raíz unidad manda al optimizador a un óptimo
        # espurio 248 puntos de AIC peor, y llega con el aviso de fue pero con
        # números de aspecto normal.
        _nd = max(0, int(n_delta))
        _kw_itv = {}
        if _nd:
            _kw_itv = dict(delta=[0.0] * _nd, delta_free=[True] * _nd)

        # Create new Intervention with correct at= (0-based index)
        itv = fue.Intervention(
            type=form,
            at=at_0,
            omega=[0.0] * n_omega,
            omega_free=[True] * n_omega,
            **_kw_itv,
        )

        # REHACER, NO SÓLO AÑADIR — BUG-0162.
        #
        # Todos los constructores hacían `list(interventions) + [itv]`. Append.
        # Y reformular —cambiar la forma, bajar el orden, mover la fecha— es la
        # operación CENTRAL del método iterativo: es lo que hace Box-Jenkins.
        # Se hacía volviendo al `.pre` anterior a la intervención, que es
        # correcto y es IMPLÍCITO: ninguna herramienta lo decía, y dependía de
        # que ese fichero existiera y de que se supiera cuál era. Apuntar al
        # equivocado deja la intervención DOS VECES sobre el mismo suceso, y el
        # síntoma es un ω no significativo, no un error.
        #
        # Y la pieza que retira ya estaba escrita: `hereda_del_base` (BUG-0150)
        # quita la que cae sobre el suceso estudiado, y su docstring dice
        # literalmente «que es el caso de rehacer la forma de un suceso ya
        # intervenido». La usaban la escalera y las configuraciones por dentro;
        # la superficie no la ofrecía. Tercera cara de BUG-0090: la capacidad
        # está abajo y el nodo no la nombra.
        from art.escalera import hereda_del_base
        _ventana = max(1, int(n_omega))
        _previas = [i for i in (m_src.interventions or [])
                    if i.type not in ("cos", "sin", "alter")
                    and abs(int(getattr(i, "at", -10**9)) - at_0) <= _ventana]
        _nota_rehacer = ""
        if rehacer:
            _base_itvs, _retiradas = hereda_del_base(
                m_src, at_estudiado=at_0, ventana=_ventana)
            new_itvs = _base_itvs + [itv]
            if _retiradas:
                _q = ", ".join(f"`{i.type}[obs {int(i.at) + 1}]` "
                               f"({len(i.omega or [])} ω)" for i in _retiradas)
                _nota_rehacer = (
                    f"\n\n♻ **Se ha REHECHO la intervención de este suceso.** "
                    f"Retirada: {_q}. En su lugar va `{form}` con {n_omega} ω "
                    f"en obs {at_0 + 1}. El resto del modelo —las demás "
                    f"intervenciones, la estructura y μ— se hereda intacto.")
            else:
                # Retirar en silencio es cambiar el modelo base sin avisar; no
                # retirar cuando se pidió, también.
                _nota_rehacer = (
                    f"\n\n⚠ **`rehacer=True` pero no había nada que rehacer**: "
                    f"ninguna intervención de suceso cae a ±{_ventana} período(s) "
                    f"de obs {at_0 + 1}. Se ha AÑADIDO, no sustituido. Si querías "
                    f"rehacer otra, mira su fecha en la ecuación del modelo.")
        else:
            new_itvs = list(m_src.interventions or []) + [itv]
            if _previas:
                _q = ", ".join(f"`{i.type}[obs {int(i.at) + 1}]`"
                               for i in _previas)
                _nota_rehacer = (
                    f"\n\n⚠ **Ya había una intervención en este suceso** "
                    f"({_q}) y ésta se ha AÑADIDO encima. Dos intervenciones "
                    f"sobre el mismo suceso se reparten el efecto: el síntoma "
                    f"es un ω que deja de ser significativo, no un error.\n\n"
                    f"Si lo que querías era **reformular**, repite con "
                    f"`rehacer=True` —retira la anterior y pone ésta en su "
                    f"lugar— o parte del `.pre` de antes de aquella "
                    f"intervención. Si de verdad son **dos sucesos distintos** "
                    f"tan juntos, esto está bien: sigue.")
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
        # EL NODO DE DECISIÓN, antes del modelo. Sin él el guion registra el
        # modelo estimado y no la DECISIÓN de forma que lo precede — y esa
        # decisión, con sus alternativas descartadas y la razón de cada
        # descarte, es lo que hace que el recorrido se pueda discutir después.
        if escalera_alt:
            try:
                gp_nodo = guion_path or _derive_guion_path(output_path, m_fit)
                _record_node_to_guion(
                    gp_nodo, nodo="intervenciones",
                    decidido=(f"{form}"
                              + (f" con {n_omega} escalones" if n_omega > 1 else "")
                              + f" en obs {at_0 + 1}"),
                    razon=(guion_rationale or
                           ("; ".join(esc.razones_para_subir)
                            if escalera_alt and esc.razones_para_subir
                            else "la lectura simple se sostiene: absorbe su "
                                 "fecha, no deja vecino y el modelo es adecuado")),
                    evidencia=" · ".join(
                        f"{p.nivel} AIC {p.aic:.2f}" for p in esc.peldanos
                        if p.estimado) if escalera_alt else "",
                    alternativas=escalera_alt,
                    decidido_por="analista+LLM")
            except Exception:
                pass
        # PERSISTIR ANTES DE REGISTRAR, y el orden no es cosmético: la
        # comprobación de la terna dentro de `_record_to_guion` (BUG-0092) mira
        # si el `.pre` y el `.out` EXISTEN en ese momento. Registrando primero,
        # la entrada quedaba con `out_path: null` y el aviso «(sin .pre, .out)»
        # aunque los dos ficheros acabaran en disco un instante después.
        #
        # El daño medido no es cosmético: en UEM_FOOD_SERV_DS la entrada
        # `m04_step1115` quedó marcada sin terna, el analista encadenó desde un
        # `.pre` MÁS ANTIGUO —el que el guion sí daba por bueno— y la
        # intervención de 11/2015 se perdió de la rama AR. Un registro que niega
        # sus artefactos dirige el encadenado hacia atrás (BUG-0109).
        #
        # `confirm_and_estimate` ya lo hacía en este orden; esta se quedó con el
        # inverso.

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

        # Y AHORA el guion, con la terna ya en disco.
        try:
            lam_fit = float(getattr(m_fit, "boxlam", 0.0) or 0.0)
            guion_note = _record_to_guion(
                model=m_fit, inp_path=output_path, lam=lam_fit,
                guion_path=guion_path or _derive_guion_path(output_path, m_fit),
                name=guion_name, decision=guion_decision,
                rationale=guion_rationale, problems_found=guion_problems,
                next_version=guion_next,
                figure_b64=diag.figure_b64,
                hist_b64=(diag.data or {}).get("hist_b64"),
                base_pre_path=inp_path,
            )
        except Exception as e:
            guion_note = f"*guion: no registrado ({type(e).__name__})*"

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

        _forma_txt = form.upper() + (f" ({n_omega} escalones en el nivel)"
                                     if n_omega > 1 else "")
        # Los ω recién estimados, leídos EN EL NIVEL. Es la primera vez que una
        # FLT de varios ω aparece en la sesión, así que es donde más falta hace
        # que nadie tenga que hacer la resta del convenio a mano.
        conv_txt = ""
        try:
            if n_omega > 1:
                _itvs = [i for i in (m_fit.interventions or [])
                         if i.type in ("step", "pulse", "impulse", "ramp")
                         and len(i.omega or []) > 1]
                if _itvs:
                    from art.ltf import operador_en_palabras
                    conv_txt = ("\n\n---\n\n"
                                + operador_en_palabras(
                                    list(_itvs[-1].omega),
                                    entrada=('impulso' if _itvs[-1].type in
                                             ('pulse', 'impulse', 'compimp')
                                             else 'escalon')))
        except Exception as _cv:
            _warn("lectura del operador en el nivel", _cv)

        text = envuelve_iteracion(
            nombre=os.path.splitext(os.path.basename(output_path))[0],
            # La ESPECIFICACIÓN de esta iteración es la forma de la intervención
            # y lo que la justifica: la escalera de Ockham y el operador leído
            # en el nivel.
            especificacion=(
                f"**Intervención {'REHECHA' if rehacer else 'añadida'}:** "
                f"{_forma_txt}  {date_note}"
                f"{context_str}" + _nota_rehacer + conv_txt + escalera_txt
                + aviso_rampa(m_fit)),
            ecuacion=eq_text,
            diagnosis=(diag.summary + "\n\n---\n" + diag.recommendation
                       + scan_section),
            reformulacion=_reformulacion_desde(diag, guion_next),
            extra=(f"*Modelo actualizado en: {output_path}{pre_note}*"
                   + (f"\n\n{guion_note}" if guion_note else "")
                   + _state_footer(
                       m_fit, inp_path=output_path, guion_note=guion_note,
                       guion_path_hint=guion_path
                       or _derive_guion_path(output_path, m_fit))),
        )

        # BUG-0113: mismo caso que el carril guiado — este sobre se compone a
        # mano (BUG-0094) y no pasa por `_result()`, asi que la ruta hay que
        # recogerla y decirla aqui.
        _ruta_fig = _escribe_fig(diag.figure_b64, "diagnosis")
        text = _con_nota_figura(text, _ruta_fig)
        items = [TextContent(type="text", text=text)]
        if diag.figure_b64:
            items.append(_imagen(diag.figure_b64, "suggest_intervention_form"))
        if scan_b64:
            items.append(_imagen(scan_b64, "suggest_intervention_form"))
        if include_histogram:
            hist_b64 = diag.data.get("hist_b64")
            if hist_b64:
                items.append(_imagen(hist_b64, "suggest_intervention_form"))
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
                con_figuras: bool = False,
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
                objetivo: _Objetivo = "univariante",
                modo: _Modo = "guiado") -> list:
    """
    ATAJO HEURÍSTICO — el pipeline de una llamada. NO es el modo autónomo.

    Runs ONE engine (pipeline.run_full): decides the spec, estimates, adds
    interventions for detected outliers and re-estimates until the diagnosis is
    clean or max_rounds.

      - Sin spec: la heurística `DefaultPolicy` decide λ, d, D, armónicos, p, q
        y la media. Es un auto-ARIMA del estilo de pmdarima, con las reglas de
        la escuela dentro — y NADA MÁS: no sobreparametriza, no mira Semana
        Santa, no pasa los contrastes formales ni reformula.
      - Con spec (lam/d/D/p/q/n_harmonics/estimate_mu/decision): se respeta lo
        fijado (ClaudePolicy) y la heurística completa el resto, con el ciclo
        de anómalos automático.

    **El modo AUTÓNOMO de art no es esta herramienta** (BUG-0180). En autónomo
    el LLM hace de analista y recorre los nodos del protocolo decidiendo cada
    uno; un autónomo que se reduce a una llamada aquí es un híbrido entre el
    guiado y un auto-ARIMA, que es lo peor de los dos. Úsala cuando el usuario
    pida expresamente un ajuste automático sin análisis, o como PROPUESTA
    inicial que luego se contrasta nodo a nodo.

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
    modo          : "guiado" (por defecto) | "autonomo". Con spec declarada y
                    modo guiado la salida termina en ⏸ para el analista humano;
                    con modo autónomo no para nunca (BUG-0181).
    guion_path    : (optional) path to guion.json — records the final model
    guion_name    : version name (e.g. "PC1"); auto-assigned if empty
    guion_decision: brief description of the model or pipeline result
    guion_rationale: justification for the spec
    """
    try:
        # Por las puertas de art no entra un objetivo que nadie eligió: la
        # política lo convertía en «univariante» en silencio (BUG-0183).
        try:
            objetivo = objetivo_declarado(objetivo)
        except ValueError as _exc_obj:
            return _err(str(_exc_obj))
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
        if decision:         overrides["decision"] = decision

        # EL CARRIL LO DECIDEN LAS DECISIONES, NO LOS DATOS — BUG-0179.
        #
        # Hasta aquí `overrides` sólo lleva DECISIONES de especificación, que es
        # lo que el docstring promete como disparador del carril guiado. El
        # dominio NO es una: es un dato sobre qué clase de serie es ésta, y
        # entra después, a propósito, para que declararlo no saque la llamada
        # del carril autónomo.
        #
        # Lo hacía. `domain` iba en el mismo diccionario y `guided =
        # bool(overrides)` lo contaba: declarar el dominio —un dato— volvía
        # «guiada» la llamada, la salida tomaba la forma de turno guiado y
        # terminaba en `FIN_DE_TURNO_GUIADO`. El asistente leía ⏸, paraba y
        # preguntaba: el carril autónomo dejaba de ser autónomo. La bifurcación
        # existía desde 12-ago (f8ee98e) y no se veía hasta que la salida se
        # unificó en el sobre de iteración (9cc69fe, 06-sep).
        guided = bool(overrides)

        # DECLARADO GANA A INFERIDO, y un valor que nadie reconoce NO gana
        # nada — BUG-0178. La guarda existía en `guided_identification` y no
        # aquí, que es por donde pasa el carril autónomo.
        try:
            dom_decl = dominio_declarado(domain)
        except ValueError as exc:
            return _err(str(exc))
        # BUG-0015: qué CLASE de serie es. Declarado gana a inferido del nombre.
        if dom_decl:         overrides["domain"] = dom_decl

        decision_policy = policy.ClaudePolicy(**overrides) if overrides else None

        # ── Run the pipeline (decisions + outlier loop) ────────────────────
        result = run_full(ts, output_path, max_rounds=max_rounds,
                          decision_policy=decision_policy, objetivo=objetivo)
        lam, d, D = result.lam, result.d, result.D
        m_fit, diag = result.final_model, result.final_diag

        # ── Reconstruct the rich text log from the structured rounds ──────
        # Dos preguntas distintas que antes compartían una variable. `guided`
        # dice si hay especificación declarada —y por tanto qué política usa el
        # motor—. Si la salida PARA o no depende de otra cosa: de si hay un
        # analista humano esperando. En el carril autónomo quien declara la spec
        # es el LLM haciendo de analista, y parar ahí es esperar a nadie
        # (BUG-0181).
        _mode = ("guiado (spec confirmada)" if (guided and modo == "guiado")
                 else ("autónomo (spec decidida)" if guided else "autónomo"))
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
                itv_labels = ", ".join(_etiqueta_itv(t) for t in rd.added[:5])
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
                        # Carril AUTÓNOMO: sólo la última ronda guarda figura.
                        # En guiado se guarda siempre — hay analista mirando.
                        figure_b64=(diag_desc.figure_b64 if es_ultima else None),
                        hist_b64=((diag_desc.data or {}).get("hist_b64")
                                  if es_ultima else None),
                    )
                except Exception as e:
                    guion_note = f"*guion: no registrado ({type(e).__name__})*"

        # EL SOBRE, también aquí: el proceso es el mismo y el guion es el
        # mismo, así que la salida es la misma. La única diferencia del carril
        # autónomo es que la FIGURA NO VIAJA (BUG-0094).
        _rutas = []
        try:
            from art.guion import load_guion
            _gp = guion_path or _derive_guion_path(output_path, m_fit)
            if os.path.exists(_gp):
                _raiz = os.path.dirname(_gp) or "."
                for _e in load_guion(_gp).entries:
                    for _campo in ("figure_path", "hist_path"):
                        _r = getattr(_e, _campo, None)
                        if _r:
                            _rutas.append(os.path.join(_raiz, _r))
        except Exception as _re:
            _warn("rutas de figuras para el sobre autónomo", _re)

        text = envuelve_iteracion(
            nombre=os.path.splitext(os.path.basename(output_path))[0],
            modo=_mode,
            especificacion="\n".join(log),
            ecuacion=eq_text,
            diagnosis=(diag_text + "\n\n---\n\n### Contrastes formales\n\n"
                       + formal_md),
            reformulacion=_reformulacion_desde(
                getattr(result, "final_diag", None) or type("_", (), {"data": {}})(),
                guion_next=""),
            rutas_figuras=_rutas if not con_figuras else None,
            extra=(f"*Modelo guardado en: {output_path}*"
                   + (f"\n\n{guion_note}" if guion_note else "")
                   + (_state_footer(
                       m_fit, inp_path=output_path, guion_note=guion_note,
                       guion_path_hint=guion_path
                       or _derive_guion_path(output_path, m_fit))
                      if m_fit is not None else "")),
        )

        items: list = [TextContent(type="text", text=text)]
        # Medido sobre las tres realizaciones del run 3 (483 llamadas): el 97.4%
        # de los bytes que salen del servidor son imágenes, y en un bucle
        # agéntico cada byte se reenvía en todos los turnos siguientes. En
        # autónomo nadie las mira. `guion_evidencia` las recupera si hacen falta.
        if con_figuras:
            for fig_b64 in round_figures:
                items.append(_imagen(fig_b64, "build_model"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: batch build (C2)
# ---------------------------------------------------------------------------

@mcp.tool()
def batch_build(inp_paths: list[str], output_dir: str,
                max_rounds: int = 5, run_meg: bool = False,
                objetivo: _Objetivo = "univariante") -> list:
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
        # Por las puertas de art no entra un objetivo que nadie eligió: la
        # política lo convertía en «univariante» en silencio (BUG-0183).
        try:
            objetivo = objetivo_declarado(objetivo)
        except ValueError as _exc_obj:
            return _err(str(_exc_obj))
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
                        items.append(_imagen(diag_desc.figure_b64, "batch_build"))

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
        _, m = _mirar(inp_path)

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
def verify_optimum(pre_path: str, output_inp: str, k: float = 1.0,
                   tol: float = 1e-5) -> list:
    """
    VERIFICA el óptimo de un `.pre` y saca errores típicos de un camino de verdad.

    Para cuando un modelo convergió en pocas iteraciones —porque arrancó cerca
    del óptimo, que es lo que el encadenado por `.pre` hace a propósito— y sus
    errores típicos se quedaron en la semilla del BFGS, √(2/n). Los valores salen
    bien y las SE mal, así que el fallo es invisible.

    **NO pongas las semillas a cero para arreglarlo.** Es la tentación evidente y
    es peligrosa por dos razones (BUG-0174):

    * desde cero el optimizador arranca **fuera de la cuenca** del óptimo
      conocido y puede caer en otra. Un óptimo distinto con ℓ mejor sería OTRO
      MODELO, no el mismo mejor estimado — y se adoptaría creyendo haberlo
      «verificado»;
    * y si se vuelve práctica, **destruye el convenio del `.pre`**: la cadena
      `.inp → .pre → .inp` sólo significa algo si cada eslabón arranca donde
      acabó el anterior.

    Esto perturba cada parámetro libre **una desviación típica** —`v ± k·SE`, con
    signos alternos— reestima, y **compara ℓ**. Tres desenlaces, y sólo uno
    autoriza a usar las SE nuevas:

        verificado   |Δℓ| ≤ tol — mismo óptimo; úsalas
        mejora       ℓ sube: el `.pre` NO era el óptimo. Hallazgo, no éxito
        no llegó     ℓ baja: la corrida en frío no alcanzó; no valen

    La perturbación es determinista: dos ejecuciones dan lo mismo. Un instrumento
    de verificación que no se puede repetir no verifica.

    Parameters
    ----------
    pre_path   : el `.pre` del modelo a verificar
    output_inp : dónde escribir el `.inp` reestimado en frío
    k          : tamaño de la perturbación, en desviaciones típicas (1.0)
    tol        : cuánto puede moverse ℓ y seguir siendo el mismo óptimo (1e-5)
    """
    try:
        from mcp.types import TextContent
        from art.pipeline import reestima_en_frio

        if not os.path.exists(pre_path):
            return _err(f"No existe el `.pre`: {pre_path}")
        m, inf = reestima_en_frio(pre_path, output_inp, k=k, tol=tol)

        v = inf["veredicto"]
        cab = {"verificado": "✓ **Mismo óptimo — las SE nuevas son las buenas**",
               "mejora": "⚠ **El `.pre` NO era el óptimo**",
               "no_llego": "⚠ **La corrida en frío no llegó al óptimo**"}[v]
        cola = {
            "verificado":
                "La reestimación perturbada converge al mismo punto, así que la "
                "covarianza sale de un camino de verdad y no de la semilla del "
                "BFGS. **Usa estas SE**, y el `.inp` escrito para reestimarlas "
                "cuando haga falta.",
            "mejora":
                "La corrida en frío encontró una verosimilitud MEJOR. Eso no "
                "valida nada: dice que el modelo guardado no estaba en su "
                "óptimo. Míralo antes de seguir — y no uses ninguna de las dos "
                "tablas de SE como si la cuestión estuviera zanjada.",
            "no_llego":
                "La corrida en frío se quedó por debajo. Sus SE no valen, y "
                "tampoco invalidan las del `.pre`: sólo dice que desde ahí no "
                "se alcanzó. Prueba con una perturbación menor (`k` más "
                "pequeño).",
        }[v]
        txt = (
            f"## Verificación del óptimo — {os.path.basename(pre_path)}\n\n"
            f"{cab}\n\n"
            f"| | `.pre` | en frío |\n|---|---|---|\n"
            f"| ℓ | {inf['loglik_pre']:.10f} | {inf['loglik_frio']:.10f} |\n"
            f"| iteraciones | {inf['niter_pre']} | {inf['niter_frio']} |\n"
            f"| SE en la semilla del BFGS | {inf['en_la_semilla_antes']} de "
            f"{inf['npar']} | {inf['en_la_semilla_despues']} de {inf['npar']} |\n\n"
            f"Δℓ = {inf['delta']:+.3e}  (tolerancia {inf['tol']:.0e}) · "
            f"perturbación de {inf['k']:g} desviación(es) típica(s)\n\n"
            f"{cola}\n\n"
            f"*Escrito en `{output_inp}`.*")
        return [TextContent(type="text", text=txt)]
    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def extend_sample(pre_path: str, source_path: str, output_inp: str,
                  column: str = "", sheet: str = "",
                  guion_path: str = "", guion_name: str = "",
                  guion_rationale: str = "") -> list:
    """
    EXTIENDE la muestra de un modelo: el mismo modelo, más observaciones.

    Es el paso que valida un modelo contra lo que vino después, y el que
    incorpora un episodio nuevo —un covid, una crisis— **sin rehacer la
    identificación**. Se parte del `.pre` del modelo y de la serie completa
    (la vieja MÁS lo nuevo), y se escribe el `.inp` extendido.

    CONSERVA TODO: deterministas con sus posiciones, ARMA regular y estacional,
    operadores de frecuencia fija, `ifadf`, μ, Box-Cox y el factor de reescala.
    Los valores estimados quedan como SEMILLAS, que es lo que un `.pre` es.

    **NO reestima.** Extender la muestra y reestimar son dos decisiones, y la
    segunda es tuya: después de esto, `confirm_and_estimate` sobre el `.inp` que
    escribe, o el nodo de intervención si lo nuevo trae sucesos.

    Se NIEGA en dos casos, y los dos son de método:

    * si la serie nueva **no empieza donde la del modelo** — extender por el
      principio desplaza la posición de todas las intervenciones y cada suceso
      quedaría en otra fecha;
    * si el **tramo común no coincide** — entonces no es esta serie extendida
      sino otra, y heredar una especificación ajustada sobre otros datos no
      significa nada.

    Antes de esto la única vía era editar el `.inp` a mano —el número de
    observaciones y el bloque de datos— con dos costes: equivocarse, y que lo
    editado a mano **no queda en el guion**, así que el recorrido perdía el
    punto donde la muestra cambió (BUG-0173).

    Parameters
    ----------
    pre_path    : el `.pre` del modelo que se extiende
    source_path : fichero con la serie COMPLETA (.csv/.xlsx), la vieja más lo nuevo
    output_inp  : dónde escribir el `.inp` extendido
    column      : columna a leer (vacío = la primera numérica)
    sheet       : hoja, para Excel
    guion_*     : registro del cambio de muestra, como en el resto de la suite
    """
    try:
        import pandas as pd
        from mcp.types import TextContent
        from art.pipeline import ErrorDeExtension, extiende_muestra

        if not os.path.exists(pre_path):
            return _err(f"No existe el `.pre`: {pre_path}")
        df = (pd.read_excel(source_path, sheet_name=sheet or 0)
              if source_path.lower().endswith((".xlsx", ".xls"))
              else pd.read_csv(source_path))
        num = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
        if not num:
            return _err("El fichero no tiene ninguna columna numérica.")
        col = column if (column and column in df.columns) else num[0]
        y = df[col].dropna().to_numpy(dtype=float)

        try:
            ts, m, n_add = extiende_muestra(pre_path, y, output_inp)
        except ErrorDeExtension as e:
            return [TextContent(type="text", text=(
                "⛔ **Eso no es extender esta serie.**\n\n" + str(e)))]

        _f = int(ts.freq or 1)
        y0, p0 = ts.start
        _o = p0 - 1 + ts.nobs - 1
        _fin = (f"{_o % _f + 1:02d}/{y0 + _o // _f}" if _f == 12 else
                f"Q{_o % _f + 1}/{y0 + _o // _f}" if _f == 4 else
                str(y0 + _o))
        n_itv = len([i for i in (m.interventions or [])
                     if i.type in ("pulse", "impulse", "step", "ramp")])

        txt = (
            f"## Muestra extendida — {ts.name or 'serie'}\n\n"
            f"**+{n_add} observaciones** → n = {ts.nobs}, hasta **{_fin}**.\n\n"
            f"Especificación conservada entera: {len(m.interventions or [])} "
            f"deterministas ({n_itv} de suceso), d={m.d}, D={m.D}, "
            f"λ={m.boxlam}, μ={'sí' if getattr(m, 'estimate_mu', False) else 'no'}"
            + (f", ifadf={list(m.ifadf)}" if any(m.ifadf or []) else "") + ".\n\n"
            f"*Escrito en `{output_inp}`. **No se ha reestimado**: los valores "
            f"del `.pre` quedan como semillas. Estima cuando decidas, con "
            f"`confirm_and_estimate`; y si lo nuevo trae sucesos, el nodo de "
            f"intervención va después.*")
        try:
            gp = guion_path or _derive_guion_path(output_inp, m)
            _record_node_to_guion(
                gp, nodo="muestra",
                decidido=f"muestra extendida +{n_add} obs → n={ts.nobs} ({_fin})",
                razon=(guion_rationale or
                       "validar el modelo contra lo que vino después"),
                evidencia=f"desde {os.path.basename(pre_path)}",
                decidido_por="analista")
        except Exception as _g:
            _warn("registro del cambio de muestra en el guion", _g)
        return [TextContent(type="text", text=txt)]
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
            # INFERIR DE VERDAD, O DECIR QUE NO SE PUDO — BUG-0169.
            #
            # `fue.TimeSeries.from_pandas` mira `idx.freqstr`, que es **None**
            # en cualquier índice PARSEADO (pandas sólo lo rellena cuando el
            # índice se construye con una frecuencia, p. ej. `date_range`). Sin
            # él caía a `freq = 1`, ANUAL, en silencio — y esta función remataba
            # afirmando «Fechas inferidas del índice», que era falso: no las
            # había mirado.
            #
            # Medido sobre `ES_CPI.csv`, con índice 2002-01, 2002-02, …:
            #     «Período: 2002 → 2294  (n=293, anual)»
            #
            # Es la PRIMERA llamada de cualquier análisis, y de `freq` cuelga
            # todo: la estacionalidad, los armónicos, los retardos de la Q, el
            # MEG, las fechas de toda intervención. No es un análisis peor: es
            # otro, sobre una serie que no existe.
            _inf = 0
            if freq <= 0:
                try:
                    _fs = pd.infer_freq(idx)
                except Exception:
                    _fs = None
                if _fs:
                    _u = str(_fs).upper()
                    _inf = (12 if _u.startswith(("M", "MS", "BM")) else
                            4 if _u.startswith(("Q", "BQ")) else
                            1 if _u.startswith(("A", "Y", "BA", "BY")) else 0)
                if not _inf and len(idx) > 2:
                    # el espaciado MODAL en días: 28-31 mensual, 89-92
                    # trimestral, 365-366 anual. `infer_freq` exige regularidad
                    # perfecta y una serie real puede no tenerla.
                    import numpy as _np
                    _d = _np.diff(_np.asarray(idx.view("int64"))) / 86_400_000_000_000
                    _md = float(_np.median(_d))
                    _inf = (12 if 27.0 <= _md <= 32.0 else
                            4 if 88.0 <= _md <= 93.0 else
                            1 if 360.0 <= _md <= 370.0 else 0)
                if not _inf:
                    return _err(
                        "El índice tiene fechas pero **no he sabido deducir la "
                        "frecuencia** de su espaciado.\n\n"
                        "Decláralo: `freq` (1 anual / 4 trimestral / 12 "
                        "mensual), `start_year` y `start_period`.\n\n"
                        "*No se supone anual: de `freq` cuelgan la "
                        "estacionalidad, los armónicos y las fechas de toda "
                        "intervención, así que adivinar mal es peor que "
                        "preguntar (BUG-0169).*")
            _f_usar = freq if freq > 0 else _inf
            ts = fue.TimeSeries.from_pandas(series.rename(name), freq=_f_usar)
            ts = fue.TimeSeries(ts.data, freq=_f_usar, start=ts.start, name=name)
            date_note = ("Fechas y frecuencia DEDUCIDAS del índice."
                         if freq <= 0 else
                         "Fechas del índice; frecuencia declarada.")
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

    LEE EL FICHERO, no lo vuelve a fabricar (BUG-0091). Antes reestimaba y
    generaba el informe otra vez, con dos consecuencias: si se le pasaba un
    `.pre` devolvía un informe con las desviaciones típicas hasta un **247%**
    desviadas del `.out` que estaba en el mismo directorio, y aun con un `.inp`
    devolvía una reestimación en vez del registro.

    Y el registro importa: **la covarianza no es una propiedad del óptimo, es un
    subproducto del camino del optimizador**, así que un fichero que sólo guarda
    el óptimo —el `.pre`— no puede llevarla. El `.out` es el único sitio donde
    las desviaciones típicas quedan tal como se calcularon.

    Si no hay `.out`, estima **y lo dice**.

    Parameters
    ----------
    inp_path : ruta del `.inp`, `.pre` o `.out`. La terna comparte basename, así
               que se busca el `.out` hermano.
    """
    try:
        from mcp.types import TextContent
        from art.outfile import hay_out, lee_out

        if hay_out(inp_path):
            r = lee_out(inp_path)
            cab = (f"*Leído de `{os.path.basename(r.ruta)}` — es el registro de "
                   f"la estimación, no una reestimación.*\n\n")
            return [TextContent(type="text",
                                text=cab + f"```\n{r.texto}\n```")]

        ts, m = _load_fitted(inp_path)
        out_text = m.write_out()
        aviso = (f"⚠ *No hay `.out` para `{os.path.basename(inp_path)}`, así que "
                 f"este informe se ha REESTIMADO ahora — no es el registro de la "
                 f"estimación original.*")
        try:
            from art.pipeline import aviso_se_no_fiable
            aviso += aviso_se_no_fiable(m)
        except Exception as _e:               # BUG-0160: no se calla
            _warn("no se pudo componer el aviso del método en get_out_report", _e)
        return [TextContent(type="text",
                            text=aviso + f"\n\n```\n{out_text}\n```")]
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: guion_evidencia — la evidencia de un nodo, SIN reestimar
# ---------------------------------------------------------------------------

@mcp.tool()
def guion_evidencia(guion_path: str, version: int = 0,
                    con_figura: bool = True) -> list:
    """La EVIDENCIA de un nodo del guion: ecuación, diagnosis y figuras.

    Para volver a un camino seguro hacen falta dos cosas: el MAPA —quién
    desciende de quién, qué se abandonó y por qué, que lo da `guion_map`— y la
    EVIDENCIA del nodo al que se vuelve. Esto es lo segundo.

    **No reestima nada.** Y ésa es toda la gracia: reestimar dirigido por el LLM
    cuesta llamadas, tokens y decisiones intermedias, y no hace falta porque el
    convenio de ficheros ya guarda lo necesario:

        el `.out`      la ecuación CON sus errores típicos, exactos. La
                       covarianza es un subproducto del camino del optimizador,
                       así que no se puede recuperar de ningún otro sitio
                       (BUG-0090, BUG-0091).
        el guion       la diagnosis registrada: Q con sus retardos y p-valores,
                       Jarque-Bera, σ̂ₐ, anómalos, y con qué versión del
                       instrumento se calculó.
        `figs/`        residuos + ACF/PACF, y el histograma.

    Si alguna pieza no está, lo DICE en vez de fabricarla en silencio; sólo la
    figura se regenera —desde el `.inp`, y avisando— porque depende de los
    valores y no de la covarianza.

    Parameters
    ----------
    guion_path  : ruta del guion.json
    version     : versión a mirar. 0 = la última con modelo.
    con_figura  : False si sólo interesa el texto (más barato).
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.guion import load_guion

        g = load_guion(os.path.expanduser(guion_path))
        modelos = [e for e in g.entries if not e.is_node]
        if not modelos:
            return _err("el guion no tiene ningún modelo todavía.")
        if version:
            e = next((x for x in g.entries if x.version == int(version)), None)
            if e is None:
                return _err(f"v{version} no está en el guion. Hay: "
                            + ", ".join(f"v{x.version}" for x in g.entries))
            if e.is_node:
                return _err(f"v{version} es un nodo de DECISIÓN, no un modelo: "
                            f"no tiene ecuación ni diagnosis. Su contenido está "
                            f"en `guion_map`.")
        else:
            e = modelos[-1]

        raiz = os.path.dirname(os.path.expanduser(guion_path)) or "."
        L = [f"## Evidencia de `{e.name}` (v{e.version}) — {g.series}", ""]
        if e.parent is not None:
            L.append(f"*Desciende de v{e.parent}.*")
        if e.timestamp:
            L.append(f"*Registrado {e.timestamp}"
                     + (f" con `{e.instrumento}`" if e.instrumento else "") + ".*")
        L.append("")

        # ── la ecuación, LEÍDA del .out ──
        ruta_out = e.out_path or (os.path.splitext(e.inp_path or "")[0] + ".out"
                                  if e.inp_path else "")
        if ruta_out and os.path.exists(ruta_out):
            from art.outfile import lee_out
            r = lee_out(ruta_out)
            L += ["### Parámetros, del registro de la estimación", "",
                  f"*Leídos de `{os.path.basename(ruta_out)}` — no se ha "
                  f"reestimado nada, así que estos errores típicos son "
                  f"exactamente los que se calcularon.*", "", "```"]
            for p_ in r.parametros:
                L.append(f"  [{p_.indice:2d}] {p_.valor:+12.6f}  "
                         f"({p_.se:.6f})   t={p_.t:+7.3f}   {p_.bloque}")
            if r.loglik is not None:
                L.append(f"\n  ℓ = {r.loglik:.4f}"
                         + (f"   σ̂ₐ = {r.sigma:.4f}" if r.sigma else "")
                         + (f"   n = {r.nobs}" if r.nobs else "")
                         + (f"   iter = {r.iteraciones}" if r.iteraciones else ""))
            L += ["```", ""]
        else:
            L += ["### Parámetros", "",
                  f"⚠ **No hay `.out` para este nodo**, así que los errores "
                  f"típicos no se pueden leer. La covarianza es un subproducto "
                  f"del camino del optimizador y no se recupera del `.pre`: "
                  f"habría que reestimar desde `"
                  + (os.path.basename(e.inp_path) if e.inp_path else "?")
                  + "` con `estimate_and_diagnose`.", ""]

        # ── la ecuación esquemática que el guion sí guarda ──
        if e.equation:
            L += ["**Forma:** `" + e.equation + "`", ""]

        # ── la diagnosis REGISTRADA ──
        st = e.stats
        if st is not None:
            L += ["### Diagnosis registrada", ""]
            fila = [f"σ̂ₐ = {st.sigma_a:.4f}", f"ℓ = {st.loglik:.4f}"]
            if st.aic is not None:
                fila.append(f"AIC = {st.aic:.2f}")
            if getattr(st, "refactor", None):
                fila.append(f"escala ×{st.refactor:g}")
            L.append("  ·  ".join(fila))
            if st.q_lags and st.q_pvalues:
                qs = "  ".join(f"Q({l})={p:.4f}"
                               for l, p in zip(st.q_lags, st.q_pvalues))
                L.append(f"\n- **Ruido blanco:** {qs}"
                         + (f"   (g.l. = retardos − {st.npar} ARMA libres)"
                            if st.npar is not None else ""))
            if st.jb_pvalue is not None:
                L.append(f"- **Normalidad:** JB p={st.jb_pvalue:.4f}")
            if st.n_extreme:
                ext = ", ".join(f"{x.get('date', x.get('obs'))} (z={x['z']:+.2f})"
                                for x in (st.extreme or [])[:6])
                L.append(f"- **{st.n_extreme} anómalo(s):** {ext}")
            L.append("")

        # ── lo que se decidió aquí ──
        for etiqueta, valor in (("Decisión", e.decision),
                                ("Razón", e.rationale),
                                ("Problemas", e.problems_found),
                                ("Siguiente", e.next_version)):
            if valor:
                L.append(f"- **{etiqueta}:** {valor}")
        # `exploring` es el estado normal y no dice nada; los otros dos sí.
        if e.status in ("adopted", "dead-end"):
            L.append(f"- **Estado:** "
                     + ("✓ adoptada" if e.status == "adopted"
                        else "✗ callejón sin salida")
                     + (f" — {e.why_abandoned}" if e.why_abandoned else ""))
        L.append("")

        # ── las figuras ──
        imgs = []
        if con_figura:
            import base64 as _b64
            faltan = []
            for campo, etq in (("figure_path", "residuos + ACF/PACF"),
                               ("hist_path", "histograma")):
                rel = getattr(e, campo, None)
                ruta = os.path.join(raiz, rel) if rel else ""
                if ruta and os.path.exists(ruta):
                    with open(ruta, "rb") as fh:
                        imgs.append(_b64.b64encode(fh.read()).decode())
                    L.append(f"*Figura ({etq}): `{ruta}`*")
                else:
                    faltan.append(etq)
            if faltan and e.inp_path and os.path.exists(e.inp_path):
                # Regenerar SÍ vale para esto: la figura depende de los VALORES,
                # y no promete errores típicos. Por eso se usa `mirar`.
                try:
                    from art.describe import describe_diagnosis
                    from art.pipeline import mirar
                    _, m = mirar(e.inp_path)
                    d = describe_diagnosis(m)
                    if "residuos" in " ".join(faltan) and d.figure_b64:
                        imgs.append(d.figure_b64)
                    if "histograma" in faltan and (d.data or {}).get("hist_b64"):
                        imgs.append(d.data["hist_b64"])
                    L.append(f"*({', '.join(faltan)}: no estaba guardado, se ha "
                             f"REGENERADO desde `{os.path.basename(e.inp_path)}`. "
                             f"Es la misma figura —depende de los valores— pero "
                             f"no es la que se guardó.)*")
                except Exception as _fe:
                    L.append(f"*({', '.join(faltan)}: no guardado y no "
                             f"regenerable: {type(_fe).__name__}: {_fe})*")
            elif faltan:
                L.append(f"*({', '.join(faltan)}: no guardado, y sin `.inp` para "
                         f"regenerarlo.)*")

        L += ["", "---", "",
              f"**El mapa:** `guion_map(\"{guion_path}\", version={e.version})` "
              f"— de dónde viene, qué se abandonó y cuál es el ancestro seguro."]

        items = [TextContent(type="text", text="\n".join(L))]
        for b in imgs:
            items.append(_imagen(b, "guion_evidencia"))
        return items
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    # BUG-0111. Dejar constancia de que se corre COMO SERVIDOR es lo que
    # permite a `_show_fig` no abrir el visor aquí y sí abrirlo cuando el
    # módulo se usa como biblioteca. Va antes de `mcp.run()`, que no devuelve.
    global _BAJO_SERVIDOR
    _BAJO_SERVIDOR = True
    mcp.run()


if __name__ == "__main__":
    main()
