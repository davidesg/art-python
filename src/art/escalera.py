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

__all__ = ["Peldano", "Escalera", "escalera_de_ockham", "describe_escalera"]


# Clases de serie en las que un cambio PERMANENTE de nivel es poco usual, y
# por tanto la lectura simple necesita respaldo antes de aceptarse. No es un
# veredicto: es la razón de dominio del punto 3 de arriba.
DOMINIOS_SIN_CAIDA_PERMANENTE = ("price_index",)


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

    def por_nivel(self, nivel: str) -> Peldano | None:
        return next((p for p in self.peldanos if p.nivel == nivel), None)


def _clona_con(model, itvs):
    """El modelo base con OTRO juego de intervenciones y las mismas semillas."""
    import fue
    kw = {}
    for a in ("ar", "ma", "ar_s", "ma_s", "ar_free", "ma_free",
              "ar_s_free", "ma_s_free", "ar_f", "ma_f", "d", "D",
              "ifadf", "mu", "estimate_mu", "boxlam"):
        v = getattr(model, a, None)
        if v is not None:
            kw[a] = v
    return fue.Model(model.series, interventions=itvs, **kw)


def _estructurales(model):
    """Armónicos y `alter`: son estructura estacional, no sucesos, y tienen que
    sobrevivir a cada peldaño."""
    return [i for i in (model.interventions or [])
            if i.type in ("cos", "sin", "alter")]


def escalera_de_ockham(model_base, episodio, dominio: str = "generic",
                       umbral_vecino: float = 3.0) -> Escalera:
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
    base_itvs = _estructurales(model_base)

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
                m, umbral_vecino=umbral_vecino) if c.itv_index == idx]
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
    mejor_simple = min(simples, key=lambda p: p.aic) if simples else None

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
                    pregunta_extramuestral=pregunta)


# ---------------------------------------------------------------------------
# Presentación — aquí es donde vive la navaja
# ---------------------------------------------------------------------------

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
            ax.set_ylabel(f"peldaño {p.nivel}", fontsize=9)
            ax.grid(alpha=.25)
            marca = "se sostiene" if p.se_sostiene else (
                "deja vecino" if p.deja_vecino else "inadecuado")
            ax.set_title(f"{p.nombre} — {marca}", fontsize=9, loc="left")
        axs[-1].set_xlabel("observación (residuos)")
        fig.suptitle("Residuos en el entorno del suceso, bajo cada peldaño",
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
          "anidadas entre sí. Cuál es la buena no lo decide el ajuste: lo "
          "deciden el dominio y lo que se sepa del suceso.", "",
          "| | forma | AIC | ω(1) — ganancia | vecino anómalo | adecuado |",
          "|---|---|---|---|---|---|",
          fila(p1a), fila(p1b), ""]

    for p, etiqueta in ((p1a, "escalón permanente"), (p1b, "impulso transitorio")):
        if p.estimado and p.treadway:
            c = p.treadway[0]
            L.append(f"- **{etiqueta}**: residuo crudo en la fecha "
                     f"{c.residuo_en_fechas[0]:+.3g}"
                     + (f", pero vecino **{c.vecino_anomalo}** con z = "
                        f"{(c.z_despues if c.vecino_anomalo == 'después' else c.z_antes):+.2f}"
                        if c.vecino_anomalo else ", sin vecino anómalo"))
    L.append("")

    L += ["#### ¿Se sube?", ""]
    if escalera.razones_para_subir:
        L += [f"- {x}" for x in escalera.razones_para_subir]
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
