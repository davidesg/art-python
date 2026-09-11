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
           "describe_configuraciones", "normaliza_naturaleza",
           "NATURALEZAS", "UMBRAL_ACTIVO", "BANDA_AIC"]


# Un residuo cuenta como ACTIVO —parte del suceso aunque no sea extremo— a
# partir de esta |z|. Fijado en 1σ por el analista. No es un umbral de detección
# sino de EXTENSIÓN: dice hasta dónde puede llegar hacia atrás un suceso ya
# detectado por sus extremos.
UMBRAL_ACTIVO = 1.0

# Dos configuraciones dentro de esta banda de AIC se consideran empatadas.
BANDA_AIC = 2.0

# Clases de serie donde un cambio PERMANENTE de nivel es poco usual.
DOMINIOS_SIN_CAIDA_PERMANENTE = ("price_index",)


# LAS TRES LECTURAS DE UN SUCESO EN EL NIVEL — BUG-0155.
#
# Eran dos, y el analista no tenía casilla. Sobre ITCER el suceso de 2008-09 es
# una caída seguida de una RECUPERACIÓN PARCIAL: el nivel no vuelve —no es
# transitorio— y tampoco se queda donde cayó —no es el permanente que el
# contraste rotula—. Obligar a elegir entre dos respuestas equivocadas convierte
# en ruido la única entrada de este nodo cuya evidencia no está en los datos.
#
# La tercera casilla existe ahora porque existe el instrumento que la mide: la
# ganancia NETA de dos intervenciones (`interventions.net_gain`, BUG-0157). Una
# casilla que nada puede contrastar sería peor que no tenerla.
NATURALEZAS = ("permanente", "transitorio", "recuperacion_parcial")

_ACENTOS = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")


def normaliza_naturaleza(v: str) -> str:
    """La forma canónica de lo que el analista escribió.

    El esquema publica un `enum`, así que un cliente conforme manda el valor
    exacto. Esto es para los que no: «recuperación parcial», «Recuperacion-
    Parcial» y `recuperacion_parcial` son la misma declaración, y rechazar las
    dos primeras sería castigar al analista por una tilde.
    """
    t = (v or "").strip().lower().translate(_ACENTOS)
    t = t.replace("-", "_").replace(" ", "_")
    while "__" in t:
        t = t.replace("__", "_")
    return {"parcial": "recuperacion_parcial",
            "recuperacion": "recuperacion_parcial"}.get(t, t)


@dataclass
class InfoExtramuestral:
    """Lo que el analista sabe del mundo y la herramienta no.

    `fuente` es obligatoria si se declara `naturaleza`: no se puede afirmar que
    un suceso fue permanente sin decir por qué se sabe. Y `aportada_por` deja
    constancia de quién lo dijo — en autónomo será «LLM», que es el dato que
    permite después distinguir lo sabido de lo inventado.
    """

    desde: str = ""              # fecha en que empezó el suceso, "QN/AAAA"
    naturaleza: str = ""         # ver NATURALEZAS
    fuente: str = ""             # qué se está citando
    aportada_por: str = ""       # "analista" | "LLM" | ""

    def __post_init__(self):
        if self.naturaleza and not self.fuente.strip():
            raise ValueError(
                "declarar `naturaleza` sin `fuente` no vale: afirmar que un "
                "suceso fue permanente o transitorio exige decir por qué se "
                "sabe. Sin fuente, deja `naturaleza` vacía y que decida el "
                "contraste de ganancia.")
        if self.naturaleza:
            canon = normaliza_naturaleza(self.naturaleza)
            if canon not in NATURALEZAS:
                raise ValueError(
                    f"naturaleza={self.naturaleza!r} no vale. Las tres lecturas "
                    f"de un suceso en el NIVEL son:\n"
                    f"  · `permanente`          el nivel se queda desplazado\n"
                    f"  · `transitorio`         el nivel vuelve a la línea base\n"
                    f"  · `recuperacion_parcial` vuelve EN PARTE — ni una cosa "
                    f"ni la otra\n"
                    f"O déjalo vacío y que decida el contraste de ganancia. "
                    f"(La descripción del suceso va en `fuente`, no aquí.)")
            self.naturaleza = canon

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
    fecha_fin: str = ""          # el ÚLTIMO período que cubre: "Q4/2008"
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
            if n == 1:
                # BUG-0157: «vuelve tras 0 período(s)» no es una vuelta, es que
                # no pasó nada. Con un solo ω no hay transitorio que decir.
                return (base + ", y la ganancia no se distingue de cero — con "
                        "un solo ω eso no es una vuelta: es que **el suceso no "
                        "deja efecto medible**")
            return (base + f", y como la ganancia no se distingue de cero, el "
                    f"nivel **vuelve a la línea base** en **{self.fecha_fin}**, "
                    f"tras {n-1} período(s): efecto TRANSITORIO")
        return (base + f", con ganancia ω(1)={self.omega_1:+.4f}: el nivel "
                f"**se queda desplazado** — efecto PERMANENTE")

    @property
    def fin_resid(self) -> int:
        """La última observación que la especificación cubre (1-based)."""
        return self.arranque_resid + self.n_escalones - 1

    @property
    def puede_expresar_una_vuelta(self) -> bool:
        """¿Admite esta especificación la lectura «el nivel VUELVE»? — BUG-0157.

        Con un solo ω, ω(1) = ω₀: las dos únicas lecturas posibles son «el
        nivel se desplaza» y «no pasó nada». La vuelta necesita un segundo ω
        que cancele al primero. Así que sobre una configuración de un escalón
        **«permanente» sale por CONSTRUCCIÓN**, y decir que contradice al
        analista es atribuirle una discrepancia que produce la propia forma.
        """
        return self.n_escalones >= 2

    @property
    def donde_situa_la_vuelta(self) -> str:
        """Y con n ω tampoco la BUSCA: la SITÚA — BUG-0157.

        ω(1)=0 significa que el nivel vuelve a la base en el último período que
        la especificación cubre, y en ningún otro. La forma no tiene libertad
        sobre CUÁNDO: contrastar «transitorio» aquí es contrastar «transitorio
        **con vuelta en esta fecha**». Si la vuelta real es posterior, el
        contraste no puede verla y el rechazo no significa lo que parece.
        """
        return self.fecha_fin or ""

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
    def referencia(self) -> "Candidato | None":
        """El candidato contra el que se juzga la información extramuestral.

        Si el analista dio la fecha, el suyo. Si no, **el que mejor AIC tiene**
        — y eso hay que decirlo, porque entonces la comparación no es con una
        configuración que el analista haya nombrado (BUG-0157).
        """
        return self.fijado_por_lo_extramuestral or self.mejor

    @property
    def vuelta_mas_tardia(self) -> str:
        """La vuelta más tardía que ALGUNA configuración construida admite.

        La marcha hacia delante para en el primer residuo tranquilo, así que el
        conjunto entero tiene un techo. Si la vuelta que el analista describe
        cae después, **ninguna** de las configuraciones puede expresarla: no es
        que el dato la desmienta, es que no se ha contrastado.
        """
        con_vuelta = [c for c in self.vivos if c.puede_expresar_una_vuelta]
        if not con_vuelta:
            return ""
        return max(con_vuelta, key=lambda c: c.fin_resid).fecha_fin

    @property
    def el_contraste_no_alcanza_la_vuelta(self) -> bool:
        """Se declara `transitorio` y el contraste lo RECHAZA — BUG-0157.

        Parece una discrepancia y no lo es. ω(1)=0 dice «el nivel vuelve **en
        el último período que la especificación cubre**», y en ningún otro: la
        forma no tiene libertad sobre CUÁNDO. Rechazarlo descarta *esa* vuelta,
        no cualquier vuelta. Una recuperación posterior al tramo le es
        sencillamente invisible.

        Y como `naturaleza` no lleva fecha de vuelta, **la discrepancia nunca se
        puede establecer**: el analista dice «transitorio», el contraste
        responde sobre «transitorio con vuelta en tal fecha», y son dos
        afirmaciones distintas.

        Sobre ITCER: referencia `Q2/2008×3`, que cubre hasta Q4/2008, contra un
        analista que describía una recuperación desde 2009Q2 — dos trimestres
        fuera del tramo. «Permanente» salía por construcción.

        El caso extremo lo da `puede_expresar_una_vuelta`: con un solo ω no hay
        vuelta posible en NINGUNA fecha.
        """
        if self.info.naturaleza != "transitorio":
            return False
        ref = self.referencia
        return ref is not None and ref.transitorio is False

    @property
    def la_tercera_lectura_no_cabe_en_este_contraste(self) -> bool:
        """Se declara `recuperacion_parcial` — BUG-0155.

        El contraste de una sola intervención tiene DOS casillas: ω(1)=0 dice
        que el nivel volvió, ω(1)≠0 que no volvió del todo. Y «no volvió del
        todo» es compatible con la recuperación parcial **y** con el permanente
        puro: no las separa.

        Lo que las separa es la ganancia NETA de la caída y la vuelta, que es
        otro instrumento y otro modelo —dos intervenciones—. Así que aquí no hay
        concordancia que afirmar ni que negar: hay que mandar al sitio correcto.
        """
        return self.info.naturaleza == "recuperacion_parcial"

    @property
    def concuerda_con_lo_extramuestral(self) -> bool | None:
        """¿La naturaleza declarada coincide con lo que dice el contraste?

        La explicación tiene que explicar la FORMA, no sólo la fecha.
        `None` si no hay información, si no hay candidato con el que comparar,
        **o si la forma contrastada no admite la lectura declarada** — que es
        el caso que BUG-0157 arregla: un contraste que sólo puede dar una
        respuesta no está contrastando nada.
        """
        if not self.info.naturaleza:
            return None
        if self.la_tercera_lectura_no_cabe_en_este_contraste:
            return None
        ref = self.referencia
        if ref is None or ref.transitorio is None:
            return None
        if self.el_contraste_no_alcanza_la_vuelta:
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

    # BUG-0172: incluye el consumo de `ifadf`. `d` llega por parámetro, así que
    # se respeta si difiere del modelo, pero el resto sale de la cuenta única.
    from art.identification import desfase_observaciones
    desfase = (int(d) - int(getattr(model_base, "d", 0) or 0)
               + desfase_observaciones(model_base))
    # BUG-0150. Este filtro se quedaba sólo con la estructura estacional y
    # tiraba TODAS las intervenciones de suceso ya estimadas, así que cada
    # candidato se evaluaba contra un base que no era el del analista. Sobre
    # ITCER los tres AIC salían PEORES que el del propio base al añadir un
    # parámetro. Se hereda lo ya estimado y se retira sólo lo que cae sobre el
    # mismo suceso.
    from art.escalera import hereda_del_base
    _ats = [at for at, _n in candidatos]
    _centro = (min(_ats) + max(_ats)) // 2 + desfase if _ats else None
    _radio = (max(_ats) - min(_ats)) + max((n for _a, n in candidatos), default=1)
    base_itvs, retiradas = hereda_del_base(model_base, at_estudiado=_centro,
                                           ventana=max(1, int(_radio)))

    def etiqueta(at_resid0):
        o = at_resid0 + desfase              # 0-based en la SERIE
        a = start_year + (start_per - 1 + o) // freq
        q = (start_per - 1 + o) % freq + 1
        return f"Q{q}/{a}" if freq == 4 else f"{q}/{a}"

    out = []
    for at_r, n_om in candidatos:
        c = Candidato(arranque_resid=at_r + 1, n_escalones=n_om,
                      fecha=etiqueta(at_r),
                      fecha_fin=etiqueta(at_r + n_om - 1),
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


def describe_configuraciones(conj: "ConjuntoCandidatos",
                            veredicto: bool = True):
    """El conjunto entero, con el rango de la ganancia como titular.

    `veredicto=False` cuando esta salida va DENTRO de otra que ya publica el
    suyo — BUG-0154. La llamada 2 de `guided_intervention` empotra este bloque,
    añade su sección «Veredicto» y remata con esta recomendación: la misma
    frase, tres veces, en la respuesta más larga del nodo. Repetir entierra lo
    que NO se repite —las configuraciones rivales, la lectura de dominio, el
    aviso de que el dato no identifica— y es lo que hace que el nodo se lea
    «enrevesado».

    Suelto —`incident_configurations`— sigue publicando el suyo: ahí es lo
    único que hay.

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
        L += ["#### Sólo se construyó **una** configuración", ""]
        L += ([f"→ {u.en_palabras}", ""] if veredicto else
              [f"→ **`{u.etiqueta}`**", ""])
        L += ["Esto **no** es que el dato la identifique: es que no hubo nada "
              "que comparar. La marcha del mecanismo no encontró ningún vecino "
              "activo —ni antes ni después— con el que formar una alternativa, "
              f"así que el umbral de activo ({conj.umbral_activo:g}σ) o el "
              "episodio de partida acotan el conjunto a un solo elemento. "
              "Baja el umbral si crees que el suceso tiene cola."]
    elif conj.identificado:
        u = emp[0] if emp else conj.mejor
        L += ["#### El dato **sí** identifica la configuración", ""]
        # Empotrado, este bloque aporta el HECHO —cuál gana y con cuánto
        # margen—; la lectura entera es del veredicto de quien lo empotra.
        L += ([f"→ {u.en_palabras}", ""] if veredicto else
              [f"→ **`{u.etiqueta}`**", ""])
        L += [f"Se construyeron {len(conj.vivos)}; sólo una cae dentro de la "
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
        ref = conj.referencia
        if conj.la_tercera_lectura_no_cabe_en_este_contraste:
            # BUG-0155. Antes esto ni siquiera se podía declarar: el analista
            # tenía que elegir entre dos respuestas equivocadas, y el aviso de
            # discrepancia se disparaba comparando lo que había dicho con un
            # contraste que no tenía su casilla.
            L.append(
                "\nℹ **Declaras la tercera lectura, y este contraste tiene dos "
                "casillas.** Con una sola intervención, ω(1)=0 dice «el nivel "
                "volvió» y ω(1)≠0 dice «no volvió del todo» — y lo segundo es "
                "compatible con la recuperación parcial **y** con el permanente "
                "puro: no las separa. No hay aquí concordancia que afirmar ni "
                "que negar.")
            L.append(
                "\nLo que las separa es la **ganancia NETA**: modeliza la caída "
                "y la vuelta como **dos intervenciones** —encadenando por "
                "`base_pre_path`— y contrasta H₀ Σᵢωᵢ(1)=0 con "
                "`test_interventions(..., ganancia_neta=[i, j])`. Devuelve la "
                "fracción recuperada, que es el número que tu lectura afirma.")
        elif conj.el_contraste_no_alcanza_la_vuelta:
            # BUG-0157. Aquí el aviso decía «la explicación no concuerda con el
            # contraste», y era falso: el contraste no puede ver la vuelta que
            # el analista describe, así que «permanente» sale por construcción.
            # Desautorizar la información extramuestral con un contraste que no
            # alcanza el suceso enseña al analista a desconfiar de lo único que
            # este nodo existe para incorporar.
            de_quien = ("" if conj.fijado_por_lo_extramuestral is not None else
                        " — la de **mejor AIC**, no una que hayas nombrado: no "
                        "diste `evento_desde`")
            if not ref.puede_expresar_una_vuelta:
                L.append(
                    f"\n⚠ **El contraste no puede ver la vuelta.** Se declara "
                    f"*transitorio*, y la configuración con la que se compara "
                    f"—**{ref.etiqueta}**{de_quien}— tiene **un solo ω**, así que "
                    f"ω(1)=ω₀: sus dos únicas lecturas son «el nivel se "
                    f"desplaza» y «no pasó nada». La vuelta necesita un segundo "
                    f"ω que cancele al primero. **«Permanente» sale aquí por "
                    f"construcción, no del dato.**")
            else:
                L.append(
                    f"\n⚠ **El contraste SITÚA la vuelta, no la busca.** Se "
                    f"declara *transitorio*, y la configuración con la que se "
                    f"compara —**{ref.etiqueta}**{de_quien}— sólo admite una "
                    f"lectura transitoria: que el nivel vuelva en "
                    f"**{ref.donde_situa_la_vuelta}**, el último período que "
                    f"cubre. Rechazar ω(1)=0 descarta *esa* vuelta, **no "
                    f"cualquier vuelta**. Si la recuperación que describes es "
                    f"posterior, el contraste no la ve y «permanente» sale por "
                    f"construcción.")
            tope = conj.vuelta_mas_tardia
            if tope:
                L.append(
                    f"\nY **ninguna** de las {len(conj.vivos)} configuraciones "
                    f"construidas sitúa la vuelta más allá de **{tope}**: la "
                    f"marcha hacia delante para en el primer residuo tranquilo, "
                    f"así que el conjunto no alcanza una recuperación diferida. "
                    f"Para un suceso con vuelta tardía hacen falta **dos "
                    f"intervenciones** —la caída y la vuelta— y el contraste de "
                    f"su ganancia **NETA** "
                    f"(`test_interventions(..., ganancia_neta=[i, j])`).")
        elif conc is False:
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

    # BUG-0157. La recomendación decía «el dato identifica la configuración:
    # … PERMANENTE» sin matiz, mientras el analista acababa de declarar
    # transitorio. Que el contraste no alcance la vuelta no invalida la
    # configuración —sigue siendo la que mejor explica lo que se ve— pero sí
    # invalida leer «PERMANENTE» como si desmintiera al analista.
    if conj.la_tercera_lectura_no_cabe_en_este_contraste:
        rec += ("\n\nℹ Y **lo que declaras no lo decide esta llamada**: una "
                "recuperación parcial es la ganancia NETA de dos "
                "intervenciones. Construye la caída con la forma de arriba, "
                "encadena la vuelta desde su `.pre`, y contrasta "
                "`test_interventions(..., ganancia_neta=[i, j])`.")
    elif conj.el_contraste_no_alcanza_la_vuelta:
        _r = conj.referencia
        _d = (f" en **{_r.donde_situa_la_vuelta}**"
              if _r is not None and _r.puede_expresar_una_vuelta else "")
        rec += ("\n\n⚠ Y **«permanente» aquí no desmiente tu «transitorio»**: "
                f"esta forma sólo sabe contrastar la vuelta{_d}. Si la "
                "recuperación que describes es posterior, modeliza el suceso "
                "como **dos intervenciones** —la caída y la vuelta— y contrasta "
                "su ganancia NETA; o declara `permanente` sólo si de verdad "
                "sostienes que el nivel no volvió.")

    return Description(
        summary="\n".join(L), figure_b64=None, recommendation=rec,
        data=dict(
            identificado=conj.identificado,
            unica_construida=conj.unica_construida,
            n_construidas=len(conj.vivos),
            n_empatados=len(emp),
            rango_ganancia=list(conj.rango_ganancia) if conj.rango_ganancia else None,
            discrepan=conj.discrepan_en_la_lectura,
            contraste_no_alcanza_la_vuelta=conj.el_contraste_no_alcanza_la_vuelta,
            tercera_lectura=conj.la_tercera_lectura_no_cabe_en_este_contraste,
            vuelta_mas_tardia=conj.vuelta_mas_tardia or None,
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
