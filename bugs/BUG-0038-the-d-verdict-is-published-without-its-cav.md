---
id: BUG-0038
title: the "consider d+1" verdict is published without its caveats when the model has no regular AR — the bare-law critical value warning lived inside the confirmatory-pair block, and that block only prints when Shin-Fuller is applicable
status: fixed
severity: high
component: formal-tests
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-27
reporter: David / réplica TFM Bolivia
tags:
  - dcd
  - integration-order
  - presentation
  - autonomous
references:
  - src/art/describe.py (describe_formal_tests, bloque od_res y bloque del par)
  - src/art/formal_tests.py (dcd_overdiff_regular)
  - bugs/BUG-0038-repro/repro.py
  - tests/test_bug_0038_overdiff_caveats_need_no_pair.py
---

## Summary

`dcd_overdiff_regular` contrasta el orden de integración en f=0, y su veredicto
—«d confirmado ✓» o «considerar d+1 ✗»— viene acompañado de dos advertencias que
el paper exige y que ART ya tenía escritas:

1. **el crítico impreso (1.94) es el de la ley DESNUDA s=1.** Con deterministas
   RESONANTES con f=0 —una constante, un escalón— el pile-up sube de 0.6575 a
   0.927 y el crítico correcto es MAYOR;
2. **si θ̂ no se apila en la frontera**, el LR usa ℓ(θ=1) calculada justo donde el
   perfil de verosimilitud de fue da un salto errático.

Las dos vivían **dentro** del bloque del par confirmatorio:

```python
if sf_res is not None and od_res is not None:
    ...  # el par
    n_det = len(model.interventions or [])
    if n_det:
        lines.append("ℹ El crítico usado … es el de la ley DESNUDA …")
```

Y ese bloque sólo se imprime cuando **Shin-Fuller es aplicable**, es decir cuando
el modelo tiene **AR regular libre**.

**Resultado: un modelo sin AR regular recibe «considerar d+1 ✗» a pelo**, con un
crítico que se sabe subestimado para él y sin nada que lo diga.

Y ninguna de las dos advertencias habla del par. Las dos hablan del **veredicto
del DCD**. Estaban en el sitio equivocado.

## El testigo, y lo que costó

RATIO (Gasto/PIB Bolivia) de la réplica, modelo m70: dos raíces unitarias
estacionales, un escalón en 2008:4, y AR **sólo estacional** — así que no hay AR
regular libre y Shin-Fuller no aplica.

```
DCD sobre-diferenciación regular
- θ̂=+0.8332, LR=2.576 (crít 5%=1.94) → considerar d+1 ✗
```

Sin aviso. Leído tal cual: «queda una raíz unitaria regular genuina». Se tomó
d=2, que era **incorrecto** — con el crítico bien calibrado, LR=2.576 no cruza el
umbral real, y el candidato d=2 bien construido apenas mueve AIC (456.14 vs
459.39) y BIC (470.36 vs 471.30) mientras EMPEORA el Q (0.2907 vs 0.3694).

El defecto es especialmente dañino para un carril autónomo: un analista con el
paper en la cabeza recuerda la salvedad; un LLM lee lo que hay impreso.

## Fix

Las dos advertencias pasan a colgar del veredicto del DCD, fuera del `if` del
par, y se añade una tercera que faltaba:

```python
lines.append(f"- θ̂={od_res.coef_free:+.4f}, LR={od_res.lr:.3f} …")

if n_det:
    lines.append("ℹ El crítico usado … ley DESNUDA … el correcto ahí es mayor, "
                 "así que un LR apenas por encima del impreso NO es evidencia de d+1.")
if abs(abs(od_res.coef_free) - 1.0) > 1e-6:
    lines.append("ℹ θ̂ no se apila en la frontera …")
if sf_res is None:
    lines.append("⚠ **Sin par confirmatorio.** … El veredicto de arriba es UN "
                 "SOLO lado, y los contrastes de frontera se leen en pareja. "
                 "Antes de mover `d`, estima el candidato d+1 y compáralo por "
                 "diagnosis y criterios de información.")
```

La tercera es la que cierra el agujero de raíz: **decir que falta el par**. Un
contraste de frontera se lee en pareja con su nula opuesta, y cuando sólo hay un
lado eso es información, no silencio.

## Repro

`bugs/BUG-0038-repro/repro.py` — paseo aleatorio con un **escalón** (el
determinista resonante con f=0), modelado SIN AR regular. Comprueba que
Shin-Fuller no aplica y mira qué acompaña al veredicto sobre `d`.

## Lo que este defecto tapaba, y el error de método que destapó

Al investigarlo salió un segundo problema, éste del analista y no del código, que
queda anotado porque es fácil de repetir: al construir el candidato d=2 sobre un
modelo con Nyquist estocástica hay que conservar **los dos** factores MA
regulares —el testigo de Nyquist (θ→−1) y el de f=0 (θ→+1)—. Dejando uno solo, la
segunda diferencia se apropia del de Nyquist para deshacer la de f=0: en RATIO
pasó de −0.7722 a +0.2654, dejando `ifadf[2]=1` **sin testigo**, que es la forma
AR-only. `dcd_overdiff_regular` ya lo hace bien (BUG-0009 añadió el slot propio);
lo que falta es que nada lo diga cuando el candidato lo construye una persona.
