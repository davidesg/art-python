"""BUG-0043 — cuatro fallos de presentación que el experimento del chat limpio
encontró, y uno de ellos deja al analista sin el nodo correcto.

Los cuatro salieron de correr el protocolo sin contexto previo, y comparten
forma: la salida dice algo que no es, o no dice lo que sabe.

1. **JB que falla sin anómalos ⇒ λ.** El consejo era «revisa la especificación»
   (nada) o, cuando había extremos, «la no-normalidad está causada por los
   outliers» — que manda a añadir intervenciones. Sobre un modelo en NIVELES de
   una magnitud positiva de recorrido amplio, eso es perseguir el síntoma: la
   heterocedasticidad que el log elimina se manifiesta a la vez como asimetría y
   como residuos grandes. Medido: un carril autónomo con λ=1 sobre un precio
   estimó seis modelos consecutivos sin alcanzar la adecuación, con el JB de 46.7
   a 8.9, y nada le dijo que volviera al nodo de λ.
2. **La media descentrada no tenía rama**, así que un modelo cuyo único fallo era
   ése cerraba con «Reformulación necesaria: .» — la razón vacía.
3. **`freq=` vacío** cuando el contraste conjunto detecta estacionalidad residual
   y ninguna frecuencia es significativa por separado.
4. **Porcentajes con denominador ≈0**: −1162%, −1561%, +687%, impresos junto a
   ACF_max=0%. El criterio de decisión ya los excluía; faltaba no publicarlos.
5. **Recetas contradictorias**: tras concluir «Decisión A — sin estacionalidad»,
   la misma respuesta imprimía la ruta B1 completa con `n_harmonics=1` y la B2
   con D=1.
"""
import numpy as np
import pytest

import fue
from art.describe import describe_diagnosis
from art.pipeline import _write_inp, _load_fitted

from datos_replica import REPLICA, REPLICA_DS, requiere_replica



def _fit(ts, tmp_path, nombre, **kw):
    ruta = str(tmp_path / f"{nombre}.inp")
    m = fue.Model(ts, **kw)
    _write_inp(ts, m, ruta)
    _, mf = _load_fitted(ruta)
    return mf


def _precio(n=84, seed=7):
    """Positivo, recorrido de factor ~5: el caso en que el nivel no vale."""
    rng = np.random.default_rng(seed)
    y = 300.0 + 200.0 * np.sin(np.linspace(0, 2.2 * np.pi, n)) + 25 * rng.standard_normal(n)
    return fue.TimeSeries(np.clip(y, 95.0, None).tolist(), freq=4,
                          start=(2004, 1), name="PRECIO")


def test_a_level_model_of_a_wide_range_positive_series_names_lambda(tmp_path):
    ts = _precio()
    m = _fit(ts, tmp_path, "niveles", boxlam=1.0, d=1, ma=[[0.0]],
             ma_free=[[True]], mu=0.0, estimate_mu=False)
    rec = describe_diagnosis(m).recommendation
    if "normal" not in rec.lower() and "JB" not in rec:
        pytest.skip("este testigo sintético no rompió la normalidad")
    assert "λ" in rec, "la recomendación no nombra la transformación"
    assert "escala" in rec or "niveles" in rec


def test_the_same_model_in_logs_does_not_get_the_lambda_warning(tmp_path):
    """La otra cara: no sembrar dudas sobre λ en un modelo que ya está en logs."""
    ts = _precio()
    m = _fit(ts, tmp_path, "logs", boxlam=0.0, d=1, ma=[[0.0]],
             ma_free=[[True]], mu=0.0, estimate_mu=False)
    rec = describe_diagnosis(m).recommendation
    assert "es λ" not in rec


def test_an_uncentred_mean_gets_a_reason(tmp_path):
    """Antes: «Reformulación necesaria: .»"""
    rng = np.random.default_rng(11)
    y = 100.0 + np.cumsum(rng.standard_normal(120) + 0.8)
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="DERIVA")
    m = _fit(ts, tmp_path, "deriva", boxlam=1.0, d=1, ma=[[0.0]],
             ma_free=[[True]], mu=0.0, estimate_mu=False)
    rec = describe_diagnosis(m).recommendation
    assert rec.strip() not in ("Reformulación necesaria: .", "")
    if not describe_diagnosis(m).summary:
        pytest.skip("sin diagnosis")
    from art.diagnosis import diagnose
    if diagnose(m).centred:
        pytest.skip("este testigo no descentró la media")
    assert "media residual" in rec


def test_the_recommendation_is_never_an_empty_reason(tmp_path):
    """Invariante: si el modelo no es adecuado, hay un motivo escrito."""
    from art.diagnosis import diagnose
    rng = np.random.default_rng(3)
    for i, y in enumerate((100.0 + np.cumsum(rng.standard_normal(120) + 0.8),
                           100.0 + np.cumsum(rng.standard_normal(120)))):
        ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name=f"S{i}")
        m = _fit(ts, tmp_path, f"s{i}", boxlam=1.0, d=1, ma=[[0.0]],
                 ma_free=[[True]], mu=0.0, estimate_mu=False)
        rec = describe_diagnosis(m).recommendation
        if not diagnose(m).clean:
            assert "Reformulación necesaria: ." != rec.strip()
            assert len(rec) > 40, f"razón demasiado corta para ser una razón: {rec!r}"


@requiere_replica
def test_marginal_joint_seasonality_says_so_instead_of_an_empty_field():
    """El testigo real: conjunto p=0.0492 y ninguna frecuencia significativa."""
    import os
    ruta = (REPLICA + "autonomo/"
            "RATIO/RATIO_m80.inp")
    if not os.path.exists(ruta):
        pytest.skip("el testigo de la réplica no está en esta máquina")
    _ts, m = fue.load(ruta)
    m.fit()
    rec = describe_diagnosis(m).recommendation
    assert "freq=" not in rec or "freq= " not in rec
    assert "NINGUNA frecuencia" in rec or "freq=" in rec


@requiere_replica
def test_percentages_are_only_given_where_the_acf_is_out_of_band(tmp_path):
    """Donde la ACF ronda cero el cociente se dispara sin significar nada."""
    import re
    from art import mcp_server as M
    salida = str(tmp_path / "I.inp")
    t = M.confirm_and_estimate(
        REPLICA + "ITCER.inp", salida,
        lam=0.0, d=1, D=0, p=0, q=0, n_harmonics=0, seasonal=False,
        estimate_mu=True)[0].text
    linea = [l for l in t.splitlines() if "Retardos ACF" in l]
    if not linea:
        pytest.skip("esta corrida no produjo el bloque de retardos")
    pcts = [abs(int(x)) for x in re.findall(r"\(([+-]\d+)%\)", linea[0])]
    assert pcts, "no quedó ningún porcentaje"
    assert max(pcts) <= 200, f"porcentaje con denominador nulo: {linea[0]}"


@requiere_replica
def test_no_seasonality_prints_no_route_recipes():
    """Una salida que concluye A y luego imprime la receta de B1 es una
    instrucción para hacer lo contrario de lo que acaba de concluir."""
    from art import mcp_server as M
    t = M.guided_identification(
        REPLICA + "ITCER.inp",
        lam=0.0, d=1)[0].text
    assert "Decisión A" in t
    assert "Route B1" not in t and "Route B2" not in t
    assert "no hay estacionalidad que enrutar" in t


@requiere_replica
def test_with_seasonality_the_recipes_are_still_there():
    from art import mcp_server as M
    t = M.guided_identification(
        REPLICA + "RATIO.inp",
        lam=0.0, d=1)[0].text
    assert "Route B1" in t and "Route B2" in t
