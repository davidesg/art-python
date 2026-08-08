

# ── BUG-0013 capa 3: la media residual, que el instrumento restaba ─────────
def _ipc():
    import fue, os
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "bugs", "BUG-0010-repro", "IPC_ES_m10.pre")
    if not os.path.exists(p):
        import pytest as _p
        _p.skip("falta el .pre de reproducción")
    return fue.load(p)


def test_the_residual_mean_is_contrasted_not_just_subtracted():
    """`diagnose` computed the residual mean only to CENTRE the z-scores, and
    never tested it. So a model missing its drift — the drift then sitting in
    the residuals — passed all three verdicts, because Q and Jarque-Bera run on
    centred residuals too. Brajín §2 lists this criterion and it was the one art
    did not have."""
    from art.diagnosis import diagnose

    ts, m = _ipc()
    m.mu0 = 0.0
    m.estimate_mu = False
    m.fit()
    r = diagnose(m)
    assert abs(r.mean_t) > 2.0, f"t = {r.mean_t}: el contraste no lo ve"
    assert r.centred is False
    assert r.clean is False


def test_it_does_not_fire_on_a_model_that_carries_its_mean():
    """A check that fired on a correct model would be worse than none.
    Measured on the same series with mu in the model: t = -0.01."""
    from art.diagnosis import diagnose

    ts, m = _ipc()
    m.estimate_mu = True
    m.fit()
    r = diagnose(m)
    assert abs(r.mean_t) < 2.0
    assert r.centred is True


def test_the_outlier_loop_asks_about_the_residuals_not_the_mean():
    """The trap this fix walked into first, and had to walk back out of.

    Folding `centred` into `clean` made the autonomous run on IPC_ES add TWO
    interventions it had not added before, chasing a drift with dummies. A dummy
    cannot absorb a missing mean, and trying is the same category error as
    re-specifying a model's shape around an anomaly.

    So the loop consults `residuals_ok` (shape) and the verdict consults `clean`
    (adequacy, which includes the mean). Measured: 1 round and 0 interventions,
    the same as before the check existed, and the defect still reported.
    """
    import os
    import tempfile

    from art.pipeline import run_full

    ts, _m = _ipc()
    r = run_full(ts, os.path.join(tempfile.mkdtemp(), "a.inp"), max_rounds=5)
    assert len(r.interventions) == 0, (
        f"{len(r.interventions)} intervenciones: el bucle está persiguiendo la media")
    fd = r.final_diag
    assert fd.residuals_ok is True      # la FORMA de los residuos está bien
    assert fd.centred is False          # y aun así el modelo NO es adecuado
    assert fd.clean is False
