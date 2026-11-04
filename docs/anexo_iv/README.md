# docs/anexo_iv — Anexo IV v3.0 de Wynik

Material de apoyo del «Anexo IV – Documentación Técnica de Programación» (versión 3.0, 04/11/2026). Ningún archivo de esta carpeta forma parte de la aplicación ni modifica su código.

| Ruta | Contenido |
|---|---|
| `informe/Anexo_IV_Wynik_v3.0.docx` · `.pdf` | Informe final (índices y listas actualizados con LibreOffice). |
| `informe/construir_informe.js` · `actualizar_indices.py` | Generan el .docx (docx-js) y actualizan índices y PDF (LibreOffice/UNO). |
| `diagnostico.md` | Diagnóstico de la versión 2.0 contra el código. |
| `pendientes.md` | Lista interna del equipo (no forma parte del informe): datos por agregar y mejoras de código observadas. |
| `capturas/macos/` · `windows/` · `fedora/` | Capturas del equipo: pruebas y práctica con piano real en macOS; pruebas en Windows 11 y Fedora Linux. |
| `crear_partituras.py` · `partituras/` | Partituras MusicXML de ejemplo (el repositorio no trae ninguna). |
| `capturar_pantallas.py` | Ejecuta la app real, recorre las pantallas y guarda `capturas/originales/` y `capturas/cajas/`. Entrada simulada, sin micrófono. |
| `anotar_capturas.py` | Dibuja los marcadores numerados en `capturas/anotadas/`. |
| `generar_evidencias.py` | Salidas de unittest, Ruff, coverage, árbol y parámetros en `evidencias/` e imágenes en `capturas/terminal/`. |
| `generar_pydoc.py` · `pydoc/` | Documentación HTML del código con pydoc. |
| `diagnostico_visibilidad.py` | Reproduce el defecto de `Ocultable` (elementos ocultos que no reaparecen). |
| `diagramas/` | Fuentes Graphviz (`.dot`) y PNG de los diagramas. |
| `_datos_demo/` | JSON escritos por la app durante la captura (ejemplos del apartado 3.7). |
| `recursos/logo_uct.png` | Logo de la portada, tomado de la versión 2.0. |

Regenerar todo (desde la raíz del repositorio, con el entorno virtual activado; en Linux sin pantalla, anteponer `xvfb-run -a` a los scripts que abren la interfaz):

```bash
python -m pip install ruff coverage            # herramientas de la revisión
python docs/anexo_iv/crear_partituras.py
python docs/anexo_iv/capturar_pantallas.py
python docs/anexo_iv/anotar_capturas.py
python docs/anexo_iv/generar_evidencias.py
python docs/anexo_iv/generar_pydoc.py
node docs/anexo_iv/informe/construir_informe.js          # requiere el paquete npm «docx»
python3 docs/anexo_iv/informe/actualizar_indices.py      # requiere LibreOffice y python3-uno
```
