/* Arnés de referencia para el puerto de LTF a Python.
 *
 * El bloque numérico está COPIADO VERBATIM de
 * /home/david/Dropbox/SRC/LTF/LTF-1.0.2/ltf.c (generate_plots, pasos 1-4),
 * quitando sólo el trazado por gnuplot. Copiado y no reescrito a propósito:
 * si el puerto de Python diverge, la divergencia es del puerto y no de una
 * re-derivación mía de lo que el C "quería decir".
 *
 * Uso:  ./harness <s> <b> <r> <K> <d> <w0 w1 ... ws> <d1 ... dr>
 * Sale: una línea "k nu_k srf_k" por retardo, con %.17g.
 */
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc < 6) { fprintf(stderr, "faltan argumentos\n"); return 2; }
    int s = atoi(argv[1]), b = atoi(argv[2]), r = atoi(argv[3]);
    int K = atoi(argv[4]), d = atoi(argv[5]);
    if (argc != 6 + (s + 1) + r) { fprintf(stderr, "nº de coeficientes\n"); return 2; }

    double *omega = calloc(s + 1, sizeof(double));
    double *delta = r ? calloc(r, sizeof(double)) : NULL;
    for (int i = 0; i <= s; i++) omega[i] = atof(argv[6 + i]);
    for (int i = 0; i <  r; i++) delta[i] = atof(argv[6 + s + 1 + i]);

    if (K <= s || d < 0 || d > 1 || !omega || (r > 0 && !delta)) {
        fprintf(stderr, "Parámetros inválidos en generate_plots()\n"); return 2;
    }

    /* ── verbatim de ltf.c ─────────────────────────────────────────────── */
    const int array_size = K + r + 1;
    double *nu = calloc(array_size, sizeof(double));
    double *srf = calloc(array_size, sizeof(double));

    // 1. Cálculo de coeficientes nu
    nu[r] = omega[0];
    for(int j = 1; j <= r; j++) {
        nu[r] += delta[j-1] * nu[r - j];
    }

    for(int k = 1; k <= s; k++) {
        nu[r + k] = -omega[k];
        for(int j = 1; j <= r; j++) {
            const int idx = r + k - j;
            if(idx >= 0) {
                nu[r + k] += delta[j-1] * nu[idx];
            }
        }
    }

    for(int k = s + 1; k <= K; k++) {
        for(int j = 1; j <= r; j++) {
            const int idx = r + k - j;
            if(idx >= 0) {
                nu[r + k] += delta[j-1] * nu[idx];
            }
        }
    }

    // 2. Aplicar dead time
    if(b > 0) {
        for(int k = K; k >= b; k--) {
            nu[r + k] = nu[r + (k - b)];
        }
        for(int k = 0; k < b; k++) {
            nu[r + k] = 0.0;
        }
    }

    // 3. Calcular SRF
    srf[r] = nu[r];
    for(int k = 1; k <= K; k++) {
        srf[r + k] = srf[r + k - 1] + nu[r + k];
    }

    // 4. Aplicar diferencias
    double *irf_data = nu + r;
    double *srf_data = srf + r;

    if(d == 1) {
        for(int k = K; k >= 1; k--) {
            irf_data[k] -= irf_data[k - 1];
            srf_data[k] -= srf_data[k - 1];
        }
    }
    /* ── fin del verbatim ──────────────────────────────────────────────── */

    for (int k = 0; k <= K; k++)
        printf("%d %.17g %.17g\n", k, irf_data[k], srf_data[k]);

    free(nu); free(srf); free(omega); free(delta);
    return 0;
}
