---
id: BUG-0249
title: guided_intervention calibra sobre los residuos de un modelo que ya tiene órdenes, y no puede ver si esos órdenes los fabrica el anómalo
status: open
severity: medium
component: intervencion
found_in: 0.2.3.dev0
fixed_in: 
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

## Fix

Calibrar siempre sobre la serie de identificación (∇^d ∇_s^D y(λ) menos los
deterministas), o, si el modelo trae ARMA, calibrar las DOS cosas y decir:
«este modelo ya tiene AR(1): sobre la serie sin él, r(1) pasa de 0.221 a 0.071
al omitir los anómalos; el par 12/1973–01/1974 hace un tercio». La llamada 2
debería contar el episodio sobre la misma serie.

## Validation

Test con la serie del ejemplo: la llamada 1 sobre m02 menciona que el orden AR
puede estar fabricado por el par 12/1973–01/1974.
