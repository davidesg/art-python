# art-python — TODO

## Arquitectura

- [ ] **Revisión de arquitectura** — [`docs/ARCHITECTURE_REVIEW.md`](docs/ARCHITECTURE_REVIEW.md),
      escrita 2026-08-27 tras la réplica del TFM de Bolivia (tres series, decenas
      de modelos, seis defectos encontrados y arreglados).
      Tesis: **la metodología es sólida y los instrumentos son excelentes; lo que
      falla es todo lo que hace el método NAVEGABLE**, y eso es casi invisible
      para un analista humano y letal para un LLM.
      Medido: 35 herramientas MCP, **28 huérfanas** (nada las sugiere jamás), **8
      aristas** de paso siguiente en todo el servidor; el guion es una lista plana
      **sin campo de parentesco**, así que no puede representar una bifurcación ni
      un callejón sin salida; y sólo `guided_identification` dice dónde estás, y
      sólo dentro de la identificación.
      Seis propuestas por orden de valor, de las cuales **cinco son cableado,
      estado o texto** — el problema no es que falten herramientas, sobran sin
      conectar.

## Funcionalidad pendiente

- [ ] **El carril GUIADO tampoco registra todo lo que estima** — la otra mitad de
      BUG-0032, abierta 2026-08-27. Sólo `confirm_and_estimate` y `build_model`
      llaman a `_record_to_guion` (4 llamadas en todo el servidor); el resto de
      caminos que producen un modelo estimado no dejan línea.
      Medido sobre la réplica del TFM: ITCER tiene 3 modelos en disco y 2 en el
      guion; **RATIO tiene 5 y 2**, y los tres que faltan (m20, m30, m31) son
      justo donde se deciden las intervenciones — es decir, donde diverge del
      carril autónomo, que es la pregunta que el guion existe para contestar.
      El arreglo no es recorrer una lista como en BUG-0032: hay que decidir qué
      herramientas cuentan como «producir un modelo» y cuáles son sólo mirar, y
      cablear las primeras. `estimate_and_diagnose` es la primera candidata (le
      falta también el pie de estado).


- [ ] **El pie de estado debe estampar QUÉ BUILD está sirviendo el servidor** —
      abierto 2026-08-27, y lo abrió un episodio que costó tres corridas.
      Se arreglaron BUG-0030 y BUG-0031 en `src/`, la batería pasó en verde, y el
      servidor MCP siguió sirviendo el código anterior: `art-mcp` había arrancado
      dos días antes y Python fija los módulos al importar. Las corridas
      autónomas de la réplica salieron con la colocación vieja de las
      intervenciones (Q3/2008 en vez de Q4/2008) y **nada en la salida lo
      delataba** — el pie de estado, el `.inp` escrito y el guion decían todos lo
      mismo, con convicción.
      Lo que lo hizo visible fue comparar contra el carril guiado y bajar a leer
      `itv.at` a mano. Eso no escala y no es reproducible.
      Basta con una línea: versión del paquete + hash git corto (o mtime del
      módulo más reciente de `src/art/`) en `_state_footer`, y el mismo dato en
      el guion de cada versión. Un analista que ve un número que no coincide con
      su árbol reconecta el servidor en cinco segundos.
      Corolario, más incómodo: **un guion escrito por un servidor obsoleto es un
      registro falso**, no meramente viejo. Los dos guiones de `auto/` de la
      réplica hubo que borrarlos porque describían modelos que ya no existían en
      disco. El guion es el registro científico; si puede mentir sobre qué código
      lo produjo, el sello de build no es un adorno.


- [ ] **Intervenciones como funciones de transferencia ω(B)/δ(B)** — ver
      [`docs/TODO-interventions.md`](docs/TODO-interventions.md).
      `fue` y el formato `.inp`/`.pre` las soportan por completo; ART sólo llega a
      un ω escalar (`mcp_server.py:2841` fija `omega=[0.0]`). Seis puntos, con la
      identificación de la forma (`intervention_response`) por delante de la
      estimación. Abierto 2026-08-26 en la réplica del TFM de Bolivia, sobre el
      episodio 2008:4–2009:2 de `ln ITCER`.

- [ ] **El motor de identificación de (p,q) sólo compara FORMAS** — ver
      [`docs/TODO-identification.md`](docs/TODO-identification.md).
      No es un defecto: los rasgos se extraen bien y la ambigüedad se declara.
      El hueco es que los prefiltros no miran magnitudes, y hay una cota clásica
      —`|rho_1| <= cos(pi/(q+2))`— que discrimina justo donde la forma no puede.
      Usarla como desempate y aviso, nunca como rechazo duro. Abierto 2026-08-26
      sobre `ln PGAS`, donde ART pone un MA(1) primero y el AR(2) correcto cuarto.

## Bugs conocidos

- [x] **ART no estima correctamente series de frecuencia ANUAL (freq=1)**
      **(RESUELTO 2026-08-12 — ver `bugs/BUG-0018`).** Y el diagnóstico cambió al
      medirlo: de los tres defectos descritos abajo, los TRES estaban ya
      arreglados, y lo que bloqueaba de verdad era un cuarto sin anotar —
      `detect_seasonality` dividía por `num_harmonics = s-1`, que en anual es
      cero, y la excepción se llevaba `run_full` antes de estimar nada. Más
      `_write_bare_inp`, que conservaba la cabecera antigua mientras `_write_inp`
      ya la escribía bien. **Lección: este defecto vivió un mes aquí en vez de en
      el registro, y en ese mes dejó de ser cierto sin que nadie lo notara.** El
      texto original se conserva debajo como registro de lo que se creía.

      (histórico) descripción original:
      descubierto 2026-07-08 revisando series anuales de precipitación (Ginebra,
      días, n=248, 1768-2015; proyecto "Joseph's Cycles"). El motor `fue` estima
      bien — el fallo está en la capa ART (construcción del modelo y del `.inp`) y
      en pyfug (gráfico de diagnosis). Como TODA serie anual es D=0, estos tres
      defectos afectan a CUALQUIER estimación anual, tanto en modo guiado
      (`confirm_and_estimate`) como autónomo (`build_model` → ambos vía
      `_make_model` / `_write_inp`).

      **(1) Determinista `alter`=(−1)ᵗ espurio — `src/art/pipeline.py:503`.** En el
      bloque `D==0` de `_make_model`, la línea 497 pone correctamente `max_pairs=0`
      para freq=1 (ningún par cos/sin), pero la línea 503 añade INCONDICIONALMENTE
      `fue.Intervention("alter", …)` (armónico de Nyquist f=s/2). En una serie anual
      (s=1) no hay Nyquist estacional: `alter`=(−1)ᵗ es una oscilación bienal
      determinista libre que no debería existir. Efecto: absorbe señal de periodo 2,
      distorsiona μ y el AR, y produce ajustes degenerados (observado: un AR(14)
      anual con logL=−2202, PEOR que su submodelo AR(7) logL=−1058 — imposible entre
      modelos anidados salvo no convergencia). Fix propuesto: envolver el bloque de
      deterministas estacionales (líneas 500-503, o al menos el append de `alter`)
      en `if freq >= 2:`. Test de regresión: estimar un ARMA anual y comprobar que
      `m.interventions` NO contiene ningún `alter`, y que logL(AR(p+k)) ≥ logL(AR(p)).

      **(2) Cabecera `.inp` mal escrita para anual — `src/art/pipeline.py:150`.** En
      `_write_inp`, la rama `else` (freq=1) escribe
      `f" {n}  {beg_year} {beg_year} {name}"`, repitiendo el año en el campo del
      periodo inicial (p.ej. `248  1768 1768 GE` en vez de `248  1 1768 GE`). Debe
      ser `f" {n}  1 {beg_year} {name}"` (periodo inicial = 1 en anual, coherente con
      `beg_period` de la línea 111). Fix: sustituir `{beg_year} {beg_year}` por
      `1 {beg_year}`. Test: round-trip write→load de una serie anual conserva
      `start` y `nobs`.

      **(3) `UnboundLocalError: x_pad` en el gráfico anual — pyfug
      `pyfug/graphics/combined.py:167`.** En `plot_combined`, `x_pad` solo se define
      dentro de `if f > 1:` (asignado en la línea 146); para `f==1` (anual) se entra
      en el `else` (línea 155) sin definirla, y la línea 167
      `ax_s.set_xlim(xs[0] - x_pad, …)` la usa → crash. Bloquea `describe_diagnosis`
      y, por tanto, `estimate_and_diagnose` y `confirm_and_estimate` (que la llaman
      tras estimar). Está en pyfug (no en fue ni en art-python), pero rompe ART; se
      registra aquí como se hizo con el fix de nlags. Fix: definir `x_pad` (p.ej.
      `x_pad = 0.3 / f`) también en la rama `else`. Test de regresión: caso anual en
      `tests/test_golden_pipeline.py` que ejecute la diagnosis sin crash (hermano de
      `test_diagnosis_short_series_no_crash`).

      Workaround temporal: construir el `.inp` a mano (cabecera correcta, sin
      `alter`) y estimar vía `model_equation_display` / `ar_factorization` (re-ajustan
      internamente y no invocan el gráfico que rompe).

- [x] **MEG ahora evalúa la frecuencia de Nyquist (bienal, f=s/2)** (RESUELTO):
      `meg` contrasta `f=1…s/2` (6 en mensual), incluyendo el Nyquist, como la
      tesis (chap2.4) y Abraham & Box (1978, Tabla A1). El factor de Nyquist es
      de primer orden `(1+B)`, así que la rama Nyquist: elimina el término
      determinista `alter`=(−1)ᵗ, activa `ifadf[s/2]=1` (el AR_f (1+B)), añade un
      **MA regular de primer orden** testigo (1+θB, preest −0.9, free) — no un
      FixedFreqFactor de 2º orden — y aplica `_dcd_nyquist_ma` (DCD con null θ=−1).
      Sin cambios en el motor (fue ya estima MA regular e ifadf en Nyquist).
      Verificado: PC6 da determinista en f=6 (testigo ≈ −0.99, LR≈0.06).
      Tests: `test_meg_nyquist_chile_pc6_deterministic`, `test_meg_all_harmonics`
      (5→6). Ref: Abraham-Box Tabla A1
      (`literature/Abraham-DeterministicForecastAdaptiveTimeDependent-1978.pdf`).

- [x] **nlags en series cortas** (RESUELTO): pyfug `plot_combined` pedía
      `nlags = 3·(f+1)` (convención J-T) y solo capaba a `n−1`, pero statsmodels
      `pacf` exige `nlags < n/2` → ValueError con muestras cortas (n=72 mensual).
      Fix en pyfug: `plot_combined` capa `nlags = min(…, n//2−1)` (ambos paneles
      consistentes, convención preservada cuando n>6·(f+1)) y `statistics.pacf`
      capa defensivamente a `len//2−1`. Test de regresión:
      `tests/test_golden_pipeline.py::test_diagnosis_short_series_no_crash`.

## El pipeline autónomo tiene documento propio (ago-2026)

**Ver `docs/AUTONOMOUS_PIPELINE.md`.** No se trabaja aquí: es tarea grande, exige
pensar la arquitectura, y el orden decidido es **primero dejar sólido el camino
guiado y después depurar el autónomo**, que es la joya de la corona.

Resumen de por qué necesita documento aparte, para quien no lo abra:

- Sus fallos no son números mal, son **decisiones que localmente parecen
  razonables** y que interactúan. Cuatro de los defectos cerrados en agosto de
  2026 (BUG-0013, 0015, 0016 y el de series anuales) eran invisibles sobre
  cualquier modelo aislado y sólo aparecieron corriendo la misma regla sobre una
  familia de series con respuesta conocida.
- Hoy entrega la **especificación inicial** y para. Medido sobre los IPC de Chile
  y Colombia (I(2), tesis): entrega d=1 con estacionalidad toda determinista,
  cuando los diecisiete modelos de la tesis son d=2 y varios llevan `ifadf`
  activo. En Chile el modelo entregado además no es adecuado — Q falla en 6, 12,
  24 y 36, los retardos estacionales.
- Y hay un defecto de reporte concreto y barato: **`dcd_overdiff_regular` no
  llega al informe de `build_model`**, que sólo formatea `dcd()` y `meg()`. El
  LR=18.235 de Chile —«considera d+1», la señal más fuerte del análisis— no se
  produce en el camino autónomo. El MEG sí se muestra, así que de los dos
  contrastes que contradicen la especificación entregada, uno se ve y el otro no.
- Cerrar el bucle no es aplicar el veredicto: **un contraste formal sobre un
  modelo inadecuado no es un contraste**, y el modelo de Chile no lo es. La
  circularidad —el modelo puede ser inadecuado *por* aquello a lo que el
  contraste apunta— es el problema de diseño, no un parche.

El documento lista los riesgos de explosión (escalada de `d`, activación de
`ifadf` en frecuencias que la muestra no sostiene, interacción entre decisiones,
el bucle de anómalos persiguiendo estructura, no terminación, divergencia
silenciosa respecto al guiado), las cinco preguntas de arquitectura que hay que
responder antes de escribir código, y qué significa exactamente «el guiado está
sólido» como puerta para volver.

---

## PRIORIDAD — Arquitectura asistente/motor de los tres pares (ago-2026)

**Estado:** propuesta escrita (`docs/ASSISTANT_LAYER_PROPOSAL.md`), inventario de
símbolos medido, nada implementado. Es la deuda arquitectónica más importante de
la suite y la que una revisión externa de los tres servidores MCP no vio
(`~/Dropbox/SRC/atws/atsw-suite/RESPUESTA_REVISION_2026-08-12.md` §5.1 y §7).

### El problema, medido

Tres pares asistente↔motor, y solo uno está bien repartido:

| Asistente | Motor | ¿Paquete propio? | Símbolos privados que cruzan |
|---|---|---|---|
| `art` | `fue`/`fuf` | **sí** (`art-tseries`) | — (pero ART importa 3 privadas de `fue.plots`) |
| `mtram` | `drtran` | no, vive dentro | 3 de 33 |
| `sima` | `drvarma` | no, vive dentro | 6 de 10 |

Coste ya pagado: `drtran` fue 0.2.2 → 0.2.3 → 0.2.4 por documentación y un filtro
de avisos, y los usuarios movieron tres veces su motor de estimación por cambios
que no lo tocaron. Y `drtran[mcp]` arrastra matplotlib y jinja2 a un motor de
estimación exacta.

### La regla que decide qué va a cada lado

No es "presentación frente a cómputo", que deja casos ambiguos:

> **Todo lo que el modelo lee pertenece al asistente. El motor entrega números y
> no argumenta.**

Instrucciones, docstrings, `TOOLS.md`, la ecuación renderizada, los argumentos a
favor y en contra: asistente. La función que devuelve los números de esa tabla:
motor. Corolario: **el motor lleva sus reservas como DATO**, no como prosa —
`ifault`/`termcode`, `delta_warnings`, el hueco de optimalidad de la puerta
diagonal ya lo hacen en `drtran`; generalizarlo.

### Consistencia del patrón, no del tamaño

El peso del criterio depende del método y los tres métodos son distintos:

- **`art`/`fue`** — el juicio es denso y está en CADA nodo (λ, d, D por
  frecuencia, armónicos, órdenes, intervenciones, media) y es iterativo. Y `art`
  está **aguas arriba**: `sima` la invoca para la siembra univariante y `mtram`
  consume los `.pre` que `art`/`fue` producen. Un defecto de política en `art` se
  propaga a la suite entera; ninguno de los otros dos tiene esa propiedad. Es a la
  vez el más complejo y el más crítico, y su reparto es el patrón a replicar.
- **`mtram`/`drtran`** — el juicio se concentra en pocas decisiones (coincidencia
  de operadores, `(b,r,s)` desde la CCF preblanqueada, la puerta diagonal). Es
  coherente que su capa de asistente sea menor, y ya está casi lista (30/33).
- **`sima`/`drvarma`** — el juicio (orden de Cholesky, desestacionalizar,
  `(p,q)` desde CCM/Tiao-Box) está MENOS guiado por la evidencia que el
  univariante, no más. Que tenga 53 líneas de instrucciones y docstrings de 412
  caracteres de media (frente a 963 de `art`, `diagnose` en 116) es el reparto
  invertido.

### El orden — y no es "separar primero"

- [ ] **(1) `<motor>/assistant/`**: subir la capa de criterio fuera de
      `mcp_server.py` a su propio subpaquete, espejo de `describe.py`/`policy.py`.
      Sin cambio de empaquetado todavía. Ahí van `report_fit`, el dibujo de
      paneles, el renderizado de ecuaciones y `_what_the_transfer_bought`.
- [ ] **(2) Declarar la API**: las promociones entran en `__all__` con docstring
      de símbolo público. `drtran`: `common_window`, `delta_operator`.
      `drvarma`: `deseasonalize_raw`, `ccf`, `qccf`, `irf_fevd_bands`.
- [ ] **(3) Partir las baterías**: hoy el servidor viaja con el motor.
- [ ] **(4) Entonces `mtram-tseries` y `sima-tseries`** — mecánico a esas alturas.

Hacer (4) antes que (2) publica un paquete cuya dependencia son internos no
declarados, y deja dos salidas: promoverlos igual, o clavar `mtram-tseries==X` a
`drtran==X` — que devuelve el acoplamiento por la puerta principal y compra un
paquete que mantener a cambio de nada.

### Por dónde empezar: por `sima`, no por el más importante

Nadie ha trabajado en él, sus docstrings son los más delgados y medibles, y
construir el patrón ahí cuesta lo menos y enseña lo más antes de tocar `mtram`,
que está en uso diario. **`art` no necesita separación —ya la tiene—: necesita lo
contrario**, cerrar su único leak y estrenar la disciplina de tests de asistente:

- [ ] **Cerrar el leak de `Description.recommendation`** (`ARCHITECTURE.md:104`):
      calcula un veredicto con heurísticas cableadas EN PARALELO al modelo. Dos
      jueces que pueden contradecirse y que anclan al analista antes de que
      ninguno haya razonado. Debe emitir **evidencia + el menú de decisiones con
      argumentos a favor y en contra**, y dejar el veredicto al modelo y al
      analista. Es lo único de `art` que NO hay que copiar a los otros dos.
- [ ] **Tests de asistente**, que son de otra clase que los del motor: comprueban
      lo que el servidor DICE. Ya hay ejemplos reales: que `estimate` anuncie un
      cast despachado, que `check_operators` avise en desajuste y calle en
      coincidencia, que toda herramienta esté registrada.

### La pieza que falta en los tres: el contrato `.pre` no tiene dueño

- [ ] **Prueba de conformidad `.pre` compartida.** El contrato cruza fronteras de
      paquete (el `.pre` de `fue` alimenta a `drtran`; `art` siembra a `sima`) y no
      vive en ninguno: se re-explica en las instrucciones de cada servidor y no hay
      una sola prueba común. **BUG-0014 es la factura**: el mecanismo para encadenar
      existía (`base_pre_path`), no estaba enrutado en ninguna parte, y la media
      estimada se tiraba en cada peldaño. El invariante ya está escrito en prosa en
      las instrucciones de `mtram` ("corre fue sobre un `.pre` y los números no se
      mueven"); falta que sea código que los tres importen y ejecuten sobre sus
      propios artefactos. Un contrato que nadie posee es un contrato que nadie prueba.

---

## Series I(0) con tendencia determinista suave — anotado, sin tocar (ago-2026)

Salió al calibrar el criterio de tendencia de BUG-0016 y **se decidió no hacer
nada por ahora**, pero conviene que quede escrito porque el caso es real y está
medido.

Las dos series anuales de precipitación de `~/Dropbox/Cycles` son I(0) y sirven
de control en el lado «la regla no debe dispararse». Pero **tienen tendencia
determinista**, suave y real:

| serie | ventana | pendiente | t (HAC) | R² de una recta |
|---|---|---|---|---|
| Ginebra, días con precipitación | 1768–2015 | +7.25 días/siglo (+5.8 % de la media) | 3.37 | 0.076 |
| Zúrich, mm | 1708–2015 | +53.3 mm/siglo (+4.9 %) | 2.20 | 0.035 |

Ginebra pasa de 121 días de media en los primeros 50 años a 135.6 en los
últimos. Es señal climática, no ruido.

**Hoy ART las modela con d=0 y sin término de tendencia, así que esa deriva queda
sin modelar.** Es lo correcto frente a la alternativa mala —diferenciar
sobrediferenciaría una serie estacionaria e inyectaría una raíz MA en −1—, pero
no es lo correcto en absoluto: una serie estacionaria alrededor de una tendencia
determinista se modela con un regresor `trend`, que **fue ya soporta** (el tipo
`trend` está en `_write_inp`).

Opciones cuando se retome, en orden de intromisión:

- [ ] Avisar en la diagnosis cuando haya pendiente significativa sin modelar, con
      las dos salidas y sus argumentos, y que decida el analista.
- [ ] Sugerir el determinista `trend` sin aplicarlo.
- [ ] Nada automático. La regla de tendencia de `decide_d` mide DOMINANCIA (R² >
      0.5) justo para no confundir este caso con una raíz unitaria.

Lo que NO hay que hacer es convertirlo en un contraste de pendiente: con |t| > 2
estas dos se diferenciarían, y son el control de que eso está mal.

## Respuesta a la revisión externa (ago-2026)

Revisión en `~/Dropbox/SRC/atws/atsw-suite/` (tres documentos, 11-ago-2026);
respuesta razonada en `RESPUESTA_REVISION_2026-08-12.md` del mismo directorio.
Se aceptó ~60 % de las recomendaciones, se corrigió ~20 % y se rechazó ~20 % con
argumento. Lo aceptado, en orden:

- [ ] 🔴 **Series anuales (freq=1)**, 3 defectos — ya está arriba en §Bugs
      conocidos. Es el mayor excluyente de usuarios y sube a lo más alto.
- [ ] 🟠 **BUG-0015 por `domain` DECLARADO, no por detector de tipo de serie.**
      La revisión proponía clasificar la serie en ~5 categorías por "nombre,
      variabilidad, tendencia" y sobreescribir `decide_lambda`/`decide_orders`.
      **Se rechaza el mecanismo**: clasificar por el nombre del fichero es
      adivinación disfrazada de política y mete un segundo juez oculto, justo lo
      que `ARCHITECTURE.md:104` advierte. Un modelo que sale distinto porque el CSV
      se llamaba `IPC_ES.csv` en vez de `serie3.csv` no es una política, es un
      efecto lateral. **Se acepta el problema**: `build_model(..., domain=
      "price_index")`, declarado por el analista, igual que `estimate_mu` acaba de
      pasar de "nada lo decide" a "lo decide la política y el analista puede
      fijarlo". Declarado se audita y entra en el guion; inferido, no.
- [ ] 🟠 **C1 — promover en `fue` lo que ART importa de `fue.plots`.**
      `_draw_acf_panel`, `_snap_cmax`, `_tj_spines` entran desde `diagnosis.py`,
      `model_detection.py`, `seasonal_detection.py` y `mcp_server.py`: cuatro
      módulos colgando de funciones con guion bajo que ningún test de `fue`
      protege. Misma clase de problema que el inventario de `mtram`/`sima`.
- [ ] 🟠 **Tests de CONTENIDO de las instrucciones MCP** (sustituye a "extraer
      `_INSTRUCTIONS` a Markdown", que se rechaza). Las instrucciones son el
      producto; sacarlas a un fichero las saca del alcance de los tests de
      importación y crea un artefacto que empaquetar — eso ya costó la 0.1.6→0.1.7.
      Si se quieren revisar fuera del código, **generar `INSTRUCTIONS.md` desde el
      string**, como `TOOLS.md` se genera desde los docstrings; no mover la fuente
      de verdad al Markdown. El problema real es otro: **no hay ningún test sobre
      lo que las instrucciones dicen**. Prueba: `base_pre_path` tenía CERO
      menciones en `_INSTRUCTIONS` mientras era la única vía de respetar el
      contrato `.pre` al añadir ARMA.
- [ ] 🟠 **`run_full` escribe en el guion** (sustituye a "log narrativo de
      decisiones"). `guion.py` ya registra especificación, diagnóstico, ecuación,
      decisión y justificación — la revisión lo elogia en una sección y propone
      construirlo de nuevo en otra. El hueco real es que solo se rellena desde el
      camino guiado (`confirm_and_estimate`, `record_version`); el autónomo no deja
      traza. Con `PipelineResult.estimate_mu` ya hay precedente de qué registrar.
- [ ] 🟡 **Quitar las 4 tools legacy** (`boxcox_analysis`, `seasonal_analysis`,
      `unit_root_analysis`, `identification_analysis`): las cuatro remiten a
      `guided_identification` en su propio docstring. **Y resolver el solape
      `estimate_and_diagnose` / `confirm_and_estimate`**, que es el que un modelo
      puede confundir de verdad. Se descarta "bajar el catálogo a 20": el número no
      es la métrica, el solape sí.
- [ ] 🟡 **Unificar `_write_inp` y `_write_bare_inp`.** La revisión decía que
      `create_inp` construye el `.inp` a mano — **es falso**: construye un
      `fue.Model` y llama al único `_write_inp` (`mcp_server.py:498`). Pero hay un
      SEGUNDO escritor que no menciona: `_write_bare_inp` (`pipeline.py:34`), usado
      desde `mcp_server.py:3765`. Dos funciones que emiten el mismo formato con las
      cabeceras duplicadas — incluida la del `beg_period` que está detrás del
      defecto (2) del bug de series anuales. Arreglar los dos a la vez.
- [ ] 🟡 **Tipar `Description.data`** (dataclass por etapa). Ya declarado como
      deuda en `docs/ARCHITECTURE.md` §7 línea 250; la revisión lo confirma pero no
      añade nada.
- [ ] 🟡 **Tests golden de más dominios**: serie sin estacionalidad, serie anual,
      outlier extremo, varianza no constante. Hoy `test_golden_pipeline.py` cubre
      IPC mensual, que es exactamente donde las heurísticas están calibradas.
- [ ] 🟢 **Versión en el formato `.inp`** (`** FORMAT VERSION: 1`).
- [ ] 🟢 `pip install --upgrade drvarma` en el entorno local (hoy 0.1.3 editable
      contra 0.1.6 publicada). Es entorno, no paquete.

**Rechazado con argumento** (detalle en la respuesta §4): el detector de tipo de
serie por nombre; extraer `_INSTRUCTIONS` a Markdown; reconstruir el log de
decisiones; "35 herramientas es demasiado"; y "dependencia de Claude" como riesgo
—es la tesis del proyecto, no una amenaza; el riesgo real y distinto es que el
asistente prometa lo que el motor ya no cumple, y eso se mitiga con versionado y
tests de asistente—.

**Ya hecho cuando se escribió la revisión** y por tanto fuera de la lista: README
de `fue` en PyPI (4.000 caracteres), CHANGELOG y docs de DRVARMA (5.948), docs
unificadas de la suite (`atsw-suite/docs/`, 7 documentos, GitHub Pages en 200).
BUG-0013 y BUG-0014 se cerraron el 12-ago.

---

## Filosofía: ART simple + Claude como analista BJ

### Modelo de colaboración (documentado en sesión jun-2026)

La experiencia con IPC_DE, IPC_FR, IPC_ES y WTI mostró que Claude funciona bien
como analista Box-Jenkins independiente, usando directamente `pyfug` y `fue` como
instrumentos. ART no necesita ser un agente complejo que automatice el flujo entero:
provee instrumentos, Claude aporta criterio.

**División de responsabilidades**:

| Capa | Qué hace | Herramienta |
|------|----------|-------------|
| **pyfug** | Gráficos Jenkins-Treadway (serie, ACF/PACF, histograma, media-σ) | Python + matplotlib |
| **fue** | Estimación ML exacta ARIMA + intervenciones | Python (+ C opcional) |
| **ART** | Pruebas formales, selección de modelo, criterios de parada | Python |
| **Claude** | Identificación BJ, interpretación, refinamiento iterativo | LLM |

---

## Flujo BJ completo documentado (jun-2026)

### Paso 1 — Transformación Box-Cox (λ)

**Gráfico**: `plot_mean_deviation_pair(ser, name="X")` — nivel y log uno al lado del otro.

**Criterio empírico** (m-dt):
- Nivel: si los puntos forman pendiente positiva (σ ∝ μ) → log indicado
- Log: si los puntos se dispersan sin pendiente (σ ≈ cte) → λ=0 confirmado

**Criterio teórico** (prevalece aunque el gráfico no sea concluyente):
- **Números índice** (IPC, IPCA, IPP, deflactores...): base arbitraria (p.e. 2015=100),
  las diferencias absolutas carecen de sentido; las tasas de variación (∇ ln) sí lo tienen.
- **Series con base arbitraria** (precios en unidades nominales, producciones indexadas):
  mismo argumento — el nivel no es comparable entre períodos.
- **Series de precios de commodities** (WTI, Brent, gas...): la volatilidad crece con el
  nivel, σ ∝ μ es la norma; el log estabiliza la varianza.
- Regla práctica: si hay razón teórica para λ=0, usarlo aunque el m-dt no lo exija.

**Comentario inicial al analista** (antes de ver el gráfico):

> El analista puede imponer λ a priori sin necesidad de ver el m-dt:
> - Para **números índice** (IPC, IPCA, IPP, deflactores) con base arbitraria,
>   λ=0 es la elección natural — las diferencias logarítmicas son tasas de variación.
> - Para **precios de commodities** (WTI, Brent, gas natural) y series multiplicativas,
>   el log estabiliza la varianza por construcción.
> - El m-dt sirve para **confirmar o cuestionar** esa elección, no para sustituirla.
>   Si el m-dt contradice la elección teórica, es señal de que algo inusual ocurre
>   (cambio estructural, truncamiento, error de datos).

**Análisis de casos (jun-2026)**:

| Serie | Evidencia m-dt nivel | Evidencia m-dt log | Decisión | Razón principal |
|-------|---------------------|-------------------|----------|----------------|
| IPC_DE | nube horizontal, outlier 2022 sup-der | similar | **λ=0** | índice base arbitraria (2015=100) |
| IPC_ES | nube dispersa, sin pendiente clara | similar | **λ=0** | índice base arbitraria (2016=100) |
| IPC_FR | nube horizontal, outlier 2022 sup-der | similar | **λ=0** | índice base arbitraria (2015=100) |
| WTI    | pendiente positiva visible | nube sin pendiente | **λ=0** | commodity + evidencia empírica |

Para los tres IPC el criterio teórico es determinante: el m-dt no muestra
heteroscedasticidad fuerte porque la inflación fue estable y baja en 2002-2021;
el outlier de 2022 (crisis energética) es un episodio excepcional, no estructura.
Para WTI el m-dt confirma empíricamente lo que la teoría ya indica.

---

### Paso 2 — Diferenciación (d, D)

Sobre la serie transformada (`ln x` si λ=0):

**2a. Diferencia regular (d)**

`plot_combined(ln x)` + ADF/KPSS sobre ln x → ACF decae → d=1

Comentario tipo:
> La ACF decae lentamente desde valores cercanos a 1 — no estacionariedad clara.
> ADF no rechaza raíz unitaria; KPSS rechaza estacionariedad. Los contrastes son
> herramienta de apoyo: la estacionalidad marcada reduce la potencia del ADF
> (residuos del AR auxiliar no son ruido blanco). La decisión d=1 descansa
> principalmente en el patrón ACF/PACF.

**2b. Estacionalidad — bifurcación B1/B2**

`plot_combined(∇ ln x)` + **contraste HAC de estacionalidad** (ART):

```python
from art.seasonal_detection import detect_seasonality, plot_seasonality
result = detect_seasonality(ts, d=1, lam=0.0)
# result.f_stat, result.p_value, result.seasonal_detected
fig = plot_seasonality(result)   # opcional — efectos mensuales + Wald por frecuencia
```

Comentario tipo cuando la estacionalidad es evidente:
> La ACF de ∇ ln x muestra picos en lags s, 2s, 3s — estacionalidad clara.
> HAC F(s-1, n-s) >> 0, p=0.000. Cuando no es obvia visualmente, el test HAC
> es especialmente valioso; el gráfico aporta además los efectos mensuales estimados.

**Bifurcación B1 / B2** — el analista elige la tradición metodológica:

| Opción | Tradición | Especificación | Contrastación posterior |
|--------|-----------|---------------|------------------------|
| **B1** | **Treadway** | d=1, D=0 + armónicos cos/sin en D_t | MEG frecuencia por frecuencia |
| **B2** | **Box-Jenkins** | d=1, D=1 (SARIMA multiplicativo) | MEG sobre D=1 vs D=0 |

**B1 (Treadway)**: la estacionalidad se modela como determinista (efectos fijos mensuales
via armónicos). Más general: permite que cada frecuencia estacional sea significativa
o no de forma independiente. Los residuos quedan más limpios para identificar el ARMA.
Tras estimar, el test MEG de ART contrasta si alguna frecuencia requiere tratamiento
estocástico. Es el camino propio del enfoque BJ-Treadway de ART.

**B2 (Box-Jenkins)**: la estacionalidad se modela como estocástica imponiendo D=1.
Conduce directamente a los modelos multiplicativos ARIMA(p,1,q)(P,1,Q)₁₂ de BJ.
Más parsimonioso cuando la estacionalidad es claramente estocástica, pero impone
una restricción que puede no ser necesaria en todas las frecuencias.

El analista elige explícitamente entre las dos tradiciones. ART implementa B1 como
flujo principal; B2 es también soportado como hipótesis de trabajo alternativa.

**Casos documentados (jun-2026)**:
- **IPC_ES** (mensual): d=1 (ADF t=−2.42 p=0.37; KPSS p<0.01); HAC F(11,250)=6351.7 p=0.0000 → **B1**
- **IPC_DE** (mensual): d=1, D=1 → ARIMA(0,1,0)(0,1,1)₁₂ (B2)
- **WTI**   (mensual): d=1, D=0, sin estacionalidad → AR(2) + escalones

---

### Paso 2c — Modo de análisis (pregunta obligatoria al analista)

**Antes de continuar con la identificación ARMA**, Claude debe preguntar:

> ¿El análisis está en **modo guiado** (un paso a la vez, con comentario y confirmación)
> o en **modo autónomo** (flujo completo hasta diagnóstico final)?

Esto determina el ritmo de la sesión y si Claude espera respuesta en cada bifurcación.

---

### Paso 3 — Intervenciones primero ("lo más obvio primero")

**Principio BJ-T**: los outliers extremos distorsionan las ACF/PACF ("las matan"),
haciendo que los coeficientes ARMA identificados sean artefactos de las interacciones
entre valores extremos, no estructura genuina de la serie. La secuencia correcta es:

1. **Identificar y tratar intervenciones** antes de identificar el ARMA
2. **Luego** identificar ARMA en los residuos limpios

**Error a evitar** (documentado en IPC_ES, jun-2026): tras el primer modelo con armónicos,
ACF(1)=+0.31* llevó a proponer MA(1). Pero había 16 outliers en 2021-2023 (máx +6.1σ)
que distorsionaban toda la ACF. El MA(1) era probablemente un artefacto. La decisión
correcta es tratar primero los outliers, luego reidentificar el ARMA.

**Herramienta ART**: `preliminary_outlier_scan` — identifica residuos > 2σ y muestra
sus contribuciones a la ACF, permitiendo calibrar cuánto distorsionan los correlogramas.

```python
from art.interventions import preliminary_outlier_scan
result = preliminary_outlier_scan(model_residuals, sigma, ...)
```

**Secuencia correcta para B1 (Treadway)**:
1. Estimar armónicos (sin ARMA)
2. **Identificar outliers** → añadir escalones/impulsos para los más extremos
3. Reestimar con intervenciones → ACF/PACF limpias
4. **Ahora** identificar ARMA en residuos limpios
5. Estimar modelo completo (armónicos + intervenciones + ARMA)

### Paso 4 — Identificación ARMA (sobre residuos limpios)

ACF/PACF de residuos tras tratar outliers:
- PACF(1..p) corta, ACF decae → **AR(p)**   ← regla clave
- ACF(1..q) corta, PACF decae → **MA(q)**
- ACF(s) significativo, PACF(s) decae → SMA(1)
- Ambas decaen → ARMA(p,q)

**Regla mnemotécnica**: PACF corta → AR; ACF corta → MA.

**Media**: si $\bar{w}/\sigma_{\bar{w}} > 2$, la media es significativa → incluir `estimate_mu=True`.
La media en $\nabla \ln x_t$ implica una tendencia (drift) en $\ln x_t$.

**Caso IPC_ES (jun-2026)**:
- PACF(1)=+0.35*, corte → AR(1)
- μ=+0.14%/mes, t=7 → media significativa (inflación promedio 2002-2024)
- Modelo: ARI(1,1) con media

---

### Paso 5 — Estimación y presentación

**Ciclo `mNN.pre` → `m(NN+1)`**:

```python
from fue.report import write_pre

# 1. Guardar modelo estimado como .pre
write_pre(m_fitted, "cases/SERIE/SERIE_mNN.pre")

# 2. Cargar .pre del modelo anterior como punto de partida
ts, m_init = fue.load("cases/SERIE/SERIE_mNN.pre")

# 3. Construir modelo siguiente añadiendo la modificación
m_next = fue.Model(ts, ..., ar=[[-0.35]], ar_free=[[True]],
                   mu=0.0014, estimate_mu=True,
                   interventions=m_init.interventions)
m_next.fit()
write_pre(m_next, "cases/SERIE/SERIE_m(NN+1).pre")
```

**Presentación del modelo**: siempre incluir:
1. Gráfico residuos + ACF/PACF (`plot_combined`)
2. Histograma (`plot_histogram`)
3. **Ecuación del modelo en Unicode** — usar `art.describe.model_equation`:

```python
from art.describe import model_equation
print(model_equation(ts, m_fitted))
```

Produce la forma BJ-T completa con coeficientes, errores estándar y estadísticos:
```
(1)  ln Xₜ = Dₜ + Nₜ          ← parte determinista (intervenciones + armónicos)
(2)  ∇(1 − φ₁B)(Nₜ − μ) = aₜ  ← ecuación de ruido (ARMA + media)
σ̂ₐ = ...   ℓ = ...   AIC = ...   BIC = ...
```
Visible directamente en Claude Code (terminal Unicode).

**Indexación `at=` en fue**: **0-based** (at=0 = primera obs).
Para (año y, mes m) con serie iniciando en (2002,1):
```python
at = (y - 2002)*12 + (m - 1)   # 0-based
```

---

### Paso 6 — Diagnóstico de residuos

- `plot_combined(residuos)` — serie + ACF/PACF: buscar Q(k) no significativo
- `plot_histogram(residuos)` — normalidad: JB+p-valor
- Outliers > 2σ → nueva intervención → ciclo `mNN.pre` → `m(NN+1)`

**Lección WTI** (jun-2026): escalones consecutivos (at=218,219,220 para crash COVID
mar-abr-may 2020) tienen multicolinealidad alta. Un t bajo no implica que el escalón
sea prescindible — revisar los residuos antes de eliminar.

---

### Sistema de control de cambios por caso (jun-2026)

Cada caso de análisis BJ tiene su directorio en `art-python/cases/SERIE/`:

```
cases/
  IPC_ES/
    IPC_ES_m00.pre   — armónicos base (sin ARMA, sin intervenciones)
    IPC_ES_m01.pre   — + intervenciones outliers
    IPC_ES_m02.pre   — + AR(1) + media
    CHANGELOG.md     — control de cambios modelo a modelo
```

**`CHANGELOG.md`** documenta por cada `mNN`:
- Especificación (qué se añadió/eliminó respecto al anterior)
- Parámetros estimados clave
- Diagnóstico (σ̂, Q, JB)
- Outliers restantes
- Próximos pasos

**Principio**: cada `.pre` es el punto de partida del siguiente modelo.
Los parámetros estimados en `mNN` se convierten en valores iniciales de `m(NN+1)`,
garantizando convergencia rápida y trazabilidad completa del proceso de refinamiento.

---

## Arquitectura de servidores de datos, gráficos y modelos (jun-2026)

### Motor de datos — fue

```
Entrada         Tipo                    Función
──────────────────────────────────────────────────────────────────
array/CSV/xlsx  → fue.TimeSeries        .from_array / .from_csv / .from_pandas
.inp / .pre     → (TimeSeries, Model)   fue.inp.load(path)   ← _InpParser.parse()
                                        at= en .inp/pre es 1-based → at_0 = at_1-1
                                        Model no estimado; .fit() para estimar

Propiedades clave de fue.TimeSeries:
  .data  : np.array   (valores en niveles tal cual se cargan)
  .freq  : int        (1=anual, 4=trim., 12=mensual)
  .start : (year, period)   1-based
  .name  : str

Nota: .residuals devuelve TimeSeries sin .start correcto → usar _resid_start(model)
```

### Motor de modelos — fue.Model

```
Construcción        Helpers ART              Parámetros clave
─────────────────────────────────────────────────────────────────
fue.Model(ts, ...)  _build_inp(...)          d, D, boxlam, ar, ma, ar_s, ma_s
                    _build_arma_on_model(m)  interventions (cos/sin/step/pulse)
                                             estimate_mu, ifadf

Estimación:   m.fit()  →  C engine MVENC  →  m._result: FitResult
Resultados:   m.residuals / .params / .std_errors / .aic / .bic / .sigma2

Serialización:
  write_pre(m, path)   →  .pre  (parámetros estimados como valores iniciales)
  fue.load(path)       ←  .pre / .inp  (Model sin estimar)

Workaround obligatorio (bug C backend):
  Si p=0 y q=0: añadir AR(1) φ=0 fijo para evitar crash del estimador C.
  _build_inp y _build_arma_on_model lo aplican automáticamente.

Bug conocido (fue/TODO.md):
  ar_s (P≥1) + ma_s (Q≥1) simultáneos → crash C. Solo P>0 ó Q>0, no ambos.
```

### Motor de gráficos — pyfug

```
Tipo entrada    Preparación ART             Función pyfug              Output
────────────────────────────────────────────────────────────────────────────────
fue.TimeSeries  _pyfug_from_fue(ts)         plot_mean_deviation_pair   PNG b64 (λ)
numpy + meta    _pyfug_ts(w, freq, start)   plot_combined(pf)          PNG b64 (serie+ACF+PACF)
residuos        _pyfug_ts(r, f, _resid_start(m))  plot_combined(pf)  PNG b64 (diagnosis)
residuos        idem                        plot_histogram(pf)         PNG b64 (histograma)

Regla crítica: pyfug opera sobre .data tal cual — NO diferencia internamente.
  plot_combined(d=, ds=) acepta esos params pero los ignora.
  ART aplica boxcox_transform + apply_differences ANTES de crear pyfug.Tseries.

Figuras internas ART (sin equivalente en pyfug, quedan en matplotlib):
  describe_unit_root        →  tabla coloreada ADF/KPSS
  describe_prelim_scan      →  serie tipificada + barras contrib. ACF outliers
  describe_seasonal_params  →  barras cos/sin ± 2SE por armónico
  _plot_series_at_d         →  [PENDIENTE migrar a pyfug — ver §Optimizaciones]
```

### Bridge fue ↔ pyfug (describe.py:53–78)

```python
# Array numpy → pyfug.Tseries
def _pyfug_ts(data, freq, start, name) -> Tseries

# fue.TimeSeries → pyfug.Tseries (datos en niveles)
def _pyfug_from_fue(ts) -> Tseries

# Start correcto para residuos (fue.TimeSeries.residuals no propaga start)
def _resid_start(model) -> tuple:
    n_skip = model.d + model.D * freq
    off    = (start[1] - 1) + n_skip
    return (start[0] + off // freq, off % freq + 1)
```

### Retorno al MCP — Description

```python
@dataclass
class Description:
    summary    : str        # markdown análisis para el LLM
    figure_b64 : str|None   # ACF/PACF o figura principal (PNG base64)
    recommendation: str     # próxima decisión sugerida
    data: dict              # {
                            #   "hist_b64": str|None,     ← histograma pyfug
                            #   "d", "D", "lam": ...,
                            #   "suggestions": [...],     ← candidatos ARMA
                            #   "outliers": [...],        ← prelim scan
                            # }

# Cada MCP tool devuelve:
[TextContent(summary + recommendation),
 ImageContent(figure_b64),        ← ACF/PACF
 ImageContent(data["hist_b64"])]  ← histograma (cuando disponible)
```

---

## Gráficos pyfug en el flujo

| Paso | Preparación | Función pyfug |
|------|------------|--------------|
| 1. λ | `_pyfug_from_fue(ts)` | `plot_mean_deviation_pair(pf, name)` |
| 2–3. Serie diferenciada | `boxcox_transform + apply_differences + new_start` | `plot_combined(pf)` |
| 4. ARMA sobre residuos | `_pyfug_ts(resid, freq, _resid_start(m))` | `plot_combined(pf, d=0)` |
| Histograma residuos | idem | `plot_histogram(pf, d=0)` |

```python
# Retardos por defecto (pyfug)
nlags = max(10, 3 * (freq + 1))   # 39 mensual, 15 trimestral, 10 anual
```

---

## Optimización de flujos — tokens y tiempo (pendiente)

### Ineficiencias actuales

**1. `_plot_series_at_d` — duplicación + matplotlib interno**

`guided_identification` calls 2 y 3 usan `_plot_series_at_d`, que reimplementa
manualmente lo que pyfug ya hace en `plot_combined`. ~110 líneas duplicadas.

```
_plot_series_at_d(ts, lam, d)
  → boxcox manual (lam=0 → log, else → (x^lam-1)/lam)
  → np.diff(y) d veces
  → fue.diagnostics.acf / pacf
  → fue.plots._draw_acf_panel  (privado de fue)
  → matplotlib figura propia
```

**Solución**: reemplazar con `_pyfug_ts(w, freq, start) + plot_combined(pf)`.
Mismo output, cero código duplicado, coherencia visual con el resto del flujo.

**2. Re-estimación en cada llamada MCP**

`_load_fitted(path)` = `fue.load(path)` + `m.fit()`. Cada tool que necesita
el modelo estimado lo re-estima desde cero aunque el `.pre` tenga parámetros.

Impacto: estimación MVENC ≈ 0.1-2s por modelo (C backend); en el ciclo de
outliers (5-20 rondas) esto suma. Sin cache entre llamadas MCP.

**Solución mínima**: leer parámetros del `.pre` como valores fijos cuando todos
los `free=False` (forecast mode). Para el caso guiado no aplica directamente,
pero documentar como limitación.

**3. Dos imágenes por llamada de diagnosis**

`estimate_and_diagnose`, `confirm_and_estimate`, `suggest_intervention_form`
devuelven ahora `[Text, ImageContent(ACF), ImageContent(hist)]`.
Cada imagen PNG base64 ≈ 15-40 KB = 20.000-55.000 tokens.
En el ciclo de outliers (10+ rondas) esto supone 200.000-550.000 tokens solo en imágenes.

**Solución**: añadir parámetro `include_histogram: bool = False` a estas tools.
El histograma solo es necesario en el diagnóstico FINAL, no en cada ronda del ciclo.

**4. `describe_diagnosis` llama al estimador dos veces vía model_equation**

`describe_diagnosis` llama `model_equation(model.series, model)` que puede
redundar con accesos a `model._result` ya disponibles.
Impacto menor pero documentar.

**5. Coste total tokens por análisis completo (estimación)**

| Fase | Tools | Imágenes | Tokens imagen aprox. |
|------|-------|----------|---------------------|
| Identificación (calls 1-4) | 4 | 1×call ≈ 1-2 imgs | 40-80 K |
| m00 estimación | 1 | 2 imgs (ACF+hist) | 40-80 K |
| Ciclo outliers × N rondas | N×2 | 2 imgs/ronda | 40-80 K × N |
| Modelo final | 1 | 2 imgs | 40-80 K |
| Refinamiento (G, H, MEG) | 3 | 1-2 imgs/tool | 40-120 K |
| **Total (N=10 rondas)** | ~20 | ~28 imgs | **~800 K tokens** |

### Acciones recomendadas (por impacto)

- [ ] **Alta**: reemplazar `_plot_series_at_d` con pyfug `plot_combined`
      (elimina ~110 líneas de código interno de fue, coherencia visual)
- [ ] **Alta**: añadir `include_histogram: bool = False` a `confirm_and_estimate`
      y `suggest_intervention_form` — histograma solo en diagnosis final
- [ ] **Media**: en `guided_identification` call 3 (HAC seasonality), no mostrar
      imagen de seasonality si el analista ya confirmó d — se puede omitir
- [ ] **Media**: documentar el bug P+Q simultáneos en fue C backend en CHANGELOG
      y en la docstring de `confirm_and_estimate`
- [ ] **Baja**: añadir `include_histogram` a `estimate_and_diagnose` también

---

## Pendiente

- [ ] **Bloque M**: `_plot_series_at_d` → migrar a pyfug (ver §Optimizaciones)
- [ ] **Bloque M**: `seasonality_form="deterministic"|"multiplicative"` en
      `guided_identification` call 3 como parámetro explícito (no solo texto).
      Es el MECANISMO de la pregunta de objetivo de más abajo (§El objetivo
      del modelo); conviene diseñar las dos juntas.
- [ ] **Pruebas de raíz unitaria**: integrar ADF/KPSS/Shin-Fuller en el flujo
- [ ] **Notebook de demostración**: flujo completo IPC_DE con pyfug + fue

---

---

## Los armónicos borran la evidencia estacional antes de buscarla (ago-2026)

**Estado: medido, sin arreglar. Es el que va primero de los dos de esta
sección — el otro no se puede calibrar hasta que éste esté resuelto.**

`suggest_orders` resta por MCO los armónicos deterministas de la serie
diferenciada ANTES de calcular la acf/pacf con que identifica
(`model_detection.py:480, 581`). El docstring de `_remove_harmonics:421` dice
para qué es:

> *"Used when D=0 so seasonal structure in ACF/PACF reflects ARMA, not
> harmonics."*

**Y sobre CPI_USA hace lo contrario de lo que dice.** Medido sobre la serie
diferenciada, banda 2/sqrt(n) = 0.126:

| | r(12) | ¿cruza? |
|---|---|---|
| serie diferenciada | **+0.239** | **sí** |
| tras quitar 5 armónicos (lo que ve el motor) | **+0.014** | no |

La autocorrelación estacional desaparece. Y no se atenúa nada más: la pacf a 12
pasa de +0.069 a **−0.124**, o sea que **cambia de signo** — la resta no está
siendo neutral.

### Consecuencia, medida

Sobre CPI_USA, `suggest_orders` propone `(0,1)(0,0)` y sus CUATRO primeros
candidatos llevan P=Q=0. Nunca mira el retardo estacional. Ajustando a mano,
con 5 armónicos y d=1:

| modelo | AIC |
|---|---|
| **(0,1)(0,0) ← lo que art propone** | **297.54** |
| (1,0)(0,0) | 290.06 |
| (2,0)(0,0) | 291.30 |
| (2,0)(1,0)_12 | 275.47 |
| (2,0)(2,0)_12 — el que David identifica como el típico | 274.81 |
| (0,1)(2,0)_12 | **271.98** |

La propuesta de art es **la peor de las seis**, por 25.6 puntos de AIC. El AR
estacional vale ~25 puntos y el motor no puede verlo.

### El argumento de fondo: es circular

Restar los armónicos es SUPONER que la estacionalidad es determinista, que es
justo lo que los órdenes P y Q existen para contrastar. El pre-paso decide la
pregunta antes de hacerla.

A eso se añade lo cuantitativo: con el defecto `n_harmonics = s//2 = 6` son 11
columnas más la constante, doce regresores ajustados por MCO sobre ~215
observaciones. Un patrón estacional estocástico es en muestra finita
parcialmente colineal con esos senos y cosenos fijos, y parte se va con ellos.

### Opciones

1. **Leer los órdenes ESTACIONALES de la serie SIN restar** y los regulares de
   la restada. Dos acf, cada pregunta sobre el dato que le corresponde. Es la
   que responde al argumento circular.
2. **Avisar del conflicto**: si r(s) cruza la banda antes de restar y no
   después, decirlo. No arregla, pero deja de ser silencioso.
3. **Bajar el defecto de `n_harmonics`.** Alivia sin resolver, y elige un
   número sin criterio.

### Cuidado al tocarlo

`suggest_orders` es el motor de identificación y David ha pedido explícitamente
no meterle heurísticos nuevos: "como está funciona más o menos". Esto NO es un
heurístico --es un pre-paso que contradice su propio docstring-- pero vive en
el mismo fichero, así que conviene que el arreglo sea claramente una corrección
y no una preferencia, y medir las ocho series antes y después.

---

## Penalizar configuraciones MA implausibles: propuesta MEDIDA, en espera

**Estado: propuesta con números, NO implementar todavía.** Depende de la ficha
de los armónicos: calibrarla ahora sería calibrarla contra un pre-paso roto.

### El mecanismo, que es la parte sólida

Para un MA(1), `rho_1 = -theta/(1+theta^2)`, luego **rho_1 > 0 <=> theta < 0**.
El signo de theta se lee en la acf empírica del retardo 1, SIN estimar nada. Y
un IMA(1,1) con theta<0 es un EWMA con suavizado (1-theta) > 1, fuera de rango,
cuyos pesos de previsión sobre los NIVELES alternan de signo (theta=-0.7 ->
1.700, -1.190, +0.833, -0.583...). Para un índice de precios no es un proceso
generador defendible.

En las ocho series del IPC, rho_1 > 0 SIN EXCEPCIÓN (de 0.079 a 0.422): el
detector dispara exactamente en el dominio del que se habla.

### Dónde y cuánto

`_parsimony_score` (`model_detection.py:381`), que ya lleva penalizaciones
ESTRUCTURALES --+0.12 si P>0 y Q>0 a la vez, +0.08/0.12/0.20 por exceso de
orden-- así que penalizar una configuración implausible es lo que esa función
ya hace, y recibe la acf empírica.

Márgenes de similitud medidos, MA(1) contra AR(1):

| serie | sim(0,1) | sim(1,0) | margen |
|---|---|---|---|
| CPI_USA | 0.8917 | 0.8487 | 0.0429 |
| IPC_JP | 0.8664 | 0.8101 | 0.0564 |
| IPC_DE | 0.9246 | 0.8663 | 0.0583 |
| IPC_CA | 0.9464 | 0.8674 | **0.0790** |

**lambda_1 = 0.10** para `p==0 and q==1 and rho_1>0` bastaría — el mínimo
medido es 0.0790, y 0.10 está en el mismo orden que el 0.12 que ya se aplica.
Para el MA(2) NO hay medida y no debe inventarse el número.

### Tres condiciones

1. **Condicional al DOMINIO.** Un prior de precios en una herramienta general
   es un sesgo escondido. `suggest_orders` no tiene marca de dominio, y ya van
   TRES fichas que la necesitan (ésta, el empate AR(1)/MA(1) y la del
   objetivo). Conviene añadirla de una vez.
2. **Anunciada siempre**, o deja de ser criterio y pasa a ser sesgo.
3. **Reversible** por parámetro.

### Lo que cuesta

**IPC_JP se voltearía, y es uno de los tres que art acierta** hoy según AIC. La
penalización no sale gratis.

### Y por qué esperar

Con el AR estacional dentro, el mejor modelo de CPI_USA resulta ser
**(0,1)(2,0)_12 — un MA regular**. Si se penaliza el MA regular calibrando
sobre las similitudes que produce el pre-paso de los armónicos, se estaría
corrigiendo el síntoma de otro defecto y empujando en contra de un modelo que
es bueno. Primero los armónicos, luego volver a medir los márgenes, luego
decidir.

### Lo que NO se confirmó, y queda anotado

El sesgo hacia MA **no se sostiene como dirección** en datos reales. De los
cinco desacuerdos entre la propuesta de art y el mejor AIC (3 de 8 coinciden),
tres van art->MA cuando el AR ajusta mejor y **dos van al revés**; y el
desacuerdo mayor con diferencia --IPC_ES, delta AIC 21.7-- es art proponiendo
AR(2) cuando el mejor es MA(2). Con n=8 no hay dirección. Lo que sí queda es un
problema de ACIERTO, y la ficha de los armónicos explica buena parte de él.

Tampoco se reprodujo el AR(2) de raíces complejas identificado como MA(2): sólo
tres de las ocho tienen raíces complejas al ajustar AR(2) (ES, EMU, JP) y en
ninguna art propone MA(2). En simulación el fallo es sub-ordenar a AR(1).

---

## El empate AR(1)/MA(1): la regla existe, falta aplicarla sola (ago-2026)

**La regla está escrita y razonada** en `policy.py:decide_orders` y, desde
2026-08-08, en las instrucciones MCP (LLAMADA 4), que es lo que Claude lee de
verdad. Hasta entonces vivía sólo en el docstring, así que se aplicaba cuando
Claude abría ese fichero y no si no — la inconsistencia que reportó el analista
("a veces caza que los precios prefieren AR, a veces sigue al pie de la letra").

**Lo que falta es que `decide_orders` la aplique**, y su propio docstring dice
por qué: no recibe (a) la marca de DOMINIO de la serie (precio/índice) ni (b)
los estadísticos de ajuste de los candidatos, que son lo que permite detectar el
empate con seguridad. Sin las dos, aplicarla sería adivinar.

### Lo que hay que decidir antes de tocarlo

1. **Cómo llega el dominio.** ¿Un campo en el `.inp`/`.pre`? ¿Un parámetro de
   `guided_identification`? ¿Se infiere del nombre, que sería frágil? Toca el
   convenio de ficheros si es lo primero.
2. **Cómo se define "empate".** ΔAIC < 2 es el umbral escrito, pero un empate
   real pide más: igual parsimonia, los dos pasando Q y JB, acf/pacf residuales
   casi idénticas. Hay que fijar el conjunto y medirlo, no elegirlo.
3. **Modo autónomo.** En guiado el analista ve las dos opciones y decide; en
   autónomo no hay nadie. ¿Aplica la regla y lo declara entre los defectos
   tomados, o se abstiene y deja el empate anotado? Lo primero encaja con cómo
   `build_model` ya declara sus defectos.
4. **Generalización.** Hoy es una regla de precios. ¿Hay otras parejas
   casi-equivalentes con lectura teórica distinta que merezcan el mismo trato?
   Diseñar un mecanismo para una sola regla es sobreingeniería; escribir la
   segunda regla a mano cuando llegue, probablemente no.

### El argumento, para que no haya que reconstruirlo

Los dos candidatos dan ρ₁ > 0 en la serie diferenciada y sólo los separan los
retardos 2+, que es donde la evidencia es más débil. El MA(1) que compite lleva
θ < 0, y un IMA(1,1) con θ < 0 es un EWMA con constante de suavizado (1−θ) > 1,
fuera de rango: sus pesos de previsión sobre los NIVELES alternan de signo
(θ=−0.7 → 1.700, −1.190, +0.833, −0.583…). Previene sobrepasando la última
observación y corrigiendo hacia atrás. El AR(1) con φ>0 dice que el CAMBIO está
positivamente autocorrelado — persistencia — que es lo que la teoría de precios
espera.

**Y la salvaguardia, que no es opcional:** la regla debe ENUNCIARSE siempre.
"Los datos prefieren X por ΔAIC=…, la teoría prefiere Y porque…, decides tú".
Un criterio teórico que no se anuncia deja de ser criterio y pasa a ser sesgo.

---

## El objetivo del modelo: ¿análisis multivariante o previsión? (ago-2026)

**Estado: a diseñar. No implementado, y no conviene implementarlo a medias.**

La línea de la escuela NO es la misma según para qué sea el modelo, y art
today no pregunta para qué es. La elección que se bifurca es la
**especificación de la estacionalidad**, en LLAMADA 3:

| objetivo | preferencia | por qué |
|---|---|---|
| análisis MULTIVARIANTE | determinista (B1, armónicos) | el preblanqueo filtra el output por el ARMA del INPUT; una estacionalidad estocástica en el output que el input no tiene sobrevive al filtro, y la ccf sale poco informativa — y **no vacía**: sale con estructura por todas partes y la heurística le lee un orden igualmente |
| PREVISIÓN | a veces estocástica (B2) | deja que el patrón estacional evolucione; unos armónicos fijos no, y cuando de hecho evoluciona previene peor |

Desde 2026-08-08 el aviso está en LLAMADA 3 y dice las dos direcciones, pero
sigue siendo TEXTO: art no pregunta el objetivo ni lo propaga.

### Lo que hace esto no trivial

**El objetivo NO manda sobre los datos.** «Es más fácil el análisis
multivariante con estacionalidad determinista **si ésta es sostenible con los
datos**» — y quien decide si lo es no es la preferencia del analista sino el
MEG, frecuencia por frecuencia (DCD sobre el testigo MA_f, Shin-Fuller sobre
el AR_f). Un diseño que dejara al objetivo imponer determinismo donde el
contraste lo rechaza convertiría una preferencia en un sesgo, y sería peor que
no preguntar nada.

Así que la pregunta no es «¿determinista o estocástica?» sino algo más fino, y
ahí está el trabajo de diseño:

1. **¿Dónde entra el objetivo?** Lo natural es que rompa EMPATES y fije la
   parada provisional, no que decida. La tradición ya especifica la
   estacionalidad provisionalmente como determinista y sólo después resuelve
   frecuencia por frecuencia: el objetivo diría hasta dónde llevar esa
   resolución, no cuál es el resultado.
2. **¿Y si el MEG dice estocástica y el objetivo es multivariante?** Es el caso
   interesante y el que más se va a dar. Hay al menos tres salidas y hay que
   elegir: (a) aceptarla y avisar de que la ccf va a ser difícil de leer;
   (b) el artificio Muñoz §2.4 — un modelo para IDENTIFICAR con la
   estacionalidad hecha determinista y otro para ESTIMAR, que es lo que mtram
   ya soporta con `ident_pre=`; (c) rechazarla, que no es defendible.
   La (b) parece la buena y ya tiene la mitad construida.
3. **¿Un modelo o dos?** Si el mismo `.pre` va a servir para prever y para una
   transferencia, el conflicto es real. ¿Se emiten dos `.pre` con un nombre que
   diga para qué es cada uno? Eso toca el convenio de ficheros
   (`drtran-python/docs/LADDER_AS_OPTIMISATION.md`) y no debería hacerse sin
   leerlo.
4. **¿Cuándo se pregunta?** No al abrir el análisis: hasta LLAMADA 3 nadie sabe
   si la serie es estacional, y preguntar antes pide una decisión sobre algo
   que todavía no existe. Ése fue el defecto que originó esta ficha.
5. **¿Se propaga?** Si art conoce el objetivo, mtram y sima podrían leerlo del
   `.pre` en vez de volver a deducirlo. Eso es un campo nuevo en el fichero, y
   otra vez el convenio.

### Mecanismo

`seasonality_form` en `guided_identification` (§Pendiente) es la palanca. El
objetivo sería lo que la mueve, no un segundo camino paralelo.

### Contraparte ya hecha en mtram

`_seasonality_note` detecta el desajuste (output estocástico / input no),
distingue SARIMA multiplicativo de híbrido MEG, y ofrece `ident_pre=`. Dice
también que para previsión la estocástica a veces gana. Lo que falta es que
alguien PREGUNTE antes, que es esta ficha.


## Revisar problemas de MEG  (detectados en el caso IPC_DE, 2026-06)

- [ ] **Bug round-trip de factores de frecuencia fija (`ma_f`/`ar_f`)** — bloquea
      el propio flujo que recomienda el MEG (activar `ifadf[f]=1` + MA_f testigo).
      El escritor (`fue.report._ffixed_body`, usado por `write_pre`/`write_fuf`)
      emite `count\n**\nfreq phi2 flag`, pero el lector
      (`fue.inp._read_ffixed_section`) espera `count freq1 freq2…\n**\ncoef flag`
      → `IndexError` al recargar cualquier modelo con `ma_f`. Cualquier modelo
      MEG-driven con raíces estacionales no sobrevive a `load`/`load_fuf`.
      Workaround actual: post-procesar el fuf al formato del lector
      (ver `drvarma .../cases/IPC_DE/work/make_uf_fuf.py`). **Unificar writer/reader.**
- [x] **Reformular el modelo tras MEG estocástico (RESUELTO)** — antes no había
      forma de construir, desde el último `.pre`, el modelo que el MEG recomienda al
      concluir estacionalidad estocástica en f. Ahora:
      helper `art.formal_tests.reformulate_stochastic(model, freq, s)` (activa
      `ifadf[freq]=1` — 1−2cos·B+B² interior, 1+B Nyquist — y elimina los armónicos
      deterministas en f; sin testigo) + tool MCP
      `meg_reformulate(inp_path, freq, output_path, base_pre_path)` que carga el
      `.pre`, reformula, re-estima, escribe `.pre/.out` y muestra ecuación+diagnosis.
      `ifadf` es lista de flags 0/1 → round-trip OK (no sufre el bug de `ma_f`).
      Verificado: reformula f=1 (ifadf[1]=1, quita armónicos de f=1, re-ajusta).
      Pendiente aún: exponer también `ma_f`/AR_f estacionario de sobreajuste si se
      quiere estructura AR/MA estacional adicional tras la raíz unitaria.
- [ ] **Falso positivo del MEG por cuasi-cancelación** — en IPC_DE el MEG marcó
      freq 1,2 estocásticas (LR 13.9/4.0) pero, al ajustar ifadf+MA_f, θ²→≈0.90/0.93
      (cerca del círculo unidad) ⇒ las raíces se cancelan casi con su MA_f testigo:
      la frecuencia es *efectivamente determinista*. La previsión out-of-sample lo
      confirmó (el determinista batió al estocástico a h=1/12/24).
      → Avisar de cuasi-cancelación (DCD_f en la frontera de invertibilidad) en la
      salida de `formal_tests`/MEG y NO recomendar `ifadf` automáticamente cuando θ²→1.
- [~] **Estacionalidad residual con ifadf**: el F≈82 se debía al bug de escala del
      HAC (mismo `_newey_west_hac`), ya CORREGIDO (ver sección "Detección de
      estacionalidad (HAC F)"). Reverificar sobre un caso con `ifadf>0` que el F
      residual ahora es razonable; si aún dispara, sería media estacional
      determinista no absorbida (test válido).

---

## Detección de estacionalidad (HAC F) — RESUELTO (jul-2026)

- [x] **Bug de escala en el HAC (RESUELTO).** El F de ART estaba inflado ~n
      (100–300×) → falso positivo del WTI. Causa: en
      `seasonal_detection._newey_west_hac`, la "carne" S se dividía por n
      (`S=(xu.T@xu)/n`), pero la varianza sandwich de β̂ es
      `(X'X)⁻¹·[Σ xₜxₜ'uₜ²]·(X'X)⁻¹` con la SUMA, no el promedio →
      `cov_hac = Var(β̂)/n` → F ×n. Comprobado con el caso White (L=0, iid →
      debe dar σ²(X'X)⁻¹). FIX: quitar el `/n` (S y cross como sumas). Verificado
      con datos reales (`Data/IPC.xlsx`, n=262): WTI pasa de F=255.9 [SÍ✗] a
      **F=0.98 [no] ✓** (drvarma OLS=0.94); IPC_ES 24.2, IPC_DE 17.5, CPI 11.5 →
      siguen SÍ. **REVISIÓN DE AMBOS:** el HAC bien escalado ≈ el OLS de drvarma en
      las 5 series (drvarma NO es inferior; ART tenía el bug). El HAC es el método
      más principled (robusto a autocorrelación) y coincide con drvarma. Un test
      (`test_seasonality_mentions_b2`) validaba el falso positivo sobre el PCE
      (deflactor de consumo, DESESTACIONALIZADO → F~1 correcto); actualizado a usar
      una serie sintética estacional. 63 tests de estacionalidad pasan. También
      corrige (misma función) el F≈82 espurio de estacionalidad residual con ifadf.

<details><summary>Diagnóstico original (histórico)</summary>

- [ ] **Discrepancia ART vs drvarma en la detección de estacionalidad determinista.**
      Mismo método nominal (regresión armónica en base diferenciada d=1 + F-test HAC),
      resultados muy distintos en magnitud y, en el caso límite, en conclusión:

      | serie  | ART (`detect_seasonality`/Call 3) | drvarma (`deseasonalize_raw`) | conclusión |
      |--------|-----------------------------------|-------------------------------|-----------|
      | WTI    | **F=272.2, p=0.000 → SÍ**         | **F=1.44, p=0.157 → NO**      | **CHOCAN** |
      | IPC_ES | F=19372                           | F=64.6                        | ambos SÍ  |
      | IPC_FR | F=7169                            | F=32.2                        | ambos SÍ  |
      | IPC_DE | F=7423                            | F=21.96                       | ambos SÍ  |

      El F de ART es ~**100–300× el de drvarma** de forma sistemática. En series
      fuertemente estacionales (IPC) ambos rechazan y no se nota; en una serie
      débil/no estacional (**WTI**, ≈paseo aleatorio) ART da un **falso positivo**
      (detecta estacionalidad) mientras drvarma concluye correctamente que **no la hay**.
      Económicamente el crudo no tiene estacionalidad determinista robusta (el patrón
      Ene/Feb/Nov/Dic recoge desplomes de otoño 2008/2014, no un ciclo repetible) →
      la conclusión sensata es la de drvarma.

      → Revisar el cálculo del estadístico F-HAC en ART (`detect_seasonality` /
        `harmonic_regression_*` / `diagnostic_hac_f_test`): la inflación sistemática
        sugiere un error de **normalización/escala** (¿χ² en vez de F?, ¿gl mal?,
        ¿matriz HAC sin escalar por n o por el factor correcto?). Contrastar contra
        la implementación de drvarma (`deseason.c` + `harmonic_regression_differenced_basis`),
        que parece la referencia correcta, y unificar para evitar falsos positivos.

</details>

---

## SPS zona euro — aplicación empírica del paper SF_MEG (jul-2026)

Objetivo: construir un **Sistema de Predicción y Seguimiento (SPS)** para la zona
euro con modelos univariantes ARIMA-HSM de **todos los IPC de la zona euro**, como
aplicación empírica del artículo SF_MEG (`~/Dropbox/SF_MEG/Borrador/SF_MEG.tex`,
Hybrid Seasonal Models). ART articula la parte MEG. Casos previos en `cases/`
(IPC_ES/DE/FR). Identificación **frecuencia por frecuencia** con el **par
confirmatorio**: DCD/MEG (lado MA, nula determinista) + Shin–Fuller AR_f (lado AR,
nula raíz unitaria estacional).

### Tarea 1 — Actualizar los valores críticos del MEG (no interpolados)
- [ ] En `src/art/formal_tests.py`, sustituir el `_DCD_CRIT_MA_F` **interpolado**
      (complejo 1.07/2.02/4.52) por los **derivados por Monte Carlo** del paper
      (ley s=2). Bare complejo, finito por n (interpolar en n):
      n=120 → 1.12/2.06/4.64; n=240 → 1.13/2.07/4.52; n=480 → 1.10/2.04/4.53;
      n=960 → 1.11/2.03/4.52; asintótico 1.11/2.04/4.52. Frecuencias de raíz real
      (tendencia f=0, Nyquist f=s/2) mantienen la ley MA(1) s=1 = 1.00/1.94/4.41.
      Documentar que los críticos **realistas** (con deterministas) son bastante
      mayores en n pequeño (n=120: 1.63/2.87/5.81 al 10/5/1%) y que el estimador
      libre de fue **está sesgado** en la frontera de 2º orden (usar perfilado, no
      el optimizador libre). Ref: `research/sf_meg/final_table.py`.

### Tarea 2 — Factorizar AR(p) e identificar AR_f (migrar Root a Python)
- [ ] Migrar `/home/david/Dropbox/SRC/Root/**Root-1.01**` (la versión BUENA;
      `root-1.02` tiene `malloc(orden-1)` → overflow = segfault en orden alto) a
      `src/art/roots.py`. Usar `np.roots` (robusto). Factorizar el AR(p) normalizado
      `1−c₁B−…−cₚBᵖ` en factores reales `(1−a₁B)` y complejos `(1−a₁B−a₂B²)`.
      Para cada par complejo (raíz z): `r=1/|z|`, `ω=|arg(z)|` (CORREGIR la fórmula
      buggy `atan(...)/(2π)` de la versión C), armónico `k=ω·s/(2π)`, periodo
      `2π/ω`. **Identificar AR_f candidatos**: par complejo con ω≈ armónico
      estacional y módulo r≈1. **Oro puro**: fue puede estimar el AR factorizado o
      SIN factorizar → factorizar el AR(p) libre estimado revela AR_f ocultos.
- [x] Integrado como tool MCP `ar_factorization(inp_path, sper)` en
      `src/art/mcp_server.py`: carga el modelo ajustado, reconstruye los coeficientes
      AR estimados (libres de `model.params`, fijos de `model.ar`), factoriza cada
      factor AR con `art.roots.factor_ar` y reporta factores + candidatos AR_f.
      Verificado end-to-end (revela AR_f oculto k≈3, r≈0.9 en un AR(3) libre).
      33 tools registradas.

### Tarea 3 — Diseño del caso empírico (tras 1 y 2)
- [ ] Recopilar los IPC de la zona euro (fuente: Eurostat HICP). Construir modelos
      univariantes ARIMA-HSM (λ, d, D/armónicos, intervenciones, ARMA) por país.
- [ ] Aplicar el par confirmatorio frecuencia por frecuencia (DCD + SF AR_f);
      documentar los casos de cuasi-cancelación (desacuerdo del par).
- [ ] Redactar la sección de aplicación empírica del paper con los resultados.

## Un ejemplo de función de transferencia, con los papeles de aplicación (ago-2026)

La FLT `ω(B)/δ(B)` es una de las tres cosas que distinguen a `fue` —respuesta
**dinámica** a un input, no un coeficiente estático— y en `fue/docs/MODEL.md`
§2.1 está escrita formalmente. Lo que falta es un **ejemplo de aplicación**, y
su sitio es aquí y no en el motor: `fue` estima la FLT que se le especifique;
decidir `(b, s, r)` y qué input corresponde a qué incidente es criterio, que es
lo que hace `art`.

Material disponible, en `fue/literature/`:

* **García-Hiernaux y Guerrero (2021)**, «Price convergence: representation and
  testing», *Economic Modelling* 104, 105641 — la fase de transición de un
  proceso de convergencia **es** un input determinista pasado por una FLT: `ω`
  es cuánto recorre, `δ` la velocidad, y la fecha de inicio es la del input. La
  forma y el punto de arranque se **estiman**, y las definiciones implican
  restricciones sobre los parámetros que se contrastan.
* **García-Hiernaux, González-Pérez y Guerrero (2023)**, «Eurozone prices: a
  tale of convergence and divergence», *Economic Modelling* 126, 106418 — el
  mismo marco sobre precios relativos de la UEM, 2001-2020, identificando fecha,
  forma y velocidad de cada proceso.

(Los otros dos de esa carpeta no son aplicaciones: `518-2013-11-11-JAM102.pdf`
es Mauricio (2002) en *JTSA* 23(4) —el `JTSA02` que cita el código— y `9720.pdf`
es Relloso Pereda (1997), ICAE WP 9720.)

**No sobrelaborar**: basta un
ejemplo con un incidente real, su `(b, s, r)`, la ganancia a largo plazo
`g = ω(1)/δ(1)` y el contraste de simplificación —que ya está documentado en
`fue/docs/FORMAL_TESTS.md` §6—. Lo que enseña es la diferencia entre «el efecto
se instala» y «el efecto se absorbe», que es lo que un escalón y un impulso
compensado dicen y un regresor estático no puede decir.
