# Separating the assistant from the engine

*A proposal for `mtram` and `sima`, with the symbol inventory measured rather
than estimated. The target is the arrangement `art` already has, and the
argument for it is the suite's own design principle — not symmetry.*

---

## 1. Why, and it is not tidiness

`ARCHITECTURE.md` §4 already draws the line:

> **Evidence** (deterministic, reproducible): the engines and the analysis
> modules. **Judgement**: Claude, through the MCP protocol.

Today `drtran/mcp_server.py` contains `_what_the_transfer_bought`,
`_certificado`, the equation rendering and the art-format diagnosis. That is
**judgement, shipped inside the engine's package**. The packaging contradicts the
document. `art` got it right — which is why `art-tseries` is a legitimate library
with or without an MCP — and `mtram` and `sima` did not.

David's framing: **logos and mythos**. The engine is logos — formal, computable,
checkable against an oracle. The assistant is mythos in the old sense, not the
false one: the mode that works by narrative, worked example and argument, which
is exactly how Box-Jenkins judgement is transmitted and why it "worked
wonderfully mainly if you were Box or Jenkins". The two are different kinds of
knowledge and they should be different artefacts.

Three costs of the current arrangement, all measured this week:

* **Touching the assistant moves the engine.** `drtran` went 0.2.2 → 0.2.3 →
  0.2.4 for documentation and a warnings filter. Users had to move their exact-ML
  estimation engine three times for changes that never touched it.
* **The engine drags the assistant's dependencies.** `drtran[mcp]` pulls
  matplotlib and jinja2. An estimation engine does not need a template engine.
* **Discovery.** A directory of MCP servers found `art` and not `mtram` or
  `sima`, partly because no package is named after them.

---

## 2. The inventory — `mtram` → `drtran`

**33 symbols across 10 modules, and only THREE are outside `drtran.__all__`.**
The boundary is nearly there already; my first estimate of "eight" was a sloppy
regex and is corrected here.

| symbol | from | status | what to do |
|---|---|---|---|
| `common_window` | `cast` | **private** | **promote.** It answers "do these series share a window", which is an analyst's question and the assistant must be able to ask it |
| `delta_operator` | `cast` | **private** | **promote.** Same: Δ(1) is a fact about the specification, and `check_operators` exists to report it |
| `report_fit` | `cli` | **private** | **move to the assistant.** It is presentation, and it living in `cli` is why the server imports from the CLI — a smell in itself |

Everything else is already public: `load_pre`, `fit`, `identify`,
`identify_network`, `impulse_response`, `forecast`, `level_band`,
`variance_decomposition`, `build_cast_spec`, `Link`, `x0_from_pre`,
`standard_errors`, `build_slots`, `read_cns`, `write_inp`, `next_inp_path`,
`rolling_evaluation`, `fixed_window_fit`, `check_acyclic`, `check_scale`,
`fitted_model`, `x0_full`, `loglik`, and the `report_*` family.

**So the engine's API is 30/33 already declared.** Two promotions and one move,
and the seam is real.

## 3. The inventory — `sima` → `drvarma`

**10 symbols, six private.** Proportionally worse, absolutely smaller, and — as
David notes — this is the one nobody has worked on yet, which makes it the
cheapest place to build the arrangement correctly from the start.

| symbol | from | status | what to do |
|---|---|---|---|
| `deseasonalize_raw` | `deseason` | private | **promote.** Measured this week: deseasonalising moves the contemporaneous correlation from 0.23 to 0.51 on the pass-through pair. A decision that consequential must be reachable and reportable |
| `ccf`, `qccf` | `diagnostics` | private | **promote.** They are identification evidence, the same class as drtran's public `identify` |
| `irf_fevd_bands` | `irf` | private | **promote.** The bands are what make an IRF readable |
| `_draw_ccf_panel`, `_snap_cmax` | `plots` | private | **move to the assistant.** Drawing panels is presentation; the underscore already says so |

Public and staying so: `Model`, `MultiSeries`, `diagnostics`, `transform`.

---

## 4. The order, and why it is not "split first"

1. **`<engine>/assistant/`** — lift the judgement layer out of `mcp_server.py`
   into its own subpackage, mirroring art's `describe.py` / `policy.py`. No
   packaging change yet. This is where `report_fit`, the panel drawing, the
   equation rendering and `_what_the_transfer_bought` go.
2. **Declare the API** — the five promotions above enter `__all__`, with the
   docstrings that a public symbol owes.
3. **Split the batteries.** drtran's 404 tests take 26 minutes largely because
   the server rides with the engine.
4. **Then `mtram-tseries` and `sima-tseries`**, which by that point is mechanical.

Doing 4 before 2 ships a package whose dependency is undeclared internals, and
leaves two exits: promote them anyway, or pin `mtram-tseries==X` to
`drtran==X` — which hands the coupling back through the front door and buys a
package to maintain in exchange for nothing.

---

## 5. What makes this architecture right FOR AN MCP ENVIRONMENT

This is the part that does not follow from ordinary library design, and it is
where I would put the judgement David asked for.

### 5.1 The seam is "what the model reads"

In an MCP server the docstrings and the server instructions are **the product** —
art's own changelog says so. So the rule that decides what goes where is not
"which layer computes it" but:

> **Everything the model reads belongs to the assistant. The engine ships
> numbers and never argues.**

Instructions, tool docstrings, the generated `TOOLS.md`, the presentation, the
arguments for and against a decision — all assistant. That is a sharper rule
than "presentation vs computation" and it settles the ambiguous cases: a
`report_*` function that renders a table is assistant; a function that returns
the numbers in that table is engine.

### 5.2 The engine must carry its own caveats AS DATA

The handoff from logos to mythos only works if the engine states its own
limits in a form the assistant can narrate. drtran already does this in three
places, and they should become a pattern rather than three good instincts:

* `ifault` and `termcode` — did it converge, and how;
* `delta_warnings` — the operators differ, so the gain is wrong by Δ(1);
* the optimality gap of the diagonal gate — were these files optima.

**Generalise it**: every engine result carries a machine-readable list of its
own caveats, and the assistant is what turns them into sentences. An engine that
returns a number with no way to say "and here is what is doubtful about it"
forces the assistant to either invent the caveat or hide it. Both are worse than
the number being unavailable.

### 5.3 The assistant needs tests of a different kind

Engine tests check numbers. Assistant tests must check **what it says** — and
this week produced real examples: that `estimate` announces a dispatched cast,
that `check_operators` warns on mismatch and stays silent on a match, that every
tool is actually registered. Those are not slower engine tests; they are a
different discipline, and they belong with the code they test.

### 5.4 The failure mode to design against: drift

Independent versioning lets the assistant promise what the engine no longer
does — a docstring that lies through the model, which is worse than a wrong
number because the analyst never sees the code. Two guards, both cheap:

* the assistant's battery runs against the engine version it declares;
* `TOOLS.md` stays **generated**, so human documentation cannot diverge from
  what the model is told.

### 5.5 And the one thing not to copy from art

art's `Description.recommendation` computes a recommendation with hard-wired
heuristics, which `ARCHITECTURE.md` §4 itself flags: **two judges at once**, the
engine's heuristic and the model, able to contradict each other and to anchor
the analyst before either has reasoned. If `mtram` and `sima` grow an assistant
layer, it should emit **evidence plus the menu of decisions with arguments for
and against**, and leave the verdict to the model and the analyst. Copy art's
separation; do not copy its one leak.

---

## 6. Effort, honestly

Steps 1–2 are a day's work each for `drtran`, less for `drvarma` — the server is
17 % of that package against 31 % of drtran's. Step 3 is mechanical. Step 4 is
naming and release plumbing, plus two new entries in the suite's install matrix.

`sima` is the one to do first. Nobody has worked on it, its docstrings are
measurably the thinnest of the three (mean 412 characters against art's 963,
with `diagnose` at 116), and building the arrangement there costs least and
teaches most before touching `mtram`, which is in daily use.
