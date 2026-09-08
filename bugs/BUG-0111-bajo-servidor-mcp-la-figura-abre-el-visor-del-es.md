---
id: BUG-0111
title: Bajo servidor MCP la figura abre el visor del escritorio — la petición al shell (os.startfile) la intercepta el anfitrión y la convierte en un diálogo de adjuntar que saca al analista del panel donde trabaja
status: fixed
severity: high
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-08
reporter: David
tags:
  - windows
  - figuras
  - visor
  - mcp
references:
  - BUG-0078
  - BUG-0082
  - BUG-0113
---

## Summary

`_show_fig` llama a `_abrir_visor` **siempre** que no esté puesto
`ART_NO_VIEWER` ni cargado `pytest` — también cuando el módulo corre como
**servidor MCP**. En Windows eso es `os.startfile(path)`, una petición al shell
para que abra el `.png` con su aplicación asociada.

Bajo un anfitrión MCP esa petición no es inocua. En Claude Code 2.1.260 (app de
escritorio, Windows 11) el anfitrión **la intercepta** y la convierte en un
diálogo modal:

    Attach "art_diagnosis_4c5182f7764f.png" to this session?
    Claude will be able to read this file and may share its contents with
    third-party tools it connects to.                      [Cancel] [Attach]

Al aceptar, el usuario acaba en otro panel de la aplicación (Chat/Cowork), fuera
del panel donde estaba analizando. **Ocurre una vez por figura.**

Bajo servidor la ventana del escritorio es redundante por diseño: la figura ya
viaja como `ImageContent` en la respuesta MCP. Lo dice el propio docstring de
`_abrir_visor` — *«ésta no es la vía principal […] La ventana del escritorio es
un extra.»* Aquí el extra no aporta nada y sí interrumpe.

## Impact

**Alto en el carril guiado, que es donde las figuras son la mitad del trabajo.**
Cada nodo produce una o dos figuras, y cada figura abre un diálogo que
interrumpe y desplaza al analista de panel. Una sesión guiada normal —Box-Cox,
d, estacionalidad, m00, m01…— dispara del orden de una docena.

Agravantes concretos observados:

* **En esta máquina el visor no abre nada de todos modos.** La asociación de
  `.png` es Fotos (UWP) y `ShellExecuteW` delega y devuelve éxito sin arrancar
  proceso: censo de procesos antes/después, cero nuevos (ver prueba 3 de
  `RESULTADOS.md` de la sesión de Windows). Coste puro, beneficio cero.
* **El diálogo puede citar un fichero viejo.** Se observó uno adjuntando
  `art_boxcox_159e7265e60f.png`, escrito el 7-sep a las 20:54 —la primera vez
  que la rama `os.startfile` se ejecutó en Windows— en una sesión que analizaba
  otra serie por completo.
* **El texto del diálogo habla de compartir el contenido con herramientas de
  terceros.** Que una biblioteca de análisis provoque esa pregunta sin que el
  analista haya pedido nada es, como mínimo, indeseable.

No corrompe resultados ni ficheros: es un defecto de flujo de trabajo.

## Reproduction

Experimento controlado, dos subprocesos idénticos salvo por `ART_NO_VIEWER`,
cada uno llamando a `art.mcp_server._show_fig` con una figura distinta,
separados 25 s, escribiendo ambos en el mismo `ART_FIG_DIR`:

    expA   ART_NO_VIEWER ausente   os.startfile LLAMADO      art_expA_d3e60d8fc003.png   -> DIÁLOGO SÍ
    expB   ART_NO_VIEWER=1         os.startfile NO llamado   art_expB_439280184d15.png   -> DIÁLOGO NO

Ambos `rc=0`, ambos escribieron su `.png`, ambos con `_ULTIMO_VISOR_ERROR`
vacío.

Detalle importante del montaje: **no hubo MCP, ni lectura de fichero por el
asistente, ni envío de fichero al usuario**. Ninguna imagen entró en la
conversación por ningún canal. Eso descarta el `ImageContent` como disparador —
expA lo produjo sin que hubiera ningún `ImageContent` en juego — y descarta
también un vigilante del directorio, porque expB escribió en la misma carpeta y
en el mismo minuto sin disparar nada.

**La única variable es la llamada al shell.**

Entorno: Windows 11 Pro 10.0.22631 · Claude Code 2.1.260 (app de escritorio) ·
Python 3.12.10 · art 0.2.0 · fue 0.1.14 · atsw 1.3.0.

## Root cause

`src/art/mcp_server.py`, guarda de `_show_fig`:

    if os.environ.get("ART_NO_VIEWER") or "pytest" in sys.modules:
        return path
    _ULTIMO_VISOR_ERROR = _abrir_visor(path)

La guarda contempla dos contextos en los que no se debe abrir ventana —la suite
y el apagado explícito— pero **no contempla el tercero: correr como servidor**.
`main()` es hoy `mcp.run()` y no deja constancia de nada, así que `_show_fig` no
tiene manera de saber en qué contexto está.

Históricamente el defecto estaba latente. Antes de BUG-0078 el código llamaba a
`xdg-open` sin condición de plataforma, en un hilo daemon y con la salida a
`/dev/null`: en Windows era un `FileNotFoundError` invisible y en Linux fallaba
tan deprisa que casi nunca abría nada. Al hacerse **síncrona y multiplataforma**
—que era justamente el arreglo del 0078— la petición al shell empezó a llegar
de verdad, y con ella el diálogo. El 0078 no introdujo un error de lógica;
destapó que faltaba el tercer contexto en la guarda.

## Fix

Que `main()` deje constancia de que se corre como servidor, y que la guarda lo
contemple:

    #: True cuando el módulo corre COMO SERVIDOR MCP. Bajo servidor la figura ya
    #: viaja como ImageContent —la ventana del escritorio es un extra, según dice
    #: el docstring de `_abrir_visor`—, así que pedirle al shell que la abra no
    #: aporta nada y en algunos anfitriones no es inocuo: el de Windows
    #: intercepta la petición y la convierte en un diálogo de «¿adjunto este
    #: fichero a la sesión?», que saca al analista del panel en el que trabaja.
    _BAJO_SERVIDOR = False

    def main():
        global _BAJO_SERVIDOR
        _BAJO_SERVIDOR = True
        mcp.run()

y en `_show_fig`:

    if _BAJO_SERVIDOR or os.environ.get("ART_NO_VIEWER") or "pytest" in sys.modules:
        return path

El uso como **biblioteca** —guiones, cuadernos, la CLI— conserva el visor, que
ahí sí es lo que el usuario espera y no hay anfitrión que intercepte nada.

### No debe entrar solo

Quitar la ventana deja la **ruta** como única red de seguridad cuando el cliente
no renderiza la imagen, y hoy esa red tiene un agujero: `guided_identification`
llama a `_show_fig` en sus cinco puntos y **descarta el valor devuelto**, sin
llamar nunca a `_nota_figura`. La red del BUG-0078 vive en `_result()`, por
donde el carril guiado no pasa. Con la ventana quitada y un cliente que no
pinte, el analista se queda **sin figura, sin ventana y sin ruta** — en el
carril donde más importan.

Así que este arreglo va acompañado de que el carril guiado cite siempre la
ruta, que es **BUG-0113**. Los dos deben entrar juntos: quitar la ventana sin
poner la ruta empeora el caso que este informe describe.

### Paliativo mientras tanto

Poner `ART_NO_VIEWER=1` en el `env` del servidor en la configuración del
anfitrión. No requiere tocar código y resuelve el síntoma por completo.

## Validation

* Repetir el experimento de arriba con el arreglo puesto, **lanzando de verdad
  el servidor** (`art-mcp`) y no llamando a las funciones desde un guion: por
  el guion `_BAJO_SERVIDOR` sigue siendo `False` y el visor debe seguir
  abriéndose. Son dos casos distintos y la prueba tiene que distinguirlos.
* Prueba unitaria: tras `main()` (o forzando `_BAJO_SERVIDOR = True`),
  `_show_fig` no debe llamar a `_abrir_visor` — espiarlo, no inferirlo del
  efecto, porque en una máquina sin asociación de `.png` el efecto no se
  observa.
* Comprobar que el `.png` se sigue escribiendo y que la ruta se sigue
  devolviendo: es lo único que queda cuando no hay ventana.

## Lo que este informe NO cubre

Que el panel de Code no pinte las imágenes devueltas por herramientas —ni el
`ImageContent` de MCP ni las de la herramienta de lectura del asistente— es un
defecto **del cliente**, no de `art`, y va aparte. `art` entrega la figura por
el canal canónico del protocolo. Los dos síntomas aparecen juntos y se
confundieron durante la investigación; conviene no volver a mezclarlos.
Documentado en `PRUEBA_WINDOWS/INFORME_RENDERIZADO_FIGURAS.md`.

---

## Cierre (2026-09-08)

`main()` marca `_BAJO_SERVIDOR = True` y la guarda de `_show_fig` lo contempla.
Importar el módulo lo deja en False, así que **el uso como biblioteca conserva el
visor** — un arreglo que lo apagara en todas partes rompería guiones y cuadernos
para tapar un problema del servidor.

Dos pruebas: que la guarda mire la marca, y que importar no la active.
