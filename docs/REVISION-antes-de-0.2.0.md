# Revisión crítica de arquitectura y cableado, antes de 0.2.0

2026-09-05. Encargada por el analista: *«dado el número de cambios es importante
una revisión crítica de la arquitectura y el cableado antes de subir de
versión»*. La mayor parte de esos cambios son míos, así que esto es sobre todo
una revisión de mi propio trabajo. Todo medido.

---

## Resumen: **no subir todavía** → RESUELTO el mismo día

Había un defecto de cableado que invalidaba buena parte del trabajo de la sesión,
y era exactamente el que diagnostiqué un día antes en otro sitio. **Cerrado.**

| hallazgo | estado |
|---|---|
| BLOQUEANTE — 23 de 46 herramientas fuera de `_INSTRUCTIONS` | **cerrado**, 23 → 0, con prueba que impide la reincidencia |
| menor 1 — `Escalera.subio` definido dos veces | **cerrado**, una definición y test |
| menor 3 — `norma_gradiente` sin lector | **podado** |
| menor 2 — 28 asertos sobre código fuente | pendiente, no bloquea |
| menor 4 — idioma de la API pública | pendiente, decisión del analista |
| cambios de comportamiento sin anunciar | **cerrado**, `CHANGELOG.md` 0.2.0 |

Lo que queda pendiente no bloquea la subida: el menor 2 es deuda de pruebas y el
4 es una decisión, no un defecto.

---

## BLOQUEANTE — 23 de 46 herramientas no existen para el LLM

`_INSTRUCTIONS` es el texto que el servidor entrega al modelo: es *el* mapa de la
superficie. **La mitad de las herramientas no aparece en él.**

```
46 herramientas registradas; 23 no mencionadas en las instrucciones:
  ar_factorization · compare_versions · export_guion · full_report
  guided_intervention · guion_diff · guion_evidencia · guion_node
  incident_configurations · intervention_analysis · intervention_ladder
  intervention_plot · meg_frequency · meg_reformulate · model_histogram
  preview_data · record_version · residual_episodes · residual_outlier_scan
  save_identification_report · series_info · sps_dashboard · update_and_forecast
```

Y lo peor está en la lista: **`guided_intervention` y `guion_evidencia`**, las
dos herramientas que esta sesión añadió. Y **siete de las nueve del nodo de
intervención**, que es el nodo que la versión venía a cerrar.

`guion_evidencia` aparece **dos veces en todo el fichero**: su comentario de
cabecera y su propio `def`. Ni `guion_map` la menciona, siendo su pareja natural
—el mapa dice a dónde volver, la evidencia dice qué hay allí—.

Esto es, literalmente, el defecto del §2.1 del documento de arquitectura
—*«ninguna de las nueve remite a otra»*— que diagnostiqué el 4 de septiembre y
repetí el 5. Arreglé el cableado **herramienta→herramienta** (las ocho sueltas
apuntan ahora a `guided_intervention`) y dejé sin cablear
**instrucciones→herramienta**, que es el que decide si el LLM la llega a llamar.

> Una herramienta que no está en las instrucciones no está rota: es que no
> existe. La capacidad está en la capa de abajo y la superficie no la nombra —
> el mismo patrón, un piso más arriba.

**Lo que hace falta:** meter las 23 en `_INSTRUCTIONS`, con `guided_intervention`
y `guion_evidencia` en su sitio del flujo, no en una lista al final.

---

## Lo que la revisión confirma que está BIEN

**El protocolo ya era correcto; el código lo incumplía.** Las instrucciones dicen
desde antes de esta sesión:

> *«LOS PARÁMETROS Y SUS ERRORES TÍPICOS SE LEEN DEL .out, NUNCA DE REEJECUTAR
> UN .pre … Se lee con `get_out_report`.»*

Y `get_out_report` reestimaba. Eso reencuadra BUG-0091: no era una decisión que
faltara, era **una regla escrita que el código rompía en silencio**. Refuerza que
`_INSTRUCTIONS` es la autoridad — y por eso el bloqueante de arriba pesa tanto.

**El sellado de los símbolos nuevos.** Los doce símbolos que añadí tienen uso real
en `src/` y cobertura en pruebas; ninguno es código muerto. `_load_fitted` sigue
como alias de `estimar`, así que nada externo se rompe.

**Los dos almacenes de figuras no colisionan.** `_show_fig` escribe en
`ART_FIG_DIR`/temporal —efímero, para mirar— y el guion en `figs/` junto al
`.json` —persistente, es el registro—. Son dos cosas distintas con dos vidas
distintas, y está bien que sean dos.

---

## MENORES, que no bloquean

### 1. Un concepto definido dos veces, y es mío

Creé `Escalera.subio` para nombrar «la recomendación está en un peldaño alto», y
en `_texto_escalera` (otro fichero) lo re-derivé como `rec == "2"`. Dos
definiciones del mismo predicado, en dos sitios, que pueden divergir: `rec` llega
como **parámetro** y el llamante lo calcula como
`esc.recomendado or esc.nivel_simple or "1a"`, que no siempre es `esc.recomendado`.

Es la misma familia que los cuatro `umbral_vecino` con tres valores (BUG-0087) y
las dos copias de la regla de λ (BUG-0080). Cometido el día después de arreglar
esos dos.

### 2. El 14% de mis pruebas nuevas mira el código fuente

28 asertos en 10 ficheros usan `fuente_de`/`cuerpo_de`. El docstring de
`tests/_fuente.py` dice que eso es «siempre el último recurso», y 28 es mucho
último recurso. Algunas son legítimas —fijar que una regla vive en `policy`, que
no quedan defaults literales— pero otras son comportamiento disfrazado de
inspección y deberían reescribirse.

### 3. `norma_gradiente` se parsea y no lo lee nadie

Peso muerto del lector del `.out`. Trivial, pero es exactamente lo que hay que
podar antes de congelar una versión.

### 4. Los identificadores mezclan idiomas

`estimar`/`mirar`/`lee_out` conviven con `_load_fitted`/`_load_ts_model`, y
`LecturaOut`/`ParametroOut` con `RespuestaFLT`/`Superposicion`. No es un defecto
funcional y el proyecto ya venía mezclando —los comentarios en español y los
bloques del motor en inglés son una propiedad declarada— pero para una API que se
congela conviene decidirlo a propósito en vez de heredarlo.

---

## Cambios de COMPORTAMIENTO que 0.2.0 tiene que anunciar

No son correcciones silenciosas. Un usuario que actualice verá veredictos
distintos:

| qué cambia | antes | ahora | por qué |
|---|---|---|---|
| umbral del vecino (Treadway) | 3.0 | **2.0** | es el contraste al 5%; con 3.0 la potencia era la mitad (BUG-0087) |
| lectura escalar de la escalera | por AIC | por la firma del residuo | el AIC no compara formas no anidadas (BUG-0086) |
| R² de `intervention_plot` | sobre la ventana | sobre el suceso | el ruido de la ventana ponía un techo (BUG-0084) |
| configuraciones del incidente | marcha sólo hacia atrás | simétrica | la mitad de los sucesos salían truncados (BUG-0083) |
| `get_out_report` | reestimaba | **lee el `.out`** | es el registro, no una reestimación (BUG-0091) |
| `estimate_and_diagnose` | `.pre` + `.out` | + `.inp` + guion | la terna y el registro (BUG-0088, BUG-0092) |
| AIC de las configuraciones | escala 1 | escala 100 | se perdía el factor al clonar (BUG-0085) |
| λ en el carril guiado | sólo regla índice | las cuatro categorías | la copia implementaba una de cuatro (BUG-0080) |

Además, un guion escrito por 0.2.0 **no se abre con 0.1.12** (tres campos
nuevos: `out_path`, `hist_path`, `refactor`). Al revés sí.

---

## Orden propuesto antes de etiquetar — y en qué quedó

1. ~~**`_INSTRUCTIONS`** — las 23, con las dos nuevas en su sitio del flujo.~~
   **HECHO.** No se añadió una lista: la ETAPA 3 se reescribió alrededor de
   `guided_intervention` con las tres llamadas y el árbitro entre instrumentos;
   se añadió la sección del GUION con `guion_map` y `guion_evidencia` como
   pareja; y una de instrumentos de apoyo agrupados por para qué sirven. Se
   escribieron además dos cosas que el protocolo no decía y son las que evitan
   el fallo típico del nodo: **el criterio de parada** (la escalada no se
   detiene sola) y **el convenio de signo con su remedio** (no hagas la resta,
   mira el camino del nivel).
   `tests/test_instrucciones_cubren_la_superficie.py` — 8 pruebas; la primera
   falla si una herramienta registrada no aparece en el texto.
2. ~~**`Escalera.subio`** — una sola definición.~~ **HECHO**, con test.
3. ~~**CHANGELOG 0.2.0**.~~ **HECHO**, con la tabla de los ocho cambios de
   comportamiento y el aviso de que un guion de 0.2.0 no se abre con 0.1.12.
4. `norma_gradiente` **podado**. Los 28 asertos de código fuente **siguen ahí**:
   es deuda de pruebas, no un defecto, y conviene revisarlos con calma en vez de
   de prisa antes de una etiqueta.
5. **El idioma de la API pública sigue sin decidirse.** No es un defecto
   funcional y el proyecto ya mezclaba a propósito (comentarios en español,
   bloques del motor en inglés). Pero congelar una API es el momento de decirlo
   explícitamente, en un sitio, en vez de heredarlo.

---

## Lo que esta revisión enseña sobre la sesión que revisa

El bloqueante no fue un descuido cualquiera: **es el mismo defecto que yo había
diagnosticado un día antes en el §2.1 del documento de arquitectura** —«ninguna
de las nueve remite a otra»— cometido un piso más arriba. Arreglé el cableado
herramienta→herramienta y dejé sin cablear instrucciones→herramienta.

Y no es el único caso. `Escalera.subio` es la misma familia que los cuatro
`umbral_vecino` con tres valores (BUG-0087) y las dos copias de la regla de λ
(BUG-0080), cometida **el día después** de arreglar ésas.

La lectura útil no es «hay que tener más cuidado». Es que **el patrón que la
sesión perseguía tiene una capa más de la que el documento de arquitectura
identificó**:

> La capacidad está abajo, la superficie no la nombra — y el que escribe la
> superficie es el mismo que acaba de arreglar el mismo defecto un piso más
> abajo.

De ahí que las dos defensas que valen sean pruebas y no disciplina: la que
comprueba que toda herramienta está en `_INSTRUCTIONS`, y la que comprueba que
no quedan umbrales literales repartidos. Las dos fallan solas cuando alguien
—yo— reincide.
