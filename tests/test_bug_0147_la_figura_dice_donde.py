"""BUG-0147 — tools that composed their envelope by hand wrote the figure and
did not say where. `_cita_figuras` cites each figure's path in the envelope's
text, before the guided lane's end-of-turn marker (BUG-0094), once per figure;
an envelope with no text gets one. The six tools of the report return through
it; tests/test_frontera_mcp.py checks it across the MCP boundary."""
import base64
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mcp.types import ImageContent, TextContent  # noqa: E402

from art import mcp_server as M  # noqa: E402


def _png(seed):
    fig, ax = plt.subplots(figsize=(1, 1))
    ax.plot([0, seed])
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def test_the_path_goes_before_the_end_of_turn_marker():
    b = _png(1)
    txt = "evidencia\n\n" + M.FIN_DE_TURNO_GUIADO
    out = M._cita_figuras([TextContent(type="text", text=txt), M._imagen(b, "t")])
    t = out[0].text
    ruta = M._FIGURAS[M._huella_figura(b)]
    assert ruta in t and t.rstrip().endswith(M.FIN_DE_TURNO_GUIADO.strip())
    assert t.count(ruta) == 1
    assert isinstance(out[1], ImageContent)


def test_an_envelope_with_only_an_image_gets_its_path():
    b = _png(2)
    out = M._cita_figuras([M._imagen(b, "model_histogram")])
    assert isinstance(out[0], TextContent) and M._FIGURAS[M._huella_figura(b)] in out[0].text


def test_the_six_tools_return_through_it():
    import inspect
    for tool in ("preliminary_outlier_scan", "residual_outlier_scan", "model_histogram",
                 "record_version", "overparameterization_analysis", "compare_versions"):
        body = inspect.getsource(getattr(getattr(M, tool), "fn", getattr(M, tool)))
        assert "_cita_figuras(" in body, tool
