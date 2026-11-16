---
id: BUG-0260
title: compare_versions suppresses the comparison between models that differ only in lambda or in the rescaling factor
status: fixed
severity: medium
component: mcp_server
found_in: 0.2.5
fixed_in: 0.2.6
reported: 2026-11-16
reporter: David / Claude — what was left of the scale round (atsw-gui docs/ESTUDIO-escala.md §5)
tags: [scale, refactor, boxcox, compare_versions, loglik]
references:
  - src/art/mcp_server.py (compare_versions; the guion map's operator and scale warnings)
  - fue.scale.loglik_y (fue 0.1.22)
  - BUG-0051 (different operators: still suppressed), BUG-0085 (the factor), BUG-0257 (a factor other than 100 can be right), BUG-0258 (σ̂ₐ as presented)
  - bugs/BUG-0260-repro/repro.py
---

## Summary

`compare_versions` put lambda in the "operator" that makes two likelihoods
incomparable, and treated a different rescaling factor the same way: it printed
"— no comp." for Δ loglik, AIC and BIC, suppressed the LR, and between factors
told the analyst it was "the same model badly labelled: re-estimate it".

Neither lambda nor the factor changes the dependent variable, only its units.
With the same differencing operator and the same sample, the log-likelihood in
the units of y,

    l_y = l + n·ln(factor) + (lambda − 1)·Σ ln y_t

over the n observations of the likelihood (the Jacobian of factor·BoxCox), is
the likelihood of the observed series: exactly invariant to the factor
(atsw-gui docs/ESTUDIO-escala.md §5) and the standard comparison between
lambdas.

```
factor 100 vs 1, same model: Δ loglik = — no comp.     (fixed: +0.000)
logs vs levels:              Δ loglik = — no comp.     (fixed: -0.108)
```

## Impact

Medium. Choosing between logs and levels, the decision the Box-Cox step makes,
could not be checked with the tool made for comparing versions; and since 0.2.5
(BUG-0257) a factor other than 100 is chosen on purpose when 100 leaves the
series outside the optimiser's band, so the advice to re-estimate at 100 was
wrong.

## Reproduction

`bugs/BUG-0260-repro/repro.py`: a quarterly random walk in logs about 100; the
same model with factor 100 and 1, and the series in logs and in levels. Exits
1 while either comparison is suppressed or the first Δ is away from 0.

## Fix

The operator is `d`, `D` and `ifadf`. When lambda or the factor differ and the
two models estimate on the same sample, loglik, AIC, BIC and the LR are
computed from `fue.scale.loglik_y`, with a note saying so (they are not the
`.out`'s figures). On different samples the Δ is still suppressed. σ̂ₐ is
shown with `fue.scale.display_scale`, as the equation shows it. The guion map
keeps its stored, engine-unit columns and its warnings, and says which groups
`compare_versions` can compare.
