"""BUG-0015 y BUG-0016 — dos decisiones que la capa guiada tomaba y el camino
autónomo no tenía por dónde pedir. La misma forma que BUG-0013, por tercera y
cuarta vez.

**BUG-0015** — la regla índice (λ=0 sobre un índice de precios, cuya base es una
convención) vivía dentro de `guided_identification`. `policy.decide_lambda` sólo
recibía las estadísticas Box-Cox, así que la regla no tenía argumento por donde
entrar: el protocolo tomaba EVIDENCIA y nunca DOMINIO. El autónomo partía una
familia de ocho IPC —4 en logs, 4 en niveles— por el signo de un gap cuyo valor
absoluto nunca pasó de 0.304.

**BUG-0016** — `decide_d` tomaba el consenso ADF+KPSS a pelo, sin ver la decisión
estacional que `run_full` ya había tomado tres líneas antes. El ADF no lleva
términos estacionales, así que el patrón infla su error típico y sesga hacia no
rechazar: las dos series que sobrediferenciaban eran exactamente las dos primeras
del ranking de estacionalidad, con corte limpio en F-HAC ≈ 50.

**Van juntos a propósito.** Con λ=1, IPC_ES no sobrediferenciaba; arreglada la
regla índice, sí. Arreglar 0015 solo habría hecho que 0016 disparara en más
series y pareciera una regresión del arreglo.
"""
import os

import pytest

from art import policy


class _TS:
    """Lo mínimo que `decide_domain` mira."""
    def __init__(self, name):
        self.name = name


# ── BUG-0015: el dominio como decisión ─────────────────────────────────────

@pytest.mark.parametrize("name,expected", [
    ("IPC_ES", "price_index"), ("CPI_USA", "price_index"),
    ("index_foo", "price_index"), ("price_wti", "price_index"),
    ("WTI", "generic"), ("serie3", "generic"), ("", "generic"),
])
def test_decide_domain(name, expected):
    assert policy.decide_domain(_TS(name)) == expected


def test_the_index_rule_overrides_the_statistic():
    """λ=0 en un índice pase lo que pase: su base es una convención."""
    # gap negativo = la estadística pide niveles
    assert policy.decide_lambda({"gap": -0.272}) == 1.0
    assert policy.decide_lambda({"gap": -0.272}, "price_index") == 0.0
    # y no fuerza logs sobre lo que no es un índice
    assert policy.decide_lambda({"gap": -0.272}, "generic") == 1.0


def test_a_declared_domain_beats_the_name():
    """El nombre es evidencia débil; declararlo es lo que se audita.

    Un modelo no puede salir distinto porque el fichero se llamara `IPC_ES` en
    vez de `serie3`, así que lo inferido tiene que poder vetarse.
    """
    ipc = _TS("IPC_ES")
    assert policy.DefaultPolicy().decide_domain(ipc) == "price_index"
    assert policy.ClaudePolicy(domain="generic").decide_domain(ipc) == "generic"
    assert policy.ClaudePolicy(domain="price_index").decide_domain(_TS("x")) == "price_index"
    assert policy.ClaudePolicy().decide_domain(ipc) == "price_index"   # silencio = la regla


def test_the_guided_layer_no_longer_carries_its_own_copy():
    """La regla estaba escrita dos veces y sólo una de las dos corría en el
    camino autónomo. Ahora hay una."""
    src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "src", "art", "mcp_server.py"), encoding="utf-8").read()
    assert "_INDEX_PREFIXES" not in src
    assert "policy.decide_domain(ts)" in src


# ── BUG-0016: el tope de d ─────────────────────────────────────────────────

def test_seasonality_caps_d_at_one():
    assert policy.decide_d({"recommended_d": 2}, seasonal=True) == 1
    assert policy.decide_d({"recommended_d": 3}, seasonal=True) == 1


def test_one_step_at_a_time_applies_with_or_without_seasonality():
    """The one-step rule is the method, not an option, and for two reasons.

    The question asked from the level is not "how many differences?" but "is at
    least one regular difference needed?". Seasonality is normally read on a
    series already differenced once, so from d=0 the question of a SECOND
    difference has never been put. Jumping 0 → 2 answers a question nobody asked.

    And take the obvious step first: if d=1 is the obvious reading, d=2 is not
    reachable from d=0 in one move.

    Nothing is lost by starting low. ADF and KPSS are tools of initial
    specification; the real contrast on d comes at the end of the process, on an
    adequate and correctly specified model (`dcd_overdiff_regular`,
    Shin-Fuller), which is where this flow already puts it.
    """
    for seasonal in (True, False, None):
        assert policy.decide_d({"recommended_d": 2}, seasonal=seasonal) == 1
        assert policy.decide_d({"recommended_d": 3}, seasonal=seasonal) == 1


def test_from_d1_the_second_difference_is_reachable():
    """Capping is not forbidding: from d=1 the second difference has been asked
    about, so it is reachable."""
    assert policy.decide_d({"recommended_d": 2}, current_d=1) == 2
    assert policy.decide_d({"recommended_d": 3}, current_d=1) == 2
    # ...salvo que la estacionalidad siga sin tratar, que es el otro tope
    assert policy.decide_d({"recommended_d": 2}, seasonal=True, current_d=1) == 1


def test_the_evidence_layer_is_left_alone():
    """El tope es de POLÍTICA: `recommended_d` sigue diciendo lo que los tests
    hallaron, así que en la tabla se ve que se sugirió 2 y que se topó."""
    data = {"recommended_d": 2}
    assert policy.decide_d(data, seasonal=True) == 1
    assert data["recommended_d"] == 2


def test_claude_policy_still_overrides_d():
    p = policy.ClaudePolicy(d=2)
    assert p.decide_d({"recommended_d": 1}, seasonal=True) == 2


# ── la tabla real, que es la prueba con respuesta conocida ─────────────────

_IPC = os.path.expanduser("~/Dropbox/Nivel de Precios y Energia/IPC.xlsx")

# serie -> (¿el detector la ve como índice?, F-HAC alto ⇒ sobrediferenciaba)
_SERIES = ["IPC_ES", "IPC_FR", "IPC_DE", "CPI_USA", "EMU", "IPC_JP",
           "IPC_CA", "IPC_UK"]


@pytest.mark.skipif(not os.path.exists(_IPC), reason="IPC.xlsx not present")
@pytest.mark.parametrize("series", _SERIES)
def test_the_eight_cpi_indices_come_out_alike(series):
    """Ocho índices del mismo tipo, una ventana, una fuente: el pipeline los
    trataba 4 en logs y 4 en niveles, y dos de ellos con d=2. Nada en los datos
    dice que difieran en clase.
    """
    import fue
    import pandas as pd
    from art.pipeline import run_full

    df = pd.read_excel(_IPC)
    df["FECHA"] = pd.to_datetime(df["FECHA"])
    df = df[(df.FECHA >= "2002-01-01") & (df.FECHA <= "2019-12-31")]
    y = df[series].dropna().to_numpy(float)
    ts = fue.TimeSeries(list(y), freq=12, start=(2002, 1), name=series)

    import tempfile
    r = run_full(ts, os.path.join(tempfile.mkdtemp(), f"{series}.inp"), max_rounds=1)
    assert r.lam == 0.0, f"{series}: en NIVELES (BUG-0015)"
    assert r.d == 1, f"{series}: d={r.d} (BUG-0016)"
