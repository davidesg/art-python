#!/usr/bin/env python3
"""BUG-0052 — la lista era un INCREMENTO y la llamada sugerida SUSTITUYE.

`guided_identification(pre_path=...)` identifica sobre los RESIDUOS del `.pre`,
que ya tienen su ARMA quitado: lo que la lista sugiere es lo que FALTA por
modelar. Pero la llamada que imprimía usa `base_pre_path`, cuya semántica es
heredar armónicos, intervenciones y media y **SUSTITUIR** el ARMA por el (p,q)
que se le pase.

Tomada al pie de la letra, la sugerencia reestimaba el MISMO modelo. Sobre
`PGAS_m03`, que ya lleva MA(1) y cuyos residuos piden q=1, la herramienta
imprimía `q=1`: eso no da un MA(2), da otra vez el MA(1). El orden correcto
--MA(2), que resulta ser el modelo final de la serie-- habia que deducirlo a
mano.

Uso:  python repro.py
"""
import sys, os, warnings, re
warnings.filterwarnings("ignore")

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run2/PGAS/"


def main():
    pre = R + "PGAS_m03.pre"
    if not os.path.exists(pre):
        print("datos de la replica no disponibles"); return 0

    from art.mcp_server import guided_identification, _load_fitted
    _, m = _load_fitted(pre)
    q_base = len(m.ma[0]) if m.ma else 0
    p_base = len(m.ar[0]) if m.ar else 0
    print(f"base `{os.path.basename(pre)}`:  p={p_base}, q={q_base}")

    f = getattr(guided_identification, "fn", guided_identification)
    out = f(pre, lam=0.0, d=1, D=0, pre_path=pre)
    txt = out[0].text if isinstance(out, list) else str(out)

    m_sug = re.search(r"\(Sugerencia: p=(\d+), q=(\d+)", txt)
    p_sug, q_sug = (int(m_sug.group(1)), int(m_sug.group(2))) if m_sug else (None, None)
    print(f"orden sugerido para pasar a confirm_and_estimate:  p={p_sug}, q={q_sug}")

    avisa = "INCREMENTO" in txt
    print(f"¿avisa de que la lista es un incremento?  {'si' if avisa else 'NO'}")

    # El fallo: sugerir el MISMO orden que ya tiene la base.
    reproduce_la_base = (p_sug, q_sug) == (p_base, q_base)
    print("\n" + ("BUG PRESENTE: la sugerencia reestima el modelo de partida"
                  if reproduce_la_base or not avisa else
                  f"ARREGLADO: sugiere el TOTAL (q={q_sug} = {q_base} de la base "
                  f"+ 1 del incremento) y lo explica"))
    return 1 if (reproduce_la_base or not avisa) else 0


if __name__ == "__main__":
    sys.exit(main())
