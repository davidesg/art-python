---
id: BUG-0082
title: La suite deja PNG en blanco en el temporal COMPARTIDO — indistinguibles de salida real, y el analista concluye que ART renderiza en blanco
status: fixed
severity: low
component: tests
found_in: 0.1.12
fixed_in: 0.1.12
reported: 2026-09-04
reporter: David — «art esta renderizando png en blanco»
tags: [tests, hygiene, presentation]
references:
  - tests/test_bug_0078_show_fig.py
  - src/art/mcp_server.py:692 (tempfile.gettempdir())
  - bugs/BUG-0082-repro/repro.py
  - BUG-0078
---

## Summary

BUG-0078 puso la guarda para no ABRIR ventana bajo pytest, y dejó a propósito la
escritura del fichero: *«El fichero se escribe igual, que es lo que una prueba
comprueba»*. Correcto — pero se escribe en `tempfile.gettempdir()`, el temporal
COMPARTIDO, con el mismo patrón de nombre que la salida real.

Resultado: cada corrida de la suite siembra `/tmp` de PNG en blanco llamados
`art_*.png`.

## Impact

Bajo, pero real y confuso, y ésta es la forma en que se manifestó: el analista vio
PNG en blanco en `/tmp` y concluyó que **ART estaba renderizando en blanco**. No
lo estaba — las figuras de la sesión eran correctas (51-112 KB). Los blancos eran
fixtures de la suite del 2026-09-03: 49 ficheros de 651 bytes con etiquetas
`prueba_ruta`, `nota`, `estable`, `en_result`, `colision`, `falla`, `multi`.

Es decir: la basura de las pruebas es indistinguible del producto, y cuesta una
sesión de diagnóstico averiguar que no hay nada roto.

## Reproduction

`bugs/BUG-0082-repro/repro.py` — cuenta los `art_*.png` del temporal antes y
después de correr UN fichero de tests:

```
17 passed, 1 warning in 3.41s

ficheros art_*.png nuevos en /tmp: 5
     651 bytes  art_colision_338937.png
     651 bytes  art_en_result_338937.png
     651 bytes  art_estable_338937.png
     651 bytes  art_nota_338937.png
     651 bytes  art_prueba_ruta_338937.png

de ellos, en blanco (<2 KB): 5
```

## Fix (propuesto)

Que bajo pytest la ruta salga de la fixture `tmp_path` en vez de
`tempfile.gettempdir()` — por ejemplo respetando una variable de entorno
`ART_FIG_DIR` que el conftest fije al `tmp_path` de cada test. Los tests siguen
comprobando que el fichero se escribe, y no queda nada en el temporal común.

---

## Fix (aplicado, 2026-09-04)

`_show_fig` respeta **`ART_FIG_DIR`**; si no está, usa el temporal del sistema
como antes. Y un `tests/conftest.py` nuevo —el primero del repo— con una fixture
`autouse` que la fija al `tmp_path` de cada prueba:

```python
@pytest.fixture(autouse=True)
def _figuras_fuera_del_temporal_comun(tmp_path, monkeypatch):
    d = tmp_path / "figs"; d.mkdir(exist_ok=True)
    monkeypatch.setenv("ART_FIG_DIR", str(d))
    monkeypatch.setenv("ART_NO_VIEWER", "1")
```

`autouse` a propósito: la higiene no puede depender de que cada prueba nueva se
acuerde de pedirla. pytest limpia `tmp_path` solo, así que no queda nada, y las
pruebas siguen comprobando que el fichero se escribe — que es lo que BUG-0078
quería preservar.

De paso la fixture fija `ART_NO_VIEWER`, con lo que la guarda de las ventanas
deja de depender de detectar `pytest` en `sys.modules`.

## Validation — resultado

El repro sale 0:

```
ficheros art_*.png nuevos en /tmp: 0
de ellos, en blanco (<2 KB): 0
```

En `tests/test_bug_0081_0082_figuras.py` hay además una regresión que **corre un
fichero de pruebas en un subproceso y cuenta lo que queda en el temporal
común**, que es la comprobación de verdad: la propiedad es sobre el efecto de
correr la suite, no sobre una llamada suelta.

## Lo que queda, y no lo borra el arreglo

En `/tmp` hay **218 ficheros `art_*.png` acumulados** de antes: 89 en blanco
(<2 KB, fixtures de corridas anteriores) y 129 reales de las sesiones de estos
días. El arreglo impide que se sigan sembrando, pero no limpia los que ya
están — son ficheros del usuario en su temporal, y borrarlos es su decisión.
