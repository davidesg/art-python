"""art.calibracion — cuánto de lo que ves en el correlograma es el anómalo.

La pregunta
-----------
Antes de elegir órdenes hay que saber si la estructura que se ve en el
correlograma es del proceso o del atípico. Y hay que saberlo **en las dos
funciones**, porque cada una decide una cosa:

    la PACF decide el orden **AR**
    la ACF  decide el orden **MA**

Calibrar sólo la ACF —que es lo que hacía el escaneo— deja media identificación
a ciegas, y no porque la ACF prediga a la PACF: **porque no la predice**. La
PACF es una transformación NO LINEAL de la ACF (Durbin-Levinson), así que las
dos pueden moverse en direcciones distintas y cambiar de veredicto en sentidos
OPUESTOS en el mismo retardo.

Medido sobre ∇ln PGAS (n=83, banda ±0,2151), omitiendo |z|>2,5 —las obs. 19 y
20—, retardo 2:

    ACF(2)   +0,1321 → +0,3143   SALE de banda   (el anómalo la ENMASCARABA)
    PACF(2)  −0,2964 → −0,1967   ENTRA en banda  (el anómalo la FABRICABA)

El mismo anómalo escondía una señal MA y fabricaba una señal AR **a la vez**.
Quien calibrase sólo la ACF concluiría «hay más MA de la que creía» y no se
enteraría de que el AR(2) que estaba a punto de estimar era el anómalo.

Y sirve en los dos sentidos, que es lo que evita **sobre-intervenir**: si al
quitar el anómalo ningún retardo cambia de veredicto dentro/fuera de banda,
intervenirlo no compra nada para la identificación, y añadir una intervención
que no hace falta es gastar un parámetro y tocar la serie sin motivo.

Cómo se calcula «sin el anómalo» — el estimador, y por qué ÉSTE
---------------------------------------------------------------
Con `I` el conjunto de índices señalados:

    μ̂ se calcula sobre las observaciones RETENIDAS
    z̃ₜ = (xₜ − μ̂)  si t ∉ I,   0  si t ∈ I
    r(k) = Σₜ z̃ₜ z̃ₜ₊ₖ / Σₜ z̃ₜ²
    φ(k)  por Durbin-Levinson sobre ese r(k)

La PACF sale de la ACF, así que **una sola omisión da las dos funciones**, que
es la propiedad que hace esto barato.

**Por qué la desviación a cero y no la eliminación por pares.** Ésta es la
decisión que gobierna el módulo y costó un defecto grave verla (BUG-0142). La
versión anterior normalizaba cada retardo por SUS pares retenidos:

    r(k) = ⟨(xᵢ−μ̂)(xᵢ₊ₖ−μ̂)⟩  sobre los pares donde ninguno está en I

Es insesgado retardo a retardo, y tiene un defecto que lo invalida: **cada r(k)
se estima sobre un subconjunto distinto**, así que la secuencia r(k) que sale
no es una función de autocovarianza. La matriz de Toeplitz que forma no tiene
por qué ser definida positiva, y Durbin-Levinson sobre una ACF inadmisible
diverge. Sobre `RATIO_m10` con umbral 2σ la PACF calibrada llegaba a **+3,394**
en el retardo 14, con la varianza de innovación ya negativa. Un coeficiente de
autocorrelación parcial vive en [−1, 1]: fuera de ahí no hay nada que leer, y
la PACF es la que decide el orden AR.

El relleno con ceros no tiene ese problema **por construcción**: r(k) vuelve a
ser la autocorrelación de una sucesión real z̃, cuya transformada es |Z(ω)|² ≥ 0.
La secuencia es definida positiva, luego |φ(k)| ≤ 1 siempre. Medido sobre 400
series de estrés con estacionalidad fuerte y de uno a cinco anómalos: máx|φ|
global **0,9062**, y ni un solo NaN.

**Y la objeción de circularidad, que hay que mirar de frente.** Este estimador
es aritméticamente IDÉNTICO a sustituir los anómalos por la media —verificado a
precisión de máquina, 3,3e-16—, y contra eso argumentaba la versión anterior:
poner el residuo a la media equivale a un impulso con ω libre, que es la
condición de primer orden de MCO, y suponer una forma en la herramienta que
existe para informar la elección de forma sería circular.

La objeción no sobrevive al requisito de admisibilidad. Cualquier estimador que
(a) quite la contribución de una observación a **todos** los retardos y (b) siga
siendo definido positivo tiene que poner su desviación a cero: c(k)=Σz̃ₜz̃ₜ₊ₖ es
la única forma que garantiza PSD, y «no contribuye» significa z̃=0 ahí. La
disyuntiva real no era «omitir contra sustituir» sino **«omitir de forma
admisible» contra «omitir de forma inadmisible»**, y la equivalencia con la
media no es un supuesto de forma que se cuela: es una coincidencia numérica con
la condición de primer orden. La medición de la versión anterior ya lo decía sin
que se leyera así — sustituir por la media daba error medio 0,0162 contra 0,0212
de la eliminación por pares, contra el modelo realmente calibrado.

Un solo correlograma en todo el paquete
---------------------------------------
**Sin omisión este estimador coincide EXACTAMENTE con `fue.acf` y `fue.pacf`**
—medido: 0,0 de diferencia en los dos—, porque es el mismo estimador de Bartlett
con el mismo denominador Σz². Eso cierra una incoherencia que llevaba tiempo
publicada: la eliminación por pares daba r(1)=+0,5819 sobre ∇ln PGAS donde la
diagnosis daba +0,5749, y la tabla de BUG-0048 llegó a listar `ACF(1)=+0,5749` y
`PACF(1)=+0,5819` **en la misma tabla**, cuando PACF(1) ≡ ACF(1) por definición.
Eran los dos estimadores, uno al lado del otro, sin que nadie lo notara.

Lo que el relleno con ceros sí cuesta
-------------------------------------
Encoge |r(k)| en aproximadamente la fracción omitida, n_I/n: el numerador pierde
los pares del anómalo y el denominador sigue contando su hueco. Con 3 anómalos
de 83 son unas 3,6 centésimas de proporción, y en la práctica mueve r(1) de
+0,6700 a +0,6534 sobre ∇ln PGAS.

**Y el sesgo va en la dirección conservadora**, que es la que importa aquí:
encoge hacia cero, así que este estimador puede dejar de detectar estructura,
pero **no puede fabricarla**. Para una herramienta cuyo trabajo es decir si un
orden AR es real o es el anómalo, equivocarse hacia «no hay estructura» es el
único error que no hace daño.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

__all__ = ["Distorsion", "CalibracionCorrelograma", "calibra_correlograma",
           "describe_calibracion"]


def _durbin_levinson(r: np.ndarray) -> np.ndarray:
    """PACF a partir de una ACF dada. `r[0]` es el retardo 1.

    Se necesita propia —y no `fue.pacf`, que toma datos— porque la ACF que se
    le pasa está calculada OMITIENDO observaciones y no proviene de una serie.

    LLEVA LA VARIANZA DE INNOVACIÓN, y por eso no puede publicar un imposible
    (BUG-0142). La recursión sólo se guardaba de dividir por cero:

        p = num / den   si   |den| > 1e-12

    y con `den = 0,019` —un denominador pequeño pero muy por encima del
    guardián— devolvía φ = **+3,394**. Un coeficiente de autocorrelación parcial
    vive en [−1, 1]; fuera de ahí no es una PACF, es basura con signo.

    La condición correcta no es sobre el denominador sino sobre v_k, la varianza
    del error de predicción a k pasos:

        v_k = v_{k−1}·(1 − φ_k²)

    que decrece monótonamente y es POSITIVA para toda ACF admisible. En cuanto
    v_k ≤ 0 —o |φ_k| > 1, que es lo mismo— la secuencia r(k) que ha entrado no
    es una función de autocovarianza y lo que salga de ahí en adelante no
    significa nada. Se devuelve NaN, que es lo que el dibujo y la tabla saben
    tratar como «indefinido».

    Con el estimador de relleno con ceros esto NO DEBERÍA SALTAR NUNCA: es la
    red, no el arreglo. El arreglo es `_acf_pacf`, que ahora entrega una r(k)
    admisible por construcción.
    """
    K = len(r)
    phi, prev = [], []
    v = 1.0
    for k in range(1, K + 1):
        if k == 1:
            p = float(r[0])
            prev = [p]
        else:
            num = r[k - 1] - sum(prev[j] * r[k - 2 - j] for j in range(k - 1))
            den = 1.0 - sum(prev[j] * r[j] for j in range(k - 1))
            p = float(num / den) if abs(den) > 1e-12 else float("nan")
            prev = [prev[j] - p * prev[k - 2 - j] for j in range(k - 1)] + [p]
        if not np.isfinite(p) or abs(p) > 1.0:
            phi.extend([float("nan")] * (K - k + 1))
            return np.array(phi)
        v *= (1.0 - p * p)
        if v <= 0.0:
            phi.extend([float("nan")] * (K - k + 1))
            return np.array(phi)
        phi.append(p)
    return np.array(phi)


def _acf_pacf(x: np.ndarray, K: int,
              omitir: set[int] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """ACF y PACF de `x` hasta K, OMITIENDO los índices de `omitir`.

    ESTIMADOR DE RELLENO CON CEROS — BUG-0142. μ̂ se calcula sobre lo retenido,
    la desviación de las omitidas se pone a CERO, y a partir de ahí es el
    estimador de Bartlett, el mismo de `fue.acf`:

        z̃ₜ = (xₜ − μ̂)  si t retenida,   0  si omitida
        r(k) = Σₜ z̃ₜ z̃ₜ₊ₖ / Σₜ z̃ₜ²

    El anómalo sigue sin contribuir a ningún retardo —que es lo que `omitir`
    significa— y r(k) vuelve a ser la autocorrelación de una sucesión REAL: su
    transformada es |Z(ω)|² ≥ 0, luego la secuencia es definida positiva, luego
    |φ(k)| ≤ 1 **siempre**.

    Lo que había antes normalizaba cada retardo por SUS pares retenidos, que es
    un divisor distinto en cada k, y eso destruye la definición positiva. Sobre
    `RATIO_m10` con umbral 2σ la PACF calibrada llegaba a **+3,394**.

    Y sin omisión esto coincide **exactamente** con `fue.acf` —medido: 0,0 de
    diferencia—, así que el paquete deja de tener dos correlogramas observados.
    """
    om = omitir or set()
    n = len(x)
    keep = np.array([i for i in range(n) if i not in om])
    if len(keep) < 2:
        raise ValueError("no quedan observaciones suficientes tras omitir.")
    mu = float(x[keep].mean())
    z = np.asarray(x, dtype=float) - mu
    if om:
        z = z.copy()
        z[np.array(sorted(om), dtype=int)] = 0.0
    c0 = float(z @ z)
    if c0 < 1e-20:
        raise ValueError("varianza nula sobre las observaciones retenidas.")
    r = np.array([float(z[k:] @ z[:n - k]) / c0 for k in range(1, K + 1)])
    return r, _durbin_levinson(r)


# Cuota mínima del par mayor sobre r(k) para que listar los pares diga algo
# — BUG-0144. No es un número de gusto: separa dos regímenes medidos.
#
#   residuos de RATIO_m10, donde un anómalo domina   el par mayor: 46 – 116%
#   ∇ln RATIO, estacionalidad repartida por la muestra           :  5 –  10%
#
# Y tiene lectura, que es lo que la hace útil: si unos pocos pares se llevan el
# retardo, ese retardo es un ARTEFACTO DE UNAS FECHAS; si el mayor se lleva un
# 5%, el retardo es estructura repartida por toda la muestra y nombrarle dos
# fechas engaña. Por eso la tabla no se dibuja siempre.
CUOTA_PAR_DOMINANTE = 0.25


def _pares_dominantes(x: np.ndarray, K: int,
                      top: int = 4) -> "list[list[tuple[int, int, float]]]":
    """Los PARES de fechas que más pesan en cada r(k) — BUG-0144.

    El estimador de Bartlett es una suma sobre PARES, y por eso admite una
    descomposición exacta que la atribución por observación no tiene:

        r(k) = Σₜ (xₜ−μ̂)(xₜ₊ₖ−μ̂) / (n·σ̂²)

    Cada sumando es el par (t, t+k) y **suman r(k) sin residuo**: no hay canal
    de varianza que separar ni pares de anómalos que sobren. Es la calibración
    que `fue` imprime en cada `.out` bajo «Calibration of distortions of the
    ACF» —puerto de `PlotCalibACF` de `diagnose.c`—, y es la más específica de
    las dos que tiene la suite: dice **qué dos fechas** hacen un retardo, no
    cuánto pone cada anómalo.

    Las dos hacen falta y contestan cosas distintas:

        r_obs(k) − r_cal(k)   ¿cuánto se movería si intervengo?   ← decide
        pares dominantes      ¿qué fechas hacen este retardo?     ← explica

    y la segunda no necesita que nadie declare nada anómalo primero.

    Devuelve, por retardo, los `top` pares con mayor |contribución|, como
    `(i, j, c)` con i, j 0-based sobre `x`.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    mu = float(x.mean())
    var = float(x.var())
    z = x - mu
    if var < 1e-20 or n < 2:
        return [[] for _ in range(K)]
    den = n * var
    # EL CRITERIO ES EL DE `fue`, no «los mayores en valor absoluto». Se listan
    # los pares que HACEN el retardo: los más positivos si r(k)>0, los más
    # negativos si r(k)<0. Un par que compensa no explica el retardo, lo
    # disimula, y mezclarlos deja una lista que no suma hacia el número que
    # encabeza. `THRESH` es la deduplicación de `PlotCalibACF`: dos pares con
    # la misma contribución a cuatro cifras se cuentan una vez.
    THRESH = 0.9999
    fuera = []
    for k in range(1, K + 1):
        c = z[: n - k] * z[k:] / den
        if len(c) == 0:
            fuera.append([])
            continue
        r_k = float(c.sum())
        if r_k > 0:
            orden = np.argsort(-c)
            avanza = lambda v, prev: prev is None or v < prev * THRESH
        elif r_k < 0:
            orden = np.argsort(c)
            avanza = lambda v, prev: prev is None or v > prev * THRESH
        else:                                             # pragma: no cover
            fuera.append([])
            continue
        sel, prev = [], None
        for i in orden:
            v = float(c[i])
            if avanza(v, prev):
                sel.append((int(i), int(i) + k, v))
                prev = v
                if len(sel) >= max(0, int(top)):
                    break
        fuera.append(sel)
    return fuera


@dataclass
class Distorsion:
    """Lo que le pasa a un retardo cuando se quita el anómalo."""

    lag: int
    acf_obs: float
    acf_cal: float
    pacf_obs: float
    pacf_cal: float
    banda: float
    # Los pares de fechas que hacen este retardo (BUG-0144). Van con `default`
    # porque son opcionales; y AL FINAL, que es donde tienen que ir los campos
    # con valor por omisión en un dataclass.
    pares: tuple = ()

    @staticmethod
    def _flip(obs: float, cal: float, banda: float) -> str | None:
        fo, fc = abs(obs) > banda, abs(cal) > banda
        if fo == fc:
            return None
        return "entra" if fo and not fc else "sale"

    @property
    def acf_flip(self) -> str | None:
        """'sale' si el retardo estaba dentro y al calibrar sale; 'entra' al revés."""
        return self._flip(self.acf_obs, self.acf_cal, self.banda)

    @property
    def pacf_flip(self) -> str | None:
        return self._flip(self.pacf_obs, self.pacf_cal, self.banda)

    @property
    def d_acf(self) -> float:
        return abs(self.acf_cal - self.acf_obs)

    @property
    def d_pacf(self) -> float:
        return abs(self.pacf_cal - self.pacf_obs)

    @property
    def amplificacion(self) -> float:
        """Cociente d_pacf/d_acf en este retardo.

        Se reporta como columna, NO como titular: donde la ACF apenas se mueve
        el cociente se dispara sin significar nada (sobre PGAS daba ×5,23 en un
        retardo con 0,019 de distorsión en la ACF). El argumento para calibrar
        la PACF no es la amplificación, es que las dos pueden cambiar de
        veredicto en direcciones OPUESTAS.
        """
        return self.d_pacf / self.d_acf if self.d_acf > 1e-12 else float("nan")


@dataclass
class CalibracionCorrelograma:
    distorsiones: list[Distorsion]
    extremos: list[tuple[int, float]]      # (obs 1-based, z)
    n: int
    banda: float
    umbral: float
    sigma_obs: float
    sigma_cal: float
    # False si la ACF omitida no es definida positiva y la PACF derivada no es
    # una PACF. Coste conocido de omitir: cada retardo usa pares distintos.
    por_omision: bool = False
    pacf_valida: bool = True
    # EL CALENDARIO — BUG-0140/0144. Los pares dominantes sólo dicen algo si se
    # pueden nombrar por su fecha, y `residuals` llega como lista pelada. Los
    # tres viajan juntos porque por separado no significan nada; `desfase` es
    # `d + D·s`, lo que se comió la diferenciación (BUG-0067).
    freq: int = 0
    start: tuple = ()
    desfase: int = 0

    def fecha(self, i0: int) -> str:
        """La fecha de la observación 0-based `i0` de los residuos, o su índice
        si esta calibración no trae calendario."""
        if not self.freq or len(self.start) < 2:
            return f"obs {i0 + 1}"
        try:
            from art.guion import _at_to_date
            return _at_to_date(int(i0) + int(self.desfase),
                               int(self.start[0]), int(self.start[1]),
                               int(self.freq))
        except Exception:                                 # pragma: no cover
            return f"obs {i0 + 1}"

    @property
    def flips_ar(self) -> list[Distorsion]:
        """Retardos donde la PACF cambia de veredicto ⇒ cambia el orden **AR**."""
        return [d for d in self.distorsiones if d.pacf_flip]

    @property
    def flips_ma(self) -> list[Distorsion]:
        """Retardos donde la ACF cambia de veredicto ⇒ cambia el orden **MA**."""
        return [d for d in self.distorsiones if d.acf_flip]

    @property
    def cambia_la_identificacion(self) -> bool:
        return bool(self.flips_ar or self.flips_ma)

    @property
    def flips_opuestos(self) -> list["Distorsion"]:
        """Retardos donde la ACF y la PACF cambian de veredicto en sentidos
        CONTRARIOS. Es la prueba de que una no sustituye a la otra."""
        return [d for d in self.distorsiones
                if d.acf_flip and d.pacf_flip and d.acf_flip != d.pacf_flip]

    @property
    def veredicto(self) -> str:
        if not self.extremos:
            return "sin extremos"
        if not self.pacf_valida:
            return "PACF calibrada no válida"
        if not self.cambia_la_identificacion:
            return "no cambia la identificación"
        return "cambia la identificación"


def calibra_correlograma(residuals: Sequence[float],
                         umbral: float = 2.5,
                         max_lag: int = 12,
                         omitir: "set[int] | None" = None,
                         top_pares: int = 4,
                         freq: int = 0,
                         start: Sequence[int] = (),
                         desfase: int = 0) -> CalibracionCorrelograma:
    """Cuánto de la ACF y de la PACF se debe a los residuos extremos.

    Parameters
    ----------
    residuals : los residuos de un modelo estimado.
    umbral    : |z| a partir del cual un residuo se considera extremo.
    max_lag   : hasta qué retardo calibrar.

    top_pares : cuántos pares de fechas listar por retardo (BUG-0144).
    freq, start, desfase : EL CALENDARIO, para poder nombrar esos pares por su
                fecha. Viajan juntos; sin ellos se nombran por su índice.

    Los extremos se omiten poniendo su desviación a CERO y se recalcula TODO
    —media, σ, ACF y PACF— con el estimador de Bartlett, el mismo de `fue.acf`.
    Ver la cabecera del módulo: el porqué de ese estimador y no otro es la
    decisión que gobierna este archivo (BUG-0142).
    """
    r = np.asarray(residuals, dtype=float)
    n = len(r)
    if n < 8:
        raise ValueError(f"n={n}: hacen falta al menos 8 residuos para calibrar.")
    K = int(min(max_lag, max(1, n // 4)))

    mu, sd = float(r.mean()), float(r.std(ddof=0))
    if sd < 1e-20:
        raise ValueError("desviación típica nula: no hay correlograma que calibrar.")
    z = (r - mu) / sd
    # BUG-0133. Tres criterios de qué omitir, no uno: por UMBRAL (el de
    # siempre), por OBSERVACIÓN o por INCIDENTE. Con `omitir` explícito el
    # umbral no interviene — se quita lo que se pide, lo marque o no, que es lo
    # que el nodo de intervención necesita cuando ya tiene el episodio
    # delimitado y quiere ver el correlograma sin él.
    #
    # Y hace falta que ESTA tabla y la figura del escaneo usen el mismo: antes
    # la figura omitía el incidente y la tabla seguía con el umbral, así que el
    # veredicto «cambia / no cambia la identificación» contestaba a la pregunta
    # que no era.
    if omitir is not None:
        idx = sorted({int(i) for i in omitir if 0 <= int(i) < n})
    else:
        idx = [i for i in range(n) if abs(z[i]) > umbral]
    extremos = [(i + 1, float(z[i])) for i in idx]

    a_obs, p_obs = _acf_pacf(r, K)
    if idx:
        # Relleno con ceros sobre las desviaciones (BUG-0142): quita la
        # contribución del anómalo a TODOS los retardos y deja una ACF
        # admisible, que es la única forma de que la PACF derivada sea una PACF.
        a_cal, p_cal = _acf_pacf(r, K, omitir=set(idx))
        keep = np.array([i for i in range(n) if i not in set(idx)])
        sigma_cal = float(r[keep].std(ddof=0))
    else:
        a_cal, p_cal, sigma_cal = a_obs.copy(), p_obs.copy(), sd

    # La red de BUG-0142. Con el estimador de relleno con ceros la ACF calibrada
    # es definida positiva POR CONSTRUCCIÓN y esto no debería ser nunca False;
    # se comprueba igual, porque publicar una |φ| ≥ 1 sería publicar algo que no
    # es una PACF.
    pd_ok = bool(np.all(np.isfinite(p_cal)) and np.max(np.abs(p_cal)) < 1.0)

    banda = 2.0 / np.sqrt(n)
    pares = _pares_dominantes(r, K, top=top_pares) if top_pares else \
        [[] for _ in range(K)]
    dis = [Distorsion(lag=k + 1, banda=banda,
                      acf_obs=float(a_obs[k]), acf_cal=float(a_cal[k]),
                      pacf_obs=float(p_obs[k]), pacf_cal=float(p_cal[k]),
                      pares=tuple(pares[k]))
           for k in range(K)]

    return CalibracionCorrelograma(
        distorsiones=dis, extremos=extremos, n=n, banda=banda, umbral=umbral,
        sigma_obs=sd, sigma_cal=sigma_cal, por_omision=(omitir is not None),
        freq=int(freq or 0), start=tuple(start), desfase=int(desfase))


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def describe_calibracion(cal: "CalibracionCorrelograma", nombre: str = "",
                         con_figura: bool = True):
    """El correlograma observado contra el calibrado, en las DOS funciones.

    La PACF va **arriba** porque es la que decide el orden AR y es la que el
    escaneo anterior no calibraba. Cada retardo lleva dos barras —observada y
    calibrada— y los retardos que cambian de veredicto van sombreados: son los
    únicos que cambian la decisión de órdenes, y por tanto los únicos que
    justifican intervenir ANTES de identificar.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from art.describe import Description, _fig_b64

    OBS, CAL, FLIP = "#94a3b8", "#1d4ed8", "#f59e0b"
    lags = np.array([d.lag for d in cal.distorsiones])
    b = cal.banda

    if not con_figura:
        # SIN FIGURA — BUG-0133. Desde que el escaneo de tres paneles es el
        # gráfico de calibración de distorsiones, esta figura duplica: enseña
        # observada contra calibrada, que es lo que aquélla enseña como
        # contribución, y le falta el panel de la serie. Lo que se conserva —y
        # es donde esta función sigue siendo la mejor— es su TABLA, con el
        # veredicto por retardo.
        #
        # `residual_outlier_scan` la pedía entera y descartaba la imagen: se
        # pagaba el render de matplotlib para tirarlo.
        b64 = None
    else:
        fig, axs = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
        for ax, (obs, cl, titulo, decide) in zip(axs, [
                ([d.pacf_obs for d in cal.distorsiones],
                 [d.pacf_cal for d in cal.distorsiones],
                 "PACF", "decide el orden AR"),
                ([d.acf_obs for d in cal.distorsiones],
                 [d.acf_cal for d in cal.distorsiones],
                 "ACF", "decide el orden MA")]):
            flips = [d.lag for d in cal.distorsiones
                     if (d.pacf_flip if titulo == "PACF" else d.acf_flip)]
            for L in flips:
                ax.axvspan(L - .5, L + .5, color=FLIP, alpha=.22, lw=0, zorder=0)
            ax.bar(lags - .19, obs, width=.36, color=OBS, label="observada", zorder=2)
            ax.bar(lags + .19, cl, width=.36, color=CAL,
                   label="calibrada (sin el anómalo)", zorder=2)
            for u in (-b, b):
                ax.axhline(u, color="#b91c1c", ls="--", lw=1.0, zorder=1)
            ax.axhline(0, color="#111", lw=.8, zorder=1)
            ax.set_ylabel(titulo)
            ax.set_title(f"{titulo} — {decide}"
                         + (f"   ·   cambia de veredicto en el retardo "
                            f"{', '.join(map(str, flips))}" if flips else
                            "   ·   ningún retardo cambia de veredicto"),
                         fontsize=9, loc="left")
            ax.grid(alpha=.2, axis="y")
            ax.set_xticks(lags)
        axs[0].legend(fontsize=8, loc="best")
        axs[1].set_xlabel("retardo")
        cab = f"Calibración del correlograma{' — ' + nombre if nombre else ''}"
        fig.suptitle(f"{cab}   (|z| > {cal.umbral:g}, n={cal.n}, banda ±{b:.3f})",
                     fontsize=10)
        fig.tight_layout()
        b64 = _fig_b64(fig)
        plt.close(fig)

    # ── texto ────────────────────────────────────────────────────────────
    if not cal.extremos:
        return Description(
            summary=f"### Calibración del correlograma{' — ' + nombre if nombre else ''}\n\n"
                    f"**Sin residuos extremos** con |z| > {cal.umbral:g}. No hay nada "
                    "que calibrar: el correlograma que ves es el del proceso.",
            figure_b64=b64,
            recommendation="Identifica los órdenes sobre el correlograma tal cual.",
            data=dict(veredicto=cal.veredicto, extremos=[], distorsiones=[]))

    ext = ", ".join(f"obs {o} (z={z:+.2f})" for o, z in cal.extremos)
    L = [f"### Calibración del correlograma{' — ' + nombre if nombre else ''}",
         "",
         (f"**{len(cal.extremos)} residuo(s) omitido(s)** por el criterio dado: {ext}"
          if cal.por_omision else
          f"**{len(cal.extremos)} residuo(s) extremo(s)** con |z| > {cal.umbral:g}: {ext}"),
         f"σ̂ pasa de **{cal.sigma_obs:.4f}** a **{cal.sigma_cal:.4f}** al quitarlos.",
         "",
         "| lag | ACF obs | ACF cal | | PACF obs | PACF cal | | ampl. |",
         "|---|---|---|---|---|---|---|---|"]
    for d in cal.distorsiones:
        fa = f"**{d.acf_flip.upper()}**" if d.acf_flip else ""
        fp = f"**{d.pacf_flip.upper()}**" if d.pacf_flip else ""
        amp = f"×{d.amplificacion:.2f}" if (np.isfinite(d.amplificacion)
                                            and d.d_acf > 0.01) else "—"
        L.append(f"| {d.lag} | {d.acf_obs:+.4f} | {d.acf_cal:+.4f} | {fa} "
                 f"| {d.pacf_obs:+.4f} | {d.pacf_cal:+.4f} | {fp} | {amp} |")
    L += ["", f"*Banda ±{cal.banda:.3f}. «SALE» = estaba dentro y al calibrar "
          "sale (el anómalo la **enmascaraba**); «ENTRA» = estaba fuera y al "
          "calibrar entra (el anómalo la **fabricaba**).*", ""]

    # QUÉ FECHAS HACEN EL RETARDO — BUG-0144.
    #
    # La tabla de arriba contesta «¿cuánto se movería si intervengo?». Ésta
    # contesta la otra mitad, que es más específica: **qué dos fechas** hacen
    # ese retardo. Son objetos distintos y hacen falta los dos —la primera
    # decide, la segunda explica— y esta segunda no necesita que nadie declare
    # nada anómalo primero, porque el estimador de Bartlett es una suma sobre
    # pares y admite la descomposición exacta.
    #
    # Reproduce el bloque «Calibration of distortions of the ACF» del `.out`,
    # con su mismo criterio de selección: los pares que HACEN el retardo, no
    # los mayores en valor absoluto.
    _prio = [d for d in cal.distorsiones if d.acf_flip or d.pacf_flip]
    if not _prio:
        _prio = sorted((d for d in cal.distorsiones
                        if abs(d.acf_obs) > cal.banda),
                       key=lambda d: -abs(d.acf_obs))
    _prio = sorted(_prio[:4], key=lambda d: d.lag)
    # Sólo donde unos pocos pares SE LLEVAN el retardo. Ver `CUOTA_PAR_DOMINANTE`.
    _prio = [d for d in _prio if d.pares and abs(d.acf_obs) > 1e-9
             and abs(d.pares[0][2] / d.acf_obs) >= CUOTA_PAR_DOMINANTE]
    if _prio:
        L += ["#### Qué fechas hacen cada retardo", "",
              "| lag | r(k) | fechas | contribución |",
              "|---|---|---|---|"]
        for d in _prio:
            for m, (i, j, c) in enumerate(d.pares):
                cab = f"| **{d.lag}** | {d.acf_obs:+.3f} " if m == 0 else "| | "
                L.append(f"{cab}| {cal.fecha(i)} – {cal.fecha(j)} | {c:+.3f} |")
        L += ["", "*Descomposición EXACTA: los pares suman r(k) sin residuo. Es "
              "el bloque «Calibration of distortions of the ACF» del `.out`, y "
              "es el instrumento **específico**: dice qué dos fechas hacen el "
              "retardo, no cuánto pone cada anómalo.*",
              "", f"*Sólo aparecen los retardos donde el par mayor se lleva al "
              f"menos el {100*CUOTA_PAR_DOMINANTE:.0f}% de r(k) — ahí el retardo "
              "es un **artefacto de unas fechas**. Si ningún par destaca, el "
              "retardo es estructura repartida por la muestra y nombrarle dos "
              "fechas engañaría.*", ""]

    if not cal.cambia_la_identificacion:
        L += ["#### Veredicto — **no cambia la identificación**", "",
              "Ningún retardo cambia de dentro a fuera de banda ni al revés. El "
              "anómalo **no está decidiendo los órdenes**, así que intervenirlo "
              "antes de identificar no compra nada: sería gastar un parámetro y "
              "tocar la serie sin que la decisión de órdenes cambie.",
              "", "Eso no dice que no haya que intervenirlo *después* —por "
              "adecuación, por normalidad o porque el suceso importe en sí—, "
              "sino que **no es un requisito previo a elegir p y q**."]
    else:
        L += ["#### Veredicto — **cambia la identificación**", ""]
        if cal.flips_ar:
            for d in cal.flips_ar:
                que = ("una señal AR que el anómalo **fabricaba**"
                       if d.pacf_flip == "entra" else
                       "una señal AR que el anómalo **enmascaraba**")
                L.append(f"- **PACF({d.lag})**: {d.pacf_obs:+.4f} → "
                         f"{d.pacf_cal:+.4f} ({d.pacf_flip}) — {que}. "
                         f"Afecta al **orden AR**.")
        if cal.flips_ma:
            for d in cal.flips_ma:
                que = ("una señal MA que el anómalo **fabricaba**"
                       if d.acf_flip == "entra" else
                       "una señal MA que el anómalo **enmascaraba**")
                L.append(f"- **ACF({d.lag})**: {d.acf_obs:+.4f} → "
                         f"{d.acf_cal:+.4f} ({d.acf_flip}) — {que}. "
                         f"Afecta al **orden MA**.")
        if cal.flips_opuestos:
            ls = ", ".join(str(d.lag) for d in cal.flips_opuestos)
            L += ["", f"⚠ **En el retardo {ls} las dos cambian en sentidos "
                  "OPUESTOS.** El mismo anómalo enmascara una señal y fabrica "
                  "la otra. Es la razón de que haya que calibrar las dos: la "
                  "PACF es una transformación no lineal de la ACF, así que la "
                  "ACF **no predice** hacia dónde se mueve la PACF."]

    rec = ("**Interviene antes de identificar.** Los órdenes que elegirías "
           "sobre el correlograma observado no son los que corresponden al "
           "proceso — mira los retardos marcados."
           if cal.cambia_la_identificacion else
           "Identifica los órdenes sin intervenir todavía: el anómalo no los "
           "cambia. Intervenir aquí sería sobre-intervenir.")

    return Description(
        summary="\n".join(L), figure_b64=b64, recommendation=rec,
        data=dict(
            veredicto=cal.veredicto, n=cal.n, banda=cal.banda,
            umbral=cal.umbral, sigma_obs=cal.sigma_obs, sigma_cal=cal.sigma_cal,
            cambia_la_identificacion=cal.cambia_la_identificacion,
            flips_opuestos=[d.lag for d in cal.flips_opuestos],
            extremos=[dict(obs=o, z=z) for o, z in cal.extremos],
            flips_ar=[d.lag for d in cal.flips_ar],
            flips_ma=[d.lag for d in cal.flips_ma],
            distorsiones=[dict(lag=d.lag, acf_obs=d.acf_obs, acf_cal=d.acf_cal,
                               pacf_obs=d.pacf_obs, pacf_cal=d.pacf_cal,
                               acf_flip=d.acf_flip, pacf_flip=d.pacf_flip,
                               amplificacion=d.amplificacion)
                          for d in cal.distorsiones]))
