# ATSW — A Time Series Workshop

The Box-Jenkins-Treadway suite: exact maximum-likelihood estimation of
univariate models, transfer functions and VARMA, with three MCP assistants so
the whole methodology can be run **by conversation**.

```
pip install atsw
```

## The ladder

The suite is one process, and the order is not a convention — it is a
dependency. Each rung produces the input the next one needs.

| rung | tool | you get |
|---|---|---|
| 1 | **`art`** (35 tools) | identification: λ, d, D, the seasonality frequency by frequency, the orders, the interventions → an `.inp` |
| 2 | **`fue`** | exact-ML estimation and the diagnosis → an `.out` and a `.pre` |
| 3 | **`mtram`** (21 tools) | transfer functions and networks: a directional model with a gain |
| 3′ | **`sima`** (15 tools) | simultaneous VARMA: both equations, impulse responses, variance decomposition |

Rungs 3 and 3′ are alternatives, not a sequence. Which one fits depends on what
you are prepared to assume — the `sima` example ends on exactly that question.

**And the univariate model is the measuring stick.** If a multivariate model
cannot beat its forecasts, the multivariate model is what needs rethinking.

## The examples run

Both series the worked examples use **ship inside the package**, so every node
can be reproduced:

```python
import atsw
atsw.example_path("IPC_ES.csv")    # Spanish CPI, 216 obs, 2002-01…2019-12
atsw.example_path("WTI.csv")       # oil, same window
```

[**How to run them**](RUN_THE_EXAMPLES.md) — the prompts to paste, and what to
expect.

## Where to start

* **New to the suite** — read the [`art` worked example](WORKED_EXAMPLE_ART.md).
  It follows one real series through every decision node, twice: once for
  forecasting and once as the input to a transfer model. The nodes are the same
  and some of the decisions are not, which is the part hardest to learn from a
  manual.
* **Building a transfer model** — [`mtram`](WORKED_EXAMPLE_MTRAM.md).
* **Building a VARMA** — [`sima`](WORKED_EXAMPLE_SIMA.md).
* **Writing files by hand or by program** — [File formats](FILE_FORMATS.md).
  Read the first section before anything else: there are two `.inp` dialects in
  this suite and they are not interchangeable.

## Per-package documentation

| package | what it documents |
|---|---|
| [art-tseries](https://github.com/davidesg/art-python/tree/master/docs) | quickstart, the 35 `art` tools, architecture |
| [drtran](https://github.com/davidesg/drtran-python/tree/master/docs) | the school's practice, the decision nodes, the ladder as an optimisation, the 21 `mtram` tools |
| [drvarma](https://github.com/davidesg/drvarma-python/tree/master/docs) | user and developer guides, the multivariate `.inp`, the 15 `sima` tools |

Every tool reference is **generated from the docstrings**. In an MCP server the
docstring is what the model reads, so the page you see and the instruction the
assistant receives are the same text by construction.

## Methodology

The analysis is not the canonical Box-Jenkins one but the version extended by
**Arthur B. Treadway**, a disciple of Gwilym Jenkins, shaped by his work on the
Forecasting and Monitoring Services of the Spanish economy. Box-Jenkins is a
case of *false simplicity*: the ARMA models are simple, but the iterative
building process worked wonderfully mainly if you were Box, Jenkins or one of
their disciples. The hard part is the judgement, and that is what the assistants
are for.
