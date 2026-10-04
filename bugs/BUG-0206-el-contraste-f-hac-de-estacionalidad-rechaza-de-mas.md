---
id: BUG-0206
title: El contraste F HAC de estacionalidad (detect_seasonality) rechaza de más bajo H0 — 19-28 % al 5 % nominal en series mensuales sin estacionalidad; un estudio de tamaño y potencia, compartido con drvarma
status: open
severity: high
component: seasonal_detection
found_in: 0.2.3.dev0
fixed_in:
reported: 2026-10-04
reporter: David / Claude — al llevar la F de art a la desestacionalización de drvarma (drvarma BUG-0003)
tags:
  - estudio
  - estacionalidad
  - hac
  - tamaño
  - potencia
  - drvarma
references:
  - src/art/seasonal_detection.py (detect_seasonality, _newey_west_hac)
  - src/art/identification.py ≈754 (la decisión estacional)
  - src/art/diagnosis.py (estacionalidad en los residuos)
  - src/art/describe.py, src/art/mcp_server.py (consumidores de seasonal_detected)
  - bugs/BUG-0206-repro/hac_size.py
  - drvarma-python src/drvarma/deseason.py (usa la F de MCO; espera este estudio)
---

## Summary

`detect_seasonality` decide si hay estacionalidad con una F de Wald sobre los
s−1 armónicos (en las diferencias), con la covarianza de Newey-West
(Bartlett, 1-3 retardos) y valores críticos de la F(s−1, n−s). Bajo H0
—una serie I(1) sin estacionalidad— rechaza mucho más del 5 % nominal. La F
de MCO de la misma regresión está en su sitio.

**Es dudoso que sea un bug y no un rasgo conocido del contraste:** los Wald
robustos con muchas restricciones en muestras moderadas rechazan de más. Por
eso se plantea como ESTUDIO, de tamaño y de potencia, para decidir qué
contraste usan art y drvarma, que deben compartir el mecanismo.

## Reproduction

`bugs/BUG-0206-repro/hac_size.py` (la función de art, sin tocar; 400
réplicas por celda; niveles I(1), diferencias AR(φ), λ=1):

| n | φ (diferencias) | F HAC (art) | F MCO | F media HAC | F media MCO |
|---|---|---|---|---|---|
| 120 | 0 | **0,275** | 0,030 | 1,55 | 1,00 |
| 120 | +0,6 | 0,083 | 0,033 | 1,06 | 0,76 |
| 120 | −0,4 | **0,250** | 0,092 | 1,53 | 1,10 |
| 216 | 0 | **0,190** | 0,058 | 1,34 | 1,04 |
| 216 | +0,6 | 0,065 | 0,040 | 1,00 | 0,79 |
| 216 | −0,4 | **0,170** | 0,115 | 1,29 | 1,12 |
| 400 | 0 | 0,102 | 0,060 | 1,15 | 1,01 |
| 400 | +0,6 | 0,022 | 0,037 | 0,87 | 0,77 |
| 400 | −0,4 | 0,048 | 0,070 | 1,03 | 1,02 |

Bajo H0 la F media debería ser ≈1. Con 18 años de datos mensuales (n=216) y
diferencias que son ruido blanco —un paseo aleatorio, el caso de libro—,
art declara estacionalidad en una de cada cinco series que no la tienen.

## Root cause (lo medido; la explicación completa es parte del estudio)

1. **Sin corrección de grados de libertad.** El sándwich es HC0: las
   varianzas de los coeficientes salen al 0,94 de las de MCO con n=216, justo
   (n−k)/n = 204/216. Falta el factor n/(n−k) (HC1).
2. **La variabilidad del propio estimador de la covarianza** con 11
   restricciones infla la cola de la F: White sin retardos ya da F media 1,19,
   y Bartlett con 3 retardos, 1,32. La F(11, n−12) no la recoge.
3. Con diferencias de autocorrelación positiva (φ=+0,6), las dos F se
   vuelven conservadoras: el HAC compensa justo donde no hace falta.

## Impact

`seasonal_detected` decide la ruta estacional en la identificación
(`identification.py`), marca «estacionalidad en los residuos» en la
diagnosis (`diagnosis.py`, `full_report.py`) y la usan `describe` y el MCP.

Queda por mirar si algún paso posterior —el LR de los armónicos dentro del
modelo, la poda— corrige el falso positivo antes de que llegue al modelo
final. Si lo corrige, el daño es de ruta y de tiempo. Si no, es de
especificación.

drvarma iba a adoptar esta F para su modo `deseason="auto"`, por coherencia
con art. Se revirtió al medir esto: sigue con la F de MCO, que es la del C, a
la espera de este estudio.

## El estudio (propuesta)

**Tamaño y potencia, los dos.** Un contraste que no rechaza de más pero no
detecta una estacionalidad real no sirve.

- **Candidatos:**
  1. la F HAC actual;
  2. HC1 / HAC con la corrección n/(n−k);
  3. HAC con valores críticos *fixed-b* (Kiefer-Vogelsang);
  4. preblanqueo: un AR(p) a los residuos de la regresión, y la F sobre los
     residuos filtrados (o MCG factible);
  5. la F de MCO tal cual;
  6. el LR de los armónicos dentro del modelo ARMA (el que el ajuste de fue
     daría), como referencia.
- **Dinámicas de las diferencias** (las mismas para el tamaño y la
  potencia): ruido blanco, AR(1), AR(2), AR(3), MA(1), ARMA(1,1) y
  ARMA(2,1). Para cada una, parámetros de signo positivo y negativo, y alguno
  cerca de la frontera de estacionariedad o de invertibilidad. Los AR(2) y
  AR(3) incluyen raíces complejas, cuyo pico espectral puede caer cerca de
  una frecuencia estacional y confundirse con estacionalidad.
- **Bajo H0 (tamaño):** n ∈ {120, 216, 400}, con todas esas dinámicas y,
  aparte, un AR estacional: estacionalidad ESTOCÁSTICA, que no es la
  determinista que se busca.
- **Potencia, en TODAS las dinámicas, no solo en el ruido blanco:** el patrón
  determinista se suma a una serie cuyas diferencias son AR(1), AR(2), AR(3),
  MA(1), ARMA(1,1) o ARMA(2,1), con los mismos parámetros que en el tamaño.
  El ruido blanco es una celda más, la de referencia. La rejilla es candidato
  × dinámica × parámetros × n × amplitud (creciente, en proporción a la
  desviación típica de las diferencias) × forma del patrón (concentrado en una
  frecuencia o repartido en todas). Para cada candidato, una curva de potencia
  por dinámica y por n. La pregunta es si algún candidato pierde potencia,
  o la gana de forma espuria, precisamente cuando hay dinámica, que es el caso
  de los datos reales.
- **Criterio:** el tamaño, cerca del 5 % en todas las celdas, y entre los que
  lo cumplen, la potencia.
- **Datos reales:** la decisión de cada candidato en las series de la suite
  (IPC_ES, IPC3, WTI, el trigo anual como control s=1).

Un mismo mecanismo para art y drvarma: la función que salga (o su puerto)
la usan las dos.

## Validation

El script del estudio con su tabla de tamaño y potencia por candidato, y la
decisión escrita. Después, que `hac_size.py` dé tamaños cerca del 5 % con el
contraste elegido, en art y en drvarma.
