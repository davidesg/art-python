"""Los RECURSOS del servidor MCP — lo que el modelo puede PEDIR.

Por qué existe este módulo
--------------------------
La documentación de `art` se entregaba por un solo canal: la descripción de cada
herramienta, que el protocolo **empuja en cada llamada**. Son 75.548 caracteres
en 46 herramientas, y un cliente real entregó al modelo **el 23%** — o sea que se
perdían unos 58.000 caracteres por sesión, entre ellos la documentación de
`easter`, la de `ar_f_freqs` y la de Shin-Fuller (BUG-0116).

Acortar no era el arreglo. El texto hace falta: lo que estaba mal es **el canal**.

MCP tiene un primitivo para esto y `art` usaba **cero**:

    herramientas   se EMPUJAN en cada llamada   → caras, y se recortan
    recursos       se PIDEN cuando hacen falta  → completos, y direccionables

Lo que va aquí es lo que se consulta: la referencia, el procedimiento, y —sobre
todo— **la memoria de por qué las cosas se hacen así**.

El registro de defectos, que es la parte que faltaba
----------------------------------------------------
El propio `guion.py` dice, sobre el registro de un análisis:

    «lo que una iteración fallida produce de valor NO es el modelo que se
    descarta, es la RAZÓN por la que se descarta — que es lo único que impide
    volver a intentarlo.»

`art` aplicaba ese principio al análisis y **no a sí mismo**. Hay 121 informes,
cada uno con una causa medida y su razón escrita, y el modelo que opera la
herramienta no veía ninguno. Es el mismo principio sin aplicar un nivel más
arriba — y no es teórico: el asistente propuso capar un AR(6) teniendo la razón
por la que no se hace escrita en el informe que lo documenta.
"""
from __future__ import annotations

import os
import re

def _raiz_del_material() -> str:
    """Dónde está el material que estos recursos sirven.

    BUG-0125. Esto contaba tres directorios por encima del módulo, que es la
    disposición del REPOSITORIO. En una instalación no existe, y además el
    material tampoco viajaba: `pyproject.toml` empaqueta sólo `src/` y
    `MANIFEST.in` lleva un `prune bugs` deliberado. La rueda 0.2.0 publicada
    tiene 27 ficheros, cero de `bugs/` y cero de `docs/` — comprobado
    descargándola, no leyendo la configuración. O sea que los cuatro recursos de
    contenido existían en `resources/list`, se podían pedir, y contestaban que no
    había nada. La peor forma de fallar: no un error, una ausencia.

    Ahora se mira primero **dentro del paquete** —`art/material/`, que
    `tools/sync_material.py` genera y el empaquetado distribuye— y sólo si no
    está, el árbol de trabajo. Un desarrollador que no haya sincronizado sigue
    viendo el original; una instalación ve la copia; y ninguno de los dos ve un
    directorio que no le corresponde.
    """
    aqui = os.path.dirname(os.path.abspath(__file__))
    empaquetado = os.path.join(aqui, "material")
    if os.path.isdir(empaquetado):
        return empaquetado
    return os.path.dirname(os.path.dirname(aqui))      # árbol de trabajo


#: Raíz del material: el paquete instalado o el árbol de trabajo.
_RAIZ = _raiz_del_material()

#: Qué decir cuando no hay material. NO es «no hay defectos»: es que esta
#: instalación no lo trae, y el sitio donde está se dice explícitamente.
SIN_MATERIAL = (
    "*(esta instalación de `art` no incluye {qué}. El material vive en el "
    "repositorio: github.com/davidesg/art-python. Si esperabas verlo aquí, "
    "es el BUG-0125.)*")


def _dir(nombre: str) -> str:
    return os.path.join(_RAIZ, nombre)


def _lee(ruta: str, tope: int = 60_000) -> str:
    """Un fichero de texto, acotado. El tope existe porque un recurso entra en
    la conversación entero: si algo no cabe, mejor decirlo que truncarlo en
    silencio — que es el defecto que este módulo viene a corregir."""
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            t = fh.read()
    except OSError as e:
        return f"*(no se puede leer `{os.path.basename(ruta)}`: {type(e).__name__})*"
    if len(t) > tope:
        t = (t[:tope] + f"\n\n*[…recortado en {tope} caracteres de "
                        f"{len(t)}. El fichero completo está en "
                        f"`{os.path.relpath(ruta, _RAIZ)}`.]*")
    return t


# ── el registro de defectos ───────────────────────────────────────────

def _informes() -> list[tuple[str, str, str, str, str]]:
    """(id, estado, severidad, título, fichero) de cada informe, por id."""
    carpeta = _dir("bugs")
    filas = []
    try:
        ficheros = sorted(os.listdir(carpeta))
    except OSError:
        return filas
    for f in ficheros:
        if not (f.startswith("BUG-") and f.endswith(".md")):
            continue
        campos = {}
        try:
            with open(os.path.join(carpeta, f), encoding="utf-8",
                      errors="replace") as fh:
                for linea in fh:
                    if linea.strip() == "---" and campos:
                        break
                    m = re.match(r"^([a-z_]+):\s*(.*)$", linea)
                    if m:
                        campos[m.group(1)] = m.group(2).strip()
        except OSError:
            continue
        filas.append((campos.get("id", f[:8]), campos.get("status", "?"),
                      campos.get("severity", "?"), campos.get("title", ""), f))
    return filas


def indice_de_defectos() -> str:
    """El índice: qué se ha roto, cómo, y qué sigue abierto."""
    filas = _informes()
    if not filas:
        return SIN_MATERIAL.format(qué="el registro de defectos")
    abiertos = [f for f in filas if f[1] not in ("fixed", "wontfix", "duplicate")]
    L = [
        "# Registro de defectos de ART",
        "",
        f"{len(filas)} informes, {len(abiertos)} sin cerrar. Cada uno lleva su "
        "causa **medida** y la razón por la que se arregló así.",
        "",
        "**Para qué sirve leer esto.** Un informe cerrado no cuenta un fallo: "
        "cuenta **por qué el método es como es**. Antes de proponer una "
        "simplificación que parezca obvia —capar un operador, podar un "
        "armónico, fiarse de un error típico— conviene mirar si ya está "
        "documentada como error. Pide el informe con "
        "`art://defectos/BUG-XXXX`.",
        "",
    ]
    if abiertos:
        L += ["## Sin cerrar", ""]
        for i, est, sev, tit, _ in abiertos:
            L.append(f"- **{i}** · {est} · {sev} — {tit}")
        L.append("")
    L += ["## Cerrados", ""]
    for i, est, sev, tit, _ in filas:
        if (i, est, sev, tit) in [(a[0], a[1], a[2], a[3]) for a in abiertos]:
            continue
        L.append(f"- {i} · {sev} — {tit}")
    return "\n".join(L)


def informe_de_defecto(bug_id: str) -> str:
    """Un informe entero, por su identificador (`BUG-0097` o `0097`)."""
    bug_id = bug_id.strip().upper()
    if not bug_id.startswith("BUG-"):
        bug_id = f"BUG-{bug_id.zfill(4)}"
    for i, _, _, _, fichero in _informes():
        if i.upper() == bug_id:
            return _lee(os.path.join(_dir("bugs"), fichero))
    disponibles = ", ".join(sorted(x[0] for x in _informes())[:6])
    return (f"*(no hay ningún `{bug_id}`. El índice está en "
            f"`art://defectos`; los primeros son {disponibles}…)*")


# ── documentos de diseño ──────────────────────────────────────────────

def _documentos() -> list[str]:
    try:
        return sorted(f for f in os.listdir(_dir("docs")) if f.endswith(".md"))
    except OSError:
        return []


def indice_de_documentos() -> str:
    docs = _documentos()
    if not docs:
        return SIN_MATERIAL.format(qué="los documentos de diseño")
    L = ["# Documentos de diseño de ART", "",
         "Se piden por `art://doc/<NOMBRE>`, sin la extensión.", ""]
    for d in docs:
        L.append(f"- `{d[:-3]}`")
    return "\n".join(L)


def documento(nombre: str) -> str:
    nombre = nombre.strip()
    if not nombre.endswith(".md"):
        nombre += ".md"
    if nombre not in _documentos():
        return (f"*(no hay `{nombre}`. El índice está en `art://docs`.)*")
    return _lee(os.path.join(_dir("docs"), nombre))
