"""Unit tests for art.policy — the centralised BJT decision rules (Fase 1)."""
from art import policy


# ── decide_lambda ──────────────────────────────────────────────────────────

def test_decide_lambda_log_when_gap_nonneg():
    assert policy.decide_lambda({"gap": 0.5}) == 0.0
    assert policy.decide_lambda({"gap": 0.0}) == 0.0


def test_decide_lambda_identity_when_gap_negative():
    assert policy.decide_lambda({"gap": -0.3}) == 1.0


def test_decide_lambda_missing_gap_defaults_log():
    assert policy.decide_lambda({}) == 0.0


# ── decide_d ───────────────────────────────────────────────────────────────

def test_decide_d_reads_recommendation():
    assert policy.decide_d({"recommended_d": 2}) == 2


def test_decide_d_default():
    assert policy.decide_d({}) == 1


# ── decide_seasonal_structure ──────────────────────────────────────────────

def test_seasonal_b1_monthly_full_harmonics():
    D, decision, n_harm = policy.decide_seasonal_structure(
        {"recommended_D": 0, "decision": "B1"}, freq=12)
    assert (D, decision, n_harm) == (0, "B1", 5)


def test_seasonal_b1_quarterly():
    D, decision, n_harm = policy.decide_seasonal_structure(
        {"recommended_D": 0, "decision": "B1"}, freq=4)
    assert (D, decision, n_harm) == (0, "B1", 1)


def test_seasonal_decision_a_no_harmonics():
    D, decision, n_harm = policy.decide_seasonal_structure(
        {"recommended_D": 0, "decision": "A"}, freq=12)
    assert n_harm == 0


def test_seasonal_b2_keeps_D():
    D, decision, n_harm = policy.decide_seasonal_structure(
        {"recommended_D": 1, "decision": "B2"}, freq=12)
    assert D == 1 and decision == "B2"


# ── decide_orders ──────────────────────────────────────────────────────────

class _Spec:
    def __init__(self, p, q):
        self.p, self.q = p, q


def test_decide_orders_takes_top():
    assert policy.decide_orders([_Spec(2, 1), _Spec(0, 3)]) == (2, 1)


def test_decide_orders_empty_fallback():
    assert policy.decide_orders([]) == (0, 1)


# ── decide_form ────────────────────────────────────────────────────────────

def test_decide_form_isolated_is_pulse():
    assert policy.decide_form(60, {60}) == "pulse"


def test_decide_form_consecutive_is_step():
    assert policy.decide_form(60, {60, 61}) == "step"
    assert policy.decide_form(61, {60, 61}) == "step"


def test_decide_form_gap_is_pulse():
    # 60 and 62 are not adjacent
    assert policy.decide_form(60, {60, 62}) == "pulse"


# ── decide_interventions ───────────────────────────────────────────────────

def test_intervention_pulse_isolated():
    # single isolated extreme → pulse, at = obs-1
    assert policy.decide_interventions([(60, 6.4)], []) == [(59, "pulse")]


def test_intervention_step_consecutive():
    # two adjacent extremes → both step
    out = policy.decide_interventions([(60, 6.4), (61, -4.9)], [])
    assert out == [(59, "step"), (60, "step")]


def test_intervention_skips_existing():
    out = policy.decide_interventions([(60, 6.4), (120, 3.2)], existing_ats=[59])
    assert out == [(119, "pulse")]


def test_intervention_sorted_by_abs_z():
    out = policy.decide_interventions([(10, 2.1), (50, -9.0)], [])
    assert out[0][0] == 49  # most extreme first


# ── should_stop ────────────────────────────────────────────────────────────

def test_should_stop_clean():
    assert policy.should_stop(clean=True, n_extreme=3) is True


def test_should_stop_no_extreme():
    assert policy.should_stop(clean=False, n_extreme=0) is True


def test_should_continue():
    assert policy.should_stop(clean=False, n_extreme=2) is False


# ── THRESHOLDS ─────────────────────────────────────────────────────────────

def test_thresholds_present():
    for k in ("outlier_user", "outlier_autonomous", "outlier_autoscan",
              "intervention_form", "intervention_autoselect"):
        assert k in policy.THRESHOLDS


# ── Policy objects (DefaultPolicy / ClaudePolicy) ──────────────────────────

def test_default_policy_matches_module_functions():
    p = policy.DefaultPolicy()
    assert p.decide_lambda({"gap": -0.3}) == policy.decide_lambda({"gap": -0.3})
    assert p.decide_d({"recommended_d": 2}) == 2
    assert p.decide_seasonal_structure({"decision": "B1", "recommended_D": 0}, 12) == (0, "B1", 5)
    assert p.decide_orders([_Spec(2, 1)]) == (2, 1)
    assert p.decide_form(60, {60, 61}) == "step"
    assert p.should_stop(True, 5) is True


def test_claude_policy_overrides_provided_choices():
    p = policy.ClaudePolicy(lam=0.0, d=1, p=2, q=0)
    # provided → returned regardless of evidence
    assert p.decide_lambda({"gap": -5.0}) == 0.0     # evidence says identity, override wins
    assert p.decide_d({"recommended_d": 9}) == 1
    assert p.decide_orders([_Spec(0, 1)]) == (2, 0)


def test_claude_policy_falls_back_to_heuristic():
    p = policy.ClaudePolicy(lam=0.0)   # only λ fixed
    # d, orders, seasonal not provided → heuristic
    assert p.decide_d({"recommended_d": 2}) == 2
    assert p.decide_orders([_Spec(3, 1)]) == (3, 1)
    D, dec, nh = p.decide_seasonal_structure({"decision": "B1", "recommended_D": 0}, 4)
    assert (D, dec, nh) == (0, "B1", 1)


def test_claude_policy_partial_seasonal_override():
    p = policy.ClaudePolicy(decision="A")   # force no seasonality
    D, dec, nh = p.decide_seasonal_structure({"decision": "B1", "recommended_D": 0}, 12)
    assert dec == "A"
    # D and n_harmonics fall back to heuristic computed from the evidence/freq
    assert D == 0
