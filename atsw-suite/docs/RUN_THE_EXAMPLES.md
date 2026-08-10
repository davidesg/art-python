# Running the examples yourself

The three worked examples are not illustrations — they are analyses of two real
series, and **both series ship inside the package** so you can rerun every node
and get the same numbers.

```
pip install atsw
```

```python
>>> import atsw
>>> atsw.example_path("IPC_ES.csv")   # Spanish CPI,  216 obs, 2002-01…2019-12
>>> atsw.example_path("WTI.csv")      # WTI oil spot, same window
>>> atsw.example_path()               # the directory, with PROVENANCE.md
```

Both are public statistics (INE and EIA/FRED). They stop in 2019-12 on purpose:
2020 onwards contains the COVID collapse and the 2022 energy shock, and those
two level breaks turn a lesson about identification into a lesson about
interventions.

---

## The normal way: ask the assistant

This suite is driven **by conversation**. You do not run a script; you tell
Claude what you want and it drives the tools, showing you the evidence at each
node and waiting for your decision. Register the servers once:

```
claude mcp add art   -- art-mcp
claude mcp add mtram -- mtram
claude mcp add sima  -- sima
```

Then paste one of these.

### The `art` example — identification, node by node

> Load `atsw`'s example series `IPC_ES.csv` (you can find it with
> `python -c "import atsw; print(atsw.example_path('IPC_ES.csv'))"`). Take me
> through the GUIDED identification, stopping at every node: the Box-Cox, the
> order of integration, the seasonality frequency by frequency, the ARMA orders
> and the interventions. At each one show me the evidence, tell me what you
> would decide and why, and give me the argument against your own choice before
> I confirm.

That last sentence is the one that matters. The tools produce the evidence; the
value of the assistant is the argument, and asking for the counter-argument is
how you stop it anchoring you.

Compare what you get with `WORKED_EXAMPLE_ART.md`, Part I. Your decisions may
differ from the recorded ones — at the `f=3` frontier they legitimately can —
and that is the point of a guided pipeline rather than a button.

### The same series, for a different purpose

> Now do it again, but the model is going to be the OUTPUT of a transfer model
> whose input is the oil price. Which of the decisions change, and why?

Two of them do. Part II of the same document says which and gives the reason.

### The `mtram` example — the pass-through

> Using `atsw`'s example series, build a transfer model of `IPC_ES` on `WTI`:
> first the univariate models with `art` and `fue`, then load both `.pre` files
> in `mtram`, check the operators, identify the link from the prewhitened CCF
> and estimate. Show me the diagonal gate before anything else, and tell me what
> the gain means in economic terms.

Expect a gain near **0.027**: a permanent 1 % move in oil passes through to
about 0.027 % of the Spanish CPI level.

### The `sima` example — the same pair, simultaneously

> Take the same two series and fit a bivariate VAR with `sima` — logs, one
> regular difference, **and deseasonalise**. Give me the impulse responses and
> the variance decomposition, and tell me what the Cholesky ordering assumes and
> what changes if I reverse it.

The reversal is the point. With a contemporaneous residual correlation near
0.5, how the shared variance is attributed is decided by the ordering, not by
the data.

And **do not skip the deseasonalising**. Without it that correlation comes out
at 0.23 instead of 0.51 and the decomposition changes accordingly — measured in
[Compared with statsmodels](COMPARISON_STATSMODELS.md), which also shows that
`statsmodels.VARMAX` has no seasonal handling at all.

---

## Without an assistant

Every server is also an ordinary Python library, and the CLIs work on their own:

```bash
fue MODEL              # estimate an .inp, write .out and .pre
drtran-py Y.pre X.pre -b 0 -r 0 -s 1     # a transfer model
drvarma DATA.inp -p 1                    # a VARMA
```

You will get the same numbers. What you will not get is the part the examples
are actually about — which question each node is answering, and why one
criterion rather than another. That is what the assistant adds, and it is also
what a colleague would add.

---

## If your numbers differ

Three usual causes, in order of frequency:

1. **A different window.** The examples run 2002-01…2019-12. Including 2020+
   changes every diagnostic.
2. **A different seasonal specification.** Deterministic harmonics and `∇₁₂` are
   not two spellings of one model; on this very series they disagree about the
   pass-through by a factor of five once the operators stop matching. See
   `FILE_FORMATS.md` on `ifadf`, and `WORKED_EXAMPLE_MTRAM.md` on the operators.
3. **A decision you took differently.** Which is allowed, and is why the
   documents record the argument and not only the answer.
