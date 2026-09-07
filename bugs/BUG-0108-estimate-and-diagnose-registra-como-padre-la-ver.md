---
id: BUG-0108
title: estimate_and_diagnose registra como padre la versión ANTERIOR del guion, no el modelo del que sale el .inp — y no hay forma de declararlo, así que la cascada de guion_abandon puede barrer la rama viva
status: fixed
severity: high
component: guion
found_in: 0.2.0.dev0
fixed_in: 0.2.0.dev0
reported: 2026-09-06
reporter: David / sesión UEM_HCPI_0226 — abandono de v11 con la rama viva colgando de él
tags:
  - guion
  - linaje
  - guion_abandon
  - cascada
references:
  - src/art/mcp_server.py (estimate_and_diagnose — sin base_pre_path/parent; confirm_and_estimate sí lo tiene)
  - src/art/mcp_server.py (guion_abandon — la cascada arrastra a los descendientes, por diseño)
  - bugs/BUG-0103-... (el modelo factorizado y ar_f sólo se pueden construir a mano: de ahí los padres falsos)
  - bugs/BUG-0037-... (la cascada barría el nodo que registraba el rechazo: mismo terreno)
  - bugs/BUG-0108-repro/repro.py
---

## Summary

`confirm_and_estimate` tiene `base_pre_path`: sabe de qué modelo encadena y
registra el linaje bien. **`estimate_and_diagnose` no tiene ningún parámetro
equivalente** —ni `base_pre_path`, ni `parent`, ni `guion_parent`— así que anota
como padre la **última entrada del guion**, que no tiene por qué ser el modelo
del que sale el `.inp`.

Eso no sería grave si todos los modelos se construyeran encadenando. Pero hay
`.inp` que **sólo** se pueden construir a mano —los AR factorizados y los AR(2)
de frecuencia fija, que la superficie MCP no expone (BUG-0103)— y ésos entran
en el guion por `estimate_and_diagnose`, cada uno con un padre inventado.

Y el linaje falso convierte en **destructivo** un abandono correcto:
`guion_abandon` arrastra a los descendientes **por diseño** —«una decisión
contaminada contamina lo que viene después»—, de modo que marcar un callejón
puede barrer la rama viva.

## Impact

Alto. El daño no es un mapa mal dibujado: es la **pérdida silenciosa del
recorrido**, que es el activo que el guion existe para conservar.

Caso real, `cases/UEM_HCPI_0226`, guion de 15 entradas:

    v10 e07_fact    <- v9    correcto
    v11 e08_noarf4  <- v10   correcto
    v12 e09_ffix4   <- v11   FALSO: se construyó a mano desde v10 (e07_fact)
    v14 e11_meg2    <- v12
    v15 e12_ffix2   <- v14

v11 es un callejón contrastado (LR=9.78, 2 g.l., p=0.0075) y **hay que
marcarlo**. Pero `guion_abandon(11)` con la cascada por defecto se lleva v12,
v14 y v15 — la rama viva, que no desciende de él. Hubo que pasar
`cascade=False` y dejar el aviso escrito a mano dentro de la razón, que es
justo lo que el registro debería evitar.

Nótese la composición de defectos: BUG-0103 obliga a construir a mano, la
construcción a mano falsea el padre, y el padre falso hace peligrosa la única
operación que da valor al guion. Cuanto más avanzado el análisis —más factores,
más frecuencias fijas— más modelos con padre falso.

## Reproduction

    cd art-python && python3 bugs/BUG-0108-repro/repro.py

    confirm_and_estimate  : base_pre_path=True
    estimate_and_diagnose : base_pre_path=False  parent=False  guion_parent=False

## Root cause

`estimate_and_diagnose` relee un `.inp` cualquiera: por construcción **no puede
inferir** de qué modelo desciende, porque esa información no está en el
fichero. Y la firma no ofrece ninguna vía para que la aporte quien sí lo sabe
—el analista o el LLM que acaba de escribir el `.inp`—. El guion cae entonces
en el único valor disponible, la versión anterior, sin marcarlo como
presunción.

## Fix

1. **Un parámetro de linaje en `estimate_and_diagnose`**: `parent: int = -1`
   (o `base_pre_path`, por simetría con `confirm_and_estimate`), que fije el
   padre explícitamente.
2. **Marcar la presunción**: si no se declara, registrar el padre como
   *presunto* —un campo `parent_inferred: true`— y que `guion_map` lo dibuje
   distinto. Un padre adivinado y uno declarado no valen lo mismo.
3. **Que `guion_abandon` avise antes de cascadear** sobre descendientes de
   padre presunto: listar a quién se va a llevar y exigir confirmación, o al
   menos imprimirlo. Hoy la cascada es silenciosa y sólo se descubre mirando el
   mapa después.
4. Y, en la raíz, exponer los operadores factorizados y `ar_f` en la superficie
   MCP (BUG-0103): sin `.inp` escritos a mano no habría padres falsos.

## Validation

`bugs/BUG-0108-repro/repro.py` sale con código 1 mientras
`estimate_and_diagnose` no acepte un parámetro de linaje. Añadir un test que
construya un guion con un padre declarado y compruebe que `guion_abandon` en
cascada respeta el árbol real.

---

## Cierre (2026-09-07) — dos mitades, porque una sola no bastaba

**1 · Que se pueda declarar.** `estimate_and_diagnose` gana `base_pre_path`, como
`confirm_and_estimate`. El docstring dice cuándo usarlo y por qué importa, que es
lo que hace que se use.

**2 · Que se sepa cuándo NO se declaró.** Ésta es la mitad que el informe no
pedía y sin la cual el arreglo sería a medias: dar el parámetro no evita que
alguien lo omita, y una entrada con padre inferido sigue siendo indistinguible de
una con padre cierto. `GuionEntry.parent_origen` guarda cuál de los dos es:

    "declarado" — el llamante dijo de qué `.pre` encadenaba
    "inferido"  — se tomó la última entrada porque nadie lo dijo

Y `guion_abandon` lo mira **antes de tocar nada**:

    ⚠ La cascada se apoya en un parentesco INFERIDO en v3 (m02_ffix). Esas
      entradas no declararon de qué modelo salían, así que su padre es «la
      última entrada del guion» y puede no ser el real. Compruébalo antes de
      darlas por muertas: si alguna no desciende de v2, repite con cascade=False.

En el caso real —`UEM_HCPI_0226`— eso es exactamente lo que hubo que descubrir a
mano y anotar dentro de la razón. Ahora lo dice la herramienta, señalando qué
entrada es la dudosa.

## Lo que NO hace

**No arregla los guiones ya escritos.** Sus entradas no llevan `parent_origen`,
así que se leen como cadena vacía y la cascada no avisa sobre ellas: no se puede
saber a posteriori si aquel padre se declaró o se supuso. Los recorridos nuevos
quedan cubiertos; los viejos siguen pidiendo el cuidado de siempre.

**Y no cierra la composición de defectos que el informe señala.** Mientras
BUG-0103 obligue a construir a mano los AR factorizados y los de frecuencia
fija, seguirá habiendo modelos que entran por esta puerta — sólo que ahora
pueden declarar su linaje, y si no lo hacen, se sabe.
