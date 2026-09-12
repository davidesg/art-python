---
id: BUG-0182
title: art ofrecía la RAMPA como una forma más — en autónomo el LLM la usó para zanjar el orden de integración, y fijó para siempre la inflación de largo plazo con una banda que no recoge esa incertidumbre
status: fixed
severity: high
component: interventions
found_in: 0.2.1
fixed_in: 0.2.1
reported: 2026-09-12
reporter: David — run 6 de IPC_ES, autónomo sin enunciado
tags:
  - intervenciones
  - rampa
  - prevision
  - autonomo
references:
  - BUG-0161
  - BUG-0180
  - BUG-0181
---

## Summary

En el run 6 —el primer autónomo con el carril arreglado, y un buen recorrido—
el LLM cerró el análisis con una **rampa en el nivel en 07/2008** (ω = −0,2043,
EE 0,048) sobre ln IPC con d=1. La razón era buena y el método no.

art se la ofreció como una forma cualquiera. El protocolo no mencionaba la
rampa **ni una vez**; `suggest_intervention_form` la listaba a la par que las
otras —*«pulse, step, ramp»*— y al añadirla sólo avisó de sobreparametrización.
Nada sobre lo que le hace a la previsión.

## Qué es una rampa en el nivel

Un escalón pasado por un integrador: `R_t = S_t/(1−B)`. Es el límite δ=1 de la
forma racional ω/(1−δB): ganancia ω(1)/δ(1) **infinita**, efecto sobre el nivel
sin cota. Es una **tendencia determinista a partir de la fecha**. Escrita como
forma racional con δ=1, el chequeo de admisibilidad de BUG-0161 la rechazaría;
como primitiva `ramp`, lo esquivaba.

Con d=1 equivale a un escalón en la tasa de crecimiento. Sobre un índice de
precios: **fijar para siempre un cambio en la inflación tendencial.**

## Lo que hizo en el run 6

Medido sobre el `.out` de m06 y contrastado con los datos (μ se lee entre 2
porque el modelo lleva `(1+B²)∇`, de ganancia 2 en la frecuencia cero):

    inflación media antes de 07/2008    3,39 %/año   (datos: 3,58 %)
    la rampa                           −2,45 %/año   para siempre
    después                             0,94 %/año   (datos: 1,00 %)

Y en la función de previsión:

    pendiente a largo plazo      sin rampa 1,82 %/año · con rampa 0,94 %/año
    nivel de precios a 10 años   −8,8 % frente al modelo sin rampa
    ancho de banda a 10 años     la alternativa d=2 (θ=0,968) daría 3,1× más

**La banda no recoge ninguna incertidumbre sobre la inflación tendencial**: la
rampa es determinista y entra como conocida.

## Por qué la razón era buena y el método no

El DCD de sobrediferenciación daba θ̂=0,968, LR=5,0 —apuntando a d+1, una raíz
unitaria en la inflación— y Shin-Fuller decía que d bastaba: la banda de
cuasi-cancelación. La media de la inflación sí cambia en 2008. Preguntarse si es
una raíz unitaria o una ruptura en la media es la pregunta de Perron (1989), un
orden más arriba.

El método falla en tres cosas:
- **La fecha se eligió con los datos** (perfil de ℓ, máximo en 07/2008) y luego
  se leyó el DCD con los críticos habituales. Con ruptura endógena no valen
  (Zivot-Andrews). Que θ̂ pase a 1,000 con LR=0 tras meter la ruptura en la
  mejor fecha no confirma nada: es lo que produce esa construcción.
- **Se decidió el orden de integración con una intervención.** En la escuela,
  d frente a d+1 se decide en el nodo d, no añadiendo términos deterministas
  hasta que el contraste esté de acuerdo.
- **En este dominio es una afirmación estructural** —el régimen de inflación
  posterior a 2008 es permanente y conocido— que un modelo univariante no puede
  sostener. La muestra extendida (2021–23) la desmiente.

El LLM descartó la alternativa estocástica escribiendo *«equivalente en
previsión según el instrumento»*. No lo es: coinciden a 12 meses (1,18×) y se
separan en el largo plazo, que es justo donde la rampa manda.

## Impact

El carril autónomo entregaba un modelo final con la inflación de largo plazo
fijada y la banda estrecha, y no lo decía. *Publica un número incorrecto y
calla.* Entra, a petición del analista: la rampa es un instrumento de usuario
avanzado, sólo del carril guiado y con aviso.

## Fix

**Una sola puerta.** La única forma de AÑADIR una rampa es
`suggest_intervention_form(form="ramp")` —`guided_intervention` le delega; la
escalera de Ockham y `decide_form` sólo devuelven escalón o impulso—. El cerrojo
va ahí:

- `modo: _Modo` en `suggest_intervention_form` y `guided_intervention`, que lo
  reenvía. En **autónomo**, `form="ramp"` se rechaza antes de escribir nada,
  explicando por qué y qué hacer: volver al nodo d y contrastar la alternativa
  estocástica, o acotar la ventana muestral.
- En **guiado** se admite, y la salida trae `aviso_rampa(model)` **con las cifras
  estimadas**: ω por periodo, anualizado, «desde esa fecha y PARA SIEMPRE»; que
  la banda no recoge esa incertidumbre; y el reparo de Zivot-Andrews si la fecha
  salió de los datos.
- El mismo aviso sale en `confirm_and_estimate` y `estimate_and_diagnose` cuando
  el modelo **ya trae** una rampa —encadenada por `.pre` o escrita a mano—:
  entra por otra puerta pero fija la previsión igual.
- Protocolo: «NO USES RAMPAS» en el carril autónomo, y un párrafo «RAMPA —
  INSTRUMENTO DE USUARIO AVANZADO» en la etapa de intervenciones del guiado.

## Validation

`tests/test_bugs_0182_0183_rampa_y_objetivo.py`, sobre una serie sintética con
la inflación media que cae a mitad de muestra:

- autónomo: rechazada en `suggest_intervention_form` y en `guided_intervention`,
  y **sin escribir** el `.inp`;
- guiado: admitida y avisada, y la cifra del aviso **es la ω del `.pre`**, no
  prosa genérica;
- un modelo sin rampa no avisa; uno que la trae avisa al reestimarlo;
- ninguna regla automática elige una rampa;
- el carril viaja como enum; el protocolo lo dice en los dos carriles.
