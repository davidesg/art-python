"""Guion de análisis BJ-T — traza completa de versiones del modelo."""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GuionStats:
    loglik: float
    aic: float | None
    bic: float | None
    sigma_a: float
    q_pass: bool | None
    jb_pass: bool | None
    n_extreme: int
    extreme: list[dict[str, Any]] = field(default_factory=list)


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

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GuionEntry":
        d = dict(d)
        stats_d = d.pop("stats", None)
        # Un nodo de decisión no tiene diagnosis: no hay modelo que diagnosticar.
        stats = GuionStats(**stats_d) if stats_d else None
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
# Persistence
# ---------------------------------------------------------------------------

def load_guion(path: str) -> Guion:
    with open(path, encoding="utf-8") as f:
        return Guion.from_dict(json.load(f))


def save_guion(guion: Guion, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(guion.to_dict(), f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Spec / stats extraction
# ---------------------------------------------------------------------------

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
        {"type": i.type, "date": _at_to_date(i.at, sy, sp, freq)}
        for i in itv
        if i.type not in ("cos", "sin", "alter")
    ]

    return {
        "lam": lam,
        "d": model.d,
        "D": model.D,
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
    )


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
            s = e.stats
            aic_str = f"{s.aic:.1f}" if s.aic is not None else "—"
            bic_str = f"{s.bic:.1f}" if s.bic is not None else "—"
            dec_short = e.decision[:60] + "…" if len(e.decision) > 60 else e.decision
            lines.append(
                f"<tr>"
                f"<td>{e.version}</td><td><a href='#v{e.version}'>{e.name}</a></td>"
                f"<td><code>{e.equation}</code></td>"
                f"<td>{s.loglik:.2f}</td><td>{aic_str}</td><td>{bic_str}</td>"
                f"<td>{s.sigma_a:.5f}</td>"
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
            aic_hdr = f"{s.aic:.1f}" if s.aic is not None else "—"
            q_hdr   = "✓" if s.q_pass else ("✗" if s.q_pass is False else "—")
            jb_hdr  = "✓" if s.jb_pass else ("✗" if s.jb_pass is False else "—")
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

            # Stats
            aic_s = f"{s.aic:.2f}" if s.aic is not None else "—"
            bic_s = f"{s.bic:.2f}" if s.bic is not None else "—"
            lines += [
                "<table style='width:auto;margin:8px 0'>",
                "<tr><th>loglik</th><th>AIC</th><th>BIC</th><th>σ_a</th><th>Q</th><th>JB</th><th>Anomalías</th></tr>",
                f"<tr><td>{s.loglik:.3f}</td><td>{aic_s}</td><td>{bic_s}</td>"
                f"<td>{s.sigma_a:.6f}</td>"
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
