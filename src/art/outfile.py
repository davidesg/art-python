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
    #: "Standard errors: <método>", que fue escribe desde 0.1.17 (fue/BUG-0015):
    #: "fdhess", "bfgs (fdhess: …)" o "none (…)". None = `.out` de un fue
    #: anterior, cuyas desviaciones típicas son las del BFGS del camino.
    metodo_se: str | None = None

    @property
    def se_del_hessiano(self) -> bool:
        """¿Estas desviaciones típicas son la curvatura EN el óptimo?"""
        return self.metodo_se == "fdhess"

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
_TERMINO_COV = re.compile(r"-?\d*\.\d{9}")
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
    return lee_texto_out(texto, path)


def lee_texto_out(texto: str, ruta: str = "") -> LecturaOut:
    """Lee el TEXTO de un `.out` (el de un fichero o el de `write_out()`)."""
    r = LecturaOut(ruta=ruta, texto=texto)
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
        elif s.startswith("Standard errors:"):
            r.metodo_se = s.split(":", 1)[1].strip() or None

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
                # fue escribe cada término con "%13.9f" y SIN separador: un
                # valor de 100 o más llena el campo (o lo desborda) y se pega al
                # anterior —"34.9639402631296.568401265"—. Cada número lleva
                # exactamente nueve decimales, y eso es lo que los separa.
                cov.append([float(x) for x in _TERMINO_COV.findall(m.group(2))])
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
            elif (m := re.match(r"^(\d+)\s+observations", s)):
                # El número va ANTES de los dos puntos: `_num` cogía el mes de
                # «from 2/2011» y daba n = 2 (BUG-0222).
                r.residuos.n = int(m.group(1)) or None
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


# ── Un `.out` anterior a fue 0.1.17 ─────────────────────────────────────────
#
# Hasta fue 0.1.16 las desviaciones típicas del `.out` salían del BFGS del
# CAMINO (fue/BUG-0015): son la constancia fiel de lo que se publicó, pero no la
# curvatura en el óptimo. Se siguen leyendo —el `.out` es el registro— y se dice
# de dónde vienen, con la salida: reestimar el `.pre` con un fue que calcula el
# hessiano da las mismas estimaciones y las desviaciones típicas buenas.

AVISO_OUT_BFGS = (
    "ℹ **Las desviaciones típicas de este `.out` son las del BFGS del camino** "
    "(el `.out` es de un fue anterior a 0.1.17, o fue tuvo que caer al BFGS). "
    "Son las que se publicaron, pero dependen de por dónde pasó el optimizador "
    "(fue/BUG-0015). Las ESTIMACIONES son correctas. Para tener la curvatura en "
    "el óptimo, reestima el `.pre`: con fue ≥ 0.1.17 da las mismas estimaciones "
    "y las desviaciones típicas del hessiano (`estimate_and_diagnose` sobre el "
    "`.pre`)."
)


def aviso_out(lectura: "LecturaOut") -> str:
    """El aviso para un `.out` cuyas SE no son del hessiano en el óptimo, o ""."""
    if lectura is None or lectura.se_del_hessiano:
        return ""
    return AVISO_OUT_BFGS


# ── El resumen (BUG-0222) ───────────────────────────────────────────────────
#
# El `.out` pesa unos 40 KB: la serie tipificada línea a línea, el histograma,
# la ACF/PACF dibujadas y la calibración de la FAS. En el carril autónomo se
# lee decenas de veces para tres cifras, y cada lectura entera satura el
# contexto. El resumen saca del MISMO fichero —no reestima— lo que decide un
# nodo; sólo añade aritmética de lo que ya está escrito: t, AIC/BIC, los
# valores p y las raíces de los factores.

_FACTOR = re.compile(r"^Coefficients for (regular|annual) (f-fixed )?(AR|MA) factor (\d+)"
                     r"(?:\s*\[f = ([\d.]+)\])?")
_DETERM = re.compile(r"^(Omegas|Deltas) for deterministic variable (\d+)")
_VALOR = re.compile(r"^\s*(-?\d+\.\d+)(?:\s*\(\s*(-?\d+\.?\d*)\s*\)\s*\[\s*(\d+)\s*\])?\s*$")
_CORR = re.compile(r"corr\[\s*(\d+)\]\[\s*(\d+)\]\s*=\s*(-?\d+\.\d+)")
_LB = re.compile(r"^\s*(\d+)\s+-?\d+\.\d+\s.*[|+]\s*(\d+\.\d+)\s+(\d+)\s*$")
_ATIP = re.compile(r"^\s*\|\s*(\d+)\s+(\S+)\s+(-?\d+\.\d+)\s+\|\s*$")
_LETRA = {("AR", False): "φ", ("AR", True): "Φ", ("MA", False): "θ", ("MA", True): "Θ"}


@dataclass
class FactorOut:
    """Un factor ARMA tal como lo escribe el `.out`: (1 − c₁B − … − c_pB^p)."""

    tipo: str                    # "AR" | "MA"
    anual: bool
    numero: int
    coefs: list[float] = field(default_factory=list)   # también el φ₁ derivado de un f-fijo
    freq_fija: float | None = None

    @property
    def nombre(self) -> str:
        clase = ("f-fijo" if self.freq_fija is not None
                 else "anual" if self.anual else "regular")
        return f"{self.tipo} {clase} {self.numero}"


def _estructura(texto: str):
    """Factores ARMA, etiqueta de cada parámetro [n], y lo que publica el
    diagnóstico: correlaciones altas, Q de Ljung-Box y tabla de anómalos."""
    factores: list[FactorOut] = []
    etiquetas: dict[int, str] = {}
    corr: list[tuple[int, int, float]] = []
    lb: list[tuple[int, float, int]] = []
    atip: list[tuple[int, str, float]] = []
    umbral_atip = None

    actual = None            # (clase, datos)
    j = 0
    seccion = "parametros"
    for L in texto.split("\n"):
        s = L.strip()
        if seccion == "parametros":
            if s.startswith("Box-Cox lambda"):
                seccion = ""
                continue
            m = _FACTOR.match(s)
            if m:
                f = FactorOut(tipo=m.group(3), anual=m.group(1) == "annual",
                              numero=int(m.group(4)),
                              freq_fija=float(m.group(5)) if m.group(5) else None)
                factores.append(f)
                actual, j = ("factor", f), 0
                continue
            m = _DETERM.match(s)
            if m:
                actual, j = ("det", (m.group(1), int(m.group(2)))), 0
                continue
            if s.startswith("Mean parameter"):
                actual, j = ("mu", None), 0
                continue
            m = _VALOR.match(L)
            if m and actual is not None:
                j += 1
                idx = int(m.group(3)) if m.group(3) else None
                clase, dat = actual
                if clase == "factor":
                    dat.coefs.append(float(m.group(1)))
                    if idx is not None:
                        etiquetas[idx] = f"{_LETRA[(dat.tipo, dat.anual)]}{j} [{dat.nombre}]"
                elif idx is not None and clase == "det":
                    nombre, k = dat
                    etiquetas[idx] = (f"ω{j - 1} [det. {k}]" if nombre == "Omegas"
                                      else f"δ{j} [det. {k}]")
                elif idx is not None:
                    etiquetas[idx] = "μ"
            continue

        if s.startswith("Correlations greater than"):
            seccion = "corr"
        elif s.startswith("Unconditional residuals"):
            seccion = ""
        elif s.startswith("Autocorrelation function"):
            seccion = "acf"
        elif s.startswith("Partial autocorrelation function"):
            seccion = ""
        elif "Table of standardized values" in s:
            seccion = "atip"
        elif s.startswith("Standardized time series histogram"):
            seccion = ""
        elif seccion == "corr":
            for a, b, v in _CORR.findall(s):
                corr.append((int(a), int(b), float(v)))
        elif seccion == "acf":
            m = _LB.match(L)
            if m:
                lb.append((int(m.group(1)), float(m.group(2)), int(m.group(3))))
        elif seccion == "atip":
            m = re.search(r"greater than or equal to\s*([\d.]+)", s)
            if m:
                umbral_atip = float(m.group(1))
            m = _ATIP.match(L)
            if m:
                atip.append((int(m.group(1)), m.group(2), float(m.group(3))))
    return factores, etiquetas, corr, lb, atip, umbral_atip


def _raices(f: FactorOut) -> list[str]:
    """Raíces de 1 − c₁z − … − c_p z^p: módulo y, si son complejas, periodo."""
    import numpy as np
    pol = [-c for c in reversed(f.coefs)] + [1.0]     # grado p … 0
    while len(pol) > 1 and pol[0] == 0:
        pol = pol[1:]
    if len(pol) < 2:
        return []
    out = []
    for z in sorted(np.roots(pol), key=abs):
        if z.imag < -1e-9:
            continue                                  # va con su conjugada
        if abs(z.imag) > 1e-9:
            per = 2 * np.pi / abs(np.angle(z))
            out.append(f"{z.real:.3f}±{abs(z.imag):.3f}i "
                       f"(|z|={abs(z):.3f}, periodo {per:.1f})")
        else:
            out.append(f"{z.real:.3f} (|z|={abs(z):.3f})")
    return out


def _p_chi2(x: float, gl: int) -> float | None:
    try:
        from scipy.stats import chi2
        return float(chi2.sf(x, gl)) if gl > 0 else None
    except Exception:
        return None


def _fp(p: float | None) -> str:
    if p is None:
        return "—"
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def resumen_out(r: LecturaOut, max_atipicos: int = 12) -> str:
    """Lo que decide un nodo, leído del `.out`, en ≈ 1–3 KB (BUG-0222).

    Parámetros con e.t. y t; σ̂ₐ; ℓ, AIC y BIC; correlaciones altas entre
    estimadores; raíces de cada factor; Q de Ljung-Box en los retardos que el
    `.out` publica (12/24/36/39 en mensual) con g.l. y p; JB con p; y la tabla
    de anómalos con fecha. Lo que falte en el fichero se omite, no se inventa.

    AIC = −2ℓ + 2k y BIC = −2ℓ + k·ln n, con k los parámetros del `.out` y n
    los residuos: los mismos que `model.aic`/`model.bic` de fue.
    """
    import math
    factores, etq, corr, lb, atip, umbral = _estructura(r.texto)
    res = r.residuos
    n_eff = res.n
    L: list[str] = []

    det = []
    if r.convergio is True:
        det.append(f"convergió en {r.iteraciones} iter." if r.iteraciones
                   else "convergió")
    elif r.convergio is False:
        det.append("⚠ NO convergió")
    if r.metodo_se:
        det.append(f"e.t.: {r.metodo_se}")
    for nom, v in (("λ", r.lam), ("d", r.d), ("D", r.D), ("s", r.freq)):
        if v is not None:
            det.append(f"{nom}={v:g}")
    if n_eff:
        det.append(f"n={n_eff} residuos")
    L.append(f"**Resumen de `{os.path.basename(r.ruta) or '.out'}`**"
             + (" — " + " · ".join(det) if det else ""))
    L.append("")

    if r.parametros:
        L.append("| # | parámetro | estimación | e.t. | t |")
        L.append("|---|---|---:|---:|---:|")
        for p in r.parametros:
            L.append(f"| {p.indice} | {etq.get(p.indice, p.bloque or '?')} | "
                     f"{p.valor:.6f} | {p.se:.6f} | {p.t:.2f} |")
    else:
        L.append("*El `.out` no trae parámetros estimados.*")
    L.append("")

    k = r.npar if r.npar is not None else len(r.parametros)
    aj = []
    if r.sigma is not None:
        aj.append(f"σ̂ₐ = {r.sigma:.6g}")
    if r.sigma2 is not None:
        aj.append(f"σ̂ₐ² = {r.sigma2:.6g}"
                  + (f" (e.t. {r.se_sigma2:.3g})" if r.se_sigma2 is not None else ""))
    if r.loglik is not None:
        aj.append(f"ℓ = {r.loglik:.3f}")
        aj.append(f"AIC = {-2 * r.loglik + 2 * k:.2f}")
        if n_eff:
            aj.append(f"BIC = {-2 * r.loglik + k * math.log(n_eff):.2f}")
    if aj:
        L.append("**Ajuste:** " + " · ".join(aj) + f" (k={k})")

    if corr:
        L.append("**Correlaciones |ρ| ≥ 0.7 entre estimadores:** " + "; ".join(
            f"{etq.get(a, f'[{a}]')} ~ {etq.get(b, f'[{b}]')}: {v:+.2f}"
            for a, b, v in sorted(corr, key=lambda c: -abs(c[2]))))
    elif "Correlations greater than" in r.texto:
        L.append("**Correlaciones |ρ| ≥ 0.7 entre estimadores:** ninguna")

    lr = []
    for f in factores:
        rr = _raices(f)
        if rr:
            var = f"B^{r.freq}" if (f.anual and r.freq) else "B"
            lr.append(f"- {f.nombre} (en {var}): " + "; ".join(rr))
    if lr:
        L.append("**Raíces** (|z| > 1 ⇒ estacionario / invertible):")
        L.extend(lr)
    L.append("")

    if lb:
        L.append("**Ljung-Box:** " + " · ".join(
            f"Q({lag}) = {q:.2f}, g.l. {gl}, p {_fp(_p_chi2(q, gl))}"
            for lag, q, gl in lb))
    if res.jarque_bera is not None:
        extra = []
        if res.asimetria is not None:
            extra.append(f"asimetría {res.asimetria:.3f}")
        if res.curtosis is not None:
            extra.append(f"curtosis {res.curtosis:.3f}")
        L.append(f"**Jarque-Bera:** {res.jarque_bera:.2f}, p "
                 f"{_fp(_p_chi2(res.jarque_bera, 2))}"
                 + (f" ({', '.join(extra)})" if extra else ""))
    if res.media is not None and res.se_media:
        L.append(f"**Media de los residuos:** {res.media:.4g} (e.t. "
                 f"{res.se_media:.3g}, t = {res.media / res.se_media:.2f})")

    if "Table of standardized values" in r.texto:
        u = f"{umbral:g}" if umbral is not None else "2"
        if atip:
            sel = atip
            if len(atip) > max_atipicos:
                sel = sorted(sorted(atip, key=lambda a: -abs(a[2]))[:max_atipicos])
            resto = len(atip) - len(sel)
            L.append(f"**Anómalos |z| ≥ {u}** ({len(atip)}): "
                     + ", ".join(f"{fecha} ({z:+.2f})" for _, fecha, z in sel)
                     + (f"; y {resto} más de menor |z|" if resto else ""))
        else:
            L.append(f"**Anómalos |z| ≥ {u}:** ninguno")
    elif "above 8 sigmas" in r.texto:
        L.append("**Anómalos:** ⚠ el `.out` avisa de al menos una observación por "
                 "encima de 8σ y no publica la tabla — mira el extremo de los "
                 "residuos o `residual_outlier_scan`.")
        for nom, ext in (("mínimo", res.minimo), ("máximo", res.maximo)):
            if ext:
                L.append(f"  residuo {nom}: {ext[0]:.4g} en {ext[1]}")
    return "\n".join(L).rstrip() + "\n"
