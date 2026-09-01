# TODO — intervenciones como funciones de transferencia en ART

**Estado:** abierto · **PRIORIDAD MÁXIMA** · **Abierto el** 2026-08-26 ·
**Reordenado el** 2026-09-02 tras medir las cuatro corridas · **Origen:** réplica
del TFM de Bolivia, nodo A4 de `ITCER` (episodio 2008:4–2009:2)

---

## ⚑ Por qué esto va primero — la medida

Cerradas las cuatro corridas (dos LLM × cuatro runs), **el nodo de intervención es
el mayor pozo de mejora medido del proyecto**, y por un margen que no admite
discusión:

| corrida | ITCER interv. | ΔAIC | PGAS interv. | ΔAIC |
|---|---|---|---|---|
| benchmark guiado | 1 · ω(B) | — | 1 | — |
| runs 1, 2 y 4 (los dos carriles) | 1 | **+6,15 a +8,84** | 1 | −0,93 |
| **run 3 claude** | **2** | **−1,09** | **2** | **−16,24** |
| runs 2-4 ds | 1 | +6,15 | 1–2 | −0,31 / +6,66 |

**Encontrar la segunda intervención del episodio 2008-09 vale entre 7 y 15 puntos
de AIC, y sólo una de ocho corridas la encontró en las dos series.** Ninguna otra
palanca del ejercicio —ni la ruta estacional, ni los órdenes ARMA, ni la
transformación— movió tanto.

Y un matiz que cambia el diseño: `run3 ds` y `run4 ds` **también** pusieron dos
intervenciones en PGAS y salieron PEOR (−0,31 y +6,66). El problema no es contar
dos: es **encontrar las dos correctas, en la fecha y la forma correctas**.

### Corrección de rumbo: el ω(B) no era la prioridad

Este TODO se abrió por el ω(B), y la medida lo desmiente. En el RUN 3, **dos
escalones escalares batieron al ω(B) del benchmark** —379,91 contra 381,00— con
los mismos tres parámetros.

Lo que falta no es la forma rica del operador: es **buscar el segundo evento**. El
ω(B) sigue siendo deseable (§2-§5 de este documento), pero **detrás** del nodo por
episodios.

---

## ⚑ 0. Nodo de intervención por EPISODIOS — lo primero de todo

Hoy `suggest_intervention_form` propone la forma de **un** residuo extremo. Nadie
sugiere que un episodio pueda necesitar **dos**, ni ofrece el contraste entre las
especificaciones rivales.

**Lo que debe hacer.** Cuando dos o más residuos extremos caen a distancia ≤ 2-3
períodos, son **un episodio**, y el nodo ofrece las especificaciones rivales y las
estima:

| candidato | qué es |
|---|---|
| A | una intervención (escalón o impulso) en el primer punto |
| B | **dos intervenciones escalares, una por punto** |
| C | una intervención con ω(B) de orden 1 |

Las tres son comparables —misma serie, misma `d`, misma transformación— así que el
AIC decide y el LR contrasta A ⊂ C y A ⊂ B donde estén anidadas. Es exactamente lo
que hizo a mano el analista del RUN 3, y le valió los dos únicos ΔAIC negativos
grandes del ejercicio.

**Por qué el nodo y no el analista.** En ocho corridas, siete no lo intentaron. No
es falta de criterio: es que **nada en la salida sugiere que la pregunta exista**.
El escaneo de anómalos enumera puntos, no episodios.

### Piezas concretas

1. **`agrupa_episodios(residuos, z, ventana=3)`** — de la lista de residuos
   extremos a una lista de episodios. Un episodio es un evento con posible
   estructura interna; un punto aislado sigue tratándose como hoy.
2. **El nodo estima los rivales y los presenta juntos**, con AIC, LR donde aplique
   y diagnosis de cada uno. No elige: pone los tres delante.
3. **La forma se decide por la aritmética de la diferencia**, que ya está escrita
   en las instrucciones: un escalón en el nivel deja UN pico en ∇y; un impulso
   deja un pico y otro de signo opuesto detrás. El nodo debe **calcular** esa
   firma sobre los datos, no dejarla al ojo.
4. **Y debe decir cuándo NO hay episodio**: dos puntos lejanos no son un episodio,
   y ofrecer los tres candidatos ahí sería ruido.

### Lo que hay que medir antes de darlo por bueno

* Sobre los cuatro episodios conocidos (ITCER 2008:4–2009:2, PGAS 2009:1–2009:2,
  RATIO 2020:2 y 2008:4): ¿propone el conjunto correcto?
* **Falsos episodios**: sobre series sin evento múltiple, ¿cuántas veces agrupa
  dos anómalos independientes? Es el riesgo simétrico y hay que acotarlo.
* ¿Cuánto cuesta? Tres estimaciones por episodio, y hay que ver si el carril
  autónomo las paga o las esquiva.

---

## ⚑ 0.b Mejorar el análisis de intervención en general

Por debajo del nodo por episodios, la misma revisión tiene tres piezas más que la
réplica dejó documentadas:

* **La forma auto-seleccionada no compensa el desfase de la diferencia**
  (BUG-0067 del ejercicio SF_MEG): con un modelo diferenciado, la fecha del
  residuo extremo no es la fecha de la intervención. Está arreglado allí; hay que
  comprobar que el nodo por episodios lo hereda.
* **La FLT se imprime con el signo crudo** (BUG-0066 de SF_MEG): el display dice
  ω₀+ω₁B cuando el motor estima ω₀−ω₁B. Cualquier presentación nueva de
  intervenciones tiene que fijar la convención de signo **una vez** y que todo la
  use.
* **La cabecera cuenta los armónicos como intervenciones** (visto en RATIO del
  RUN 4): cosmético, pero confunde determinista-de-calendario con evento.

---

## El hecho que lo motiva

`fue` soporta intervenciones como **funciones de transferencia lineales**
completas — su propio docstring lo dice: *«Deterministic component with linear
transfer function. The effect on the series is `ω(B)/δ(B)·x_t`»* — y el formato
`.inp`/`.pre` las transporta con round-trip exacto. **ART no llega a nada de
eso.**

| capa | ω(B)/δ(B) | comprobado |
|---|---|---|
| motor `fue` (C + Python) | completo: `omega`, `delta`, `omega_free`, `delta_free`; tipos `impulse`, `compimp`, `step`, `ramp`, `custom` | estima ω de orden 2 sin problema |
| formato `.inp`/`.pre` | completo: `step 4 2008`, orden de ω, pares coef/bandera, orden de δ | round-trip exacto en `step` y `impulse` |
| **capa ART** | **sólo `omega=[0.0]`**, escalar, sin δ | `mcp_server.py:2841` lo fija |

`suggest_intervention_form` expone `form ∈ {pulse, step, ramp, auto}`: un
coeficiente escalar sobre una forma fija. Toda la maquinaria del motor es
inalcanzable desde el flujo guiado y desde el autónomo.

## Por qué importa, con el caso concreto

En `ln ITCER`, la primera diferencia da −11,36% en 2008:4, −2,33% en 2009:1
(z=−0,59: nada) y +6,56% en 2009:2. Integrando, eso son dos impulsos en el nivel.
Hay dos especificaciones defendibles:

1. **Impulsos:** `(ω₀ − ω₁B) Ξ^impulse, 2008:4`
2. **Escalones:** `(ω₀ − ω₁B − ω₂B²) Ξ^step, 2008:4`

**No son alternativas: la 2 anida a la 1.** Con `d=1` las intervenciones se
especifican sobre el nivel, así que:

| input | efecto sobre el nivel | efecto permanente |
|---|---|---|
| impulso, ω(B)=ω₀−ω₁B | ω₀ en T, −ω₁ en T+1, 0 después | **cero por construcción** |
| escalón, ω(B)=ω₀−ω₁B−ω₂B² | ω₀, luego ω₀−ω₁, luego ω₀−ω₁−ω₂ para siempre | **ω(1)**, libre |

Elegir el input **es** elegir si la ganancia de largo plazo está restringida a
cero. Lo correcto no es elegir sino estimar la 2 y contrastar **H₀: ω(1)=0** —
una restricción lineal única. Si no se rechaza, la 1 queda *justificada* en vez
de supuesta. Hoy ART obliga a suponerla.

---

## Los puntos, en el orden en que los haría

### 1. ~~La línea `ifadf` vacía rompe el round-trip~~ — hecho

BUG-0026, arreglado. Era la mina que habrían pisado los tests de todo lo demás:
los modelos con ω(B) se construyen a mano y `fue.Model` deja `ifadf=[]`.

### 2. `intervention_response(date, max_lag)` — **la pieza que más falta**

Hoy ART **no puede ver la forma** de una respuesta a intervención: sólo postular
una y estimarla. Sin esto, añadir `omega_order` traslada la adivinanza de «¿pulso
o escalón?» a «¿qué orden?».

La vía es la clásica de Box-Tiao: ajustar la respuesta **libre** —impulsos
consecutivos en T, T+1, …, T+k, todos con coeficiente libre— y **dibujar la
respuesta estimada con sus bandas**, leyendo k de donde muere. Eso identifica el
orden antes de estimarlo, que es el orden correcto de las operaciones y el que la
escuela impone en todo lo demás.

Va **antes** que el punto 3.

### 3. `omega_order` / `delta_order` en `suggest_intervention_form`

Pasados directos a `fue`. Con `0/0` el comportamiento actual no cambia: no rompe
nada existente.

**Nota de diseño.** La tentación es hacer de esto la interfaz principal. No lo
haría: el analista no piensa en «orden 2», piensa en «¿vuelve o no vuelve, y en
cuántos trimestres se ajusta?». Los órdenes son la respuesta, no la pregunta —
por eso el punto 4 no es cosmético.

### 4. Reportar ω(1) automáticamente

Cuando el input sea `step` y `omega_order ≥ 1`, ART debe reportar **ω(1), su
error típico y el LR de H₀: ω(1)=0**, etiquetado como ganancia de largo plazo /
efecto permanente. Ése es el número por el que existe la especificación; no
debería exigir que el analista lo componga a mano desde tres coeficientes y una
matriz de covarianzas.

Simétricamente, con input `impulse`: decir que el efecto permanente es **cero por
construcción**, para que se vea lo que se ha supuesto en vez de que pase
inadvertido.

### 4b. El contraste de ganancia nula falta en `simplify_interventions`

**Este es el sitio natural del punto 4, y hoy no está.** La sección de
simplificación de intervenciones existe (`interventions.py:397`
`simplify_interventions` → `test_intervention`), pero lo que contrasta es
**H₀: ω=0 para cada ω libre por separado**, con t individuales. Su propio
docstring acota el alcance:

> *«For FLTs **with delta**, an additional joint Wald test is performed:
> H₀: g = α·ω = 0, α = (1, −δ₁, −δ₂, …)»*

El contraste conjunto **sólo se ejecuta cuando hay denominador**. Para una
intervención FIR pura — ω de orden ≥1 **sin δ**, que es el caso corriente — no
hay ningún contraste de la ganancia de largo plazo.

Y esa es precisamente la simplificación que da sentido a la sección: **contrastar
si una secuencia de escalones se puede restringir a impulsos por tener ganancia
nula en el largo plazo.** Es la simplificación estructural del apartado, no un
extra:

```
   escalon con  ω(B) = ω₀ − ω₁B − ω₂B²      y   ω(1) = 0
        ⇔  impulso con ω̃(B) de un orden menos
```

Los dos modelos están **perfectamente anidados**: con ω(1)=0 el escalón conserva
dos parámetros libres y genera exactamente el mismo espacio que el impulso — una
excursión de dos períodos. Una restricción lineal, un grado de libertad.

**Medido en `ln ITCER`, episodio 2008:4** (por `fue` directamente, porque ART no
llega):

| | logL | ω̂ |
|---|---|---|
| impulso, ω orden 1 | 196,196 | −0,0832 · +0,0814 |
| escalón, ω orden 2 | 196,808 | −0,0991 · +0,0166 · −0,0662 |

ω(1) = −0,0495 (−4,95% permanente); LR = **1,223**, χ²(1), **p = 0,269** → no se
rechaza. El episodio fue **transitorio**, y eso queda *contrastado* en vez de
supuesto. Yendo directo al impulso se impone por decreto la respuesta a la
pregunta que más interesa.

**Y el caso de VARIAS intervenciones, que es donde más falta hace.** Cuando el
efecto está repartido entre **escalones consecutivos**, la ganancia no vive dentro
de una ω(B): es la **suma de las ganancias individuales**, una combinación lineal
que cruza intervenciones. Ninguna capa la calcula hoy, y es justo la que hay que
mirar, porque los coeficientes individuales **no están identificados**.

Medido en `ln PGAS` sobre el episodio 2008–2009, con el mismo AR(2) debajo:

| especificación | ganancia LP | **ee** | p(gain=0) |
|---|---|---|---|
| 1 escalón (2009:1) | −0,195 | **0,063** | 0,002 |
| 2 escalones (2008:3, 2009:1) | −0,177 | 0,082 | 0,030 |
| 2 escalones (2008:1, 2009:1) | −0,103 | 0,089 | 0,246 |
| 3 escalones (2008:3, 2008:4, 2009:1) | **+0,427** | **0,227** | 0,060 |

Cada escalón añadido **multiplica el error típico de la ganancia** — ×3,6 al pasar
de uno a tres — hasta invertirle el signo. La causa es estructural: con `d=1` un
escalón es casi colineal con el propio paseo aleatorio (los dos desplazan el nivel
de forma permanente), y varios escalones consecutivos lo son entre sí. El reparto
lo delata: el escalón de 2009:1 vale −0,199 con dos y **−0,036** con tres, un
factor 5,5, mientras la verosimilitud apenas se mueve.

Sin la ganancia y **su error típico** delante, esa degeneración es invisible: los
tres modelos tienen diagnosis limpia y el de tres escalones es el que mejor JB da.

Lo que hay que añadir a `test_intervention`, para toda intervención con ω de
orden ≥ 1 **haya o no δ**, y para todo GRUPO de intervenciones del mismo tipo:

- **ω(1)** (con δ: la ganancia estacionaria ω(1)/δ(1)), su error típico por el
  método delta y el Wald / LR de H₀: ganancia = 0;
- la lectura explícita: *«ganancia nula ⇒ el efecto es transitorio ⇒ este escalón
  se puede restringir a impulso»*, que es la acción de simplificación;
- **la ganancia AGREGADA de los escalones del modelo** —suma de las
  individuales— con su error típico por combinación lineal `√(c'Vc)` y su Wald.
  Es la magnitud identificada cuando las individuales no lo están, y su `ee`
  creciente es el único aviso de que se están añadiendo escalones colineales;
- y con input `impulse`, decir que la ganancia es **cero por construcción**, para
  que se vea lo supuesto en lugar de que pase inadvertido.

### 5. Sobreparametrización obligatoria sobre el bloque ω

Con ω de orden 2 en una sola fecha, los coeficientes salen de ~3 observaciones.
Es la misma trampa que produjo `corr(AR(1),AR(2)) = −0,964` en `ln PGAS`.
`overparameterization_analysis` debería correr sobre el bloque ω y reportar las
correlaciones **sin que haya que pedirlo**.

### 6. Acceso al tipo `custom`

ω(B) **no expresa cómodamente «T y T+2 pero no T+1»**, que es justamente la forma
que se sospecha en el episodio 2008–2009: entre los dos extremos hay un trimestre
con z=−0,59. Un ω de orden 2 obliga al modelo a decir algo de 2009:1 y gastará un
parámetro en estimar ω₁≈0. Es contrastable, así que no es incorrecto — pero
cuando la forma real tiene huecos, `custom` con indicador explícito es más
honesto. ART tampoco lo alcanza hoy.

---

## Lo que este TODO **no** cubre

La identificación del orden con `n` corto sigue siendo un problema estadístico,
no de API: el punto 2 lo hace visible y el 5 lo hace ruidoso, pero ninguno lo
resuelve. Con 84 observaciones y un evento, ω de orden alto no será estimable
por muchos gráficos que se dibujen — y eso es correcto que se vea.
