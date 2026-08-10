# Changelog — art-tseries / atsw

This monorepo ships **art-tseries** (Box-Jenkins-Treadway toolkit + MCP server, at
the repo root) and **atsw** (the umbrella meta-package, in `atsw-suite/`). See
`bugs/` for the full reports. Release tags: `art-v*` (art-tseries), `atsw-v*` (atsw).

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
