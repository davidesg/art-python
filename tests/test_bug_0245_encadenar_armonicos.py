"""BUG-0245 — encadenar ignoraba en silencio `n_harmonics` / `seasonal`.

Con `base_pre_path`, `confirm_and_estimate` heredaba siempre los deterministas
del `.pre` y descartaba los armónicos pedidos: el modelo «con armónicos» era
byte a byte el base, se registraba en el guion con la razón de los armónicos y
la salida decía «se conservan sus intervenciones y armónicos». Ahora el bloque
pedido se aplica sobre el heredado y la salida lo dice; con `None` (por
defecto) se sigue heredando.
"""
import os

import numpy as np
import pytest

os.environ.setdefault("ART_NO_VIEWER", "1")

from art.pipeline import _build_arma_on_model, _make_model


def terminos_armonicos(itvs):
    """«cos 1», «sin 1», «alter»: los términos del bloque estacional."""
    return [f"{i.type} {int(round(float(i.harmonic)))}" if i.type in ("cos", "sin")
            else "alter" for i in (itvs or []) if i.type in ("cos", "sin", "alter")]

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = os.path.join(HERE, "..", "bugs", "BUG-0245-repro")


def _ts(freq=4, n=80, seed=11):
    import fue
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    y = (np.cumsum(rng.normal(0, 1.0, n)) + 100.0
         + 2.0 * np.cos(2 * np.pi * t / freq))
    y[40:] += 6.0
    return fue.TimeSeries(list(y), freq=freq, start=(2000, 1), name="X")


def _base(seasonal=False, n_harmonics=0, freq=4):
    m = _make_model(_ts(freq), lam=1.0, d=1, D=0, p=0, q=0,
                    n_harmonics=n_harmonics, seasonal=seasonal,
                    extra_itvs=[(40, "step")], estimate_mu=False)
    m.fit()
    return m


def _txt(out):
    return "\n".join(getattr(c, "text", "") or "" for c in out)


def test_sin_argumentos_se_heredan():
    b = _base(seasonal=True, n_harmonics=1)
    m = _build_arma_on_model(b, p=1, q=0)
    assert terminos_armonicos(m.interventions) == ["cos 1", "sin 1", "alter"]


def test_se_anaden_sobre_un_base_sin_armonicos():
    m = _build_arma_on_model(_base(), p=1, q=0, n_harmonics=1, seasonal=True)
    assert sorted(terminos_armonicos(m.interventions)) == ["alter", "cos 1", "sin 1"]
    assert [i.type for i in m.interventions][0] == "step"


def test_seasonal_false_los_quita_y_conserva_la_intervencion():
    b = _base(seasonal=True, n_harmonics=1)
    m = _build_arma_on_model(b, p=1, q=0, seasonal=False)
    assert terminos_armonicos(m.interventions) == []
    assert [i.type for i in m.interventions] == ["step"]


def test_los_que_ya_estaban_conservan_su_omega():
    b = _base(seasonal=True, n_harmonics=5, freq=12)
    w = {terminos_armonicos([i])[0]: list(i.omega) for i in b.interventions
         if terminos_armonicos([i])}
    m = _build_arma_on_model(b, p=1, q=0, n_harmonics=2)
    got = {terminos_armonicos([i])[0]: list(i.omega) for i in m.interventions
           if terminos_armonicos([i])}
    assert sorted(got) == ["alter", "cos 1", "cos 2", "sin 1", "sin 2"]
    assert all(got[k] == w[k] for k in got)


def test_seasonal_true_sin_n_no_rehace_un_bloque_simplificado():
    """Un base al que se le quitó un par conserva su bloque: `seasonal=True`
    sólo exige que lo haya."""
    b = _base(seasonal=True, n_harmonics=5, freq=12)
    b.interventions = [i for i in b.interventions
                       if terminos_armonicos([i]) not in (["cos 3"], ["sin 3"])]
    m = _build_arma_on_model(b, p=1, q=0, seasonal=True)
    assert "cos 3" not in terminos_armonicos(m.interventions)


def test_el_caso_del_informe_por_el_servidor(tmp_path):
    from art import mcp_server as M
    fn = getattr(M.confirm_and_estimate, "fn", M.confirm_and_estimate)
    base = os.path.join(REPRO, "GDPDEC_m02_s0804x2.pre")
    kw = dict(base_pre_path=base, lam=0, d=1, D=0, p=2, q=0, estimate_mu=True)
    h, n = str(tmp_path / "h.inp"), str(tmp_path / "n.inp")
    th = _txt(fn(base, h, seasonal=True, n_harmonics=2, **kw))
    tn = _txt(fn(base, n, **kw))
    assert open(h).read() != open(n).read()
    _, mh = M._load_fitted(h)
    assert sorted(terminos_armonicos(mh.interventions)) == ["alter", "cos 1", "sin 1"]
    assert float(mh.loglik) == pytest.approx(-140.69, abs=0.01)
    assert "Armónicos cambiados" in th
    # el base no tiene armónicos: la salida no puede decir que se conservan
    assert "intervenciones y armónicos" not in th + tn
    assert "Armónicos cambiados" not in tn


def test_con_D1_se_rechaza(tmp_path):
    from art import mcp_server as M
    fn = getattr(M.confirm_and_estimate, "fn", M.confirm_and_estimate)
    import fue
    rng = np.random.default_rng(2)
    ts = fue.TimeSeries(list(100 + np.cumsum(rng.normal(0, 1, 96))), freq=12,
                        start=(2000, 1), name="X")
    m = _make_model(ts, lam=1.0, d=1, D=1, p=0, q=1, n_harmonics=0, Q=1)
    m.fit()
    pre = str(tmp_path / "b.pre")
    m.write_pre(pre)
    out = _txt(fn(pre, str(tmp_path / "c.inp"), base_pre_path=pre,
                  p=0, q=1, Q=1, n_harmonics=5, seasonal=True))
    assert "D=1" in out and "redundantes" in out
    assert not os.path.exists(str(tmp_path / "c.inp"))


def test_el_alter_del_base_se_hereda_como_este():
    """`n_harmonics` cuenta pares: un base sin Nyquist no lo recupera por
    pedir pares, y uno con Nyquist no lo pierde."""
    b = _base(seasonal=True, n_harmonics=5, freq=12)
    sin_alter = [i for i in b.interventions if i.type != "alter"]
    b.interventions = sin_alter
    m = _build_arma_on_model(b, p=1, q=0, n_harmonics=3)
    assert "alter" not in terminos_armonicos(m.interventions)
    b2 = _base(seasonal=True, n_harmonics=5, freq=12)
    m2 = _build_arma_on_model(b2, p=1, q=0, n_harmonics=3)
    assert "alter" in terminos_armonicos(m2.interventions)
