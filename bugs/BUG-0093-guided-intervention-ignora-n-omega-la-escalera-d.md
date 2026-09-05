---
id: BUG-0093
title: guided_intervention ignora n_omega — la escalera de N escalones no se puede construir desde el carril guiado
status: fixed
severity: high
component: interventions
found_in: 0.1.12
fixed_in: 0.2.0
reported: 2026-09-05
reporter: David / sesión SERV_UEM — escalera 11/2015
tags:
  - interventions
  - escalera
  - n_omega
  - treadway
references:
  - src/art/mcp_server.py:5854 (guided_intervention Call 3 delega en suggest_intervention_form pasando n_omega tal cual)
  - src/art/mcp_server.py:5869 (cabecera "Se construye {form} de orden omega {max(1,int(n_omega))-1}")
  - src/art/mcp_server.py:5768 (docstring de guided_intervention: "n_omega: orden del numerador. 0 = uno solo")
  - src/art/mcp_server.py:6099-6102 (docstring de suggest_intervention_form: "n_omega: nº de coeficientes. form=step y n_omega=N => FLT de N escalones")
  - src/art/mcp_server.py:6204 (suggest_intervention_form: n_omega = max(1, int(n_omega)) if n_omega else 1)

---

## Summary

La Call 3 de `guided_intervention` ignora el peldaño pedido por el analista:
con `form="step"` y `n_omega=1` construye un **escalón simple (omega orden 0)** en
vez de la FLT de 2 escalones. El reporte lo confiesa en su propia cabecera
("Se construye step de orden omega 0"), y el modelo resultante es idéntico al del
escalón simple. La regla de Treadway («si el vecino queda >2sigma, sube de
peldaño») ordena añadir un escalón, pero desde el carril guiado no hay forma
de hacerlo: el analista queda atrapado en el peldaño bajo.

## Impact

Rompida la escalera de Treadway en su carril principal. Cuando un escalón
simple deja un vecino anómalo >2sigma (BUG-0087 ya detecta ese caso), la regla
manda subir de peldaño; `guided_intervention` no puede cumplirla, así que la
intervención se queda en una forma que la propia regla da por mala, o el
analista tiene que abandonar el flujo guiado y llamar a
`suggest_intervention_form` con otra semántica para lograrlo. Medido en
SERV_UEM 11/2015: el escalón simple deja 11/2015 en z=-2.14 >2sigma; la
escalera de 2 escalones existe y se estima (omega[0]=-0.4189,
omega[1]=+0.0567), pero el nodo guiado no la produce.

## Reproduction

En la sesión SERV_UEM (muestra 1/2002-12/2019), con el modelo
`services/work/SERV_UEM_m04_ma2_sar2.pre`:

1. `guided_intervention(inp_path=...m04...pre, date="11/2015", form="step",
   n_omega=1, output_path=...m08...)` -> responde "Se construye **step** de
   orden omega **0**" y estima `xi^{S,11/2015} = -0.4339`, AIC -129.69 —
   idéntico al escalón simple.
2. `suggest_intervention_form(inp_path=...m04..., date="11/2015",
   form="step", n_omega=2, output_path=...m09...)` -> construye la FLT de 2
   escalones: `(-0.4189 - 0.0567*B) xi^{S,11/2015}`, AIC -127.87.

El mismo analista, la misma intención, dos herramientas, dos modelos
distintos. La vía guiada produce el peldaño bajo; la directa, la escalera.

## Root cause

Hay **dos semánticas distintas para `n_omega`** y `guided_intervention` delega
sin convertir:

- `guided_intervention` documenta `n_omega` como **orden** del numerador
  ("0 = uno solo", mcp_server.py:5768), y su cabecera hace
  `orden = max(1, int(n_omega)) - 1` (mcp_server.py:5869).
- `suggest_intervention_form` documenta `n_omega` como **nº de coeficientes**
  ("n_omega=N => FLT de N escalones", mcp_server.py:6099) y lo aplica como
  `n_omega = max(1, int(n_omega))` (mcp_server.py:6204).

La Call 3 de `guided_intervention` llama a `suggest_intervention_form(...,
n_omega=n_omega)` (mcp_server.py:5854) **sin la conversión orden->coeficientes**.
Con `n_omega=1` (que en la semántica del carril guiado significa "orden 1 = 2
escalones"), la herramienta receptora lee "1 coeficiente = 1 escalón" y
construye el escalón simple. Para conseguir 2 escalones hay que pasar
`n_omega=2`, que en la semántica guiada significaría "orden 2 = 3 escalones" —
un número que el analista no tiene por qué descubrir y que contradice el
docstring que está leyendo.

## Fix

Unificar la semántica. Lo más limpio: que `guided_intervention` adopte la de
`suggest_intervention_form` (**nº de coeficientes omega**, `n_omega=0` = lo que
decida la escalera) y, al delegar, pase el valor sin más (ya coinciden). Como
mínimo, si se conserva la semántica de "orden", convertir en el puente:
`n_omega_coef = max(1, int(n_omega)) + 1` antes de delegar, y corregir la
cabecera para que no reste 1 de un número que el analista ya declaró como
orden.

## Validation

Reestimar SERV_UEM 11/2015 con `guided_intervention(..., form="step",
n_omega=1)` debe producir la FLT de 2 escalones (omega[0] y omega[1] libres),
no el escalón simple; y `n_omega=0` debe seguir delegando en la decisión de la
escalera. Test sintético en `bugs/BUG-0093-repro/`: mismo suceso de 2
períodos, verificar que el modelo del carril guiado y el de
`suggest_intervention_form` son idénticos para la misma petición.

---

## Fix (aplicado, 2026-09-05)

**El título del reporte dice «ignora n_omega», y el código NO lo ignora**:
`n_omega=k` construye k coeficientes, siempre. Pero el reporte tiene razón desde
el lado del analista, y por una razón peor: **el docstring de
`guided_intervention` documentaba el parámetro como el grado del polinomio**, y
cuenta coeficientes. El contrato prometía una cosa y el código hacía otra.

Y la Call 3 lo remataba informando «de orden ω {n_omega−1}», con lo que el
analista al que Treadway acababa de ordenar subir de peldaño leía «orden ω 0»
después de pedir `n_omega=1`, y concluía —razonablemente— que le habían ignorado.

**Gana la semántica de CONTAR**, y no por gusto: es la de las otras cuatro
piezas del nodo —`suggest_intervention_form` («nº de coeficientes ω»),
`incident_configurations` («N escalones consecutivos en el nivel»), la escalera,
y la propia Call 2, que devuelve el `n_omega` calculado listo para pegar—.
Cambiarla habría roto cuatro sitios para arreglar un docstring.

Tres cambios, todos de unidades:

1. **La cabecera habla en escalones**, con el orden entre paréntesis:
   `Se construye **step** de **2 escalón(es) en el nivel** (ω de orden 1)…`
2. **El docstring dice lo que el parámetro hace**, con la equivalencia escrita
   para quien venga del operador: **N escalones ⇔ ω(B) de orden N−1**.
3. El árbol de decisión pide «de CUÁNTOS ESCALONES», no «de qué orden».

## Validation — resultado

El repro se reescribió: el suyo exigía que `n_omega=1` diera dos escalones, que
es el lado perdedor de la ambigüedad. El nuevo comprueba lo que importa — que
haya UNA semántica, que esté documentada de verdad, y **que el bucle se cierre**:
lo que la Call 2 sugiere, la Call 3 lo construye. Sale 0.

`tests/test_bug_0093_0096_escalones_y_cola.py` — 20 pruebas (compartidas con
BUG-0096).
