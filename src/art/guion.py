"""Guion de análisis BJ-T — traza completa de versiones del modelo."""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

def cifra(v, fmt: str = ".2f", ausente: str = "—") -> str:
    """Un número del registro, o la marca de que NO CONSTA.

    Desde que un guion escrito por una versión anterior se puede LEER
    (BUG-0098), sus cifras pueden faltar: `loglik`, `bic` y `sigma_a` se
    añadieron después y valen `None` en los registros previos. `None` es lo
    cierto —no consta— pero cualquier `f"{v:.2f}"` revienta con él.

    Es el precio de haber hecho legible lo viejo, y se paga en un solo sitio:
    todo lo que presente una cifra del registro pasa por aquí.
    """
    if v is None:
        return ausente
    try:
        return format(float(v), fmt)
    except (TypeError, ValueError):
        return ausente


def _campos_conocidos(cls, d: dict[str, Any] | None) -> dict[str, Any]:
    """Los campos del dict que la clase entiende hoy, y sólo ésos.

    Un guion es un registro histórico y se lee con el instrumento de HOY, que no
    es el que lo escribió. Puede llevar campos que ya no existen (los descarta) y
    faltarle campos que aún no existían (los pone la clase por defecto). Sin esto
    la lectura revienta con un TypeError y el registro entero queda ilegible
    — 10 entradas del corpus, no por borrado sino por leerlas mal (BUG-0098).

    Lo que se descarta se pierde al reescribir, así que **no reescribas un guion
    leído con una versión más antigua que la que lo escribió**. La lectura es
    segura; la reescritura es la que trunca.
    """
    if not d:
        return {}
    campos = {f.name for f in fields(cls)}
    return {k: v for k, v in d.items() if k in campos}


@dataclass
class GuionStats:
    # Todos con valor por defecto, y es una decisión sobre el REGISTRO, no una
    # comodidad: un guion escrito por una versión anterior de art tiene que
    # seguir abriéndose. `loglik`, `bic` y `sigma_a` se añadieron después, y sin
    # defecto convertían en ilegible todo guion anterior a ellos — 10 entradas
    # del corpus real, perdidas no por borrado sino por un TypeError al leer
    # (BUG-0098). El registro científico no puede caducar con el instrumento.
    #
    # `None` aquí significa NO CONSTA, que es lo cierto, y no cero.
    loglik: float | None = None
    aic: float | None = None
    bic: float | None = None
    sigma_a: float | None = None
    q_pass: bool | None = None
    jb_pass: bool | None = None
    n_extreme: int = 0
    extreme: list[dict[str, Any]] = field(default_factory=list)
    # ── Los DATOS, no sólo el veredicto ─────────────────────────────────
    # El guion guardaba `q_pass`/`jb_pass` como booleanos calculados en el
    # momento de registrar. Cuando el instrumento se corrige —y hoy se corrigió
    # tres veces sobre el mismo estadístico: BUG-0074, BUG-0075, BUG-0077— el
    # registro conserva el veredicto del instrumento VIEJO y el mapa lo presenta
    # sin fecha, como si fuera el estado actual. Sobre ITCER llegó a decir que
    # añadir la media EMPEORABA el ruido blanco.
    #
    # Guardar los p-valores no deshace el problema —el registro sigue siendo
    # histórico, que es lo que un guion es— pero permite RELEERLO: con los
    # retardos, los p-valores y la versión del instrumento se puede saber qué se
    # vio y con qué, y decidir si vuelve a mirarse.
    q_lags: list[int] = field(default_factory=list)
    q_pvalues: list[float] = field(default_factory=list)
    jb_pvalue: float | None = None
    npar: int | None = None          # la corrección de g.l. que se usó
    # ── En qué UNIDADES están ℓ, AIC y BIC ───────────────────────────────
    # La suite estima sobre `refactor`·log(y) (100 por convención, que es lo que
    # hace que σ̂ₐ se lea en tanto por ciento). Un modelo en otra escala tiene
    # una ℓ que difiere en n·ln(refactor) — misma verosimilitud, otras unidades.
    # Sin este campo, la columna del mapa no se puede releer: se apilan cifras
    # que parecen comparables y no lo son (BUG-0085).
    refactor: float | None = None


@dataclass
class GuionEntry:
    version: int
    name: str
    inp_path: str
    timestamp: str
    spec: dict[str, Any]
    stats: GuionStats | None
    equation: str
    decision: str
    rationale: str
    problems_found: str
    next_version: str
    figure_b64: str | None = None
    # BUG-0043: la figura se guarda como fichero HERMANO y aquí sólo va su ruta
    # relativa. Empotrada en base64 ocupaba el 96% del guion —450-735 KB para
    # nueve entradas, con el razonamiento en 7-9 KB— y crecía ~110 KB por
    # modelo. El guion es el registro científico y se carga entero en cada
    # operación del mapa; una figura es DERIVADA (se rehace desde el `.inp`), así
    # que empotrarla es meter caché en el registro. `figure_b64` se conserva para
    # que los guiones ya escritos sigan abriéndose.
    figure_path: str | None = None
    # ── El `.out`, que es un artefacto de PRIMERA CLASE y no un derivado ──
    # La terna comparte basename, así que el `.out` se podría derivar del
    # `inp_path`. Pero derivarlo es SUPONER que está, y esa suposición ya falló:
    # sobre el corpus real 4 de 15 entradas apuntaban a ficheros ausentes
    # (BUG-0092).
    #
    # Y no es un artefacto cualquiera. La covarianza no es una propiedad del
    # óptimo sino un subproducto del camino del optimizador, así que un fichero
    # que sólo guarda el óptimo —el `.pre`— no puede llevarla: **el `.out` es la
    # única constancia fiel de las desviaciones típicas** (BUG-0090, BUG-0091).
    # Una entrada sin `.out` es una entrada cuyos errores típicos no se pueden
    # recuperar sin reestimar, y eso cambia lo que se puede hacer desde ese nodo.
    # Merece un campo, como `figure_path`.
    #
    # El `.pre` NO lo lleva, y es deliberado: es la semilla del paso siguiente,
    # no algo que se relea, y derivarlo por nombre basta.
    out_path: str | None = None
    #: El histograma de residuos, hermano de `figure_path`. La diagnosis de esta
    #: escuela son TRES cosas —residuos, ACF/PACF e histograma— y el
    #: Jarque-Bera se lee sobre la tercera. `describe_diagnosis` las genera todas
    #: y sólo se guardaba la combinada, así que al volver a un nodo faltaba
    #: justo la que sostiene el veredicto de normalidad.
    hist_path: str | None = None

    # ── El nodo de decisión, que no es un modelo ──────────────────────────
    # Un guion que sólo registra MODELOS empieza a contar la historia tarde.
    # Para cuando existe el primer modelo estimado ya se ha decidido λ, se ha
    # decidido d, se ha decidido si hay estacionalidad y de qué tipo, y se han
    # elegido los órdenes — y ninguna de esas decisiones deja rastro. Sobre
    # PGAS la divergencia entera entre los dos carriles está en λ, que se
    # decide ANTES del primer modelo: el guion no podía enseñarla.
    #
    # `kind` distingue las dos cosas que viven en la misma cadena:
    #   "model" — un modelo estimado, con su `.inp`, su ecuación y su diagnosis.
    #   "node"  — una decisión de especificación, sin fichero ni diagnosis.
    # Van en UNA lista y no en dos porque el orden en que ocurrieron ES la
    # información: un nodo después de un modelo es una REFORMULACIÓN, y eso
    # sólo se ve si están intercalados.
    #
    # `decided_by` es lo que hace comparables dos guiones. El protocolo es el
    # mismo en los dos carriles y los nodos son los mismos; lo único que cambia
    # es quién decidió cada uno. Sin este campo, dos guiones son dos listas
    # parecidas; con él, son el mismo recorrido con distinto decisor, que es
    # exactamente lo que se quiere contrastar.
    kind: str = "model"                # model | node
    node: dict[str, Any] | None = None  # {nodo, decidido, evidencia, alternativas}
    decided_by: str = ""               # "analista+LLM" | "LLM" | "heurística"

    # ── El mapa del laberinto ────────────────────────────────────────────
    # Sin estos tres campos el guion es un REGISTRO: dice dónde se ha estado,
    # en una lista. Con ellos es un MAPA: dice de qué versión desciende cada
    # versión, cuáles se adoptaron y cuáles fueron callejón sin salida.
    #
    # El método es una búsqueda iterativa con vuelta atrás, no un descenso por
    # un árbol de decisión. Sus callejones no son fallos del método: son el
    # método funcionando. Y lo que una iteración fallida produce de valor NO es
    # el modelo que se descarta, es la RAZÓN por la que se descarta — que es lo
    # único que impide volver a intentarlo. `why_abandoned` es ese registro.
    #
    # Los tres llevan valor por defecto para que los guiones ya escritos sigan
    # cargando: un guion antiguo se lee como una cadena lineal sin abandonos.
    parent: int | None = None
    status: str = "exploring"          # exploring | adopted | dead-end
    why_abandoned: str = ""

    # ── LA ITERACIÓN ──────────────────────────────────────────────────────
    # El método es iterativo y sus etapas están dadas: especificación inicial,
    # estimación por MVENC, diagnosis, reformulación. Una iteración es UNA
    # vuelta por las cuatro: lleva una semilla y se mueve en una dirección, y
    # termina en un informe y una decisión.
    #
    # El guion registraba las cuatro etapas y no registraba la vuelta. Sin este
    # campo, «¿cuántas iteraciones tuvo este análisis?» tiene tres respuestas
    # defendibles sobre el mismo corpus —una por entrada, una por modelo, una
    # por nodo— y el código no elige ninguna. Con él tiene una.
    #
    # La regla: un MODELO estimado cierra una iteración y se lleva el número.
    # Los NODOS de decisión que lo preceden llevan ESE MISMO número, porque son
    # su etapa 1 — no son iteraciones aparte. Por eso un nodo puede contener
    # varias iteraciones (medido: hasta 9) y una iteración no puede contener
    # varios nodos.
    iteracion: int | None = None
    #: CÓMO se supo el padre. Es la diferencia entre un mapa y una conjetura:
    #:
    #:   "declarado" — el llamante dijo de qué `.pre` encadenaba;
    #:   "inferido"  — se tomó la última entrada del guion porque nadie lo dijo.
    #:
    #: Un padre inferido puede ser falso, y `guion_abandon` arrastra a los
    #: descendientes POR DISEÑO: sobre un linaje inventado, marcar un callejón
    #: correcto barre la rama viva (BUG-0108). Distinguirlos permite avisar antes
    #: de hacer daño, en vez de exigir que el analista lo recuerde.
    parent_origen: str = ""

    #: A qué nodo del protocolo sirve esta iteración (`lambda`, `d`,
    #: `estacionalidad`, `ordenes`, `intervenciones`…). En las entradas de tipo
    #: `node` es el nodo que se decide; en las de tipo `model`, el nodo abierto
    #: cuando se estimó.
    nodo: str = ""

    # ── La semilla: de dónde SALIÓ esta versión ───────────────────────────
    # `infer_parent` ya recibía el `.pre` desde el que se encadenó, lo usaba
    # para decidir el padre... y lo tiraba. El resultado es que el campo que
    # DETERMINA el parentesco no queda en el registro: sobre el corpus real, 0
    # de 1.306 entradas lo llevan. Se puede leer de quién desciende un nodo,
    # pero no comprobarlo, porque el dato con el que se dedujo ya no está.
    #
    # Y no es sólo auditoría del padre. Un `.pre` de partida es la mitad de la
    # ESPECIFICACIÓN de una iteración: dice qué se daba por estimado al empezar
    # —los armónicos, la media— frente a qué se estimó de nuevo. Dos entradas
    # con la misma spec y distinta semilla son dos iteraciones distintas, y sin
    # este campo se leen como la misma.
    #
    # Con `spec` ya completa, éste es el campo que faltaba para que una entrada
    # diga de dónde vino Y a dónde llegó.
    base_pre_path: str = ""

    # Con QUÉ instrumento se calculó lo de arriba. Un guion sin esto no se puede
    # releer: no hay forma de saber si un veredicto viene de una versión con un
    # defecto ya corregido. Y es lo que hace comparables —o no— dos guiones de
    # runs distintos.
    instrumento: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GuionEntry":
        d = _campos_conocidos(cls, d)
        stats_d = d.pop("stats", None)
        # Un nodo de decisión no tiene diagnosis: no hay modelo que diagnosticar.
        stats = GuionStats(**_campos_conocidos(GuionStats, stats_d)) if stats_d else None
        return cls(stats=stats, **d)

    @property
    def is_node(self) -> bool:
        return self.kind == "node"


@dataclass
class Guion:
    series: str
    analyst: str
    created: str
    entries: list[GuionEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "series": self.series,
            "analyst": self.analyst,
            "created": self.created,
            "entries": [e.to_dict() for e in self.entries],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Guion":
        entries = [GuionEntry.from_dict(e) for e in d.get("entries", [])]
        return cls(
            series=d.get("series", ""),
            analyst=d.get("analyst", ""),
            created=d.get("created", ""),
            entries=entries,
        )


# ---------------------------------------------------------------------------
# El mapa: parentesco, ramas y callejones
# ---------------------------------------------------------------------------

def infer_parent(guion: "Guion", base_pre_path: str = "") -> int | None:
    """De qué versión desciende la que se está registrando.

    Dos casos, y el orden importa:

    1. Se encadenó desde un `.pre` concreto (`base_pre_path`): el padre es la
       versión que produjo ESE fichero. Es el caso exacto y hay que probarlo
       primero, porque encadenar desde una versión antigua es precisamente
       VOLVER ATRÁS — y si se ignora, una vuelta atrás queda registrada como si
       fuese el paso siguiente de la última rama, que es la mentira que borra
       el mapa.
    2. No se encadenó: el padre es la última versión registrada. La cadena
       lineal es el caso corriente y no hay que hacerla explícita.

    Devuelve None sólo para la primera versión del guion.
    """
    if not guion.entries:
        return None
    if base_pre_path:
        import os
        objetivo = os.path.splitext(os.path.abspath(os.path.expanduser(base_pre_path)))[0]
        for e in reversed(guion.entries):
            if os.path.splitext(os.path.abspath(e.inp_path))[0] == objetivo:
                return e.version
    return guion.entries[-1].version


def descendants(guion: "Guion", version: int) -> list[int]:
    """Versiones que cuelgan de `version`, directa o indirectamente."""
    fuera, frontera = [], [version]
    while frontera:
        v = frontera.pop()
        for e in guion.entries:
            if e.parent == v and e.version not in fuera:
                fuera.append(e.version)
                frontera.append(e.version)
    return sorted(fuera)


def abandon(guion: "Guion", version: int, why: str,
            cascade: bool = True) -> list[int]:
    """Marcar una versión como callejón sin salida, CON SU RAZÓN.

    `why` no es opcional por diseño: un callejón sin razón anotada no evita que
    se vuelva a entrar en él, que es la única cosa para la que sirve marcarlo.

    Con `cascade`, todo lo que desciende del callejón queda marcado también —
    porque una decisión contaminada contamina lo que viene después, y ésa es la
    propiedad que hace que haya que volver atrás en lugar de seguir parcheando.

    **Los NODOS de decisión no se abandonan: se recolocan (BUG-0037).** Un nodo
    es un argumento escrito, y el argumento que suele venir justo detrás de un
    modelo fallido es precisamente *el que lo condena* — "lo probé, ω sale con
    t=1,66, me quedo con el anterior". Ese nodo no desciende del fallo: es la
    conclusión que se saca de él, y pertenece al tronco que sobrevive. La cascada
    lo barría porque `guion_node` lo había encadenado a la última entrada, que
    era el callejón.

    Y barrerlo es lo contrario de lo que el mapa existe para hacer. Lo que una
    iteración fallida produce de valor no es el modelo que se tira: es la razón,
    y marcar la razón como callejón la borra del tronco justo cuando más falta
    hace. Así que un nodo alcanzado por la cascada se re-encadena al lugar seguro
    más cercano y conserva su estado.

    Devuelve `(abandonadas, recolocadas)`.
    """
    if not why or not why.strip():
        raise ValueError(
            "abandon() exige una razón: un callejón sin anotar por qué lo es no "
            "impide volver a entrar, que es para lo único que sirve marcarlo.")
    por_v = {e.version: e for e in guion.entries}
    alcanzadas = [version] + (descendants(guion, version) if cascade else [])

    # El destino de los nodos recolocados: el primer ancestro NO alcanzado.
    destino = por_v[version].parent if version in por_v else None
    while destino is not None and destino in alcanzadas:
        destino = por_v[destino].parent

    # BUG-0058 (a). Recolocar un NODO lo saca de la cascada, pero sus
    # descendientes ya estaban recogidos en `alcanzadas` y se abandonaban igual.
    # Después de recolocarlo cuelgan de `destino`, que está vivo, así que ya no
    # descienden del callejón y no hay nada que los condene. Se podan con él.
    #
    # Es el caso que se observó: una rama con `parent` apuntando a un NODO de
    # decisión quedó marcada aunque ese nodo se había re-encadenado al tronco.
    a_podar = set()
    for v in alcanzadas:
        e = por_v.get(v)
        if e is not None and v != version and getattr(e, "kind", "model") == "node":
            a_podar.update(descendants(guion, v))
    alcanzadas = [v for v in alcanzadas if v not in a_podar]

    abandonadas, recolocadas = [], []
    for v in alcanzadas:
        e = por_v.get(v)
        if e is None:
            continue
        if v != version and getattr(e, "kind", "model") == "node":
            e.parent = destino
            recolocadas.append(v)
            continue

        # BUG-0058 (b). `why_abandoned` se sobrescribía SIEMPRE, así que
        # abandonar una versión pisaba la razón de todo callejón anterior que la
        # cascada volviera a tocar. Se observó con cuatro versiones llevando
        # literalmente el mismo texto. Y borrar esa razón es exactamente lo
        # contrario de para lo que sirve marcar un callejón: la propia docstring
        # dice que sin ella no se evita volver a entrar.
        #
        # Una razón escrita NO SE PISA. Y la de un descendiente no es la del
        # ancestro: es que su ancestro cayó, y así se dice.
        if v == version:
            e.why_abandoned = why.strip()
        else:
            heredada = f"Arrastrado por el callejón de v{version}: {why.strip()}"
            previa = (getattr(e, "why_abandoned", "") or "").strip()
            if previa and previa != heredada:
                # conserva lo suyo y anota la herencia, sin perder ninguna de las dos
                e.why_abandoned = f"{previa}\n[Además: {heredada}]"
            else:
                e.why_abandoned = heredada
        e.status = "dead-end"
        abandonadas.append(v)
    return sorted(abandonadas), sorted(recolocadas)


def safe_ancestor(guion: "Guion", version: int | None = None) -> int | None:
    """El lugar seguro más cercano: subiendo, la primera versión no abandonada.

    Es la operación de «volver» del laberinto. Desde donde se esté, ¿cuál es el
    último punto cuyas decisiones seguían siendo buenas?
    """
    por_v = {e.version: e for e in guion.entries}
    if version is None:
        version = guion.entries[-1].version if guion.entries else None
    while version is not None:
        e = por_v.get(version)
        if e is None:
            return None
        if e.status != "dead-end":
            return e.version
        version = e.parent
    return None


def path_to_root(guion: "Guion", version: int) -> list[int]:
    """La cadena de decisiones que llevó hasta `version`, de la raíz hacia acá."""
    por_v = {e.version: e for e in guion.entries}
    cadena, v = [], version
    while v is not None and v in por_v:
        cadena.append(v)
        v = por_v[v].parent
    return list(reversed(cadena))


# ---------------------------------------------------------------------------
# Los nodos de decisión, y el contraste entre dos recorridos
# ---------------------------------------------------------------------------

# El orden canónico del protocolo BJ-T. Sirve para dos cosas: alinear dos
# guiones que recorrieron los mismos nodos, y detectar los que uno de los dos
# ni siquiera visitó — que es un hallazgo, no un hueco.
NODOS_CANONICOS = [
    "dominio", "lambda", "estacionalidad", "d", "ordenes",
    "media", "intervenciones", "reformulacion",
]


def nodes(guion: "Guion") -> list["GuionEntry"]:
    """Sólo los nodos de decisión, en el orden en que se tomaron."""
    return [e for e in guion.entries if getattr(e, "kind", "model") == "node"]


def models(guion: "Guion") -> list["GuionEntry"]:
    """Sólo los modelos estimados."""
    return [e for e in guion.entries if getattr(e, "kind", "model") != "node"]


def _clave(e: "GuionEntry") -> str:
    nd = e.node or {}
    return str(nd.get("nodo", e.name) or "").strip().lower()


def diff_nodes(a: "Guion", b: "Guion",
               etiqueta_a: str = "A", etiqueta_b: str = "B") -> list[dict[str, Any]]:
    """Contrasta dos recorridos NODO A NODO, con el razonamiento de cada uno.

    Por qué esta función y no una tabla de resultados: comparar dos modelos
    finales dice QUE difieren; comparar dos recorridos dice DÓNDE y POR QUÉ, y
    esa es la única comparación de la que se aprende algo. Un modelo peor cuya
    cadena de decisiones se entiende enseña más que uno mejor que salió de una
    caja.

    El emparejamiento es por NOMBRE de nodo, no por posición: dos recorridos
    pueden visitar los mismos nodos en distinto orden, o uno puede volver sobre
    un nodo que el otro decidió una sola vez —que es precisamente lo que hace
    ITERATIVO al método— y alinear por posición convertiría eso en ruido. Cuando
    un nodo se visita más de una vez se comparan en orden de visita, porque la
    segunda visita a `lambda` es una reformulación y no la misma decisión.

    Devuelve una lista de dicts con: nodo, valor y razón de cada lado, quién
    decidió en cada lado, y `veredicto` ∈ {coinciden, divergen, sólo A, sólo B}.
    """
    from collections import defaultdict

    def indexa(g):
        por_nodo = defaultdict(list)
        for e in nodes(g):
            por_nodo[_clave(e)].append(e)
        return por_nodo

    ia, ib = indexa(a), indexa(b)
    orden = [n for n in NODOS_CANONICOS if n in ia or n in ib]
    orden += sorted((set(ia) | set(ib)) - set(orden))

    filas: list[dict[str, Any]] = []
    for nombre in orden:
        ea_list, eb_list = ia.get(nombre, []), ib.get(nombre, [])
        for i in range(max(len(ea_list), len(eb_list))):
            ea = ea_list[i] if i < len(ea_list) else None
            eb = eb_list[i] if i < len(eb_list) else None
            va = (ea.node or {}).get("decidido") if ea else None
            vb = (eb.node or {}).get("decidido") if eb else None
            if ea is None:
                veredicto = f"sólo {etiqueta_b}"
            elif eb is None:
                veredicto = f"sólo {etiqueta_a}"
            else:
                veredicto = "coinciden" if str(va) == str(vb) else "divergen"
            filas.append({
                "nodo": nombre + (f" (visita {i+1})" if max(len(ea_list), len(eb_list)) > 1 else ""),
                "valor_a": va, "valor_b": vb,
                "razon_a": ea.rationale if ea else "",
                "razon_b": eb.rationale if eb else "",
                "evidencia_a": (ea.node or {}).get("evidencia", "") if ea else "",
                "evidencia_b": (eb.node or {}).get("evidencia", "") if eb else "",
                "decidio_a": ea.decided_by if ea else "",
                "decidio_b": eb.decided_by if eb else "",
                "veredicto": veredicto,
            })
    return filas


# ---------------------------------------------------------------------------
# La iteración: la unidad del método
# ---------------------------------------------------------------------------

@dataclass
class Iteracion:
    """Una vuelta por las cuatro etapas, con todo lo que la identifica.

    No es un envoltorio de presentación: es la unidad que se cuenta, se compara
    entre dos recorridos y se cita. `envuelve_iteracion` PRESENTA una; esto la
    IDENTIFICA.
    """
    numero: int
    nodo: str = ""
    #: Etapa 1. Las decisiones de especificación que la preceden.
    especificacion: list[GuionEntry] = field(default_factory=list)
    #: Etapas 2-3. El modelo estimado y diagnosticado. `None` = iteración
    #: especificada y no estimada todavía.
    modelo: GuionEntry | None = None

    @property
    def semilla(self) -> str:
        """El `.pre` de partida. Con la dirección, es lo que la define."""
        return (self.modelo.base_pre_path if self.modelo else "") or ""

    @property
    def decision(self) -> str:
        """Etapa 4. Toda iteración termina en una."""
        if self.modelo and self.modelo.decision:
            return self.modelo.decision
        return "; ".join(e.decision for e in self.especificacion if e.decision)

    @property
    def cerrada(self) -> bool:
        return self.modelo is not None

    @property
    def estado(self) -> str:
        return self.modelo.status if self.modelo else "sin estimar"


def numera_iteraciones(guion: "Guion") -> None:
    """Pone `iteracion` y `nodo` a cada entrada, en su sitio.

    Es una DERIVACIÓN, no una invención: el orden de las entradas ya lleva la
    información y esto sólo la hace explícita. Por eso se puede aplicar a los
    guiones ya escritos sin tocar un byte de lo que dicen.

    Sólo rellena lo que falta. Un número ya escrito manda sobre el derivado: si
    alguna vez la numeración de escritura y la derivada discrepan, la que vale
    es la que se registró cuando ocurrió.
    """
    n = 0
    nodo_actual = ""
    for e in guion.entries:
        if e.is_node:
            nodo_actual = (e.node or {}).get("nodo") or e.name or nodo_actual
            if e.iteracion is None:
                e.iteracion = n + 1     # es la etapa 1 de la que viene
            if not e.nodo:
                e.nodo = nodo_actual
        else:
            n += 1
            if e.iteracion is None:
                e.iteracion = n
            if not e.nodo:
                e.nodo = nodo_actual


def iteraciones(guion: "Guion") -> list[Iteracion]:
    """Las iteraciones del recorrido, en orden."""
    numera_iteraciones(guion)
    por_num: dict[int, Iteracion] = {}
    for e in guion.entries:
        k = int(e.iteracion or 0)
        it = por_num.setdefault(k, Iteracion(numero=k, nodo=e.nodo))
        if e.is_node:
            it.especificacion.append(e)
            if not it.nodo:
                it.nodo = e.nodo
        else:
            it.modelo = e
            it.nodo = e.nodo or it.nodo
    return [por_num[k] for k in sorted(por_num)]


def modelos_sin_registrar(guion: "Guion", guion_path: str) -> list[str]:
    """Ternas que hay en la carpeta del guion y NO están en el guion.

    El registro no tenía forma de saberse incompleto, y se sabe incompleto de
    verdad. Caso UEM_FOOD_SERV_DS, que salió bien y fue difícil: 13 modelos con
    terna completa en disco, 9 en el guion. El guion deja de escribirse a las
    19:04 y el análisis sigue hasta las 21:06 — y el modelo FINAL, `m11_fact`,
    es uno de los que faltan. El registro se quedó con el subcampeón: AIC −41,13
    frente a −44,77, BIC 29,75 frente a 19,36.

    Esto no lo impide —una herramienta que escribe un `.inp` sin registrar lo
    seguirá haciendo— pero lo hace VISIBLE, que es lo que faltaba. Se mira sólo
    lo que tiene `.out`: un `.inp` sin estimar no es una iteración.
    """
    carpeta = os.path.dirname(os.path.abspath(os.path.expanduser(guion_path)))
    try:
        ficheros = sorted(os.listdir(carpeta))
    except OSError:
        return []
    registrados = set()
    for e in guion.entries:
        if e.inp_path:
            registrados.add(os.path.splitext(os.path.basename(e.inp_path))[0])
    sueltos = []
    for f in ficheros:
        raiz, ext = os.path.splitext(f)
        if ext != ".inp" or raiz in registrados:
            continue
        if os.path.exists(os.path.join(carpeta, raiz + ".out")):
            sueltos.append(os.path.join(carpeta, f))
    return sueltos


#: Tipos deterministas que son ESTRUCTURA estacional, no sucesos. `_extract_spec`
#: no los guarda como intervenciones —van en `n_harmonics` y en `alter`— así que
#: tampoco se cuentan al reconciliar.
_ESTRUCTURALES = ("cos", "sin", "alter")


def _deterministas_del_inp(ruta: str) -> list[str]:
    """Los deterministas NO estructurales que declara un `.inp`, leyendo el
    fichero — sin motor, sin estimar y sin cargar el modelo.

    Se lee el texto a propósito: esto se llama una vez por entrada al dibujar el
    mapa, e instanciar el modelo de cada una costaría el doble de lo que cuesta
    el mapa entero.
    """
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            lineas = fh.read().splitlines()
    except OSError:
        return []
    for i, ln in enumerate(lineas):
        if "Number of deterministic" not in ln:
            continue
        try:
            n = int(lineas[i + 1].strip())
        except (ValueError, IndexError):
            return []
        nombres = []
        j = i + 2
        while j < len(lineas) and len(nombres) < n:
            t = lineas[j].strip()
            if t and not t.startswith("*"):
                nombres.append(t.split()[0])
            j += 1
        return [x for x in nombres if x not in _ESTRUCTURALES]
    return []


def entradas_que_no_cuadran(guion: "Guion") -> list[tuple]:
    """Entradas cuyo registro CONTRADICE el fichero al que apuntan.

    El guion es el registro científico y su `.inp` es la evidencia. Que discrepen
    no es un descuadre de formato: es que lo que se lee en el mapa no es lo que
    se estimó, y nadie se entera.

    Medido sobre el corpus —616 entradas-modelo con su fichero en disco— hay
    **una**: `b02_covid_auto` declara UNA intervención y su `.inp` lleva CUATRO;
    las tres que se pierden son las que venía arrastrando de su padre. La entrada
    está marcada como callejón sin salida, así que la pérdida no contaminó nada
    aguas abajo — esta vez.

    No se ha podido reproducir con el código de hoy: `_extract_spec` sobre ese
    mismo fichero devuelve las cuatro, y la ruta `form="auto"` de extremo a
    extremo las registra todas. Puede que ya esté arreglado y puede que no. Por
    eso esto no es un arreglo sino un DETECTOR: la comprobación cuesta una
    lectura de texto por entrada y convierte un fallo que no sé reproducir en uno
    que no puede pasar desapercibido (BUG-0102).

    Devuelve `(version, nombre, n_en_el_fichero, n_en_el_registro)`.
    """
    fuera = []
    for e in guion.entries:
        if e.is_node or not e.inp_path or not os.path.exists(e.inp_path):
            continue
        registradas = (e.spec or {}).get("interventions")
        if registradas is None:          # spec vieja: no afirmaba nada
            continue
        en_fichero = _deterministas_del_inp(e.inp_path)
        if len(en_fichero) != len(registradas):
            fuera.append((e.version, e.name, len(en_fichero), len(registradas)))
    return fuera


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

#: Campos de `GuionEntry` que apuntan a un fichero de la terna y por tanto se
#: guardan ABSOLUTOS. `figure_path` y `hist_path` NO están aquí a propósito: son
#: hermanos del propio guion (viven en `figs/` a su lado) y viajan con él.
CAMPOS_DE_RUTA = ("inp_path", "out_path")


def _resuelve_ruta(ruta: str, base: str) -> str:
    """Un camino relativo del guion, resuelto contra la carpeta del guion.

    Los guiones guardaban el camino tal como se lo pasaron, y a la herramienta
    se lo pasaban relativo al directorio de trabajo de aquel día. Medido sobre
    el corpus: de 629 entradas con `inp_path`, 189 apuntaban a un fichero
    inexistente — y **las 189 eran relativas, ninguna absoluta**. No se había
    borrado nada; el guion había viajado y el cwd no.

    De esas 189, **188 resuelven contra la carpeta del propio guion**. La
    evidencia estaba donde siempre y el registro sabía dónde: lo que fallaba era
    el origen desde el que se leía el camino.

    Sólo se reescribe cuando el camino guardado NO existe y el resuelto SÍ, así
    que no puede robarle el sitio a un fichero que esté donde dice.
    """
    # LO QUE DECIDE ES SI EXISTE, no si PARECE absoluto.
    #
    # Aquí había un `os.path.isabs(ruta)` que cortocircuitaba, y estaba mal en
    # el caso que más importa: **el mismo Dropbox abierto en otro sistema**.
    # `ntpath.isabs("/home/david/…")` es True en Windows, así que un guion
    # escrito en Linux —y desde BUG-0098 sus caminos son absolutos— llegaba
    # aquí, se declaraba «absoluto», se devolvía tal cual y quedaba muerto: el
    # rescate no llegaba a probarse.
    #
    # El basename contra la carpeta del guion resuelve ese caso, que es
    # exactamente para lo que existe esta función: la evidencia viaja CON el
    # guion, en su misma carpeta, se llame como se llame el punto de montaje.
    if not ruta or os.path.exists(ruta):
        return ruta
    for cand in (os.path.join(base, ruta),
                 os.path.join(base, os.path.basename(ruta.replace("\\", "/")))):
        if os.path.exists(cand):
            return os.path.abspath(cand)
    return ruta


def load_guion(path: str) -> Guion:
    with open(path, encoding="utf-8") as f:
        g = Guion.from_dict(json.load(f))
    base = os.path.dirname(os.path.abspath(os.path.expanduser(path)))
    for e in g.entries:
        for campo in CAMPOS_DE_RUTA:
            v = getattr(e, campo, "") or ""
            if v:
                setattr(e, campo, _resuelve_ruta(v, base))
    # Los guiones ya escritos no llevan número de iteración: se DERIVA del orden,
    # que ya lo contiene. No se reescribe nada por leerlo.
    numera_iteraciones(g)
    return g


def save_guion(guion: Guion, path: str) -> None:
    """Se escribe con los caminos ABSOLUTOS, que es la otra mitad del arreglo.

    Resolver al leer rescata los guiones ya escritos; guardar absoluto impide
    que vuelva a ocurrir. Se absolutiza únicamente lo que EXISTE en el momento
    de escribir: un camino que no se puede comprobar se deja tal cual, porque
    convertirlo a absoluto contra este cwd sería inventar una ubicación —
    exactamente el error que se está corrigiendo, con otro disfraz.
    """
    # Se numera aquí y no en cada llamante: así toda escritura queda con su
    # iteración estampada, la de hoy y la que se añada mañana. Al leer se vuelve
    # a derivar sólo lo que falte, de modo que un número escrito manda sobre el
    # derivado — que es lo correcto: lo estampó quien estaba allí.
    numera_iteraciones(guion)
    dest = os.path.dirname(os.path.abspath(path))
    os.makedirs(dest, exist_ok=True)
    d = guion.to_dict()
    for e in d.get("entries", []):
        for campo in CAMPOS_DE_RUTA:
            v = e.get(campo) or ""
            if not v or os.path.isabs(v):
                continue
            for cand in (v, os.path.join(dest, v),
                         os.path.join(dest, os.path.basename(v))):
                if os.path.exists(cand):
                    e[campo] = os.path.abspath(cand)
                    break
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Spec / stats extraction
# ---------------------------------------------------------------------------

#: Tipos deterministas que NO son sucesos: son variables de calendario
#: definidas sobre TODA la muestra. Su `at` es un relleno —vale 0— y no una
#: fecha.
SIN_FECHA = ("easter", "trend")


def _det_a_spec(i, sy: int, sp: int, freq: int) -> dict:
    """Una intervención, como la guarda el guion.

    Un `easter` con `"date": "01/2005"` es un REGISTRO FALSO: dice que hubo un
    suceso en enero de 2005 y no lo hubo. El efecto de Semana Santa es un
    regresor de calendario sobre toda la serie, y ese 01/2005 era el `at=0` del
    relleno convertido en fecha por el mero hecho de pasar por la misma función.
    Misma clase que la λ tomada del argumento: un dato inventado en el registro
    que se lee después como si constara.
    """
    d = {"type": i.type}
    if i.type not in SIN_FECHA:
        d["date"] = _at_to_date(i.at, sy, sp, freq)
    return d


def _at_to_date(at: int, start_year: int, start_per: int, freq: int) -> str:
    """Convert 0-based observation index to a date string (MM/YYYY or QN/YYYY or YYYY)."""
    if freq == 12:
        total = (start_per - 1) + at
        month = total % 12 + 1
        year  = start_year + total // 12
        return f"{month:02d}/{year}"
    elif freq == 4:
        total = (start_per - 1) + at
        q    = total % 4 + 1
        year = start_year + total // 4
        return f"Q{q}/{year}"
    else:
        return str(start_year + at)


def _extract_spec(model, lam: float) -> dict[str, Any]:
    """Build spec dict from a fue.Model instance."""
    p = len(model.ar[0]) if model.ar else 0
    q = len(model.ma[0]) if model.ma else 0
    P = len(model.ar_s[0]) if model.ar_s else 0
    Q = len(model.ma_s[0]) if model.ma_s else 0

    itv = model.interventions or []
    n_harmonics = sum(1 for i in itv if i.type == "cos")

    freq = model.series.freq if model.series else 12
    sy, sp = (model.series.start if model.series else (2000, 1))

    other_itvs = [
        _det_a_spec(i, sy, sp, freq)
        for i in itv
        if i.type not in ("cos", "sin", "alter")
    ]

    # ── LO QUE FALTABA, Y HACÍA QUE LA SPEC NO DETERMINARA EL MODELO ──────
    #
    # Hallazgo #3 de una revisión con contexto limpio. Medido sobre 81 guiones:
    # de 50 pares con spec idéntica **carácter a carácter**, 48 tenían ℓ
    # distinta —mediana Δℓ = 4,87, máximo 57,88—. No eran revisitas: era una
    # spec que no distinguía modelos separados por 57 puntos de verosimilitud.
    #
    # Abriendo los pares contra el motor, lo que los separaba era siempre uno
    # de tres, y los tres se caían aquí:
    #
    #   ar_free / ma_free   las banderas libre/fijo — 21 pares
    #   estimate_mu / mu    la media                — 19 pares
    #   el `alter` de Nyquist                       —  5 pares
    #
    # La consecuencia no es cosmética. Sin esto **no hay identidad de estado
    # definible**, y sin identidad de estado no hay lista cerrada posible: una
    # construida con la clave vieja declararía a `m01` una revisita de `m00` y
    # podaría el modelo bueno — 37,6 puntos de AIC en el caso medido.
    #
    # Y `guion_diff`, que compara dos recorridos nodo a nodo, comparaba specs
    # que no determinan modelos.
    def _banderas(factores, libres):
        """Las banderas por factor, en la forma en que `fue` las guarda."""
        if not factores:
            return []
        if libres is None:
            return [[True] * len(f) for f in factores]
        return [list(x) if isinstance(x, (list, tuple)) else [bool(x)]
                for x in libres]

    # El `alter` es el armónico de Nyquist —la frecuencia π, el (−1)ᵗ— y es un
    # término de la parte determinista como cualquier otro. Se filtraba de
    # `other_itvs` por no ser un suceso, y con eso desaparecía del registro.
    tiene_alter = any(i.type == "alter" for i in itv)

    return {
        "lam": lam,
        "d": model.d,
        "D": model.D,
        # La media: `mu` sin `estimate_mu` no dice nada — un μ=0 fijo y un μ=0
        # estimado son modelos distintos con un parámetro de diferencia.
        "mu": float(getattr(model, "mu", 0.0) or 0.0),
        "estimate_mu": bool(getattr(model, "estimate_mu", False)),
        "alter": tiene_alter,
        "ar_free": _banderas(model.ar, getattr(model, "ar_free", None)),
        "ma_free": _banderas(model.ma, getattr(model, "ma_free", None)),
        "ar_s_free": _banderas(model.ar_s, getattr(model, "ar_s_free", None)),
        "ma_s_free": _banderas(model.ma_s, getattr(model, "ma_s_free", None)),
        # BUG-0051. `ifadf` --la diferenciación POR FRECUENCIA-- se caía aquí, y
        # con ella de todo lo que use el spec: la ecuación, el diff de versiones
        # y la detección de anidamiento. Es tanto una transformación de los datos
        # como la D: con ifadf=[0,1,0] el modelo no explica ∇ln y sino
        # (1+B²)∇ln y, otra variable dependiente y otro tamaño muestral efectivo.
        "ifadf": list(model.ifadf or []),
        "p": p,
        "q": q,
        "P": P,
        "Q": Q,
        "n_harmonics": n_harmonics,
        "interventions": other_itvs,
    }


def _extract_stats(model, diag_result) -> GuionStats:
    """Build GuionStats from a fitted fue.Model and its DiagnosisResult."""
    r = model._result
    sigma_a = math.sqrt(r.sigma2) if r.sigma2 and r.sigma2 > 0 else 0.0

    # extreme: list of (obs_1based, z) from DiagnosisResult
    n_orig = len(model.series.data)
    n_res  = len(r.residuals)
    offset = n_orig - n_res   # observations removed by differencing / AR init
    s = model.series.freq

    extreme_list = []
    for obs1, z in diag_result.extreme:
        t0 = offset + obs1 - 1    # 0-based in original series
        try:
            yr, per = model.series._obs_to_date(t0 + 1)
            if s == 12:
                date_str = f"{per:02d}/{yr}"
            elif s == 4:
                date_str = f"Q{per}/{yr}"
            else:
                date_str = str(yr)
        except Exception:
            date_str = str(obs1)
        extreme_list.append({"obs": int(obs1), "date": date_str, "z": float(z)})

    return GuionStats(
        loglik=float(r.loglik),
        aic=float(r.aic) if r.aic is not None else None,
        bic=float(r.bic) if r.bic is not None else None,
        sigma_a=sigma_a,
        q_pass=diag_result.white_noise,
        jb_pass=diag_result.normal,
        n_extreme=len(extreme_list),
        extreme=extreme_list,
        q_lags=[int(x) for x in (diag_result.q_lags or [])],
        q_pvalues=[float(x) for x in (diag_result.q_pvalues or [])],
        jb_pvalue=float(diag_result.jb_pvalue),
        npar=int(diag_result.npar),
        refactor=float(getattr(model, "refactor", None) or 1.0),
    )


def version_instrumento() -> str:
    """Con qué se calculó: versión de `art`, commit, y si el árbol estaba sucio.

    Un guion sin esto no se puede releer — no hay forma de saber si un veredicto
    viene de una versión con un defecto ya corregido.

    Dos trampas que hay que esquivar, y las dos aparecieron al escribir esto:

    **`art.__version__` miente en instalación editable.** Lee la metadata del
    paquete INSTALADO, que no se regenera al subir la versión en
    `pyproject.toml`. Daba «0.1.11» sobre un árbol que ya iba por 0.1.12. Así
    que se prefiere la versión del FUENTE cuando el árbol está delante.

    **Y el commit no basta si hay cambios sin commitear.** Con el árbol sucio,
    el SHA identifica el último commit, no el código que corrió. Se marca con
    `+sucio`, que es lo honesto: dice que ese registro no es reproducible a
    partir del SHA solo.
    """
    import os, subprocess
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))

    # la versión del FUENTE, si el árbol está delante
    v = ""
    try:
        with open(os.path.join(raiz, "pyproject.toml"), encoding="utf-8") as fh:
            for ln in fh:
                if ln.strip().startswith("version"):
                    v = ln.split("=", 1)[1].strip().strip('"\'')
                    break
    except Exception:
        pass
    if not v:
        try:
            from art import __version__ as v
        except Exception:
            v = "?"

    def _git(*args, tiempo=3):
        """Consulta a git, best-effort y ACOTADA DE VERDAD.

        BUG-0114. Esto era `subprocess.run(..., timeout=3)`, y el `timeout` NO
        acota: cuando salta, `run` mata al hijo y vuelve a llamar a
        `communicate()` **sin límite** para vaciar las tuberías. Si git dejó un
        nieto vivo con el extremo de escritura abierto —un ayudante de
        credenciales, un paginador—, ese segundo `communicate()` no vuelve
        jamás. Bajo servidor MCP eso cuelga la herramienta ENTERA después de
        haber hecho todo el trabajo: el `.inp`, el `.out` y el `.pre` quedan
        escritos y la respuesta no sale nunca.

        Además el hijo heredaba el `stdin` del proceso, que bajo un servidor
        stdio es la tubería del protocolo y no se cierra nunca: cualquier git
        que decida leer de ahí se queda esperando.

        La versión de aquí: `stdin` a DEVNULL, git en modo no interactivo, y
        tras el plazo se mata y se ABANDONA la tubería en vez de volver a
        esperarla. Saber la versión del instrumento es un adorno del registro;
        no puede costar la sesión.
        """
        pr = None
        try:
            pr = subprocess.Popen(
                ["git", "-C", raiz, *args],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True,
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0",
                     "GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat"},
            )
            salida, _ = pr.communicate(timeout=tiempo)
            return (salida or "").strip()
        except Exception:
            if pr is not None:
                try:
                    pr.kill()
                    if pr.stdout is not None:
                        pr.stdout.close()
                except Exception:
                    pass
            return ""

    sha = _git("rev-parse", "--short", "HEAD")
    sucio = bool(_git("status", "--porcelain")) if sha else False
    out = f"art {v}"
    if sha:
        out += f" @{sha}" + ("+sucio" if sucio else "")
    return out


# ---------------------------------------------------------------------------
# Equation builder
# ---------------------------------------------------------------------------

def _build_equation(spec: dict[str, Any], freq: int) -> str:
    """
    Build a human-readable BL-O equation string from spec.

    Example: ∇²[ln y_t] = D_t(6 arm.) + (1-θ₁B) a_t
    """
    lam = spec.get("lam", 0.0)
    d   = spec.get("d", 0)
    D   = spec.get("D", 0)
    p   = spec.get("p", 0)
    q   = spec.get("q", 0)
    P   = spec.get("P", 0)
    Q   = spec.get("Q", 0)
    n_h = spec.get("n_harmonics", 0)
    itvs = spec.get("interventions", [])

    # Transformed series symbol
    if abs(lam) < 1e-6:
        yt = "ln y_t"
    elif abs(lam - 0.5) < 1e-6:
        yt = "√y_t"
    elif abs(lam - 1.0) < 1e-6:
        yt = "y_t"
    else:
        yt = f"y_t^{{{lam:.2f}}}"

    # Differencing
    diff = ""
    if d == 1:
        diff = "∇"
    elif d > 1:
        diff = f"∇^{d}"
    if D == 1:
        diff += f"∇_{freq}"
    elif D > 1:
        diff += f"∇_{freq}^{D}"

    # BUG-0051. La diferenciación POR FRECUENCIA no aparecía: un modelo con
    # ifadf=[0,1,0] se escribía «∇[ln y_t]» igual que uno con ifadf=[0,0,0],
    # cuando explica (1+B²)∇ln y --otra variable dependiente-- y la diferencia
    # es justo la que hace incomparables sus verosimilitudes. Se nombra el
    # factor de cada frecuencia activa: f=0 → (1−B); la de Nyquist (f=s/2) →
    # (1+B); las interiores → (1 − 2cos(w_f)B + B²), con w_f = 2πf/s.
    ifadf = list(spec.get("ifadf") or [])
    if any(ifadf):
        import math as _m
        factores = []
        for f_i, activo in enumerate(ifadf):
            if not activo:
                continue
            if f_i == 0:
                factores.append("(1−B)")
            elif freq and f_i == freq // 2:
                factores.append("(1+B)")
            else:
                c = 2 * _m.cos(2 * _m.pi * f_i / freq) if freq else 0.0
                if abs(c) < 1e-9:          # cos(π/2)=0 sale como 1.2e-16
                    factores.append("(1+B²)")
                elif c > 0:
                    factores.append(f"(1−{c:.4g}B+B²)")
                else:
                    factores.append(f"(1+{-c:.4g}B+B²)")
        diff = "".join(factores) + diff

    lhs = f"{diff}[{yt}]" if diff else yt

    # Deterministic RHS components
    rhs_parts = []
    # La MEDIA. Sin ella, un modelo con deriva y otro sin ella se escriben
    # exactamente igual, y son modelos distintos con un parámetro de diferencia
    # —sobre un caso real, 37,6 puntos de AIC—. La ecuación es la presentación
    # autoritativa del modelo: si dos modelos distintos se escriben igual, la
    # presentación miente (hallazgo #3 de la revisión externa).
    if spec.get("estimate_mu"):
        rhs_parts.append("μ")
    elif spec.get("mu"):
        rhs_parts.append(f"{float(spec['mu']):+g}")
    # Y el `alter`: el armónico de Nyquist, el (−1)ᵗ. Es un término determinista
    # como cualquier otro, y se filtraba del registro por no ser un suceso.
    if spec.get("alter"):
        rhs_parts.append("(−1)ᵗ")
    if n_h > 0:
        rhs_parts.append(f"D_t({n_h} arm.)")
    if itvs:
        rhs_parts.append(f"I_t({len(itvs)} itvs)")

    # Stochastic noise N_t
    ar_str  = f"φ(B)"  if p > 0 else ""
    ar_s_str = f"Φ(B^{freq})" if P > 0 else ""
    ma_str  = f"θ(B)"  if q > 0 else ""
    ma_s_str = f"Θ(B^{freq})" if Q > 0 else ""

    ar_full  = "·".join(filter(None, [ar_s_str, ar_str]))
    ma_full  = "·".join(filter(None, [ma_s_str, ma_str]))

    if not ar_full and not ma_full:
        noise = "a_t"
    elif not ar_full:
        noise = f"[1-{ma_full}]·a_t"
    elif not ma_full:
        noise = f"[1-{ar_full}]⁻¹·a_t"
    else:
        noise = f"[1-{ar_full}]⁻¹·[1-{ma_full}]·a_t"

    if rhs_parts:
        rhs = " + ".join(rhs_parts) + " + " + noise
    else:
        rhs = noise

    return lhs + " = " + rhs


# ---------------------------------------------------------------------------
# HTML export
# ---------------------------------------------------------------------------

_CSS = """
body { font-family: "Segoe UI", Arial, sans-serif; max-width: 1100px; margin: 40px auto;
       padding: 0 20px; background:#f7f7f7; color:#222; }
h1 { color:#1a237e; border-bottom:3px solid #1a237e; padding-bottom:8px; }
h2 { color:#283593; margin-top:32px; }
table { border-collapse:collapse; width:100%; margin:16px 0; background:#fff; }
th { background:#283593; color:#fff; padding:8px 12px; text-align:left; font-size:13px; }
td { padding:7px 12px; border-bottom:1px solid #e0e0e0; font-size:13px; }
tr:hover td { background:#e8eaf6; }
.ok  { color:#2e7d32; font-weight:bold; }
.bad { color:#c62828; font-weight:bold; }
details { background:#fff; border:1px solid #c5cae9; border-radius:6px;
          margin:14px 0; padding:12px 18px; }
summary { font-size:16px; font-weight:bold; color:#283593; cursor:pointer; }
summary:hover { color:#1a237e; }
.eq { font-family:monospace; background:#f0f4ff; border-left:4px solid #5c6bc0;
      padding:8px 14px; margin:10px 0; font-size:14px; }
.decision { background:#fff9c4; border-left:4px solid #f9a825;
            padding:8px 14px; margin:6px 0; }
.problems { background:#fce4ec; border-left:4px solid #e91e63;
            padding:8px 14px; margin:6px 0; }
.next     { background:#e8f5e9; border-left:4px solid #43a047;
            padding:8px 14px; margin:6px 0; }
img { max-width:100%; border:1px solid #c5cae9; border-radius:4px; margin:10px 0; }
.meta { color:#555; font-size:12px; margin:2px 0; }
"""


def _pass_cell(val: bool | None) -> str:
    if val is None:
        return "<td>—</td>"
    if val:
        return '<td class="ok">✓</td>'
    return '<td class="bad">✗</td>'


def export_guion_html(guion: Guion) -> str:
    """Render a Guion to a self-contained HTML string."""
    lines = [
        "<!DOCTYPE html><html lang='es'><meta charset='utf-8'>",
        f"<title>Guion — {guion.series}</title>",
        f"<style>{_CSS}</style>",
        "<body>",
        f"<h1>Guion de análisis — {guion.series}</h1>",
        f"<p class='meta'>Analista: {guion.analyst} &nbsp;·&nbsp; Creado: {guion.created}</p>",
    ]

    if not guion.entries:
        lines.append("<p><em>Sin versiones registradas.</em></p>")
    else:
        # Summary table
        lines += [
            "<h2>Resumen de versiones</h2>",
            "<table>",
            "<tr><th>#</th><th>Nombre</th><th>Ecuación</th>"
            "<th>loglik</th><th>AIC</th><th>BIC</th>"
            "<th>σ_a</th><th>Q</th><th>JB</th><th>Anomalías</th><th>Decisión (resumen)</th></tr>",
        ]
        for e in guion.entries:
            # UN NODO DE DECISIÓN NO TIENE DIAGNOSIS, y el export recorría TODAS
            # las entradas desreferenciando `e.stats.aic`. Bastaba un nodo —los
            # que escribe `guion_node`— para que el informe navegable muriera con
            # `AttributeError: 'NoneType' object has no attribute 'aic'` y no
            # produjera fichero alguno (BUG-0107).
            #
            # Un nodo se dibuja como lo que es: una decisión, con su fila y sin
            # columnas de ajuste. Omitirlo sería peor —el recorrido cuenta la
            # historia y los nodos son la mitad que explica POR QUÉ— y es
            # justamente lo que BUG-0101 arregló en el mapa.
            if e.is_node:
                nd = e.node or {}
                dec = f"{nd.get('nodo', e.name)} = {nd.get('decidido', '')}"
                lines.append(
                    f"<tr><td>{e.version}</td>"
                    f"<td><a href='#v{e.version}'>◆ {e.name}</a></td>"
                    f"<td colspan='8'><em>nodo de decisión</em></td>"
                    f"<td>{dec[:60]}</td></tr>")
                continue
            s = e.stats
            aic_str = f"{s.aic:.1f}" if s.aic is not None else "—"
            bic_str = f"{s.bic:.1f}" if s.bic is not None else "—"
            dec_short = e.decision[:60] + "…" if len(e.decision) > 60 else e.decision
            lines.append(
                f"<tr>"
                f"<td>{e.version}</td><td><a href='#v{e.version}'>{e.name}</a></td>"
                f"<td><code>{e.equation}</code></td>"
                f"<td>{cifra(s.loglik)}</td><td>{aic_str}</td><td>{bic_str}</td>"
                f"<td>{cifra(s.sigma_a, '.5f')}</td>"
                + _pass_cell(s.q_pass) + _pass_cell(s.jb_pass) +
                f"<td>{s.n_extreme}</td>"
                f"<td>{dec_short}</td>"
                f"</tr>"
            )
        lines.append("</table>")

        # Per-entry collapsible sections
        lines.append("<h2>Detalle por versión</h2>")
        for e in guion.entries:
            s = e.stats
            open_attr = " open" if e == guion.entries[-1] else ""
            # Igual aquí: un nodo no tiene ajuste que resumir en la cabecera.
            aic_hdr = f"{s.aic:.1f}" if (s and s.aic is not None) else "—"
            q_hdr   = "✓" if (s and s.q_pass) else ("✗" if (s and s.q_pass is False) else "—")
            jb_hdr  = "✓" if (s and s.jb_pass) else ("✗" if (s and s.jb_pass is False) else "—")
            lines += [
                f"<details id='v{e.version}'{open_attr}>",
                f"<summary>v{e.version} — {e.name}"
                f"  <span style='font-weight:normal;font-size:13px;color:#555'>"
                f"  AIC={aic_hdr}  Q={q_hdr}  JB={jb_hdr}"
                f"  </span></summary>",
                f"<p class='meta'>Archivo: <code>{e.inp_path}</code> &nbsp;·&nbsp; {e.timestamp}</p>",
                f"<div class='eq'>{e.equation}</div>",
            ]

            # Spec table
            sp = e.spec
            lines += [
                "<table style='width:auto;margin:8px 0'>",
                "<tr><th>λ</th><th>d</th><th>D</th><th>p</th><th>q</th>"
                "<th>P</th><th>Q</th><th>arm.</th><th>itvs</th></tr>",
                f"<tr>"
                f"<td>{sp.get('lam',0):.1f}</td><td>{sp.get('d',0)}</td>"
                f"<td>{sp.get('D',0)}</td><td>{sp.get('p',0)}</td><td>{sp.get('q',0)}</td>"
                f"<td>{sp.get('P',0)}</td><td>{sp.get('Q',0)}</td>"
                f"<td>{sp.get('n_harmonics',0)}</td>"
                f"<td>{len(sp.get('interventions',[]))}</td>"
                f"</tr></table>",
            ]

            # Stats — sólo si las hay. Un nodo de decisión llega hasta aquí con
            # su razón y sus alternativas, que es lo que tiene que enseñar; una
            # tabla de ajuste vacía no diría nada y desreferenciarla mata el
            # export entero (BUG-0107).
            if s is None:
                nd = e.node or {}
                if nd.get("evidencia"):
                    lines.append(f"<p><b>Evidencia:</b> {nd['evidencia']}</p>")
                if nd.get("alternativas"):
                    lines.append(f"<p><b>Descartado:</b> {nd['alternativas']}</p>")
                if e.decided_by:
                    lines.append(f"<p class='meta'>Decidido por: {e.decided_by}</p>")
                if e.rationale:
                    lines.append(f"<p><b>Razón:</b> {e.rationale}</p>")
                lines.append("</details>")
                continue
            aic_s = f"{s.aic:.2f}" if s.aic is not None else "—"
            bic_s = f"{s.bic:.2f}" if s.bic is not None else "—"
            lines += [
                "<table style='width:auto;margin:8px 0'>",
                "<tr><th>loglik</th><th>AIC</th><th>BIC</th><th>σ_a</th><th>Q</th><th>JB</th><th>Anomalías</th></tr>",
                f"<tr><td>{cifra(s.loglik, '.3f')}</td><td>{aic_s}</td><td>{bic_s}</td>"
                f"<td>{cifra(s.sigma_a, '.6f')}</td>"
                + _pass_cell(s.q_pass) + _pass_cell(s.jb_pass) +
                f"<td>{s.n_extreme}</td></tr>",
                "</table>",
            ]

            if s.extreme:
                lines.append("<p><b>Residuos extremos:</b> "
                             + ", ".join(f"{x['date']} (z={x['z']:+.2f})" for x in s.extreme)
                             + "</p>")

            if e.decision:
                lines.append(f"<div class='decision'><b>Decisión:</b> {e.decision}</div>")
            if e.rationale:
                lines.append(f"<div class='decision'><b>Justificación:</b> {e.rationale}</div>")
            if e.problems_found:
                lines.append(f"<div class='problems'><b>Problemas detectados:</b> {e.problems_found}</div>")
            if e.next_version:
                lines.append(f"<div class='next'><b>Próxima versión:</b> {e.next_version}</div>")

            if getattr(e, "figure_path", None):
                lines.append(f"<img src='{e.figure_path}' alt='diagnosis'>")
            elif e.figure_b64:
                # Guion antiguo, con la figura empotrada.
                lines.append(f"<img src='data:image/png;base64,{e.figure_b64}' alt='diagnosis'>")

            lines.append("</details>")

    lines.append("</body></html>")
    return "\n".join(lines)
