# ATSW MCP servers en DeepSeek TUI

La suite ATSW incluye tres servidores MCP independientes que siguen la
metodologia Box-Jenkins-Treadway. Estan optimizados para Claude Code, pero
funcionan con cualquier cliente MCP compatible, incluido DeepSeek TUI.

## Los tres servidores

| Servidor | Comando | Paquete | Rol |
|---|---|---|---|
| `art` | `art-mcp` | `art-tseries` | ARIMA univariante + intervenciones (motor: `fue`) |
| `mtram` | `mtram` | `drtran` | Funciones de transferencia y redes (motor: `drtran`) |
| `sima` | `sima` | `drvarma` | VARMA simultaneo (motor: `drvarma`) |

## Instalacion

### 1. Instalar la suite completa

```bash
pip install atsw
```

Esto instala `art-tseries`, `drtran`, `drvarma`, `fue` y `pyfug` con sus
dependencias y registra los tres comandos `art-mcp`, `mtram` y `sima` en
`~/.local/bin/`.

### 2. Configurar DeepSeek TUI

Editar `~/.deepseek/config.toml` y anadir:

```toml
[mcp_servers.art]
command = "art-mcp"

[mcp_servers.mtram]
command = "mtram"

[mcp_servers.sima]
command = "sima"
```

Alternativamente, editar `~/.deepseek/mcp.json`:

```json
{
  "mcpServers": {
    "art":   { "command": "art-mcp", "args": [] },
    "mtram": { "command": "mtram",   "args": [] },
    "sima":  { "command": "sima",    "args": [] }
  }
}
```

### 3. Reiniciar DeepSeek TUI

Cerrar y volver a abrir la sesion. Los tres servidores apareceran como
herramientas disponibles en el espacio de trabajo.

## Verificacion

Comprobar que los tres comandos estan en PATH:

```bash
which art-mcp mtram sima
# ~/.local/bin/art-mcp
# ~/.local/bin/mtram
# ~/.local/bin/sima
```

Verificar que arrancan (quedan a la escucha en stdin, Ctrl+C para salir):

```bash
art-mcp   # Muestra warnings si los hay, pero debe arrancar
mtram     # Sin salida = correcto
sima      # Sin salida = correcto
```

## Uso de la escalera ATSW

Los tres servidores forman una escalera metodologica:

1. **`art`** — Construye cada serie por separado (identificacion, estimacion,
   diagnostico). Escribe archivos `.pre` con los parametros estimados.
2. **`mtram`** — Toma los `.pre` de `art` y modela como X mueve a Y (funciones
   de transferencia, redes dirigidas). Declara y testea exogeneidad.
3. **`sima`** — Modela todo contra todo (VARMA simultaneo). `mtram` entrega a
   `sima` cuando la red que propone contiene un ciclo.

## Notas

- El metapaquete `atsw` incluye `atsw-mcp`, un instalador especifico para
  Claude Code. **No es necesario para DeepSeek TUI**: la configuracion manual
  de arriba es suficiente.
- Si usas un virtualenv, asegurate de que los comandos `art-mcp`, `mtram` y
  `sima` esten en el PATH que ve DeepSeek TUI. Usa rutas absolutas en
  `config.toml` si hay ambiguedad:
  ```toml
  [mcp_servers.art]
  command = "/ruta/al/venv/bin/art-mcp"
  ```
- El `mcp.json` de DeepSeek TUI soporta `enabled_tools` y `disabled_tools` para
  filtrar herramientas por servidor si alguna no es necesaria.
