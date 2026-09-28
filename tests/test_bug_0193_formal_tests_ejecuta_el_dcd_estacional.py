"""BUG-0193: formal_tests runs the DCD of the seasonal MA (dcd_s, BUG-0039).

It existed and was validated, but only the autonomous lane consumed it, so in
the guided lane a B2 model could not be refuted. Two cases: the airline on
Box-Jenkins' series G (the seasonal difference is genuine) and a synthetic
series with DETERMINISTIC seasonality (the airline's Theta goes to the wall and
the seasonal difference is superfluous).
"""
import os
import shutil

import pytest

pytest.importorskip("fue")
from art.mcp_server import formal_tests  # noqa: E402

F = os.path.join(os.path.dirname(__file__), "fixtures", "bug_0193")


def _run(tmp_path, name):
    shutil.copy(os.path.join(F, name), tmp_path)
    out = formal_tests(inp_path=str(tmp_path / name))
    return "\n".join(x if isinstance(x, str) else getattr(x, "text", str(x)) for x in out)


def test_airline_series_g_the_seasonal_difference_is_genuine(tmp_path):
    txt = _run(tmp_path, "AIRLINE_m01.inp")
    assert "DCD — no invertibilidad MA estacional" in txt
    assert "Θ̂=+0.5569, LR=30.631 (crít 5%=2.31)" in txt
    assert "la ∇12 es GENUINA" in txt
    assert "el lado B2 del par es el DCD del MA estacional" in txt


def test_deterministic_seasonality_the_seasonal_difference_is_superfluous(tmp_path):
    txt = _run(tmp_path, "SINTETICA_estacionalidad_determinista.inp")
    assert "la ∇12 SOBRA" in txt
    assert "Vuelve a la ruta B1" in txt          # and it reaches the recommendation
