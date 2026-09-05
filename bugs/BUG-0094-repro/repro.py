"""BUG-0094 — la salida del carril guiado no está estandarizada.

La presentación final de cada herramienta MCP queda delegada al LLM mediante
instrucciones en prosa DENTRO de la propia respuesta ("[Claude: muestra el
bloque TAL CUAL]", "Preséntalos en ESTE ORDEN", "NUNCA construyas tu propia
tabla"). La misma estimación produce salidas distintas según el agente.

Determinista, sin datos ni motor: inspecciona el código fuente. El bug está
PRESENTE mientras existan las marcas de delegación y no haya un esquema de
salida estructurado (secciones fijas ya ordenadas). Exit 1 = bug presente;
exit 0 = corregido.
"""
import pathlib
import sys

SRC = pathlib.Path("src/art/mcp_server.py").read_text()
FALLOS = []

print("== Marcas de presentación delegada al agente (el bug está presente si existen)")
marcas = {
    "[Claude:": "[Claude: ...] visible en la respuesta",
    "Preséntalos en ESTE ORDEN": "instrucción de ORDEN dirigida al agente",
    "PROHIBIDO: NUNCA construyas tu propia tabla": "prohibición dirigida al agente",
}
for pat, desc in marcas.items():
    n = SRC.count(pat)
    print(f"  {desc:52s} : {n} aparición(es)")
    if n > 0:
        FALLOS.append(f"'{pat}' sigue delegando la presentación al LLM")

print("\n== Esquema de salida estándar")
tiene_secciones = ("SUGERENCIA SIGUIENTE" in SRC) and ("CONCLUSIONES" in SRC)
print(f"  la herramienta ya compone secciones fijas (CONCLUSIONES / SUGERENCIA) : {tiene_secciones}")
if not tiene_secciones:
    FALLOS.append("no hay esquema de salida estructurado")

print("\n" + "=" * 70)
if FALLOS:
    print("FALLA (bug presente):", ", ".join(FALLOS))
    sys.exit(1)
print("OK: la salida está estandarizada; no queda presentación delegada al LLM.")
