---
id: BUG-0249
title: guided_intervention calibra sobre los residuos de un modelo que ya tiene órdenes, y no puede ver si esos órdenes los fabrica el anómalo
status: fixed
severity: medium
component: intervencion
found_in: 0.2.3.dev0
fixed_in: 0.2.3
reported: 2026-10-14
reporter: David / Claude — rodaje de art con el ejemplo lutkepohl_poskitt de sima (Minneapolis, carril guiado)
tags:
  - guided_intervention
  - calibracion
references:
  - src/art/mcp_server.py guided_intervention, llamadas 1 y 2
---

## Summary

La llamada 1 de `guided_intervention` pregunta «¿cambian los anómalos la
identificación?» y la contesta calibrando el correlograma de los RESIDUOS del
modelo que se le pasa. Si ese modelo ya tiene el orden que el anómalo pudo
fabricar, el orden ya se comió la señal y la calibración no puede verla: el
veredicto «no cambia la identificación» sale igual, sin aviso.

Minneapolis (ln, d = 1), AR(1) φ = 0.229 (t 2.34), m02:

| calibrado sobre | r(1) obs | r(1) sin anómalos |
|---|---|---|
| residuos del AR(1) (m02) | +0.009 | −0.110 |
| residuos del (0,1,0) (m03) = ∇ln | **+0.221** | **+0.071** |

Sobre m03 el par 12/1973–01/1974 hace +0.072 de r(1) (un tercio; la tabla
«Qué fechas hacen cada retardo» lo marca como artefacto), y con dos escalones en
12/1973 el φ del AR(1) cae a 0.118 (t 1.16). Sobre m02 nada de esto aparece.

La llamada 2 sobre m02 tiene el mismo origen: el encabezado dice «1 extremo,
1 período alterado en el nivel» porque el AR ya absorbió enero de 1974, y la
configuración que gana es de 2 períodos (12/1973×2).

Además, la leyenda del gráfico de la llamada 2 dice «hypothesis × 0.88» sin
explicar el factor.

## Impact

La pregunta que el nodo existe para contestar —¿este orden es estructura o lo
hace un suceso?— queda sin respuesta precisamente cuando el orden ya está en el
modelo, que es el caso normal tras identificar. El analista lee «no cambia la
identificación» y adopta el AR(1).

## Reproduction

`python3 bugs/BUG-0249-repro/repro.py` — con los datos del ejemplo (`flour_prices.csv`); sale con 1 mientras el bug siga abierto.

    # sima examples/lutkepohl_poskitt/data/flour_prices.csv, columna Minneapolis
    confirm_and_estimate(lam=0, d=1, D=0, p=1, q=0, n_harmonics=0, seasonal=False)  # m02
    guided_intervention(m02.pre, threshold=2.4)                                     # r(1) 0.009
    confirm_and_estimate(... p=0, q=0 ...)                                          # m03
    guided_intervention(m03.pre, threshold=2.4)                                     # r(1) 0.221 → 0.071

## Root cause

La llamada 1 calibraba `m._result.residuals` y nada más. Con el orden ya en el
modelo, la señal que el anómalo fabricaba en ese retardo está absorbida por el
coeficiente, y los residuos no la tienen.

## Fix

La segunda opción de la propuesta: si el modelo trae ARMA, calibrar las DOS
cosas y decirlo (`src/art/mcp_server.py`).

- `_ordenes_arma`, `_texto_ordenes_arma`, `_sin_arma`, `_orden_y_anomalos`
  (antes de `guided_intervention`): los órdenes con coeficientes libres (el
  relleno `[[0.0]]` fijo no cuenta); el mismo modelo sin su ARMA
  (`_build_arma_on_model(m, 0, 0)`, que hereda deterministas, d, D y factores
  de frecuencia fija), estimado: sus residuos son la serie de identificación;
  y, sobre su calibración, los retardos de los órdenes del modelo (PACF para el
  AR, ACF para el MA) con su estado: «fabricada» (cambio de veredicto con el
  margen de BUG-0212) o «marginal» (fuera de banda, dentro al omitir, sin el
  margen).
- Llamada 1: sección «Este modelo ya tiene AR(1)» con la tabla de esos
  retardos sobre la serie sin el ARMA, y por cada sospecha el aviso («lo
  fabrican» / «puede estar fabricado») con el par de fechas dominante si se
  lleva al menos `CUOTA_PAR_DOMINANTE` de r(k). Si no hay sospecha, lo dice.
  El veredicto: con «fabricada» deja de decir «sobre-intervenir»; con
  «marginal» añade «Salvo el orden del modelo…». La recomendación igual.
  `data` lleva `orden_fabricado` y `orden_sospechoso`.
- Llamada 2: un párrafo que explica el factor de la leyenda «hypothesis ×
  0.88» (la escala por mínimos cuadrados de `describe_superposicion`, cuyo
  texto esta llamada no publica).

**Lo que NO se hizo: contar el episodio de la llamada 2 sobre la serie sin el
ARMA.** Sobre la serie sin el AR(1) el episodio de 12/1973 tiene 2 extremos
(no 1), pero `decide_episodios` (d = 1) le sigue dando 1 período en el nivel,
y el encabezado diría lo mismo. No hay discrepancia que explicar con la
configuración ganadora (12/1973×2): un episodio de L períodos se especifica
como L + 1 escalones en el nivel, así que uno de 1 período son 2 escalones, y
la estimación decide qué pasó en cada uno. La matemática de los episodios está
bien definida: un impulso en el nivel se ve en ∇ como un impulso compensado
(+, −); un escalón en el nivel, como un impulso en ∇; dos extremos seguidos
del mismo signo en ∇ son dos escalones, que es lo que esos L + 1 escalones
cubren. No es un defecto.

Test: `tests/test_bug_0249_intervencion_con_el_orden_ya_dentro.py` — sobre
Minneapolis, la llamada 1 con el AR(1) dice «Este modelo ya tiene AR(1)», da
`| AR | PACF(1) | +0.221 | +0.071 |`, «puede estar fabricado» con el par
12/1973–01/1974 y «Salvo el orden del modelo»; sobre el (0,1,0) no hay
sección; la llamada 2 explica el factor de la leyenda; y `_ordenes_arma` no
cuenta el relleno. Falla sin el arreglo.

## Validation

El repro sale con 0. La llamada 1 sobre m02 dice:

    ### Este modelo ya tiene AR(1)
    | AR | PACF(1) | +0.221 | +0.071 |
    ⚠ El AR(1) puede estar fabricado por los anómalos: al omitirlos, PACF(1)
    pasa de +0.221, fuera de banda, a +0.071, dentro —sin el margen que haría
    falta para cambiar de veredicto, pero es el retardo del orden. El par
    12/1973–01/1974 hace +0.072 de r(1) (33 %).

Es «marginal», no «fabricada»: con banda ±0.201, +0.221 no llega a
banda·1.25 = 0.251, así que el veredicto de la calibración de residuos no
cambia, pero ya no calla el orden. Los tests de `guided_intervention`
(`test_guided_intervention.py`, BUG-0149, 0152-0156, 0162, 0182) siguen
pasando.
