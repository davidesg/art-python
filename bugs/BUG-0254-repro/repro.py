"""BUG-0254: tools/gen_tools_md.py writes each tool's description as the
interpreter gives it, and since Python 3.13 the compiler strips the common
leading whitespace of every docstring. The same source renders a different
docs/TOOLS.md on 3.12 and on 3.13+, so
tests/test_recuentos_que_no_envejecen.py::test_TOOLS_md_esta_regenerado fails
on every 3.13+ interpreter against the file generated on 3.12 (the
clean-install test of atsw 2.1.0, 2026-10-30: Debian 13, Fedora 41 and Arch,
"-     candidate seasonal AR_f factors." against "+ candidate seasonal AR_f
factors.").

The repro renders one fake tool twice: with the docstring as Python 3.12 keeps
it (indented continuation lines) and as 3.13 gives it (dedented). Expected:
the same page.

    python3 bugs/BUG-0254-repro/repro.py   # exits 1 while open
"""
import importlib.util
import inspect
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "_gen_tools_md", os.path.join(HERE, "..", "..", "tools", "gen_tools_md.py"))
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

DOC_312 = """Identify the seasonal structure.

    Returns the order and the
    candidate seasonal AR_f factors.
    """
DOC_313 = inspect.cleandoc(DOC_312) + "\n"


def page(description):
    tool = types.SimpleNamespace(name="identify", description=description,
                                 inputSchema={"properties": {}})

    async def list_tools():
        return [tool]
    sys.modules["_fake_server"] = types.SimpleNamespace(
        mcp=types.SimpleNamespace(list_tools=list_tools))
    return gen.render("_fake_server", "fake")


a, b = page(DOC_312), page(DOC_313)
diff = [(x, y) for x, y in zip(a.splitlines(), b.splitlines()) if x != y]
for x, y in diff:
    print(f"3.12: {x!r}\n3.13: {y!r}")
print("same page on both interpreters:", not diff)
sys.exit(1 if diff else 0)
