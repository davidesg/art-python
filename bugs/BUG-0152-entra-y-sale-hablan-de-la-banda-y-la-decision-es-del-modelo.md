---
id: BUG-0152
title: «ENTRA» y «SALE» hablan de la BANDA mientras la decisión es sobre el MODELO, y se leen al revés
status: open
severity: medium
component: calibracion
found_in: 0.2.0
fixed_in:
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

## Fix propuesto

No cambiar el cálculo —está bien—, sino **nombrar lo que se decide**. Dos
opciones, y la segunda me parece mejor:

**a)** invertir las palabras, que obliga a cambiar la glosa y deja el mismo
problema con el sujeto implícito.

**b)** rotular por el efecto sobre el MODELO, que es lo que el analista hace
con la fila:

    el anómalo FABRICABA este orden   →  al calibrar, desaparece
    el anómalo ENMASCARABA este orden →  al calibrar, aparece

Las dos frases ya están en la glosa; lo que falta es que sean la etiqueta en
vez del pie. Y entonces la columna se lee sin glosa.

## Validation

La prueba tiene que fijar la DIRECCIÓN, no el texto: para un retardo cuya ACF
observada está fuera de banda y la calibrada dentro, la etiqueta debe decir que
el anómalo lo **fabricaba**.
