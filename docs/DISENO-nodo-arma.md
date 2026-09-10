# El nodo ARMA — doctrina de `confirm_and_estimate`

Esto es lo que salió de la descripción de `confirm_and_estimate` en ORDEN 1.2.
No se ha borrado nada: se ha movido del canal que se **empuja** —la descripción
de la herramienta, que viaja entera en cada llamada y llega recortada— al que
se **pide**. Se cita desde la herramienta como `art://doc/DISENO-nodo-arma`.

---

## 1 · El AR como PRODUCTO de factores, y por qué nunca se capa

`fue` estima el AR regular como un producto de factores, y así es como esta
escuela lee un operador: **cada factor tiene su amortiguamiento y su período**.

    p = 6            un operador de orden 6
    p = [1,1,2,2]    cuatro factores — el modelo FACTORIZADO

La forma factorizada es una reparametrización **exactamente identificada** del
mismo modelo: misma verosimilitud, mismos grados de libertad. Su valor no es
ajustar mejor —no puede—, es que cada factor obtiene su `d ± SE` y su
`período ± SE`, sin los cuales **no se puede contrastar si un factor admite la
frecuencia estacional**.

> **Nunca sustituyas un AR(p) por un operador capado o disperso porque sus
> módulos se parezcan.** Eso impone p−1 restricciones **sin contrastar** y
> cierra la puerta a Shin-Fuller. El orden es: estimar el operador completo,
> factorizarlo, y entonces contrastar.

`ar_seeds` da los valores de partida por factor —`ar_factorization` los
calcula—, para que al partir un operador ya estimado el ajuste arranque en el
óptimo que ya había encontrado.

`ar_f_freqs` son las frecuencias k de los factores AR(2) de **frecuencia
fijada**: cada uno es (1 − φ₁B − φ₂B²) con la frecuencia clavada en 2πk/s, de
modo que sólo se estima φ₂ y φ₁ se deriva. Es la versión **contrastable** de
«este factor es estacional»: está anidada en el factor libre, así que una razón
de verosimilitudes con 1 g.l. lo decide. Sin ella, la única forma de afirmar
que un factor es estacional era imponerlo.

Ver también BUG-0103 (`art://defectos/0103`).

## 2 · `P` y `Q` funcionan con `D=0`, y no es un caso raro

Una **estacionalidad estocástica estacionaria montada encima de los armónicos
deterministas** es la forma que tiene la ruta B1 de absorber lo que los
armónicos dejan. Los dos modelos finales de RATIO de esta réplica son
exactamente eso —P=1 con D=0— y `_make_model` lo construye desde siempre.

BUG-0050: esta línea decía «(D=1 only)». Era falso y caro: quien se lo creyera
concluiría que un AR estacional residual obliga a D=1, o sea a la ruta B2 — la
única que `objetivo="multivariante"` prohíbe. **La documentación mandaba a la
ruta prohibida a resolver un problema que la ruta permitida resuelve.**

Y una nota sobre `Q`: los operadores de frecuencia fijada (`ar_f`/`ma_f`, donde
vive el testigo MA_f del MEG) **no** los gobierna `Q`. Se heredan de
`base_pre_path` como estructura, junto con `ifadf` (BUG-0034).

## 3 · `objetivo` — lo único que los datos no pueden dar

`univariante` (prever la serie), `multivariante` (entra en un sistema: VECM,
función de transferencia) o `estructural` (leer los componentes).

Se pregunta como **propósito** y no como método para que una sola respuesta
informe a varios nodos. Donde más pesa es en la ruta estacional: con
estacionalidad detectada el pipeline estima **las dos** —B1 con D=0 y armónicos,
B2 con D=1— y las arbitra con el par MEG/DCD_f. `objetivo` rompe el empate
cuando los contrastes no deciden, y **veta B2 bajo «multivariante»**: las raíces
unitarias estacionales complican la cointegración, y todas las series de un
sistema tienen que llevar el mismo tratamiento estacional o sus órdenes de
integración no son comparables.

## 4 · `domain` — se registra y se contrasta

`price_index` | `multiplicative` | `ratio` | `generic`. Es un dato **del
analista**: no se puede recuperar releyendo el `.inp`, y por eso se registra en
el guion. Y se **contrasta** con la λ que se pasa: declarar `price_index` con
λ=1 es una contradicción y la herramienta lo dice.

Es exactamente el fallo que motivó BUG-0080 — art recomendó «identidad (λ=1)»
sobre un índice de precios y el carril guiado no ofrecía la corrección.

## 5 · `estimate_mu` — con qué t se decide

Ponlo a True cuando la **deriva de la serie diferenciada** tenga |t| > 2. **No**
la media de los residuos de un modelo que ya ajustó una μ, que sale ~0 por
construcción (BUG-0013). Cuando `base_pre_path` trae una media ajustada, se
hereda: pasa True para conservarla.
