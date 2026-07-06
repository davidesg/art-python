# ATSW — estado v1 y próximos pasos

**ATSW = A Time Series Workshop / ART Time Series Workshop.**
Suite Box-Jenkins-Treadway para series temporales univariantes, con servidor MCP
para operarla con un LLM. Estado a jun-2026: **v1 publicada en PyPI producción**
(`pip install atsw` funciona end-to-end) y validada previamente en TestPyPI.
Todo en commits locales (sin push a GitHub, por preferencia).

## Componentes y versiones

| Paquete | Versión | Repo | Rol |
|---------|---------|------|-----|
| `fue`         | 0.1.4 | `atws/fue/fue`     | estimación ML exacta (ARMAX + funciones de transferencia) + FUF (previsión); motor C (cffi) + fallback puro-Python |
| `pyfug`       | 2.0.0 | `atws/fug/pyfug`  | gráficos de alta definición para análisis de series temporales |
| `art-tseries` | 0.1.1 | `ART/art-python`  | construcción de modelos, diagnosis, contrastes + **servidor MCP** (`art-mcp`) |
| `atsw`        | 1.0.2 | `ART/art-python/atsw-suite` | meta-paquete paraguas (sin código): `pip install atsw` → toda la suite |

Grafo: `atsw` → `fue>=0.1.4` + `pyfug>=2.0` + `art-tseries>=0.1.1`;
`art-tseries` → `fue` + `pyfug` + numpy/scipy/matplotlib/statsmodels/mcp.
FUF vive dentro de `fue` (`load_fuf`/`forecast_fuf`/`write_fuf`, script `fuf`).

## Hecho

- **PyPI producción — release de bugfix (06-jul-2026):** **fue 0.1.4**, **art-tseries 0.1.1**,
  **atsw 1.0.2** (pyfug 2.0.0 sin cambios). Correcciones acumuladas: normalización de
  invertibilidad del MA (fue `cast_us.normalize_ma_invertibility` en `fit()`), writer de secciones
  f-fixed en formato del lector C, y el workflow de **estacionalidad estocástica** de ART
  (`meg_frequency`, reformulación con testigo `with_witness`, arranques YW/HR, factorización AR
  `roots.py`, guards de baseline, criticos DCD_f). Ramas `fue/ma-invertibility-normalization` y
  `art/meg-stochastic-seasonality` **mergeadas a master**. Orden fue → art-tseries → atsw.
  - Validado en **TestPyPI** (venv limpio, resolución de deps, `art-mcp` OK) y en **producción**
    (`pip install --no-cache-dir atsw==1.0.2` → fue 0.1.4 compila wheel, `import fue,pyfug,art` +
    entry point OK). Suite ART: **435 passed, 21 skipped**.
  - https://pypi.org/project/fue/0.1.4/ · /art-tseries/0.1.1/ · /atsw/1.0.2/
- **PyPI producción (20-jun-2026):** los 4 paquetes publicados —
  fue 0.1.3 (solo sdist; el wheel `linux_x86_64` lo rechaza PyPI),
  pyfug 2.0.0, art-tseries 0.1.0, atsw 1.0.1 (1.0.0 inicial; 1.0.1 re-publicado
  con el README de difusión = quickstart + Background en la página de PyPI).
  Subida en orden de dependencias con `twine` (`[pypi]` de `~/.pypirc`);
  `twine check` PASSED en todos.
  - https://pypi.org/project/fue/0.1.3/ · /pyfug/2.0.0/ · /art-tseries/0.1.0/ · /atsw/
  - **Validación en venv limpio (índice solo-producción):** `pip install atsw`
    resuelve e instala la suite + deps, compila `fue` desde sdist,
    `import fue, pyfug, art` OK, entry point `art-mcp` (`art.mcp_server:main`)
    carga el server FastMCP.
- **TestPyPI:** los 4 paquetes subidos y validados previamente (paso intermedio).
- Empaquetado coherente (deps, licencia GPL-2.0, READMEs); docs IA-friendly
  (`AGENTS.md`, `llms.txt`, `docs/TOOLS.md`, `docs/ARCHITECTURE.md`,
  `docs/PUBLISHING.md`).
- Suite de tests: 408 passed.

## Próximos pasos (roadmap)

1. **Regenerar el token de TestPyPI.** Una parte se expuso en un error de parseo
   durante la subida; revócalo en https://test.pypi.org/manage/account/token/ y
   crea uno nuevo (en `~/.pypirc` `[testpypi]`, en una sola línea). Bajo riesgo
   (TestPyPI), pero higiene. El token de PyPI producción no se tocó ni expuso.

2. **Wheels manylinux para fue (CI).** `fue` tiene extensión C; en producción
   solo hay **sdist** (compila en instalación si hay GSL, o usa el fallback
   puro-Python). Para wheels binarios multiplataforma (instalación sin compilar)
   hace falta **GitHub Actions + cibuildwheel** (`[tool.cibuildwheel]` ya está en
   `fue/pyproject.toml`). No bloquea la difusión; es optimización de instalación.

3. **Difusión entre colegas.** Ya instalable con `pip install atsw`. Pendiente:
   quickstart en español (instalar → `claude mcp add art -- art-mcp` → analizar
   una serie), demo reproducible (`demo_chile_ipc.py`, `CASE_STUDIES.md`) y
   mensaje de anuncio. Comunicar los dos modos de uso: con Claude (MCP) y como
   librería/CLI Python pura.

4. **Validación en venv 100% nativo.** Requiere `apt install python3.12-venv`
   (no instalado; se usó `virtualenv` para la validación, que pasó).

5. **Limpieza de casos.** `cases/CPI_USA|IPC_DE|IPC_FR/` son outputs reales de
   pruebas en otras series; decidir si se curan como casos de estudio versionados
   o se mueven a `cases/<serie>/work/` (gitignored).

6. **Release de los fixes del motor C y del writer (jul-2026).** Se corrigieron
   bugs que rompían los modelos MEG híbridos con testigo `ma_f`: (a) `tensor()`
   de-NR en `fue-1.13.1` y `fuf-1.08.1` había perdido el offset `t -= nrl` →
   double-free con índice de fila negativo (`gamwa = tensor(-q+1,0,…)`, q>0);
   (b) doble `fclose(inputv)` en el `fue-1.12.03` antiguo; (c) `report.py`
   `_ffixed_body` escribía las secciones f-fixed en un formato que el reader C no
   acepta (→ previsión corrupta) y además rompía el round-trip del parser fuf.
   Commiteados **en local**: `fue-1.13.1` `b3e7dfd`, `fuf-1.08.1` `6f4c35d`, `fue`
   `6f0a4f0`. **Pendiente de publicar cuando se libere versión estable:**
   - **PyPI:** nueva versión del paquete `fue` (lleva el fix de `report.py`
     `_ffixed_body`); revisar si `atsw`/`art-tseries` necesitan bump por dependencia.
   - **GitHub:** actualizar los **programas C** (`fue`, `fuf`) con los parches del
     `tensor()` (y el del `fclose`) al hacer el push a la versión estable.
   Verificado: C y Python coinciden al dígito en estimación (logelf −11.9928042176)
   y previsión (`[82.1212, 82.2543, 82.8643, 83.9145]`); binarios parcheados ya
   instalados en `/usr/local/bin`.

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
