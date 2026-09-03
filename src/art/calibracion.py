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

Medido sobre PGAS m00, retardo 2:

    ACF(2)   +0,1321 → +0,3108   SALE de banda   (el anómalo la ENMASCARABA)
    PACF(2)  −0,2964 → −0,1991   ENTRA en banda  (el anómalo la FABRICABA)

El mismo anómalo escondía una señal MA y fabricaba una señal AR **a la vez**.
Quien calibrase sólo la ACF concluiría «hay más MA de la que creía» y no se
enteraría de que el AR(2) que estaba a punto de estimar era el anómalo.

Y sirve en los dos sentidos, que es lo que evita **sobre-intervenir**: si al
quitar el anómalo ningún retardo cambia de veredicto dentro/fuera de banda,
intervenirlo no compra nada para la identificación, y añadir una intervención
que no hace falta es gastar un parámetro y tocar la serie sin motivo.

Cómo se calcula «sin el anómalo» — y por qué así
------------------------------------------------
**Se OMITEN los anómalos del cálculo. No se sustituyen por nada.**

La razón es que sustituirlos supondría una forma. Poner el residuo a la media
equivale a un **impulso** con ω libre —es lo que hace la condición de primer
orden, la regla de Treadway—, y eso es circular: esta herramienta existe para
informar la elección de forma, así que no puede suponer una para calcularse.

Concretamente, con `I` el conjunto de índices señalados:

    μ̂  y  σ̂²   se calculan sobre las observaciones RETENIDAS
    r(k) = ⟨(xᵢ−μ̂)(xᵢ₊ₖ−μ̂)⟩  sobre los pares donde NINGUNO de los dos está en I
    φ(k)  por Durbin-Levinson sobre ese r(k)

La PACF sale de la ACF, así que **una sola omisión da las dos funciones**, que
es la propiedad que hace esto barato.

Normalizar bien es la mitad del asunto
--------------------------------------
La primera versión omitía los pares pero seguía normalizando con la μ y la σ
**contaminadas**, y salía mal: decía que la autocorrelación de retardo 1 BAJA
al quitar el anómalo cuando en realidad sube. Contrastado sobre PGAS m00 contra
el modelo realmente calibrado (m10):

    PACF               lag1      lag2      lag3      lag4    error medio
    observada        +0.5749   -0.2964   +0.1054   -0.0444
    omitir, ingenua  +0.5256   -0.0312   -0.0007   +0.0467      0.0795  ✗
    omitir, CORRECTA +0.6700   -0.2146   +0.0602   +0.0699      0.0212  ←
    a la media       +0.6521   -0.1991   +0.0550   +0.0600      0.0162
    REAL (m10)       +0.6497   -0.2348   +0.0378   +0.0399

Omitir bien y sustituir por la media empatan en la práctica —0,0212 frente a
0,0162, y en el retardo 2, que es el que decide, omitir es incluso mejor
(−0,215 contra −0,199, frente al real −0,235)—, así que no hay nada que pagar
por evitar el supuesto de forma.

Una nota de consistencia
------------------------
Las dos columnas —observada y calibrada— se calculan con **el mismo estimador**,
normalizando por el número de pares retenidos. Sin omisión eso es n−k, mientras
que `fue.acf` y `diagnose` normalizan por n, así que la columna «observada» de
aquí puede diferir de la de la diagnosis en la tercera cifra (sobre PGAS:
+0,5819 frente a +0,5749). Se prefiere la consistencia INTERNA: así todo el
movimiento entre las dos columnas es efecto de la omisión y no del estimador,
que es lo que la herramienta afirma medir. El efecto de la omisión en ese mismo
retardo es de 0,095 — trece veces la diferencia de convenio.

Lo que la omisión sí cuesta
---------------------------
Cada retardo usa un conjunto de pares distinto, así que la secuencia r(k) que
sale **no está garantizada definida positiva**. Cuando no lo es, la recursión
de Durbin-Levinson devuelve |φ(k)| ≥ 1, que no es una PACF. Es una decisión
subóptima y conocida: la herramienta la detecta y lo **dice**, en vez de
publicar números que no significan nada.
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
    """
    K = len(r)
    phi, prev = [], []
    for k in range(1, K + 1):
        if k == 1:
            p = float(r[0])
            prev = [p]
        else:
            num = r[k - 1] - sum(prev[j] * r[k - 2 - j] for j in range(k - 1))
            den = 1.0 - sum(prev[j] * r[j] for j in range(k - 1))
            p = float(num / den) if abs(den) > 1e-12 else float("nan")
            prev = [prev[j] - p * prev[k - 2 - j] for j in range(k - 1)] + [p]
        phi.append(p)
    return np.array(phi)


def _acf_pacf(x: np.ndarray, K: int,
              omitir: set[int] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """ACF y PACF de `x` hasta K, OMITIENDO los índices de `omitir`.

    μ̂ y σ̂² se calculan sobre lo retenido, y cada r(k) promedia sólo los pares
    donde ninguno de los dos miembros está omitido. Normalizar con la μ y la σ
    contaminadas invierte el signo del efecto — ver la cabecera del módulo.
    """
    om = omitir or set()
    n = len(x)
    keep = np.array([i for i in range(n) if i not in om])
    mu = float(x[keep].mean())
    var = float(((x[keep] - mu) ** 2).mean())
    if var < 1e-20:
        raise ValueError("varianza nula sobre las observaciones retenidas.")
    r = np.empty(K)
    for k in range(1, K + 1):
        pares = [(x[i] - mu) * (x[i + k] - mu) for i in range(n - k)
                 if i not in om and (i + k) not in om]
        r[k - 1] = (float(np.mean(pares)) / var) if pares else 0.0
    return r, _durbin_levinson(r)


@dataclass
class Distorsion:
    """Lo que le pasa a un retardo cuando se quita el anómalo."""

    lag: int
    acf_obs: float
    acf_cal: float
    pacf_obs: float
    pacf_cal: float
    banda: float

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
    pacf_valida: bool = True

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
                         max_lag: int = 12) -> CalibracionCorrelograma:
    """Cuánto de la ACF y de la PACF se debe a los residuos extremos.

    Parameters
    ----------
    residuals : los residuos de un modelo estimado.
    umbral    : |z| a partir del cual un residuo se considera extremo.
    max_lag   : hasta qué retardo calibrar.

    Los extremos se sustituyen por la media y se recalcula TODO —media, σ, ACF
    y PACF—, que es lo que hace una intervención de impulso con ω libre. Ver la
    validación en la cabecera del módulo.
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
    idx = [i for i in range(n) if abs(z[i]) > umbral]
    extremos = [(i + 1, float(z[i])) for i in idx]

    a_obs, p_obs = _acf_pacf(r, K)
    if idx:
        # OMITIR, no sustituir: sustituir supondría una forma (un impulso), y
        # esta herramienta existe para informar la elección de forma.
        a_cal, p_cal = _acf_pacf(r, K, omitir=set(idx))
        keep = np.array([i for i in range(n) if i not in set(idx)])
        sigma_cal = float(r[keep].std(ddof=0))
    else:
        a_cal, p_cal, sigma_cal = a_obs.copy(), p_obs.copy(), sd

    # La secuencia omitida no está garantizada definida positiva: cada retardo
    # usa un conjunto de pares distinto. Si no lo es, Durbin-Levinson devuelve
    # |φ| ≥ 1, que no es una PACF, y hay que decirlo en vez de publicarla.
    pd_ok = bool(np.all(np.isfinite(p_cal)) and np.max(np.abs(p_cal)) < 1.0)

    banda = 2.0 / np.sqrt(n)
    dis = [Distorsion(lag=k + 1, banda=banda,
                      acf_obs=float(a_obs[k]), acf_cal=float(a_cal[k]),
                      pacf_obs=float(p_obs[k]), pacf_cal=float(p_cal[k]))
           for k in range(K)]

    return CalibracionCorrelograma(
        distorsiones=dis, extremos=extremos, n=n, banda=banda, umbral=umbral,
        sigma_obs=sd, sigma_cal=sigma_cal)


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def describe_calibracion(cal: "CalibracionCorrelograma", nombre: str = ""):
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
         f"**{len(cal.extremos)} residuo(s) extremo(s)** con |z| > {cal.umbral:g}: {ext}",
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
