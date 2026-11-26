---
id: BUG-0267
title: guided_intervention construye una forma sin pasar por la Llamada 2, y la diagnosis sugiere esa forma (pulse) cuando la Llamada 2 dice escalón
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.6
fixed_in: unreleased
reported: 2026-11-26
reporter: David / sesión Plata México — producción de plata 1701-1810, 2026-11-26
tags:
  - intervencion
  - forma
  - treadway
references:
  - src/art/describe.py:2245-2271 (diagnosis: «Intervenciones sugeridas», forma por consecutividad de los extremos de los RESIDUOS)
  - src/art/policy.py:667-679 (decide_form: la misma regla, fuente única del carril autónomo y de suggest_intervention_form)
  - src/art/mcp_server.py:9696 (guided_intervention: la Llamada 3 se ejecuta sin que haya corrido la Llamada 2 para esa fecha)
  - bugs/BUG-0030 (índice de residuos frente a posición en la serie original con d+D*s)
  - bugs/BUG-0267-repro/repro.py
---

## Summary

La forma de una intervención se puede decidir sin el nodo que la decide. Dos
defectos encadenados. (A) La diagnosis de `confirm_and_estimate` imprime
«Intervenciones sugeridas: 1803 … pulse (observación aislada)»: una FORMA,
elegida por una regla que mira si el extremo de los RESIDUOS es aislado o tiene
un vecino extremo. Esa regla está **invertida cuando el modelo está
diferenciado**: con d=1, un escalón en el nivel deja UN residuo extremo
(aislado) y un impulso en el nivel deja DOS (+ y −). La propia Llamada 2 lo
dice («L impulsos del nivel se ven como L+1 extremos»). Así, la diagnosis
recomienda pulse justo para el caso que es un escalón. (B) `guided_intervention`
con `form` construye y estima la Llamada 3 aunque la Llamada 2 no haya corrido
nunca para esa fecha, y no dice antes de estimar qué forma admite el dato. El
analista que sigue la sugerencia de la diagnosis llega a la Llamada 3 con la
forma equivocada, y sólo DESPUÉS Treadway le dice que la representación falla.

(C) Hallado al revisar el bug: la llamada que escribe la opción A,
`suggest_intervention_form(inp_path=…, date="1803")`, no lleva `output_path`,
que la herramienta exige. Copiada tal cual falla, y el camino que funciona es
el atajo: `guided_intervention(form=…)` con la forma del texto.

**No es una regresión.** El repro sale igual en art-v0.2.5, art-v0.2.6, antes
de #27, antes de #29 y en master (86cf9a2). La pista de forma de la diagnosis
está desde el primer commit (junio) y la «forma sugerida» de la opción A desde
septiembre; la escalera de Ockham (F3) sustituyó la regla de adyacencia en las
herramientas de intervención, pero no en la diagnosis. Dos motores para la
misma forma, y uno al revés con diferencias.

## Impact

Alto. Es el camino natural del carril guiado: la diagnosis sugiere una forma con
nombre, y la puerta del nodo acepta esa forma sin pasar por su veredicto. En la
sesión (producción de plata de Nueva España, 1701-1810, ARIMA(0,1,1)) el
asistente construyó un impulso en 1803 a partir de la sugerencia: ω=+23,2
(t=2,3), el JB pasó y la diagnosis salió APROBADA, pero Treadway falló (residuo
en 1803 +1,66σ, 1804 +2,44σ). La Llamada 2, pedida después por el analista,
dio un escalón permanente en 1803 (1/1803×1): ω=+45,2 % (t=3,8), Treadway ✓,
AIC 861,80 frente a 870,28. Un analista que se fiara de la diagnosis APROBADA
habría adoptado la forma errónea con la mitad del efecto, y en este caso el
suceso es sustantivo (la vuelta del azogue tras la paz de Amiens), no ruido.
La regla de `decide_form` es la misma (policy.py:667), así que el carril
autónomo hereda el error sobre todo modelo con d ≥ 1.

## Reproduction

Fixture: `bugs/BUG-0267-repro/AGPROD_ma1.inp` (log producción de plata de Nueva
España, anual 1701-1810, n=110, ARIMA(0,1,1) sin intervención; mayor residuo
1803, z=+3,39).

1. `confirm_and_estimate(... p=0, q=1, d=1)` → «Intervenciones sugeridas:
   1803 (obs 102, z=+3.39): pulse (observación aislada)».
2. `guided_intervention(inp, date="1803")` (Llamada 2) → «1/1803×1 — un
   escalón en el nivel a partir de 1/1803», ω(1)=+45,2, PERMANENTE.
3. Sobre una copia limpia, `guided_intervention(inp, date="1803",
   form="pulse", n_omega=1, output_path=...)` sin Llamada 2 previa → construye
   y estima el impulso; no menciona la forma admitida antes del modelo; Treadway
   ✗ después.

    python3 bugs/BUG-0267-repro/repro.py   # exits 1 while open

## Root cause

(A) describe.py:2245-2271 y policy.py:667-679 deciden la forma por la
consecutividad de los extremos de los residuos, sin tener en cuenta d (ni D·s).
La regla es correcta para d=0 y está invertida para d=1: el escalón en el nivel
es un impulso en ∇ (un extremo) y el impulso en el nivel es (1−B) en ∇ (dos
extremos de signo opuesto). (B) mcp_server.py:9696: la Llamada 3 no comprueba
si la Llamada 2 se hizo para esa fecha.

## Fix

Hecho (mínimo; la escalera no se toca):
- (A) `describe.py`: la diagnosis da las FECHAS para intervenir, sin forma, y
  dice que la forma la estima la escalera en niveles. `intervention_hints`
  conserva la clave `form`, a None.
- (A, C) La opción A ya no nombra una forma, y su llamada va completa:
  `suggest_intervention_form(inp_path, output_path=<stem>_itv<fecha>.inp,
  date)`, con la Llamada 2 como alternativa.
- (B) La Llamada 3 avisa ANTES de estimar cuando la forma no viene de la
  Llamada 2 ni de la escalera (`form="auto"`) para ese modelo y fecha
  (registro en memoria del servidor, `_FORMA_DE_ART`). La decisión sigue
  siendo del analista: avisa, no bloquea.
- Queda fuera, para su propio bug: el bucle automático del pipeline
  (`policy.decide_interventions`) sigue con la regla de adyacencia (recibe d);
  cambiarlo mueve el carril autónomo y hay que medirlo.

Propuesta original:

Propuesto: (A) que la diagnosis NO sugiera una forma, sino la fecha y la puerta
(«1803: pásalo por guided_intervention(date=…)»), o que use
`incident_configurations` como la Llamada 2; y que `decide_form` tenga en cuenta
d (o se sustituya por la misma configuración). (B) que la Llamada 3, si no hay
Llamada 2 registrada para esa fecha en el guion, la ejecute (o al menos imprima
su veredicto) ANTES de estimar, y avise cuando la forma pedida no es la que el
dato admite; la decisión sigue siendo del analista.

## Validation

`bugs/BUG-0267-repro/repro.py` sale con 0. Test: sobre AGPROD_ma1.inp la
diagnosis no sugiere pulse para 1803 (o sugiere el escalón), y la Llamada 3 con
form="pulse" sin Llamada 2 muestra «1/1803×1» antes del modelo estimado. Test de
la regla: series simuladas con d=1, un escalón y un impulso en el nivel; la
forma sugerida coincide con la verdadera en los dos casos.
