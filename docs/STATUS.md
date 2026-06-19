# ATSW — estado v1 y próximos pasos

**ATSW = A Time Series Workshop / ART Time Series Workshop.**
Suite Box-Jenkins-Treadway para series temporales univariantes, con servidor MCP
para operarla con un LLM. Estado a jun-2026: **v1 funcional, publicada y validada
en TestPyPI**. Todo en commits locales (sin push a GitHub, por preferencia).

## Componentes y versiones

| Paquete | Versión | Repo | Rol |
|---------|---------|------|-----|
| `fue`         | 0.1.3 | `atws/fue/fue`     | estimación ML exacta (ARMAX + funciones de transferencia) + FUF (previsión); motor C (cffi) + fallback puro-Python |
| `pyfug`       | 2.0.0 | `atws/fug/pyfug`  | gráficos de alta definición para análisis de series temporales |
| `art-tseries` | 0.1.0 | `ART/art-python`  | construcción de modelos, diagnosis, contrastes + **servidor MCP** (`art-mcp`) |
| `atsw`        | 1.0.0 | `ART/art-python/atsw-suite` | meta-paquete paraguas (sin código): `pip install atsw` → toda la suite |

Grafo: `atsw` → `fue>=0.1.3` + `pyfug>=2.0` + `art-tseries>=0.1.0`;
`art-tseries` → `fue` + `pyfug` + numpy/scipy/matplotlib/statsmodels/mcp.
FUF vive dentro de `fue` (`load_fuf`/`forecast_fuf`/`write_fuf`, script `fuf`).

## Hecho

- **TestPyPI:** los 4 paquetes subidos
  (fue 0.1.3, pyfug 2.0.0, art-tseries 0.1.0, atsw 1.0.0).
- **Validación en venv limpio** (`pip install atsw` desde TestPyPI): instala toda
  la suite + dependencias; `art-mcp` arranca con 32 tools; smoke funcional
  (estimación + `model_equation`) OK.
- Empaquetado coherente (deps, licencia GPL-2.0, READMEs); docs IA-friendly
  (`AGENTS.md`, `llms.txt`, `docs/TOOLS.md`, `docs/ARCHITECTURE.md`,
  `docs/PUBLISHING.md`).
- Suite de tests: 408 passed.
- Nombre `atsw` libre también en **PyPI producción** (reservable al promocionar).

## Próximos pasos (roadmap)

1. **Regenerar el token de TestPyPI.** Una parte se expuso en un error de parseo
   durante la subida; revócalo en https://test.pypi.org/manage/account/token/ y
   crea uno nuevo (en `~/.pypirc` `[testpypi]`, en una sola línea). Bajo riesgo
   (TestPyPI), pero higiene. El token de PyPI producción no se tocó ni expuso.

2. **Wheels manylinux para fue (CI).** `fue` tiene extensión C; en local solo se
   genera un wheel `linux_x86_64` no portable (lo rechaza PyPI). Para producción
   hacen falta wheels multiplataforma vía **GitHub Actions + cibuildwheel**
   (`[tool.cibuildwheel]` ya está en `fue/pyproject.toml`). Mientras tanto el
   sdist funciona (compila en instalación si hay GSL, o usa el fallback puro-Python).

3. **Promoción a PyPI producción** (`docs/PUBLISHING.md`, orden
   fue→pyfug→art-tseries→atsw). Producción es **irreversible** por versión;
   validar primero en TestPyPI (hecho). Subir fue 0.1.3 a producción (allí está
   0.1.2) para que `art-tseries` (que exige `fue>=0.1.3`) resuelva.

4. **Validación en venv 100% nativo.** Requiere `apt install python3.12-venv`
   (no instalado; se usó `virtualenv` para la validación, que pasó).

5. **Limpieza de casos.** `cases/CPI_USA|IPC_DE|IPC_FR/` son outputs reales de
   pruebas en otras series; decidir si se curan como casos de estudio versionados
   o se mueven a `cases/<serie>/work/` (gitignored).

## Deuda / pendientes funcionales conocidos

- **Entrega de la ecuación en el prompt:** Claude tiende a reformatear la ecuación
  a su propia tabla en vez de mostrar el bloque autoritativo. Mitigado con
  `_equation_for_prompt` (bloque marcado "verbatim") + regla anti-tabla en las
  instrucciones, pero depende del comportamiento del LLM. Plan B definitivo si
  reincide: renderizar la ecuación como imagen (estudiado, revertido a petición).
- **CI/CD** no configurado (publicación manual por ahora).

## Cómo usar (usuario final)

```bash
pip install atsw                 # cuando esté en PyPI producción
claude mcp add art -- art-mcp    # conectar el servidor MCP
```
Doc operativa para agentes: `AGENTS.md`, `llms.txt`, `docs/TOOLS.md`.
Diseño y filosofía: `docs/ARCHITECTURE.md`.
