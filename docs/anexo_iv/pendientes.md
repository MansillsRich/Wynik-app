# Lista interna del Anexo IV v3.0 (Wynik)

Lista de trabajo del equipo. No forma parte del informe ni se cita en él.

## Resuelto el 04/11/2026

- Fecha de la prueba con piano real: 04/11/2026.
- Nota incorrecta en macOS: primero se tocó a propósito un Do♯1 y la app lo marcó como error (Figura 24); en el segundo intento el La4 pedido se reconoció como correcto (Figura 25).
- Pruebas de Sebastián (Windows 11, Python 3.12.3 AMD64) y Benjamín (Fedora Linux, Python 3.14.10 x86_64): 13/13 OK; agregadas en el apartado 5.8.2 (figuras 26 y 27).
- Apartado 5.7.4 (defecto de `Ocultable`) retirado del informe por decisión del equipo.
- Integrantes y roles, incluida Javiera Alejandra Celia Muñoz Toledo (desarrolladora y tester).
- IDE: Visual Studio Code, última versión.
- Licencia de materialyoucolor: MIT (archivo `LICENSE` del paquete).
- APK: generado con Buildozer; el informe indica que aún tiene errores de compatibilidad entre versiones y que se está trabajando en ello.

## Mejoras de código observadas (para el equipo; el informe no las lista)

- [ ] **`Ocultable`** (`vistas/componentes.py`): los elementos ocultos al iniciar se liberan y no reaparecen (aviso de importación, «¿Cómo suena esta guitarra?», `texto_aviso` y resumen de «Mis partituras»). Reproducción: `python docs/anexo_iv/diagnostico_visibilidad.py`.
- [ ] **«Oído» y el mensaje** pueden mostrar eventos distintos cuando un evento no cambia el resultado (Figura 24).
- [ ] **APK:** captura de audio con `AudioRecord` (pyjnius), selector de documentos de Android y permiso `RECORD_AUDIO`.
- [ ] **Ruff:** 37 avisos; 35 se corrigen con `ruff check . --fix` (revisar el diff).
- [ ] **Historial:** escribir `historial_partituras.json` con `escribir_json` (escritura atómica).
- [ ] **Pruebas:** cubrir la detección (`audio/`), la importación MusicXML y `SesionDePractica` (cobertura actual: 10 %). `nucleo/sesion.py` cita `tests/test_22_sincronizacion.py`, que no existe.
- [ ] **Requisitos:** las cabeceras citan `requirements.txt`, `requirements-referencia.*` y `requirements-desarrollo.txt`, que no están en el repositorio; pytest está declarado en `pyproject.toml` y no se usa.
- [ ] **pydoc:** `vistas/avisos.py` falla con `KeyError: '__objclass__'`.
- [ ] **Comentario residual** «hola» en `nucleo/sesion.py`.
- [ ] **Versión de Python:** `pyproject.toml` declara `>=3.13`, pero en Windows se usó 3.12.3 (las 13 pruebas pasan).
