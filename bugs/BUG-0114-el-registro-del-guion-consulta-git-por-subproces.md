---
id: BUG-0114
title: El registro del guion consulta git por subproceso y bajo servidor MCP se cuelga para siempre — el `timeout` de subprocess.run no acota, y la herramienta no responde nunca aunque el trabajo esté hecho
status: fixed
severity: critical
component: guion
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-08
reporter: David
tags:
  - mcp
  - cuelgue
  - windows
references:
  - BUG-0098
  - BUG-0111
---

## Summary

`version_instrumento()` (`guion.py`) consulta `git` por subproceso para sellar
el registro con el SHA del instrumento. Bajo **servidor MCP** esa consulta no
termina nunca, y con ella la herramienta que la llamó.

El trabajo ya está hecho cuando ocurre: `confirm_and_estimate` estima, escribe
`.inp`, `.out` y `.pre` — todos con su tamaño correcto — y **se cuelga en el
último paso, el registro del guion**. La llamada no devuelve nada, ni error ni
resultado. Desde el cliente parece que la herramienta «tarda»; en realidad no
va a contestar nunca.

    en proceso, hilo principal    3,20 s   OK
    en proceso, hilo trabajador   2,90 s   OK
    por servidor MCP            > 600 s   sin respuesta, ficheros escritos

## Impact

**Crítico: inutiliza el carril guiado por MCP.** `confirm_and_estimate` es la
herramienta que se usa en cada iteración, y todas registran guion. Cada llamada
cuelga el servidor para siempre.

Lo que lo hace peor que un fallo normal:

* **Miente por omisión.** Los artefactos quedan en disco, así que el estado del
  caso avanza mientras el analista ve una llamada que no responde. En una sesión
  real se dio por rechazada una llamada cuyo modelo **sí se había estimado y
  registrado**; el guion quedó con una entrada que nadie sabía que existía.
* **No hay error que rastrear.** Sin traza, sin código de salida, sin aviso.
* **Sólo aparece cruzando el servidor.** En proceso —incluso en un hilo
  trabajador, que es la condición que impone FastMCP— la misma llamada tarda
  3 s. Las pruebas que desenvuelven el `@mcp.tool()` no lo ven. Es la misma
  clase de defecto que BUG-0112.
* **`guided_identification` sí responde**, porque no registra guion. Eso
  despista: el servidor parece sano.

## Reproduction

    cd bugs/BUG-0114-repro
    python repro.py

Levanta el servidor con `faulthandler.dump_traceback_later(75)`, lanza una
llamada a `confirm_and_estimate` y vuelca las pilas de todos los hilos mientras
está colgado.

Salida observada (art 0.2.0, Python 3.12.10, Windows 11):

    [  6.90s OUT] respuesta JSON id=1  (35.065 B)
    [ 13.01s ERR] Processing request of type CallToolRequest
    [ 75.06s ERR] Timeout (0:01:15)!
    ...
      File "...\Lib\threading.py", line 1169 in _wait_for_tstate_lock
      File "...\Lib\threading.py", line 1149 in join
      File "...\Lib\subprocess.py", line 1628 in _communicate
      File "...\Lib\subprocess.py", line 1209 in communicate
      File "...\Lib\subprocess.py", line 559 in run
      File "...\art\guion.py", line 1022 in _git
      File "...\art\guion.py", line 1027 in version_instrumento
      File "...\art\mcp_server.py", line 5010 in _version_instr
      File "...\art\mcp_server.py", line 5130 in _record_to_guion
      File "...\art\mcp_server.py", line 5523 in confirm_and_estimate
      ...
    ficheros escritos: ['P.inp', 'P.out', 'P.pre']

Nótese la última línea: **los tres artefactos están escritos.** El cuelgue es
posterior a todo el trabajo útil.

Descartados por experimento antes de llegar aquí, y conviene que consten para
que nadie los vuelva a recorrer:

* **no es el motor** — `m.fit()` tarda 0,01 s; la rueda C está en uso;
* **no es matplotlib** — la figura tarda 0,14 s;
* **no es Dropbox ni el antivirus** — escribir 600 KB en la carpeta del caso
  tarda 0,01 s, igual que en disco local;
* **no es el tamaño de la respuesta** — 148 KB, y `guided_identification`
  devuelve 144 KB por el mismo canal sin problema;
* **no es corrupción de stdout** — 0 líneas no-JSON en el canal del protocolo;
* **no es el hilo ni el backend GUI** — en hilo trabajador con `tkagg` tarda
  2,90 s.

## Root cause

`src/art/guion.py:1020`

    def _git(*args, tiempo=3):
        try:
            return subprocess.run(["git", "-C", raiz, *args], capture_output=True,
                                  text=True, timeout=tiempo).stdout.strip()
        except Exception:
            return ""

Hay un `timeout=3`, y **no acota**. Es el comportamiento documentado de
`subprocess.run`: cuando el plazo salta, mata al hijo y llama a
`communicate()` **otra vez y sin plazo** para vaciar las tuberías. Si git dejó
un nieto vivo con el extremo de escritura abierto —un ayudante de credenciales,
un paginador—, matar al hijo no cierra esa tubería, y el segundo
`communicate()` espera para siempre. La pila lo enseña exactamente:
`run → communicate → _communicate → join → _wait_for_tstate_lock`.

Agravante que sólo se da bajo servidor: el hijo **hereda el `stdin` del
proceso**, que en un servidor stdio es la tubería del protocolo y no se cierra
nunca. Cualquier git que decida leer de ahí se queda esperando, y encima
compite por el canal de entrada del servidor.

Que el repositorio esté en Dropbox añade probabilidad —`git status
--porcelain` sobre un árbol sincronizado es lento y puede tropezar con
bloqueos— pero no es la causa: la causa es que el plazo no acota.

## Fix

Aplicado en el árbol de fuentes:

    pr = subprocess.Popen(
        ["git", "-C", raiz, *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0",
             "GIT_OPTIONAL_LOCKS": "0", "GIT_PAGER": "cat"},
    )
    salida, _ = pr.communicate(timeout=tiempo)
    return (salida or "").strip()
    # y en el except: pr.kill(); pr.stdout.close(); return ""   <- NO re-esperar

Tres cambios, y los tres hacen falta:

1. **`stdin=DEVNULL`** — el hijo deja de heredar la tubería del protocolo.
2. **git en modo no interactivo** — `GIT_TERMINAL_PROMPT=0` mata la petición de
   credenciales, `GIT_OPTIONAL_LOCKS=0` evita que `status` tome bloqueos,
   `GIT_PAGER=cat` descarta el paginador.
3. **Tras el plazo se ABANDONA la tubería** en vez de volver a esperarla, que
   es lo que hace `subprocess.run` y lo que cuelga.

El criterio de fondo: **saber la versión del instrumento es un adorno del
registro y no puede costar la sesión.** Cualquier consulta a un programa
externo desde dentro de una herramienta MCP tiene que ser acotada de verdad o
no estar.

### Conviene revisar el resto

`_git` es el caso encontrado, no necesariamente el único. Merece un repaso a
todas las llamadas a `subprocess` del paquete con el mismo criterio: `stdin`
cerrado y plazo que acote de verdad.

## Validation

Medido con el mismo cliente stdio mínimo, mismo comando de servidor, misma
llamada:

    antes del arreglo    > 600 s   sin respuesta
    despues del arreglo    2,89 s  MA(1)   ·   2,50 s  AR(1)

* El repro debe terminar **sin volcado de pilas**: la respuesta JSON id=2 debe
  salir antes de los 75 s.
* Prueba de regresión: `version_instrumento()` debe seguir devolviendo
  `art X.Y.Z @sha[+sucio]` en un repositorio normal, y `art X.Y.Z` a secas
  donde no haya git — sin colgarse en ninguno de los dos casos.
* Y la prueba que de verdad cierra la familia: ejercitar `confirm_and_estimate`
  **cruzando el servidor**, no desenvolviendo el decorador. Ni éste ni BUG-0112
  eran visibles por dentro.

---

## Cierre (2026-09-08)

`stdin=DEVNULL`, git no interactivo (`GIT_TERMINAL_PROMPT=0`,
`GIT_OPTIONAL_LOCKS=0`, `GIT_PAGER=cat`) y, tras el plazo, se mata y se
**abandona** la tubería en vez de volver a esperarla.

El repro original era un volcado de pilas con tres rutas absolutas de Windows:
sirvió para LOCALIZAR el defecto —lo hizo, con `faulthandler` sobre el servidor
colgado— pero no corría en ninguna otra máquina. **Reescrito portátil**: pone en
el PATH un `git` falso que escupe algo, deja un nieto agarrado a la tubería y se
va, que es exactamente la forma del fallo. Con el defecto no vuelve; con el
arreglo vuelve en 3,0 s.

Saber la versión del instrumento es un adorno del registro. No puede costar la
sesión.
