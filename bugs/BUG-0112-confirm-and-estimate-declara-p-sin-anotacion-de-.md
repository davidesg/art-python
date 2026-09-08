---
id: BUG-0112
title: confirm_and_estimate declara `p` sin anotación de tipo — por MCP llega como cadena y revienta en _arma_starts, así que no se puede especificar orden AR desde el servidor
status: fixed
severity: critical
component: mcp-tools
found_in: 0.2.0
fixed_in: 0.2.1
reported: 2026-09-08
reporter: David
tags:
  - mcp
  - tipos
  - arma
references:
  - BUG-0103
---

## Summary

`confirm_and_estimate` declara `p=0` **sin anotación de tipo**
(`mcp_server.py:5177`). FastMCP, a falta de anotación, publica el parámetro
como `"type": "string"`. Un cliente conforme al esquema envía entonces una
**cadena**, y `art.pipeline._arma_starts` la compara con un entero:

    ar = (_yw_ar(resid, p) if p > 0 else []) or [0.0] * p
    TypeError: '>' not supported between instances of 'str' and 'int'

Es el único parámetro sin anotar de toda la superficie MCP: sus hermanos `q`,
`P`, `Q`, `d`, `D` salen como `integer`.

    p  -> type='string'     default=0
    q  -> type='integer'    default=1
    P  -> type='integer'    default=0
    Q  -> type='integer'    default=0
    d  -> type='integer'    default=1
    D  -> type='integer'    default=0

El valor por defecto sí es un entero, así que **omitir `p` funciona**. El fallo
aparece únicamente cuando el llamante lo pasa — que es lo que hace el carril
guiado en cuanto hay un orden AR que fijar.

### Y por el otro camino no revienta: MIENTE

Esto es lo más grave, y no se vio al principio porque el síntoma ruidoso tapaba
al callado. Los dos modos de `confirm_and_estimate` tratan `p` de forma
distinta:

* **modo incremental** (`base_pre_path=<.pre>`) → `_build_arma_on_model` →
  `_arma_starts` → `p > 0` → **TypeError**. Ruidoso, se ve enseguida.
* **modo fresco** → `_make_model` → `ordenes_ar(p)`, que hace
  `isinstance(p, int)` y, si no lo es, **itera**. Una cadena es iterable:

        ordenes_ar(12)    = [12]      un operador AR(12)
        ordenes_ar("12")  = [1, 2]    DOS factores, de órdenes 1 y 2

  **Pedir un AR(12) por MCP no daba error: estimaba otro modelo.** Sin aviso,
  sin traza, con su tabla de parámetros y su diagnosis de aspecto impecable —
  y con los grados de libertad, el AIC y la lectura de los factores mal.

Un fallo ruidoso cuesta una sesión de rastreo; éste puede no descubrirse nunca.
Y afecta justo a la forma factorizada que BUG-0103 acaba de exponer, que es
donde los órdenes de dos cifras y las listas tienen sentido.

## Impact

**Crítico para el carril guiado por MCP.** `confirm_and_estimate` es la
herramienta principal de estimación, y el nodo ARMA existe precisamente para
fijar `p` y `q`. Con este defecto:

* se puede estimar el modelo de armónicos (`p` omitido, por defecto 0);
* **no se puede añadir ningún orden AR** — ni `p=1`, ni la forma factorizada
  `p=[1,1,2,2]` que BUG-0103 acaba de exponer, que es la que la escuela usa
  para leer cada factor con su `d ± SE` y su `periodo ± SE`.

O sea que el carril guiado, por servidor, se detiene en el primer modelo con
dinámica regular. Es el nodo central de la metodología.

**Por qué no se había visto:** casi todas las pruebas —y las cinco de la
sesión de Windows— llaman a las funciones **desenvolviendo el `@mcp.tool()`**.
Por ese camino `p` viaja como entero de Python y nada falla. El defecto vive
exactamente en la frontera que ese estilo de prueba no cruza. Conviene tenerlo
presente más allá de este informe: hay una clase de defectos que sólo existe
cruzando el servidor.

## Reproduction

    cd bugs/BUG-0112-repro
    python repro.py

Instantáneo y determinista: **no estima nada**. Levanta el servidor sólo para
leer el esquema publicado, y luego ejercita el punto de impacto directamente.

Salida observada (art 0.2.0, Python 3.12.10, Windows 11):

    1 · Parametros SIN anotacion de tipo en la superficie MCP
      confirm_and_estimate.p = 0  (int)
      total: 1

    2 · Lo que el servidor PUBLICA para confirm_and_estimate
      p  -> type='string'     default=0
      q  -> type='integer'    default=1
      ...

    3 · El punto de impacto — pipeline._arma_starts
      con p=1 (entero, como llega por guion):
          OK -> ar=[-0.112]
      con p="1" (cadena, como llega por MCP):
          TypeError: '>' not supported between instances of 'str' and 'int'

    esquema publica `p` como string : SI
    entero funciona en _arma_starts : SI
    cadena rompe en _arma_starts    : SI

El repro **no** hace la llamada de extremo a extremo a propósito: estima de
verdad y tarda minutos, lo que lo convertiría en algo que nadie ejecuta. El
fallo está en la frontera, y el repro ejercita el sitio exacto donde estalla.

### Traza real observada por MCP

Del uso normal, carril guiado, modo incremental
(`base_pre_path=<…m00.pre>`, `estimate_mu=True`, `p=0`, `q=0`):

    ❌ Error: Traceback (most recent call last):
      File "...\art\mcp_server.py", line 5342, in confirm_and_estimate
        m = _build_arma_on_model(m_base, p=p, q=q, P=P, Q=Q,
      File "...\art\pipeline.py", line 673, in _build_arma_on_model
        ar_i, ma_i, ars_i, mas_i = _arma_starts(resid, p, q, P, Q, s_freq)
      File "...\art\pipeline.py", line 565, in _arma_starts
        ar   = (_yw_ar(resid, p)      if p > 0 else []) or [0.0] * p
    TypeError: '>' not supported between instances of 'str' and 'int'

Nótese que ahí `p` valía **0**: basta con pasarlo, sea cual sea su valor.

## Root cause

`src/art/mcp_server.py:5177`

    def confirm_and_estimate(inp_path: str, output_path: str,
                             lam: float = 0.0, d: int = 1, D: int = 0,
                             p=0, q: int = 1,          # <- `p` sin anotar
                             ...

La ausencia de anotación es probablemente deliberada: el docstring documenta
que `p` admite **un entero o una lista de órdenes por factor** (`[1,1,2,2]`,
la forma factorizada de BUG-0103), y no hay una anotación obvia para eso. Pero
dejarlo sin anotar no lo hace polimórfico — hace que FastMCP elija `string`,
que es el único tipo que ninguna de las dos formas es.

Y aguas abajo nadie normaliza: `_arma_starts` y `_build_arma_on_model` suponen
un entero (o una secuencia) sin comprobarlo.

## Fix

Dos partes, y las dos hacen falta.

**1 · Anotar el parámetro con el tipo que realmente admite:**

    p: int | list[int] = 0

Con eso FastMCP publica un `anyOf` que acepta las dos formas documentadas, y el
cliente deja de tener que adivinar.

**2 · Normalizar en la entrada de `confirm_and_estimate`**, porque una
anotación no impide que llegue basura desde un cliente laxo y porque el
docstring promete tolerancia:

    def _orden_ar(p):
        """Acepta 3, "3", [1,1,2] o "[1,1,2]" y devuelve int o list[int]."""
        if isinstance(p, str):
            p = p.strip()
            p = json.loads(p) if p.startswith("[") else int(p)
        if isinstance(p, (list, tuple)):
            return [int(x) for x in p]
        return int(p)

**3 · Cerrar el camino silencioso en `pipeline.ordenes_ar`**, que es el que
importa de verdad. No basta con normalizar en la herramienta: mientras
`ordenes_ar` acepte iterar una cadena, cualquier otro llamante puede volver a
descomponer un `"12"` en dos factores sin que nadie se entere.

    if isinstance(p, str):
        p = p.strip()
        p = json.loads(p) if p.startswith("[") else int(p)

**4 · Guarda barata en `_arma_starts`** que falle **diciendo qué pasa**, en vez
de por una comparación — el `TypeError` original no menciona ni el parámetro ni
la herramienta:

    for _nombre, _v in (("p", p), ("q", q), ("P", P), ("Q", Q)):
        if not isinstance(_v, (int, np.integer)) or isinstance(_v, bool):
            raise TypeError(f"orden {_nombre} debe ser un entero, "
                            f"recibido {type(_v).__name__}: {_v!r}")

## Validation

* `bugs/BUG-0112-repro/repro.py` debe salir con dos líneas del veredicto
  invertidas: el esquema ya no publica `p` como `string` y la cadena ya no
  rompe.
* Prueba de la superficie: **recorrer todas las herramientas y afirmar que
  ningún parámetro queda sin anotación**. Son tres líneas con
  `inspect.signature` y cierra la familia entera, no sólo este caso. El censo
  de hoy da exactamente uno.
* Prueba de extremo a extremo, cruzando el servidor de verdad —no
  desenvolviendo el decorador—: `confirm_and_estimate` con `p=1` y con
  `p=[1,1,2,2]` sobre un `.pre` ya ajustado, y que las dos estimen. Es la única
  forma de que esta clase de defecto no vuelva.

---

## Cierre (2026-09-08)

Anotación `p: int | list[int]`, normalizador que acepta las cinco formas
documentadas, y `_arma_starts` fallando **con el nombre del parámetro** en vez de
por una comparación.

**La prueba que importa no es de `p`.** Es
`test_ningun_parametro_se_publica_como_string_por_no_estar_anotado`: recorre el
esquema que el servidor PUBLICA —`mcp.list_tools()`, lo que ve un cliente— y
exige que ningún parámetro con defecto numérico salga como cadena. Cierra la
clase, no el caso: un parámetro que se olvide de anotar mañana vuelve a caer ahí.

Y una para el camino callado, que era el peligroso: `ordenes_ar("12")` daba
`[1, 2]` —dos factores— en vez de `[12]`, un AR(12). Sin error y sin aviso.
