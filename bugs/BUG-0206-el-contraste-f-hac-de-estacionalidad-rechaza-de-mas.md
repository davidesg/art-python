---
id: BUG-0206
title: El contraste F HAC de estacionalidad (detect_seasonality) rechaza de más bajo H0 — 19-28 % al 5 % nominal en series mensuales sin estacionalidad; un estudio de tamaño y potencia, compartido con drvarma
status: fixed
severity: high
component: seasonal_detection
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
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

## Resultados del estudio (2026-10-04)

`research/seasonal_test/` (`README.md` y las tablas `results_n*.md`). Seis
candidatos, 16 dinámicas ARMA de las diferencias más un AR estacional,
n = 120, 216 y 400. Tamaño con 2000 réplicas; potencia bruta y ajustada por
tamaño, con 500.

| contraste | peor tamaño | tamaño mediano | celdas > 0,075 | potencia ajustada media |
|---|---|---|---|---|
| hac_art (el actual) | 0,290 | 0,086 | 25/48 | 0,611 |
| hac_hc1 | 0,246 | 0,068 | 21/48 | 0,611 |
| ewc (fixed-b) | **0,065** | 0,048 | **0/48** | 0,469 |
| fgls (preblanqueo AR por AIC, p ≤ 6) | 0,102 | 0,062 | 7/48 | **0,674** |
| ols (el de drvarma y el C) | 0,202 | 0,052 | 21/48 | 0,552 |
| lr con los órdenes verdaderos (oráculo) | 0,102 | 0,064 | 13/48 | 0,680 |

- **El contraste actual de art no solo rechaza de más: su tamaño depende de
  la dinámica**, del 0 % (AR(1) φ=+0,9) al 29 % (ARMA(2,1) con el pico
  espectral en una frecuencia estacional). La corrección HC1 apenas lo
  mueve: el problema es el estimador de Bartlett con 11 restricciones.
- **La F de MCO de drvarma tampoco vale con dinámica:** 13–20 % cuando el
  AR tiene autocorrelación negativa o un pico estacional, y ~0 % con
  autocorrelación positiva fuerte.
- **El preblanqueo (fgls) tiene la potencia del LR oráculo** en todas las
  dinámicas, sin conocer los órdenes. Su tamaño está entre 4,4 % y 8 %,
  salvo en el MA(1) casi no invertible (θ=0,9): 10 % con n=120. Subir el
  orden máximo del AR a 12 o 13 lo empeora.
- **EWC mantiene el tamaño en todas las celdas**, pero pierde un tercio de
  la potencia con n ≤ 216.
- **La estacionalidad estocástica** (AR estacional) la rechazan todos entre
  el 43 % y el 95 %. Distinguirla de la determinista es cosa de la decisión
  de la diferencia estacional, no de este contraste.

(Propuesta inicial: el preblanqueo como mecanismo común. Superada por la
decisión de abajo.)

## Decisión (2026-10-04): cada F donde le corresponde

Decisión del analista, en el contexto de art: **la identificación es un
cribado inicial**. Lo que detecta se elabora después dentro del modelo,
según las prácticas convencionales: contrastes y poda de los armónicos,
`test_seasonal_simplification`, `seasonal_param_analysis`.

En ese papel los dos errores no cuestan lo mismo. Un falso positivo mete
armónicos que luego se podan; un falso negativo deja fuera la
estacionalidad desde el principio. Comparada con la F de MCO, la F HAC tiene
más potencia (0,61 frente a 0,55 ajustada; 0,66 frente a 0,55 bruta). Su
tamaño es peor con diferencias ruido blanco o MA, pero la de MCO también
falla con dinámica: 13–20 % con autocorrelación negativa o un pico
estacional. Ninguna domina. **Se mantiene la F HAC en la identificación.**

**En la diagnosis de residuos, no.** Ese uso no estaba en el estudio y se
midió aparte: `diagnosis.diagnose` aplica el contraste a los residuos (d=0),
y su veredicto entra en `residuals_ok`. Eso decide si el bucle de atípicos
para y si el modelo sale «limpio». Ahí H0 es justo el ruido blanco, el peor
caso del HAC: sobre residuos blancos, 30 % de falsas alarmas con n=120,
18 % con n=216 y 12 % con n=400. Con la F de MCO, 5 %, 4 % y 6 %. Y el HAC
no aporta nada, porque la blancura la juzga Ljung-Box aparte. **En los
residuos, la F de MCO.**

Implementado:
- `detect_seasonality(..., test="hac" | "ols")`, con `"hac"` por defecto:
  la identificación no cambia.
- `diagnosis.diagnose` pide `test="ols"`.
- drvarma decide su `deseason="auto"`, que es una decisión de
  identificación, con la misma F HAC: `deseason.seasonal_f_hac`, puerto que
  da la F y el p de art a 1e-9. Es el mecanismo compartido.
- Tests: `tests/test_bug_0206_contraste_estacional.py` en art (el defecto
  sigue siendo HAC, `"ols"` es la F de MCO, la diagnosis pide `"ols"`, falsas
  alarmas < 9 % con residuos blancos). En drvarma,
  `test_auto_decides_with_arts_identification_test`.

El estudio (`research/seasonal_test/`) queda como respaldo de por qué cada F
está donde está. Si algún día se quiere una sola F con buen tamaño y la
potencia del HAC, el candidato es el preblanqueo (fgls), con la potencia del
LR oráculo.

