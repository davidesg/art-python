# ATSW — Announcement / Mensaje de anuncio

Two ready-to-send versions (short email / mailing list). Pick one or adapt.
Dos versiones listas para enviar (email corto / lista de distribución).

---

## English

**Subject:** ATSW — a Box-Jenkins time series workshop you can drive by talking to an AI

Dear colleagues,

I'd like to share **ATSW** (A Time Series Workshop), a Python suite for building
univariate time series models the Box-Jenkins-Treadway way: exact
maximum-likelihood ARMAX / transfer-function estimation, forecasting,
identification, diagnosis and formal tests.

What's different: ATSW ships an **MCP server**, so you can run the whole
methodology *by conversation* with Claude. The tool supplies the evidence
(graphs, tests, numbers); you and the AI supply the judgement at each decision
node — guided step by step, or fully autonomous. It also works as a plain Python
library if you don't use Claude.

A bit of background. Box-Jenkins is a case of *false simplicity*: the ARMA models
are simple, but the iterative building process worked wonderfully mainly if you
were Box, Jenkins, or one of their disciples — the hard part is training analysts
in the (often heuristic) decisions. ATSW pairs that criterion with statistical
methods, and AI — with its limitations — supplies the criterion and suggestions a
trained analyst would offer. The methodology here is not the canonical one but the
extended version of **Arthur B. Treadway** (a disciple of Gwilym Jenkins), shaped
by his work on the Forecasting and Monitoring Services of the Spanish economy. A
useful rule of thumb: these univariate forecasts are a *measuring stick* — if a
fancier model can't beat them, rethink it.

Get started in two minutes:

```bash
pip install atsw
claude mcp add art -- art-mcp          # optional: drive it from Claude
```

Then ask Claude to analyse one of your own series, or run the worked example in
`demo_chile_ipc.py`. Quickstart and docs are bundled (`docs/QUICKSTART.md`,
`AGENTS.md`, `CASE_STUDIES.md`).

PyPI: https://pypi.org/project/atsw/ — feedback very welcome.

Best,
David

---

## Español

**Asunto:** ATSW — un taller de series temporales Box-Jenkins que manejas hablando con una IA

Estimados colegas:

Quiero compartir **ATSW** (A Time Series Workshop), una suite en Python para
construir modelos de series temporales univariantes con la metodología
Box-Jenkins-Treadway: estimación máximo-verosímil exacta (ARMAX y funciones de
transferencia), previsión, identificación, diagnosis y contrastes formales.

Lo distinto: ATSW incluye un **servidor MCP**, así que puedes ejecutar toda la
metodología *conversando* con Claude. La herramienta aporta la evidencia
(gráficos, contrastes, números); tú y la IA aportáis el criterio en cada nodo de
decisión — guiado paso a paso, o totalmente autónomo. También funciona como
librería Python normal si no usas Claude.

Un poco de contexto. Box-Jenkins es un caso de *falsa simplicidad*: los modelos
ARMA son simples, pero el proceso iterativo de construcción funcionaba de maravilla
sobre todo si eras Box, Jenkins o uno de sus discípulos — lo difícil es entrenar
a los analistas en unas decisiones muchas veces heurísticas. ATSW combina ese
criterio con métodos estadísticos, y la IA —con sus limitaciones— aporta el
criterio y las sugerencias que daría un analista entrenado. La metodología no es
la canónica sino la versión con extensiones de **Arthur B. Treadway** (discípulo
de Gwilym Jenkins), fruto de su trabajo en los Servicios de Previsión y
Seguimiento de la economía española. Y una regla útil: estas previsiones
univariantes son una *regla de medida* — si un modelo más sofisticado no las
mejora, repiénsalo.

Empezar lleva dos minutos:

```bash
pip install atsw
claude mcp add art -- art-mcp          # opcional: manejarlo desde Claude
```

Después pídele a Claude que analice una serie tuya, o ejecuta el ejemplo resuelto
en `demo_chile_ipc.py`. El quickstart y la documentación van incluidos
(`docs/QUICKSTART.md`, `AGENTS.md`, `CASE_STUDIES.md`).

PyPI: https://pypi.org/project/atsw/ — agradezco mucho cualquier comentario.

Un saludo,
David

---

### Versión muy corta (chat / Slack / Twitter-X)

> **ATSW** ya en PyPI: `pip install atsw`. Suite Box-Jenkins-Treadway de series
> temporales (estimación ML exacta + previsión + diagnosis) con servidor MCP para
> manejarla hablando con Claude — guiado o autónomo. También usable como librería
> Python. https://pypi.org/project/atsw/

> **ATSW** is on PyPI: `pip install atsw`. A Box-Jenkins-Treadway time series
> suite (exact ML estimation + forecasting + diagnosis) with an MCP server so you
> can run it by talking to Claude — guided or autonomous. Also a plain Python
> library. https://pypi.org/project/atsw/
