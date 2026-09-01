"""BUG-0066 — el signo de ω en los retardos ≥1 es RESTADO, no crudo.

`fue` calcula la respuesta de una intervención como `nu[j] = Σ δ·nu[j−i] − ω[j]`
(`calcnu()` en `fue_api.c`): ω₀ − ω₁B − ω₂B² − …, la misma convención que AR y MA.
El display usaba el signo crudo, así que el término B salía invertido.

El invariante que se fija: **lo que se dibuja tiene que ser lo que responde.**
"""
import importlib
import os
import warnings

import pytest

import fue
from art.describe import model_equation

from datos_replica import REPLICA, requiere_replica

_fc = importlib.import_module("fue.forecast")


def _respuesta(itv, lags=4):
    return [float(x) for x in _fc._calcnu(
        [float(x) for x in itv.omega],
        [float(x) for x in (itv.delta or [])], lags)]


def _signos_del_display(linea):
    """Los signos que el display pone delante de cada término, en orden."""
    import re
    cuerpo = linea[linea.index("(") + 1:linea.index(")")]
    # el primer término lleva su signo pegado; los siguientes van con − o +
    trozos = re.split(r"\s+([−+])\s+", cuerpo)
    signos = [-1.0 if trozos[0].strip().startswith("-") else 1.0]
    for i in range(1, len(trozos), 2):
        signos.append(-1.0 if trozos[i] == "−" else 1.0)
    return signos


@requiere_replica
@pytest.mark.parametrize("rel", ["guiado/ITCER/ITCER_m10.pre",
                                 "guiado/RATIO/RATIO_m31.pre"])
def test_el_display_coincide_con_la_respuesta(rel):
    """El invariante: signo dibujado = signo de la respuesta, término a término."""
    p = REPLICA + rel
    if not os.path.exists(p):
        pytest.skip("modelo no disponible")
    warnings.simplefilter("ignore")
    ts, m = fue.load(p)
    m.fit()
    itvs = [i for i in (m.interventions or [])
            if i.type not in ("cos", "sin", "alter") and len(i.omega or []) > 1]
    if not itvs:
        pytest.skip("este modelo no tiene ω(B) de orden ≥1")

    lineas = [l for l in model_equation(ts, m).splitlines()
              if "ξ" in l and "·B" in l]
    assert len(lineas) >= len(itvs)

    for itv, linea in zip(itvs, lineas):
        nu = _respuesta(itv, len(itv.omega))
        signos = _signos_del_display(linea)
        for k, (s_disp, v_nu) in enumerate(zip(signos, nu)):
            if abs(v_nu) < 1e-9:
                continue
            assert s_disp * abs(v_nu) == pytest.approx(v_nu, abs=1e-6), (
                f"{rel} término {k}: el display dice signo {s_disp:+.0f} y la "
                f"respuesta es {v_nu:+.4f}")


@requiere_replica
def test_el_caso_que_lo_delato():
    """ITCER: ω=[−8.9851, +8.9352] responde [−8.9851, −8.9352] — SE SUMAN."""
    p = REPLICA + "guiado/ITCER/ITCER_m10.pre"
    if not os.path.exists(p):
        pytest.skip("modelo no disponible")
    warnings.simplefilter("ignore")
    ts, m = fue.load(p)
    m.fit()
    itv = [i for i in m.interventions if len(i.omega or []) > 1][0]
    nu = _respuesta(itv, 1)
    assert nu[0] < 0 and nu[1] < 0, "el caso ya no ilustra la suma"
    linea = [l for l in model_equation(ts, m).splitlines() if "ξ" in l][0]
    assert "− 8.9352·B" in linea, f"el display sigue invirtiendo el término B: {linea}"
    assert "+ 8.9352·B" not in linea


def test_omega_cero_lleva_signo_crudo(tmp_path):
    """ω₀ entra tal cual: la corrección no puede alcanzarlo."""
    warnings.simplefilter("ignore")
    from datos_replica import REPLICA as R
    p = R + "guiado/PGAS/PGAS_m20.pre" if R else ""
    if not p or not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    ts, m = fue.load(p)
    m.fit()
    itv = [i for i in (m.interventions or [])
           if i.type not in ("cos", "sin", "alter")]
    if not itv or len(itv[0].omega or []) != 1:
        pytest.skip("este modelo no tiene una intervención de un solo ω")
    v = float(itv[0].omega[0])
    linea = [l for l in model_equation(ts, m).splitlines() if "ξ" in l][0]
    assert ("−" in linea) == (v < 0)
