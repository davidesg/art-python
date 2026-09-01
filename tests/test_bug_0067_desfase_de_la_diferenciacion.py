"""BUG-0067 — los índices de RESIDUO y de SERIE no son el mismo espacio.

Los residuos de un modelo diferenciado empiezan `d + D·s` observaciones después
que la serie. `suggest_intervention_form` mezclaba los dos espacios en tres
sitios: la fecha auto-seleccionada, la comprobación de «ya cubierto», y el
argumento de `decide_form`.

Sobre el ITCER de la réplica (d=1) el escaneo dice —bien— «Q4/2008» y el
auto-select colocaba la intervención en Q3/2008.
"""
import os
import tempfile
import warnings

import numpy as np
import pytest

import fue

from datos_replica import REPLICA, requiere_replica

M00 = REPLICA + "run4/ITCER/ITCER_m00.pre" if REPLICA else ""


def _fn(name):
    import art.mcp_server as M
    f = getattr(M, name)
    return getattr(f, "fn", f)


@requiere_replica
def test_el_caso_tiene_desfase_que_medir():
    warnings.simplefilter("ignore")
    _, m = fue.load(M00)
    m.fit()
    assert m.d + m.D * m.series.freq == 1, "el caso ya no tiene desfase"


@requiere_replica
def test_la_fecha_autoseleccionada_es_la_del_escaneo(tmp_path):
    """El analista lee una fecha en el escaneo; el auto-select debe coger ÉSA."""
    warnings.simplefilter("ignore")
    escaneo = _fn("residual_outlier_scan")(M00)
    escaneo = escaneo[0].text if isinstance(escaneo, list) else str(escaneo)
    assert "Q4/2008" in escaneo, "el escaneo cambió; el test no mide nada"

    r = _fn("suggest_intervention_form")(M00, str(tmp_path / "a.inp"))
    t = r[0].text if isinstance(r, list) else str(r)
    assert "Q4/2008" in t
    assert "Q3/2008" not in t


@requiere_replica
def test_la_intervencion_queda_en_la_observacion_correcta(tmp_path):
    """No basta el rótulo: el `at` que va al modelo tiene que ser el bueno."""
    warnings.simplefilter("ignore")
    out = str(tmp_path / "b.inp")
    _fn("suggest_intervention_form")(M00, out)
    _, m = fue.load(out.replace(".inp", ".pre") if os.path.exists(
        out.replace(".inp", ".pre")) else out)
    itvs = [i for i in (m.interventions or [])
            if i.type not in ("cos", "sin", "alter")]
    assert len(itvs) == 1
    sy, sp = m.series.start
    off = (sp - 1) + itvs[0].at
    anio, trim = sy + off // 4, off % 4 + 1
    assert (anio, trim) == (2008, 4), f"la intervención cayó en Q{trim}/{anio}"


@requiere_replica
def test_no_se_repite_la_intervencion_ya_puesta(tmp_path):
    """La comprobación de «ya cubierto» comparaba residuo contra serie."""
    warnings.simplefilter("ignore")
    a = str(tmp_path / "c1.inp")
    _fn("suggest_intervention_form")(M00, a)
    base = a.replace(".inp", ".pre")
    if not os.path.exists(base):
        pytest.skip("no se escribió el .pre")
    b = str(tmp_path / "c2.inp")
    r = _fn("suggest_intervention_form")(base, b)
    t = r[0].text if isinstance(r, list) else str(r)
    # la segunda llamada no puede volver a proponer Q4/2008
    if "Fecha auto-detectada" in t:
        assert "Q4/2008" not in t.split("Fecha auto-detectada")[1][:60]
