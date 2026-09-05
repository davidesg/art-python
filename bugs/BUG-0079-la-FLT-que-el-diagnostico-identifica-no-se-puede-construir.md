---
id: BUG-0079
title: La FLT que el diagnóstico identifica no se puede construir desde la superficie MCP — `incident_configurations` nombra un step con ω de orden s, el motor lo soporta y fue lo estima, pero ninguna herramienta lo expone; y con ello el Wald de ganancia nula de BUG-0071/0072 queda inalcanzable desde el carril guiado
status: fixed
severity: high
component: mcp-tools
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David / sesión guiada FOOD_UEM (HICP alimentos UEM, 2002:01-2019:12)
tags:
  - interventions
  - transfer-function
  - guided-lane
  - wiring
references:
  - src/art/mcp_server.py (suggest_intervention_form, confirm_and_estimate, build_model)
  - src/art/pipeline.py:556 (_make_model, extra_itvs con n_omega) y :168-181 (_write_inp)
  - src/art/interventions.py:464 (Joint Wald) y el gate `if k > 1`
  - bugs/BUG-0079-repro/repro.py
  - BUG-0071, BUG-0072 (construyeron el Wald de ganancia nula)
  - BUG-0030 (el arranque del incidente, mismo nodo)
---

## Summary

`incident_configurations` identifica el incidente y lo devuelve **nombrado como
una función de transferencia**:

> *«Se lee «fecha×N» como N escalones consecutivos en el nivel, es decir un
> `step` con ω de orden N−1»*
> → **2/2017×2**, ω(1)=−0.0015, IC [−0.008, +0.005], lectura TRANSITORIO

Y no hay ninguna herramienta que la construya. `suggest_intervention_form` sólo
acepta `form ∈ {pulse, step, ramp, auto}` —ninguna lleva orden—, y
`confirm_and_estimate` no tiene parámetros de intervención. El analista recibe la
respuesta y no puede aplicarla.

**El eslabón de abajo está entero**, y eso es lo que convierte esto en cableado y
no en una carencia: `_make_model` acepta la tupla `(at, form, n_omega)`,
`_write_inp` escribe el orden y los coeficientes, `fue.inp.load` lo relee y fue
lo estima. Escrito el `.inp` a mano, el modelo estima sin tocar nada y la
ecuación se imprime bien:

```
  + (0.5700  − 0.7236·B) ξₜ^{S,2/2017}
```

## Impact

Tres capas, de menor a mayor.

**1. El analista acaba en la forma equivocada.** Sin poder declarar el orden, la
ruta `auto` aplica la regla simple. Sobre FOOD_UEM propuso un ESCALÓN PERMANENTE
donde el dato dice episodio transitorio. La diferencia no es cosmética: afirma
que el índice de alimentos de la UEM quedó un 0.86% por debajo de su trayectoria
**para siempre**, en vez de un bache de dos meses que revierte.

**2. El apaño degrada el ajuste.** Montado como intervenciones sueltas se llega
al mismo óptimo, pero sólo si el analista sabe montar las dos y con qué signo.
Las tres especificaciones de un solo escalón que la superficie sí permite son
todas peores:

| modelo | forma | σ̂ₐ | ℓ | AIC | BIC |
|---|---|---|---|---|---|
| m03_i1 | escalón permanente 03/2017 | 0.2157% | 24.52 | −21.05 | 26.14 |
| m04_ep17 | escalón permanente 02/2017 | 0.2178% | 22.53 | −17.06 | 30.12 |
| m05_ep17b | dos escalones sueltos (apaño) | 0.2124% | 27.88 | −25.75 | 24.81 |
| m06_flt17 | `(ω₀−ω₁B)·step 2/2017` (a mano) | 0.2124% | 27.88 | −25.75 | 24.81 |

**3. Y deja huérfano un contraste que el proyecto ya construyó.** El Wald conjunto
de ganancia nula —H₀: ω(1)=0, lo que separa transitorio de permanente— está en
`interventions.py:464` con la puerta `if k > 1`, donde `k` es el número de ω
libres **en una intervención**. Como el carril guiado no puede construir ninguna
con k>1, **ese contraste no se alcanza nunca desde ahí**. Es el contraste que
BUG-0071 y BUG-0072 arreglaron y afinaron; existe y no llega.

Comprobado en la sesión: con el apaño de dos intervenciones sueltas
`test_interventions` no lo emite (hubo que sacarlo a mano de la covarianza del
`.out`: ω(1)=−0.154, SE=0.339, χ²=0.205, p=0.65). Declarado como una intervención
de dos ω, sale solo:

```
ω(1)=-0.1536 [desplazamiento permanente del nivel]  Wald χ²(1)=1.227  p=0.2679
H₀: ganancia nula ⇒ efecto TRANSITORIO  (no se rechaza)
```

## Reproduction

`bugs/BUG-0079-repro/repro.py` — determinista, sin datos externos, sin estimar.
Sale 1 con la cadena cortada. Comprueba las tres capas:

```
== A. Herramientas MCP que crean o modifican intervenciones
  suggest_intervention_form    expone orden de omega: NO
  confirm_and_estimate         expone orden de omega: NO
  build_model                  expone orden de omega: NO
  formas admitidas: ['pulse', 'step', 'ramp', 'auto']

== B. _make_model / _write_inp / fue.inp.load
  _make_model menciona n_omega: True
  intervención construida: type=step  n_omega=2  -> orden 1
  línea de órdenes de omega en el .inp: '1'
  releído por fue.inp.load: n_omega=2
  -> fue acepta la forma. El motor NO es el problema.

== C. El Wald de ganancia nula
    k = len(free_om_idx)
    if k > 1:

CADENA CORTADA en la superficie MCP: suggest_intervention_form,
confirm_and_estimate, build_model
```

Camino manual que lo confirma sobre datos reales (HICP alimentos UEM,
2002:01-2019:12, hoja `Uem` de `Datos_Históricos_Inflacion_UEM_Países.xlsx`):

1. `incident_configurations(m02_ar1.inp, at=182, umbral_activo=1.5)`
   → identifica **2/2017×2**, transitorio.
2. `suggest_intervention_form(date="02/2017", form="auto")`
   → *«La fecha no cae en ningún episodio detectado; forma decidida por la regla
   simple»* → un escalón permanente. No hay forma de pedirle el orden.
3. Editar el `.inp` a mano: ndet 13→12, quitar `step 3 2017`, poner la línea de
   órdenes de ω a `... 0 1`, y fundir los dos bloques en uno con dos
   coeficientes **con el signo del convenio** (fue guarda ω(B)=ω₀−ω₁B, así que
   el −0.723614 del escalón suelto entra como **+0.723614**).
4. `estimate_and_diagnose` → estima, y `test_interventions` ya emite el Wald.

## Root cause

Cableado, no motor. `n_omega` existe en `_make_model` (documentado en su propio
docstring: *«extra_itvs : list of (at_0based, form_str) or (at_0based, form_str,
n_omega) tuples»*) y no lo propaga ninguna herramienta MCP. La ruta `auto` de
`suggest_intervention_form` sube a la escalera sólo si su detector de episodios
ve el episodio, y ese detector usa |z|≥3: en FOOD_UEM el arranque real (02/2017)
tenía z≈+2.4, así que no lo vio. Es decir, la ruta que existe para tratar los
episodios es ciega justo en el caso que motiva su existencia — un suceso cuyo
arranque queda por debajo del umbral, que es el escenario que BUG-0030 y el
propio `incident_configurations` documentan.

## Fix (propuesto)

1. `suggest_intervention_form`: parámetro `n_omega: int = 1` (o `orden: int = 0`),
   propagado a `extra_itvs` como la tupla de tres. Es la pieza que falta.
2. Que `form="auto"` acepte la configuración de `incident_configurations` como
   entrada —fecha de arranque y longitud— en vez de volver a decidirla con el
   detector de episodios y su umbral. Hoy hay dos criterios distintos para la
   misma pregunta y no se hablan.
3. Cuando la ruta auto no vea episodio pero `incident_configurations` sí lo haya
   identificado, decirlo en la salida en vez de aplicar la regla simple en
   silencio. (Hoy lo dice a medias: *«la fecha no cae en ningún episodio
   detectado»*, sin mencionar que hay otra herramienta que sí lo detectó.)

## Validation

- `bugs/BUG-0079-repro/repro.py` debe salir 0 cuando A quede cableado.
- Un test que construya el episodio por la vía MCP y compruebe que
  `test_interventions` emite el Wald de ganancia nula (hoy no lo emite).
- Comparación de ajuste: la vía MCP debe alcanzar ℓ=27.88 / AIC=−25.75 sobre
  FOOD_UEM, no los −21.05 de la regla simple.

---

## Fix (aplicado, 2026-09-04)

**1. `suggest_intervention_form` gana `n_omega: int = 0`** (0 = automático, lo
decide la escalera; ≥1 = declaración del analista, que manda sobre ella). Se
propaga a `_make_model` como la tupla de tres `(at, form, n_omega)`. El orden es
**ortogonal a la forma**: multiplica a `pulse`, `step` o `ramp` por igual, y
`n_omega=0` conserva el comportamiento anterior exacto.

**2. El árbitro entre los dos criterios de forma.** La ruta `form="auto"` tomaba
la longitud del escalón de `residual_episodes`, que agrupa **sólo extremos**;
ahora la toma de `arranques_candidatos`/`evalua_configuraciones`, que extiende el
arranque **por el mecanismo** y es el criterio que `incident_configurations`
publica al analista. Eran dos respuestas a la misma pregunta sin árbitro.

**3. Y cuando el dato no identifica la configuración, lo dice.** Si hay
configuraciones empatadas dentro del margen, la salida avisa y remite a
`incident_configurations` antes de fijar la forma, en vez de aplicar la regla
simple en silencio.

Lo que **no** se tocó, y por qué: `confirm_and_estimate` y `build_model` siguen
sin parámetro de intervención, y es correcto. Ninguna de las dos crea
intervenciones desde la superficie — la primera las **hereda** del `.pre` base,
la segunda las **decide dentro**, por `policy.decide_interventions`, que ya
devuelve `(at, form, n_omega)`. La puerta que faltaba era una sola. El criterio
del repro se acotó a eso (bloque A: exige el orden sólo a las herramientas que
además exponen `date`/`at`/`form`).

## Validation — resultado

**(a) El repro sale 0.** Y se le añadió un bloque D de aceptación de extremo a
extremo —construir la FLT por la superficie MCP y comprobar que el Wald se
emite— para que deje de ser una comprobación de firmas.

**(b) `tests/test_bug_0079_flt_desde_mcp.py`**, 8 pruebas: la puerta, la
precedencia de `n_omega` sobre la escalera, la compatibilidad hacia atrás, el
Wald de ganancia nula emitido desde el carril guiado, el orden visible en la
ecuación renderizada, y el árbitro de configuración con su aviso.

**(c) Ajuste sobre FOOD_UEM, por la vía MCP** (base `m02_ar1`, `date="02/2017"`):

| vía | ℓ | AIC |
|---|---|---|
| MCP `n_omega=1` (regla simple, 02/2017) | 22.532013 | −17.064026 |
| escalón suelto 03/2017 (`m03_i1`) | 24.522866 | −21.045731 |
| **MCP `n_omega=2`** | **27.877243** | **−25.754485** |
| `m06_flt17` (el `.inp` a mano) | 27.877243 | −25.754485 |
| `m05_ep17b` (dos escalones sueltos) | 27.877243 | −25.754485 |

Se alcanza el objetivo. Y los tres últimos coinciden a diez decimales, que es la
comprobación que de verdad importa: la FLT de dos ω en 02/2017 y los dos
escalones sueltos en 02 y 03/2017 son **el mismo modelo reparametrizado**, no dos
ajustes parecidos. Lo que cambia es que uno se puede pedir y del otro hay que
saber el signo del convenio.
