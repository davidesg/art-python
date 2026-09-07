---
id: BUG-0103
title: El modelo FACTORIZADO que ar_factorization prescribe no se puede estimar desde la superficie MCP — y la salida que invita a factorizar no advierte que leer los módulos iguales como un operador en B^s impone 5 restricciones sin contrastar
status: open
severity: high
component: mcp-tools
found_in: 0.2.0.dev0
fixed_in: 
reported: 2026-09-06
reporter: David / sesión UEM_HCPI_0219 — nodo de órdenes sobre m02
tags:
  - factorizacion
  - ar_factorization
  - sparse
  - restriccion
  - mcp-surface
references:
  - src/art/mcp_server.py:4969 (confirm_and_estimate — `p: int` escalar, un único operador sin factorizar)
  - src/art/mcp_server.py (ar_factorization — devuelve los factores; ninguna vía para volver a estimarlos)
  - fue/src/fue/model.py:84-140 (Model.ar es una LISTA DE FACTORES; Model.ar_f son los AR(2) de frecuencia fija)
  - bugs/BUG-0095-... (misma doctrina por la puerta de la identificación; ésta es la puerta a posteriori)
  - bugs/BUG-0079-... (mismo patrón: el motor lo soporta, el carril guiado no lo alcanza)
  - bugs/BUG-0103-repro/repro.py
---

## Summary

`ar_factorization` factoriza el AR(p) estimado y documenta que un factor
complejo cuyo periodo coincide con un ciclo estacional y cuyo amortiguamiento
esté cerca de 1 es **candidato a operador AR_f estacional**, para alimentar el
MEG (DCD_f) y el par confirmatorio Shin-Fuller. Esa es la ruta correcta: el
polinomio se estima completo y las restricciones —frecuencia fija, ceros
intermedios, ciclos— se reservan para el análisis a posteriori de raíces (la
doctrina que BUG-0095 fijó para la puerta de la identificación).

**El siguiente paso de esa ruta no existe en la superficie MCP.** Para
contrastar si un factor admite la frecuencia estacional hay que (1) estimar el
modelo FACTORIZADO —los mismos parámetros reagrupados en factores, con lo que
cada uno recibe su `d ± SE` y su `periodo ± SE`— y (2) reestimarlo con el
factor restringido a frecuencia fija, para la razón de verosimilitudes anidada.
`fue.Model` soporta las dos cosas: `ar` es una **lista de factores** y `ar_f`
son los factores de segundo orden con frecuencia fija. `confirm_and_estimate`
expone `p: int` escalar, que construye **un único operador sin factorizar de
orden p**, y ninguna otra herramienta MCP expone `ar`, `ar_orders` ni `ar_f`.
La ruta que la propia herramienta prescribe se corta en el primer peldaño.

Y hay un segundo defecto, que es el que hace daño en la práctica. La salida de
`ar_factorization` presenta módulos y periodos sin decir en ninguna parte que
**unos módulos casi iguales son exactamente la firma de un operador «sólo en
B^s»**, y que por tanto leerlos como tal IMPONE la restricción en vez de
contrastarla. La igualdad de módulos es la hipótesis, no el hallazgo. Como el
único camino transitable tras `ar_factorization` es `confirm_and_estimate(p=…)`
—defecto 1—, los dos defectos se componen: el asistente ve los módulos casi
iguales, no puede estimar el modelo factorizado, y lo único que SÍ puede hacer
es imponer la restricción sin contrastarla.

## Impact

Alto, y de la clase peor: no rompe nada, produce un modelo estimable y con
mejor BIC.

En la sesión UEM_HCPI_0219 (HICP UEM, 2002:01–2019:12, 216 obs) el modelo
`m02 = AR(6) × SAR(1)₁₂` + 11 armónicos + μ dio una factorización con los seis
módulos entre 1.2684 y 1.2934. El asistente lo leyó como «esto es un operador
puro en B⁶», y propuso al analista sustituir el AR(6) por un AR disperso
`(1 − φ₁B − φ₆B⁶)` apelando al BIC (15.23 → previsto ≈ −6) y a las t (sólo
φ₁ y φ₆ significativas). El analista lo paró:

> «el operador no se debería proponer nunca de esa forma. (1−ΘB⁶) =
> (1−θB)(1+θB+…+θ⁵B⁵), todos con el mismo módulo. Si lo estimas así estás
> imponiendo una restricción sin contrastar.»

Sin esa intervención el caso habría seguido adelante con 4 restricciones
impuestas a ciegas, entre ellas la que más importa aquí: el factor AR(2)
semianual sale con **periodo 6.67 estimado frente al 6.00** que el operador en
B⁶ fija por decreto —un +11.1 %— y esa desviación es precisamente lo que había
que contrastar, porque de ella depende que el factor sea o no estacional y, por
tanto, que llegue o no al MEG. Un factor que se fija a 6.00 sin preguntarlo
entra en el MEG como estacional sin haberlo demostrado; uno que se fija cuando
en realidad era un ciclo no estacional de 6.7 meses contamina el veredicto de
la frecuencia f=2 en la dirección contraria.

Nótese que el asistente había argumentado explícitamente, dos nodos antes y en
la misma sesión, que los seis armónicos deben ponerse todos porque «el armónico
ES la hipótesis nula del MEG» y podar antes de contrastar deja la hipótesis sin
contrastar. Aplicó la doctrina a los armónicos y la violó en los factores AR
media hora después. Que el mismo razonamiento no se transfiera solo indica que
el aviso tiene que estar en la salida de `ar_factorization`, no en la cultura
general del carril.

## Reproduction

    cd art-python && python3 bugs/BUG-0103-repro/repro.py

Comprueba dos cosas independientes:

**A) El álgebra.** Con Θ = 0.2290 (el φ₆ de m02) y θ = Θ^(1/6) = 0.78218:

    (1 − Θ·B⁶) = (1 − θB)(1 + θB + θ²B² + θ³B³ + θ⁴B⁴ + θ⁵B⁵)
               = (1 − θ²B²)(1 − θB + θ²B²)(1 + θB + θ²B²)

verificado numéricamente. Las seis raíces salen con módulo **idéntico**
1.278480 (dispersión 1.8e−15) en ángulos exactos 0°, 60°, 120°, 180° —periodos
∞, 6.000, 3.000, 2.000—. Un operador en B⁶ impone por tanto un amortiguamiento
común a las cuatro frecuencias Y las cuatro frecuencias fijadas: 1 parámetro
frente a los 6 del AR(6) libre = **5 restricciones** (4 en la variante dispersa
`1 − φ₁B − φ₆B⁶`). Frente a eso, el AR(6) libre de m02 da cuatro
amortiguamientos distintos (0.780 / 0.773 / 0.790 / 0.780) y frecuencias
libres (periodos 3.03 y 6.67).

**B) La superficie.** `inspect` sobre las firmas:

    fue.Model.__init__ : ar=True  ar_f=True   («Each inner list is one factor»)
    confirm_and_estimate: p=int (escalar)  factores expuestos=False  ar_f expuesto=False
    herramientas MCP que exponen factores/ar_f: NINGUNA

## Root cause

Dos causas, una por defecto.

1. `src/art/mcp_server.py:4969` — `confirm_and_estimate(..., p: int = 0, ...)`.
   El parámetro es un orden escalar y aguas abajo construye un único operador
   de orden `p`. El espacio de modelos de `fue.Model` (`ar` lista de factores,
   `ar_f` de frecuencia fija) es estrictamente mayor que el que la superficie
   MCP sabe nombrar. Es el mismo patrón de BUG-0079: el motor lo soporta, el
   carril guiado no lo alcanza.

2. `ar_factorization` — el docstring delega la interpretación en el asistente
   («INTERPRETATION IS LEFT TO THE ASSISTANT») y describe el caso de uso
   correcto (candidato a AR_f estacional → MEG), pero no menciona el modo de
   fallo simétrico y mucho más tentador: módulos aproximadamente iguales ⇒
   operador «sólo en B^s» ⇒ imponer. La salida no lleva el aviso, y BUG-0095
   —que fijó esta misma doctrina— sólo actuó sobre la generación de candidatos
   en `model_detection`, no sobre la ruta a posteriori que él mismo señala como
   la correcta.

## Fix

1. **Exponer el modelo factorizado.** Un parámetro de órdenes por factor en
   `confirm_and_estimate` —p. ej. `ar_orders: list[int] | int`, donde `6`
   sigue significando un operador de orden 6 y `[1, 1, 2, 2]` significa cuatro
   factores— más la semilla opcional de coeficientes, que `ar_factorization` ya
   calcula y podría devolver en forma reejecutable. La reparametrización está
   exactamente identificada (misma verosimilitud, mismos grados de libertad),
   así que es una llamada barata y sin compromiso.

2. **Exponer `ar_f`**, los AR(2) de frecuencia fija, para que la restricción a
   frecuencia estacional sea una estimación anidada y su LR un contraste, en
   vez de una imposición. Con 1 y 2 el procedimiento completo queda
   transitable: factorizar → estimar factorizado → restringir a frecuencia
   estacional (LR, 1 g.l. por factor) → MEG sobre los factores que pasen.

3. **Aviso en la salida de `ar_factorization`**, en el mismo lugar donde
   imprime los módulos: cuando la dispersión relativa de los módulos sea
   pequeña, decir explícitamente que ése es el aspecto que tendría un operador
   en B^s, que la igualdad es la hipótesis y no la conclusión, y nombrar la
   llamada que la contrasta. Es el análogo del aviso que `meg_frequency` y
   `test_seasonal_simplification` ya llevan para la poda de armónicos.

## Validation

`bugs/BUG-0103-repro/repro.py` sale con código 1 mientras la superficie no
exponga los factores y vuelve a 0 cuando `confirm_and_estimate` (u otra
herramienta) acepte `ar_orders`/`ar_factors`/`ar_f`. La parte A del repro es
una identidad algebraica y debe seguir pasando siempre: sirve de test de
regresión del enunciado del aviso.

Caso de referencia: `cases/UEM_HCPI_0219` — m02 y el nodo n4 del guion, que
registra la propuesta rechazada con su demostración.
