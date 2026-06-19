# ART — Box-Jenkins-Treadway time series toolkit + MCP server

`art-tseries` (ART) builds univariate time series models following the
**Box-Jenkins-Treadway** methodology: an iterative, decision-driven process that
uses graphical tools and formal tests to identify, estimate, diagnose and refine
a model until it is adequate and parsimonious.

ART is the orchestration layer of a four-part suite:

| Package | Role |
|---------|------|
| **[fue](https://pypi.org/project/fue/)** | Exact maximum-likelihood estimation (ARMAX + transfer functions) and **FUF** forecasting. C engine with a pure-Python fallback. |
| **pyfug** | High-definition graphics for time series analysis. |
| **ART** (`art-tseries`) | Identification, model building, diagnosis, formal tests, versioning — and an **MCP server** that exposes all of this to an LLM. |

The Box-Jenkins-Treadway loop needs *judgement* at each decision node. ART
supplies the evidence (graphs, tests, numbers); a human analyst and/or Claude
supply the criterion. Two modes:

- **Guided** — analyst + Claude: Claude proposes with arguments, the analyst decides.
- **Autonomous** — Claude/heuristic decides every step and presents a final model.

## Install

```bash
pip install art-tseries          # pulls fue + pyfug automatically
```

This installs the `art-mcp` command (the MCP server).

## Use as an MCP server (Claude Code, etc.)

```bash
claude mcp add art -- art-mcp
```

Then ask Claude to analyse a series. ART will ask whether you want a **guided**
or **autonomous** analysis and drive the workflow from there.

## Use as a library

```python
import fue
from art.describe import describe_boxcox, describe_identification, model_equation

ts, _ = fue.inp.load("series.inp")
print(describe_boxcox(ts).summary)
```

## Methodology

The model-building process is iterative and sequential: each estimation starts
from the previous likelihood optimum (the `.pre` of the previous model), and
every step produces a `.pre` (estimated parameters as initial values) and a
`.out` (results), mirroring `fue`. Decisions and changes are recorded in a
`guion.json` audit trail. See `docs/ARCHITECTURE.md` for the full design and the
evidence-vs-criterion philosophy.

## License

GPL-2.0-or-later. © David E. Guerrero.
