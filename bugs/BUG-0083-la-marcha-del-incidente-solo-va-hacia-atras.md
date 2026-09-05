---
id: BUG-0083
title: La marcha del incidente sólo va HACIA ATRÁS — un suceso cuya cola queda bajo el umbral no genera nunca la configuración larga, y el informe concluye «el dato SÍ identifica la configuración» sin haber comparado nada
status: fixed
severity: high
component: identification
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David / sesión guiada FOOD_UEM — incidente 12/2004
tags: [interventions, incident, episodes, reporting]
references:
  - src/art/configuracion.py:266 (arranques_candidatos), :296 (el bucle)
  - src/art/mcp_server.py:979 (incident_configurations)
  - bugs/BUG-0083-repro/repro.py
  - BUG-0030 (el arranque desplazado), BUG-0079 (no se puede construir lo identificado)
---

## Summary

`arranques_candidatos` acota el conjunto por el mecanismo, y eso está bien. Pero
lo acota **sólo por un lado**:

```python
primero, ultimo = ext[0], ext[-1]
arranques = [primero]
s = primero - 1
while s >= 0 and (primero - s) <= tope_atras and abs(zz[s]) >= umbral_activo:
    arranques.append(s); s -= 1
...
n = (ultimo - a + 1) - int(d) + 1
```

Se anda hacia atrás desde el PRIMER extremo mientras los vecinos sigan activos
(`|z| ≥ umbral_activo`), pero el final queda clavado en `ultimo`, el ÚLTIMO
extremo **por encima del umbral de extremo** (2.5 por defecto). No hay marcha
hacia delante con el criterio de «activo».

Consecuencia: si la cola del suceso se queda entre `umbral_activo` y el umbral de
extremo —que es justo el caso que la herramienta existe para tratar— **la
configuración larga no se construye jamás**.

## Impact

Los dos casos son el mismo mecanismo con el extremo en un sitio distinto, y la
herramienta trata uno y no el otro. Medido en la misma serie, FOOD_UEM:

| suceso | extremo | vecino enmascarado | ¿lo pilla? |
|---|---|---|---|
| 02-03/2017 | 03/2017, z=−3.80 | 02/2017, z≈+2.4, **antes** | **Sí** — enumera 2/2017×2 y acierta |
| 12/2004-01/2005 | 12/2004, z=+3.56 | 01/2005, z=−2.20, **después** | **No** — sólo enumera 12/2004×1 |

En el segundo caso el `.out` del modelo lo tiene delante y en letra grande:
*«Maximum 0.759425 at 12/2004 (observation 35)»*, *«Minimum −0.466594 at 1/2005
(observation 36)»* — el máximo y el mínimo de toda la serie de residuos,
consecutivos. La superposición lo confirma: con dos escalones **escala 0.9974** y
restos ≈0 en ambas fechas; con el escalón permanente que la herramienta propuso,
**escala 0.863** y el −0.47 de 01/2005 entero en los restos.

**Y el informe lo publica como si estuviera identificado.** Con una sola
candidata construida, la salida dice:

> *«#### El dato **sí** identifica la configuración … Sólo una cae dentro de la
> banda de AIC; las demás quedan fuera.»*

No hay «las demás». Afirmar identificación cuando la alternativa nunca se
construyó es exactamente la precisión fabricada que el docstring de esta
herramienta dice no querer fabricar: *«Publicar una y su error típico sería
fabricar una precisión que no existe»*.

## Reproduction

`bugs/BUG-0083-repro/repro.py` — sintético, determinista, sin datos ni motor.
Dos vectores de z idénticos salvo por el lado en que cae la cola:

```
cola DELANTE  (02-03/2017)
   z          = [0.2, -0.4, 0.3, 2.4, -3.8, -0.1, 0.3, -0.2]
   extremos   = [4]   (|z| >= 2.5)
   candidatas = [(3, 2), (4, 1)]   longitudes [2, 1]
   la de longitud 2 se enumera: SI

cola DETRAS   (12/2004-01/2005)
   z          = [0.2, -0.4, 0.3, -0.1, 3.56, -2.2, 0.3, -0.2]
   extremos   = [4]   (|z| >= 2.5)
   candidatas = [(4, 1)]   longitudes [1]
   la de longitud 2 se enumera: NO  <-- FALLA
```

## Fix (propuesto)

1. Marcha **simétrica**: extender `ultimo` hacia delante con el mismo criterio de
   `umbral_activo` y un `tope_delante` análogo a `tope_atras`. El mecanismo que
   justifica la marcha hacia atrás —con d=1 un suceso reparte su firma entre
   períodos contiguos— no distingue el signo del desplazamiento.
2. Cuando el conjunto tenga **una sola** candidata, no decir «el dato sí
   identifica la configuración». Decir que sólo se construyó una, y por qué.

---

## Fix (aplicado, 2026-09-04)

**1. Marcha simétrica** en `arranques_candidatos`. Se añade `tope_delante` y una
segunda marcha, desde el ÚLTIMO extremo hacia delante, con el mismo criterio de
`umbral_activo` y parando en el primer vecino inactivo. La longitud pasa a
calcularse contra el final extendido:

    n_escalones = (final − arranque + 1) − d + 1

Sigue sin ser una rejilla: ambas marchas paran en el primer vecino inactivo, y
**sin vecinos activos el conjunto degenera en el candidato único de antes**, que
es el comportamiento anterior exacto. Los duplicados que puede producir un tope
saturado se eliminan conservando el orden.

**2. «Sólo se construyó una» ya no se publica como «el dato identifica».** Nueva
propiedad `ConjuntoCandidatos.unica_construida` (`len(vivos) <= 1`), y tres
ramas nuevas en el informe: el bloque, la recomendación y el `data` dict
(`unica_construida`, `n_construidas`). El texto dice qué pasó y qué hacer:

> #### Sólo se construyó **una** configuración
> Esto **no** es que el dato la identifique: es que no hubo nada que comparar.
> La marcha del mecanismo no encontró ningún vecino activo —ni antes ni
> después— … Baja el umbral si crees que el suceso tiene cola.

Y la rama que sí afirma identificación ahora dice **cuántas** se construyeron,
que es el dato que faltaba para poder creérsela.

`umbral_activo` se pasa desde `incident_configurations` hasta el
`ConjuntoCandidatos`, para que el aviso cite el umbral que de verdad se usó y no
el defecto.

**3. De propina, «1 escalones».** La rama de candidata única se imprime mucho más
ahora, y la frase se montaba sin mirar el número.

## Validation — resultado

**(a) El repro sale 0**, y los dos casos espejo enumeran ya la configuración de
dos escalones:

```
cola DELANTE  candidatas = [(3, 2), (4, 1)]   longitudes [2, 1]   SI
cola DETRAS   candidatas = [(4, 1), (4, 2)]   longitudes [1, 2]   SI
```

Nótese la asimetría que **queda**, y que es la correcta: con la cola delante
cambia el ARRANQUE, con la cola detrás cambia el FINAL. En los dos casos sale el
mismo par anidado de longitudes {1, 2}.

**(b) `tests/test_bug_0083_marcha_simetrica.py`**, 14 pruebas: los dos lados, la
igualdad de longitudes entre los casos espejo, la degeneración a un candidato sin
vecinos activos, la parada en el primer hueco, el tope, el borde derecho del
array, la deduplicación, y las cuatro del informe.

**(c) Sobre el caso real, FOOD_UEM 12/2004** (`m02_ar1`, `umbral_activo=1.5`):

| configuración | AIC | ΔAIC | ω(1) | lectura |
|---|---|---|---|---|
| **12/2004×2** | −2002.44 | +0.00 | +0.0045 | transitorio |
| 12/2004×1 | −2002.01 | +0.43 | +0.0088 | — |

Antes sólo existía la segunda fila, y el informe la publicaba como identificada.
Ahora la larga se construye, gana por AIC, y —esto es lo importante— **la
herramienta no la canta como identificada**: las dos caen dentro de la banda, así
que dice que no identifica y publica el rango de la ganancia. Que es el
resultado honesto: son dos modelos anidados separados por 0.43 puntos.

Y el otro camino también quedó comprobado sobre datos reales: el episodio
aislado de 10/2007 sale ahora con *«Sólo se construyó una configuración … no
hubo nada que comparar»* en vez de *«el dato sí identifica»*.
