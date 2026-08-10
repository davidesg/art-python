# Documenting the suite: art, mtram and sima

*A plan, and an answer to the second question — how the documentation should be
shown. Everything in §1 is measured, not assumed.*

---

## 1. What the survey found

**The three servers, and what they document about themselves:**

| server | package | tools | tool reference | user guide | worked example |
|---|---|---|---|---|---|
| **art** | `art-tseries` | 35 | `TOOLS.md`, ~32 entries | Quickstart (EN/ES) | — |
| **mtram** | `drtran` | 21 | **none** | — | — |
| **sima** | `drvarma` | 15 | **none** | `USER_GUIDE.md` | — |

Seventy-one tools across the suite, and two of the three servers have no
reference at all. **No repository has an `examples/` directory.**

**Language is almost a non-issue.** Measured over every document in the three
repositories, all of drtran's and all of drvarma's are in English. Two
exceptions, and only one matters:

* `art/docs/ARCHITECTURE.md` is **entirely in Spanish — and it ships** in
  `art-tseries 0.1.7`. That is the one real language defect.
* `art/docs/QUICKSTART.md` is deliberately bilingual (`Quickstart (EN / ES)`).
  That is a choice, not an oversight, and §4 argues for keeping it.

`drtran/docs/SCHOOL_PRACTICE_STUDY.md` reads as Spanish-heavy to a word counter
because it QUOTES the theses. Quotations stay in the original; that is correct
and must not be "fixed".

**sima is the best-organised of the three, and should be the template.** It
already has `USER_GUIDE.md`, `DEVELOPER_GUIDE.md`, an explicit `MANIFEST.in`
that lists what ships, and — importantly — **`INP_FORMAT.md`**, the file-format
specification I had recorded as missing from the suite. It is not missing; it is
in the wrong place, because the format is the SUITE's contract and not
drvarma's.

**Packaging** (after this week's releases): art and drtran declare five URLs
each and ship a curated document set; drvarma declares three (no `Documentation`,
no `Changelog`) and its `MANIFEST.in` ships `STATUS.md` and `PURE_PYTHON_PLAN.md`,
which are working notes.

---

## 2. The shape: one shape, three servers

An analyst who learns to read one server's documentation should be able to
navigate the other two without relearning. So each package documents its own
server in the SAME four parts — sima's structure, generalised:

```
USER_GUIDE.md      what this server is for, where it sits on the ladder,
                   and the decisions it expects the analyst to make
TOOLS.md           every tool: the QUESTION it answers, its arguments,
                   what it returns, and what it does NOT do
EXAMPLE.md         one real series, end to end, with real output pasted in
DEVELOPER_GUIDE.md architecture, engine, and what may not be broken
```

And **`INP_FORMAT.md` moves up to the suite level**: `.inp` / `.out` / `.pre`
are what the three servers exchange, so the specification cannot belong to one
of them. `drtran/docs/LADDER_AS_OPTIMISATION.md` already states the CONTRACT
(what each file asserts, and the fixed-point invariant); drvarma's
`INP_FORMAT.md` states the SYNTAX. Together they are the specification, and they
should be one document with two sections.

---

## 3. atsw documents the suite, not the parts

`atsw` is the umbrella, and today its PyPI page is a 104-line README. What it
should carry:

* **The ladder in one page.** Which server you use when, and why the order is
  `art → fue → mtram / sima`. This does not exist anywhere; it is currently
  folklore distributed across three READMEs.
* **One worked example per server**, complete and runnable, with real output:
  * `art` — a monthly price index: identification, estimation, diagnosis.
  * `mtram` — a pass-through: two `.pre` files, the diagonal gate, the link,
    the gain. WTI → a national CPI is the obvious case and it is already the
    suite's regression test.
  * `sima` — a small VARMA where the joint model earns its place over the
    univariate ones.
* **The file formats**, per §2.
* **The install matrix**: what `pip install atsw` brings, and the version floors
  that matter (`drtran>=0.2.0` is not housekeeping — below it the transfer gain
  is wrong whenever the operators differ).

---

## 4. Language

**English for everything that ships.** Two exceptions, both deliberate:

1. **Quotations from the sources stay in Spanish**, with a translation when the
   argument depends on the wording. Relloso, Muñoz, Brajín and Treadway's own
   notes are the authority being cited; translating a citation silently changes
   what is being claimed.
2. **The Quickstart stays bilingual.** The suite's first audience is a Spanish
   school of time-series analysis, and the Quickstart is the one document a
   newcomer reads before deciding whether to continue. Everything downstream of
   it can be English.

The one thing to fix is `art/docs/ARCHITECTURE.md`: Spanish, shipped, and
developer-facing. Translate it.

---

## 5. How the documentation should be SHOWN

Four surfaces, and they are not alternatives — each reaches a reader the others
do not.

**(0) The README, on PyPI.** PyPI renders the README and nothing else, and
resolves relative links against the Homepage. So: absolute links, and the README
must work as a standalone page. This is done for art and drtran; atsw's needs
the §3 content.

**(1) Inside the distribution.** `MANIFEST.in`, curated by audience. Readable
offline and locked to the version installed, which matters because a tool
reference that describes a different release is worse than none. Done for art
and drtran; drvarma still ships two working notes.

**(2) GitHub.** Free, already rendering, and the target of every absolute link.
It is what the URLs point at today and it is sufficient for developers.

**(3) A site for the suite — MkDocs Material on GitHub Pages.** The sources are
already Markdown, `mkdocs.yml` is the only new file, and the build is static.
This is what an analyst deserves: one navigation, one search box, one place
where the ladder is a path and not four repositories.

```
Start here     what ATSW is · the ladder in one page · install
art            user guide · tools · worked example
mtram          user guide · tools · worked example
sima           user guide · tools · worked example
Formats        .inp / .out / .pre — syntax and contract
Methodology    the school's practice, decision nodes, forecasting diagnosis
Developers     architecture per package · the record of defects
```

**(4) And the surface nobody has counted as documentation: the docstrings.**
In an MCP server the tool docstrings are what the MODEL reads, and art's own
changelog says it outright — *"todo lo de esta versión es lo que Claude LEE; en
un servidor MCP las instrucciones son el producto"*. That makes the suite's
documentation have two audiences, human and model, and **the failure mode is
divergence**: a rule stated in `TOOLS.md` but absent from the docstring is a
rule the model does not apply, and a docstring that promises what the tool no
longer does is a lie told to the analyst through the model.

Concretely: `TOOLS.md` should be GENERATED from the docstrings, not written
beside them. Then they cannot drift, and the reference is complete by
construction — which also closes the gap of art's 32 entries for 35 tools.

---

## 6. Order of work

1. **Translate `art/docs/ARCHITECTURE.md`.** It ships today in Spanish; it is
   the only outright language defect.
2. **Generate `TOOLS.md` from the docstrings**, for the three servers. This is a
   script, it removes the drift risk permanently, and it fills mtram's and
   sima's missing references — 36 tools currently undocumented for humans.
3. **One worked example per server**, in `atsw`. Real series, real output. The
   mtram one exists already as a regression test and only needs writing up.
4. **Lift `INP_FORMAT.md` to the suite**, merged with the contract half of
   `LADDER_AS_OPTIMISATION.md`.
5. **drvarma's packaging**: `Documentation` and `Changelog` URLs, and stop
   shipping `STATUS.md` and `PURE_PYTHON_PLAN.md`.
6. **`mkdocs.yml` and the first build**, with the structure in §5.

Steps 1 and 2 are the ones that change what a user can find out today. Step 6 is
the one that makes it look like a suite.
