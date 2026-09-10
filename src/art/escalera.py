"""art.escalera — la escalera de Ockham del análisis de intervención.

**Lo más obvio primero.** El análisis de intervención sube por una escalera de
sofisticación, y sólo se sube un escalón cuando el de abajo no se sostiene.

    peldaño 1   UNA intervención escalar. Dos lecturas del MISMO coste —un
                parámetro cada una— y no anidadas entre sí:
                  1a  escalón en el nivel   → efecto PERMANENTE
                  1b  impulso en el nivel   → efecto TRANSITORIO, 1 período
    peldaño 2   EPISODIO: L+1 escalones en el nivel, la forma general de la
                familia anidada. Con ganancia ω(1)=0 son L impulsos de nivel.
    peldaño 3   FLT con denominador, cuando la respuesta decae.

Lo que este módulo PROHÍBE
--------------------------
**El AIC no arbitra la subida de escalón.** Compara *dentro* de un peldaño, o
confirma una subida ya justificada por otra cosa. Una escalera que se quedara
con el mejor AIC subiría siempre, porque el modelo más sofisticado casi siempre
ajusta mejor: tiene más parámetros. Eso es exactamente lo contrario de la
navaja.

Lo que justifica subir es, en este orden:

1. **Treadway** — la forma de abajo deja un vecino anómalo. Es evidencia
   objetiva y no cuesta preguntar nada: la parte no modelizada del suceso cae
   entera en el vecino (ver `interventions.check_intervention_fit`).
2. **Inadecuación** — la forma de abajo no deja ruido blanco.
3. **Dominio** — la lectura simple es implausible para esta clase de serie. Una
   caída PERMANENTE de nivel en un índice de precios es poco usual.
4. **Ausencia de explicación extramuestral** — no hay suceso conocido que
   justifique la forma simple.

Los dos primeros los ve la herramienta. El tercero lo sabe por `decide_domain`.
**El cuarto sólo lo sabe el analista**, y por eso este módulo lo pregunta en vez
de suponerlo: es el único nodo de `art` cuya evidencia no está en los datos.

Y la explicación tiene que explicar la FORMA, no sólo la fecha
---------------------------------------------------------------
Una bajada de impuestos explica un escalón **permanente**; una huelga, un
impulso **transitorio**. Si el analista aporta una explicación de suceso
permanente pero el contraste de ganancia dice transitorio, la explicación no
cubre lo que hay y se sube igual. Cuando el registro extramuestral y el
contraste discrepan, eso es información y hay que enseñarla.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

__all__ = ["Peldano", "Escalera", "escalera_de_ockham", "describe_escalera",
           "lectura_escalar"]


# Clases de serie en las que un cambio PERMANENTE de nivel es poco usual, y
# por tanto la lectura simple necesita respaldo antes de aceptarse. No es un
# veredicto: es la razón de dominio del punto 3 de arriba.
DOMINIOS_SIN_CAIDA_PERMANENTE = ("price_index",)

# Cuánto del pico puede quedar SIN cancelar y seguir leyéndose como un impulso
# de nivel. El diccionario de la FLT dice que en ∇ un impulso de nivel deja
# +ω, −ω, cuya suma es exactamente cero; lo que sobra de esa suma es lo que no
# revierte. Es una convención declarada, no un contraste: el contraste de
# ganancia nula se hace después, sobre los ω estimados.
TOL_CANCELA = 0.35


def lectura_escalar(episodio, d: int) -> tuple[str, str]:
    """Cuál de las dos lecturas escalares dice el DATO: «1a» o «1b».

    No lo decide el ajuste (BUG-0086). `1a` y `1b` no están anidadas y cuestan
    lo mismo, así que el AIC no puede compararlas: elegir por AIC es leer ruido.
    Lo decide la FIRMA que el suceso deja en los residuos, vía el diccionario
    de la FLT —el mismo que usa `art.ltf`—:

        en el NIVEL          en ∇                         suma en ∇
        escalón ω en T   →   UN impulso ω en T            ω
        impulso ω en T   →   DOS impulsos +ω, −ω          0

    De ahí sale la regla, y sale sin umbral nuevo: se lee sobre los EXTREMOS
    del episodio, que son los que la intervención tiene que explicar.

    * con `d ≥ 1` los residuos viven en ∇:
        - dos extremos contiguos de **signo opuesto y magnitud comparable** son
          la firma de un impulso de nivel → `1b`;
        - cualquier otra cosa —un extremo solo, o vecinos que no se cancelan—
          es la firma de un escalón → `1a`.
    * con `d = 0` los residuos viven en el nivel, y el diccionario se invierte:
        - un extremo solo es un impulso de nivel → `1b`;
        - una racha del mismo signo es un escalón → `1a`.

    Un vecino por DEBAJO del umbral de extremo no cuenta aquí, y es a propósito:
    ésa es la cola de un episodio más largo (BUG-0083), no la mitad
    compensadora de un impulso. Lo que hace con ella la escalera es subir al
    peldaño 2, no cambiar la lectura escalar.

    Returns
    -------
    (nivel, razón) — el nivel recomendado y la frase que lo justifica, para que
    el informe diga POR QUÉ y no sólo qué.
    """
    ext = sorted(episodio.extremos)          # [(obs_1based, z), ...]
    if not ext:
        return "1a", ("no hay extremos que leer; se toma el escalón, que es la "
                      "lectura por defecto de un suceso sin firma de reversión")

    if int(d) >= 1:
        if len(ext) == 2 and ext[1][0] == ext[0][0] + 1:
            z0, z1 = ext[0][1], ext[1][1]
            pico = max(abs(z0), abs(z1))
            resto = abs(z0 + z1)
            if z0 * z1 < 0 and pico and resto <= TOL_CANCELA * pico:
                return "1b", (
                    f"dos extremos contiguos que se CANCELAN ({z0:+.2f} y "
                    f"{z1:+.2f}, suma {z0 + z1:+.2f} = {resto / pico:.0%} del "
                    "pico): en ∇ ésa es la firma de un IMPULSO de nivel, que "
                    "revierte")
            if z0 * z1 < 0 and pico:
                return "1a", (
                    f"dos extremos contiguos de signo opuesto que NO se "
                    f"cancelan ({z0:+.2f} y {z1:+.2f}, suma {z0 + z1:+.2f} = "
                    f"{resto / pico:.0%} del pico, por encima del "
                    f"{TOL_CANCELA:.0%}): lo que no revierte es un ESCALÓN. El "
                    "segundo extremo es cola del suceso, no la mitad "
                    "compensadora de un impulso")
        if len(ext) == 1:
            return "1a", (
                f"un extremo aislado ({ext[0][1]:+.2f}) sin vecino que lo "
                "compense: en ∇ un impulso solo es la firma de un ESCALÓN de "
                "nivel, que no revierte")
        return "1a", (
            f"{len(ext)} extremos que no forman un par compensado: la lectura "
            "escalar es el escalón, y la forma de verdad está más arriba en la "
            "escalera")

    # d = 0 — los residuos ya están en el nivel
    if len(ext) == 1:
        return "1b", (f"un solo extremo en el NIVEL ({ext[0][1]:+.2f}), sin "
                      "diferenciar: eso es un impulso, no un escalón")
    signos = {1 if z > 0 else -1 for _, z in ext}
    if len(signos) == 1:
        return "1a", (f"{len(ext)} extremos del mismo signo en el NIVEL: una "
                      "racha sostenida es un escalón")
    return "1a", (f"{len(ext)} extremos de signos mezclados en el NIVEL; se "
                  "toma el escalón como lectura por defecto")


@dataclass
class Peldano:
    """Un escalón de la escalera, estimado."""

    nivel: str                       # "1a" | "1b" | "2"
    nombre: str
    tipo: str                        # tipo de intervención de fue
    n_omega: int
    model: Any = None
    aic: float = float("nan")
    loglik: float = float("nan")
    omega: list[float] = field(default_factory=list)
    omega_1: float | None = None     # ω(1), la ganancia sin denominador
    wald_p: float | None = None      # H₀: ω(1)=0
    q_pass: bool | None = None
    jb_pass: bool | None = None
    treadway: list = field(default_factory=list)
    error: str = ""

    @property
    def estimado(self) -> bool:
        return self.model is not None and not self.error

    @property
    def deja_vecino(self) -> bool:
        return any(c.vecino_anomalo for c in self.treadway)

    @property
    def absorbe(self) -> bool:
        return bool(self.treadway) and all(c.absorbido for c in self.treadway)

    @property
    def adecuado(self) -> bool:
        return bool(self.q_pass) and bool(self.jb_pass)

    @property
    def se_sostiene(self) -> bool:
        """El peldaño aguanta: absorbe, no deja vecino y deja ruido blanco."""
        return self.estimado and self.absorbe and not self.deja_vecino \
            and self.adecuado

    @property
    def transitorio(self) -> bool | None:
        """Lectura del contraste de ganancia; None si no aplica."""
        if self.wald_p is None:
            return None
        return self.wald_p >= 0.05          # no se rechaza ganancia nula


@dataclass
class Escalera:
    peldanos: list[Peldano]
    episodio: Any
    dominio: str
    razones_para_subir: list[str]
    recomendado: str | None
    pregunta_extramuestral: str
    # Cuál de las dos lecturas escalares dice el dato, y por qué. No es
    # adorno: es lo que impide que el lector suponga que decidió el AIC, que es
    # lo que decidía antes (BUG-0086).
    nivel_simple: str = ""
    criterio_simple: str = ""

    def por_nivel(self, nivel: str) -> Peldano | None:
        return next((p for p in self.peldanos if p.nivel == nivel), None)

    @property
    def subio(self) -> bool:
        """¿La recomendación ESTÁ en un peldaño alto?

        No es lo mismo que «había razones para subir». Cuando las hay pero el
        peldaño 2 tampoco se sostiene, la escalera recomienda el bajo — y decir
        entonces «se subió de peldaño» es afirmar algo que no pasó (BUG-0084 §4).
        """
        return self.recomendado == "2"

    @property
    def ningun_peldano_se_sostiene(self) -> bool:
        """Había razones para subir y arriba tampoco se sostiene.

        Es el estado que el mensaje contradictorio ocultaba, y es el que el
        analista necesita saber: no es que se haya elegido bien, es que ninguna
        de las formas de esta escalera resuelve el suceso.
        """
        return bool(self.razones_para_subir) and not self.subio


def _clona_con(model, itvs):
    """El modelo base con OTRO juego de intervenciones y las mismas semillas."""
    import fue
    kw = {}
    # `refactor` es parte de la lista y no un extra: `fue.Model` lo tiene a 1.0
    # por defecto y la suite estima sobre 100·log(y), así que un clon que no lo
    # copie sale en OTRA escala y su ℓ/AIC difieren en n·ln(100) — comparables
    # entre clones, incomparables con el modelo del que salieron (BUG-0085).
    for a in ("ar", "ma", "ar_s", "ma_s", "ar_free", "ma_free",
              "ar_s_free", "ma_s_free", "ar_f", "ma_f", "d", "D",
              "ifadf", "mu", "estimate_mu", "boxlam", "refactor"):
        v = getattr(model, a, None)
        if v is not None:
            kw[a] = v
    return fue.Model(model.series, interventions=itvs, **kw)


#: Tipos que son ESTRUCTURA estacional y no sucesos. Sobreviven siempre.
_ESTRUCTURA = ("cos", "sin", "alter")


def hereda_del_base(model, at_estudiado=None, ventana=0):
    """Las intervenciones del base que un candidato tiene que LLEVAR — BUG-0150.

    Aquí había un filtro que se quedaba sólo con `cos`, `sin` y `alter`, o sea
    que **tiraba todas las intervenciones de suceso ya estimadas**. El docstring
    prometía «el modelo ajustado SIN la intervención» —la que se estudia— y el
    código hacía algo más fuerte: sin NINGUNA. Las dos cosas coinciden en la
    primera intervención de una serie, que es donde se escribió y se probó.

    Con la segunda ya no. Sobre ITCER, la llamada 2 en Q2/2009 sobre un base que
    llevaba la caída de 2008 daba AIC ≈396 para los tres candidatos cuando el
    propio base estaba en 381,93: añadir un parámetro «empeoraba» el ajuste, que
    es imposible. Y las ganancias salían de la base equivocada (11,64/15,07
    frente a 11,13/14,30).

    Lo que se retira es SÓLO la intervención que cae en la misma fecha —o dentro
    de `ventana` períodos—, que es el caso de rehacer la forma de un suceso ya
    intervenido. Devuelve `(heredadas, retiradas)` para que la salida pueda
    decir cuál se quitó: retirar una intervención en silencio es cambiar el
    modelo base sin avisar.
    """
    itvs = list(model.interventions or [])
    if at_estudiado is None:
        return [i for i in itvs if i.type in _ESTRUCTURA], []
    hereda, retira = [], []
    for i in itvs:
        if i.type in _ESTRUCTURA:
            hereda.append(i)
        elif abs(int(getattr(i, "at", -10**9)) - int(at_estudiado)) <= int(ventana):
            retira.append(i)
        else:
            hereda.append(i)
    return hereda, retira


def _estructurales(model):
    """Compatibilidad: sólo la estructura estacional. Ver `hereda_del_base`."""
    return hereda_del_base(model)[0]


def escalera_de_ockham(model_base, episodio, dominio: str = "generic",
                       umbral_vecino: float = 0.0) -> Escalera:
    # `umbral_vecino=0` significa «usa el de la política» —el mismo idioma que
    # `ventana=0` en este nodo—. Estaba clavado a 3.0, que es el umbral de los
    # anómalos SUELTOS, y dejaba ciego el tramo (2, 3)σ justo donde la regla de
    # Treadway es más sensible (BUG-0087).
    """Estima los peldaños en orden y dice qué justifica subir — o no subir.

    Parameters
    ----------
    model_base : `fue.Model` AJUSTADO y **sin** la intervención en cuestión.
                 Sus residuos son justo lo que la intervención debe explicar.
    episodio   : el `episodes.Episodio` que sitúa el suceso.
    dominio    : de `policy.decide_domain`. Gobierna la lectura de plausibilidad.
    """
    import fue
    from art.interventions import check_intervention_fit, test_intervention

    freq = int(getattr(model_base.series, "freq", 1) or 1)
    desfase = int(getattr(model_base, "d", 0)) \
        + int(getattr(model_base, "D", 0)) * freq
    at = episodio.at_0based(desfase)
    L = episodio.duracion_nivel
    # BUG-0150: se heredan las intervenciones YA ESTIMADAS del base; sólo se
    # retira la que cae sobre el mismo suceso que se está estudiando.
    base_itvs, _retiradas = hereda_del_base(model_base, at_estudiado=at,
                                            ventana=max(1, int(L)))

    def construye(nivel, nombre, tipo, n_om):
        p = Peldano(nivel=nivel, nombre=nombre, tipo=tipo, n_omega=n_om)
        try:
            itv = fue.Intervention(tipo, at=at, omega=[0.0] * n_om,
                                   omega_free=[True] * n_om)
            m = _clona_con(model_base, base_itvs + [itv])
            m.fit()
            p.model = m
            p.aic = float(m.aic)
            p.loglik = float(m._result.loglik)
            idx = len(base_itvs)
            p.omega = [float(v) for v in (m.interventions[idx].omega or [])]
            try:
                tr = test_intervention(m, idx)
                p.omega_1, p.wald_p = tr.omega_1, tr.wald_p
            except Exception:
                pass
            p.treadway = [c for c in check_intervention_fit(
                m, umbral_vecino=umbral_vecino or None) if c.itv_index == idx]
            from art.diagnosis import diagnose
            dg = diagnose(m)
            # `white_noise` es el veredicto de Q y `normal` el de JB. Se leen de
            # las propiedades y no de los p-valores sueltos para no tener aquí
            # una segunda definición de adecuación que pueda desviarse de la de
            # `diagnosis.py`.
            p.q_pass = bool(dg.white_noise)
            p.jb_pass = bool(dg.normal)
        except Exception as e:                              # pragma: no cover
            p.error = f"{type(e).__name__}: {e}"
        return p

    peldanos = [
        construye("1a", "escalón en el nivel (permanente)", "step", 1),
        construye("1b", "impulso en el nivel (transitorio)", "impulse", 1),
    ]
    # El peldaño 2 sólo tiene sentido si el episodio dura más de un período o si
    # el 1 no se sostiene: la forma general de un episodio de L es L+1 escalones.
    peldanos.append(construye(
        "2", f"episodio de {L} período(s) — {L + 1} escalones en el nivel",
        "step", L + 1))

    # ── por qué subir, o por qué no ─────────────────────────────────────
    p1a, p1b, p2 = (peldanos[0], peldanos[1], peldanos[2])
    simples = [p for p in (p1a, p1b) if p.estimado]
    # NO por AIC (BUG-0086). `1a` y `1b` no están anidadas y cuestan lo mismo;
    # el hueco de AIC entre ellas es ruido, y sobre FOOD_UEM 12/2004 ese ruido
    # —0.74 puntos, prestados de una cola sub-umbral que el impulso capturaba a
    # medias— hacía recomendar un impulso transitorio para un escalón permanente
    # de nivel. La lectura la da la firma del residuo.
    nivel_simple, criterio_simple = lectura_escalar(
        episodio, int(getattr(model_base, "d", 0)))
    mejor_simple = next((p for p in simples if p.nivel == nivel_simple), None)
    if mejor_simple is None:                      # el elegido no estimó
        mejor_simple = simples[0] if simples else None
        if mejor_simple is not None:
            criterio_simple += (f" — pero el peldaño {nivel_simple} no estimó, "
                                f"así que se presenta el {mejor_simple.nivel}")

    razones: list[str] = []
    if mejor_simple is not None:
        if mejor_simple.deja_vecino:
            lado = mejor_simple.treadway[0].vecino_anomalo
            razones.append(
                f"**Treadway**: la lectura simple deja un anómalo de vecino "
                f"({lado}). La parte no modelizada del suceso cae entera ahí — "
                "es evidencia de que la representación se queda corta.")
        if not mejor_simple.adecuado:
            razones.append("**Inadecuación**: la lectura simple no deja ruido "
                           "blanco (Q o JB rechazan).")
    if L > 1:
        razones.append(f"**El episodio dura {L} períodos**: una intervención "
                       "escalar no puede representar más de uno.")
    if dominio in DOMINIOS_SIN_CAIDA_PERMANENTE and p1a.estimado \
            and p1a.omega and p1a.omega[0] < 0:
        razones.append(
            f"**Dominio**: en una serie de clase `{dominio}` una caída "
            "PERMANENTE de nivel es poco usual. La lectura de escalón necesita "
            "respaldo extramuestral antes de aceptarse.")

    recomendado = None
    if mejor_simple is not None and not razones and mejor_simple.se_sostiene:
        recomendado = mejor_simple.nivel
    elif p2.estimado and p2.se_sostiene:
        recomendado = "2"
    elif mejor_simple is not None:
        recomendado = mejor_simple.nivel

    forma = ("permanente" if (mejor_simple is p1a) else "transitoria")
    pregunta = (
        f"¿Hay un suceso conocido en esa fecha que explique una alteración "
        f"**{forma}** del nivel? Un cambio de impuestos o de metodología "
        "explica un escalón permanente; una huelga o un temporal, un impulso "
        "transitorio. La explicación tiene que explicar la FORMA, no sólo la "
        "fecha: si aportas una de suceso permanente y el contraste de ganancia "
        "dice transitorio, no cubre lo que hay.")

    return Escalera(peldanos=peldanos, episodio=episodio, dominio=dominio,
                    razones_para_subir=razones, recomendado=recomendado,
                    pregunta_extramuestral=pregunta,
                    nivel_simple=(mejor_simple.nivel if mejor_simple
                                  else nivel_simple),
                    criterio_simple=criterio_simple)


# ---------------------------------------------------------------------------
# Presentación — aquí es donde vive la navaja
# ---------------------------------------------------------------------------

def _nombre_en(p) -> str:
    """El nombre del peldaño, en inglés, para la FIGURA.

    `p.nombre` está en español porque viaja a la tabla y al dict de datos, que
    son narrativa —el asistente los traduce al idioma del usuario—. Dentro de
    la figura no hay quien traduzca: lo que se dibuja se lee tal cual, y por eso
    va en inglés como el resto de los rótulos (BUG-0139).
    """
    if p.tipo in ("impulse", "pulse"):
        return "impulse in level (transitory)"
    if p.n_omega and p.n_omega > 1:
        return f"episode — {p.n_omega} steps in level"
    return "step in level (permanent)"


def describe_escalera(escalera: "Escalera"):
    """Presenta la escalera EN ORDEN: lo simple primero, y el porqué de subir.

    El orden de la presentación no es cosmético. Enseñar los tres peldaños en
    una tabla ordenada por AIC invita exactamente al error que la navaja
    prohíbe: quedarse con el que mejor ajusta. Aquí el peldaño 1 va delante,
    con su lectura, y el 2 aparece **después de las razones** que justifican
    subir — o no aparece como recomendación si no las hay.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from art.describe import Description, _fig_b64

    ep = escalera.episodio
    p1a = escalera.por_nivel("1a")
    p1b = escalera.por_nivel("1b")
    p2 = escalera.por_nivel("2")
    vivos = [p for p in escalera.peldanos if p.estimado]

    # ── figura: el entorno de residuos bajo cada peldaño ────────────────
    fig = None
    if vivos:
        fig, axs = plt.subplots(len(vivos), 1, figsize=(9, 1.9 * len(vivos)),
                                sharex=True)
        axs = np.atleast_1d(axs)
        ini, fin = max(1, ep.inicio - 6), ep.fin + 6
        for ax, p in zip(axs, vivos):
            r = np.asarray(p.model._result.residuals, dtype=float)
            sd = r.std(ddof=0) or 1.0
            z = (r - r.mean()) / sd
            hi = min(fin, len(z))
            k = np.arange(ini, hi + 1)
            col = "#15803d" if p.se_sostiene else "#b91c1c"
            ax.axhline(0, color="#111", lw=.8)
            for u in (-3, 3):
                ax.axhline(u, color="#b91c1c", ls=":", lw=.9)
            ax.axvspan(ep.inicio - .5, ep.fin + .5, color="#f59e0b", alpha=.25, lw=0)
            ax.bar(k, z[ini - 1:hi], color=col, width=.6)
            ax.set_ylabel(f"rung {p.nivel}", fontsize=9)
            ax.grid(alpha=.25)
            marca = "holds" if p.se_sostiene else (
                "leaves a neighbour" if p.deja_vecino else "inadequate")
            ax.set_title(f"{_nombre_en(p)} — {marca}", fontsize=9, loc="left")
        # EL EJE, EN FECHAS — BUG-0140. El calendario ya estaba aquí
        # (`model.series`); lo que faltaba era leerlo. `desfase` es lo que se
        # comió la diferenciación: sobre residuos, la observación 1 NO es la 1
        # de la serie (BUG-0067).
        _ser = getattr(vivos[0].model, "series", None)
        if _ser is not None:
            from art.describe import _eje_de_fechas
            _f = int(getattr(_ser, "freq", 1) or 1)
            _desf = int(getattr(vivos[0].model, "d", 0)) \
                + int(getattr(vivos[0].model, "D", 0)) * _f
            for _a in axs:
                _eje_de_fechas(_a, _f, getattr(_ser, "start", (1, 1)), _desf)
        axs[-1].set_xlabel("date", fontsize=9)
        fig.suptitle("Residuals around the event, under each rung",
                     fontsize=10)
        fig.tight_layout()

    def fila(p):
        if not p.estimado:
            return f"| {p.nivel} | {p.nombre} | — | — | — | *{p.error}* |"
        w1 = f"{p.omega_1:+.4f}" if p.omega_1 is not None else "—"
        gan = w1
        if p.wald_p is not None:
            gan += f" (p={p.wald_p:.3f})"
        vec = "—"
        if p.treadway:
            vec = p.treadway[0].vecino_anomalo or "ninguno"
        adec = "✓" if p.adecuado else "✗"
        return (f"| **{p.nivel}** | {p.nombre} | {p.aic:.2f} | {gan} | "
                f"{vec} | {adec} |")

    L = [f"### Escalera de Ockham — episodio {ep.inicio}"
         + (f"–{ep.fin}" if not ep.aislado else "")
         + f", {ep.duracion_nivel} período(s) en el nivel", ""]

    L += ["#### Peldaño 1 — una intervención escalar", "",
          "Dos lecturas del **mismo coste**, un parámetro cada una, y no "
          "anidadas entre sí. Cuál es la buena no lo decide el ajuste: la "
          "decide la firma que el suceso deja en los residuos, y después la "
          "matizan el dominio y lo que se sepa del suceso.", "",
          "| | forma | AIC | ω(1) — ganancia | vecino anómalo | adecuado |",
          "|---|---|---|---|---|---|",
          fila(p1a), fila(p1b), ""]
    if escalera.criterio_simple:
        L += [f"**Se lee `{escalera.nivel_simple}`**: "
              f"{escalera.criterio_simple}.", ""]
    if p1a.estimado and p1b.estimado and np.isfinite(p1a.aic) \
            and np.isfinite(p1b.aic):
        L += [f"*La columna de AIC está para mirarla, no para arbitrar: entre "
              f"`1a` y `1b` hay {abs(p1a.aic - p1b.aic):.2f} puntos, y no "
              "significan nada — las dos formas no están anidadas y cuestan lo "
              "mismo, así que su Δ mide ruido (BUG-0086).*", ""]

    for p, etiqueta in ((p1a, "escalón permanente"), (p1b, "impulso transitorio")):
        if p.estimado and p.treadway:
            c = p.treadway[0]
            L.append(f"- **{etiqueta}**: residuo crudo en la fecha "
                     f"{c.residuo_en_fechas[0]:+.3g}"
                     + (f", pero vecino **{c.vecino_anomalo}** con z = "
                        f"{(c.z_despues if c.vecino_anomalo == 'después' else c.z_antes):+.2f}"
                        if c.vecino_anomalo else ", sin vecino anómalo"))
            # La cola activa va como NOTA, nunca en `razones_para_subir`
            # (BUG-0096). La regla de Treadway se queda en 2σ; esto sólo dice
            # que con ARMA el residuo crudo pierde potencia y que ahí un vecino
            # sub-umbral PUEDE ser la cola. Meterlo en las razones convertiría
            # un 13% de probabilidad bajo la nula en evidencia, y la
            # sobre-intervención es el modo de fallo que no se detiene solo.
            if c.cola_activa and not c.vecino_anomalo:
                _zc = max((abs(v) for v in (c.z_antes, c.z_despues)
                           if v is not None and abs(v) < c.umbral_vecino),
                          default=0.0)
                L.append(f"  *(vecino {c.cola_activa} a {_zc:.2f}σ: no llega a "
                         f"anómalo, pero el modelo lleva ARMA y ahí el residuo "
                         f"crudo pierde potencia. Nota, no razón para subir.)*")
    L.append("")

    L += ["#### ¿Se sube?", ""]
    if escalera.razones_para_subir:
        L += [f"- {x}" for x in escalera.razones_para_subir]
        if escalera.ningun_peldano_se_sostiene:
            _alto = escalera.por_nivel("2")
            _pega = ("tampoco se estimó" if _alto is None or not _alto.estimado
                     else f"deja vecino ({_alto.treadway[0].vecino_anomalo})"
                     if _alto.deja_vecino else "tampoco deja ruido blanco")
            L += ["", f"**…y aun así se recomienda `{escalera.recomendado}`, "
                  "que es el peldaño bajo.** No es que la subida se haya "
                  f"evaluado y descartado: es que el peldaño 2 {_pega}, así que "
                  "**ninguna forma de esta escalera resuelve el suceso**. Lo "
                  "que se recomienda es el menos malo, no uno que se sostenga. "
                  "Mira si el episodio está bien delimitado "
                  "(`incident_configurations`) o si lo que queda no es un "
                  "suceso sino estructura sin modelizar."]
        L += ["", "#### Peldaño 2 — el episodio", "",
              "| | forma | AIC | ω(1) — ganancia | vecino anómalo | adecuado |",
              "|---|---|---|---|---|---|", fila(p2), ""]
        if p2.estimado and p2.transitorio is not None:
            L.append(
                f"El contraste de ganancia **{'no rechaza' if p2.transitorio else 'RECHAZA'}** "
                f"ω(1)=0 ⇒ el efecto es "
                f"**{'TRANSITORIO' if p2.transitorio else 'PERMANENTE'}**"
                + (f": {ep.duracion_nivel} impulso(s) en el nivel y vuelta a la "
                   "línea base." if p2.transitorio
                   else ": el nivel se queda desplazado."))
    else:
        L += ["**No hay razón para subir.** La lectura simple absorbe su fecha, "
              "no deja vecino anómalo y el modelo es adecuado. Subir un peldaño "
              "aquí sería añadir parámetros a un problema resuelto.", ""]

    if len(vivos) > 1:
        mejor = min(vivos, key=lambda p: p.aic)
        peor = max(vivos, key=lambda p: p.aic)
        L += ["", f"*Para referencia, el rango de AIC va de {mejor.aic:.2f} "
              f"({mejor.nivel}) a {peor.aic:.2f} ({peor.nivel}).* **El AIC no "
              "arbitra la subida de peldaño**: compara dentro de uno, o confirma "
              "una subida ya justificada. Una escalera que se quedase con el "
              "mejor AIC subiría siempre, porque el modelo más sofisticado casi "
              "siempre ajusta mejor — tiene más parámetros."]

    L += ["", "---", "", "#### Lo que la herramienta no puede saber", "",
          escalera.pregunta_extramuestral]

    rec = escalera.recomendado
    recomendacion = (
        f"Peldaño **{rec}** por las razones de arriba. Antes de fijarlo, "
        "contesta la pregunta extramuestral: si hay un suceso conocido que "
        "explique la FORMA simple, la simple gana aunque ajuste peor."
        if rec else
        "Ningún peldaño se sostiene. Revisa la fecha con `intervention_plot` "
        "antes de añadir parámetros.")

    return Description(
        summary="\n".join(L),
        figure_b64=_fig_b64(fig) if fig is not None else None,
        recommendation=recomendacion,
        data=dict(
            episodio=dict(inicio=ep.inicio, fin=ep.fin,
                          duracion_nivel=ep.duracion_nivel,
                          n_escalones=ep.n_escalones),
            dominio=escalera.dominio,
            recomendado=rec,
            razones=escalera.razones_para_subir,
            peldanos=[dict(nivel=p.nivel, nombre=p.nombre, aic=p.aic,
                           loglik=p.loglik, omega=p.omega, omega_1=p.omega_1,
                           wald_p=p.wald_p, adecuado=p.adecuado,
                           deja_vecino=p.deja_vecino, absorbe=p.absorbe,
                           se_sostiene=p.se_sostiene, transitorio=p.transitorio,
                           error=p.error)
                      for p in escalera.peldanos]),
    )
