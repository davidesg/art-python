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
| **pyfug** | `atws/fug/pyfug` | `.github/workflows/publish.yml` | `v*` | puro Python; **activo sólo desde el 2026-09-25** (ver abajo) |
| **art-tseries** | `ART/art-python` | `.github/workflows/publish-art.yml` | `art-v*` | **con smoke test** antes de publicar |
| **atsw** | `ART/art-python` (`atsw-suite/`) | `.github/workflows/publish-atsw.yml` | `atsw-v*` | meta-paquete |

**pyfug: su workflow no funcionó hasta el 2026-09-25.** Estaba en el repo desde
julio, pero GitHub nunca lo registró (la lista de workflows sólo tenía
«Dependency Graph», y `gh workflow run` daba 404): la 2.0.0 se subió a mano, y
pyfug no tenía ningún tag. Se registró tocando el fichero. Si un workflow no
aparece en `gh workflow list`, ése es el remedio. Publicar por él exige un
*trusted publisher* en PyPI para `davidesg/pyfug`, workflow `publish.yml`,
entorno `pypi`.

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

## 5. Probar en un entorno limpio — con las suites, no sólo con el smoke test

**Añadido el 2026-09-25**, tras encontrar así BUG-0191: la 0.2.1 publicada tenía
rotas tres herramientas en toda instalación limpia (faltaba jinja2), y ni la
suite ni el smoke test del CI podían verlo, porque en el entorno de desarrollo
todo estaba instalado por otra vía.

Y hay una segunda razón: **el entorno de desarrollo envejece**. El 2026-09-25
tenía numpy 1.26 y pandas 2.1; un `pip install` limpio trajo numpy 2.5 y pandas
3.0, y sólo así salieron los tests de fue que no funcionaban con numpy 2.

```bash
D=/ruta/de/pruebas
python -m build --outdir $D/dist                 # en pyfug, fue y art (art: antes
                                                 # tools/sync_material.py)
python -m venv $D/env
$D/env/bin/pip install $D/dist/*.whl pytest
# las suites CONTRA LO INSTALADO — y comprobando que es lo instalado lo que se
# importa (un test canario que mire `art.__file__`, `fue.__file__`…):
cd art-python && $D/env/bin/python -m pytest tests     # art: `-m`, sus tests
                                                       # importan `tests._texto`
cd fue/fue    && $D/env/bin/pytest --import-mode=importlib tests
cp -r fug/pyfug/tests $D/t && cd $D && env/bin/pytest t   # pyfug mete la raíz
                                                          # del repo en sys.path
```

Lo que falle aquí y no en desarrollo es exactamente lo que verá un usuario.

## Checklist previo a cada publicación

- [ ] Versión subida en `pyproject` (y en `__version__` donde aplique).
- [ ] Entrada de `CHANGELOG.md` escrita, con la fecha del día.
- [ ] `dependencies` correctas y mínimas, con su porqué comentado.
- [ ] Suite completa en verde.
- [ ] **Las ruedas instaladas en un entorno limpio, y las suites en verde contra
      ellas** (§5).
- [ ] `python -m build` sin avisos; `twine check dist/*` OK.
- [ ] **Ninguna ruta personal en el sdist**: `tar xzf` y `grep -r /home/`.
- [ ] `bugs/` NO viaja (lo garantiza `prune bugs` en `MANIFEST.in`; compruébalo
      construyendo, no leyendo).
- [ ] `workflow_dispatch` del workflow correspondiente, en verde.
- [ ] Y sólo entonces, la etiqueta.
