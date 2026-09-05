"""art.outfile — leer el `.out`, que es la única constancia fiel de una estimación.

Por qué existe este módulo
--------------------------
El convenio de ficheros tiene tres piezas:

    .inp  una ESPECIFICACIÓN; sus valores son SEMILLAS.   → estimar
    .pre  el óptimo en forma reejecutable.                → sembrar el .inp siguiente
    .out  el registro de una estimación y su diagnosis.   → LEER

Y la tercera es la que faltaba en el cableado. La razón no es de comodidad, es de
fondo: **la covarianza no es una propiedad del óptimo, es un subproducto del
CAMINO** que recorre el optimizador. BFGS la acumula iteración a iteración, así
que arrancar ya en el óptimo no acumula nada y la covarianza se queda en la
semilla (BUG-0027, BUG-0090).

De ahí se sigue que un fichero que guarda sólo el óptimo —el `.pre`— **no puede**
llevar la curvatura, por bien escrito que esté. El `.out` es el único sitio donde
las desviaciones típicas quedan tal como se calcularon. Medido: las SE leídas de
aquí coinciden con las de una reestimación desde el `.inp` en los 15 parámetros
(razón 1.000), y las de una reestimación desde el `.pre` se van entre 0.46× y
3.47× (BUG-0091).

art ya lo decía en sus propios avisos —*«el `.out` del modelo trae la covarianza
completa»*— y no tenía con qué leerlo: la instrucción existía y no era
ejecutable.

Qué garantiza
-------------
Lectura **defensiva**: un `.out` de otra versión del motor, truncado o con una
sección ausente devuelve esa sección a `None` y el resto poblado. Nunca levanta
por una sección que falte; sólo si el fichero no existe o no se puede leer.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


@dataclass
class ParametroOut:
    """Un parámetro tal como el `.out` lo registró."""

    indice: int                  # el [n] del fichero, 1-based
    valor: float
    se: float
    bloque: str                  # «Omegas for deterministic variable 12», …

    @property
    def t(self) -> float:
        return self.valor / self.se if self.se else float("nan")


@dataclass
class ResiduosOut:
    """Las estadísticas de los residuos que el `.out` publica."""

    n: int | None = None
    media: float | None = None
    se_media: float | None = None
    varianza: float | None = None
    desv_tipica: float | None = None
    asimetria: float | None = None
    curtosis: float | None = None
    jarque_bera: float | None = None
    minimo: tuple[float, str, int] | None = None    # (valor, fecha, obs)
    maximo: tuple[float, str, int] | None = None


@dataclass
class LecturaOut:
    """Lo que un `.out` dice. Todo opcional salvo `texto` y `ruta`."""

    ruta: str
    texto: str
    nobs: int | None = None
    npar: int | None = None
    iteraciones: int | None = None
    convergio: bool | None = None
    parametros: list[ParametroOut] = field(default_factory=list)
    covarianza: list[list[float]] | None = None      # triangular inferior
    sigma2: float | None = None
    se_sigma2: float | None = None
    sigma: float | None = None
    loglik: float | None = None
    hannan_quinn: float | None = None
    schwarz: float | None = None
    lam: float | None = None
    d: int | None = None
    D: int | None = None
    freq: int | None = None
    residuos: ResiduosOut = field(default_factory=ResiduosOut)

    @property
    def se(self) -> list[float]:
        """Las desviaciones típicas, en el orden del `.out`."""
        return [p.se for p in self.parametros]

    @property
    def valores(self) -> list[float]:
        return [p.valor for p in self.parametros]

    @property
    def completo(self) -> bool:
        """¿Trae lo que hace falta para no tener que reestimar?"""
        return bool(self.parametros) and self.loglik is not None


# ── el lector ────────────────────────────────────────────────────────────────

_PAR = re.compile(r"^\s*(-?\d+\.\d+)\s*\(\s*(-?\d+\.?\d*)\s*\)\s*\[\s*(\d+)\s*\]")
_COV = re.compile(r"^\s*x\[\s*(\d+)\]\s*->\s*(.*)$")
_EXTREMO = re.compile(
    r"^\s*(Minimum|Maximum):\s*(-?\d+\.\d+)\s+at\s+(\S+)\s+\(observation\s+(\d+)\)")


def _num(linea: str) -> float | None:
    """El primer número DESPUÉS de los dos puntos.

    Buscarlo en la línea entera se come el dígito de la etiqueta: `sigma2:` daba
    2.0 en vez de la varianza. Las etiquetas del `.out` llevan número
    (`sigma2`, `x[ 1]`, `AR factor 1`), así que hay que cortar por el separador.
    """
    cuerpo = linea.split(":", 1)[1] if ":" in linea else linea
    m = re.search(r"(-?\d+\.?\d*(?:[eE][-+]?\d+)?)", cuerpo)
    return float(m.group(1)) if m else None


def lee_out(path: str) -> LecturaOut:
    """Lee un `.out`. `path` puede ser el propio `.out` o cualquier hermano.

    Si se le pasa `X.inp` o `X.pre`, busca `X.out`: la terna comparte basename y
    exigir la extensión exacta sería trasladar al llamante una regla que este
    módulo ya conoce.
    """
    path = os.path.expanduser(path)
    if not path.lower().endswith(".out"):
        cand = os.path.splitext(path)[0] + ".out"
        if os.path.exists(cand):
            path = cand
    if not os.path.exists(path):
        raise FileNotFoundError(f"No hay `.out` que leer: {path}")
    with open(path, encoding="utf-8", errors="replace") as fh:
        texto = fh.read()

    r = LecturaOut(ruta=path, texto=texto)
    lineas = texto.split("\n")

    bloque = ""
    en_cov = False
    cov: list[list[float]] = []
    en_res = False

    for i, L in enumerate(lineas):
        s = L.strip()

        # ── cabecera ──
        if s.startswith("Observations:"):
            r.nobs = int(_num(s) or 0) or None
        elif s.startswith("Parameters"):
            r.npar = int(_num(s) or 0) or None
        elif "CONVERGENCE OBTAINED AFTER" in s:
            r.convergio = True
            m = re.search(r"AFTER\s+(\d+)\s+ITERATIONS", s)
            if m:
                r.iteraciones = int(m.group(1))
        elif "STOPPING CRITERIUM" in s and "SATISFIED" not in s:
            r.convergio = False

        # ── especificación ──
        elif s.startswith("Box-Cox lambda"):
            r.lam = _num(s)
        elif s.startswith("Seasonal period"):
            r.freq = int(_num(s) or 0) or None
        elif s.startswith("Regular differences"):
            r.d = int(_num(s) or 0)
        elif s.startswith("Annual differences"):
            r.D = int(_num(s) or 0)

        # ── ajuste ──
        elif s.startswith("sigma2:"):
            r.sigma2 = _num(s)
            m = re.search(r"\(\s*(-?\d+\.?\d*)\s*\)", s)
            if m:
                r.se_sigma2 = float(m.group(1))
        elif s.startswith("sigma :") or s.startswith("sigma:"):
            r.sigma = _num(s)
        elif s.startswith("logelf:"):
            r.loglik = _num(s)
        elif s.startswith("Hannan-Quinn"):
            r.hannan_quinn = _num(s)
        elif s.startswith("Schwarz"):
            r.schwarz = _num(s)

        # ── secciones ──
        elif s.startswith("Estimated covariance matrix"):
            en_cov, en_res = True, False
            continue
        elif s.startswith("Estimated correlation matrix"):
            en_cov = False
        elif s.startswith("Unconditional residuals"):
            en_res = True
            m = re.search(r"seasonal period:\s*(\d+)", s)
            if m and r.freq is None:
                r.freq = int(m.group(1))
        elif s.startswith("Standardized time series plot"):
            en_res = False

        if en_cov:
            m = _COV.match(L)
            if m:
                cov.append([float(x) for x in m.group(2).split()])
            continue

        if en_res:
            if s.startswith("Mean:"):
                r.residuos.media = _num(s)
            elif s.startswith("Standard error of mean"):
                r.residuos.se_media = _num(s)
            elif s.startswith("Variance:"):
                r.residuos.varianza = _num(s)
            elif s.startswith("Standard deviation"):
                r.residuos.desv_tipica = _num(s)
            elif s.startswith("Skewness:"):
                r.residuos.asimetria = _num(s)
            elif s.startswith("Kurtosis:"):
                r.residuos.curtosis = _num(s)
            elif s.startswith("Jarque-Bera:"):
                r.residuos.jarque_bera = _num(s)
            elif s.startswith(("Minimum:", "Maximum:")):
                m = _EXTREMO.match(L)
                if m:
                    dato = (float(m.group(2)), m.group(3), int(m.group(4)))
                    if m.group(1) == "Minimum":
                        r.residuos.minimo = dato
                    else:
                        r.residuos.maximo = dato
            elif re.match(r"^\d+\s+observations", s):
                r.residuos.n = int(_num(s) or 0) or None
            continue

        # ── la tabla de parámetros ──
        # El bloque lo nombra la línea anterior («Omegas for deterministic
        # variable 12:»), y el valor viene como `v  (se) [n]`. Se guarda el
        # índice del fichero y no la posición en la lista: es el que casa con
        # `x[n]` de la matriz de covarianzas.
        if s.endswith(":") and not _PAR.match(L):
            bloque = s[:-1]
        else:
            m = _PAR.match(L)
            if m:
                r.parametros.append(ParametroOut(
                    indice=int(m.group(3)), valor=float(m.group(1)),
                    se=float(m.group(2)), bloque=bloque))

    if cov:
        r.covarianza = cov
    r.parametros.sort(key=lambda p: p.indice)
    return r


def hay_out(path: str) -> bool:
    """¿Existe el `.out` de esta terna?"""
    p = os.path.expanduser(path)
    if p.lower().endswith(".out"):
        return os.path.exists(p)
    return os.path.exists(os.path.splitext(p)[0] + ".out")
