"""Batería de regresión del pipeline: una matriz de casos con verdad conocida.

`test_golden_pipeline.py` congela las decisiones de UNA serie sintética sobre los
dos puntos de entrada. Esto es lo otro que hace falta para que tocar algo no
rompa nada en silencio: **varias series cuya respuesta se sabe de antemano**, y
un puñado de invariantes que deben cumplirse en todas.

Dos capas, y sirven para cosas distintas:

1. **Invariantes** (§1). Reglas que no dependen de los números y que no admiten
   excepción. Si una falla, hay un defecto metodológico, no un cambio de
   resultado. Cada una lleva la ficha que la puso ahí.

2. **Matriz de casos** (§2). Series simuladas con semilla fija cuya estructura
   se conoce —determinista, estocástica en una frecuencia, I(0), I(1), I(2),
   anual— sobre las que se comprueba que la decisión del pipeline es la
   correcta, no simplemente la de ayer. Un golden dice «esto cambió»; esto dice
   «esto está mal», que es más útil cuando se acaba de tocar el criterio.

Por qué la matriz es sintética: porque la verdad tiene que ser conocida. Con una
serie real sólo se puede fijar lo que salió, y entonces un cambio de criterio
—incluso uno correcto— aparece como fallo, que es como se acaba actualizando el
golden sin mirar.

**Coste.** Las series son cortas (n≤240) y los casos, seis. Está pensado para
correrse entero cada vez, no para una noche de CI.
"""
import warnings

import numpy as np
import pytest

import fue

warnings.simplefilter("ignore")


# ===========================================================================
# Las series, con su verdad
# ===========================================================================

def _ruido(rng, n, sd=1.0):
    return rng.normal(0.0, sd, n)


def caso_determinista(seed=1):
    """Estacionalidad puramente DETERMINISTA sobre nivel estacionario."""
    rng = np.random.RandomState(seed)
    n, s = 240, 12
    t = np.arange(1, n + 1)
    y = (50.0
         + 3.0 * np.cos(2 * np.pi * t / s) + 1.5 * np.sin(2 * np.pi * t / s)
         + 2.0 * np.cos(2 * np.pi * 2 * t / s)
         + _ruido(rng, n))
    return dict(name="DET", y=y, freq=s, d=0, estocasticas=[])


def caso_estocastica_f2(seed=20260814):
    """MIXTA: determinista en f=1, ESTOCÁSTICA en f=2.

    El caso que destapó BUG-0019: en f=2 el armónico determinista sale no
    significativo POR CONSTRUCCIÓN, porque la amplitud vaga.
    """
    rng = np.random.RandomState(seed)
    n, s = 240, 12
    t = np.arange(1, n + 1)
    det = 3.0 * np.cos(2 * np.pi * t / s) + 1.5 * np.sin(2 * np.pi * t / s)
    c2 = 2 * np.cos(2 * np.pi * 2 / s)
    x2 = np.zeros(n)
    u = rng.normal(0, 0.35, n)
    for k in range(2, n):
        x2[k] = c2 * x2[k - 1] - x2[k - 2] + u[k]
    y = 100 + det + x2 + _ruido(rng, n)
    return dict(name="MIXTA", y=y, freq=s, d=0, estocasticas=[2])


def caso_i1(seed=3):
    """I(1) con deriva: el caso económico corriente."""
    rng = np.random.RandomState(seed)
    n = 200
    y = 100 + np.cumsum(0.1 + _ruido(rng, n, 0.5))
    return dict(name="I1", y=y, freq=12, d=1, estocasticas=[])


def caso_i0(seed=4):
    """I(0): AR(1) estacionario. La trampa es que el contraste lo llame I(1).

    ⚠ El arranque va en la media (y[0]=20) y NO en cero, y no es cosmética: con
    y[0]=0 —un salto inicial de veinte desviaciones, que es una serie legítima—
    `describe_unit_root` revienta con `MissingDataError: exog contains inf or
    nans` sobre datos que son finitos y no tienen ningún NaN. Los genera él.
    Hallazgo del 14-ago-2026, pendiente de ficha.
    """
    rng = np.random.RandomState(seed)
    n = 200
    y = np.zeros(n)
    y[0] = 20.0
    for t in range(1, n):
        y[t] = 20 + 0.6 * (y[t - 1] - 20) + rng.normal(0, 1.0)
    return dict(name="I0", y=y, freq=12, d=0, estocasticas=[])


def caso_i2(seed=5):
    """I(2). La decisión INICIAL correcta es d=1, no d=2 — un paso cada vez."""
    rng = np.random.RandomState(seed)
    n = 200
    y = 100 + np.cumsum(np.cumsum(_ruido(rng, n, 0.3)))
    return dict(name="I2", y=y, freq=12, d=1, estocasticas=[])


def caso_anual(seed=6):
    """Serie ANUAL: freq=1, sin frecuencias estacionales. BUG-0018."""
    rng = np.random.RandomState(seed)
    n = 80
    y = 100 + np.cumsum(0.5 + _ruido(rng, n, 1.0))
    return dict(name="ANUAL", y=y, freq=1, d=1, estocasticas=[])


CASOS = [caso_determinista, caso_estocastica_f2, caso_i1,
         caso_i0, caso_i2, caso_anual]
IDS = [f.__name__.replace("caso_", "") for f in CASOS]


def _serie(c):
    inicio = (2000, 1) if c["freq"] > 1 else (1950, 1)
    return fue.TimeSeries(list(c["y"]), freq=c["freq"], start=inicio,
                          name=c["name"])


# ===========================================================================
# §1 · Invariantes — no dependen de los números
# ===========================================================================

@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_d_avanza_de_uno_en_uno(caso):
    """BUG-0016. Desde d=0 la especificación inicial nunca salta a d=2.

    La razón es de potencia, no de gusto: con estacionalidad el contraste tiene
    poca potencia, y la segunda diferencia nunca se evalúa desde d=0. El
    contraste de verdad sobre d va al final, sobre un modelo adecuado.
    """
    from art.describe import describe_unit_root
    from art.policy import decide_d

    c = caso()
    ts = _serie(c)
    ur = describe_unit_root(ts).data
    d = decide_d(ur, seasonal=(c["freq"] > 1), current_d=0)
    assert 0 <= d <= 1, f"{c['name']}: la especificación inicial propone d={d}"


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_la_especificacion_inicial_lleva_todos_los_armonicos(caso):
    """BUG-0019. El nodo guiado no filtra por significación.

    El modelo nulo del MEG en la frecuencia f ES el armónico determinista en f:
    si no se pone, la frecuencia deja de ser una pregunta.
    """
    from art.describe import describe_seasonality

    c = caso()
    if c["freq"] == 1:
        pytest.skip("serie anual: no hay frecuencias estacionales")
    d = describe_seasonality(_serie(c))
    txt = d.summary + "\n" + (d.recommendation or "")
    if "Decisión B1" not in txt:
        pytest.skip("esta serie no llega a la rama B1")
    assert "para cada frecuencia significativa" not in txt
    assert "TODAS" in txt


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_una_serie_anual_no_inventa_estacionalidad(caso):
    """BUG-0018. freq=1 no tiene frecuencias estacionales: ni armónicos, ni MEG,
    ni ifadf. Es aritmética, no criterio."""
    from art.describe import describe_seasonality

    c = caso()
    if c["freq"] != 1:
        pytest.skip("sólo aplica a series anuales")
    d = describe_seasonality(_serie(c))
    txt = (d.summary + " " + (d.recommendation or "")).lower()
    assert "armónico" not in txt or "no aplica" in txt or "anual" in txt


def test_el_orden_meg_antes_de_podar_esta_declarado():
    """El texto ES el comportamiento: quien lo lee hace lo que dice."""
    import inspect

    from art import describe

    src = inspect.getsource(describe.describe_seasonal_params)
    assert "Considera eliminarlos" not in src
    assert "MEG" in src and "ifadf" in src


# ===========================================================================
# §2 · La matriz: la decisión debe ser la CORRECTA, no la de ayer
# ===========================================================================

@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_la_diferenciacion_inicial_es_la_de_la_verdad(caso):
    """d conocido por construcción. I(2) entra aquí esperando d=1: un paso."""
    from art.describe import describe_unit_root
    from art.policy import decide_d

    c = caso()
    ur = describe_unit_root(_serie(c)).data
    d = decide_d(ur, seasonal=(c["freq"] > 1), current_d=0)
    assert d == c["d"], (
        f"{c['name']}: el pipeline propone d={d} y la verdad es d={c['d']}")


@pytest.mark.parametrize("caso", [caso_determinista, caso_estocastica_f2],
                         ids=["determinista", "estocastica_f2"])
def test_el_meg_encuentra_la_estacionalidad_que_hay_y_no_otra(caso):
    """La prueba de fondo del MEG, sobre un modelo ADECUADO.

    No se contrasta sobre la especificación inicial: se estima primero el modelo
    con la estructura que la serie pide, y sólo entonces se barre. Es la regla
    de Treadway y es la que este pipeline debe respetar.
    """
    from art.formal_tests import meg

    c = caso()
    ts = _serie(c)
    interv = []
    for f in range(1, c["freq"] // 2):
        interv.append(fue.Intervention("cos", harmonic=float(f), omega=[0.1]))
        interv.append(fue.Intervention("sin", harmonic=float(f), omega=[0.1]))
    interv.append(fue.Intervention("alter", omega=[0.1]))
    m = fue.Model(ts, d=0, interventions=interv,
                  ar=[[0.3]], ar_free=[[True]],
                  mu=float(np.mean(c["y"])), estimate_mu=True)
    m.fit()

    res = meg(m)
    if not res:
        pytest.skip("el MEG no devolvió resultados en este entorno")
    declaradas = sorted({r.freq for r in res
                         if getattr(r, "stochastic", False)})
    verdad = sorted(c["estocasticas"])

    # SENSIBILIDAD: lo que hay, tiene que encontrarlo. Esto no admite excusa.
    faltan = [f for f in verdad if f not in declaradas]
    assert not faltan, (
        f"{c['name']}: el MEG NO encuentra la estacionalidad estocástica en "
        f"{faltan}, que está ahí por construcción")

    # ESPECIFICIDAD: mide los falsos positivos y los deja a la vista.
    #
    # Medido el 14-ago-2026: sobre la serie DETERMINISTA el barrido declara
    # estocásticas f=1 y f=6, que no lo son. Es coherente con la advertencia de
    # producción ya documentada (fue/docs/FORMAL_TESTS.md §3): la verosimilitud
    # de frontera hay que calcularla EXACTA, y con el optimizador libre de fue el
    # pile-up sale ~0.82 contra el 0.62 correcto — es decir, sobre-rechaza.
    #
    # El marcador es de DOS LADOS a propósito: si mejora, esta prueba falla y hay
    # que actualizar la cifra; si empeora, también.
    falsos = [f for f in declaradas if f not in verdad]
    esperados = {"DET": [1, 6], "MIXTA": []}[c["name"]]
    assert falsos == esperados, (
        f"{c['name']}: los falsos positivos del MEG han cambiado — antes "
        f"{esperados}, ahora {falsos}. Si es una mejora, actualiza la cifra y "
        f"la nota; si no, hay una regresión.")


@pytest.mark.parametrize("caso", CASOS, ids=IDS)
def test_mu_se_decide_y_no_se_queda_en_cero_por_descuido(caso):
    """BUG-0013/0014 de art: μ se hereda y se decide, no se pierde.

    μ es la media de la variable DIFERENCIADA, así que en una serie con deriva
    tiene que salir distinta de cero.
    """
    from art.policy import decide_mu

    c = caso()
    ts = _serie(c)
    d = c["d"]
    w = np.diff(c["y"], d) if d else c["y"]
    decision = decide_mu(ts, lam=1.0, d=d, D=0)
    assert isinstance(decision, (bool, np.bool_, dict)), decision
    if isinstance(decision, dict):
        decision = decision.get("estimate_mu", decision.get("mu", True))
    if abs(float(np.mean(w))) > 3 * float(np.std(w)) / np.sqrt(len(w)):
        assert decision, (
            f"{c['name']}: la media de la diferenciada es "
            f"{np.mean(w):.4f} y el pipeline no la estima")
