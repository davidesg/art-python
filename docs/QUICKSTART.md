# ATSW — Quickstart (EN / ES)

**ATSW** (A/ART Time Series Workshop) is a Box-Jenkins-Treadway suite for
univariate time series: exact maximum-likelihood estimation (ARMAX + transfer
functions), forecasting, identification, diagnosis and formal tests — plus an
**MCP server** that lets an LLM (Claude) drive the whole methodology.

---

## English

### 1. Install

```bash
pip install atsw
```

This pulls the whole suite: `fue` (estimation + forecasting engine), `pyfug`
(graphics) and `art-tseries` (model building, diagnosis, tests + the `art-mcp`
server). `fue` has a C engine; if your machine lacks the build toolchain or GSL,
it falls back automatically to a pure-Python implementation — nothing to do.

> Requires Python ≥ 3.10.

### 2a. Use it with Claude (recommended)

Connect the MCP server to Claude Code (or any MCP client):

```bash
claude mcp add art -- art-mcp
```

Then just talk to Claude:

> "Analyse this monthly series for me." *(attach a CSV/Excel, or point to an `.inp`)*

ART will ask whether you want a **guided** analysis (step by step, with graphs
and your confirmation at each decision) or an **autonomous** one (full automatic
pipeline ending in a final model). It supplies the evidence — graphs, tests,
numbers — and you (and/or Claude) supply the judgement at each Box-Jenkins node.

### 2b. Use it as a plain Python library (no Claude needed)

```python
import fue
from art.describe import describe_boxcox, describe_identification, model_equation

ts, _ = fue.inp.load("series.inp")        # load a series
print(describe_boxcox(ts).summary)         # Box-Cox transformation analysis
print(describe_identification(ts).summary) # ACF/PACF identification
```

Estimation and forecasting (FUF) live in `fue`; the CLI tool `fuf` forecasts
from an estimated model. See `docs/TOOLS.md` for the full API surface.

### Background — a modern Box-Jenkins-Treadway

The Box-Jenkins analysis was enormously popular at its launch as a process for
building ARMA models (with extensions). The models themselves are simple, but the
iterative building process is a case of *false simplicity*: in practice it worked
beautifully **if you were Box, Jenkins, or one of their disciples**. Its main
difficulty has always been training analysts to make the decisions the process
demands — decisions often guided by heuristics. ATSW combines that *criterion*
with statistical methods in a modern form; AI — with its limitations — supplies
the criterion and suggestions a well-trained analyst would offer.

The analysis here is **not** the canonical Box-Jenkins: it follows the extended
version of **Arthur B. Treadway** (a disciple of Gwilym Jenkins), which adds
elements and heuristics drawn from his work on the Forecasting and Monitoring
Services (SPS) of the Spanish economy. Forecasting is one goal of an ARMAX model
— arguably an unbeatable one — but univariate analysis is also the foundation of
more sophisticated relational analysis. These univariate forecasting models
should be the **measuring stick** for more sophisticated ones: if you cannot beat
their forecasts, your model has a problem and you should rethink it.

### 3. Where to go next

- `AGENTS.md`, `llms.txt` — how an LLM agent should operate the suite.
- `docs/TOOLS.md` — every analysis tool and what it returns.
- `docs/ARCHITECTURE.md` — the design and the *evidence-vs-criterion* philosophy.
- `CASE_STUDIES.md` + `demo_chile_ipc.py` — worked, reproducible examples.

---

## Español

### 1. Instalación

```bash
pip install atsw
```

Esto instala toda la suite: `fue` (motor de estimación + previsión), `pyfug`
(gráficos) y `art-tseries` (construcción de modelos, diagnosis, contrastes + el
servidor `art-mcp`). `fue` tiene un motor en C; si tu máquina no tiene compilador
o GSL, cae automáticamente a una implementación puro-Python — no hay que hacer
nada.

> Requiere Python ≥ 3.10.

### 2a. Úsalo con Claude (recomendado)

Conecta el servidor MCP a Claude Code (o cualquier cliente MCP):

```bash
claude mcp add art -- art-mcp
```

Y a partir de ahí, habla con Claude:

> "Analízame esta serie mensual." *(adjunta un CSV/Excel, o indica un `.inp`)*

ART te preguntará si quieres un análisis **GUIADO** (paso a paso, con gráficos y
tu confirmación en cada decisión) o **AUTÓNOMO** (pipeline automático completo que
termina en un modelo final). ART aporta la evidencia —gráficos, contrastes,
números— y tú (y/o Claude) aportáis el criterio en cada nodo de decisión
Box-Jenkins.

### 2b. Úsalo como librería Python pura (sin Claude)

```python
import fue
from art.describe import describe_boxcox, describe_identification, model_equation

ts, _ = fue.inp.load("series.inp")        # carga una serie
print(describe_boxcox(ts).summary)         # análisis de transformación Box-Cox
print(describe_identification(ts).summary) # identificación ACF/PACF
```

La estimación y la previsión (FUF) viven en `fue`; el comando `fuf` genera
previsiones desde un modelo estimado. La superficie completa del API está en
`docs/TOOLS.md`.

### Contexto — un Box-Jenkins-Treadway moderno

El análisis de Box-Jenkins fue enormemente popular en su lanzamiento como proceso
de construcción de modelos ARMA (con extensiones). Aunque los modelos son
simples, el proceso iterativo de construcción es un caso de *falsa simplicidad*:
en la práctica funcionaba muy bien **si eras Box, Jenkins o uno de sus
discípulos**. Su principal dificultad siempre ha sido el entrenamiento de los
analistas en la toma de decisiones que el proceso exige, muchas veces guiada por
heurísticos. ATSW combina ese *criterio* con métodos estadísticos en una versión
moderna; la IA —con sus limitaciones— aporta el criterio y las sugerencias que
proporcionaría un analista entrenado.

El análisis que se presenta aquí **no** es el canónico de Box y Jenkins: sigue la
versión con extensiones de **Arthur B. Treadway** (discípulo de Gwilym Jenkins),
que añade elementos y heurísticos producto de su experiencia en la producción de
los Servicios de Previsión y Seguimiento (SPS) de la economía española. La
previsión es uno de los objetivos al construir un modelo ARMAX —quizá imbatible
en previsión—, pero el análisis univariante es además la base de un análisis de
relaciones más sofisticado. Estos modelos univariantes deberían ser la **regla de
medida** de modelos más sofisticados: si no puedes mejorar sus previsiones, tu
modelo tiene algún problema y deberías repensarlo.

### 3. Para seguir

- `AGENTS.md`, `llms.txt` — cómo debe operar la suite un agente LLM.
- `docs/TOOLS.md` — cada herramienta de análisis y qué devuelve.
- `docs/ARCHITECTURE.md` — el diseño y la filosofía *evidencia-vs-criterio*.
- `CASE_STUDIES.md` + `demo_chile_ipc.py` — ejemplos resueltos y reproducibles.

---

PyPI: [`atsw`](https://pypi.org/project/atsw/) ·
[`fue`](https://pypi.org/project/fue/) ·
[`pyfug`](https://pypi.org/project/pyfug/) ·
[`art-tseries`](https://pypi.org/project/art-tseries/) ·
GPL-2.0-or-later © David E. Guerrero.
