# Los contrastes formales — doctrina de `formal_tests`

Salido de la descripción de `formal_tests` en ORDEN 1.2: del canal que se
empuja al que se pide. Se cita como `art://doc/DISENO-contrastes-formales`.

## 1 · Qué significa «(experimental)», que no es lo que parece

**Casi todo está publicado y establecido.** Los modelos son antiguos —Abraham y
Box (1978)—; la idea de resolver la estacionalidad frecuencia por frecuencia
está en HEGY (Hylleberg, Engle, Granger y Yoo); el DCD (Davis, Chen y Dunsmuir)
está publicado; el Shin-Fuller está publicado.

**Lo nuevo es poco, y menos de lo que la palabra sugiere:** los valores críticos
derivados por Monte Carlo, que difieren por un margen marginal de los
interpolados ya publicados, y —sobre todo— **la implementación de `art`**, que
es donde están los tres defectos abiertos.

Así que «(experimental)» es una **salvaguardia**, no un aviso de que el método
sea dudoso. El método está establecido; lo que no está avalado es esta
implementación y el último decimal de los críticos.

**Puedes ofrecerla.** Preguntar al analista si quiere evaluar la naturaleza de
la estacionalidad —determinista o estocástica, frecuencia por frecuencia— es
una pregunta legítima, y hay analistas que la quieren siempre. Ofrécela marcada
«(experimental)», no como camino por defecto. Lo que **no**: tomar una decisión
de especificación apoyándote sólo en ella. Contrástala con Shin-Fuller y con la
acf/pacf, y si su veredicto contradice al resto del informe, hoy es más probable
que el fallo esté aquí que en los otros instrumentos.

## 2 · El nombre: HSM, y por qué el código dice MEG

La clase se llama **HSM** —Hybrid Seasonal Models—, que es como la nombra el
artículo de referencia (SF_MEG). **MEG**, Modelos de Estacionalidad Generalizada
(Gallego, 1995), es su nombre en la literatura española y el identificador que
conserva el código. En prosa, di HSM.

## 3 · Las dos líneas, y por qué HSM no es una tercera

    DETERMINISTA   armónicos con coeficientes de previsión fijos
    ESTOCÁSTICA    SARIMA multiplicativo, la diferencia anual 1−Bˢ entera

HSM no es una tercera línea: es la **forma canónica de Abraham y Box (1978)**,
en la que cada frecuencia es independientemente una u otra, y que **anida las
dos líneas como casos especiales**. Ellos ya distinguen componentes
deterministas de *forecast-adaptive* y notan que un modelo puede ser adaptativo
en unos parámetros y no en otros. Esa ruta es la experimental.

## 4 · Los contrastes que corre

    Shin-Fuller (1998)  Φ₁ᵤ; H₀: ρ = 1−4/n (raíz casi unitaria); crítico 5% ≈ 1,75
    DCD                 no invertibilidad de factores MA regulares (H₀: θ=1)   [exp.]
    DCD_f               no invertibilidad de factores MA estacionales (H₀: λ₂=−1) [exp.]
    RV                  frecuencia fijada para factores AR(2)
    MEG                 barrido HSM: estocástica frente a determinista,
                        frecuencia por frecuencia (exige D=0 + armónicos)      [exp.]

## 5 · Los tres defectos abiertos, todos en esta familia

| | |
|---|---|
| **BUG-0009** | `dcd_overdiff_regular` pisa el testigo de Nyquist —comparten la ranura de MA regular y miden raíces **opuestas** (B=+1 frente a B=−1)— y recomienda d+1 sobre una d correcta. |
| **BUG-0010** | Podar un armónico no significativo anula el barrido MEG **entero**, la excepción se traga, y el informe cierra diciendo que el modelo es adecuado mientras se pierde una frecuencia genuinamente estocástica. **Por eso el MEG va ANTES de podar armónicos.** |
| **BUG-0011** | `dcd_overdiff_regular` recomienda d+1 en toda especificación de un índice de precios, incluida la línea base que su propio docstring prescribe. Causa establecida: los armónicos deterministas compiten con el testigo, y la precondición nombraba al competidor equivocado. |
