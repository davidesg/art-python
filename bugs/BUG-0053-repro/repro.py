#!/usr/bin/env python3
"""BUG-0053 — `meg_reformulate` escribia un modelo que el guion nunca veia.

Todas las herramientas que producen un modelo aceptan `guion_path`,
`guion_name`, `guion_decision` y `guion_rationale` y registran una version.
`meg_reformulate` no los tenia. Escribia el `.inp`/`.pre`/`.out` a disco y el
guion no se enteraba.

Consecuencia sobre el linaje, que es lo grave: el modelo reformulado quedaba
huerfano, y el modelo que se encadenara ENCIMA se registraba como descendiente
del modelo ANTERIOR a la reformulacion. La cadena real m03 -> m06 -> m07 salia
del mapa como m03 -> m07, y la rama que el ejercicio del MEG existe para
documentar era justo la que no se podia enseñar.

Uso:  python repro.py
"""
import sys, os, json, shutil, tempfile, warnings, inspect
warnings.filterwarnings("ignore")

R = "/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/run2/RATIO/"


def main():
    from art.mcp_server import meg_reformulate, _record_to_guion, _load_fitted
    f = getattr(meg_reformulate, "fn", meg_reformulate)

    print("1) ¿Acepta los parametros del guion?")
    pars = list(inspect.signature(f).parameters)
    faltan = [x for x in ("guion_path", "guion_name", "guion_decision",
                          "guion_rationale") if x not in pars]
    print(f"   faltan: {faltan or 'ninguno'}")

    if not os.path.exists(R + "RATIO_m03.pre"):
        print("\ndatos de la replica no disponibles")
        return 1 if faltan else 0

    print("\n2) ¿Se recompone el linaje?")
    tmp = tempfile.mkdtemp(prefix="bug0053_")
    g = os.path.join(tmp, "g.json")
    base = os.path.join(tmp, "RATIO_m03.pre")
    shutil.copy(R + "RATIO_m03.pre", base)

    _, mb = _load_fitted(base)
    _record_to_guion(mb, base, 0.0, g, name="m03", decision="baseline B1")

    kw = {} if faltan else dict(guion_path=g, guion_name="m06_MEG_f1")
    f(base, freq=1, output_path=os.path.join(tmp, "MEG.inp"),
      base_pre_path=base, **kw)

    d = json.load(open(g))
    for e in d["entries"]:
        print(f"   v{e['version']}  {e['name']:12s} parent={e.get('parent')}"
              f"  ifadf={e['spec'].get('ifadf')}")
    huerfano = len(d["entries"]) < 2
    if huerfano:
        print("   ← la reformulacion NO aparece: modelo en disco, invisible en el mapa")

    roto = bool(faltan) or huerfano
    print("\n" + ("BUG PRESENTE" if roto else
                  "ARREGLADO: la reformulacion es una version mas, colgada de su padre"))
    return 1 if roto else 0


if __name__ == "__main__":
    sys.exit(main())
