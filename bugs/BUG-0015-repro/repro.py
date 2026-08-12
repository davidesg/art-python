"""BUG-0015 — the INDEX RULE that forces lambda=0 on a price index lives only in
the guided MCP layer, so the autonomous pipeline splits a homogeneous family of
CPI indices between logs and levels on the sign of a noisy statistic.

`guided_identification` (mcp_server.py) prints, and applies:

    ⚠ REGLA ÍNDICE APLICADA: «IPC_ES» es una serie índice sin base natural
      — se impone λ=0 (log) independientemente de las estadísticas Box-Cox.

`policy.decide_lambda` (policy.py:46-53), which is what `run_full` — i.e.
`build_model` and `batch_build` — actually calls, is only:

    gap = boxcox_data.get("gap", 0.0)
    return 0.0 if gap >= 0 else 1.0

There is no index rule in the policy, and no `decide_lambda` override on
`build_model`. Exactly the shape of BUG-0013: a decision the guided layer makes
and the autonomous path has no door to ask for.

`gap` is corr(raw) − corr(log) of the mean–std scatter over 18 annual groups. On
a CPI index the two correlations are both small and noisy, so its SIGN is close
to a coin flip — and it is the sign, not the magnitude, that decides the
transformation.

Eight monthly CPI indices, same source file, same window (2002-01…2019-12,
n=216), same nature. Run:

    python3 bugs/BUG-0015-repro/repro.py

Expected: the family splits roughly in half, and the split is not a property of
the series but of a statistic that is near zero for all of them.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent

SERIES = ["IPC_ES", "IPC_FR", "IPC_DE", "CPI_USA",
          "EMU", "IPC_JP", "IPC_CA", "IPC_UK"]


def main() -> int:
    from art.describe import describe_boxcox
    from art.policy import DefaultPolicy

    # Se pregunta a la POLÍTICA por el mismo camino que `run_full`: primero el
    # dominio, y la λ con el dominio en la mano. Antes del arreglo `decide_lambda`
    # sólo recibía las estadísticas Box-Cox y la regla índice no tenía por dónde
    # entrar. El repro se actualizó al contrato nuevo el 12-ago-2026; la tabla y
    # el argumento son los mismos.
    pol = DefaultPolicy()

    print(__doc__.split("Run:")[0].strip())
    print()
    print("  series      corr(raw)   corr(log)      gap    policy lambda   "
          "index rule wants")
    print("  " + "-" * 76)

    logs = levels = 0
    rows = []
    import fue

    for name in SERIES:
        ts, _model = fue.load(str(HERE / f"{name}.inp"))
        d = describe_boxcox(ts).data
        gap = float(d.get("gap", 0.0))
        lam = pol.decide_lambda(d, pol.decide_domain(ts))
        rows.append((name, d.get("corr_raw"), d.get("corr_log"), gap, lam))
        if lam == 0.0:
            logs += 1
        else:
            levels += 1
        print(f"  {name:10} {float(d.get('corr_raw', 0)):9.3f}   "
              f"{float(d.get('corr_log', 0)):9.3f}   {gap:+7.3f}   "
              f"{'log (0)' if lam == 0.0 else 'LEVELS (1)':>13}   "
              f"{'log (0)':>15}")

    print()
    print(f"  policy: {logs} in logs, {levels} in LEVELS."
          f"   index rule: 8 in logs.")
    print()

    gaps = [abs(r[3]) for r in rows]
    print(f"  |gap| ranges {min(gaps):.3f} … {max(gaps):.3f} — all small. The")
    print("  decision rides on a sign, not on a magnitude.")
    print()

    if levels:
        print("  BUG-0015 REPRODUCED: the autonomous pipeline puts")
        print("  " + ", ".join(r[0] for r in rows if r[4] != 0.0))
        print("  in LEVELS. The guided path puts all eight in logs.")
        print()
        print("  Why it matters beyond taste:")
        print("   - a level model of an index has no interpretable scale: the")
        print("     base year is a convention, so only relative changes mean")
        print("     anything;")
        print("   - in a transfer function against a log input the gain stops")
        print("     being an elasticity and becomes a semi-elasticity, so the")
        print("     countries in levels cannot be compared with those in logs;")
        print("   - NOTHING downstream flags it. Q, Jarque-Bera and the new")
        print("     residual-mean test all pass on the level models. It is a")
        print("     silent failure like BUG-0013 was, but the residual-mean")
        print("     check added there does not cover this one.")
        return 1

    print("  All eight in logs — la regla índice está en la política.")
    print()
    print("  Nota, y es una limitación honesta del criterio: EMU sale del")
    print("  detector como `generic` porque su NOMBRE no lleva prefijo de")
    print("  índice, y acaba en logs sólo porque su gap es +0.304. El nombre")
    print("  es evidencia débil: por eso `domain` se puede DECLARAR")
    print("  (`build_model(domain=...)`, `ClaudePolicy(domain=...)`) y lo")
    print("  declarado gana siempre a lo inferido.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
