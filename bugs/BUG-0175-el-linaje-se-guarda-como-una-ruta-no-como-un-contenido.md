---
id: BUG-0175
title: El linaje se guarda como una RUTA, no como un contenido — si el `.pre` del padre se reescribe, el guardián del encadenado lo aprueba y `guion_map` sigue dibujando el árbol viejo
status: fixed
severity: high
component: guion
found_in: 0.2.1
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — sesión superviviente del run 3 en `/SF_MEG/empirical`
tags:
  - contrato-de-ficheros
  - guion
  - linaje
  - encadenado
references:
  - BUG-0099
  - BUG-0110
  - BUG-0159
  - BUG-0164
---

## Cómo se llegó aquí

Cerrado el run 3, el analista dio por cerrados todos los chats. No lo estaban:
un fork reanudado seguía vivo **16 h 27 min** después, en
`/home/david/Dropbox/SF_MEG/empirical` —el directorio de trabajo del run— con
`--reply-on-resume --permission-mode auto`, consumiendo CPU (5 ticks en una
ventana de 5 s) y sosteniendo dos `art-mcp`.

Que la sesión sobreviva al cierre del cliente **no es defecto de art** y no se
arregla aquí. Lo que sí es de art es la pregunta que deja: si esa sesión hubiera
escrito en `cases/<serie>/work/`, ¿qué lo habría detectado?

**Nada.** Y no hace falta una segunda sesión para provocarlo.

## Summary

El encadenado y el guion identifican al padre de un modelo por su **RUTA**.
Ninguno de los dos guarda nada del **CONTENIDO** del `.pre` del que se
descendió. Si ese fichero se reescribe —otra sesión, una reestimación en la
misma ruta, una edición— el hijo sigue declarando que desciende de él, el
guardián del encadenado lo aprueba y `guion_map` dibuja el mismo árbol. El
linaje publicado pasa a ser falso y no hay un solo aviso.

Es exactamente la enfermedad recurrente: **una propiedad que sólo se sostiene
porque todos se acuerdan es una costumbre, no una propiedad del sistema.** El
convenio dice *«un `.pre` que se TOCA vuelve a ser un `.inp`»*. Está enunciado
en la cabecera de drtran como propiedad. Nada lo comprueba.

## Lo que sí existe, y por qué no llega

BUG-0099 ya puso un guardián: `_exige_la_misma_serie` compara los **datos** del
`.pre` con los de la serie en curso, y rechaza encadenar de otra serie. Funciona
y no se toca.

Pero compara la SERIE, no el MODELO. Dos especificaciones distintas sobre la
misma serie tienen idéntico bloque de datos, así que el guardián las da por
buenas a las dos. El hueco es justo ese.

## Reproduction

Sintético y determinista (`numpy.default_rng(7)`, n=120, mensual). Medido:

```python
m0 = fue.Model(A, d=1, mu=0.0, estimate_mu=True, refactor=_RESCALE_FACTOR)
_write_inp(A, m0, inp); _, f0 = estimar(inp); f0.write_pre(pre)
ts0, mt0 = mirar(pre)
_exige_la_misma_serie(A, ts0, "hijo.inp", "B.pre")     # el hijo se encadena

# otra sesión —o la misma— estima OTRO modelo sobre la MISMA serie, misma ruta
m1 = fue.Model(A, d=1, ar=[[0.3], [0.2]], ma=[[-0.4]], mu=0.0,
               estimate_mu=True, refactor=_RESCALE_FACTOR)
_write_inp(A, m1, inp); _, f1 = estimar(inp); f1.write_pre(pre)
ts1, mt1 = mirar(pre)
_exige_la_misma_serie(A, ts1, "hijo.inp", "B.pre")     # ¿y ahora?
```

Salida:

    t0 spec: {'ar': [[0.0]], 'ma': [], 'd': 1, 'D': 0}
    t0 loglik: -590.648168
       guardian OK, el hijo desciende de este .pre
    t1 spec: {'ar': [[-0.96124879], [-0.01992986]], 'ma': [[-1.0]], 'd': 1, 'D': 0}
    t1 loglik: -590.131693
    t1 guardian: PASA  <-- el padre es OTRO modelo y nadie lo ve

De `(1,1,0)` con φ=0 a `(2,1,1)` con φ₁=−0,96 y θ=−1,0. **Otro modelo, misma
ruta, mismo veredicto del guardián.**

## Root cause

Dos sitios, y el segundo es el que publica.

**1 · `src/art/mcp_server.py` — `_exige_la_misma_serie`.** Compara `series`
contra `series`. Correcto para lo que BUG-0099 pedía; ciego al ARMA, a los
deterministas y a las intervenciones del `.pre`.

**2 · `src/art/guion.py:288` — `infer_parent`.** El emparejamiento es por raíz
de ruta:

```python
objetivo = os.path.splitext(os.path.abspath(os.path.expanduser(base_pre_path)))[0]
for e in reversed(guion.entries):
    if os.path.splitext(os.path.abspath(e.inp_path))[0] == objetivo:
        return e.version
```

Y su propio docstring declara otra cosa: *«el padre es la versión que produjo
ESE fichero»*. Lo que el código devuelve es *la última versión registrada cuya
ruta coincide* — que es el que lo **reescribió**, no el que lo produjo. El
`reversed` lo garantiza.

**Esto ocurre dentro de una sola sesión.** Si en un guion se reestima dos veces
en la misma ruta, los hijos de la primera quedan colgando de la segunda. No hace
falta ningún fork superviviente: la sesión fantasma sólo lo hizo evidente.

## Impact

El guion existe para **conservar la evidencia** de cómo se llegó al modelo
—BUG-0110 va de eso mismo—. Un árbol cuyos enlaces no se pueden verificar no es
evidencia: es un dibujo. `guion_map`, `guion_evidencia` y `export_guion`
publican ese árbol sin reservas.

Contra la tabla de la congelación:

| criterio | |
|---|---|
| publica un número **incorrecto** y calla | el linaje se publica y puede ser falso, en silencio |
| pierde datos o corrompe un fichero | el `.pre` se pisa sin dejar rastro de que se pisó |

A mi juicio **entra**. La decisión es del analista.

## Fix

En el guion, no en el fichero. `src/art/guion.py`:

1. `sha_del_fichero(ruta)` y `pre_hermano(inp_path)`. La huella devuelve `""`
   —«no consta»— en vez de levantar: un guion tiene que poder registrarse aunque
   el fichero falte; lo que no puede es AFIRMAR un linaje que no comprobó.
2. `GuionEntry` gana **`pre_sha`** —la huella del `.pre` que esta versión
   produjo— y **`base_pre_sha`** —la del `.pre` semilla, leída al encadenar—.
   Con las dos, un enlace padre→hijo se contrasta en vez de creerse.
3. `infer_parent(guion, base_pre_path, base_pre_sha)`: la ruta sólo SELECCIONA
   candidatos; quien decide es la huella. Un homónimo cuya huella no cuadra se
   descarta. Si hay homónimos con huella y ninguno cuadra devuelve `None`: el
   fichero lo escribió algo que este guion no registró, y nombrar al último
   sería nombrar a un impostor.
4. `linaje_dudoso(guion)` — `(version, motivo)` con tres motivos: *el padre es
   otro*, *el fichero ha cambiado*, *sin contrastar*. Un `.pre` **borrado** no
   se denuncia: que un fichero de trabajo desaparezca es corriente y no
   contradice nada de lo registrado.

`src/art/mcp_server.py`: `_record_to_guion` —el sitio único por el que pasan
`confirm_and_estimate` y `record_version`— sella las dos huellas, y `guion_map`
añade el bloque que dice que sus propios enlaces no se sostienen. El mapa ES el
árbol: si el árbol no se contrasta, hay que decirlo ahí.

**Compatibilidad.** Huella vacía significa «no consta», nunca «cuadra». Un guion
anterior al campo se sigue leyendo (BUG-0098), se empareja por ruta como antes y
sale listado como *sin contrastar* — que es la verdad sobre él, ni roto ni
comprobado.

**`_exige_la_misma_serie` NO se toca, y es deliberado.** Al encadenar no hay
ninguna expectativa declarada sobre el modelo contra la que contrastar: el
llamante pide «encadena de este `.pre`» y no dice de qué modelo cree que viene.
El guardián no puede comprobar lo que nadie afirmó. Quien sí guarda esa
afirmación es el guion, y ahí es donde se contrasta.

**Alternativa descartada, y por qué.** Sellar la procedencia en la cabecera del
`.inp` no vale la pena y arriesga el contrato. El lector en C es **posicional**:
`fue.c` [3.0] hace exactamente cinco `fgets` («may contain anything») y a partir
de ahí `fgets`+`fscanf` alternos. Una línea de más desplaza la lectura entera.
Sólo cabría reaprovechando la quinta línea —hoy en blanco—, que el lector de
Python descarta como comentario puro (`inp.py:113`, rama `startswith("*")`) y el
de C se traga. Cabe, sí; pero no compra nada que el guion no dé y toca el
formato, que es el activo a proteger.

## Validation

`tests/test_bug_0175_el_linaje_es_contenido_no_ruta.py` — 16 casos:

- **el defecto**: dos versiones en la misma ruta y un hijo de la primera;
  `infer_parent` con la huella de v1 devuelve 1, no 2. Sobre el código anterior
  devolvía 2, porque el `reversed` da con la última coincidencia de ruta;
- una huella que no conoce ninguna entrada no nombra padre;
- **lo que ya funcionaba sigue**: sin encadenar, el padre es la última entrada;
  un guion sin huellas empareja por ruta; el primer registro no tiene padre;
- `linaje_dudoso` distingue los tres motivos, y un `.pre` borrado no se denuncia;
- las huellas sobreviven al disco —`save_guion`/`load_guion` y el JSON crudo—;
- `guion_map` calla con el fichero intacto y avisa cuando se reescribe.
