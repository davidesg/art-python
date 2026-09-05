"""art.configuracion — qué configuraciones del incidente admite el dato.

El problema
-----------
Con `d=1` un spike observado en ∇ puede ser el **arranque** de un suceso o la
**cola** de uno que empezó un período antes: un impulso de nivel en T produce
+ω en T y −ω en T+1. Si la serie deambula y el primer spike queda tapado por un
vaivén de signo contrario, lo que cruza el umbral es el segundo, y la
intervención cae un período tarde — es BUG-0030, con Δ logL = 0,03 entre la
fecha buena y la mala.

Y el arranque no es un detalle de fecha: **decide la línea base**. Una
intervención mide siempre contra lo que la precede, así que arrancar antes
absorbe parte del ascenso previo y encoge la ganancia estimada.

Lo que se midió sobre PGAS
--------------------------
Enumerando `(arranque, longitud)` entre 2008Q1 y 2009Q1: **seis configuraciones
dentro de 2 puntos de AIC, ninguna dejando vecino anómalo**. Ni el AIC ni la
regla de Treadway las separan. Y discrepan en lo sustantivo: la ganancia va de
−0,04 a −0,58 y el veredicto permanente/transitorio se invierte.

Peor: **la de ventana más corta tiene el intervalo más estrecho y es la única
que excluye el cero.** No es suerte — acortar la ventana quita parámetros y
aprieta la identificación DENTRO del modelo mientras empeora la línea base. La
lectura equivocada viene con la etiqueta de precisión más convincente.

    dispersión ENTRE configuraciones   0,189
    error típico DENTRO de un modelo   0,139 – 0,328

Son del mismo orden: reportar sólo el segundo subestima la incertidumbre a la
mitad, y justo en el número que se va a interpretar.

Qué hace este módulo
--------------------
**Acota el conjunto por el MECANISMO, no por rejilla.** La marcha es
**simétrica**: hacia atrás desde el primer extremo y hacia delante desde el
último, en ambos casos mientras los residuos contiguos sigan ACTIVOS (|z| ≥
`umbral_activo`) y parando en el primero que no lo esté. Fijados arranque y
final, la longitud queda determinada:

    n_escalones = (final − arranque + 1) − d + 1

Tiene que ser simétrica porque el mecanismo que la justifica —con d≥1 un suceso
del nivel reparte su firma entre residuos contiguos, y el extremo puede caer en
cualquiera de ellos— no distingue el signo del desplazamiento. Acotar sólo por
la izquierda dejaba fuera para siempre los sucesos con la cola por debajo del
umbral de extremo (BUG-0083).

Sigue sin haber barrido: las dos marchas paran en el primer vecino inactivo, y
sin vecinos activos el conjunto degenera en un solo candidato — en cuyo caso el
informe dice que no hubo nada que comparar, no que el dato identifique.

Y **no elige** cuando el dato no identifica: publica el conjunto, el rango de la
ganancia, y devuelve la pregunta extramuestral. Es el resultado honesto.

Dominio e información extramuestral
-----------------------------------
Son las dos cosas que sí identifican, y entran de forma distinta:

* **El dominio lo sabe la herramienta** (`policy.decide_domain`): sobre un
  índice de precios una caída permanente de nivel es poco usual. **Marca
  implausibilidad, no elimina candidatos** — una heurística de nombre no puede
  decidir econometría.
* **La información extramuestral NO la sabe la herramienta y no debe
  inventarla.** Entra como parámetro. Lo único que la herramienta puede hacer
  —y hace— es dejar constancia de QUIÉN la aportó, para que se pueda discutir
  después. En el carril autónomo eso queda como «LLM», que es exactamente el
  dato que hace falta para saber si el modelo lo sabía o se lo inventó.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

__all__ = ["Candidato", "ConjuntoCandidatos", "InfoExtramuestral",
           "arranques_candidatos", "evalua_configuraciones",
           "describe_configuraciones", "UMBRAL_ACTIVO", "BANDA_AIC"]


# Un residuo cuenta como ACTIVO —parte del suceso aunque no sea extremo— a
# partir de esta |z|. Fijado en 1σ por el analista. No es un umbral de detección
# sino de EXTENSIÓN: dice hasta dónde puede llegar hacia atrás un suceso ya
# detectado por sus extremos.
UMBRAL_ACTIVO = 1.0

# Dos configuraciones dentro de esta banda de AIC se consideran empatadas.
BANDA_AIC = 2.0

# Clases de serie donde un cambio PERMANENTE de nivel es poco usual.
DOMINIOS_SIN_CAIDA_PERMANENTE = ("price_index",)


@dataclass
class InfoExtramuestral:
    """Lo que el analista sabe del mundo y la herramienta no.

    `fuente` es obligatoria si se declara `naturaleza`: no se puede afirmar que
    un suceso fue permanente sin decir por qué se sabe. Y `aportada_por` deja
    constancia de quién lo dijo — en autónomo será «LLM», que es el dato que
    permite después distinguir lo sabido de lo inventado.
    """

    desde: str = ""              # fecha en que empezó el suceso, "QN/AAAA"
    naturaleza: str = ""         # "permanente" | "transitorio" | ""
    fuente: str = ""             # qué se está citando
    aportada_por: str = ""       # "analista" | "LLM" | ""

    def __post_init__(self):
        if self.naturaleza and not self.fuente.strip():
            raise ValueError(
                "declarar `naturaleza` sin `fuente` no vale: afirmar que un "
                "suceso fue permanente o transitorio exige decir por qué se "
                "sabe. Sin fuente, deja `naturaleza` vacía y que decida el "
                "contraste de ganancia.")
        if self.naturaleza and self.naturaleza not in ("permanente", "transitorio"):
            raise ValueError(f"naturaleza={self.naturaleza!r}: "
                             "'permanente', 'transitorio' o vacío.")

    @property
    def hay(self) -> bool:
        return bool(self.desde or self.naturaleza)


@dataclass
class Candidato:
    """Una configuración del incidente, estimada."""

    arranque_resid: int          # obs 1-based en los RESIDUOS
    n_escalones: int
    etiqueta: str = ""           # código corto para tablas: "Q2/2008×5"
    fecha: str = ""              # la fecha sola: "Q2/2008"
    model: Any = None
    aic: float = float("nan")
    omega_1: float | None = None
    se_omega_1: float | None = None
    wald_p: float | None = None
    deja_vecino: str | None = None
    error: str = ""

    @property
    def estimado(self) -> bool:
        return self.model is not None and not self.error

    @property
    def transitorio(self) -> bool | None:
        return None if self.wald_p is None else self.wald_p >= 0.05

    @property
    def en_palabras(self) -> str:
        """Qué ES esta configuración, dicho para alguien que la ve por primera
        vez. `Q2/2008×5` es un código, no una frase: quien no conozca la
        convención no puede saber si son cinco escalones, cinco impulsos, o un
        escalón de orden cinco.
        """
        n = self.n_escalones
        base = ("**un escalón en el nivel** a partir de " if n == 1 else
                f"**{n} escalones consecutivos en el nivel** a partir de ") \
            + f"**{self.fecha}**"
        if n > 1:
            base += f" — un `step` con ω de orden s={n-1}"
        if self.transitorio is None:
            return base
        if self.transitorio:
            return (base + f", y como la ganancia no se distingue de cero, el "
                    f"nivel **vuelve a la línea base** tras {n-1} período(s): "
                    f"efecto TRANSITORIO")
        return (base + f", con ganancia ω(1)={self.omega_1:+.4f}: el nivel "
                f"**se queda desplazado** — efecto PERMANENTE")

    @property
    def ic95(self) -> tuple[float, float] | None:
        if self.omega_1 is None or self.se_omega_1 is None \
                or not np.isfinite(self.se_omega_1):
            return None
        return (self.omega_1 - 1.96 * self.se_omega_1,
                self.omega_1 + 1.96 * self.se_omega_1)

    @property
    def ic_excluye_cero(self) -> bool:
        ic = self.ic95
        return bool(ic and (ic[0] > 0 or ic[1] < 0))


@dataclass
class ConjuntoCandidatos:
    candidatos: list[Candidato]
    dominio: str = "generic"
    info: InfoExtramuestral = field(default_factory=InfoExtramuestral)
    umbral_activo: float = UMBRAL_ACTIVO
    banda_aic: float = BANDA_AIC

    @property
    def vivos(self) -> list[Candidato]:
        return [c for c in self.candidatos if c.estimado]

    @property
    def mejor(self) -> Candidato | None:
        v = self.vivos
        return min(v, key=lambda c: c.aic) if v else None

    @property
    def empatados(self) -> list[Candidato]:
        """Los que caen dentro de la banda de AIC del mejor."""
        m = self.mejor
        if m is None:
            return []
        return sorted([c for c in self.vivos if c.aic - m.aic <= self.banda_aic],
                      key=lambda c: c.aic)

    @property
    def identificado(self) -> bool:
        """El dato identifica la configuración si sólo una queda en la banda."""
        return len(self.empatados) <= 1

    @property
    def unica_construida(self) -> bool:
        """Sólo se llegó a estimar una configuración: no hubo comparación.

        `identificado` sale True igual, y por eso hay que distinguirlo: una cosa
        es que las alternativas se construyeran y perdieran, y otra que no
        existiera ninguna que comparar. Publicar lo segundo como lo primero es
        la precisión fabricada que esta herramienta dice no querer fabricar
        (BUG-0083).
        """
        return len(self.vivos) <= 1

    @property
    def rango_ganancia(self) -> tuple[float, float] | None:
        g = [c.omega_1 for c in self.empatados if c.omega_1 is not None]
        return (min(g), max(g)) if g else None

    @property
    def discrepan_en_la_lectura(self) -> bool:
        """Los empatados no coinciden en permanente/transitorio."""
        lect = {c.transitorio for c in self.empatados if c.transitorio is not None}
        return len(lect) > 1

    @property
    def el_mas_estrecho_es_el_mas_corto(self) -> bool:
        """La trampa de §2.1: la ventana corta da el IC más estrecho.

        Cuando además es la única que excluye el cero, su lectura «permanente»
        es sospechosa de ser un artefacto del arranque tardío.
        """
        emp = [c for c in self.empatados if c.se_omega_1 is not None
               and np.isfinite(c.se_omega_1)]
        if len(emp) < 2:
            return False
        estrecho = min(emp, key=lambda c: c.se_omega_1)
        corto = max(emp, key=lambda c: c.arranque_resid)
        return estrecho is corto and estrecho.ic_excluye_cero

    @property
    def implausible_por_dominio(self) -> list[Candidato]:
        """Candidatos cuya lectura choca con la clase de serie."""
        if self.dominio not in DOMINIOS_SIN_CAIDA_PERMANENTE:
            return []
        return [c for c in self.empatados
                if c.transitorio is False and (c.omega_1 or 0) < 0]

    @property
    def concuerda_con_lo_extramuestral(self) -> bool | None:
        """¿La naturaleza declarada coincide con lo que dice el contraste?

        La explicación tiene que explicar la FORMA, no sólo la fecha.
        `None` si no hay información o no hay candidato con el que comparar.
        """
        if not self.info.naturaleza:
            return None
        ref = self.fijado_por_lo_extramuestral or self.mejor
        if ref is None or ref.transitorio is None:
            return None
        return ref.transitorio == (self.info.naturaleza == "transitorio")

    @property
    def fijado_por_lo_extramuestral(self) -> Candidato | None:
        """El candidato cuyo arranque coincide con la fecha declarada."""
        if not self.info.desde:
            return None
        # Se empareja por FECHA y no por prefijo de la etiqueta: la etiqueta es
        # un código compuesto («Q3/2008×4») y un `startswith` sobre ella ata la
        # lógica al formato de presentación, que es justo lo que se ha cambiado.
        return next((c for c in self.vivos if c.fecha == self.info.desde), None)


def arranques_candidatos(z: Sequence[float], extremos_idx: Sequence[int],
                         d: int = 0,
                         umbral_activo: float = UMBRAL_ACTIVO,
                         tope_atras: int = 6,
                         tope_delante: int = 6) -> list[tuple[int, int]]:
    """Los arranques admisibles y su longitud, acotados por el MECANISMO.

    Parameters
    ----------
    z             : residuos TIPIFICADOS.
    extremos_idx  : índices 0-based de los residuos extremos del episodio.
    d             : diferenciación regular del modelo.
    umbral_activo : |z| a partir del cual un residuo contiguo cuenta como parte
                    del suceso aunque no sea extremo.
    tope_atras    : cuántos períodos como máximo se extiende hacia ATRÁS el
                    arranque.
    tope_delante  : cuántos períodos como máximo se extiende hacia DELANTE el
                    final. (BUG-0083.)

    Returns
    -------
    Lista de `(arranque_0based, n_escalones)`, ordenada por arranque y longitud.

    La marcha es **simétrica**, y tiene que serlo: el mecanismo que justifica
    extender hacia atrás —con d≥1 un suceso del nivel reparte su firma entre
    residuos contiguos, y el extremo puede caer en cualquiera de ellos— no
    distingue el signo del desplazamiento. Acotar sólo por la izquierda hacía
    que un suceso con la cola por DEBAJO del umbral de extremo, pero por encima
    del de activo, no generase nunca la configuración larga: exactamente el caso
    que esta herramienta existe para tratar (BUG-0083).

    Ambas marchas paran en el primer vecino inactivo, así que el conjunto es
    pequeño: sin vecinos activos degenera en un único candidato, que es el
    comportamiento anterior exacto.
    """
    zz = np.asarray(z, dtype=float)
    ext = sorted(int(i) for i in extremos_idx)
    if not ext:
        return []
    primero, ultimo = ext[0], ext[-1]

    # hacia atrás desde el PRIMER extremo, mientras siga ACTIVO
    arranques = [primero]
    s = primero - 1
    while s >= 0 and (primero - s) <= tope_atras and abs(zz[s]) >= umbral_activo:
        arranques.append(s)
        s -= 1

    # hacia delante desde el ÚLTIMO extremo, con el mismo criterio
    finales = [ultimo]
    e = ultimo + 1
    while e < zz.size and (e - ultimo) <= tope_delante \
            and abs(zz[e]) >= umbral_activo:
        finales.append(e)
        e += 1

    out = []
    for a in sorted(arranques):
        for f in sorted(finales):
            n = (f - a + 1) - int(d) + 1
            if n >= 1:
                out.append((a, n))
    # un arranque puede repetir longitud si el tope la satura; se deduplica
    # conservando el orden.
    return list(dict.fromkeys(out))


def evalua_configuraciones(model_base, candidatos: Sequence[tuple[int, int]],
                           d: int = 0, dominio: str = "generic",
                           info: "InfoExtramuestral | None" = None,
                           freq: int = 4, start_year: int = 2004,
                           start_per: int = 1,
                           umbral_vecino: float = 0.0,
                           umbral_activo: float = UMBRAL_ACTIVO) -> ConjuntoCandidatos:
    """Estima cada configuración candidata y monta el conjunto.

    `model_base` es el modelo AJUSTADO **sin** la intervención. `candidatos`
    viene de `arranques_candidatos` en índices 0-based de RESIDUOS.
    """
    import fue
    from art.interventions import test_intervention, check_intervention_fit

    desfase = int(d) + int(getattr(model_base, "D", 0)) * int(freq)
    base_itvs = [i for i in (model_base.interventions or [])
                 if i.type in ("cos", "sin", "alter")]

    def etiqueta(at_resid0):
        o = at_resid0 + desfase              # 0-based en la SERIE
        a = start_year + (start_per - 1 + o) // freq
        q = (start_per - 1 + o) % freq + 1
        return f"Q{q}/{a}" if freq == 4 else f"{q}/{a}"

    out = []
    for at_r, n_om in candidatos:
        c = Candidato(arranque_resid=at_r + 1, n_escalones=n_om,
                      fecha=etiqueta(at_r),
                      etiqueta=f"{etiqueta(at_r)}×{n_om}")
        try:
            itv = fue.Intervention("step", at=at_r + desfase,
                                   omega=[0.0] * n_om,
                                   omega_free=[True] * n_om)
            kw = {}
            # `refactor` va en la lista y no es un extra: `fue.Model` lo tiene
            # a 1.0 por defecto y la suite estima sobre 100·log(y), así que un
            # clon que no lo copie sale en OTRA escala. Los candidatos serían
            # comparables entre sí y su AIC incomparable con el del modelo base
            # —sobre FOOD_UEM, −2002 frente a −8,20— (BUG-0085).
            for a in ("ar", "ma", "ar_s", "ma_s", "ar_free", "ma_free",
                      "ar_s_free", "ma_s_free", "ar_f", "ma_f", "d", "D",
                      "ifadf", "mu", "estimate_mu", "boxlam", "refactor"):
                v = getattr(model_base, a, None)
                if v is not None:
                    kw[a] = v
            m = fue.Model(model_base.series,
                          interventions=base_itvs + [itv], **kw)
            m.fit()
            idx = len(base_itvs)
            tr = test_intervention(m, idx)
            # 0 = el de la política. Aquí el valor clavado era 2.5, un TERCER
            # número para el mismo concepto —3.0 en la escalera, 2.5 aquí— y ni
            # uno era el de la regla (BUG-0087). El umbral del vecino es una
            # decisión del método y vive en `policy`, no repartida en tres
            # defaults literales.
            ck = [x for x in check_intervention_fit(
                m, umbral_vecino=umbral_vecino or None)
                  if x.itv_index == idx]
            c.model, c.aic = m, float(m.aic)
            c.omega_1, c.se_omega_1, c.wald_p = tr.omega_1, tr.se_omega_1, tr.wald_p
            c.deja_vecino = ck[0].vecino_anomalo if ck else None
        except Exception as e:                              # pragma: no cover
            c.error = f"{type(e).__name__}: {e}"
        out.append(c)

    return ConjuntoCandidatos(candidatos=out, dominio=dominio,
                              info=info or InfoExtramuestral(),
                              umbral_activo=umbral_activo)


def describe_configuraciones(conj: "ConjuntoCandidatos"):
    """El conjunto entero, con el rango de la ganancia como titular.

    **No elige cuando el dato no identifica.** Publicar una configuración y su
    error típico cuando hay seis empatadas es fabricar una precisión que no
    existe — y la que el AIC saca tiende a ser la de ventana corta, que es la
    lectura equivocada con la etiqueta más convincente.
    """
    from art.describe import Description

    emp = conj.empatados
    L = ["### Configuraciones del incidente que el dato admite", ""]

    if not conj.vivos:
        return Description(
            summary="### Configuraciones del incidente\n\nNinguna estimable.",
            figure_b64=None, recommendation="Revisa el episodio detectado.",
            data=dict(identificado=False, candidatos=[]))

    L += ["*Se lee «fecha×N» como **N escalones consecutivos en el nivel a "
          "partir de esa fecha**, es decir un `step` con ω de orden N−1.*", "",
          "| configuración | AIC | ΔAIC | ω(1) | SE | IC 95% | vecino | lectura |",
          "|---|---|---|---|---|---|---|---|"]
    m0 = conj.mejor.aic
    for c in sorted(conj.vivos, key=lambda x: x.aic):
        ic = c.ic95
        ic_s = f"[{ic[0]:+.3f}, {ic[1]:+.3f}]" if ic else "—"
        se_s = f"{c.se_omega_1:.3f}" if c.se_omega_1 is not None else "—"
        w = f"{c.omega_1:+.4f}" if c.omega_1 is not None else "—"
        lect = ("—" if c.transitorio is None else
                "transitorio" if c.transitorio else "**PERMANENTE**")
        marca = "" if c in emp else " *(fuera de banda)*"
        L.append(f"| **{c.etiqueta}**{marca} | {c.aic:.2f} | {c.aic - m0:+.2f} "
                 f"| {w} | {se_s} | {ic_s} | {c.deja_vecino or '—'} | {lect} |")
    L.append("")

    if conj.identificado and conj.unica_construida:
        u = emp[0] if emp else conj.mejor
        L += ["#### Sólo se construyó **una** configuración", "",
              f"→ {u.en_palabras}", "",
              "Esto **no** es que el dato la identifique: es que no hubo nada "
              "que comparar. La marcha del mecanismo no encontró ningún vecino "
              "activo —ni antes ni después— con el que formar una alternativa, "
              f"así que el umbral de activo ({conj.umbral_activo:g}σ) o el "
              "episodio de partida acotan el conjunto a un solo elemento. "
              "Baja el umbral si crees que el suceso tiene cola."]
    elif conj.identificado:
        u = emp[0] if emp else conj.mejor
        L += ["#### El dato **sí** identifica la configuración", "",
              f"→ {u.en_palabras}", "",
              f"Se construyeron {len(conj.vivos)}; sólo una cae dentro de la "
              "banda de AIC y las demás quedan fuera."]
    else:
        rg = conj.rango_ganancia
        L += [f"#### El dato **NO** identifica la configuración", "",
              f"**{len(emp)} configuraciones dentro de {conj.banda_aic:g} puntos "
              "de AIC.** Elegir una y publicar su error típico sería fabricar "
              "una precisión que no existe."]
        if rg:
            L.append(f"\nLa ganancia a largo plazo está entre **{rg[0]:+.4f}** y "
                     f"**{rg[1]:+.4f}** según cuál se tome — y eso es la "
                     "incertidumbre de verdad, no el SE de ninguna de ellas.")
        if conj.discrepan_en_la_lectura:
            L.append("\n⚠ **Las empatadas ni siquiera coinciden en si el efecto "
                     "es permanente o transitorio.**")
        if conj.el_mas_estrecho_es_el_mas_corto:
            L.append("\n⚠ **Cuidado con la de arranque más tardío**: tiene el "
                     "intervalo más estrecho y es la única que excluye el cero. "
                     "No es suerte — acortar la ventana quita parámetros y "
                     "aprieta la identificación DENTRO del modelo mientras "
                     "empeora la línea base, porque deja fuera lo que precede "
                     "al suceso. La lectura más segura es aquí la más "
                     "sospechosa.")

    impl = conj.implausible_por_dominio
    if impl:
        L += ["", "#### Lectura de dominio", "",
              f"La serie es de clase `{conj.dominio}`, donde una caída "
              "**permanente** de nivel es poco usual. Eso resta plausibilidad "
              "a: " + ", ".join(f"**{c.etiqueta}**" for c in impl) +
              ". No las elimina —una heurística de clase no decide "
              "econometría— pero pide respaldo antes de aceptarlas."]

    L += ["", "#### Información extramuestral", ""]
    if not conj.info.hay:
        L += ["**No aportada.** Es lo único que identifica de verdad: la fecha "
              "en que empezó el suceso fija el arranque, y con el arranque fijo "
              "el resto se estima.", "",
              "❓ ¿Consta cuándo empezó el incidente y de qué naturaleza fue? "
              "Un cambio de impuestos o de metodología explica un escalón "
              "**permanente**; una huelga o un temporal, un impulso "
              "**transitorio**. La herramienta no lo sabe y no debe suponerlo."]
    else:
        quien = conj.info.aportada_por or "sin atribuir"
        L.append(f"Aportada por **{quien}**"
                 + (f" · desde **{conj.info.desde}**" if conj.info.desde else "")
                 + (f" · **{conj.info.naturaleza}**" if conj.info.naturaleza else "")
                 + (f"\n\n> {conj.info.fuente}" if conj.info.fuente else ""))
        fij = conj.fijado_por_lo_extramuestral
        if fij is not None:
            L.append(f"\nLa fecha declarada fija la configuración en "
                     f"**{fij.etiqueta}**.")
        elif conj.info.desde:
            L.append(f"\n⚠ La fecha declarada (**{conj.info.desde}**) no "
                     "coincide con ningún arranque candidato. O el suceso "
                     "empezó antes de lo que el mecanismo admite, o la fecha "
                     "es otra.")
        conc = conj.concuerda_con_lo_extramuestral
        if conc is False:
            L.append("\n⚠ **La explicación no concuerda con el contraste.** Se "
                     f"declara *{conj.info.naturaleza}* y la ganancia dice lo "
                     "contrario. La explicación tiene que explicar la FORMA, no "
                     "sólo la fecha: si no la cubre, no vale para elegir.")
        elif conc is True:
            L.append("\n✓ La explicación **concuerda** con el contraste de "
                     "ganancia.")

    if conj.identificado and conj.unica_construida:
        u = emp[0] if emp else conj.mejor
        rec = ("Sólo se construyó una configuración, así que no hay "
               "identificación que afirmar: " + u.en_palabras +
               ". Si el suceso puede tener cola, baja `umbral_activo`.")
    elif conj.identificado:
        rec = f"El dato identifica la configuración: {emp[0].en_palabras}."
    elif conj.fijado_por_lo_extramuestral is not None \
            and conj.concuerda_con_lo_extramuestral is not False:
        rec = ("El dato no identifica, pero la información extramuestral sí: "
               + conj.fijado_por_lo_extramuestral.en_palabras + ".")
    else:
        rec = ("**No elijas por AIC.** El dato no identifica la configuración y "
               "las empatadas discrepan en la lectura. Aporta la fecha de "
               "inicio del suceso, o publica el rango de la ganancia en vez de "
               "un número.")

    return Description(
        summary="\n".join(L), figure_b64=None, recommendation=rec,
        data=dict(
            identificado=conj.identificado,
            unica_construida=conj.unica_construida,
            n_construidas=len(conj.vivos),
            n_empatados=len(emp),
            rango_ganancia=list(conj.rango_ganancia) if conj.rango_ganancia else None,
            discrepan=conj.discrepan_en_la_lectura,
            trampa_ventana_corta=conj.el_mas_estrecho_es_el_mas_corto,
            dominio=conj.dominio,
            implausibles=[c.etiqueta for c in impl],
            info=dict(desde=conj.info.desde, naturaleza=conj.info.naturaleza,
                      fuente=conj.info.fuente,
                      aportada_por=conj.info.aportada_por),
            concuerda=conj.concuerda_con_lo_extramuestral,
            candidatos=[dict(etiqueta=c.etiqueta, aic=c.aic, omega_1=c.omega_1,
                             se_omega_1=c.se_omega_1, wald_p=c.wald_p,
                             ic95=list(c.ic95) if c.ic95 else None,
                             fecha=c.fecha, en_palabras=c.en_palabras,
                             deja_vecino=c.deja_vecino,
                             transitorio=c.transitorio,
                             en_banda=c in emp, error=c.error)
                        for c in conj.candidatos]))
