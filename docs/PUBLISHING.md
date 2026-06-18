# Publicación de la suite ATWS en PyPI

Orden de publicación (respeta dependencias): **fue → pyfug → art-tseries → atws**.
Validar siempre primero en TestPyPI.

## 0. Requisitos

```bash
python -m pip install --upgrade build twine
```
Cuentas en https://test.pypi.org y https://pypi.org con API tokens.

## 1. fue 0.1.3 (re-publicar con los fixes)

fue tiene extensión C → wheels por plataforma con `cibuildwheel` (ya configurado
en su `pyproject.toml`). En local se puede subir sdist + wheel local; para wheels
multiplataforma usar CI (GitHub Actions + cibuildwheel).

```bash
cd atws/fue/fue
python -m build            # sdist + wheel local
twine upload --repository testpypi dist/*
```
Verificar instalación limpia: `pip install -i https://test.pypi.org/simple/ fue==0.1.3`.

## 2. pyfug 2.0.0 (puro-Python)

```bash
cd atws/fug/pyfug
python -m build
twine upload --repository testpypi dist/*
```

## 3. art-tseries 0.1.0

Depende de `fue>=0.1.3` y `pyfug>=2.0` (ya en TestPyPI tras los pasos 1-2).
```bash
cd ART/art-python
python -m build
twine upload --repository testpypi dist/*
# probar resolución de dependencias desde TestPyPI:
pip install -i https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ art-tseries
art-mcp --help   # comprobar que el script existe
```

## 4. atws 1.0.0 (meta-paquete)

```bash
cd ART/art-python/atws-suite
python -m build
twine upload --repository testpypi dist/*
pip install -i https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ atws
```

## 5. Promoción a PyPI

Cuando TestPyPI valide (instalación + `claude mcp add art -- art-mcp` funciona),
repetir `twine upload dist/*` (sin `--repository testpypi`) en el mismo orden.

## Checklist previo a cada subida

- [ ] Versión bumpeada (pyproject + `__init__`/`__version__` donde aplique).
- [ ] `dependencies` correctas y mínimas.
- [ ] `README.md` presente y referenciado en `readme`.
- [ ] `license` declarada (GPL-2.0-or-later en toda la suite).
- [ ] `python -m build` sin warnings; `twine check dist/*` OK.
- [ ] Instalación limpia en un venv vacío.
