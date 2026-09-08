"""BUG-0112 — `p` de confirm_and_estimate llega como str por MCP y revienta.

`confirm_and_estimate` declara `p=0` SIN anotacion de tipo. FastMCP, sin
anotacion, publica el parametro como `"type": "string"`, asi que por el
servidor MCP llega `"1"` en vez de `1` y `art.pipeline._arma_starts` compara
`p > 0` contra un str.

El defecto es INVISIBLE llamando a las funciones directamente (desenvolviendo
el `@mcp.tool()`), que es como se prueban casi todos los demas informes: por
ahi `p` viaja como entero. Solo aparece cruzando el servidor de verdad.

    python repro.py

No necesita ficheros externos: fabrica su propia serie.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
import threading


# ── Parte 1 — el censo de anotaciones, sin levantar nada ──────────────────────

def censo_anotaciones() -> None:
    from art import mcp_server as M

    def desenvuelve(obj):
        for a in ("fn", "func", "__wrapped__"):
            if hasattr(obj, a):
                return getattr(obj, a)
        return obj

    print("=" * 72)
    print("1 · Parametros SIN anotacion de tipo en la superficie MCP")
    print("=" * 72)
    hallados = []
    for nombre in dir(M):
        if nombre.startswith("_"):
            continue
        f = desenvuelve(getattr(M, nombre))
        if not callable(f) or getattr(f, "__module__", "") != "art.mcp_server":
            continue
        try:
            sig = inspect.signature(f)
        except (TypeError, ValueError):
            continue
        for par in sig.parameters.values():
            if par.annotation is inspect.Parameter.empty:
                hallados.append((nombre, par.name, par.default))

    for tool, par, defecto in hallados:
        print(f"  {tool}.{par} = {defecto!r}  ({type(defecto).__name__})")
    print(f"\n  total: {len(hallados)}")
    print("  -> el defecto es un ENTERO, pero sin anotacion FastMCP publica string.\n")


# ── Parte 2 — cliente MCP minimo por stdio ───────────────────────────────────

class Servidor:
    """Handshake y tools/call contra art-mcp, por stdio. Sin dependencias."""

    def __init__(self):
        # `-c` en vez del ejecutable: funciona igual en Linux y en Windows y no
        # depende de que Scripts/ este en el PATH.
        self.p = subprocess.Popen(
            [sys.executable, "-c", "from art.mcp_server import main; main()"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", bufsize=1)
        self._id = 0
        self._resp: dict = {}
        self._lock = threading.Condition()
        threading.Thread(target=self._leer, daemon=True).start()
        self._peticion("initialize", {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "repro-0112", "version": "0"}})
        self._enviar({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _enviar(self, obj) -> None:
        self.p.stdin.write(json.dumps(obj) + "\n")
        self.p.stdin.flush()

    def _leer(self) -> None:
        for linea in self.p.stdout:
            linea = linea.strip()
            if not linea:
                continue
            try:
                msg = json.loads(linea)
            except ValueError:
                continue
            if "id" in msg:
                with self._lock:
                    self._resp[msg["id"]] = msg
                    self._lock.notify_all()

    def _peticion(self, metodo, params, timeout=180):
        self._id += 1
        rid = self._id
        self._enviar({"jsonrpc": "2.0", "id": rid,
                      "method": metodo, "params": params})
        with self._lock:
            if not self._lock.wait_for(lambda: rid in self._resp, timeout):
                raise TimeoutError(f"{metodo}: sin respuesta en {timeout}s")
            return self._resp.pop(rid)

    def llama_o_espera(self, tool, args, timeout):
        """Como `llama`, pero un agotamiento no tumba el repro.

        El caso de control estima de verdad y puede tardar varios minutos; los
        dos casos que demuestran el defecto fallan en milisegundos, antes de
        llegar al motor. Que el lento no concluya no invalida nada.
        """
        try:
            return self.llama(tool, args, timeout=timeout)
        except TimeoutError as e:
            return f"TIMEOUT: {e}"

    def esquema(self, tool):
        r = self._peticion("tools/list", {})
        for t in r.get("result", {}).get("tools", []):
            if t["name"] == tool:
                return t.get("inputSchema", {})
        raise KeyError(tool)

    def llama(self, tool, args, timeout=180):
        r = self._peticion("tools/call", {"name": tool, "arguments": args},
                           timeout=timeout)
        if "error" in r:                       # rechazo del validador
            return "VALIDACION: " + json.dumps(r["error"], ensure_ascii=False)
        trozos = []
        for c in r.get("result", {}).get("content", []):
            if c.get("type") == "text":
                trozos.append(c["text"])
            elif c.get("type") == "image":
                trozos.append(f"<imagen {len(c.get('data',''))} b64>")
        return "\n".join(trozos)

    def cierra(self):
        try:
            self.p.terminate()
            self.p.wait(timeout=5)
        except Exception:
            self.p.kill()


def primera_linea_util(texto, n=6):
    return "\n".join(l for l in texto.splitlines() if l.strip())[:900] if n else texto


def main() -> int:
    censo_anotaciones()

    import random
    random.seed(0)

    s = Servidor()
    try:
        esq = s.esquema("confirm_and_estimate")
        print("=" * 72)
        print("2 · Lo que el servidor PUBLICA para confirm_and_estimate")
        print("=" * 72)
        for par in ("p", "q", "P", "Q", "d", "D"):
            prop = esq.get("properties", {}).get(par, {})
            print(f"  {par:2s} -> type={prop.get('type')!r:12s} default={prop.get('default')!r}")
        publica_string = esq.get("properties", {}).get("p", {}).get("type") == "string"
        print("  -> `p` sale como string; sus hermanos, como integer.\n")

    finally:
        s.cierra()

    # ── Parte 3 — el punto de impacto, sin servidor y sin estimar ────────────
    #
    # A proposito NO se hace la llamada de extremo a extremo: estima de verdad
    # y tarda minutos, lo que convertiria el repro en algo que nadie ejecuta.
    # El fallo esta en la frontera —el tipo con que llega el parametro— y se
    # ejercita el sitio exacto donde estalla. La traza real observada por MCP
    # esta en el cuerpo del informe.

    print("=" * 72)
    print("3 · El punto de impacto — pipeline._arma_starts")
    print("=" * 72)
    from art.pipeline import _arma_starts
    resid = [random.gauss(0, 1) for _ in range(200)]

    print("  con p=1 (entero, como llega por guion):")
    try:
        ar, ma, ars, mas = _arma_starts(resid, 1, 0, 0, 0, 12)
        print(f"      OK -> ar={[round(x, 4) for x in ar]}")
        entero_ok = True
    except Exception as e:
        print(f"      {type(e).__name__}: {e}")
        entero_ok = False

    print('  con p="1" (cadena, como llega por MCP):')
    try:
        _arma_starts(resid, "1", 0, 0, 0, 12)
        print("      OK  <- el defecto ya no esta")
        cadena_rompe = False
    except TypeError as e:
        print(f"      TypeError: {e}")
        print("      en pipeline.py, `_arma_starts`:  ar = (_yw_ar(resid, p) if p > 0 ...)")
        cadena_rompe = True
    except Exception as e:
        print(f"      {type(e).__name__}: {e}  <- otra excepcion, revisar")
        cadena_rompe = False
    print()

    # ── Parte 4 — el otro camino: no revienta, MIENTE ───────────────────────
    #
    # `_make_model` normaliza con `ordenes_ar`, que hace `isinstance(p, int)` y
    # si no, ITERA. Una cadena es iterable: "12" no da error, da dos factores de
    # ordenes 1 y 2 en vez de un AR(12). Ese camino no falla: estima otro modelo
    # y no lo dice.

    print("=" * 72)
    print("4 · El camino de modelo fresco — pipeline.ordenes_ar")
    print("=" * 72)
    from art.pipeline import ordenes_ar
    silencioso = False
    for v in (12, "12"):
        try:
            o = ordenes_ar(v)
        except Exception as e:
            o = f"{type(e).__name__}: {e}"
        print(f"  ordenes_ar({v!r:6}) = {o!r}")
    try:
        silencioso = ordenes_ar("12") == [1, 2] and ordenes_ar(12) == [12]
    except Exception:
        silencioso = False
    print("  -> " + ("UN AR(12) pedido por MCP se estima como DOS factores (1 y 2),"
                     " sin aviso" if silencioso else
                     "las dos formas coinciden: normalizado"))
    print()

    # ── Parte 5 — normalizador de entrada (solo existe tras el arreglo) ──────

    print("=" * 72)
    print("5 · Normalizador de entrada (_orden_ar)")
    print("=" * 72)
    try:
        from art.mcp_server import _orden_ar
        casos = [(12, 12), ("12", 12), ("1", 1),
                 ([1, 1, 2], [1, 1, 2]), ("[1,1,2]", [1, 1, 2])]
        normaliza = True
        for entrada, esperado in casos:
            got = _orden_ar(entrada)
            ok = got == esperado
            normaliza &= ok
            print(f"  _orden_ar({entrada!r:10}) = {got!r:12} {'OK' if ok else 'MAL'}")
    except ImportError:
        normaliza = False
        print("  no existe — el arreglo no esta aplicado")
    print()

    arreglado = (not publica_string) and (not silencioso) and normaliza

    print("=" * 72)
    print("VEREDICTO — " + ("ARREGLADO" if arreglado else "DEFECTO PRESENTE"))
    print("=" * 72)
    print(f"  esquema publica `p` como string     : {'SI' if publica_string else 'NO'}")
    print(f"  entero funciona en _arma_starts     : {'SI' if entero_ok else 'NO'}")
    print(f"  cadena rechazada en _arma_starts    : {'SI' if cadena_rompe else 'NO'}")
    print(f"  ordenes_ar interpreta mal la cadena : {'SI' if silencioso else 'NO'}")
    print(f"  _orden_ar normaliza las 5 formas    : {'SI' if normaliza else 'NO'}")
    print()
    if arreglado:
        print("  El esquema pide int|list[int], el normalizador acepta las dos")
        print("  formas documentadas, y _arma_starts rechaza lo que no sea entero")
        print("  DICIENDO cual es el parametro — no por una comparacion.")
    else:
        print("  Un cliente MCP no puede fijar el orden AR:")
        print("    modo incremental -> TypeError en _arma_starts")
        print("    modo fresco      -> estima OTRO modelo, en silencio")
    return 0 if arreglado else 1


if __name__ == "__main__":
    sys.exit(main())
