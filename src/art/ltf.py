"""art.ltf — la respuesta de una función lineal de transferencia, simulada.

Puerto a Python de `SRC/LTF/LTF-1.0.2/ltf.c`, el simulador con el que se enseña
a leer la forma de una intervención.

Para qué está
-------------
La forma de una intervención **no se identifica a ojo**. `fue` permite
especificarla como una FLT —varios parámetros para un solo suceso— y en cuanto
`s` crece, la figura del gráfico deja de tener lectura obvia: dos impulsos en el
nivel pueden aparecer, en primeras diferencias, con un aspecto que no sugiere
dos impulsos.

Este módulo no decide nada. Dibuja **la hipótesis** para que se pueda poner al
lado del patrón observado y ver si son compatibles — evidencia, no veredicto.

El diccionario nivel ↔ primeras diferencias
-------------------------------------------
Toda intervención se especifica **en el nivel de la serie**, sea cual sea la `d`
con la que se trabaje. Sin ese convenio, «escalón» significa una cosa en `d=0` y
otra en `d=1` y el analista no puede razonar. Con él:

===========================  ==================================  ==========
en el NIVEL                  en primeras diferencias             suma en ∇
===========================  ==================================  ==========
escalón ω en T               UN impulso ω en T                   ω
impulso ω en T               DOS impulsos: +ω en T, −ω en T+1    **0**
dos impulsos (ω₀, ω₁)        TRES impulsos: +ω₀, ω₁−ω₀, −ω₁      **0**
===========================  ==================================  ==========

Un escalón en el nivel es un efecto **permanente**; un impulso en el nivel es un
efecto **transitorio**. La suma de la respuesta en ∇ es la ganancia a largo
plazo, y **ganancia cero ⟺ transitorio**.

De ahí sale la familia anidada sobre la que descansa el nodo de episodios: N
escalones consecutivos en el nivel con ganancia nula son N−1 impulsos en el
nivel, o sea un episodio de duración N−1
(`docs/DISENO-nodo-intervencion.md` §2.2).

La convención de signo, que es donde se cae
-------------------------------------------
`fue` guarda el numerador con ω **restada** en los retardos ≥ 1:

    ω(B) = ω₀ − ω₁B − ω₂B² − ⋯

Se ve en `calcnu()` de `fue_api.c` y en `ltf.c`. Es lo que costó BUG-0066:
leímos como cuasi-cancelación (−0,05) una respuesta que **suma** −17,92. La
ganancia es por tanto

    ν(1) = ω(1)/δ(1) = (ω₀ − ω₁ − ⋯ − ω_s) / (1 − δ₁ − ⋯ − δ_r)

Alcance: d = 0, 1
-----------------
Con `d=2` un impulso en la serie transformada equivale a una **rampa** en el
nivel: el diccionario de arriba tiene otra fila y la lectura cambia. El C ya
valida `d < 0 || d > 1`; aquí se levanta una excepción explícita en vez de
devolver una figura que se leería mal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

__all__ = ["RespuestaFLT", "respuesta_flt", "describe_ltf"]


@dataclass
class RespuestaFLT:
    """La respuesta de una FLT, en impulso y en escalón.

    `nu` es la respuesta a un choque unitario de UNA VEZ en la entrada (IRF).
    `srf` es la respuesta a un cambio unitario PERMANENTE (la acumulada), y es
    la que da el **camino del nivel** cuando la intervención se especifica como
    escalón — que es el caso del nodo de episodios.

    Con `d=1` ambas vienen ya diferenciadas: es lo que se ve en el gráfico de la
    serie transformada.
    """

    nu: np.ndarray                 # IRF, (K+1,)
    srf: np.ndarray                # SRF acumulada, (K+1,)
    omega: tuple[float, ...]
    delta: tuple[float, ...]
    b: int
    d: int
    K: int
    omega_1: float                 # ω(1) = ω₀ − ω₁ − ⋯ − ω_s
    delta_1: float                 # δ(1) = 1 − δ₁ − ⋯ − δ_r
    gain: float                    # ν(1) = ω(1)/δ(1); NaN si δ(1) ≈ 0

    @property
    def s(self) -> int:
        return len(self.omega) - 1

    @property
    def r(self) -> int:
        return len(self.delta)

    @property
    def transitorio(self) -> bool:
        """Ganancia nula ⟹ el nivel vuelve a la base. Lectura exacta, sin
        contraste: aquí los parámetros son DADOS, no estimados. El contraste
        sobre parámetros estimados es `interventions.test_intervention`."""
        return abs(self.gain) < 1e-12

    @property
    def duracion_episodio(self) -> int | None:
        """Períodos con el nivel alterado, si el efecto es transitorio.

        Para N escalones en el nivel con ganancia nula son N−1 = s períodos.
        `None` si el efecto es permanente, donde «duración» no significa nada.
        """
        return self.s if self.transitorio else None


def respuesta_flt(omega: Sequence[float],
                  delta: Sequence[float] = (),
                  b: int = 0,
                  K: int = 48,
                  d: int = 0) -> RespuestaFLT:
    """Simula la respuesta de ω(B)/δ(B) con retardo muerto `b`.

    Parameters
    ----------
    omega : los ω₀…ω_s del numerador, **con la convención de fue**: ω₀ suma y
            los demás restan.
    delta : los δ₁…δ_r del denominador (vacío = sin denominador).
    b     : retardo muerto, en períodos.
    K     : hasta qué retardo simular. Debe ser > s.
    d     : 0 devuelve las respuestas en el NIVEL; 1 las devuelve en primeras
            diferencias, que es lo que se ve en la serie transformada.

    Raises
    ------
    ValueError : si d ∉ {0,1}, si K ≤ s, o si b < 0.
    """
    om = [float(v) for v in omega]
    dl = [float(v) for v in delta]
    s, r = len(om) - 1, len(dl)

    if not om:
        raise ValueError("omega no puede estar vacío: sin ω no hay respuesta.")
    if d not in (0, 1):
        raise ValueError(
            f"d={d} fuera de alcance: este simulador cubre d=0 y d=1. Con d=2 "
            "un impulso en la serie transformada equivale a una RAMPA en el "
            "nivel, el diccionario nivel↔diferencias tiene otra fila y la "
            "figura se leería mal. Ver docs/DISENO-nodo-intervencion.md §2.3.")
    if K <= s:
        raise ValueError(f"K={K} debe ser mayor que s={s}: la respuesta no "
                         "cabe en la ventana simulada.")
    if b < 0:
        raise ValueError(f"b={b} negativo: el retardo muerto no va hacia atrás.")

    # ── 1. los ν, con la recursión de calcnu()/ltf.c ─────────────────────
    # nu[k] = Σ_j δ_j·nu[k−j] − ω_k    (ω RESTADA en k ≥ 1)
    # Antes de k=0 la respuesta es cero, que es lo que en el C hacen las r
    # celdas de relleno del calloc.
    nu = np.zeros(K + 1)
    nu[0] = om[0]
    for k in range(1, K + 1):
        v = -om[k] if k <= s else 0.0
        for j in range(1, r + 1):
            if k - j >= 0:
                v += dl[j - 1] * nu[k - j]
        nu[k] = v

    # ── 2. retardo muerto: desplaza la respuesta b períodos ──────────────
    if b > 0:
        for k in range(K, b - 1, -1):
            nu[k] = nu[k - b]
        nu[:b] = 0.0

    # ── 3. la acumulada ──────────────────────────────────────────────────
    srf = np.cumsum(nu)

    # ── 4. y a primeras diferencias si se pide ───────────────────────────
    # nu[0] y srf[0] no se tocan: no hay observación previa que restar.
    if d == 1:
        nu = np.concatenate(([nu[0]], np.diff(nu)))
        srf = np.concatenate(([srf[0]], np.diff(srf)))

    omega_1 = om[0] - sum(om[1:])
    delta_1 = 1.0 - sum(dl)
    gain = omega_1 / delta_1 if abs(delta_1) > 1e-10 else float("nan")

    return RespuestaFLT(nu=nu, srf=srf, omega=tuple(om), delta=tuple(dl),
                        b=b, d=d, K=K, omega_1=omega_1, delta_1=delta_1,
                        gain=gain)


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def describe_ltf(omega: Sequence[float],
                 delta: Sequence[float] = (),
                 b: int = 0,
                 K: int = 24,
                 d: int = 0,
                 etiqueta: str = ""):
    """Dibuja la hipótesis, en el nivel y en primeras diferencias.

    Devuelve una `Description` como el resto del paquete. La figura lleva
    CUATRO paneles porque la pregunta que el analista trae —«¿lo que veo es
    compatible con esto?»— sólo se contesta viendo la misma respuesta en las
    dos escalas a la vez: en el nivel, que es donde se especifica, y en
    diferencias, que es donde se mira.

    No emite veredicto. La lectura permanente/transitorio que da es EXACTA
    porque aquí los parámetros son dados; sobre parámetros estimados el que
    decide es el contraste de `interventions.test_intervention`.
    """
    import io, base64
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from art.describe import Description, _fig_b64

    niv = respuesta_flt(omega, delta, b=b, K=K, d=0)
    dif = respuesta_flt(omega, delta, b=b, K=K, d=1)
    k = np.arange(K + 1)

    fig, ax = plt.subplots(2, 2, figsize=(11, 6.2), sharex=True)
    paneles = [
        (ax[0][0], niv.nu,  "IRF — nivel",            "#1d4ed8"),
        (ax[0][1], niv.srf, "SRF — nivel (camino del nivel)", "#b91c1c"),
        (ax[1][0], dif.nu,  "IRF — primeras diferencias",     "#1d4ed8"),
        (ax[1][1], dif.srf, "SRF — primeras diferencias",     "#b91c1c"),
    ]
    for a, y, titulo, color in paneles:
        a.stem(k, y, linefmt=color, markerfmt="o", basefmt=" ")
        a.axhline(0, color="#111", lw=0.8)
        a.set_title(titulo, fontsize=10)
        a.grid(alpha=0.25)
    # la ganancia, donde la acumulada del nivel converge
    if np.isfinite(niv.gain):
        ax[0][1].axhline(niv.gain, ls="--", lw=1.0, color="#111")
        ax[0][1].annotate(f"ganancia {niv.gain:.4f}", (K, niv.gain),
                          textcoords="offset points", xytext=(-4, 5),
                          ha="right", fontsize=8)
    ax[1][0].set_xlabel("retardo k")
    ax[1][1].set_xlabel("retardo k")
    cab = etiqueta or f"ω{tuple(round(v, 4) for v in niv.omega)}"
    if niv.delta:
        cab += f" / δ{tuple(round(v, 4) for v in niv.delta)}"
    if b:
        cab += f", b={b}"
    fig.suptitle(f"Respuesta de la FLT — {cab}", fontsize=11)
    fig.tight_layout()
    b64 = _fig_b64(fig)
    plt.close(fig)

    if niv.transitorio:
        lectura = (f"**TRANSITORIO** — ganancia ω(1)/δ(1) = 0: el nivel vuelve "
                   f"a la línea base tras **{niv.duracion_episodio}** período(s). "
                   f"Equivale a {niv.duracion_episodio} impulso(s) en el nivel.")
    elif np.isnan(niv.gain):
        lectura = ("**INADMISIBLE** — δ(1) = 0: la ganancia no está acotada. "
                   "La respuesta no converge y la figura no se puede leer como "
                   "un efecto de nivel.")
    else:
        lectura = (f"**PERMANENTE** — ganancia **{niv.gain:+.4f}**: el nivel se "
                   f"queda desplazado.")

    lineas = [
        f"### Respuesta simulada — {cab}",
        "",
        f"ω(1) = **{niv.omega_1:+.4f}**   ·   δ(1) = **{niv.delta_1:+.4f}**   ·   "
        f"ganancia ν(1) = **{niv.gain:+.4f}**" if np.isfinite(niv.gain) else
        f"ω(1) = **{niv.omega_1:+.4f}**   ·   δ(1) = **{niv.delta_1:+.4f}**   ·   "
        f"ganancia **no acotada**",
        "",
        lectura,
        "",
        "*La fila de arriba es el NIVEL, donde se especifica la intervención; la "
        "de abajo, primeras diferencias, que es donde se mira. La columna SRF es "
        "la respuesta a un escalón — el camino del nivel.*",
    ]

    return Description(
        summary="\n".join(lineas),
        figure_b64=b64,
        recommendation=(
            "Compara esta figura con el patrón de los residuos. Si no encajan, "
            "la hipótesis de forma es otra: prueba otro número de escalones o "
            "añade denominador. El simulador no decide — enseña."),
        data=dict(omega=list(niv.omega), delta=list(niv.delta), b=b, K=K,
                  omega_1=niv.omega_1, delta_1=niv.delta_1, gain=niv.gain,
                  transitorio=niv.transitorio,
                  duracion_episodio=niv.duracion_episodio,
                  nu_nivel=niv.nu.tolist(), srf_nivel=niv.srf.tolist(),
                  nu_dif=dif.nu.tolist(), srf_dif=dif.srf.tolist()),
    )


# ---------------------------------------------------------------------------
# Superposición: la hipótesis ENCIMA de lo observado
# ---------------------------------------------------------------------------

@dataclass
class Superposicion:
    """Cómo de bien explica una forma hipotética lo que se ve en el entorno.

    Tres números que separan tres preguntas distintas, y que se leen sin
    necesidad de mirar la figura —así sirven también al carril autónomo:

    `escala`  cuánto hay que multiplicar la respuesta simulada para que encaje.
              Lejos de 1 con ω estimados dice que la AMPLITUD no es la que se
              creía; con ω unitarios es simplemente la magnitud del suceso.
    `r2`      qué fracción de la suma de cuadrados del entorno explica la forma
              ya escalada. Bajo = la FORMA no es ésa, por mucho que la amplitud
              cuadre.
    `z_resto` el mayor residuo que queda en el entorno después de quitar la
              forma escalada, en unidades de desviación típica global. Es el
              más interpretable: si tras ajustar la forma sigue habiendo un 4,
              la hipótesis no cubre lo que hay.
    """

    k: np.ndarray                  # posiciones 1-based de la ventana mostrada
    observado: np.ndarray
    simulado: np.ndarray           # ya escalado
    resto: np.ndarray              # observado − simulado
    at: int
    escala: float
    r2: float
    z_resto: float
    sd: float
    entrada: str

    @property
    def la_forma_explica(self) -> bool:
        """Criterio de lectura, no veredicto: la forma cubre lo que hay si
        explica la mayor parte del entorno y no deja nada extremo detrás."""
        return self.r2 >= 0.70 and abs(self.z_resto) < 3.0


def superpone(observado: Sequence[float],
              at: int,
              omega: Sequence[float],
              delta: Sequence[float] = (),
              b: int = 0,
              d: int = 0,
              ventana: int = 8,
              entrada: str = "escalon") -> Superposicion:
    """Pone la respuesta simulada encima de lo observado, en el ENTORNO.

    Parameters
    ----------
    observado : la serie sobre la que se mira — normalmente los RESIDUOS de un
                modelo SIN la intervención, que es exactamente la parte que la
                intervención tiene que explicar.
    at        : posición 1-based donde arranca el suceso, en el índice de
                `observado`.
    omega,
    delta, b  : la hipótesis de forma, con la convención de fue.
    d         : diferenciación del modelo. `observado` está diferenciado, así
                que la respuesta hay que diferenciarla igual para compararlas.
    ventana   : períodos a mostrar antes y después del soporte de la respuesta.
    entrada   : "escalon" usa la respuesta al escalón (el camino del nivel, que
                es el lenguaje homogeneizado del nodo); "impulso" usa la IRF.

    La escala se ajusta por mínimos cuadrados por el origen, y por eso `escala`
    y `r2` separan dos preguntas: la amplitud y la forma. Un ajuste de forma
    bueno con escala 3 dice «es esta forma, tres veces más grande»; una escala
    1 con r2 bajo dice «esta forma no es».
    """
    y = np.asarray(observado, dtype=float)
    n = len(y)
    if not (1 <= at <= n):
        raise ValueError(f"at={at} fuera de la serie observada (1..{n}).")

    s = len(omega) - 1
    K = max(s + ventana, 2 * ventana)
    r = respuesta_flt(omega, delta, b=b, K=K, d=d)
    base = r.srf if entrada == "escalon" else r.nu
    if entrada not in ("escalon", "impulso"):
        raise ValueError(f"entrada={entrada!r}: 'escalon' o 'impulso'.")

    # soporte efectivo: hasta donde la respuesta deja de moverse
    nz = np.nonzero(np.abs(base) > 1e-12)[0]
    fin_sop = int(nz[-1]) if len(nz) else 0

    ini = max(1, at - ventana)
    fin = min(n, at + fin_sop + ventana)
    k = np.arange(ini, fin + 1)
    obs = y[ini - 1:fin]

    sim = np.zeros_like(obs)
    for j in range(fin_sop + 1):
        pos = at + j
        if ini <= pos <= fin:
            sim[pos - ini] = base[j]

    den = float(sim @ sim)
    escala = float(obs @ sim) / den if den > 1e-15 else 0.0
    sim_esc = escala * sim
    resto = obs - sim_esc

    ss_tot = float(obs @ obs)
    r2 = 1.0 - float(resto @ resto) / ss_tot if ss_tot > 1e-15 else 0.0
    sd = float(np.std(y, ddof=0)) or 1.0
    z_resto = float(np.max(np.abs(resto)) / sd)

    return Superposicion(k=k, observado=obs, simulado=sim_esc, resto=resto,
                         at=at, escala=escala, r2=r2, z_resto=z_resto,
                         sd=sd, entrada=entrada)


def describe_superposicion(observado: Sequence[float],
                           at: int,
                           omega: Sequence[float],
                           delta: Sequence[float] = (),
                           b: int = 0,
                           d: int = 0,
                           ventana: int = 8,
                           entrada: str = "escalon",
                           etiqueta: str = ""):
    """La superposición, presentada. Figura para el carril guiado; los tres
    números de `Superposicion` sirven en los dos."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from art.describe import Description, _fig_b64

    sp = superpone(observado, at, omega, delta, b=b, d=d,
                   ventana=ventana, entrada=entrada)

    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.4), sharex=True,
                                 gridspec_kw=dict(height_ratios=[2.2, 1]))
    a1.axhline(0, color="#111", lw=0.8)
    a1.axvline(sp.at, color="#f59e0b", lw=8, alpha=0.30)
    a1.plot(sp.k, sp.observado, color="#1d4ed8", lw=1.2, marker="o", ms=4,
            label="observado", zorder=3)
    a1.plot(sp.k, sp.simulado, color="#b91c1c", lw=1.6, ls="--", marker="s",
            ms=4, label=f"hipótesis × {sp.escala:.3g}", zorder=2)
    a1.legend(fontsize=8, loc="best")
    a1.set_ylabel("nivel" if d == 0 else "∇")
    a1.grid(alpha=0.25)
    a1.set_title(etiqueta or f"Superposición en el entorno de obs {sp.at}",
                 fontsize=10)

    a2.axhline(0, color="#111", lw=0.8)
    for u in (-3, 3):
        a2.axhline(u * sp.sd, color="#b91c1c", ls=":", lw=0.9)
    a2.bar(sp.k, sp.resto, color="#6b7280", width=0.65)
    a2.set_ylabel("resto")
    a2.set_xlabel("observación")
    a2.grid(alpha=0.25)
    fig.tight_layout()
    b64 = _fig_b64(fig)
    plt.close(fig)

    if sp.la_forma_explica:
        lectura = ("**La forma cubre lo que hay.** Explica la mayor parte del "
                   "entorno y no deja nada extremo detrás.")
    elif sp.r2 < 0.70:
        lectura = (f"**La FORMA no encaja** (R² = {sp.r2:.2f}). No es cuestión "
                   "de amplitud: el perfil observado es otro. Prueba otro "
                   "número de escalones, o mira si hay denominador.")
    else:
        lectura = (f"La forma encaja pero **deja un residuo de z = "
                   f"{sp.z_resto:+.2f}** en el entorno: hay algo más que esta "
                   "hipótesis no recoge.")

    lineas = [
        f"### Superposición — entorno de la observación {sp.at}",
        "",
        f"escala **{sp.escala:.4g}** · forma explicada **R² = {sp.r2:.3f}** · "
        f"mayor resto **z = {sp.z_resto:+.2f}**",
        "",
        lectura,
        "",
        "*La escala y el R² separan dos preguntas: la AMPLITUD y la FORMA. Un "
        "R² alto con escala 3 dice «es esta forma, tres veces mayor»; una "
        "escala 1 con R² bajo dice «esta forma no es».*",
    ]

    return Description(
        summary="\n".join(lineas),
        figure_b64=b64,
        recommendation=(
            "Si la forma no encaja, no la estimes: cambia la hipótesis y vuelve "
            "a superponer. Estimar una forma que ya se ve incompatible gasta un "
            "modelo para confirmar lo que el gráfico decía gratis."),
        data=dict(at=sp.at, escala=sp.escala, r2=sp.r2, z_resto=sp.z_resto,
                  entrada=sp.entrada, d=d, omega=list(omega),
                  delta=list(delta), b=b,
                  k=sp.k.tolist(), observado=sp.observado.tolist(),
                  simulado=sp.simulado.tolist(), resto=sp.resto.tolist(),
                  la_forma_explica=sp.la_forma_explica),
    )
