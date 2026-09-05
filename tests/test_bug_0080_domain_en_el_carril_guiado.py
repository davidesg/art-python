"""BUG-0080 — `domain` no era alcanzable desde el carril guiado.

`policy.decide_domain` declara de sí misma que su inferencia es una SUGERENCIA y
que **lo declarado gana siempre** — y con razón: un índice *«no tiene firma en
el dato que lo distinga de cualquier otra magnitud positiva; lo que lo define es
que su nivel es una convención, y eso no se ve en la serie»*. El dominio lo pone
el analista.

Pero `domain=` sólo existía en `build_model`. Recorriendo los nodos uno a uno no
había forma de declararlo, así que sobre el HICP de alimentos de la UEM art
publicó **«Recomendación: identidad (λ=1)»** sobre un índice de precios y el
carril guiado no ofrecía dónde corregirlo.

Es el mismo defecto que `objetivo` tuvo, en la misma función y para el parámetro
de al lado.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art import policy
from art.pipeline import _RESCALE_FACTOR, _write_inp

GID = getattr(srv.guided_identification, "fn", srv.guided_identification)
CE = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)


def _txt(res):
    return "\n".join(getattr(c, "text", "") for c in res)


@pytest.fixture(scope="module")
def indice(tmp_path_factory):
    """Una serie que el estadístico manda dejar en niveles.

    Varianza homogénea en la escala original, así que `gap < 0` y
    `recommended_lambda` sale 1.0 — el caso de FOOD_UEM. Lo que la convierte en
    un índice no está en el dato: lo dice el analista.

    Y el NOMBRE tampoco puede delatarlo, o la prueba no probaría nada:
    `decide_domain` mira `_INDEX_PREFIXES`, y «IDX…» habría devuelto
    `price_index` sola. Ése es justo el mecanismo que falló sobre FOOD_UEM —el
    nombre no cruzaba la lista— y por el que hace falta poder declararlo.
    """
    d = tmp_path_factory.mktemp("dom")
    # seed 1: gap = -0.0376, así que el estadístico recomienda λ=1 — el caso
    # de FOOD_UEM, donde gap=-0.179 con el IC de la correlación cruzando cero
    # en las dos escalas: el estadístico se abstiene y el signo decide.
    rng = np.random.default_rng(1)
    y = 100.0 + np.cumsum(rng.standard_normal(160) * 0.4)
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1985, 1), name="SERIE_X")   # el nombre NO puede delatar el dominio
    m = fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f = str(d / "idx.inp")
    _write_inp(ts, m, f)
    return f, str(d)


# ───────────────── la puerta que faltaba ─────────────────

def test_guided_identification_acepta_domain():
    import inspect
    assert "domain" in inspect.signature(GID).parameters


def test_confirm_and_estimate_acepta_domain():
    import inspect
    assert "domain" in inspect.signature(CE).parameters


def test_declarar_indice_impone_log_aunque_el_estadistico_diga_lo_contrario(indice):
    f, _ = indice
    sin = _txt(GID(f))
    con = _txt(GID(f, domain="price_index"))
    assert "lam=1.0" in sin, "la fixture ya no reproduce el caso: revísala"
    assert "lam=0.0" in con
    assert "REGLA DE DOMINIO APLICADA" in con


def test_la_recomendacion_anulada_no_se_deja_contradiciendo(indice):
    """Dejar «Confirma λ=1.0» encima de una nota que impone λ=0 son dos
    instrucciones contrarias en la misma pantalla, y la de arriba se lee
    primero. La EVIDENCIA del estadístico sí se conserva verbatim."""
    f, _ = indice
    t = _txt(GID(f, domain="price_index"))
    assert "queda anulada por la regla de dominio" in t
    assert "Correlación media-std" in t          # la evidencia sigue ahí


def test_la_salida_dice_si_el_dominio_es_declarado_o_inferido(indice):
    f, _ = indice
    assert "declarado por el analista" in _txt(GID(f, domain="price_index"))


def test_un_dominio_declarado_que_coincide_tambien_se_anota(indice):
    f, _ = indice
    t = _txt(GID(f, domain="generic"))
    assert "generic" in t
    assert "REGLA DE DOMINIO APLICADA" not in t


def test_un_dominio_inventado_se_rechaza_con_la_lista(indice):
    f, _ = indice
    t = _txt(GID(f, domain="precio_del_gas"))
    assert "❌" in t
    for d in policy.DOMINIOS:
        assert d in t


# ───────────────── las otras dos categorías, que tampoco llegaban ─────────────

def test_multiplicative_y_ratio_tambien_llegan_ahora(indice):
    """La copia que había en la capa guiada implementaba SÓLO la rama del
    índice, así que las dos categorías que BUG-0040 añadió no llegaban al carril
    guiado ni declarándolas. Ahora se enruta por `decide_lambda`, que las tiene
    todas."""
    f, _ = indice
    for dom in ("multiplicative", "ratio"):
        t = _txt(GID(f, domain=dom))
        assert "lam=0.0" in t, f"{dom} no impuso el log"


def test_la_regla_sigue_viviendo_en_policy():
    """Una copia, dos caminos — que es lo que produjo BUG-0015."""
    from _fuente import fuente_de
    src = fuente_de(GID)
    assert "policy.decide_lambda" in src


# ───────────────── confirm_and_estimate ─────────────────

def test_declarar_indice_con_lambda_1_avisa_de_la_contradiccion(indice):
    f, d = indice
    t = _txt(CE(f, os.path.join(d, "c1.inp"), lam=1.0, d=1, D=0, p=0, q=0,
                n_harmonics=0, domain="price_index"))
    assert "λ=1" in t
    assert "escala interpretable" in t


def test_declarar_indice_con_lambda_0_no_avisa(indice):
    f, d = indice
    t = _txt(CE(f, os.path.join(d, "c2.inp"), lam=0.0, d=1, D=0, p=0, q=0,
                n_harmonics=0, domain="price_index"))
    assert "escala interpretable" not in t


def test_el_aviso_no_bloquea_la_estimacion(indice):
    """El analista manda: se dice y se estima lo que ha pedido."""
    f, d = indice
    out = os.path.join(d, "c3.inp")
    t = _txt(CE(f, out, lam=1.0, d=1, D=0, p=0, q=0, n_harmonics=0,
                domain="price_index"))
    assert os.path.exists(out)
    assert "MODELO ESTIMADO" in t


def test_el_dominio_queda_en_el_guion(indice):
    """No se puede recuperar releyendo el `.inp`: es un dato del analista. Si no
    queda registrado, la razón por la que λ vale lo que vale se pierde."""
    import json
    f, d = indice
    g = os.path.join(d, "g80.json")
    CE(f, os.path.join(d, "c4.inp"), lam=0.0, d=1, D=0, p=0, q=0,
       n_harmonics=0, domain="price_index", guion_path=g,
       guion_decision="prueba")
    with open(g) as fh:
        gg = json.load(fh)
    assert gg["entries"][0]["spec"].get("dominio") == "price_index"


def test_sin_domain_no_se_inventa_nada_en_el_guion(indice):
    import json
    f, d = indice
    g = os.path.join(d, "g80b.json")
    CE(f, os.path.join(d, "c5.inp"), lam=0.0, d=1, D=0, p=0, q=0,
       n_harmonics=0, guion_path=g, guion_decision="prueba")
    with open(g) as fh:
        gg = json.load(fh)
    assert "dominio" not in gg["entries"][0]["spec"]


def test_confirm_and_estimate_rechaza_un_dominio_inventado(indice):
    f, d = indice
    t = _txt(CE(f, os.path.join(d, "c6.inp"), lam=0.0, d=1, D=0, p=0, q=0,
                n_harmonics=0, domain="chorizo"))
    assert "❌" in t
