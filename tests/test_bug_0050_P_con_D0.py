"""BUG-0050 — P/Q no son «D=1 only», y decirlo manda a la ruta prohibida.

Un AR estacional ESTACIONARIO montado sobre los armónicos deterministas es la
forma en que la ruta B1 absorbe lo que los armónicos dejan. La documentación de
`confirm_and_estimate` decía que P y Q sólo valen con D=1: quien se lo crea
concluye que un AR estacional residual obliga a D=1, o sea a B2, que es la ruta
que `objetivo="multivariante"` prohíbe.
"""
import warnings

import numpy as np
import pytest

import fue
from art.pipeline import ModelSpec, build_and_fit


def _serie(n=120, Phi=0.65, seed=11):
    """D=0: armónico fijo + AR(1) estacional ESTACIONARIO sobre ∇ln."""
    rng = np.random.default_rng(seed)
    a = rng.standard_normal(n + 40)
    w = np.zeros(n + 40)
    for t in range(4, n + 40):
        w[t] = Phi * w[t - 4] + a[t]
    w = w[40:]
    t = np.arange(n)
    nivel = np.cumsum(w) / 40.0 + 0.06 * np.cos(2 * np.pi * t / 4.0)
    return fue.TimeSeries((100.0 * np.exp(nivel)).tolist(),
                          freq=4, start=(2000, 1), name="PD0")


def test_la_documentacion_no_afirma_D1_only():
    """El texto es la entrega: mientras lo diga, manda a B2 sin necesidad."""
    import art.mcp_server as M
    fn = getattr(M.confirm_and_estimate, "fn", M.confirm_and_estimate)
    doc = fn.__doc__ or ""
    assert "seasonal AR order (D=1 only)" not in doc
    assert "seasonal MA order (D=1 only)" not in doc


def test_un_AR_estacional_con_D0_se_estima_y_blanquea(tmp_path):
    """Lo que el motor hace de verdad, que es lo que la documentación negaba."""
    warnings.simplefilter("ignore")
    spec = ModelSpec(lam=0.0, d=1, D=0, p=0, q=0, P=1, Q=0,
                     n_harmonics=1, seasonal=True)
    fr = build_and_fit(_serie(), spec, str(tmp_path / "PD0.inp"), 3.5)

    assert fr.model is not None, "P=1 con D=0 tiene que estimarse"
    qmin = min(fr.diag.q_pvalues)
    assert qmin > 0.05, (
        f"el AR estacional con D=0 no blanqueó (Q p-mín={qmin:.4f}); "
        "el caso sintético ya no mide lo que dice medir")


def test_el_caso_real_del_proyecto_lleva_P1_con_D0():
    """Los dos RATIO finales son exactamente la combinación que se negaba."""
    import os
    R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/"
    encontrados = 0
    for f in ("guiado/RATIO/RATIO_m31.pre", "run2/RATIO/RATIO_m03.pre"):
        if not os.path.exists(R + f):
            continue
        L = open(R + f, encoding="utf-8", errors="replace").read().splitlines()
        P = D = None
        for i, l in enumerate(L):
            if "annual AR operators" in l:  P = L[i + 1].split()[0]
            if "Box-Cox lambda" in l:       D = L[i + 1].split()[2]
        assert (P, D) == ("1", "0"), f"{f}: P={P} D={D}"
        encontrados += 1
    if not encontrados:
        pytest.skip("datos de la réplica no disponibles")
