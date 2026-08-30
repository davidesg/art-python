# ART — an architectural review

**Written:** 2026-08-27 · **By:** David, from the Bolivia TFM replication ·
**Version reviewed:** 0.1.11 (+ fixes for BUG-0021…0027)

This is not a bug report. It is an attempt to look at the whole after a long run
of individual defects — because when bugs are found and fixed one at a time, the
architecture erodes without anyone deciding that it should.

The occasion was a full replication: three quarterly series, dozens of estimated
models, every node driven interactively, and six defects found and fixed along
the way. Enough exposure to see the shape of the thing rather than its pixels.

---

## 0. The thesis, up front

**The methodology is sound and the instruments are excellent. What is weak is
everything that makes the method *navigable*.**

That weakness is nearly invisible to a human analyst, because a human supplies
from his own head the three things ART does not provide — where he is, what he
has already tried, and how to get back. It is close to fatal for an LLM, which
has none of the three and whose only memory is a transcript that decays, costs
money, and keeps quoting its own earlier mistakes.

The corollary matters as much as the thesis: **the problem is not missing tools.
There is a surplus of tools that are not connected.** Almost everything proposed
below is wiring and state, not new functionality.

---

## 1. What the method requires

Box-Jenkins, in Treadway's extension, is not a procedure. It is an iterative
search in which each step is a *decision*, and the decision is taken by an
analyst looking at instruments.

The right mental image is **a labyrinth**, not a decision tree. A tree suggests
the route is predetermined and that one merely descends it. A labyrinth has:

- a start and an end, joined by the line of correct decisions;
- **dead ends** — and a dead end is not a failure of the method, it is the method
  working;
- and the guarantee that **you can always return to a safe place**: a point whose
  decisions were sound, from which another door can be tried.

Three consequences follow, and they are architectural requirements, not niceties:

1. **The instruments must be at hand at every step**, because the decision is
   taken from them and not from a rule.
2. **Each step must be solid**, because a bad decision contaminates every step
   after it — the contamination is not local.
3. **Backtracking must be a first-class operation**, and it must carry *why* the
   branch was abandoned. That reason is the most valuable thing produced by a
   failed iteration, and the only thing that stops it being tried again.

ART does (1) superbly, does not enforce (2), and does not implement (3).

---

## 2. What was measured

All figures from `src/art/mcp_server.py` at the reviewed version.

### 2.1 The navigation graph is almost empty

| | |
|---|---|
| MCP tools exposed | **35** |
| tools nothing ever suggests (**orphans**) | **28** |
| "next step" edges in the entire server | **8** |

The complete navigable path is:

```
preview_data → load_data → guided_identification → confirm_and_estimate
```

plus four loose edges: `preliminary_outlier_scan → {guided_identification,
suggest_intervention_form}`, `meg_frequency → meg_reformulate`,
`unit_root_analysis → formal_tests`, `batch_build → build_model`.

`confirm_and_estimate` — **the tool that closes every iteration** — emits no
next-step text of its own. What looks like its suggestions is the outlier-scan
block it embeds.

**Why this is not a cosmetic problem.** For an LLM, a tool that nothing mentions
does not exist. It is not "forgotten"; it never enters the action space at all.

Empirically, in a three-series replication with dozens of models, these were
never called once: `get_out_report`, `test_interventions`,
`overparameterization_analysis`, `model_equation_display`, `compare_versions`,
`record_version`, `export_guion`. `ar_factorization` was reached only because the
analyst asked for it by name.

### 2.2 There is no memory of the path

`Guion.entries` is a **flat list**. `GuionEntry` carries `version: int` and
`next_version: str` (free prose).

Occurrences of `parent`, `branch`, `from_version` in `guion.py`: **zero**.

So the guion cannot express *which version descends from which*. It is a log, not
a map. There is no `restore`, no `branch`, no `abandon`. `record_version` only
appends. `compare_versions` compares two **files**, not two guion entries.

**The labyrinth has no map, and the dead ends leave no trace.**

### 2.3 There is no position

Only `guided_identification` says where you are — "Paso 1…4" — and only within
identification. Nothing states where you are in the *cycle*: identify → estimate
→ diagnose → reformulate → formal tests.

And it is stateless by design: *"Sin estado en memoria — cada llamada es
idempotente."* Position is derived from which arguments are still `-1`.

---

## 3. Three layers, three different verdicts

### Layer 1 — the instruments: very good, and the best thing here

The plots are designed, not generated. The tests are the right ones. And most
valuable: **the doctrine is written inside the outputs**, at the point of use —

> *"el modelo nulo del MEG en la frecuencia f **es** el armónico determinista en
> f. Si no se pone, esa frecuencia deja de ser una pregunta: no se puede
> contrastar lo que no está."*

> *"un estadístico bajo en f es evidencia **a favor** de estacionalidad
> estocástica en f."*

That is not documentation. It is reasoning delivered where the decision is taken,
and it is why the substantive nodes of the replication came out right.

`build_model` running **one engine** for both guided and autonomous modes, with
the policy as the only difference, is a genuinely good decision: it makes a
guided-vs-autonomous discrepancy localise to a decision node rather than to a
program.

### Layer 2 — the wiring: broken

28 orphans, 8 edges. See §2.1. Nothing more needs saying except that this is the
cheapest thing on the list to fix.

### Layer 3 — the memory of the path: absent

See §2.2. This is where the labyrinth breaks against the implementation, and it
is the highest-value gap.

---

## 4. Why this weighs more on an LLM

A human analyst at the screen gets three things for free:

| | human analyst | LLM |
|---|---|---|
| **position** | knows where he is because he has been there | only what the last call returned |
| **instruments in view** | the plots stay on screen | they fall out of context |
| **backtracking** | remembers the order, can undo | reasons from its own earlier statements — **including the wrong ones** |

The third row is the dangerous one. When an LLM takes a bad decision it does not
merely contaminate the next step: **it contaminates its own reasoning**, because
it keeps citing itself. In this replication that happened literally — the MEG was
run out of stage, and the model was then reformulated twice on an invalid verdict
and defended with conviction for several turns.

**The failure pattern is the whole argument.** Reviewing every mistake made
during the replication:

| failure | nature |
|---|---|
| MEG run out of stage | **navigation** — nothing said what stage we were at |
| four API signatures mis-called in a row | **navigation** — signatures do not survive in context |
| plots and ACF tables hand-rolled | **navigation** — the tools that do it are orphans |
| `.pre` files written by hand | **navigation** — the convention is not stated in art |
| wrong standard errors published | **navigation** — the `.out` is unreachable (BUG-0029) |

**Not one was a statistical error.** The nodes where evidence was actually
weighed — Box-Cox, the order of integration, the form of the interventions, the
complex AR(2) — came out right, and the ones that went wrong were corrected by
arguments about *method*, not about calculation.

Everything that broke, broke in navigation. That is the diagnosis, and it is why
the fixes below are about wiring and state.

---

## 5. What to do, in order of value

### 5.1 Parentage and status in the guion — highest value, lowest cost

```python
GuionEntry:
    + parent: int | None          # which version this descends from
    + status: "exploring" | "adopted" | "dead-end"
    + why_abandoned: str          # the reason — the thing worth keeping
```

This turns the guion from a record into **the map of the labyrinth**, and enables:

- `guion_branch(from_version)` — return to the safe place and try another door;
- `guion_abandon(version, why)` — mark a dead end **with its reason**, which is
  today discarded entirely.

An assistant that can read *"the MEG was tried here and it was premature"* will
not try it again. Today that knowledge lives only in a transcript that will be
summarised away.

### 5.2 A cycle-state footer on every output

Not a new tool that must itself be discovered — **a footer on every response**,
derivable from the `.inp` plus the guion, computing nothing new:

```
── State ──  series RATIO · version m20 (parent m10)
   settled : λ=0 · d=1 · D=0 harmonics f=1,f=2 · SAR(1)₄ · impulse 2020:2
   pending : outlier 2008:4 · formal tests
   stage   : diagnosis  (formal tests come AFTER, and require clean Q and JB)
   doors   : suggest_intervention_form · guided_identification(pre_path=…) · get_out_report
```

This solves position, instruments and stage doctrine at once. It is the single
highest-leverage output change, because it is *unavoidable* — it appears whether
or not the caller thought to ask.

### 5.3 Wire the orphans — **applied 2026-08-27 (partial, deliberately)**

**Measured after:** 38 tools (three new), **18 orphans** — down from 28.

Wired, and always *at the stage where they are legitimate* rather than from one
particular tool, which is the neighbourhood idea rather than a tree:

| tool | where it now appears |
|---|---|
| `get_out_report` | state footer, every stage |
| `formal_tests` | state footer, **only when the diagnosis is clean** |
| `test_interventions`, `overparameterization_analysis` | state footer, clean stage |
| `residual_outlier_scan` | state footer, when there are extreme residuals |
| `model_histogram` | state footer, when normality fails |
| `ar_factorization` | state footer, when an AR factor has order ≥ 2 |
| `guion_map` | state footer, whenever a guion exists |
| `guion_abandon`, `export_guion` | from `guion_map` itself |
| `unit_root_analysis`, `identification_analysis` | guided_identification, steps 2 and 4 |

**Stopped here on purpose.** The 18 that remain are end products
(`full_report`, `sps_dashboard`, forecasting), entry points already covered by
the instructions (`create_inp`, `load_data`), or deep-dive instruments whose
content is already inlined in the guided flow (`boxcox_analysis`,
`seasonal_analysis`). Wiring those would add text to every output without adding
a decision anyone needs to take — and the cost of length falls on every call.

The one that mattered most was `guion_abandon`: newly built, and nothing pointed
at it. Exactly the trap this review describes, committed while fixing it.

### 5.3 (original) Wire the orphans

Not a decision tree — a tree misrepresents the method, promising a predetermined
route. A **neighbourhood**: *from here, these doors*. The difference is that a
neighbourhood only asserts what is legitimate to attempt now, which is exactly
what the method licenses.

### 5.4 Make the `.out` the closing of a step

A step is **solid** when its decision is recorded together with its evidence. The
`.out` *is* that evidence — parameters with their standard errors, sigma, the
likelihood, the full covariance and correlation matrices — and nothing points to
it (BUG-0029).

Having `confirm_and_estimate` end by directing to `get_out_report` turns "I
estimated a model" into "I closed a node".

### 5.5 One question, one tool, one shape

The outlier scan exists in two incompatible forms — on the series and on the
residuals — one reachable and one locked inside `confirm_and_estimate`
(BUG-0028). Identification exists in two: `identification_analysis` and
`guided_identification` call 4.

For an LLM, two names for one question is an invitation to pick the wrong one.

### 5.6 State the file convention in art

The `.inp` / `.out` / `.pre` convention is written, precisely, in **drtran's** MCP
instructions (`drtran-python/src/drtran/mcp_server.py:80`, with detail in
`docs/LADDER_AS_OPTIMISATION.md`). drtran is a *later* rung. **The three files are
born in art**, and art says nothing — its header presents `.inp` and `.pre` as
interchangeable inputs and adds that "every call is idempotent", which actively
invites re-running on the `.pre`. See BUG-0029.

---

## 6. What not to touch

**The doctrine embedded in the outputs.** It is the best thing in the system and
should be *extended*, not trimmed. Every place where a tool explains why a step
comes where it comes is a place where a wrong turn was prevented.

**One engine for both modes.** `build_model`'s design should be preserved.

And one warning about the natural impulse on reading a review like this: the
temptation is to add tools. Resist it. Of the six proposals above, five are
wiring, state or text; only `guion_branch`/`guion_abandon` is new surface, and
it is small.

---

## 7. Open questions this review does not settle

- **Where does the state footer come from?** Deriving it from the `.inp` plus the
  guion is cheap but assumes a guion exists. Whether to require one — that is,
  whether the guion becomes mandatory rather than optional — is a real design
  decision with a cost, and it is not made here.
- **Does the autonomous lane need the same map?** It has no analyst to backtrack.
  Arguably it needs the dead-end record *more*, because it cannot notice.
- **How much doctrine is too much?** The outputs are already long, and length has
  a token cost that falls on every call. The footer proposal adds to it. There is
  a real trade-off between the doctrine that prevents errors and the context it
  consumes, and this review does not measure it.
