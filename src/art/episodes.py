"""art.episodes — agrupar residuos extremos en EPISODIOS.

El problema que resuelve
------------------------
Hasta ahora un suceso que dura tres períodos eran tres atípicos sueltos, cada
uno con su forma decidida por separado por una comprobación de adyacencia:

    has_consec = (obs - 1 in ext) or (obs + 1 in ext)
    return "step" if has_consec else "pulse"

Dos formas, elegidas por una regla. Nunca se estimaba una alternativa, así que
la pregunta del análisis de intervención —¿permanente o transitorio?— se
contestaba con una etiqueta heredada de esa regla en vez de con un contraste.

Costaba, medido sobre la réplica de Bolivia: **−16,24 AIC** en PGAS por
encontrar la segunda intervención del episodio 2008-09, y **1 de 8** corridas la
encontró.

Qué hace este módulo
--------------------
Agrupa los extremos separados por un hueco ≤ `ventana` en un EPISODIO, con su
extensión. La ventana es un **parámetro declarado** —no un número mágico
enterrado— y por defecto vale 2, que admite un período tranquilo dentro del
suceso.

Y da la forma general que le corresponde. Por el diccionario de
`docs/DISENO-nodo-intervencion.md` §2.2:

    N escalones consecutivos en el NIVEL con ganancia nula
      ≡ N−1 impulsos en el nivel
      ≡ un episodio de duración N−1

luego un episodio de duración **L** se especifica como **L+1 escalones** en el
nivel a partir de su inicio. Los períodos interiores sin extremo entran igual:
el episodio fija la VENTANA y la estimación decide cuánto pasó en cada período.

Lo que esto disuelve
--------------------
La dicotomía escalón/impulso deja de ser una **regla** y pasa a ser un
**contraste**. Un episodio aislado (L=1) da dos escalones; si ω(1)=0 es un
impulso de nivel (transitorio) y si ω(1)≠0 es un cambio de nivel (permanente),
y quién de las dos cosas es lo dice `interventions.test_intervention`, no una
comprobación de adyacencia.

Espacio de índices — dos conversiones, no una
---------------------------------------------
**La posición.** Se trabaja en el espacio de la serie de RESIDUOS, que es donde
vive `diagnosis.extreme`. La serie de residuos empieza `d + D·s` observaciones
después de la original; `Episodio.at_0based(offset)` hace la conversión, y es la
misma que costó BUG-0030 y BUG-0067.

**La DURACIÓN, que es la otra y se olvida.** Los residuos están diferenciados, y
por el diccionario de arriba **L impulsos en el nivel se ven como L+d extremos
en la serie diferenciada**: dos impulsos de nivel dan tres residuos extremos con
d=1. Así que la duración medida sobre los residuos NO es la duración del suceso:

    duración en el nivel  =  duración en residuos − d

Se descubrió comprobando este módulo de punta a punta: sobre un DGP con dos
impulsos de nivel y d=1, el episodio salía de tres períodos y pedía cuatro
escalones donde hacían falta tres. El defecto tenía la forma exacta de BUG-0030
—«esta función no recibía `d`, así que no podía hacer la conversión aunque
quisiera»— y por eso `agrupa_episodios` la recibe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

__all__ = ["Episodio", "agrupa_episodios", "VENTANA_POR_DEFECTO"]


# Hueco máximo, en períodos, entre dos extremos consecutivos para que
# pertenezcan al mismo suceso. 1 = estrictamente adyacentes; 2 = admite un
# período tranquilo dentro; 3 = admite dos. Declarado aquí y expuesto al
# analista en vez de enterrado en un `if`.
VENTANA_POR_DEFECTO = 2


@dataclass
class Episodio:
    """Un suceso, con los extremos que lo componen y la forma que implica."""

    inicio: int                       # obs 1-based del PRIMER extremo (residuos)
    fin: int                          # obs 1-based del ÚLTIMO extremo
    extremos: list[tuple[int, float]] = field(default_factory=list)
    d: int = 0                        # diferenciación regular del modelo

    @property
    def duracion(self) -> int:
        """Períodos que abarca EN LOS RESIDUOS, extremos incluidos."""
        return self.fin - self.inicio + 1

    @property
    def duracion_nivel(self) -> int:
        """Períodos alterados EN EL NIVEL de la serie — la duración del suceso.

        Los residuos están diferenciados: L impulsos en el nivel se ven como
        L+d extremos. Restar `d` es lo que devuelve el suceso a la escala en la
        que se especifica la intervención y en la que el analista razona.
        """
        return max(self.duracion - self.d, 1)

    @property
    def n_extremos(self) -> int:
        return len(self.extremos)

    @property
    def z_max(self) -> float:
        return max((abs(z) for _, z in self.extremos), default=0.0)

    @property
    def aislado(self) -> bool:
        """Un solo período alterado EN EL NIVEL."""
        return self.duracion_nivel == 1

    @property
    def n_escalones(self) -> int:
        """Escalones en el NIVEL de la forma general: L+1 para un suceso de L.

        `L` es `duracion_nivel`, NO la duración en residuos: contar sobre los
        residuos pedía un escalón de más por cada orden de diferenciación.

        Con ganancia nula equivalen a L impulsos en el nivel — el episodio.
        Con ganancia no nula, a un cambio de nivel permanente. Cuál de las dos
        cosas lo decide el contraste, no esta cuenta.
        """
        return self.duracion_nivel + 1

    @property
    def huecos(self) -> list[int]:
        """Períodos DENTRO del episodio sin residuo extremo."""
        con = {o for o, _ in self.extremos}
        return [p for p in range(self.inicio, self.fin + 1) if p not in con]

    @property
    def cohesion(self) -> float:
        """Fracción de períodos del episodio que tienen extremo. 1,0 = macizo."""
        return self.n_extremos / self.duracion if self.duracion else 0.0

    @property
    def parece_encadenado(self) -> bool:
        """Aviso de que la agrupación puede estar cosiendo cosas distintas.

        Una cadena larga y con muchos huecos es más probable que sea estructura
        no modelizada —estacionalidad, un cambio de régimen— que un suceso. No
        es un veredicto: es una razón para mirar antes de intervenir.
        """
        return self.duracion > 4 or (self.duracion >= 3 and self.cohesion < 0.6)

    def at_0based(self, offset: int = 0) -> int:
        """Índice 0-based EN LA SERIE ORIGINAL donde arranca la intervención.

        `offset` es `d + D·s`, las observaciones que se pierden al diferenciar.
        Sin él la intervención cae ese desfase antes del anómalo que la disparó,
        que es BUG-0030 — y en un mensual con D=1 son trece períodos.
        """
        return self.inicio - 1 + int(offset)

    def __repr__(self) -> str:                              # pragma: no cover
        return (f"Episodio({self.inicio}..{self.fin}, L={self.duracion}, "
                f"n={self.n_extremos}, |z|max={self.z_max:.2f})")


def agrupa_episodios(extreme: Iterable[tuple[int, float]],
                     ventana: int = VENTANA_POR_DEFECTO,
                     d: int = 0) -> list[Episodio]:
    """Agrupa residuos extremos en episodios.

    Parameters
    ----------
    extreme : iterable de `(obs_1based, z)` — `diagnosis.extreme` tal cual,
              en el espacio de la serie de RESIDUOS.
    ventana : hueco máximo entre extremos consecutivos para que sean el mismo
              suceso. `obs_{i+1} − obs_i ≤ ventana` los une.
    d       : diferenciación regular del modelo. Sin ella la duración se lee en
              la escala de los residuos y sale `d` períodos larga — ver la nota
              de arriba sobre las DOS conversiones.

    Returns
    -------
    Lista de `Episodio`, ordenada por posición.

    Notas
    -----
    La unión es por **encadenamiento**: A-B y B-C dentro de ventana ponen A, B y
    C en el mismo episodio aunque A y C estén lejos. Es la lectura natural de
    «el mismo suceso», y por eso el `Episodio` publica `duracion`, `huecos` y
    `cohesion`: para que una cadena larga se vea, en vez de esconderse detrás de
    un solo número.
    """
    if ventana < 1:
        raise ValueError(f"ventana={ventana}: el hueco máximo es al menos 1 "
                         "(extremos adyacentes). Con 0 no se agruparía nada.")

    puntos = sorted({(int(o), float(z)) for o, z in extreme},
                    key=lambda t: t[0])
    if not puntos:
        return []

    episodios: list[Episodio] = []
    actual = [puntos[0]]
    for obs, z in puntos[1:]:
        if obs - actual[-1][0] <= ventana:
            actual.append((obs, z))
        else:
            episodios.append(Episodio(inicio=actual[0][0], fin=actual[-1][0],
                                      extremos=list(actual), d=int(d)))
            actual = [(obs, z)]
    episodios.append(Episodio(inicio=actual[0][0], fin=actual[-1][0],
                              extremos=list(actual), d=int(d)))
    return episodios


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

def describe_episodios(residuals: Sequence[float],
                       episodios: Sequence["Episodio"],
                       ventana: int = VENTANA_POR_DEFECTO,
                       umbral: float = 3.0,
                       offset: int = 0):
    """Enseña la agrupación, que es lo que hay que juzgar en este nodo.

    La pregunta del analista aquí no es «cuántos atípicos hay» sino **«esto es
    un suceso o son varios»**, y ésa sólo se contesta viendo los extremos en su
    sitio con la agrupación encima. La figura sombrea cada episodio sobre los
    residuos tipificados.

    No emite veredicto sobre la forma: dice qué especificación general le
    corresponde a cada episodio y deja el permanente/transitorio al contraste.
    """
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from art.describe import Description, _fig_b64

    z = np.asarray(residuals, dtype=float)
    sd = z.std(ddof=0)
    z = z / sd if sd > 0 else z
    k = np.arange(1, len(z) + 1)

    fig, ax = plt.subplots(figsize=(11, 3.4))
    ax.axhline(0, color="#111", lw=0.8)
    for u in (-umbral, umbral):
        ax.axhline(u, color="#b91c1c", ls="--", lw=0.9)
    ax.plot(k, z, color="#1d4ed8", lw=0.9, marker="o", ms=2.4)
    for i, ep in enumerate(episodios):
        ax.axvspan(ep.inicio - 0.5, ep.fin + 0.5,
                   color="#f59e0b", alpha=0.28, lw=0)
        ax.annotate(f"E{i+1}", (ep.inicio + (ep.duracion - 1) / 2,
                                ax.get_ylim()[1]),
                    ha="center", va="top", fontsize=8, color="#92400e")
    ax.set_xlabel("observación (espacio de RESIDUOS)")
    ax.set_ylabel("z")
    ax.set_title(f"Episodios — ventana {ventana}, umbral |z| > {umbral:g}",
                 fontsize=10)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    b64 = _fig_b64(fig)
    plt.close(fig)

    if not episodios:
        return Description(
            summary="### Episodios\n\nNinguno: no hay residuos extremos que agrupar.",
            figure_b64=b64,
            recommendation="Nada que intervenir por esta vía.",
            data=dict(ventana=ventana, episodios=[]))

    filas = ["| # | tramo (resid.) | dur. resid. | **dur. nivel** | nº extr. "
             "| \\|z\\|máx | cohesión | forma general |",
             "|---|---|---|---|---|---|---|---|"]
    avisos = []
    for i, ep in enumerate(episodios):
        tramo = (f"{ep.inicio}" if ep.aislado else f"{ep.inicio}–{ep.fin}")
        filas.append(f"| E{i+1} | {tramo} | {ep.duracion} | "
                     f"**{ep.duracion_nivel}** | {ep.n_extremos} | "
                     f"{ep.z_max:.2f} | {ep.cohesion:.2f} | "
                     f"**{ep.n_escalones} escalones** en el nivel |")
        if ep.parece_encadenado:
            avisos.append(
                f"- **E{i+1}** abarca {ep.duracion} períodos con "
                f"{len(ep.huecos)} hueco(s) (cohesión {ep.cohesion:.2f}). Una "
                "cadena larga y con huecos es más probable que sea estructura "
                "no modelizada —estacionalidad, un cambio de régimen— que un "
                "suceso. Mira el gráfico antes de intervenirla, o baja la ventana.")

    n_multi = sum(1 for e in episodios if not e.aislado)
    lineas = [
        f"### Episodios — {len(episodios)} con ventana {ventana}",
        "",
        *filas,
        "",
        f"**{n_multi}** de {len(episodios)} duran más de un período." if n_multi
        else "Todos duran un solo período.",
        "",
        "Un episodio de duración **L** se especifica como **L+1 escalones en el "
        "nivel** desde su inicio. Con ganancia ω(1)=0 equivalen a L impulsos en "
        "el nivel —efecto **transitorio**—; con ganancia distinta de cero, a un "
        "cambio de nivel **permanente**. Cuál de las dos cosas lo dice el "
        "contraste, no la forma del grupo.",
    ]
    if avisos:
        lineas += ["", "**Avisos de agrupación:**", *avisos]

    return Description(
        summary="\n".join(lineas),
        figure_b64=b64,
        recommendation=(
            "Juzga la AGRUPACIÓN sobre el gráfico: ¿los sombreados son sucesos "
            "o son varias cosas cosidas? Si no te convence, mueve la ventana "
            f"(ahora {ventana}). Para ver qué forma implica cada episodio, "
            "`simulate_intervention_shape` la dibuja antes de estimar nada."),
        data=dict(
            ventana=ventana, umbral=umbral, offset=offset,
            episodios=[dict(inicio=e.inicio, fin=e.fin, duracion=e.duracion,
                            duracion_nivel=e.duracion_nivel, d=e.d,
                            n_extremos=e.n_extremos, z_max=e.z_max,
                            cohesion=e.cohesion, huecos=e.huecos,
                            n_escalones=e.n_escalones, aislado=e.aislado,
                            parece_encadenado=e.parece_encadenado,
                            at_0based=e.at_0based(offset))
                       for e in episodios]),
    )
