# Where the example data comes from

Both series are **public official or market statistics**, shipped here only so
the worked examples can be run. They are not part of the software and carry
their sources' own terms.

| file | series | source | window |
|---|---|---|---|
| `IPC_ES.csv` | Spanish national CPI, general index | INE (Instituto Nacional de Estadística), series `IPC290751`, base 2025 | 2002-01 … 2019-12 |
| `WTI.csv` | West Texas Intermediate spot price, monthly | EIA / FRED | 2002-01 … 2019-12 |

**Why the window stops in 2019-12.** The examples are teaching material, and
2020 onwards contains the COVID collapse and the 2022 energy shock — two level
breaks that dominate every diagnostic and turn a lesson about identification
into a lesson about interventions. The published analyses these examples follow
truncate at the same point and say so.

Update them from the sources if you want the full sample; nothing in the
examples depends on the truncation except the numbers.
