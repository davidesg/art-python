"""BUG-0252: encadenar (base_pre_path) con ar_f_freqs añade el AR(2) de
frecuencia fija pedido, como el modo nuevo; los heredados no se tocan.
Minneapolis, del ejemplo lutkepohl_poskitt de sima."""
import os

import pytest

fue = pytest.importorskip("fue")
from art import mcp_server as M

CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "bugs", "BUG-0252-repro", "flour_prices.csv")
SPEC = dict(lam=0.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)


def _fn(t):
    return getattr(t, "fn", t)


def _txt(o):
    return "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                     for c in (o if isinstance(o, list) else [o]))


@pytest.fixture(scope="module")
def m02(tmp_path_factory):
    d = tmp_path_factory.mktemp("b252")
    inp = str(d / "Minneapolis.inp")
    _fn(M.load_data)(CSV, inp, column="Minneapolis")
    _fn(M.confirm_and_estimate)(inp, str(d / "m02.inp"), p=1, q=0, **SPEC)
    return d, inp


def _ar_f(path):
    return sorted(int(f.freq) for f in (fue.load(path)[1].ar_f or []))


def test_encadenar_anade_el_factor_pedido(m02):
    d, inp = m02
    out = _txt(_fn(M.confirm_and_estimate)(inp, str(d / "m03.inp"),
                                          base_pre_path=str(d / "m02.pre"),
                                          p=1, q=0, ar_f_freqs=[2], estimate_mu=False))
    assert _ar_f(str(d / "m03.pre")) == [2]
    assert "AR(2) de frecuencia fija añadidos" in out


def test_el_heredado_no_se_duplica(m02):
    d, inp = m02
    _fn(M.confirm_and_estimate)(inp, str(d / "m03b.inp"), base_pre_path=str(d / "m02.pre"),
                                p=1, q=0, ar_f_freqs=[2], estimate_mu=False)
    out = _txt(_fn(M.confirm_and_estimate)(inp, str(d / "m04.inp"),
                                          base_pre_path=str(d / "m03b.pre"),
                                          p=1, q=0, ar_f_freqs=[2, 4], estimate_mu=False))
    assert _ar_f(str(d / "m04.pre")) == [2, 4]
    assert "ya lleva ese factor de frecuencia fija" in out


def test_sin_ar_f_freqs_se_heredan(m02):
    d, inp = m02
    _fn(M.confirm_and_estimate)(inp, str(d / "m05.inp"), base_pre_path=str(d / "m03b.pre"),
                                p=0, q=0, estimate_mu=False)
    assert _ar_f(str(d / "m05.pre")) == [2]
