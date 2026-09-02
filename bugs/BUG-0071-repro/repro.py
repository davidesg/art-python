"""BUG-0071 — qué cantidad calculaba el alpha de test_intervention.

Repro determinista, sin datos y sin fue: pura aritmética sobre la convención
de signo del motor. Muestra que alpha = (1, -d1, -d2, ...) no reproduce ni la
ganancia nu(1) ni el numerador w(1) en ningun caso.

Sintetico, determinista, sin datos. Compara tres lecturas de la ganancia de
una FLT con la convención de fue: w(B) = w0 - w1 B - ... ; d(B) = 1 - d1 B - ...
"""
import numpy as np

def calcnu(omega, delta, K=400):
    """La recursión de calcnu()/ltf.c: nu[j] = sum d_i nu[j-i] - w[j]."""
    r, s = len(delta), len(omega) - 1
    nu = np.zeros(K + 1)
    nu[0] = omega[0]
    for k in range(1, K + 1):
        v = -omega[k] if k <= s else 0.0
        for j in range(1, r + 1):
            if k - j >= 0:
                v += delta[j - 1] * nu[k - j]
        nu[k] = v
    return nu

def gain_analitica(omega, delta):
    return (omega[0] - sum(omega[1:])) / (1.0 - sum(delta))

def gain_actual(omega, delta):
    """Lo que hace hoy interventions.py: alpha = (1, -d1, -d2, ...)."""
    k = len(omega)
    a = np.array([1.0] + [-d for d in delta[:k - 1]])
    a = np.pad(a, (0, max(0, k - len(a))))[:k]
    return float(a @ np.array(omega))

casos = [
    ("FLT s=1 r=1 decaimiento",      [0.80, -0.30], [0.50]),
    ("FLT s=1 r=1 respuesta lenta",  [1.00,  0.20], [0.80]),
    ("FLT s=2 r=1",                  [1.50, -0.40, 0.25], [0.60]),
    ("FLT s=2 r=2",                  [2.00,  0.50, -0.30], [0.40, 0.20]),
]

print(f"{'caso':<28} {'nu(1) recursión':>16} {'w(1)/d(1)':>12} {'alpha ACTUAL':>13}  ok?")
print("-" * 78)
for nombre, w, d in casos:
    nu = calcnu(w, d)
    rec = nu.sum()
    ana = gain_analitica(w, d)
    act = gain_actual(w, d)
    # el alpha actual pretende ser un contraste sobre la ganancia; compárese
    # con el NUMERADOR w(1), que es la parte lineal en omega
    num = w[0] - sum(w[1:])
    ok = "SÍ" if abs(act - num) < 1e-12 else "no"
    print(f"{nombre:<28} {rec:16.6f} {ana:12.6f} {act:13.6f}   {ok}"
          f"   [w(1)={num:+.4f}]")

print()
print("Lectura:")
print("  · 'nu(1) recursión' y 'w(1)/d(1)' coinciden siempre: la ganancia es esa.")
print("  · 'alpha ACTUAL' debería reproducir w(1) —la parte lineal en omega—")
print("    y sólo lo hace cuando todas las delta valen 1, que es el caso")
print("    INADMISIBLE (d(1)=0, ganancia infinita).")
