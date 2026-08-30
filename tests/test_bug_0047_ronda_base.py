"""BUG-0047 — el bucle de anómalos siempre tiene que dar una vuelta.

`max_rounds` cuenta rondas de INTERVENCIÓN, y la ronda 1 no interviene: es la
estimación base. Con 0 el rango salía vacío, no se estimaba nada y el `None`
resultante moría en `_write_inp` con un AttributeError.
"""
import warnings

import numpy as np
import pytest

import fue
from art.pipeline import run_full


def _serie(n=80, seed=3):
    rng = np.random.default_rng(seed)
    return fue.TimeSeries(
        (100.0 * np.exp(np.cumsum(rng.standard_normal(n)) / 60.0)).tolist(),
        freq=4, start=(2000, 1), name="LLANA")


@pytest.mark.parametrize("max_rounds", [0, 1, 2])
def test_siempre_se_devuelve_un_modelo(tmp_path, max_rounds):
    warnings.simplefilter("ignore")
    r = run_full(_serie(), str(tmp_path / f"m{max_rounds}.inp"),
                 max_rounds=max_rounds)
    assert r.final_model is not None
    assert r.final_diag is not None
    assert r.rounds, "sin rondas registradas no hay nada que auditar"


def test_cero_y_uno_significan_lo_mismo(tmp_path):
    """Cero rondas de intervención ES la base sola, no la ausencia de modelo."""
    warnings.simplefilter("ignore")
    a = run_full(_serie(), str(tmp_path / "a.inp"), max_rounds=0)
    b = run_full(_serie(), str(tmp_path / "b.inp"), max_rounds=1)
    assert len(a.rounds) == len(b.rounds) == 1
    assert a.interventions == b.interventions
