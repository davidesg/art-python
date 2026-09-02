# Publicación de la suite ATSW en PyPI

**Reescrito el 2026-09-02.** La versión anterior describía subidas manuales con
`twine`, y **el procedimiento real es por CI desde hace tiempo**: cada paquete
tiene su workflow, se dispara con una etiqueta, y publica con *trusted
publishing* (OIDC) sin credenciales en ninguna máquina.

Se detectó al preparar art-tseries 0.1.12: el documento llevó a subir a TestPyPI
a mano, que no es dañino pero **no valida el camino real** — se salta el smoke
test que el workflow hace antes de publicar.

---

## 0. El mapa

| paquete | repositorio | workflow | etiqueta que dispara | notas |
|---|---|---|---|---|
| **fue** | `atws/fue/fue` | `.github/workflows/wheels.yml` | `v*` | extensión C → **cibuildwheel**, ruedas por plataforma |
| **pyfug** | `atws/fug/pyfug` | `.github/workflows/publish.yml` | — | puro Python |
| **art-tseries** | `ART/art-python` | `.github/workflows/publish-art.yml` | `art-v*` | **con smoke test** antes de publicar |
| **atsw** | `ART/art-python` (`atsw-suite/`) | `.github/workflows/publish-atsw.yml` | `atsw-v*` | meta-paquete |

**Orden de publicación** (respeta dependencias): `fue → pyfug → art-tseries →
atsw`. Sólo hace falta el paquete que cambia; los demás se quedan donde están.

## 1. Validar SIN publicar — `workflow_dispatch`

Los cuatro workflows tienen `workflow_dispatch`, y el job que publica está
condicionado a la etiqueta:

```yaml
if: startsWith(github.ref, 'refs/tags/art-v')
```

Así que **lanzarlo a mano construye y valida, y no publica nada**. Es la
comprobación previa correcta:

```bash
gh workflow run publish-art.yml --ref <rama>
gh run watch                     # o: gh run list --workflow=publish-art.yml
```

Qué comprueba el job `build` de art-tseries, y por qué importa:

* construye sdist y rueda;
* **instala la rueda recién construida en un entorno limpio**, la importa, y
  levanta el servidor MCP comprobando que expone ≥ 30 herramientas.

Ese paso no existía. Su ausencia es exactamente cómo se publicó 0.1.3 rota:
declaraba `mcp>=1.0` sin cota, `mcp 2.0.0` quitó `mcp.server.fastmcp`, y
`art-mcp` no podía importarse en un entorno limpio. `python -m build` no lo
habría cazado, porque **el empaquetado estaba bien; lo que fallaba era la
resolución**.

## 2. Publicar — etiqueta y empujón

```bash
git tag art-v0.1.12
git push origin art-v0.1.12
```

El workflow construye, hace el smoke test, y sólo entonces publica con OIDC. Si
el smoke test falla, la publicación **se detiene**, que es lo correcto: mejor una
versión bloqueada que una publicada que nadie puede instalar.

Para `fue` la etiqueta es `v*`; para `atsw`, `atsw-v*`.

## 3. TestPyPI: cuándo sí y cuándo no

TestPyPI sigue sirviendo para probar **la resolución de dependencias desde cero**
en una máquina limpia, que el smoke test del CI no cubre del todo:

```bash
python -m twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ art-tseries==X.Y.Z
```

El `--extra-index-url` no es opcional: TestPyPI **no tiene las versiones actuales
de las dependencias** —a 2026-09-02 tiene `fue` hasta 0.1.4 mientras art-tseries
exige `>=0.1.10`—, así que sin él la instalación falla por una razón que no tiene
que ver con el paquete que se prueba.

Y una advertencia que cuesta cara: **una versión subida a TestPyPI no se puede
reemplazar**. Si se sube 0.1.12 y luego hay que corregir algo, ese número queda
quemado allí. Por eso la validación normal es el `workflow_dispatch`, y TestPyPI
se reserva para cuando de verdad se quiere probar la instalación.

## 4. El meta-paquete `atsw`

`atsw-suite/pyproject.toml` **fija las versiones mínimas** de los tres paquetes.
Publicar una versión nueva de `art-tseries` no obliga a tocar `atsw`, pero si se
quiere que la suite arrastre los arreglos hay que:

1. subir el pin (`art-tseries>=X.Y.Z`),
2. versionar `atsw`,
3. etiquetar `atsw-v*`.

Los comentarios de ese `pyproject` explican por qué cada cota mínima es la que
es. **No las subas sin leerlos**: varias no son mantenimiento sino la frontera de
un fallo concreto.

## Checklist previo a cada publicación

- [ ] Versión subida en `pyproject` (y en `__version__` donde aplique).
- [ ] Entrada de `CHANGELOG.md` escrita, con la fecha del día.
- [ ] `dependencies` correctas y mínimas, con su porqué comentado.
- [ ] Suite completa en verde.
- [ ] `python -m build` sin avisos; `twine check dist/*` OK.
- [ ] **Ninguna ruta personal en el sdist**: `tar xzf` y `grep -r /home/`.
- [ ] `bugs/` NO viaja (lo garantiza `prune bugs` en `MANIFEST.in`; compruébalo
      construyendo, no leyendo).
- [ ] `workflow_dispatch` del workflow correspondiente, en verde.
- [ ] Y sólo entonces, la etiqueta.
