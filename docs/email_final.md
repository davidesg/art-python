# Email de difusión — ATSW (listo para enviar)

Versión condensada, lista para copiar/pegar. Español como principal; inglés para
colegas internacionales.

---

## Español

**Asunto:** ATSW — un taller de series temporales Box-Jenkins que manejas hablando con una IA

Estimados colegas:

Quiero compartir **ATSW** (*A Time Series Workshop*), una suite en Python para
construir modelos univariantes de series temporales con la metodología
**Box-Jenkins-Treadway**: estimación máximo-verosímil exacta (ARMAX y funciones
de transferencia), previsión, identificación, diagnosis y contrastes formales.

Lo distinto es que ATSW incluye un **servidor MCP**, así que puedes ejecutar toda
la metodología *conversando* con Claude: la herramienta aporta la evidencia
(gráficos, contrastes, números) y tú y la IA aportáis el criterio en cada
decisión, de forma guiada paso a paso o totalmente autónoma. También funciona como
librería Python normal si no usas Claude.

Un poco de contexto: Box-Jenkins es un caso de *falsa simplicidad* —los modelos
ARMA son simples, pero el proceso iterativo de construcción funcionaba de
maravilla sobre todo si eras Box, Jenkins o uno de sus discípulos—; lo difícil es
entrenar al analista en unas decisiones muchas veces heurísticas. ATSW combina ese
criterio con métodos estadísticos, y la IA —con sus limitaciones— aporta el
criterio y las sugerencias que daría un analista entrenado. La metodología no es la
canónica, sino la versión con extensiones de **Arthur B. Treadway** (discípulo de
Gwilym Jenkins), fruto de su trabajo en los Servicios de Previsión y Seguimiento
de la economía española. Y una regla útil: estas previsiones univariantes son una
*regla de medida* — si un modelo más sofisticado no las mejora, repiénsalo.

Empezar lleva dos minutos:

```
pip install atsw
claude mcp add art -- art-mcp     # opcional: manejarlo desde Claude
```

Después pídele a Claude que analice una serie tuya. La suite y la documentación
están en PyPI: https://pypi.org/project/atsw/

Cualquier comentario será muy bienvenido.

Un saludo,
David E. Guerrero
davidesg@ucm.es

---

## English

**Subject:** ATSW — a Box-Jenkins time series workshop you can drive by talking to an AI

Dear colleagues,

I'd like to share **ATSW** (*A Time Series Workshop*), a Python suite for building
univariate time series models the **Box-Jenkins-Treadway** way: exact
maximum-likelihood ARMAX / transfer-function estimation, forecasting,
identification, diagnosis and formal tests.

What's different is that ATSW ships an **MCP server**, so you can run the whole
methodology *by conversation* with Claude: the tool supplies the evidence (graphs,
tests, numbers) and you and the AI supply the judgement at each decision — guided
step by step, or fully autonomous. It also works as a plain Python library if you
don't use Claude.

A bit of background: Box-Jenkins is a case of *false simplicity* — the ARMA models
are simple, but the iterative building process worked wonderfully mainly if you
were Box, Jenkins, or one of their disciples; the hard part is training analysts in
the (often heuristic) decisions. ATSW pairs that criterion with statistical
methods, and AI — with its limitations — supplies the criterion and suggestions a
trained analyst would offer. The methodology is not the canonical one but the
extended version of **Arthur B. Treadway** (a disciple of Gwilym Jenkins), shaped
by his work on the Forecasting and Monitoring Services of the Spanish economy. A
useful rule of thumb: these univariate forecasts are a *measuring stick* — if a
fancier model can't beat them, rethink it.

Getting started takes two minutes:

```
pip install atsw
claude mcp add art -- art-mcp     # optional: drive it from Claude
```

Then ask Claude to analyse one of your own series. Suite and docs on PyPI:
https://pypi.org/project/atsw/

Feedback very welcome.

Best,
David E. Guerrero
davidesg@ucm.es
