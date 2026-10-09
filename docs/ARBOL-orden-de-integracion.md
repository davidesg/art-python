# El orden de integración con Shin-Fuller y el DCD — árbol de decisiones

Fecha: 8-oct-2026. Origen: los análisis guiados de Salamanca y Villaverde (P02), BUG-0226,
0227, 0232, 0235.

## 1. La lógica matemática

El modelo es φ(B) ∇^d w_t = θ(B) a_t. El orden de integración en f = 0 es el número de
factores (1 − B). Toda la cuestión de una frontera d / d+1 es **dónde está el factor
(1 − B) que sobra o falta**, y sólo puede estar en dos sitios:

- **En el AR del modelo en d**, como una raíz real positiva en 1: φ(B) = (1 − ρB)·φ*(B) con
  ρ = 1. Entonces falta una diferencia. Es lo que contrasta **Shin-Fuller**: H₀: ρ = 1
  (en la práctica ρ_m = 1 − 4/n, la vecindad local de la unidad).
- **En el MA del modelo en d+1**, como una raíz en 1: si la serie es I(d), diferenciar una
  vez más multiplica el lado MA por (1 − B), así que el modelo en d+1 tiene θ = 1 exactamente.
  Entonces sobra la diferencia. Es lo que contrasta el **DCD**: H₀: θ = 1 en un MA(1).

De ahí salen tres hechos que ordenan el árbol:

1. **Los dos lados tienen nulas opuestas sobre la misma pregunta.** SF en d tiene como nula
   «hace falta d+1»; el DCD sobre ∇^{d+1} tiene como nula «basta con d». Por eso se leen en
   par: cada uno sólo puede rechazar su propia nula.
2. **El DCD de sobrediferenciación desde d y el DCD de subdiferenciación desde d+1 contrastan
   la MISMA hipótesis**: si la (d+1)-ésima diferencia se cancela con θ = 1. Difieren sólo en
   el ARMA que acompaña al testigo:
   - sobrediferenciación desde d: el AR del modelo en d, reestimado dentro de ∇^{d+1}, y el
     testigo en lugar de su MA;
   - subdiferenciación desde d+1: el ARMA que se ha estimado para el modelo en d+1.

   Asintóticamente deben coincidir. **Si no coinciden, el resultado depende de la
   representación**, y eso es información: en Salamanca el AR(4) dentro de ∇² dio LR 1,88
   («se cancela»), y el IMA en d=2 dio LR 92,9 («genuina»). El AR(4), con cuatro coeficientes
   libres, absorbe la persistencia que el testigo tendría que leer.
3. **Así que el par opuesto real de una frontera d / d+1 es SF en d frente a un DCD sobre
   la (d+1)-ésima diferencia**, el de sobrediferenciación o el de subdiferenciación del
   modelo en d+1. Cuando los dos DCD no coinciden, manda el del modelo más parsimonioso.

### La tabla de verdad de una frontera

Con nulas opuestas hay cuatro resultados posibles, y no son simétricos:

| SF en d (H₀: ρ = 1) | DCD de la ∇ d+1 (H₀: θ = 1) | Lectura | Qué hacer |
|---|---|---|---|
| rechaza: ρ < 1 | no rechaza: θ → 1 | coinciden en **d** | d |
| no rechaza: ρ ≈ 1 | rechaza: θ < 1 | coinciden en **d+1** | estimar d+1 |
| rechaza: ρ < 1 | rechaza: θ < 1 | **los dos rechazan su nula**. Bajo una verdad exacta (I(d) o I(d+1)) es imposible: si fuera I(d), θ sería 1; si fuera I(d+1), ρ sería 1. Hay que mirar **a qué distancia de 1 está el testigo θ̂** (el criterio de art, del paper SF_MEG, `tab:compare`): **a 0,10 o menos** (θ̂ ≳ 0,90) es la **banda de cuasi-cancelación**, una raíz cercana a 1 pero menor, y los dos tienen razón → ambiguo (Salamanca, Villaverde: θ̂ 0,93-0,95). **Más lejos** (Chamberí: θ̂ = 0,77, a 0,23), no es la banda: las representaciones difieren de verdad, y manda el resto de la evidencia (el otro DCD de la misma ∇, el SF de otros modelos, el nivel del SF) | dentro de la banda: ambiguo (parsimonia o fuera de muestra). Fuera: estimar el candidato rival y decidir con el conjunto |
| no rechaza | no rechaza | **ninguno rechaza**: los contrastes no tienen potencia (muestra corta, mucho ruido) | indeterminado: quedarse en d por parsimonia y decirlo |

La primera versión de este documento llamaba «contradicción» a la última fila; no lo es.
Contradicción, bajo una verdad exacta, sería la tercera; en la práctica es la banda cuando el
testigo está cerca de 1, y una diferencia real entre representaciones cuando no lo está
(corregido el 8-oct-2026 con Chamberí).

### La tendencia determinista (Chan y Wallis)

Si el nivel es estacionario alrededor de una **recta** (I(0) con tendencia), diferenciarlo
deja un MA con raíz en 1 y una media μ ≠ 0. Entonces el DCD de subdiferenciación en d=1
dice «la ∇ se cancela», pero la conclusión no es «d=0 sin más», sino **d=0 con tendencia
lineal**. En precios e índices no se plantea (el dominio da d ≥ 1); en un ratio con deriva,
sí.

## 2. Las reglas que valen para todo el árbol

1. **Un paso cada vez.** d se mueve entre 0, 1 y 2. Desde d=0 sólo se pregunta por d=1;
   desde d=1, por d=2 (subir) o por d=0 (bajar); desde d=2, sólo por d=1 (bajar). Una
   tercera diferencia no se contrasta (BUG-0235).
2. **Antes de leer los contrastes, el modelo tiene que ser adecuado**: residuos de ruido
   blanco, estacionalidad tratada, anómalos tratados. Las distribuciones nulas suponen ruido
   blanco; si no lo es, lo que sale es informativo, no concluyente (Villaverde).
3. **El dominio acota d=0.** Un precio o un índice no son I(0); d=0 sólo se plantea para
   ratios, tasas o saldos (o para una relación de cointegración).
4. **Cada frontera se lee en par** (sección 1) y con su tabla de verdad.

## 3. Los contrastes y lo que necesitan del modelo

| Contraste | Pregunta | H₀ | Se aplica sobre | Necesita |
|---|---|---|---|---|
| **Shin-Fuller (SF)** | ¿falta una ∇? (d → d+1) | raíz AR **real positiva** en 1 | el modelo en d | un AR regular libre con una raíz real positiva |
| **DCD sobrediferenciación** | ¿sobraría la ∇ siguiente? (d → d+1) | θ = 1 en un testigo MA(1) sobre ∇^{d+1} | un candidato construido desde el modelo en d | nada; ver condicionales |
| **DCD subdiferenciación** | ¿sobraba la última ∇? (d → d−1) | θ = 1 en el MA(1) que cancelaría la ∇ | el modelo en d (d ≥ 1) | nada; ver condicionales |

Los DCD se leen con la ley s = 1, crítico al 5 % ≈ 1,94:
- **LR < 1,94** (θ̂ → 1, no invertible): la diferencia se cancela, sobra.
- **LR ≥ 1,94** (θ̂ < 1, invertible): la diferencia es genuina.
- **Un LR no finito** (−inf) no es un veredicto, sino un fallo numérico (BUG-0232).

## 4. Los condicionales: qué ARMA lleva el modelo

| El modelo en d tiene… | SF | DCD sobrediferenciación (candidato ∇^{d+1}) | DCD subdiferenciación (en ∇^d) |
|---|---|---|---|
| **AR con raíces reales, sin MA** (AR(1), AR(p)) | sí, sobre la raíz real positiva dominante | se AÑADE un testigo MA(1) (θ⁰ = +0,85) y el AR se reestima dentro. **θ̂ depende de ese AR**: con muchos coeficientes libres absorbe la persistencia y el testigo se va a 1 (Salamanca AR(4): LR 1,88, «d basta» con poca potencia) | se AÑADE un testigo MA(1). **Con AR libre, bajo H₀ el AR se va a 1 y reconstruye la ∇ cancelada**, porque (1 − ρB) con ρ → 1 es otra vez (1 − B): el contraste pierde potencia (BUG-0224) o falla (LR −inf, BUG-0232). No es fiable |
| **AR(2) con raíces complejas** | **no directamente** (no hay raíz real que aislar); art lo **recupera por sobreajuste**: AR(p+1) → AR(1)·AR(p) y SF sobre el AR(1) (sección 5) | se añade el testigo; el par complejo no puede imitar un (1 − B) mientras siga siendo complejo, así que el testigo lee la f=0 limpio. Salvo que la reestimación lo vuelva real (ver 5) | se añade el testigo; mismo razonamiento: un par complejo no reconstruye la ∇ salvo que degenere en dos raíces reales |
| **MA, sin AR** (MA(1), IMA) | **no aplicable**: falta el lado AR; el par se forma con el SF del modelo en d−1 | el MA(1) del modelo se SUSTITUYE por el testigo | el MA(1) del modelo ES el testigo: H₀ θ = 1 sobre él (coincide con el DCD de invertibilidad) |
| **AR(1) y MA(1)** (ARMA(1,1)) | sí | el MA(1) se sustituye por el testigo y el AR(1) se reestima dentro | el MA(1) del modelo es el testigo; si φ̂ ≈ 1, mismo riesgo que con AR libre |
| **ni AR ni MA** ((0,d,0)) | **no aplicable** | se añade el testigo: el caso validado con fue | se añade el testigo |

Notas:
- **Un ARMA(1,1) con φ̂ ≈ 1 y θ̂ < φ̂** (Salamanca: 0,943 y 0,683) es la forma en d de un
  IMA en d+1: (1 − φB)∇ ≈ ∇² cuando φ → 1. Sus SF y DCD de sobrediferenciación suelen pedir
  d+1, y llevan a estimar el IMA. El aviso de correlación por encima de 0,7 entre φ̂ y θ̂ (el
  umbral de fue) es su firma: se da siempre, pero no manda quitar nada si los t son grandes.
- La validación del DCD con fue se hizo sobre candidatos **sin AR**; con AR dentro, el
  resultado se lee con cautela, y art lo avisa.

## 5. El AR(2) con raíces complejas

φ(B) = 1 − φ₁B − φ₂B², con raíces complejas cuando φ₁² + 4φ₂ < 0. Módulo de las raíces
inversas: r = √(−φ₂); frecuencia: cos ω = φ₁ / (2r); periodo 2π/ω.

1. **El par no dice nada de d mientras ω esté lejos de 0.** Un par complejo con r → 1 es
   una raíz unitaria en la frecuencia ω, no en f = 0: un ciclo que no se amortigua. Si ω es
   una frecuencia estacional (2πk/s), es estacionalidad estocástica, y se contrasta con el
   HSM (MEG, DCD_f, Shin-Fuller dual del AR_f). Si no lo es, es un ciclo, y
   `ar_factorization` da su amortiguamiento y su periodo.
2. **Pero el lado AR de f = 0 no se pierde: art lo recupera por SOBREAJUSTE**
   (`formal_tests.shin_fuller_sobreajuste`, que `formal_tests` lanza solo). La
   reparametrización de Shin-Fuller (ec. 2.2-2.3) escribe el operador como (m − ρ)·A(m) con
   ρ real, y un par conjugado no admite esa forma (BUG-0215). La salida de la escuela es:
   - estimar un AR(p+1) en lugar del AR(p): en el AR(2) complejo, un AR(3);
   - factorizarlo como AR(1)·AR(p);
   - contrastar con SF la raíz real del AR(1);
   - y leer el **ΔAIC del sobreajuste** como segundo dato. Si no hay raíz unitaria, la raíz
     añadida es espuria y se paga como un parámetro de más (medido: +0,6 a +1,1). Si la hay,
     el AR(p+1) captura algo real y mejora (medido: −3,8 a −23,6).

   Medido en 40 réplicas por celda (n = 83), condicionado a que el AR(2) salga complejo:

   | verdad | AR(3)+SF → d+1 | DCD solo → d+1 | ΔAIC |
   |---|---|---|---|
   | estacionario, complejo | 0/37 y 0/40 | 3/37 y 3/40 | +1,10 y +0,62 |
   | I(1) × complejo | 14/16 y 32/35 | 13/16 y 33/35 | −3,79 y −23,64 |

   Tamaño 0/77 y potencia del 88-91 %: mejor que el DCD solo en falsos positivos, e igual
   de potente. **El AR(p+1) es un contraste, no un modelo: no se adopta** (su última raíz es
   espuria por construcción cuando no hay raíz unitaria).
3. **Dos opciones de estimación para el par complejo** (`confirm_and_estimate`):
   - `p` como **lista de órdenes por factor** (p.ej. `[1, 2]`): el modelo **factorizado**, una
     reparametrización exactamente identificada del mismo modelo (misma verosimilitud,
     mismos grados de libertad). Sirve para que cada factor reciba su `d ± SE` y su
     `periodo ± SE`; con `ar_seeds` se arranca desde la factorización ya estimada.
   - `ar_f_freqs=[k]`: un factor AR(2) de **frecuencia fija** 2πk/s (sólo se estima φ₂). Es
     la versión contrastable de «este factor es estacional»: anidado en el factor libre, una
     razón de verosimilitudes con 1 g.l. lo decide. Nunca se impone un operador capado o
     disperso «porque los módulos se parecen» (Villaverde, el B⁷): se estima el operador
     completo, se factoriza y se contrasta.
4. **El límite que sí importa: un ciclo largo con r → 1 es casi I(2).** Cuando ω → 0 y
   r → 1, (1 − 2r cos ω B + r² B²) → (1 − B)². Un AR(2) complejo de periodo muy largo
   (varios años en datos mensuales) y amortiguamiento cerca de 1 está imitando DOS
   diferencias:
   - sobre el nivel (d = 0), es el aspecto de una serie I(2);
   - sobre ∇ (d = 1), pediría d = 3, que no se considera: se lee como un ciclo largo (el
     ciclo inmobiliario, por ejemplo) y se dice así, con su periodo.

   El periodo a partir del cual hay que sospechar crece con n: un ciclo no se distingue de
   una deriva si la muestra no cubre al menos un par de periodos.
5. **En los DCD**, un par complejo dentro del candidato no puede reconstruir un (1 − B)
   mientras siga siendo complejo. El testigo lee la f = 0 sin la pérdida de potencia de
   BUG-0224. Pero la reestimación es libre: si en el modelo restringido (θ = 1) los
   coeficientes cruzan φ₁² + 4φ₂ = 0, el par se vuelve real y una de las raíces puede irse
   a 1. Hay que comprobar, en el restringido, si el AR sigue siendo complejo; si no lo es,
   el contraste vuelve a la fila «AR con raíces reales».
6. **En el árbol:** un modelo cuyo AR sea sólo un par complejo tiene su lado AR por
   sobreajuste (punto 2); el par queda completo: SF del AR(1) del AR(p+1) frente al DCD.

## 6. El árbol

```
¿El modelo es adecuado? (Q en s, 2s, 3s+3; JB; estacionalidad y anómalos tratados)
│
├─ NO → los contrastes son informativos. Cerrar antes el ciclo; si no se puede
│        (P02: intervenciones fuera de alcance), escribir «no terminado» y leerlos así.
│
└─ SÍ → ¿qué AR tiene? (sección 4)
    │   real positivo → SF directo · sólo complejo → SF por sobreajuste, AR(p+1) (sección 5.2)
    │   sin AR → SF no aplicable · ¿AR(2) complejo con ω → 0 y r → 1? → casi (1−B)² (5.4)
    │
    └─ ¿en qué d está?
        │
        ├─ d = 0  (sólo ratios, tasas, saldos)
        │   └─ frontera 0/1, en el MISMO modelo:
        │       ├─ con SF → par SF + DCD sobrediferenciación (testigo en ∇) → tabla de verdad
        │       └─ sin SF → sólo el DCD (un lado): θ̂ → 1 → d = 0 · genuina → estimar d = 1
        │
        ├─ d = 1
        │   ├─ HACIA ARRIBA, frontera 1/2:
        │   │   ├─ con SF → par SF + DCD sobrediferenciación (testigo en ∇²) → tabla de verdad:
        │   │   │     ρ<1 y θ→1 ............ d = 1
        │   │   │     ρ≈1 y θ<1 ............ estimar d = 2 → rama d = 2 (mirar desde abajo)
        │   │   │     ρ<1 y θ<1 ............ banda de cuasi-cancelación → ambiguo
        │   │   │     ρ≈1 y θ→1 ............ sin potencia → indeterminado, d = 1 por parsimonia
        │   │   ├─ sin SF → sólo el DCD (un lado); si dice «genuina», estimar d = 2
        │   │   └─ si el AR es largo (AR(4), AR(7)), su DCD pierde potencia: contrastar también
        │   │       con el modelo parsimonioso o con el DCD de subdiferenciación desde d = 2 (1.2)
        │   └─ HACIA ABAJO, frontera 0/1 (sólo si el dominio admite d = 0):
        │       ├─ con MA(1) → DCD subdiferenciación sobre su MA
        │       ├─ sin MA → se añade un testigo (⚠ con AR real libre no es fiable: BUG-0224)
        │       ├─ genuina → d = 1 confirmado por abajo
        │       └─ cancelada → estimar d = 0; con μ ≠ 0, d = 0 CON tendencia lineal (Chan y Wallis)
        │
        └─ d = 2
            │   no se mira hacia arriba (no hay ∇³). Sólo la frontera 1/2, y el par CRUZA
            │   dos modelos:
            ├─ lado MA: DCD subdiferenciación sobre el modelo en d = 2
            │     (con MA(1), su MA es el testigo; sin MA, se añade, con la cautela de BUG-0224)
            ├─ lado AR: SF sobre el mejor modelo en d = 1 (necesita un AR real)
            └─ tabla de verdad:
                  SF (d=1)        DCD sub (d=2)        conclusión
                  ρ<1             2.ª ∇ cancelada       d = 1
                  ρ≈1             2.ª ∇ genuina         d = 2
                  ρ<1             2.ª ∇ genuina         θ̂ a ≤ 0,10 de 1: banda → AMBIGUO
                                                         (Salamanca, Villaverde); más lejos:
                                                         manda el conjunto (Chamberí → d = 2)
                  ρ≈1             2.ª ∇ cancelada       sin potencia → indeterminado
            y comprobar 1.2: el DCD sobrediferenciación desde d = 1 contrasta lo mismo;
            si no coincide con éste, el resultado depende de la representación.
```

## 7. Cuando sale «ambiguo» o «indeterminado»

- No se fuerza: el guion dice «los datos no discriminan entre I(1) e I(2)», con los dos
  estadísticos.
- Si los dos modelos son adecuados, se pueden **adoptar los dos** (Salamanca: AR(4) en d=1,
  IMA(1) en d=2). Si sólo uno lo es, manda la diagnosis (Villaverde: d=1).
- Lo que separa los dos caminos es la **previsión a largo plazo**: con d=1 la tasa vuelve a
  su media; con d=2 sigue la última pendiente y la incertidumbre crece mucho más deprisa.
  Si hay que elegir uno, el criterio es la previsión fuera de muestra o el uso del modelo, no
  un estadístico más.

## 8. Los dos casos de la P02

| | Salamanca | Villaverde |
|---|---|---|
| Modelo en d=1 | AR(4), adecuado | AR(7), no adecuado (JB) |
| AR del modelo en d=1 | (1−0,891B)(1+0,570B)(complejo, periodo 4,0, d 0,61) | (1−0,888B)(tres complejos de periodos 7,7/3,5/2,4) |
| SF sobre el modelo en d=1 | Φ̂ = 3,59 → ρ < 1 | Φ̂ = 3,03 → ρ < 1 |
| DCD sobrediferenciación desde d=1 (testigo en ∇²) | θ̂ 0,93, LR 1,88 → se cancela (por poco; AR(4) dentro) | θ̂ 0,95, LR 2,19 → genuina |
| Modelo en d=2 | IMA(1), θ̂ 0,751, adecuado | IMA(1), θ̂ 0,906, no adecuado (Q y JB) |
| DCD subdiferenciación sobre el IMA | genuina (LR 92,9) | genuina (LR 23,9) |
| ¿Coinciden los dos DCD (1.2)? | **no**: depende de la representación (el AR(4) absorbe) | sí |
| Fila de la tabla de verdad | ρ<1 y θ<1 (con el DCD del IMA): banda | ρ<1 y θ<1: banda |
| Conclusión | ambiguo; se adoptan los dos | ambiguo; d=1 por diagnosis, AR(7) provisional |

Los factores complejos de los dos AR están lejos de ω = 0 (periodos de 2 a 8 meses) y con
amortiguamientos de 0,6 a 0,8: no imitan diferencias (5.4). La persistencia que decide d
está en la raíz real (0,89).
