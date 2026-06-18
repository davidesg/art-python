# ATWS — Box-Jenkins-Treadway time series suite

`atws` is an **umbrella package**: installing it pulls the complete Box-Jenkins-
Treadway time series suite plus the MCP server, in one step.

```bash
pip install atws
```

This installs:

| Component | Package | Role |
|-----------|---------|------|
| **FUE** (+ FUF) | `fue` | Exact ML estimation (ARMAX + transfer functions) and forecasting |
| **FUG** | `pyfug` | Jenkins-Treadway high-definition graphics |
| **ART** | `art-tseries` | Model building, diagnosis, formal tests + **MCP server** (`art-mcp`) |

## Use with an LLM (MCP)

```bash
claude mcp add art -- art-mcp
```

Ask Claude to analyse a time series; it will offer a **guided** (analyst decides,
Claude advises) or **autonomous** (Claude decides) Box-Jenkins-Treadway workflow.

## Components on PyPI

Each component is also installable on its own — `atws` just fixes a compatible
set. See each package's README and `art-tseries`'s `docs/ARCHITECTURE.md` for the
full design.

## License

GPL-2.0-or-later. © David E. Guerrero.
