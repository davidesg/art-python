"""BUG-0211 — «REVISAR ✗» y «No procede reformular: el modelo se sostiene» juntos.

El veredicto de la diagnosis es `DiagnosisResult.clean` (media centrada, ruido
blanco, normalidad, sin estacionalidad residual); la conclusión, la §4 y las
alternativas miraban sólo Q y JB. Un modelo que fallaba por la media o por la
estacionalidad residual salía REVISAR en la §3 y «se sostiene» en la §4. Ahora
las tres leen el mismo predicado.
"""
import os
import re
import warnings
from types import SimpleNamespace

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp


def _desc(**kw):
    data = dict(clean=True, white_noise=True, normal=True, centred=True,
                mean_t=0.0, seasonal_residual=False, seasonal_p=0.5,
                n_extreme=0, nobs=200)
    data.update(kw)
    return SimpleNamespace(data=data)


@pytest.mark.parametrize("fallo, texto", [
    (dict(centred=False, mean_t=4.03), "media residual NO es cero"),
    (dict(seasonal_residual=True, seasonal_p=0.003), "estacionalidad en los residuos"),
])
def test_un_revisar_no_dice_que_se_sostiene(fallo, texto):
    d = _desc(clean=False, **fallo)
    concl = srv._conclusiones_desde(d)
    assert "NO se sostiene" in concl and texto in concl
    assert "El modelo se sostiene" not in concl
    ref = srv._reformulacion_desde(d)
    assert ref, "la §4 queda vacía y el sobre dice «no procede reformular»"
    sobre = srv.envuelve_iteracion(nombre="m", modo="autónomo", reformulacion=ref)
    assert "No procede reformular" not in sobre
    alts = " ".join(srv._alternativas_desde(d, inp_path="m.inp"))
    assert "Adoptar este modelo" not in alts


def test_red_de_seguridad_clean_falso_sin_motivo_nombrado():
    d = _desc(clean=False)
    assert "NO se sostiene" in srv._conclusiones_desde(d)
    assert srv._reformulacion_desde(d)


def test_un_aprobado_sigue_sosteniendose():
    d = _desc()
    assert "El modelo se sostiene" in srv._conclusiones_desde(d)
    assert srv._reformulacion_desde(d) == ""
    assert "Adoptar este modelo" in " ".join(srv._alternativas_desde(d))


def _T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


def test_extremo_a_extremo_sin_media(tmp_path):
    """Paseo aleatorio con deriva estimado SIN μ: Q y JB pasan, la media no (cf. IPC_DE (0,1,0) de la P02)."""
    rng = np.random.default_rng(211)
    z = np.cumsum(0.002 + 0.006 * rng.standard_normal(216))
    ts = fue.TimeSeries(np.exp(4.5 + z).tolist(), freq=12, start=(2002, 1), name="W")
    f = str(tmp_path / "W.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, refactor=_RESCALE_FACTOR), f)
    fn = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _T(fn(f, str(tmp_path / "w1.inp"), lam=0, d=1, D=0, p=0, q=0,
                  n_harmonics=0, seasonal=False, estimate_mu=False,
                  domain="price_index", modo="autonomo"))
    veredicto = re.search(r"Veredicto: \*\*(\w+)", t).group(1)
    sec4 = t.split("## 4")[1]
    assert veredicto == "REVISAR"
    assert "Ruido blanco (Q): ✓" in t and "Normalidad (JB): ✓" in t
    assert "No procede reformular" not in sec4
    assert "NO se sostiene" in sec4 and "media residual" in sec4
