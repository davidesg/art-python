"""BUG-0010 — podar un armónico anulaba el barrido MEG entero, en silencio.

Tres capas, cada una defendible por separado y juntas mudas:

  1. `meg()` validaba TODAS las frecuencias antes de calcular ninguna, así que
     una sola irreformulable abortaba el barrido;
  2. `describe_formal_tests` la llamaba dentro de `_try(..., [])`, que hacía
     indistinguible "lanzó" de "no se pidió";
  3. `_meg_suitable()` seguía siendo cierto — el modelo aún tiene cos/sin — así
     que la rama "MEG no aplica" tampoco saltaba.

La sección MEG desaparecía del informe sin una palabra y la recomendación pasaba
a «Los contrastes formales no detectan problemas. El modelo es adecuado.» sobre
un modelo con f=3 estocástica dentro.

Los dos ficheros son el mismo IPC_ES (INE, 2002-01…2019-12, n=216, λ=0, d=1,
D=0, AR(1)+μ) y difieren SOLO en si está el par cos/sin de f=5. Esa es la parte
controlada: un par de armónicos de diferencia, y un veredicto estocástico en una
frecuencia intacta se convertía en un certificado de buena salud.
"""
import os

import pytest

_REPRO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "bugs", "BUG-0010-repro")
_FULL = os.path.join(_REPRO, "IPC_ES_m10.pre")          # 5 pares + Nyquist
_PRUNED = os.path.join(_REPRO, "IPC_ES_m10_podado.pre")  # sin el par de f=5

pytestmark = pytest.mark.skipif(
    not (os.path.exists(_FULL) and os.path.exists(_PRUNED)),
    reason="faltan los .pre de reproducción de BUG-0010")


def _fitted(path):
    import fue
    ts, m = fue.load(path)
    m.fit()
    return m


# ── el motor ───────────────────────────────────────────────────────────────

def test_the_sweep_reports_every_requested_frequency():
    """Ni una se pierde: las testables con veredicto, la podada como skipped."""
    from art.formal_tests import meg

    res = meg(_fitted(_PRUNED))
    assert [r.freq for r in res] == [1, 2, 3, 4, 5, 6]

    skipped = [r for r in res if r.skipped]
    assert [r.freq for r in skipped] == [5]
    assert skipped[0].reason and "f=5" in skipped[0].reason
    assert skipped[0].stochastic is False and skipped[0].deterministic is False


def test_the_stochastic_verdict_survives_the_pruning():
    """El corazón del bug: f=3 es estocástica en AMBOS modelos.

    Antes del arreglo, el modelo podado no devolvía ningún veredicto.
    """
    from art.formal_tests import meg

    for path in (_FULL, _PRUNED):
        res = {r.freq: r for r in meg(_fitted(path))}
        assert res[3].status == "stochastic", f"{os.path.basename(path)}: f=3"
        assert res[3].dcd_result.lr > res[3].dcd_result._crit["5%"]


def test_an_explicit_request_still_raises_with_its_message():
    """Barrido y petición explícita quieren cosas opuestas y las reciben.

    `meg_frequency` pide una frecuencia por su nombre: no poder atenderla es un
    error, y el mensaje de `_check_reformulable` es lo accionable que hay.
    """
    from art.formal_tests import meg

    with pytest.raises(ValueError, match="no cos/sin harmonics at f=5"):
        meg(_fitted(_PRUNED), frequencies=[5])


def test_the_full_model_skips_nothing():
    """Un control: el arreglo no debe inventar skips donde no los hay."""
    from art.formal_tests import meg

    assert [r for r in meg(_fitted(_FULL)) if r.skipped] == []


# ── el informe, que es donde el silencio dolía ─────────────────────────────

def test_the_report_carries_the_verdict_and_the_skip():
    from art.describe import describe_formal_tests

    d = describe_formal_tests(_fitted(_PRUNED), run_meg=True)

    assert "MEG" in d.summary
    assert "freq=3" in d.summary and "stochastic" in d.summary
    assert "sin contrastar" in d.summary          # f=5, con su razón
    megs = {x["freq"]: x for x in d.data["meg"]}
    assert megs[3]["status"] == "stochastic"
    assert megs[5]["status"] == "skipped" and megs[5]["reason"]
    assert d.data["meg_error"] is None


def test_the_recommendation_cannot_say_the_model_is_fine():
    """La línea que cerraba el informe sobre un modelo con f=3 estocástica."""
    from art.describe import describe_formal_tests

    for path in (_FULL, _PRUNED):
        rec = describe_formal_tests(_fitted(path), run_meg=True).recommendation
        assert "El modelo es adecuado" not in rec, os.path.basename(path)
        assert "freq=3 es estocástica" in rec, os.path.basename(path)

    # y el podado además avisa de lo que no se contrastó, con el porqué
    rec = describe_formal_tests(_fitted(_PRUNED), run_meg=True).recommendation
    assert "sin contrastar" in rec and "[5]" in rec
    assert "A FAVOR" in rec      # la t baja es evidencia de estocástica


# ── la guía, que es lo que llevó a podar primero ───────────────────────────

def test_the_pruning_tools_state_the_ordering():
    """Los docstrings son lo que el modelo lee: si no lo dicen, no existe."""
    import art.mcp_server as S

    for name in ("seasonal_param_analysis", "test_seasonal_simplification"):
        tool = getattr(S, name)
        doc = (getattr(tool, "fn", tool)).__doc__ or ""
        assert "MEG" in doc, name
        assert "BUG-0010" in doc, name

    assert "EL MEG VA ANTES DE PODAR" in S._INSTRUCTIONS
