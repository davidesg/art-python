"""
art-bug — command-line front end for the in-repo bug tracker (art.bugs).

    art-bug [--dir D] list [--status S] [--component C]   list reports
    art-bug show BUG-NNNN                        print a report
    art-bug new "title" --component pipeline     create a new report
    art-bug index                               regenerate bugs/README.md
    art-bug check                               validate all reports (CI-friendly)

`--dir` apunta el registro a OTRO repositorio. La biblioteca (`art.bugs`) ya
aceptaba `bugs_dir` en todas sus funciones; lo que faltaba era la puerta, y sin
ella los demás programas de la escalera —`pyfug`, `drvec`, `drtran`,
`drvarma`— no podían usar este registro sin copiarlo. Copiarlo habría sido la
enfermedad de siempre: la misma capacidad en N sitios.

Sin `--dir` se localiza subiendo desde el directorio actual, y si ahí no hay
nada se cae a la ubicación del paquete — que es cómodo dentro de `art` y un
cepo fuera: `art-bug index` desde un repo sin `bugs/` escribiría el índice de
`art`.
"""

from __future__ import annotations

import argparse
import sys

from . import bugs as _bugs


def _cmd_list(args):
    items = _bugs.list_bugs(bugs_dir=args.dir, status=args.status,
                            component=args.component)
    if not items:
        print("no bug reports found.")
        return 0
    for b in items:
        flag = " " if b.status != "open" else "*"
        print(f"{flag}{b.id}  [{b.status:11s}] {b.severity:8s} "
              f"{b.component:12s} {b.title}")
    n_open = sum(1 for b in items if b.is_open)
    print(f"\n{len(items)} report(s), {n_open} open.")
    return 0


def _cmd_show(args):
    for b in _bugs.list_bugs(bugs_dir=args.dir):
        if b.id == args.id:
            print(_bugs.render_frontmatter(b))
            print()
            print(b.body)
            return 0
    print(f"art-bug: no report with id {args.id}", file=sys.stderr)
    return 1


def _cmd_new(args):
    path = _bugs.new_bug(
        args.title, component=args.component, severity=args.severity,
        found_in=args.found_in, reporter=args.reporter,
        tags=args.tag or [], bugs_dir=args.dir)
    print(f"created {path}")
    print("edit it, then run 'art-bug index' to refresh bugs/README.md")
    return 0


def _cmd_index(args):
    path = _bugs.write_index(args.dir)
    print(f"wrote {path}")
    return 0


def _cmd_check(args):
    report = _bugs.validate_all(args.dir)
    if not report:
        n = len(_bugs.list_bugs(bugs_dir=args.dir))
        print(f"OK — {n} report(s), all valid.")
        return 0
    print("INVALID bug reports:", file=sys.stderr)
    for who, errs in report.items():
        for e in errs:
            print(f"  {who}: {e}", file=sys.stderr)
    return 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="art-bug",
                                description="ART in-repo bug tracker")
    p.add_argument("--dir", metavar="BUGS_DIR", default=None,
                   help="directorio bugs/ sobre el que operar; por omisión se "
                        "localiza subiendo desde el directorio actual. Sirve "
                        "para llevar este registro a otro repositorio de la "
                        "escalera (pyfug, drvec, drtran, drvarma).")
    sub = p.add_subparsers(dest="cmd")

    pl = sub.add_parser("list", help="list bug reports")
    pl.add_argument("--status", choices=_bugs.STATUSES)
    pl.add_argument("--component")
    pl.set_defaults(func=_cmd_list)

    ps = sub.add_parser("show", help="print a report")
    ps.add_argument("id")
    ps.set_defaults(func=_cmd_show)

    pn = sub.add_parser("new", help="create a new report")
    pn.add_argument("title")
    pn.add_argument("--component", required=True)
    pn.add_argument("--severity", choices=_bugs.SEVERITIES, default="medium")
    pn.add_argument("--found-in", dest="found_in", default="")
    pn.add_argument("--reporter", default="")
    pn.add_argument("--tag", action="append")
    pn.set_defaults(func=_cmd_new)

    pi = sub.add_parser("index", help="regenerate bugs/README.md")
    pi.set_defaults(func=_cmd_index)

    pc = sub.add_parser("check", help="validate all reports")
    pc.set_defaults(func=_cmd_check)

    args = p.parse_args(argv)
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
