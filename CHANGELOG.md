# Changelog — art-tseries / atsw

This monorepo ships **art-tseries** (Box-Jenkins-Treadway toolkit + MCP server, at
the repo root) and **atsw** (the umbrella meta-package, in `atsw-suite/`). See
`bugs/` for the full reports. Release tags: `art-v*` (art-tseries), `atsw-v*` (atsw).

## art-tseries (sin publicar) — 2026-08-12

**BUG-0011 — el par confirmatorio de f=0 se reportaba partido**, así que sobre
IPC_ES el informe emitía «considerar d+1» como si fuera una conclusión.

Shin-Fuller y el DCD de sobrediferenciación tienen nulas **opuestas** y acotan la
banda de cuasi-cancelación: su desacuerdo no es una contradicción que resolver
eligiendo uno, **es el diagnóstico** (SF_MEG, `tab:compare`). Sobre este modelo el
lado AR da Φ̂₁ᵤ=37.5 («d basta») y el lado MA LR=4.220 («d+1») con el testigo en
θ̂=0.9709 — a tres centésimas de la frontera, literalmente la columna r≈0.95 de la
tabla del paper. Los dos tienen razón, y en esa banda las dos representaciones son
equivalentes en previsión.

Ahora el informe lleva un bloque «Par confirmatorio en f=0», etiqueta la
discrepancia como lo que es, y **la recomendación dice que NO se cambie `d` con
esta evidencia** — que se decida por parsimonia o comparando previsiones fuera de
muestra. Se imprimen además los dos avisos que el paper documenta y que sólo
muerden aquí: que el crítico usado es el de la ley desnuda s=1 mientras el modelo
lleva deterministas **resonantes** con la raíz unitaria de f=0 (el paper mide
pile-up 0.927 frente a 0.6575), y que con θ̂<1 la ℓ(θ=1) se evalúa justo donde el
perfil de fue da un salto errático.

Quedan abiertas las dos partes de calibración —verosimilitud exacta de frontera y
crítico corregido por resonancia—, que tocan los valores críticos del paper.

**BUG-0012 — los factores `ifadf` se imprimían fuera del paréntesis de μ**, así
que la ecuación impresa no era de media cero y por tanto no era el modelo que se
había ajustado. Sólo renderizado: la estimación siempre fue correcta.

```
antes  (1 − 0.4074·B) (1 + B + B²)_f=4 (∇Nₜ − 0.4642) = …
ahora  (1 − 0.4074·B) ((1 + B + B²)_f=4 ∇Nₜ − 0.4642) = …
```

`ifadf` es diferenciación, igual que ∇, así que va dentro: μ es la media de lo
que queda **después de toda** la diferenciación. Leída la forma antigua, la media
de la expresión era `A_f(1)·(m − μ)` = 3·(0.1545 − 0.4642) = −0.93.

Con la colocación correcta la deriva se lee directamente de la ecuación y sale
invariante en las cuatro frecuencias —0.1544, 0.1552, 0.1547 y 0.1545 con
ganancias 1, 2, 3 y 2—, que es la definición funcionando. La forma antigua hacía
que eso pareciera una inconsistencia entre el factor AR regular y el estacional,
y llegó a costar un informe de bug falso.

Doce tests, seis de los cuales fallan contra el código previo, en tres capas: que
el factor esté dentro, que **ningún** operador de diferenciación quede fuera —el
contraste que atrapa la clase entera— y el invariante numérico μ̂ ≈ A_f(1)·m.

**BUG-0009 — el testigo de f=0 se apropiaba de la ranura del de Nyquist.**
`dcd_overdiff_regular` construía su candidato con «reemplaza cualquier MA regular
existente», y esa ranura no siempre está libre: cuando la frecuencia de Nyquist
se ha reformulado a estocástica, el testigo que vive ahí es el suyo. Misma forma
—un MA regular de primer orden— y fronteras opuestas: en el convenio `(1 − θB)`,
θ=+1 cancela `(1−B)` y θ=−1 cancela `(1+B)`. Sólo así cancela cada uno su
diferencia, y por eso compartir ranura no podía funcionar.

Ahora cada frecuencia lleva su testigo y no se comparten: con Nyquist estocástica
el MA existente **no es competencia** —es lo que cancela `(1+B)`— así que se
conserva y el de f=0 va a ranura propia. Donde no hay colisión, el
comportamiento es idéntico al anterior.

- **La dirección del defecto no era la que la ficha predecía.** Se esperaba que
  el testigo borrado empujara a un `d+1` espurio; en el caso medido hizo lo
  contrario — la `(1+B)` huérfana tiraba del testigo de f=0 hacia −1 y el LR caía
  POR DEBAJO del crítico. Lo que importa es que **el veredicto se movía**:
  reformular f=6 no cambia `d`, así que el contraste del orden regular debe dar
  lo mismo. Antes 4.220 → 1.859; ahora 4.220 → 4.257. El test de regresión afirma
  esa invariancia, no el veredicto.
- **Y el error de categoría, dicho:** f=s/2 no lo gobierna `d`. Su orden de
  integración es `ifadf[s/2]`; `d` es el orden en la frecuencia cero.
- **Calibración comprobada primero**, antes de tocar nada: sobre un paseo
  aleatorio con deriva `∇w_t − μ = a_t`, sin armónicos ni ARMA, 25 muestras — 4 %
  de falsos positivos contra un 5 % nominal, y θ̂ exactamente en la frontera en 12
  de 25. La maquinaria del contraste es sana; lo que falla es lo que el candidato
  arrastra.

**BUG-0015 y BUG-0016 — dos decisiones más que la capa guiada tomaba y el
autónomo no tenía por dónde pedir.** La misma forma que BUG-0013, por tercera y
cuarta vez, y **se arreglan juntas porque interactúan**: con λ=1 el IPC_ES no
sobrediferenciaba, así que arreglar la regla índice sola habría hecho que la otra
disparara en más series y pareciera una regresión del arreglo.

- **`decide_domain` es la séptima decisión del protocolo `Policy`**, y cierra el
  hueco general que BUG-0015 identificó: *la política tomaba evidencia pero nunca
  dominio*. La regla índice —λ=0 sobre un índice de precios, cuya base es una
  convención— vivía sólo en `guided_identification`, así que el autónomo partía
  una familia de ocho IPC en 4 logs y 4 niveles por el signo de un gap que nunca
  pasó de 0.304 en valor absoluto. `_INDEX_PREFIXES` aparece ahora **cero veces**
  en `mcp_server.py`: una copia de la regla, no dos.
- **Declarado gana a inferido.** El detector infiere del nombre, que es evidencia
  débil, así que la respuesta se REGISTRA (`PipelineResult.domain`) en vez de
  aplicarse en silencio y `build_model(domain=…)` la declara. El propio caso lo
  justifica: `EMU` es un índice de precios y su nombre no lo dice.
- **`decide_d` recibe la decisión estacional** y topa d en 1 cuando hay
  estacionalidad detectada y sin tratar. El ADF no lleva términos estacionales,
  así que el patrón infla su error típico y sesga hacia no rechazar: las dos
  series que sobrediferenciaban eran exactamente las dos primeras del ranking de
  estacionalidad, con corte limpio en F-HAC ≈ 50. El tope va en la POLÍTICA:
  `recommended_d` sigue diciendo 2 y en la tabla se ve que se topó.
- **Y de d=0 sólo se pasa a d=1, nunca a d=2** (`max_step=1` por defecto), haya
  estacionalidad o no. No es prudencia: la pregunta que se hace desde el nivel no
  es «¿cuántas diferencias?» sino «¿hace falta AL MENOS una?». La estacionalidad
  se lee normalmente sobre una serie ya diferenciada una vez, así que desde d=0
  la pregunta por la SEGUNDA nunca se ha puesto; saltar 0 → 2 responde a algo que
  nadie preguntó. Y lo obvio primero: si d=1 es lo obvio, d=2 no se alcanza de un
  salto. Lo que cierra la objeción de que esto subdiferenciaría una I(2) genuina
  es que **no se pierde nada por empezar bajo**: ADF, KPSS y el gráfico son
  herramientas de especificación INICIAL, y el contraste de verdad sobre el orden
  de integración se hace al FINAL, sobre un modelo adecuado y bien especificado
  —`dcd_overdiff_regular`, Shin-Fuller—, que es donde este flujo ya los pone.
  Desde `current_d=1` la segunda diferencia sí se alcanza, porque para entonces
  la pregunta ya se hizo.

Las ocho series salen ahora en logs y con d=1, y IPC_JP sigue sin media — el
control de BUG-0013 intacto. 23 tests, 20 de los cuales fallan contra el código
previo.

**BUG-0018 — las series anuales (freq=1) no llegaban al final del flujo.** Y el
diagnóstico cambió al medirlo: de los tres defectos que el TODO llevaba anotados
desde el 8-jul, **los tres estaban ya arreglados** —el `alter` espurio por el
guardia `freq >= 2` de BUG-0005, la cabecera de `_write_inp`, y el `x_pad` de
pyfug— y lo que bloqueaba de verdad era un cuarto sin anotar.

- **`detect_seasonality` dividía por cero.** `num_harmonics = s - 1`, que en anual
  es CERO, y el F-test HAC divide por él. No era un resultado degenerado: era una
  excepción lanzada antes de correr ningún contraste, y se llevaba el pipeline
  autónomo entero (`run_full` → `describe_seasonality`) sin haber estimado nada.
  Una serie anual no tiene frecuencias estacionales, así que el contraste **no
  aplica** en vez de fallar: se devuelve pronto un resultado bien formado, que
  `decide_seasonal_structure` lee como decisión "A" con `n_harmonics=0` — lo que
  un modelo anual necesita.
- **`_write_bare_inp` seguía escribiendo el año repetido** en el campo del periodo
  inicial mientras `_write_inp` ya lo hacía bien. El arreglo no viajó de un
  escritor al otro, que es el argumento para unificarlos. La cabecera mal escrita
  no rompía el round-trip —el parser la tolera en anual—, así que era latente.

Con esto una serie anual completa el flujo: identificación, estimación, diagnosis
con figura y contrastes formales. 9 tests nuevos, 6 de los cuales fallan contra el
código previo; los otros 3 son guardias de los defectos ya arreglados.

**BUG-0010 — podar un armónico anulaba el barrido MEG entero, en silencio.** Se
quitaba un par cos/sin no significativo y el MEG no perdía esa frecuencia:
perdía **todas**. `meg()` validaba las frecuencias por adelantado, así que una
irreformulable abortaba el barrido; `describe_formal_tests` la llamaba dentro de
`_try(..., [])`, que hace indistinguible «lanzó» de «no se pidió»; y
`_meg_suitable()` seguía siendo cierto, así que tampoco saltaba el aviso de «MEG
no aplica». La sección desaparecía del informe sin una palabra y la recomendación
pasaba a «El modelo es adecuado» sobre un modelo con f=3 estocástica dentro.

- **El barrido reporta lo que no puede contrastar.** La validación pasa al bucle
  y devuelve `status='skipped'` con la razón. Un skip es un resultado, no una
  ausencia. Barrido y petición explícita se separan: `meg(model)` salta y
  reporta, `meg(model, frequencies=[f])` lanza con el mensaje accionable — que es
  lo que `meg_frequency` necesita y lo que los dos tests de guarda ya afirmaban.
- **El informe no puede callarse.** Las saltadas se imprimen con su razón y
  **entran en la recomendación**, así que ya no puede cerrarse con «adecuado» una
  frecuencia sin mirar. Un fallo inesperado del MEG se anuncia en vez de
  devolver lista vacía.
- **Y la guía, que es lo que llevaba a podar primero.** La nota de
  sobreparametrización avisa cuando el par incluye armónicos estacionales; los
  docstrings de `seasonal_param_analysis` y `test_seasonal_simplification`
  declaran la precondición; y la ETAPA 4 de las instrucciones abre con el orden.
  El argumento, que no es de fontanería: **una t baja en un armónico es evidencia
  A FAVOR de que esa frecuencia sea estocástica**, no de que no exista, así que
  podar por significación borra justo las frecuencias que el MEG necesita mirar.
  En IPC_ES los dos criterios salen casi ortogonales en las dos direcciones a la
  vez: f=5 (|t|=0.29 y 1.27, la primera que cualquier filtro borra) llevaba la
  segunda evidencia más fuerte de estocasticidad, y f=3 (|t|=5.4 y 2.1) es la que
  ES estocástica. La regla general de contrastar sobre un modelo parsimonioso no
  alcanza a los parámetros que SON la hipótesis.



**La media deja de perderse entre el modelo determinista y el ARMA.** Dos
defectos con un solo síntoma: se estimaba un modelo con armónicos y media, y al
añadirle la estructura ARMA volvía sin media.

- **BUG-0014 — el contrato `.pre` se respeta.** `_build_arma_on_model` heredaba
  las intervenciones y el `ifadf` del modelo base pero no la media: con
  `estimate_mu=False` la tiraba (0.154472 → 0) y con `True` la volvía a derivar
  de la serie (0.160085) en vez de llevarla. Once deterministas se heredaban
  idénticos y la media no, en el mismo constructor. Ahora `estimate_mu` tiene
  tres estados y `None` —el de por defecto— hereda `estimate_mu` y `mu0` del
  base. Y **`base_pre_path` pasa de 0 menciones a 4 en las instrucciones**: la
  máquina existía, nada mandaba a usarla, y la Llamada 4 pasaba el `.pre` como
  `inp_path`, que es el modo "desde cero".

- **BUG-0013 — la política decide la media.** No es que `run_full` se olvidara
  de ponerla: **no tenía por dónde pedirla**. El protocolo `Policy` declaraba
  seis decisiones y ninguna era la media, así que toda serie modelada de forma
  autónoma salía con μ clavado en cero. Se añade `decide_mu`, séptima decisión,
  con la regla que el propio informe proponía: la deriva de la serie
  diferenciada contra su error típico, `|t| > 2` (`THRESHOLDS["mu_drift"]`).
  Reproduce las ocho series del informe, **Japón incluido** —la única en que
  `estimate_mu=False` es la respuesta correcta, t=1.08—, que es lo que lo hace
  un contraste y no una regla que siempre dice que sí. `build_model` acepta
  `estimate_mu` con el mismo convenio de `-1` que `lam`/`d`/`p`/`q`.

- **La pregunta de la media se hacía sobre los residuos equivocados.** La
  Llamada 4 medía la media de los residuos de un modelo que YA tenía μ ajustado,
  leía t ≈ 0 y recomendaba `estimate_mu=False` sobre una serie con t=5.40. Ahora
  contrasta siempre la deriva de la diferenciada.

En IPC_FR los residuos pasan de media 0.11 con t ≈ 8.5 —y `APROBADA`— a t=0.00.
La capa 3 (el contraste de media residual en `diagnose`, ya existente) hizo su
trabajo: falló al cambiar la política, porque IPC_ES ya no llega sin deriva. El
test ahora induce el defecto a propósito.

## art-tseries 0.1.10 / atsw 1.2.5 — 2026-08-10

Corrige el silenciado de 0.1.9, que no silenciaba. El aviso de
`pydantic_settings` no salta al IMPORTAR FastMCP sino al CONSTRUIRLO, y el
filtro estaba puesto alrededor del import, dentro de un `catch_warnings` que se
deshacía justo antes de que hiciera falta. Ahora va a nivel de módulo, acotado
por mensaje y por módulo de origen. Comprobado con `-W always`: cero avisos.

## art-tseries 0.1.9 / atsw 1.2.4 — 2026-08-10

Limpieza para una versión estable. Sin cambios en los motores.

- **`__version__` se lee de los metadatos instalados** en vez de ser una
  constante escrita a mano. `art.__version__` decía `0.1.2` con la 0.1.8
  instalada, y `atsw` iba a derivar igual: dos sitios que cambiar es uno de más,
  y el que deriva es siempre el que nadie construye. `drtran` ya lo hacía así.
- **Silenciado el aviso de `pydantic_settings` al arrancar el servidor MCP.**
  `IncompleteFieldDefinitionWarning` sobre el campo `lifespan` sale de la
  interacción entre versiones de dependencias, no de este código, y no toca el
  protocolo --stdout sale limpio--; pero un servidor de stdio que escribe en
  stderr al arrancar puede leerse como un fallo. Silenciado ACOTADO a ese aviso
  y sólo alrededor del import que lo dispara.

## art-tseries 0.1.8 — 2026-08-10

Documentación. Sin cambios en el motor ni en el servidor.

- **`docs/TOOLS.md` se GENERA de los docstrings** (`tools/gen_tools_md.py`), y
  cubre las **35** herramientas: la versión escrita a mano cubría 32. En un
  servidor MCP el docstring es lo que lee el MODELO, así que la referencia y la
  instrucción son ahora el mismo texto por construcción y no pueden divergir.
  El generador lee las herramientas REGISTRADAS, no el código, así que una que
  exista y no esté registrada aparece como ausente también aquí.
- **`docs/ARCHITECTURE.md` traducido al inglés.** Era el único documento que se
  publicaba en español. Corregido de paso su recuento de herramientas.
- `docs/SUITE_DOCUMENTATION_PLAN.md`: el inventario de la documentación de los
  tres servidores y qué hacer con ella.

## art-tseries 0.1.7 — 2026-08-10

Corrige el EMPAQUETADO de 0.1.6, no el código: el motor y el servidor son los
mismos. La 0.1.6 llevaba `recursive-include docs *.md` en su `MANIFEST.in` y eso
metió en el sdist siete documentos INTERNOS --un borrador de email de difusión,
el anuncio, el procedimiento de publicación, las notas de estado y los 18
informes de `bugs/`-- que no son documentación de usuario. **No se expuso
ninguna credencial**: esos ficheros mencionan que existen tokens, nunca sus
valores.

- `docs/email_final.md` eliminado del repositorio.
- El `MANIFEST.in` LISTA los documentos uno a uno y además EXCLUYE
  explícitamente los internos. Las dos cosas hacen falta: `include` sólo añade,
  nunca quita, y el `SOURCES.txt` del `egg-info` anterior arrastra lo que se
  incluyó alguna vez, así que una lista blanca por sí sola no basta --comprobado
  construyendo, no supuesto--.
- El README gana una sección **Documentation** con enlaces ABSOLUTOS. PyPI
  renderiza sólo el README y resuelve los relativos contra la Homepage, así que
  fuera del repositorio se rompen.

Viajan ahora: README, CHANGELOG, TODO, QUICKSTART, TOOLS, ARCHITECTURE y
RESCALING_ARCHITECTURE.

La 0.1.6 sigue descargable con los internos dentro: PyPI no permite reemplazar
una versión ya subida.

## art-tseries 0.1.6 — 2026-08-10

Publica lo que quedó fuera de 0.1.5: el cambio de código llegó DESPUÉS del
empaquetado, así que la 0.1.5 de PyPI no lo lleva. Y arregla los metadatos, que
no declaraban ni una sola URL.

- **BUG-0013, capa 3: la media residual se CONTRASTA, no sólo se resta.**
  `diagnosis` expone `mean` y `mean_t = r̄/(s/√n)`, y el bucle autónomo para con
  `residuals_ok` en vez de con `clean`. La distinción no es cosmética: fundir
  las dos hacía que el guiado añadiera DOS intervenciones persiguiendo una media
  que faltaba, y separarlas deja el veredicto (`clean`) intacto para el analista
  mientras el bucle usa el criterio que le corresponde.
- **Metadatos.** `[project.urls]` con Homepage, Documentation, Issues y
  Changelog —no había ninguna, así que la página de PyPI no llevaba a ningún
  sitio— y un `MANIFEST.in` que mete `docs/`, `CHANGELOG.md` y `bugs/` en el
  sdist, de modo que la documentación se lee sin red.

Batería: 474 pasan, 21 saltados.

## art-tseries 0.1.5 — 2026-08-08

Todo lo de esta versión es lo que Claude LEE. En un servidor MCP las
instrucciones son el producto, y aquí había criterio escrito que no llegaba.

- **El empate AR(1)/MA(1) llega por fin a las instrucciones.** La regla estaba
  razonada y con citas en `policy.py:decide_orders` —incluido el caso IPC_ES,
  ΔAIC=1.12 favoreciendo nominalmente al MA(1) y AR(1) elegido— pero
  `_INSTRUCTIONS` no la mencionaba ni una vez, así que se aplicaba cuando Claude
  abría ese fichero por casualidad. Ahora está en LLAMADA 4 con el argumento
  entero, el alcance estricto (sólo precios/índices, sólo ante empate genuino) y
  la obligación de presentar SIEMPRE las dos opciones: un criterio teórico que
  no se enuncia deja de ser criterio y pasa a ser sesgo.
  El argumento contra el MA(1) va con números: su competidor lleva θ<0, y un
  IMA(1,1) con θ<0 es un EWMA con suavizado (1−θ)>1, fuera de rango, cuyos pesos
  de previsión sobre los NIVELES alternan de signo (θ=−0.7 → 1.700, −1.190,
  +0.833, −0.583…).
- **El aviso de estacionalidad va donde se DETECTA** (LLAMADA 3), no al abrir el
  análisis: preguntar antes pide una decisión sobre algo que aún no se sabe si
  existe. Y dice qué cuesta la elección aguas abajo — determinista para análisis
  multivariante, a veces estocástica para previsión.
- **HSM, y "(experimental)" dicho con precisión.** Las líneas de estacionalidad
  son dos (determinista y estocástica); HSM —Hybrid Seasonal Models, MEG en la
  literatura española— es la forma canónica de Abraham y Box (1978) que las
  anida. La etiqueta es una salvaguardia, no una advertencia sobre el método:
  los modelos son de 1978, la idea está en HEGY, y DCD y Shin-Fuller están
  publicados. Lo nuevo son los valores críticos por Monte Carlo, que difieren
  por un margen marginal de los publicados, y la implementación.
- **BUG-0011: causa establecida.** No es el ARMA, son los armónicos
  deterministas: quitarlos invierte el veredicto (LR 4.220 → 0.193). La
  precondición del docstring nombra al competidor equivocado. Sigue ABIERTO —
  el porqué no está entendido y no se toca hasta que lo esté.
- **BUG-0009 y BUG-0010 verificados y reproducidos**, ambos abiertos.
- TODO: la pregunta del OBJETIVO (multivariante o previsión), analizada y sin
  implementar — el objetivo no manda sobre los datos, y ésa es la parte difícil.

## atsw 1.1.0 — 2026-07-27

- Adds **drvarma>=0.1.1** to the suite — multivariate VARMA (exact-ML estimation,
  forecasting with bands, impulse responses, FEVD, diagnostics, volatility). So
  `pip install atsw` now pulls the univariate (fue/ART) *and* multivariate (drvarma)
  engines. Description/keywords updated (VARMA, multivariate).

## atsw 1.0.4 — 2026-07-23

- Pins bumped to **fue>=0.1.8** and **art-tseries>=0.1.3** so `pip install atsw`
  pulls the rescaling/forecast fixes and the naming/language pass.
- Description reworked: **"A Time Series Workshop"** — the fue + pyfug + ART suite,
  with the MCP server surfaced for discoverability.

## art-tseries 0.1.3 — 2026-07-23

Requires **fue>=0.1.8**. Rescaling made a single source of truth, seasonal-seed fix,
and a naming/language pass for the (English-majority) audience.

- **Rescaling P1 — `refactor` as single source of truth**
  (`docs/RESCALING_ARCHITECTURE.md`). No file/function hardcodes `100`: `_make_model`
  sets `model.refactor`; `_mu_seed(refactor)` seeds on the already-rescaled series;
  `_build_arma_on_model` forwards the base refactor; `_write_inp` writes
  `model.refactor`. Invariant `in-memory forecast == .pre round-trip forecast` now
  holds (`tests/test_rescaling_invariant.py`).
- **BUG-0006** (seed): the seasonal-AR seed was Yule-Walker'd on the
  harmonic-*containing* differenced series (positive `r(12)`), giving a positive Φ
  seed against the noise's negative Φ → spurious optimum for the US AR(2)×AR(2). Now
  the deterministic harmonics (+ Nyquist alter) are regressed out first; the seed is
  taken on the residual noise. Removes the per-country seed workaround.
- **BUG-0005** (seasonal package): the deterministic seasonal block (harmonic pairs +
  Nyquist alter) is now gated on a `seasonal` flag instead of `n_harmonics>0`, so
  low-frequency seasonal models are handled correctly.
- **Naming:** ART is now glossed **"A Real-Time Time-Series Analysis"** (Box-Jenkins-
  Treadway methodology retained in the description/README body). No package, module,
  or repo rename.
- **Seasonality routes** renamed from the school labels to the working hypothesis:
  **B1 — Deterministic seasonality** (D=0, harmonics), **B2 — Stochastic seasonality**
  (D=1, seasonal differencing).
- **Language:** the MCP server now instructs the assistant to **always respond in the
  user's language** (default English); user-facing route labels are in English.

## art-tseries 0.1.2 — 2026-07-19

Requires **fue>=0.1.7**. Fixes found reviewing the *Joseph's Cycles* models
(`Cycles/bugs_art_fue.md`); an in-repo bug tracker (`art.bugs` + `art-bug`) was
added, mirroring fue's.

- **BUG-0001** (inp-builder): an untransformed series fit with AR(p)+mean came back
  with μ≈0 and a spurious near-unit AR root absorbing the level, because the `.inp`
  hard-coded a ×100 rescaling while μ was seeded at 0. Added `_mu_seed()` =
  `refactor·mean(∇^d∇_s^D BoxCox_λ(y))` and pass it from `_make_model` /
  `_build_arma_on_model`. Validated: GE (λ=1) μ=126.15, GEP (λ=0) μ=6.7555.
- **BUG-0002** (identification): `recommended_d` required the strict consensus
  (ADF rejects AND KPSS doesn't), so a KPSS rejection over-differenced even when
  ADF rejected the unit root decisively. Now ADF governs: smallest d where ADF
  rejects. GEP d2→0, GE d1→0.
- **BUG-0003** (mcp-tools): `estimate_and_diagnose` gained an opt-in `output_path`
  that persists the `.pre`/`.out` trio via `_persist_pre_out` (previously only
  `confirm_and_estimate`, which carried BUG-0001).
- **BUG-0004** (roots): delta-method SEs for a complex AR(2) factor's damping and
  period in `ar_factorization` (ported from `caracterizar_operadores.car_ar2`,
  matching ABTreadway-Dperar2.xls). `d ± SE`, `per ± SE` when the 2×2 coefficient
  covariance is available.

## atsw 1.0.3 — 2026-07-19

- Floor the suite to the fixed engine/toolkit: `fue>=0.1.7`, `art-tseries>=0.1.2`
  (keeps `pyfug>=2.0`).

## Infrastructure — 2026-07-19

- Both packages now publish to PyPI via **trusted publishing** (OIDC) from GitHub
  Actions: `publish-art.yml` (tag `art-v*`) and `publish-atsw.yml` (tag `atsw-v*`).
  Build-only in the publish job (no install-smoke-test — a suite dependency may be
  unpublished at coordinated-release time).
