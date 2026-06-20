# ATSW — Box-Jenkins-Treadway time series suite

`atsw` is an **umbrella package**: installing it pulls the complete Box-Jenkins-
Treadway time series suite plus the MCP server, in one step.

```bash
pip install atsw
```

It installs `fue` (exact ML estimation of ARMAX / transfer functions +
forecasting), `pyfug` (graphics) and `art-tseries` (model building, diagnosis,
formal tests + the `art-mcp` MCP server). Requires Python ≥ 3.10. `fue` has a C
engine with an automatic pure-Python fallback, so it installs everywhere.

| Component | Package | Role |
|-----------|---------|------|
| **FUE** (+ FUF) | `fue` | Exact ML estimation (ARMAX + transfer functions) and forecasting |
| **FUG** | `pyfug` | High-definition graphics for time series analysis |
| **ART** | `art-tseries` | Model building, diagnosis, formal tests + **MCP server** (`art-mcp`) |

## Use with an LLM (recommended)

```bash
claude mcp add art -- art-mcp
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

The Box-Jenkins analysis was enormously popular at its launch as a process for
building ARMA models (with extensions). The models themselves are simple, but the
iterative building process is a case of *false simplicity*: in practice the method
worked beautifully **if you were Box, Jenkins, or one of their disciples**. Its
main difficulty has always been training analysts to make the decisions the
process demands — decisions often guided by heuristics.

ATSW combines that *criterion* with statistical methods to build the models in a
modern form. AI — with its limitations — supplies the criterion and the
suggestions a well-trained time series analyst would offer.

The analysis presented here is **not** the canonical Box-Jenkins. It follows the
extended version of **Arthur B. Treadway** (a disciple of Gwilym Jenkins), which
adds elements and heuristics drawn from his experience producing the Forecasting
and Monitoring Services (SPS) of the Spanish economy.

Forecasting is one of the goals of building an ARMAX model — and arguably an
unbeatable one — but univariate analysis is also the foundation of more
sophisticated relational analysis. These univariate forecasting models should be
the **measuring stick** for more sophisticated models: if you cannot beat their
forecasts, your model has a problem and you should rethink it.

## Components on PyPI

Each component is also installable on its own — `atsw` just fixes a compatible
set: [`fue`](https://pypi.org/project/fue/) ·
[`pyfug`](https://pypi.org/project/pyfug/) ·
[`art-tseries`](https://pypi.org/project/art-tseries/). See `art-tseries`'s
`AGENTS.md`, `docs/QUICKSTART.md`, `docs/TOOLS.md` and `docs/ARCHITECTURE.md` for
the full design, the operating guide and the *evidence-vs-criterion* philosophy.

## License

GPL-2.0-or-later. © David E. Guerrero.
