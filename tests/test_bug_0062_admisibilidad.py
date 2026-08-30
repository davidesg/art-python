"""BUG-0062 — un operador fuera de la región admisible no puede pasar por bueno.

AR con raíz dentro del círculo → no estacionario. MA con raíz dentro → no
invertible. Y la FRONTERA es un caso distinto: un MA con raíz unitaria y d≥1
cancela la diferencia, que es sobrediferenciación, no un operador roto.
"""
import os
import warnings

import numpy as np
import pytest

from art.diagnosis import _raices_factor, admissibility_problems

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/"
RDS = "/home/david/Dropbox/TFM_UCM/Tesis_Michael_DS/replica/"


class _M:
    """Doble mínimo: sólo lo que mira `admissibility_problems`."""
    def __init__(self, **kw):
        self.ar = self.ma = self.ar_s = self.ma_s = None
        self.series = type("S", (), {"freq": 4})()
        for k, v in kw.items():
            setattr(self, k, v)


# ── la convención de signo, que es de donde sale todo ─────────────────────

def test_la_convencion_es_1_menos_c_B():
    """`fue` guarda (1 − c₁B − c₂B² − …) para AR y MA por igual."""
    # (1 − 0.5B) tiene raíz en B=2
    assert _raices_factor([0.5]) == pytest.approx([2.0])
    # (1 + 0.5B) → c=−0.5, raíz en B=−2
    assert _raices_factor([-0.5]) == pytest.approx([2.0])


# ── dentro, frontera y fuera ──────────────────────────────────────────────

def test_un_MA_invertible_no_se_marca():
    assert admissibility_problems(_M(ma=[[-0.7879, -0.2760]])) == []


def test_un_MA_estacional_no_invertible_se_marca_en_B():
    """Θ₄=−2.0989: |raíz| en u es 0.476 y en B, 0.831. Se reporta en B."""
    pr = admissibility_problems(_M(ma_s=[[-2.098883]]))
    assert len(pr) == 1
    etq, mod, donde = pr[0]
    assert etq == "MA estacional"
    assert mod == pytest.approx(0.8308, abs=1e-3)
    assert donde == "dentro"


def test_un_AR_no_estacionario_se_marca():
    pr = admissibility_problems(_M(ar=[[1.2]]))     # (1 − 1.2B), raíz 0.833
    assert pr and pr[0][0] == "AR" and pr[0][2] == "dentro"


def test_la_frontera_se_distingue_de_dentro():
    pr = admissibility_problems(_M(ma=[[1.0]]))     # (1 − B), raíz exactamente 1
    assert pr and pr[0][2] == "frontera"


def test_los_operadores_de_frecuencia_fija_quedan_fuera():
    """El testigo del MEG apunta a la frontera a propósito; marcarlo sería ruido."""
    m = _M(ma=[[-0.5]])
    m.ma_f = [object()]
    assert admissibility_problems(m) == []


# ── el caso real, y la ausencia de falsos positivos ───────────────────────

def _eq(rel, base=R):
    p = base + rel
    if not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _load_fitted
    from art.describe import model_equation
    ts, m = _load_fitted(p)
    return model_equation(ts, m)


def test_el_caso_real_aparece_en_la_ecuacion():
    eq = _eq("run3/RATIO/RATIO_m04sma1.pre")
    assert "NO ADMISIBLE" in eq
    assert "NO INVERTIBLE" in eq
    assert "0.8308" in eq


def test_la_frontera_habla_de_sobrediferenciacion():
    eq = _eq("run2/RATIO/RATIO_m22.pre", base=RDS)
    assert "FRONTERA" in eq
    assert "SOBREDIFERENCIACIÓN" in eq
    assert "formal_tests" in eq


@pytest.mark.parametrize("rel", ["guiado/PGAS/PGAS_m20.pre",
                                 "run2/PGAS/PGAS_m04.pre",
                                 "run3/RATIO/RATIO_m03.pre",
                                 "guiado/RATIO/RATIO_m31.pre"])
def test_los_modelos_buenos_no_reciben_aviso(rel):
    eq = _eq(rel)
    assert "NO ADMISIBLE" not in eq
    assert "EN LA FRONTERA" not in eq
