# ATSW — Box-Jenkins-Treadway time series suite

`atsw` is an **umbrella package**: installing it pulls the complete Box-Jenkins-
Treadway time series suite plus the MCP server, in one step.

```bash
pip install atsw
```

It installs the estimation engines, the graphics, and **three MCP assistants**.
Requires Python ≥ 3.10. Every engine has a C implementation with an automatic
pure-Python fallback, so the suite installs everywhere.

| Component | Package | Role |
|-----------|---------|------|
| **FUE** (+ FUF) | `fue` | Exact ML estimation (ARMAX + transfer functions) and forecasting |
| **FUG** | `pyfug` | High-definition graphics for time series analysis |
| **ART** | `art-tseries` | Model building, diagnosis, formal tests + the `art-mcp` server |
| **DRTRAN** | `drtran` | Transfer functions and networks by exact ML + the `mtram` server |
| **DRVARMA** | `drvarma` | Multivariate VARMA by exact ML + the `sima` server |

## The three assistants, and when to move between them

They are **separate servers on purpose**. An MCP client sees every connected
server at once, so this is not three tools you have to choose between — it is
one ladder with three rungs, and each assistant knows when to hand over.

| Assistant | Question it answers | Engine |
|---|---|---|
| `art` | One series: what ARIMA model, what interventions? | `fue` |
| `mtram` | How does X move Y? Transfer functions, and networks of them (a DAG) | `drtran` |
| `sima` | Everything moves everything: a simultaneous VARMA | `drvarma` |

`mtram` starts from the `.pre` files `art` writes, so the univariate rung is
already climbed and committed to a file you can read. The handoff to `sima` is
**testable, not a preference**: if the proposed network contains a CYCLE there is
no topological order, the system cannot be written as a triangular VARMA, and it
is therefore simultaneous. `mtram` says so and stops.

## Use with an LLM (recommended)

```bash
claude mcp add art   -- art-mcp     # one series
claude mcp add mtram -- mtram       # transfer functions and networks
claude mcp add sima  -- sima        # simultaneous VARMA
```

Then ask Claude to analyse a series (attach a CSV/Excel, or point to an `.inp`).
ART offers a **guided** workflow (analyst decides, Claude advises step by step,
with graphs and your confirmation at each decision) or an **autonomous** one
(Claude/heuristic decides every step and presents a final model). The suite
supplies the *evidence* — graphs, tests, numbers; you and/or Claude supply the
*criterion* at each Box-Jenkins decision node.

## Use as a plain Python library (no Claude needed)

```python
import fue
from art.describe import describe_boxcox, describe_identification

ts, _ = fue.inp.load("series.inp")
print(describe_boxcox(ts).summary)          # Box-Cox transformation analysis
print(describe_identification(ts).summary)  # ACF/PACF identification
```

Estimation and forecasting (FUF) live in `fue`; the `fuf` command forecasts from
an estimated model.

## Background — a modern Box-Jenkins-Treadway

The Box-Jenkins analysis was tremendously popular at its launch as a process for
building ARMA models (with extensions). The models themselves are simple, but the
iterative building process is a case of *false simplicity*: in practice the method
worked wonderfully **if you were Box, Jenkins, or one of their disciples**. The
real obstacle is training the analyst to make the decisions the process demands —
decisions often guided by heuristics.

ATSW combines that *criterion* with statistical methods to build the models in a
modern form: AI — with its limitations — supplies the criterion and the
suggestions a trained time series analyst would offer.

The analysis presented here is **not** the canonical Box-Jenkins, but the extended
version of **Arthur B. Treadway** (a disciple of Gwilym Jenkins), which adds
elements and heuristics drawn from his experience producing the Forecasting and
Monitoring Services (SPS) of the Spanish economy.

Forecasting is one of the goals of building an ARMAX model — and perhaps an
unbeatable one — but univariate analysis is also the foundation of more
sophisticated relational analysis. These univariate forecasting models should be
the **measuring stick** for more complex ones: if you cannot beat their forecasts,
your model has a problem and you should rethink it.

## Components on PyPI

Each component is also installable on its own — `atsw` just fixes a compatible
set: [`fue`](https://pypi.org/project/fue/) ·
[`pyfug`](https://pypi.org/project/pyfug/) ·
[`art-tseries`](https://pypi.org/project/art-tseries/). See `art-tseries`'s
`AGENTS.md`, `docs/QUICKSTART.md`, `docs/TOOLS.md` and `docs/ARCHITECTURE.md` for
the full design, the operating guide and the *evidence-vs-criterion* philosophy.

## License

GPL-2.0-or-later. © David E. Guerrero.
