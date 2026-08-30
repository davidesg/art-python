"""BUG-0038 — las salvedades del veredicto sobre `d` colgaban del par
confirmatorio, y el par sólo existe si hay AR regular.

`dcd_overdiff_regular` contrasta el orden de integración en f=0. Su veredicto
viene con dos advertencias que el paper exige:

  1. el crítico impreso (1.94) es el de la ley DESNUDA s=1; con deterministas
     RESONANTES con f=0 —una constante, un escalón— el pile-up sube de 0.6575 a
     0.927 y el crítico correcto es MAYOR;
  2. si θ̂ no se apila en la frontera, el LR se evalúa donde el perfil de
     verosimilitud de fue da un salto errático.

Las dos vivían dentro del bloque `if sf_res is not None and od_res is not None`,
que sólo se imprime cuando Shin-Fuller es aplicable. Un modelo SIN AR regular
libre recibía "considerar d+1 ✗" a pelo.

Ninguna de las dos habla del par: las dos hablan del veredicto del DCD.

Testigo real: RATIO de la réplica del TFM. Dos raíces unitarias estacionales, un
escalón, AR sólo estacional → sin Shin-Fuller. LR=2.576 contra 1.94 impreso y sin
aviso: se leyó como "falta una diferencia" y llevó a un d=2 incorrecto.
"""
import numpy as np
import pytest

import fue
from art.describe import describe_formal_tests
from art.formal_tests import shin_fuller
from art.pipeline import _write_inp, _load_fitted


def _modelo_sin_ar_regular(tmp_path, con_escalon=True):
    rng = np.random.default_rng(5)
    nivel = 100.0 + np.cumsum(rng.standard_normal(110))
    itvs = []
    if con_escalon:
        nivel[55:] += 9.0
        itvs = [fue.Intervention("step", at=55, omega=[0.0], omega_free=[True])]
    ts = fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="ESCALON")
    ruta = str(tmp_path / f"esc{int(con_escalon)}.inp")
    m = fue.Model(ts, d=1, boxlam=1.0, ma=[[0.0]], ma_free=[[True]],
                  interventions=itvs, mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, mf = _load_fitted(ruta)
    return mf


def test_shin_fuller_really_is_unavailable(tmp_path):
    """La premisa del testigo: sin AR regular no hay par."""
    m = _modelo_sin_ar_regular(tmp_path)
    assert not m.ar
    with pytest.raises(Exception):
        shin_fuller(m)


def test_the_bare_law_caveat_appears_without_a_pair(tmp_path):
    m = _modelo_sin_ar_regular(tmp_path)
    txt = describe_formal_tests(m).summary
    assert "DESNUDA" in txt, (
        "el veredicto sobre d se publica sin decir que el crítico impreso está "
        "subestimado para un modelo con deterministas resonantes en f=0")
    assert "RESONANTE" in txt


def test_the_missing_pair_is_stated(tmp_path):
    """Que falte el par no es un detalle: un contraste de frontera se lee en
    pareja, y si sólo hay un lado hay que decirlo."""
    m = _modelo_sin_ar_regular(tmp_path)
    txt = describe_formal_tests(m).summary
    assert "Sin par confirmatorio" in txt


def test_no_deterministics_no_bare_law_caveat(tmp_path):
    """La otra cara: el aviso del crítico sólo muerde cuando hay deterministas
    resonantes. Sin ellos no debe aparecer y ensuciar la salida."""
    m = _modelo_sin_ar_regular(tmp_path, con_escalon=False)
    txt = describe_formal_tests(m).summary
    assert "DESNUDA" not in txt
    # pero el aviso del par sí, porque sigue sin haber AR regular
    assert "Sin par confirmatorio" in txt


def test_the_caveats_still_appear_when_the_pair_exists(tmp_path):
    """No romper el caso que ya funcionaba: con AR regular hay par, y las
    salvedades deben seguir estando."""
    rng = np.random.default_rng(3)
    w = np.zeros(110)
    for t in range(1, 110):
        w[t] = 0.5 * w[t - 1] + rng.standard_normal()
    nivel = 100.0 + np.cumsum(w)
    nivel[55:] += 9.0
    ts = fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="CONAR")
    ruta = str(tmp_path / "conar.inp")
    m = fue.Model(ts, d=1, boxlam=1.0, ar=[[0.4]], ar_free=[[True]],
                  interventions=[fue.Intervention("step", at=55, omega=[0.0],
                                                  omega_free=[True])],
                  mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, mf = _load_fitted(ruta)
    txt = describe_formal_tests(mf).summary
    assert "Par confirmatorio" in txt
    assert "DESNUDA" in txt
    assert "Sin par confirmatorio" not in txt
