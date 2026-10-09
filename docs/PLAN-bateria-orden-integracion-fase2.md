# Fase 2 de la batería del orden de integración — tamaño, potencia y la regla del árbol

Fecha: 8-oct-2026. Sigue a `research/bateria_contrastes_d.py` (fase 1: QUÉ contrastes lanza
art) y a `docs/ARBOL-orden-de-integracion.md`. Bugs que valida: BUG-0224, 0232, 0235, 0236,
0237.

## 1. La pregunta

La fase 1 estimó cada serie con su d verdadera, así que sólo pudo decir qué se lanza. La
fase 2 tiene que decir **si se acierta**:

1. **Cada contraste por separado**: su tamaño (cuántas veces rechaza una nula verdadera) y su
   potencia (cuántas veces rechaza una falsa), estimando con la d verdadera, con una de menos
   y con una de más.
2. **La regla del árbol entera** (pares, tabla de verdad, par cruzado con d=2): con qué
   frecuencia llega a la d verdadera, y con qué frecuencia dice «ambiguo» o «indeterminado».
3. **Frente a lo que hay**: la política ADF+KPSS de art (pasos 2 y 3) y `ndiffs` de pmdarima
   (KPSS y ADF).
4. **Los defectos registrados**, medidos antes y después de arreglarlos con el mismo arnés.

## 2. Los modelos verdaderos

| Grupo | Estructuras | d |
|---|---|---|
| base | ruido; AR(1) φ = 0,5; MA(1) θ = 0,5; ARMA(1,1) 0,6/0,3 | 0, 1, 2 |
| cerca de la raíz unitaria (la banda) | AR(1) φ = 0,8 · 0,9 · 0,95 · 0,98; ARMA(1,1) señal + ruido 0,95/0,7 | 1 y 2 |
| MA cerca de 1 (cerca de sobrediferenciar) | MA(1) θ = 0,9 · 0,95 | 1 y 2 |
| AR(2) | reales 0,5/0,3; complejo de ciclo corto (periodo 8, r = 0,7); **complejo de ciclo largo** (periodo 36, r = 0,97: imita (1 − B)², árbol §5.4) | 0, 1, 2 |
| tendencia determinista (Chan y Wallis) | I(0) alrededor de una recta | 0 |
| contaminados (Villaverde) | AR(1) 0,5 con d = 1 más (a) tres escalones de nivel de 4σ; (b) un cambio de varianza a la mitad (σ × 0,4) | 1 |
| los casos reales | los parámetros estimados de Salamanca (AR(4); IMA(1) 0,75) y Villaverde (AR(7)) | 1 y 2 |

- **Tamaños:** n = 100 y n = 200 (los distritos tienen 188).
- **Frecuencia 12**, sin estacionalidad, como los distritos.
- **Repeticiones:** 50 en el piloto (±7 pp) y 200 en las celdas de la frontera (±3,5 pp).

## 3. Qué se estima en cada serie

Para cada serie, **tres modelos**: con d_verdadera − 1 (si ≥ 0), d_verdadera y
d_verdadera + 1 (si ≤ 2). Y dos brazos de órdenes:

- **oráculo:** los órdenes ARMA verdaderos;
- **identificados:** los que art pone primero (`suggest_orders`, opción B) en esa d. Es lo que
  pasa en la práctica, y es donde aparecen los AR largos que absorben persistencia (Salamanca).

Sobre cada modelo: `confirm_and_estimate` y `formal_tests(subdiferenciacion=True,
run_meg=False)`, más `describe_unit_root` + `policy.decide_d` (la política ADF+KPSS) y
`pmdarima.arima.ndiffs` sobre la serie.

## 4. Qué se mide

**Por contraste** (en cada d de estimación):

| Contraste | Nula verdadera cuando… | Tasa que se mide |
|---|---|---|
| SF (directo y por sobreajuste) | se estima con d < d verdadera | rechazo: tamaño o potencia, según la celda |
| DCD de sobrediferenciación | se estima con d ≥ d verdadera | rechazo |
| DCD de subdiferenciación | se estima con d > d verdadera | rechazo; y, con AR libre, cuántas veces dice «d−1 bastaba» en falso (BUG-0224) |
| los dos DCD de la misma frontera (§1.2) | — | % de acuerdo entre el de sobrediferenciación desde d y el de subdiferenciación desde d+1 |

**Por la salud del cálculo:** % de LR no finitos o negativos y % de testigos con θ̂ < 0
(BUG-0232, 0236).

**Por la puerta de adecuación** (BUG-0237): % de modelos verdaderos declarados «no adecuados»,
con la regla de hoy y con dos alternativas (Holm sobre los criterios; la Q sólo en 3s+3 y lo
demás como salvedad).

**Por la regla del árbol:** la d final (0, 1, 2, «ambiguo», «indeterminado») frente a la
verdadera, en una matriz de confusión por celda. Es el resultado que importa: si en la banda
(φ ≈ 0,9-0,98) dice «ambiguo» y fuera de ella acierta, la regla funciona.

**Comparación:** % de acierto en d de la regla del árbol, de la política ADF+KPSS de art y de
`ndiffs` (KPSS, ADF), sobre las mismas series.

## 5. Coste y ejecución

- Una serie son hasta tres estimaciones con `formal_tests`: unos 10-15 s.
- La rejilla completa (unas 40 celdas × 2 tamaños × 200 repeticiones) son 16.000 series:
  más de 50 h en un núcleo, unas 13 h en los 4 de esta máquina. Por eso, en dos tandas:
  1. **Piloto:** 50 repeticiones, n = 200, todas las celdas, brazo oráculo. Unas 3-4 h con 4
     procesos.
  2. **Foco:** 200 repeticiones en las celdas donde el piloto vea problemas (la banda, los
     contaminados, los AR largos, d = 2), y el brazo identificado.
- **Arnés:** `research/fase2_orden_integracion.py`, con `multiprocessing` (4 procesos), un CSV
  con una fila por serie y modelo (reanudable: si se corta, sigue donde iba) y un
  `research/fase2_resumen.py` que saca las tablas.
- **Antes y después:** el mismo arnés, con la misma semilla, sobre el código de hoy y sobre
  cada arreglo (0224, 0232, 0235, 0236, 0237). Cada arreglo se cierra con su delta.
- Se lanza cuando termine `ART_18/tests/benchmark_arima.py`, que ahora ocupa la CPU.

## 6. Lo que saldrá de aquí

1. Si la regla del árbol es mejor que la política ADF+KPSS y que pmdarima para decidir d, y
   en qué celdas.
2. Cuánto pesan en la práctica los defectos registrados.
3. Si la puerta de adecuación necesita una corrección por multiplicidad, y cuál.
4. Cómo construir en art el par cruzado de la frontera 1/2 (BUG-0235), con la evidencia de
   qué DCD manda cuando los dos de la misma frontera discrepan (§1.2 del árbol).
