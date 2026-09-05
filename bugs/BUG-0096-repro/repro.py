"""BUG-0096 — el vecino sub-umbral no decía nada, ni siquiera con ARMA.

`check_intervention_fit` calcula `z_antes` y `z_despues` y sólo los usaba si
cruzaban el umbral de anómalo. Un vecino por debajo no se reportaba, y ahí es
donde cae la cola del suceso.

LO QUE SE ADOPTÓ, Y LO QUE NO
─────────────────────────────
El reporte pedía marcar la banda [umbral_activo, umbral_vecino) = [1.0, 2.0)
como «cola activa», que `funciona` dejara de ser limpio, y que entrara en
`describe_escalera` **como razón para subir de peldaño**. Decisión del analista,
2026-09-05, y este repro comprueba la decisión y no la petición:

  ▸ La regla de Treadway **se queda en 2σ**, con ARMA y sin él. `funciona` y
    `vecino_anomalo` NO cambian.
  ▸ Sólo una NOTA, y **sólo si el modelo lleva ARMA** — que es donde el residuo
    crudo del vecino deja de ser el contraste exacto y pierde potencia (47%
    frente al 77.5% del LR; BUG-0089).
  ▸ **No entra en `razones_para_subir`.** Eso convertiría en evidencia algo que
    bajo la nula pasa el 13% de las veces, y la sobre-intervención es el modo de
    fallo que no se detiene solo.
  ▸ La banda empieza en **1.5, no en 1.0**. El número lo decide la nula:

        |z| > 1.0  →  p = 0.317   uno de cada 3     ← eso es ruido
        |z| > 1.5  →  p = 0.134   uno de cada 7.5
        |z| > 2.0  →  p = 0.046   uno de cada 22    ← la regla

    Consecuencia asumida: el caso que motivó el reporte —SERV_UEM 11/2015, con
    el vecino a **−1.40σ**— queda POR DEBAJO de la banda y no produce nota. Es
    decisión, no descuido: a 1.40 la nula da uno de cada seis.
"""
import sys

sys.path.insert(0, "src")

FALLOS = []
from art.interventions import InterventionFitCheck
from art.policy import THRESHOLDS

LO = THRESHOLDS["intervention_cola_activa"]
HI = THRESHOLDS["intervention_vecino"]


def chk(z_despues, con_arma):
    return InterventionFitCheck(
        itv_index=0, itv_type="step", at_0based=243, fechas=[243],
        z_en_fechas=[0.0], z_antes=0.19, z_despues=z_despues,
        umbral_vecino=HI, umbral_absorcion=1.5, con_arma=con_arma,
        umbral_cola=LO)


print(f"== Umbrales: nota desde {LO}σ, regla de Treadway en {HI}σ")

print("\n== A. La nota sale donde toca — y sólo con ARMA")
CASOS = [(-1.60, True, "después"), (-1.60, False, None), (-0.80, True, None),
         (-2.40, True, None)]
for z, arma, esperado in CASOS:
    c = chk(z, arma)
    ok = c.cola_activa == esperado
    print(f"  z={z:+.2f} arma={arma!s:5}  cola_activa={c.cola_activa!r:10} "
          f"(esperado {esperado!r})  {'OK' if ok else 'FALLA'}")
    if not ok:
        FALLOS.append(f"cola_activa mal en z={z} arma={arma}")

print("\n== B. La REGLA no cambia: 2σ, con ARMA y sin él")
for z, arma in ((-1.60, True), (-1.60, False), (-1.90, True)):
    c = chk(z, arma)
    if not c.funciona or c.vecino_anomalo is not None:
        print(f"  FALLA: z={z:+.2f} arma={arma} alteró el veredicto")
        FALLOS.append("la nota cambió el veredicto")
    else:
        print(f"  z={z:+.2f} arma={arma!s:5}  funciona=True  vecino_anomalo=None  OK")
c = chk(-2.40, True)
print(f"  z=-2.40 arma=True   funciona={c.funciona}  "
      f"vecino_anomalo={c.vecino_anomalo!r}  ← la regla SÍ dispara")
if c.funciona or c.vecino_anomalo is None:
    FALLOS.append("la regla de 2σ dejó de disparar")

print("\n== C. El caso del reporte queda fuera, por decisión")
c = chk(-1.40, True)
print(f"  SERV_UEM 11/2015, z=-1.40 con ARMA → cola_activa={c.cola_activa!r}")
if c.cola_activa is not None:
    print("  FALLA: la banda no empieza en 1.5 como se decidió")
    FALLOS.append("la banda no arranca donde se decidió")

print("\n== D. La nota NO es una razón para subir de peldaño")
import inspect
from art import escalera
src = inspect.getsource(escalera)
i = src.find("cola_activa")
bloque = src[max(0, i - 900):i + 900] if i > 0 else ""
if "razones.append" in bloque:
    print("  FALLA: la cola activa alimenta `razones_para_subir`")
    FALLOS.append("la nota entró en las razones")
else:
    print("  la escalera la publica como nota, no como razón: OK")

print("\n== E. Y el texto dice cuán probable es que sea ruido")
t = chk(-1.60, True).summary()
if "%" in t and "nula" in t and "nota" in t.lower():
    print("  el aviso trae la probabilidad bajo la nula: OK")
else:
    print("  FALLA: el aviso no dice cuán probable es")
    FALLOS.append("el aviso no cuantifica")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA:", ", ".join(FALLOS))
    sys.exit(1)
print("OK: nota con ARMA desde 1.5σ; la regla de Treadway sigue en 2σ.")
