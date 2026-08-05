"""Register the suite's three MCP assistants in one command.

WHY THIS EXISTS, AND WHAT IT IS NOT. In MCP a server cannot install or register
other servers: the client starts the processes, and only the client's own
configuration decides which. So there is no "umbrella MCP" in the literal sense,
and this is not one — it is a setup command that writes the three entries for
you, so the user runs one thing instead of three.

WHY NOT ONE MERGED SERVER. It is technically possible to mount all three into a
single server, and it would be worse. An MCP client already shows every
connected server at once, so routing is not a missing capability; what merging
would actually merge is the three INSTRUCTION blocks, and those contradict each
other on purpose. `art` and `sima` open with "guided or autonomous?", `mtram`
opens with "which series is the output?". More to the point, the three make
different claims about the world — `mtram` declares and TESTS exogeneity, `sima`
assumes everything is endogenous — and an assistant that would discuss both in
the same breath is one that has blurred the distinction the suite exists to
keep. Three servers, one ladder, and each one knows when to hand over.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

# name -> (console script, what it is for)
SERVERS = {
    "art":   ("art-mcp", "one series: ARIMA + interventions (engine: fue)"),
    "mtram": ("mtram",   "transfer functions and networks, a DAG (engine: drtran)"),
    "sima":  ("sima",    "simultaneous VARMA (engine: drvarma)"),
}


def _installed(exe: str) -> bool:
    return shutil.which(exe) is not None


def _registered() -> set[str]:
    """Names already known to the Claude CLI (empty if it cannot be asked)."""
    try:
        p = subprocess.run(["claude", "mcp", "list"], capture_output=True,
                           text=True, timeout=60)
    except Exception:                                      # noqa: BLE001
        return set()
    if p.returncode != 0:
        return set()
    out = set()
    for line in p.stdout.splitlines():
        if ":" in line:
            out.add(line.split(":", 1)[0].strip())
    return out


def _config_json() -> str:
    """The equivalent config, for clients that are not Claude Code."""
    return json.dumps(
        {"mcpServers": {n: {"command": exe, "args": []}
                        for n, (exe, _) in SERVERS.items()
                        if _installed(exe)}},
        indent=2)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="atsw-mcp",
        description="Register art, mtram and sima with Claude Code in one step.",
        epilog="Not an MCP server itself: MCP has no mechanism for one server to "
               "register another. This writes the three entries for you.")
    ap.add_argument("--scope", default="user", choices=["user", "project", "local"],
                    help="Claude Code scope for the registration (default: user)")
    ap.add_argument("--print-config", action="store_true",
                    help="print the equivalent mcpServers JSON and exit, for "
                         "clients other than Claude Code")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the commands without running them")
    a = ap.parse_args(argv)

    if a.print_config:
        print(_config_json())
        return 0

    missing = [n for n, (exe, _) in SERVERS.items() if not _installed(exe)]
    if missing:
        print("These assistants are not installed: %s\n"
              "  pip install atsw            (the whole suite)\n"
              "  pip install 'drtran[mcp]'   (mtram alone)\n"
              "  pip install 'drvarma[mcp]'  (sima alone)"
              % ", ".join(missing), file=sys.stderr)

    if not a.dry_run and shutil.which("claude") is None:
        print("The `claude` CLI is not on PATH, so nothing was registered.\n"
              "Use --print-config and paste the result into your client's "
              "configuration.", file=sys.stderr)
        return 1

    already = set() if a.dry_run else _registered()

    # `sima` was called `multiart` until the suite settled its names. A client
    # that still has the old entry keeps talking to whatever `multiart` resolves
    # to, which after an upgrade is nothing at all — and a dead server reads as
    # "the assistant is not there" rather than "the name changed".
    if "multiart" in already:
        print("NOTE: `multiart` is still registered. That was sima's old name.\n"
              "      Remove it once sima answers:  claude mcp remove multiart",
              file=sys.stderr)
    done, skipped = [], []
    for name, (exe, what) in SERVERS.items():
        if not _installed(exe):
            continue
        if name in already:
            skipped.append(name)
            continue
        cmd = ["claude", "mcp", "add", "--scope", a.scope, name, "--", exe]
        if a.dry_run:
            print(" ".join(cmd))
            continue
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if p.returncode == 0:
            done.append(name)
        else:
            print("could not register %s: %s"
                  % (name, (p.stderr or p.stdout).strip()[:200]), file=sys.stderr)

    if a.dry_run:
        return 0

    for name in done:
        print("registered %-6s — %s" % (name, SERVERS[name][1]))
    for name in skipped:
        print("already there: %s" % name)
    if done or skipped:
        print("\nRestart Claude Code so it picks them up. The ladder:\n"
              "  art    build each series on its own, it writes a .pre\n"
              "  mtram  how X moves Y: transfer functions and networks\n"
              "  sima   everything moves everything: simultaneous VARMA\n"
              "mtram starts from art's .pre files, and hands over to sima when the\n"
              "network it proposes contains a cycle — that is a test, not a taste.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
