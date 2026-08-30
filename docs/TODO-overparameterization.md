# TODO — la sobreparametrización como paso previo a declarar un modelo final

**Estado:** abierto · **Abierto el** 2026-08-29 · **Origen:** réplica del TFM de
Bolivia, RATIO del RUN 2 en el carril DeepSeek

---

## El hecho que lo motiva

`overparameterization_analysis` existe, funciona, y **nadie la llama**. En las
tres series del RUN 2, ninguno de los dos carriles la invocó una sola vez: 138
llamadas al servidor entre los dos, y cero a esta herramienta.

El modelo final de RATIO del carril DS es un `ARMA(4,2)` con 11 parámetros. Su
propio `.out`, el de la estimación real, ya lo decía:

```
Correlations greater than or equal to 0.7 in absolute value:

corr[ 8][ 6] =  0.93     AR(3) — AR(1)
corr[ 9][ 7] =  0.98     AR(4) — AR(2)
corr[11][ 1] =  0.80     MA(2) — cos(k=1)
```

Y el patrón dice qué está pasando: las correlaciones altas son entre retardos de
la **misma paridad** —1 con 3, 2 con 4—, que es la firma de un AR(4) regular
imitando una estructura **estacional de periodo 4**. El carril rival la escribe
como un `AR(1)₄`: un parámetro en lugar de cuatro. Once parámetros haciendo el
trabajo de seis, a cambio de 7,26 de AIC y 19,35 de BIC.

El aviso estaba impreso, en su fichero, y pasó de largo. Un modelo se declaró
final sin que nadie mirara sus correlaciones.

## Lo que hay que hacer, y con qué cautela

**Mirar la sobreparametrización antes de declarar un modelo definitivo.** Es una
herramienta de DIAGNOSIS y se puede correr en cada diagnosis; al final del
proceso es casi obligatoria.

**Pero no como criterio binario, y esto es lo importante.** Un modelo adecuado
puede tener correlaciones altas entre parámetros sin estar sobreparametrizado.
El caso de manual: **un ARMA(2,1) con raíces imaginarias casi siempre las
tiene**, y no sobra nada — la correlación es una propiedad de la
parametrización, no un defecto del modelo. Convertir `|r| > 0.7` en una regla de
rechazo produciría el error opuesto al que se quiere evitar.

La correlación alta es una **pregunta**, no un veredicto: *¿hay dos parámetros
haciendo el mismo trabajo?* La respuesta pide mirar la estructura. En el RATIO
de DS la responde el patrón de paridad —los retardos correlados son los que un
operador estacional de periodo 4 explicaría solo—, y ahí sí sobra. En un
ARMA(2,1) de raíces complejas la respuesta es que no.

## Por dónde puede ir

Sin decidir todavía, y en orden de menos a más intrusivo:

1. **Que la diagnosis la incluya** cuando el modelo pase de un número modesto de
   parámetros, con el resultado como NOTA, nunca como bloqueo de adecuación.
2. **Que el nodo de cierre la exija**: declarar un modelo final sin haberla
   mirado debería ser algo que la herramienta señale, del mismo modo que ya
   señala leer un contraste formal sobre una diagnosis sucia.
3. **Que el diagnóstico interprete el PATRÓN, no sólo el umbral.** Correlaciones
   altas entre retardos de la misma paridad, o separados por el periodo
   estacional, sugieren un operador estacional mal colocado; entre parámetros de
   un mismo factor ARMA de raíces complejas, no sugieren nada. Distinguir los dos
   casos es lo que convierte el aviso en información.

El texto que acompañe al aviso tiene que llevar la cautela **dentro**: hoy dice
«Sobreparametrización probable → reducir modelo», que es demasiado afirmativo
para lo que el estadístico sostiene.

## Lo que este TODO NO propone

Ningún umbral automático de rechazo, y ninguna poda automática. La decisión sigue
siendo del analista; lo que falta es que llegue a su mesa.
