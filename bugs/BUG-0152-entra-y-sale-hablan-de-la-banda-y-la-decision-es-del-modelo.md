---
id: BUG-0152
title: «ENTRA» y «SALE» hablan de la BANDA mientras la decisión es sobre el MODELO, y se leen al revés
status: fixed
severity: medium
component: calibracion
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-11
reporter: David — corrida guiada de ITCER
tags:
  - intervenciones
  - presentacion
references:
  - BUG-0133
---

## Summary

En la tabla de calibración de la llamada 1 de `guided_intervention`, cada
retardo que cambia de veredicto se marca `ENTRA` o `SALE`. **Las dos palabras
toman como sujeto la banda; la decisión que el analista tiene que tomar es sobre
el modelo, y van en sentido contrario.**

    ENTRA  el retardo entra EN LA BANDA  →  deja de ser significativo
                                         →  el orden SALE del modelo

El código y su glosa son coherentes entre sí, así que no hay contradicción
interna — lo que hay es que el rótulo nombra lo que no se decide:

```python
# calibracion.py:313  (fo/fc = «está FUERA de banda», observada / calibrada)
return "entra" if fo and not fc else "sale"
```

```
*«SALE» = estaba dentro y al calibrar sale (el anómalo la enmascaraba);
 «ENTRA» = estaba fuera y al calibrar entra (el anómalo la fabricaba).*
```

## Impact

Es la tabla de la **primera** llamada del nodo, la que contesta «¿hay que
intervenir?». Leerla al revés invierte la conclusión: se cree que hay que
añadir un orden cuando lo que dice es que sobra.

Anotado por el analista corriendo ITCER: *«Las etiquetas de la tabla se leen al
revés: ENTRA significa que el retardo vuelve DENTRO de la banda, es decir, que
el orden SALE del modelo.»*

## Fix

Se toma la opción **(b)**, y un paso más: las palabras no son la etiqueta, son
**el dato**.

```python
return "fabricada" if fo and not fc else "enmascarada"
```

`acf_flip` y `pacf_flip` devolvían `"entra"` / `"sale"`, así que cada sitio que
las presentaba tenía que acordarse de traducirlas — y la traducción es justo
donde estaba el error. Con el valor ya nombrado por lo que decide, **ningún
sitio puede volver a invertirlo**. Es la misma lección de BUG-0159 y BUG-0160:
lo que se sostiene porque todo el mundo se acuerda es una costumbre.

La glosa pasa a decir el efecto sobre el modelo, que es lo que el analista hace
con la fila:

    «FABRICADA»    = no existe sin el anómalo, así que ese orden **sobra**
    «ENMASCARADA»  = el anómalo la tapaba, así que ese orden **falta**

Y la columna se lee sin glosa, que era el objetivo.

**De paso, el veredicto decía la palabra dos veces en la misma línea** —«…
(fabricada) — una señal AR que el anómalo **fabricaba**»—. Ahora el rótulo va
una vez y lo que sigue es lo que aporta: qué hacer con ese orden. Es BUG-0154 en
pequeño, en la misma pantalla.

## Validation

`tests/test_bugs_0152_0153_0154_la_pantalla_del_nodo.py`. Lo que fija la prueba
es la **dirección**, no el texto: un retardo fuera de banda que al calibrar
entra tiene que decir que el anómalo lo **fabricaba**, y al revés. Y que la
glosa hable del modelo —«sobra», «falta»— y no de la banda.
