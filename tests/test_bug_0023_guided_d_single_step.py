"""BUG-0023 — el nodo guiado de `d` saltaba de d=0 a d=2 de una vez.

En la escuela no se saltan dos decisiones sin pasar por los instrumentos de
especificación y diagnosis: desde d=0 sólo se va a d=1 o se queda en d=0. Y el
motivo técnico acompaña al metodológico: la regresión del ADF no lleva términos
estacionales, así que con estacionalidad fuerte el patrón cae en su varianza
residual y sesga el contraste hacia no rechazar — o sea, hacia "vuelve a
diferenciar". Fallar en d=0 y en d=1 es la firma de un contraste sin potencia,
no una licencia para ir a 2.

El tope NO va en `recommended_d`, que es la capa de evidencia (ver
test_bug_0015_0016 y test_bug_0002): va en quien la llama.
"""
import os
import tempfile

import numpy as np
import pytest

from art import mcp_server as A
from art.identification import unit_root_tests, recommended_d
from art.pipeline import _load_ts_model
from art.describe import describe_unit_root, describe_seasonality
from art import policy as pol


def _serie(patron, seed=5, n=84):
    """Paseo aleatorio (d=1 por construcción) + patrón trimestral fijo."""
    rng = np.random.default_rng(seed)
    y = 100.0 + np.cumsum(rng.normal(0, 1.0, n)) + np.tile(np.asarray(patron, float),
                                                           n // 4)
    d = tempfile.mkdtemp(prefix="bug0023-")
    inp = os.path.join(d, "S.inp")
    A.create_inp(list(map(float, y)), inp, name="S", freq=4,
                 start_year=2004, start_period=1)
    ts, _ = _load_ts_model(inp)
    return ts


ESTACIONAL = [-8.0, +1.5, +1.0, +5.5]      # Q1 bajo, Q4 alto


def _serie_i2(seed=4, n=84):
    """I(2) genuina y SIN estacionalidad: aquí el aviso «Considera d=2» es
    legítimo y debe conservarse. Es el control del arreglo."""
    rng = np.random.default_rng(seed)
    y = 100.0 + np.cumsum(np.cumsum(rng.normal(0, 1.0, n)))
    d = tempfile.mkdtemp(prefix="bug0023-i2-")
    inp = os.path.join(d, "S2.inp")
    A.create_inp(list(map(float, y)), inp, name="S2", freq=4,
                 start_year=2004, start_period=1)
    ts, _ = _load_ts_model(inp)
    return ts


@pytest.fixture(scope="module")
def ts_estacional():
    return _serie(ESTACIONAL)


def test_el_caso_sigue_siendo_el_que_muerde(ts_estacional):
    """Sin el tope, la evidencia manda a d=2 sobre una serie cuyo d es 1."""
    assert recommended_d(unit_root_tests(ts_estacional, lam=1.0, max_d=2)) == 2


def test_capada_en_d1_la_recomendacion_es_1(ts_estacional):
    assert recommended_d(unit_root_tests(ts_estacional, lam=1.0, max_d=1)) == 1


def test_el_nodo_guiado_no_tabula_d2(ts_estacional):
    """El paso 2 evalúa DESDE d=0 y sólo ofrece d=0 o d=1: no puede tabular 2."""
    urt = describe_unit_root(ts_estacional, lam=1.0, max_d=1)
    niveles = [row["d"] for row in urt.data["results"]]
    assert niveles == [0, 1]
    assert urt.data["recommended_d"] <= 1
    assert "| 2 |" not in urt.summary


def test_con_estacionalidad_no_se_sugiere_d2(ts_estacional):
    """El aviso salía TRES LÍNEAS después de detectar la estacionalidad."""
    seas = describe_seasonality(ts_estacional)
    assert bool(seas.data["seasonal_detected"]) is True
    assert "Considera d=2" not in seas.summary
    assert "no es evidencia de d=2" in seas.summary


def test_sin_estacionalidad_el_aviso_se_conserva():
    """Donde el aviso es legítimo debe seguir apareciendo: I(2) y sin estacionalidad."""
    seas = describe_seasonality(_serie_i2())
    assert bool(seas.data["seasonal_detected"]) is False
    assert bool(seas.data["d_stationary"]) is False   # numpy.bool_, de ahí el bool()
    assert "Considera d=2" in seas.summary


# ─────────────────────────────────────────────────────────────────────────────
# El tope es RELATIVO, no una prohibición de d=2
#
# Evaluada d=1 se estudia la estacionalidad. A PARTIR DE ESE MOMENTO preguntar
# por d=2 es legítimo: la primera decisión está tomada y, si no hay
# estacionalidad, ya no queda nada que contamine el ADF. Lo que la escuela
# prohíbe es saltarse la decisión intermedia, no llegar a d=2.
#
# La otra mitad de BUG-0023: `decide_d` admitía `current_d` desde el arreglo de
# BUG-0016, pero NADIE lo llamaba una segunda vez, así que el carril autónomo no
# alcanzaba d=2 jamás — ni sobre una I(2) limpia. Defecto espejo: el guiado
# sobrediferenciaba, el autónomo subdiferenciaba.
# ─────────────────────────────────────────────────────────────────────────────


def _dos_pasos(ts, lam=1.0):
    """La secuencia de la escuela: d -> estacionalidad -> ¿d+1?"""
    urt  = describe_unit_root(ts, lam=lam, max_d=2)
    seas = describe_seasonality(ts)
    dec  = pol.decide_seasonal_structure(seas.data, ts.freq)[1]
    paso1 = pol.decide_d(urt.data, seasonal=(dec != "A"))
    paso2 = pol.decide_d(urt.data, seasonal=False, current_d=paso1) if dec == "A" else paso1
    return dict(evidencia=int(urt.data["recommended_d"]),
                estacional=bool(seas.data["seasonal_detected"]),
                paso1=paso1, paso2=paso2)


def _serie_i1(seed=4, n=84):
    rng = np.random.default_rng(seed)
    return _desde_valores(100.0 + np.cumsum(rng.normal(0, 1.0, n)), "i1")


def _desde_valores(y, tag):
    d = tempfile.mkdtemp(prefix=f"bug0023-{tag}-")
    inp = os.path.join(d, "S.inp")
    A.create_inp(list(map(float, y)), inp, name="S", freq=4,
                 start_year=2004, start_period=1)
    ts, _ = _load_ts_model(inp)
    return ts


def test_i2_sin_estacionalidad_alcanza_d2_en_el_segundo_paso():
    """El caso que el carril autónomo no podía resolver: d=1 -> sin
    estacionalidad -> d=2, que es exactamente la secuencia legítima."""
    r = _dos_pasos(_serie_i2())
    assert r["evidencia"] == 2          # la evidencia lo pedía desde el principio
    assert r["estacional"] is False     # y nada la contamina
    assert r["paso1"] == 1              # pero primero se pasa por d=1
    assert r["paso2"] == 2              # y ENTONCES d=2 es legítimo


def test_i1_sin_estacionalidad_se_queda_en_d1():
    """El segundo paso no es automático: sólo se da si la evidencia lo pide."""
    r = _dos_pasos(_serie_i1())
    assert r["estacional"] is False
    assert r["paso1"] == 1
    assert r["paso2"] == 1


def test_con_estacionalidad_el_segundo_paso_NO_se_ofrece(ts_estacional):
    """Con estacionalidad sin tratar el ADF sigue sesgado: d se topa en 1
    aunque la evidencia cruda diga 2."""
    r = _dos_pasos(ts_estacional)
    assert r["evidencia"] == 2
    assert r["estacional"] is True
    assert r["paso1"] == 1
    assert r["paso2"] == 1


def test_el_nodo_guiado_ofrece_el_segundo_paso_sin_estacionalidad():
    """Sin estacionalidad, el paso 3 del guiado debe tabular d -> d+1."""
    from art import mcp_server as M
    out = M.guided_identification(
        _escribe(_serie_i2()), lam=1.0, d=1, D=-1)
    texto = "\n".join(c.text for c in out if hasattr(c, "text"))
    assert "¿Hace falta una diferencia más?" in texto
    assert "| 2 |" in texto              # la tabla llega a d=2, ya legítimamente


def test_el_nodo_guiado_NO_ofrece_el_segundo_paso_con_estacionalidad(ts_estacional):
    from art import mcp_server as M
    out = M.guided_identification(
        _escribe(ts_estacional), lam=1.0, d=1, D=-1)
    texto = "\n".join(c.text for c in out if hasattr(c, "text"))
    assert "¿Hace falta una diferencia más?" not in texto


def _escribe(ts):
    """Devuelve una ruta .inp para la serie dada (el MCP toma rutas)."""
    d = tempfile.mkdtemp(prefix="bug0023-path-")
    inp = os.path.join(d, "S.inp")
    A.create_inp([float(v) for v in ts.data], inp, name="S", freq=ts.freq,
                 start_year=2004, start_period=1)
    return inp


def test_el_tercer_caso_la_tabla_recomienda_MENOS_que_la_d_actual():
    """`recommended_d` recorre la tabla entera y puede devolver un valor POR
    DEBAJO de la d confirmada. Eso no contesta «¿hace falta una MÁS?»: reabre una
    decisión ya tomada. El nodo debe decir que no hace falta otra diferencia y
    remitir la sospecha de sobrediferenciación al DCD sobre el modelo estimado,
    no a un ADF sobre la serie."""
    from art import mcp_server as M
    # I(0) con algo de persistencia: la tabla recomendará d=0 aunque entremos con d=1
    rng = np.random.default_rng(3)
    n = 84
    y = np.zeros(n)
    for t in range(1, n):
        y[t] = 0.7 * y[t - 1] + rng.normal(0, 1.0)
    ts = _desde_valores(y + 100.0, "menos")

    urt = describe_unit_root(ts, lam=1.0, max_d=2)
    if int(urt.data["recommended_d"]) >= 1:
        pytest.skip("esta realización no recomienda por debajo de d=1")

    out = M.guided_identification(_escribe(ts), lam=1.0, d=1, D=-1)
    texto = "\n".join(c.text for c in out if hasattr(c, "text"))
    assert "No hace falta otra diferencia" in texto
    assert "POR DEBAJO de la d=1 confirmada" in texto
    assert "DCD sobre el MODELO ESTIMADO" in texto
    # y NO debe invitar a reentrar con d=2
    assert "La evidencia apunta a **d=2**" not in texto
