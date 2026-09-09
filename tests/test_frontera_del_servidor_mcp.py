"""Los defectos que sólo existen CRUZANDO el servidor MCP.

BUG-0111 · 0112 · 0113 · 0114, todos de la sesión del 8 de septiembre en
Windows, y todos encontrados **usando** la herramienta, no probándola.

    defecto            por llamada directa    por servidor MCP
    0111 visor         sin efecto visible     diálogo modal por figura
    0112 `p`           funciona (int)         TypeError, o modelo equivocado
    0113 ruta          invisible (hay ventana) sin figura y sin ruta
    0114 `git`         3 s                    CUELGUE INFINITO

Casi todas las pruebas de este repositorio desenvuelven el `@mcp.tool()` y
llaman a la función. **Hay una clase entera de defectos que vive justo en la
frontera que ese estilo no cruza**, y ninguno de los cuatro lo habría
encontrado la suite. Esto empieza a cubrirla.
"""
import asyncio
import os
import subprocess
import sys
import tempfile
import textwrap
import time

import pytest

os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv


# ══════ BUG-0112 — el esquema que el servidor PUBLICA ══════

@pytest.fixture(scope="module")
def esquemas():
    """Lo que ve un cliente MCP, no lo que dice la firma de Python."""
    return {t.name: t.inputSchema for t in asyncio.run(srv.mcp.list_tools())}


def test_ningun_parametro_se_publica_como_string_por_no_estar_anotado(esquemas):
    """LA PRUEBA QUE CIERRA LA CLASE.

    `p` estaba sin anotar —porque admite un entero o una lista, y no hay
    anotación obvia para las dos— y FastMCP, sin anotación, publica
    `"type": "string"`. Un cliente conforme mandaba entonces una cadena.

    Lo que se comprueba no es `p`: es que **ningún** parámetro cuyo valor por
    defecto sea numérico o booleano se publique como cadena. Un parámetro que se
    olvide de anotar mañana vuelve a caer aquí."""
    import inspect
    malos = []
    for nombre, esquema in esquemas.items():
        fn = getattr(srv, nombre, None)
        fn = getattr(fn, "fn", fn)
        if fn is None or not callable(fn):
            continue
        try:
            firma = inspect.signature(fn)
        except (TypeError, ValueError):
            continue
        for par, prop in (esquema.get("properties") or {}).items():
            p_sig = firma.parameters.get(par)
            if p_sig is None or p_sig.default is inspect.Parameter.empty:
                continue
            numerico = isinstance(p_sig.default, (int, float)) and not isinstance(
                p_sig.default, bool)
            if numerico and prop.get("type") == "string":
                malos.append(f"{nombre}.{par}")
    assert not malos, (
        f"publicados como string con defecto numérico: {malos}. "
        f"Sin anotación FastMCP los declara string y el cliente manda una "
        f"cadena (BUG-0112).")


def test_p_admite_entero_y_lista_en_el_esquema(esquemas):
    """`p` es el nodo central del carril guiado: si no se puede fijar, el
    análisis se detiene ahí."""
    prop = esquemas["confirm_and_estimate"]["properties"]["p"]
    texto = str(prop)
    assert "integer" in texto, prop
    assert "array" in texto or "list" in texto, prop


@pytest.mark.parametrize("entrada,esperado", [
    (3, [3]), ("3", [3]), ([1, 1, 2], [1, 1, 2]), ("[1,1,2]", [1, 1, 2]),
    (0, []), ("", []),
])
def test_el_normalizador_acepta_las_formas_documentadas(entrada, esperado):
    from art.pipeline import ordenes_ar
    assert ordenes_ar(srv._orden_ar(entrada)) == esperado


def test_una_cadena_ya_no_se_descompone_en_digitos():
    """El camino CALLADO, que era el peligroso: una cadena es iterable, así que
    `"12"` daba [1, 2] —dos factores— en vez de [12], un AR(12). Sin error, sin
    aviso, y con los grados de libertad y el AIC mal."""
    from art.pipeline import ordenes_ar
    assert ordenes_ar(srv._orden_ar("12")) == [12]


def test_un_orden_no_entero_falla_DICIENDO_cual_es():
    """El otro camino era ruidoso pero mudo: `TypeError: '>' not supported
    between 'str' and 'int'`, que no menciona ni el parámetro ni la
    herramienta, y costó una sesión rastrear."""
    from art.pipeline import _arma_starts
    with pytest.raises(TypeError, match=r"\bq\b"):
        _arma_starts(None, 1, "2", 0, 0, 12)


# ══════ BUG-0111 — el visor, bajo servidor, calla ══════

def test_bajo_servidor_no_se_pide_al_shell_que_abra_la_figura():
    """En Windows el anfitrión INTERCEPTA `os.startfile` y lo convierte en un
    diálogo «¿adjunto este fichero a la sesión?». Una vez por figura, y una
    sesión guiada dispara del orden de una docena.

    Bajo servidor la ventana es redundante por diseño: la figura ya viaja como
    ImageContent."""
    from tests._fuente import fuente_de
    src = "\n".join(l.split("#", 1)[0]
                    for l in fuente_de(srv._show_fig).splitlines())
    assert "_BAJO_SERVIDOR" in src


def test_pero_como_BIBLIOTECA_el_visor_se_conserva():
    """Un arreglo que lo apagara en todas partes rompería guiones y cuadernos
    para tapar un problema del servidor. `main()` es el único sitio que lo
    marca, así que importar el módulo lo deja en False."""
    from tests._fuente import fuente_de
    assert srv._BAJO_SERVIDOR is False, "importar no puede activarlo"
    assert "_BAJO_SERVIDOR = True" in fuente_de(srv.main)


# ══════ BUG-0121 — …pero SÓLO donde el anfitrión intercepta ══════
#
# Se leen con las dos de arriba, y por eso van aquí. El 0111 apagó la ventana
# bajo servidor sin mirar la plataforma; el defecto medido era de Windows.

def test_en_posix_bajo_servidor_la_ventana_se_conserva():
    """La regresión. En Linux nadie intercepta `xdg-open`, y en un anfitrión
    que no pinta el ImageContent la ventana es el ÚNICO canal por el que el
    analista ve la figura. El 0111 se lo cerró: nodo de Box-Cox del RATIO de la
    réplica de Bolivia, 8-sep, el analista se quedó mirando texto."""
    assert srv._visor_procede(True, "posix", {}, bajo_pytest=False)


def test_en_windows_bajo_servidor_sigue_callada():
    """Y el 0111 se conserva: allí la petición al shell se convierte en un
    diálogo modal de adjuntar, una vez por figura."""
    assert not srv._visor_procede(True, "nt", {}, bajo_pytest=False)


def test_como_biblioteca_la_ventana_se_abre_en_las_dos():
    for so in ("posix", "nt"):
        assert srv._visor_procede(False, so, {}, bajo_pytest=False), so


def test_ART_VIEWER_enciende_donde_el_0111_apagaria():
    """Para el anfitrión de Windows que no intercepte —o que sí y aun así
    prefiera la ventana."""
    assert srv._visor_procede(True, "nt", {"ART_VIEWER": "1"}, bajo_pytest=False)


def test_ART_NO_VIEWER_y_pytest_ganan_a_todo():
    assert not srv._visor_procede(
        True, "nt", {"ART_VIEWER": "1", "ART_NO_VIEWER": "1"}, bajo_pytest=False)
    assert not srv._visor_procede(False, "posix", {}, bajo_pytest=True)


def test_show_fig_consulta_la_decision_y_no_la_reimplementa():
    """La enfermedad recurrente de este proyecto es el concepto escrito dos
    veces, y la copia que se queda atrás. La decisión vive en UN sitio."""
    from tests._fuente import fuente_de
    src = "\n".join(l.split("#", 1)[0]
                     for l in fuente_de(srv._show_fig).splitlines())
    assert "_visor_procede(" in src
    # `os.name` sí aparece: se le PASA. Lo que no puede aparecer es la regla.
    assert '"nt"' not in src, "la plataforma se JUZGA en _visor_procede"


# ══════ BUG-0113 — la ruta de la figura, dicha ══════

def test_el_carril_guiado_no_tira_la_ruta_que_devuelve_show_fig():
    """`_show_fig` DEVUELVE la ruta: es la mitad del arreglo del BUG-0078. Pero
    `guided_identification` la descartaba en sus cinco llamadas, y la red vive
    en `_result()`, por donde este carril no pasa.

    Con el visor apagado por el 0111 y un cliente que no renderice, el analista
    se queda sin figura, sin ventana y sin ruta."""
    from tests._fuente import fuente_de
    gi = getattr(srv.guided_identification, "fn", srv.guided_identification)
    src = fuente_de(gi)
    # BUG-0126: el carril guiado pide la RUTA, no la ventana.
    llamadas = src.count("_escribe_fig(")
    usadas = src.count("= _escribe_fig(")
    assert llamadas > 0
    assert usadas == llamadas, (
        f"{llamadas - usadas} de {llamadas} llamadas descartan el retorno")
    assert "_nota_figura(" in src, "la ruta se recoge y no se dice"


# ══════ BUG-0114 — git acotado DE VERDAD ══════

@pytest.mark.skipif(os.name == "nt", reason="el git falso es un guion POSIX")
def test_version_instrumento_vuelve_aunque_git_deje_un_nieto_vivo(tmp_path):
    """`subprocess.run(timeout=)` NO acota: al saltar el plazo mata al hijo y
    vuelve a llamar a `communicate()` SIN plazo. Si git dejó un nieto con el
    extremo de escritura abierto, esa segunda espera es infinita — y bajo
    servidor MCP cuelga la herramienta entera DESPUÉS de haber escrito el .inp,
    el .out y el .pre."""
    import stat
    git = tmp_path / "git"
    git.write_text("#!/bin/sh\nsleep 600 &\necho deadbeef\nsleep 600\n")
    git.chmod(git.stat().st_mode | stat.S_IEXEC)
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(srv.__file__)))
    guion = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {raiz!r})
        from art.guion import version_instrumento
        version_instrumento()
        print("VUELVE")
    """)
    t0 = time.time()
    r = subprocess.run([sys.executable, "-c", guion],
                       env={**os.environ,
                            "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]},
                       capture_output=True, text=True, timeout=25)
    assert "VUELVE" in r.stdout, r.stderr[-400:]
    assert time.time() - t0 < 20, "no acota"


def test_git_no_hereda_el_stdin_del_servidor():
    """Bajo un servidor stdio ese stdin es la tubería del protocolo y no se
    cierra nunca: cualquier git que decida leer de ahí se queda esperando."""
    from tests._fuente import fuente_de
    from art.guion import version_instrumento
    src = fuente_de(version_instrumento)
    assert "stdin=subprocess.DEVNULL" in src
    assert "GIT_TERMINAL_PROMPT" in src


def test_los_cuatro_estan_documentados():
    for n in ("0112", "0113", "0114"):
        assert os.path.exists(f"bugs/BUG-{n}-repro/repro.py"), n


# ══════ 0113 contra 0094 — dos arreglos correctos que chocaban ══════

def test_la_ruta_de_la_figura_va_DENTRO_del_sobre_guiado():
    """BUG-0113 exige decir la ruta; BUG-0094 exige que la salida guiada TERMINE
    en la marca de decisión. Pegar la nota al final rompía el segundo: la última
    línea pasaba a ser un nombre de fichero y el turno dejaba de cerrar donde
    debía.

    La ruta es evidencia, así que va delante de la decisión — no detrás."""
    texto = ("## 3 · CONCLUSIONES\n\nse sostiene\n\n"
             "## 4 · DECISIÓN\n\n**A)** adoptar\n\n"
             + srv.FIN_DE_TURNO_GUIADO)
    r = srv._con_nota_figura(texto, "/tmp/x.png")
    assert r.rstrip().endswith(srv.FIN_DE_TURNO_GUIADO)
    assert "/tmp/x.png" in r
    assert r.index("/tmp/x.png") < r.index(srv.FIN_DE_TURNO_GUIADO)


def test_sin_marca_la_nota_va_al_final_como_siempre():
    """El carril autónomo y los instrumentos no llevan marca: ahí el final es
    su sitio."""
    r = srv._con_nota_figura("## Diagnosis\n\nQ ✓", "/tmp/y.png")
    assert r.rstrip().endswith("*")
    assert "/tmp/y.png" in r


def test_sin_ruta_no_se_toca_el_texto():
    t = "## Diagnosis\n\nQ ✓"
    assert srv._con_nota_figura(t, "") == t


def test_un_solo_sitio_sabe_donde_va_la_nota():
    """Estaba escrito a mano en tres sitios y cada uno lo hacía a su manera —
    que es exactamente cómo se llegó al choque."""
    import pathlib
    src = "\n".join(l.split("#", 1)[0] for l in
                    pathlib.Path("src/art/mcp_server.py").read_text().splitlines())
    assert src.count("FIN_DE_TURNO_GUIADO)") <= 2, (
        "más de un sitio decide dónde va la nota respecto de la marca")


# ══════ BUG-0120 — el bloque del modelo, una sola vez ══════

@pytest.fixture(scope="module")
def salidas(tmp_path_factory):
    """Las seis herramientas que cierran una iteración, ejecutadas de verdad.

    La comprobación estática no vale aquí: en `meg_reformulate` la ecuación
    entraba por DOS niveles de indirección —`ecuacion=eq` y `{eq}` dentro de un
    `header` que llegaba como `especificacion=`— y un `grep` de un solo nivel
    decía que estaba limpia. Lo único que discrimina es contar en la salida."""
    import warnings as _w
    import numpy as _np
    import fue as _fue
    from art.pipeline import _RESCALE_FACTOR as _RF, _write_inp as _wi
    d = tmp_path_factory.mktemp("sobre")
    rng = _np.random.default_rng(6)
    n = 180
    t = _np.arange(n)
    y = (100 + _np.cumsum(rng.standard_normal(n) * 0.3)
         + 2.0 * _np.cos(2 * _np.pi * 4 * t / 12))
    ts = _fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="M")
    F = lambda x: getattr(x, "fn", x)          # noqa: E731
    out = {}
    with _w.catch_warnings():
        _w.simplefilter("ignore")
        _wi(ts, _fue.Model(ts, d=1, mu=0.0, estimate_mu=False, refactor=_RF),
            str(d / "M.inp"))
        def _txt(r):
            return "\n".join(c.text for c in r if getattr(c, "text", None))
        out["confirm_and_estimate"] = _txt(F(srv.confirm_and_estimate)(
            str(d / "M.inp"), str(d / "M0.inp"), lam=0.0, d=1, D=0, p=0, q=0,
            n_harmonics=5, estimate_mu=True, guion_decision="base"))
        out["estimate_and_diagnose"] = _txt(F(srv.estimate_and_diagnose)(
            str(d / "M0.inp"), str(d / "M0b.inp")))
        out["meg_reformulate"] = _txt(F(srv.meg_reformulate)(
            str(d / "M0.inp"), freq=4, output_path=str(d / "M1.inp")))
        out["suggest_intervention_form"] = _txt(F(srv.suggest_intervention_form)(
            str(d / "M0.inp"), date="06/2010", form="step",
            output_path=str(d / "M2.inp")))
        out["build_model"] = _txt(F(srv.build_model)(
            str(d / "M.inp"), str(d / "M3.inp"), max_rounds=1))
    return out


@pytest.mark.parametrize("herramienta", [
    "confirm_and_estimate", "estimate_and_diagnose", "meg_reformulate",
    "suggest_intervention_form", "build_model"])
def test_el_bloque_del_modelo_sale_UNA_vez(salidas, herramienta):
    """`meg_reformulate` lo imprimía dos veces, idéntico, en las secciones 2 y
    3. Era un residuo del propio arreglo del BUG-0094: se añadió el campo
    `ecuacion=` sin quitar el `{eq}` que la cabecera ya llevaba de cuando esta
    función componía su salida a mano.

    Se comprueban las cinco que muestran ecuación, no sólo la que falló: el
    residuo podía estar en cualquiera de las que se envolvieron a la vez."""
    n = salidas[herramienta].count("MODELO ESTIMADO:")
    assert n == 1, f"{herramienta}: {n} veces"


def test_record_version_NO_muestra_esa_ecuacion_y_es_correcto():
    """La sexta envuelta sale con CERO, y no es un defecto: `record_version`
    abre con `_mirar` —acepta un `.pre`— y la ecuación del prompt imprime cada
    coeficiente con su error típico debajo. Desde un `.pre` esos errores no son
    fiables (BUG-0090/0091), así que usa la ecuación ESTRUCTURAL del guion, que
    dice la FORMA sin inventar precisión.

    Se fija aquí para que un futuro «arreglo» de la asimetría no la rompa."""
    from tests._fuente import fuente_de
    rv = getattr(srv.record_version, "fn", srv.record_version)
    src = fuente_de(rv)
    assert "_build_equation" in src
    assert "_equation_for_prompt" not in src


def test_la_especificacion_del_MEG_sigue_diciendo_lo_suyo(salidas):
    """Quitar la ecuación de la cabecera no puede vaciar la etapa 1: sigue
    siendo la ESPECIFICACIÓN —qué se activó, dónde, con o sin testigo, desde
    qué `.pre`—."""
    t = salidas["meg_reformulate"]
    i = t.index("## 1 · ESPECIFICACIÓN")
    j = t.index("## 2 ·")
    esp = t[i:j]
    assert "ifadf" in esp and "Re-estimado desde" in esp


# ══════ BUG-0122 — una figura que nadie escribe ══════
#
# Cierra la familia 0078 · 0081 · 0111 · 0113 · 0119 · 0121: todos son «la
# figura llega, o no llega, al analista». Los anteriores arreglaron el CAMINO;
# éste arregla que quince herramientas no entraran en él.

def test_result_escribe_la_figura_no_solo_la_busca():
    """`_result` buscaba la huella en `_FIGURAS` por si otro la había escrito.
    Si nadie lo hizo, se callaba: ni fichero, ni ventana, ni ruta que citar."""
    from tests._fuente import fuente_de
    src = "\n".join(l.split("#", 1)[0]
                     for l in fuente_de(srv._result).splitlines())
    # BUG-0126: escribir dejó de ser `_show_fig` y pasó a ser `_escribe_fig`,
    # que escribe y NO abre ventana. La propiedad que esta prueba cuida es que
    # `_result` escriba; con cuál de las dos, es implementación.
    assert "_escribe_fig(" in src or "_show_fig(" in src


def test_el_ImageContent_nace_en_un_solo_sitio():
    """La enfermedad de este proyecto es el concepto escrito dos veces. Aquí
    estaba escrito VEINTITRÉS veces, y en quince herramientas la mitad que
    escribe el fichero faltaba. Con un solo constructor, olvidarlo deja de ser
    posible."""
    import io as _io
    import os as _os
    fuente = _io.open(_os.path.join(_os.path.dirname(srv.__file__),
                                    "mcp_server.py"), encoding="utf-8").read()
    fuera = [l for l in fuente.splitlines()
             if "ImageContent(" in l
             and "from mcp.types" not in l
             and "return ImageContent(type=" not in l]
    assert not fuera, f"{len(fuera)} ImageContent fuera de _imagen: {fuera[:3]}"


def test_imagen_escribe_siempre(tmp_path, monkeypatch):
    """Y lo hace de verdad, no sólo en el fuente."""
    import base64
    monkeypatch.setenv("ART_FIG_DIR", str(tmp_path))
    png = base64.b64encode(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6360000002000100ffff03000006000557bfabd4000000"
        "0049454e44ae426082")).decode()
    srv._FIGURAS.pop(srv._huella_figura(png), None)
    item = srv._imagen(png, "prueba")
    assert item.type == "image" and item.data == png
    assert srv._huella_figura(png) in srv._FIGURAS
    assert list(tmp_path.glob("*.png")), "no escribió ningún fichero"


def test_ninguna_herramienta_de_figura_se_queda_sin_escribirla():
    """El censo. Una herramienta que devuelve figura tiene que pasar por
    `_imagen` o por `_result` — que ahora escribe. La medida que encontró el
    defecto daba 15 de 28 sin escribir."""
    import ast
    import io as _io
    import os as _os
    ruta = _os.path.join(_os.path.dirname(srv.__file__), "mcp_server.py")
    fuente = _io.open(ruta, encoding="utf-8").read()
    huerfanas = []
    for n in ast.walk(ast.parse(fuente)):
        if not isinstance(n, ast.FunctionDef):
            continue
        if not any("tool" in ast.dump(d) for d in n.decorator_list):
            continue
        cuerpo = ast.get_source_segment(fuente, n) or ""
        if "ImageContent(" in cuerpo and "_imagen(" not in cuerpo:
            huerfanas.append(n.name)
    assert not huerfanas, huerfanas


# ══════ BUG-0126 — una ventana por imagen, ni más ni menos ══════
#
# Escribir y ENSEÑAR eran la misma función. Escribir es idempotente y se pide
# tantas veces como haga falta; abrir una ventana no. La misma figura abría
# TRES: la herramienta pedía la ruta, `_result` la pedía otra vez para la nota,
# y `_imagen` una tercera al construir la salida.
#
# Ninguna de las 1.617 pruebas lo vio: todas comprueban que el FICHERO se
# escribe, y ninguna cuenta ventanas — bajo pytest el visor no se abre, con
# razón, y nadie separó «no abrir en la suite» de «poder contar cuántas
# abriría».

def test_solo_imagen_abre_ventana():
    """El censo. `_show_fig` es el único que abre, y dentro del servidor lo
    llama sólo `_imagen`. Todo lo demás usa `_escribe_fig`, que escribe y
    calla."""
    import ast
    import io as _io
    import os as _os
    import re as _re
    ruta = _os.path.join(_os.path.dirname(srv.__file__), "mcp_server.py")
    fuente = _io.open(ruta, encoding="utf-8").read()
    culpables = []
    for n in ast.walk(ast.parse(fuente)):
        if not isinstance(n, ast.FunctionDef) or n.name in ("_imagen", "_show_fig"):
            continue
        cuerpo = ast.get_source_segment(fuente, n) or ""
        if _re.search(r"(?<![_\w])_show_fig\(", cuerpo):
            culpables.append(n.name)
    assert not culpables, (
        f"{len(culpables)} funciones abren ventana por su cuenta: {culpables}")


def test_se_cuentan_las_ventanas_no_solo_los_ficheros(monkeypatch, tmp_path):
    """La prueba que faltaba: contar aperturas. Se sustituye `_abrir_visor` y
    se levanta la guarda de pytest para poder medir lo que el servidor haría."""
    import base64
    import sys as _sys
    png = base64.b64encode(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6360000002000100ffff03000006000557bfabd4000000"
        "0049454e44ae426082")).decode()
    monkeypatch.setenv("ART_FIG_DIR", str(tmp_path))
    monkeypatch.delenv("ART_NO_VIEWER", raising=False)
    ventanas = []
    monkeypatch.setattr(srv, "_abrir_visor", lambda p: ventanas.append(p) or "")
    monkeypatch.setattr(srv, "_visor_procede",
                        lambda *a, **k: True)      # como si no fuera la suite
    srv._FIGURAS.pop(srv._huella_figura(png), None)

    srv._escribe_fig(png, "a")
    srv._escribe_fig(png, "b")
    assert ventanas == [], "escribir no puede abrir ventana"

    srv._imagen(png, "c")
    assert len(ventanas) == 1, f"una imagen, {len(ventanas)} ventanas"


def test_escribe_fig_sigue_escribiendo(monkeypatch, tmp_path):
    """Separar no puede haber roto la mitad que ya funcionaba (BUG-0122)."""
    import base64
    monkeypatch.setenv("ART_FIG_DIR", str(tmp_path))
    png = base64.b64encode(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6360000002000100ffff03000006000557bfabd4000000"
        "0049454e44ae426082")).decode()
    srv._FIGURAS.pop(srv._huella_figura(png), None)
    ruta = srv._escribe_fig(png, "prueba")
    assert ruta and os.path.exists(ruta)
    assert srv._huella_figura(png) in srv._FIGURAS
