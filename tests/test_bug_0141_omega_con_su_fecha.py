"""BUG-0141 — dos intervenciones, la misma etiqueta.

`_build_param_labels` rotulaba las intervenciones por su TIPO: `ω(S)` para un
escalón, `ω(I)` para un impulso. Con dos escalones en el mismo modelo —que es lo
normal en cuanto hay dos sucesos— la tabla de sobreparametrización listaba
`ω(S)` **dos veces**, y el analista no tenía forma de saber cuál de las dos
fechas era la del par correlado. La tabla existe para decir qué parámetro hay
que tocar; una etiqueta que no identifica su parámetro no dice nada.

La fecha estaba a mano: `Intervention.at` y `series.start`. Es la misma que el
analista escribió en el `.inp` (`step 4 2008`) y la misma que lee en el `.out`.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.diagnosis import _build_param_labels


def _modelo(interv, n=120, freq=4, start=(2004, 1)):
    rng = np.random.default_rng(3)
    y = np.cumsum(rng.normal(0, 1.0, n)) + 100.0
    ts = fue.TimeSeries(data=y.tolist(), freq=freq, start=list(start), name="X")
    m = fue.Model(ts, d=1, D=0, boxlam=1.0, interventions=interv,
                  mu=0.0, estimate_mu=False)
    m.fit()
    return m


def test_dos_escalones_ya_no_comparten_etiqueta():
    """EL defecto. `at=19` es Q4/2008 y `at=65` es Q2/2020, desde 2004Q1."""
    m = _modelo([
        fue.Intervention("step", at=19, omega=[0.0], omega_free=[True]),
        fue.Intervention("step", at=65, omega=[0.0], omega_free=[True]),
    ])
    labels = _build_param_labels(m)
    assert labels.count("ω(S)") == 0, f"la etiqueta sin fecha sigue ahí: {labels}"
    assert "ω(S,Q4/2008)" in labels, labels
    assert "ω(S,Q2/2020)" in labels, labels
    assert len(set(labels)) == len(labels), f"etiquetas repetidas: {labels}"


def test_la_fecha_es_la_que_el_analista_escribio_en_el_inp():
    """`step 4 2008` en el `.inp` ⇒ `ω(S,Q4/2008)` en la tabla. El mismo
    idioma en los dos sitios, que es lo que hace comparable el registro."""
    m = _modelo([fue.Intervention("step", at=19, omega=[0.0],
                                  omega_free=[True])])
    assert "ω(S,Q4/2008)" in _build_param_labels(m)


def test_un_episodio_de_varios_omega_lleva_fecha_y_retardo():
    m = _modelo([fue.Intervention("impulse", at=65, omega=[0.0, 0.0],
                                  omega_free=[True, True])])
    labels = _build_param_labels(m)
    assert "ω(I,Q2/2020)" in labels, labels
    assert "ω(I,Q2/2020,l1)" in labels, labels


def test_las_armonicas_NO_llevan_fecha():
    """No es un olvido: su `at` no significa nada —actúan sobre toda la
    muestra— y lo que las identifica es el orden del armónico."""
    m = _modelo([
        fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True],
                         harmonic=1),
        fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True],
                         harmonic=1),
    ])
    labels = _build_param_labels(m)
    assert "cos(k=1)" in labels and "sin(k=1)" in labels, labels
    assert not any("/" in l for l in labels), labels


def test_mensual_tambien():
    rng = np.random.default_rng(5)
    y = np.cumsum(rng.normal(0, 1.0, 150)) + 100.0
    ts = fue.TimeSeries(data=y.tolist(), freq=12, start=[2000, 1], name="M")
    m = fue.Model(ts, d=1, D=0, boxlam=1.0, mu=0.0, estimate_mu=False,
                  interventions=[fue.Intervention("step", at=59, omega=[0.0],
                                                  omega_free=[True])])
    m.fit()
    assert "ω(S,12/2004)" in _build_param_labels(m)
