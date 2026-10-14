"""BUG-0247 — con la horquilla, el nodo Box-Cox no dice «Ambas … razonables».

Con signos opuestos (`horquilla`) y |Δcorr| < 0.10 (`ambiguous`) salían los dos
avisos seguidos: «Eso NO es "las dos son razonables"» y, debajo, «Ambas
transformaciones son razonables». Y la recomendación mandaba a la detección de
estacionalidad, cuando el nodo que sigue a λ es d.

Buffalo (flour_prices.csv, ejemplo lutkepohl_poskitt de sima): corr +0.159 con
λ=1 y −0.077 con λ=0.
"""
import csv
import os
import warnings

import fue
from art.describe import describe_boxcox

CSV = os.path.join(os.path.dirname(__file__), os.pardir,
                   "bugs", "BUG-0247-repro", "flour_prices.csv")


def _buffalo():
    with open(CSV) as f:
        filas = list(csv.DictReader(f))
    a, m = (int(x) for x in filas[0]["date"].split("-"))
    return fue.TimeSeries([float(r["Buffalo"]) for r in filas], freq=12,
                          start=(a, m), name="Buffalo")


def _desc():
    warnings.simplefilter("ignore")
    return describe_boxcox(_buffalo())


def test_precondicion_horquilla_y_ambigua():
    d = _desc()
    assert d.data["horquilla"] is True
    assert d.data["ambiguous"] is True


def test_la_horquilla_no_va_con_ambas_razonables():
    d = _desc()
    txt = d.summary.replace("**", "")
    assert "signos son OPUESTOS" in txt
    assert "Ambas transformaciones son razonables" not in txt
    assert "puedes usar λ=1.0" not in d.recommendation
    assert "dominio" in d.recommendation


def test_el_siguiente_paso_es_d():
    d = _desc()
    assert "detección de estacionalidad" not in d.recommendation
    assert "d = 0" in d.recommendation
