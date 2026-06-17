"""
Golden / characterization tests for the orchestration paths (Fase 0).

Purpose: pin the CURRENT behaviour of the two orchestration entry points
(`build_model` = autonomous, `confirm_and_estimate` = guided estimation) so the
orchestration-unification refactor (see docs/ARCHITECTURE.md §6) can be proven
behaviour-preserving.

We snapshot a NORMALISED dict of *decisions and key estimates* — not the prose
or the figure bytes — so that:
  * legitimate prose/formatting changes do not cause spurious failures, and
  * any change in the actual model that comes out (λ, d, D, harmonics, p, q,
    interventions added, final verdict, loglik/AIC) DOES fail loudly.

The frozen input series lives in tests/golden/synth_b1_series.json and never
changes.  Golden snapshots live in tests/golden/*.json; delete a snapshot and
re-run to regenerate it deliberately.
"""
import json
import os
import re
import tempfile

import pytest

_GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")
_SERIES_JSON = os.path.join(_GOLDEN_DIR, "synth_b1_series.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def synth_inp():
    """Write the frozen synthetic series to a temp .inp and return its path."""
    import fue
    from art.mcp_server import _write_bare_inp

    if not os.path.exists(_SERIES_JSON):
        pytest.skip(f"frozen series fixture missing: {_SERIES_JSON}")
    with open(_SERIES_JSON) as fh:
        d = json.load(fh)
    ts = fue.TimeSeries(d["data"], freq=d["freq"],
                        start=tuple(d["start"]), name=d["name"])
    tmp = tempfile.mkdtemp()
    inp = os.path.join(tmp, "synth.inp")
    _write_bare_inp(ts, inp)
    return inp, tmp


# ---------------------------------------------------------------------------
# Snapshot helper
# ---------------------------------------------------------------------------

def _assert_matches_golden(name: str, data: dict):
    """Compare *data* against tests/golden/<name>.json.

    First run (file absent): write the baseline and skip with a notice.
    Subsequent runs: assert exact equality, printing a readable diff.
    """
    path = os.path.join(_GOLDEN_DIR, f"{name}.json")
    if not os.path.exists(path):
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        pytest.skip(f"golden baseline created: {path} — re-run to enforce")

    with open(path) as fh:
        golden = json.load(fh)

    if data != golden:
        diffs = []
        for k in sorted(set(golden) | set(data)):
            gv, dv = golden.get(k, "<absent>"), data.get(k, "<absent>")
            if gv != dv:
                diffs.append(f"  {k}: golden={gv!r}  actual={dv!r}")
        raise AssertionError(
            f"Behaviour drift vs golden '{name}':\n" + "\n".join(diffs)
            + f"\n\nIf intentional, delete {path} and re-run to regenerate."
        )


def _text_of(result) -> str:
    """Extract the single text-content payload from an MCP tool result."""
    return next(it.text for it in result if it.type == "text")


# ---------------------------------------------------------------------------
# Decision extractors (normalisation layer)
# ---------------------------------------------------------------------------

def _extract_build_model(text: str) -> dict:
    out: dict = {}

    m = re.search(r"λ=(\d)", text)
    out["lambda"] = int(m.group(1)) if m else None

    m = re.search(r"decisión=(\w+)\s+d=(\d)\s+D=(\d)\s+armónicos=(\d+)", text)
    if m:
        out["decision"] = m.group(1)
        out["d"] = int(m.group(2))
        out["D"] = int(m.group(3))
        out["n_harmonics"] = int(m.group(4))

    m = re.search(r"ARIMA\((\d+),(\d+),(\d+)\)", text)
    if m:
        out["p"] = int(m.group(1))
        out["q"] = int(m.group(3))

    m = re.search(r"Rondas totales:\*\*\s*(\d+)", text)
    out["rounds"] = int(m.group(1)) if m else None

    # Interventions added across all rounds, in order
    out["interventions"] = [
        [form, int(obs)] for form, obs in re.findall(r"(STEP|PULSE|RAMP) obs (\d+)", text)
    ]

    out["verdict"] = "APROBADA" if "APROBADA" in text else (
        "REVISAR" if "REVISAR" in text else None)

    # Aggregate estimates (deterministic on a fixed machine/spec)
    m = re.search(r"ℓ\s*=\s*(-?[\d.]+)", text)
    out["loglik"] = round(float(m.group(1)), 1) if m else None
    m = re.search(r"AIC\s*=\s*(-?[\d.]+)", text)
    out["aic"] = round(float(m.group(1)), 1) if m else None
    return out


def _extract_estimate(text: str) -> dict:
    out: dict = {}

    m = re.search(r"Veredicto:\s*\*\*(\w+)", text)
    out["verdict"] = m.group(1) if m else (
        "REVISAR" if "REVISAR" in text else ("APROBADA" if "APROBADA" in text else None))

    # White-noise / normality flags
    out["white_noise"] = ("Ruido blanco (Q): ✓" in text)
    out["normal"] = ("Normalidad (JB): ✓" in text)

    m = re.search(r"ℓ\s*=\s*(-?[\d.]+)", text)
    out["loglik"] = round(float(m.group(1)), 1) if m else None
    m = re.search(r"AIC\s*=\s*(-?[\d.]+)", text)
    out["aic"] = round(float(m.group(1)), 1) if m else None

    # Count estimated parameters shown in the equation (SE lines in parentheses)
    out["n_se_shown"] = len(re.findall(r"\(\d+\.\d+\)", text))
    return out


# ---------------------------------------------------------------------------
# Golden tests
# ---------------------------------------------------------------------------

def test_build_model_golden(synth_inp):
    """Autonomous pipeline behaviour on the frozen B1 monthly series."""
    from art.mcp_server import build_model

    inp, tmp = synth_inp
    out = os.path.join(tmp, "synth_build_out.inp")
    result = build_model(inp, out, max_rounds=5)
    text = _text_of(result)
    assert "❌" not in text, f"build_model errored:\n{text}"

    decisions = _extract_build_model(text)
    # Sanity: the pipeline must have reached a real spec
    assert decisions.get("d") is not None and decisions.get("p") is not None
    _assert_matches_golden("build_model_synth_b1", decisions)


def test_confirm_and_estimate_golden(synth_inp):
    """Guided estimation behaviour for a FIXED spec on the same series.

    Pins what comes out of confirm_and_estimate given an analyst-confirmed
    (λ, d, D, p, q, harmonics) — i.e. the estimation half of the guided path.
    """
    from art.mcp_server import confirm_and_estimate

    inp, tmp = synth_inp
    out = os.path.join(tmp, "synth_ce_out.inp")
    result = confirm_and_estimate(
        inp_path=inp, output_path=out,
        lam=1.0, d=1, D=0, p=0, q=1, n_harmonics=5,
    )
    text = _text_of(result)
    assert "❌" not in text, f"confirm_and_estimate errored:\n{text}"

    decisions = _extract_estimate(text)
    assert decisions.get("loglik") is not None
    _assert_matches_golden("confirm_and_estimate_synth_b1", decisions)


def test_run_full_policy_swappable(synth_inp):
    """run_full honours a ClaudePolicy override and falls back to the heuristic
    for unspecified choices (Fase 4 — swappable policy)."""
    import os
    from art.pipeline import run_full
    from art import policy

    inp, tmp = synth_inp
    r_default = run_full(inp_to_ts(inp), os.path.join(tmp, "rf_def.inp"), max_rounds=3)
    r_claude  = run_full(inp_to_ts(inp), os.path.join(tmp, "rf_cla.inp"), max_rounds=3,
                         decision_policy=policy.ClaudePolicy(lam=0.0, q=2))
    # Default matches the autonomous golden (λ=1, q=1)
    assert r_default.lam == 1.0 and r_default.q == 1
    # Overrides flow through; p unspecified → heuristic (same as default)
    assert r_claude.lam == 0.0 and r_claude.q == 2
    assert r_claude.p == r_default.p


def inp_to_ts(inp_path):
    import fue
    ts, _ = fue.inp.load(inp_path)
    return ts


def test_build_model_guided_honours_confirmed_spec(synth_inp):
    """build_model with analyst-confirmed overrides drives run_full through a
    ClaudePolicy: the spec is honoured and the header reports guided mode."""
    import os, re
    from art.mcp_server import build_model

    inp, tmp = synth_inp
    result = build_model(inp, os.path.join(tmp, "guided.inp"),
                         max_rounds=3, lam=0.0, q=2)
    text = _text_of(result)
    assert "guiado" in text.splitlines()[0]
    assert re.search(r"λ=0", text)
    assert "ARIMA(0,1,2)" in text   # q override honoured, p fell back to heuristic
