# DIAGNÓSTICO DE IMPLEMENTACIÓN DE ANALÍTICA MJV – WYNIK

## 1. Resumen ejecutivo

Se implementó el sistema de analítica local defensiva para **Wynik** alineado con la metodología **MJV (Métrica – Justificación – Valor)** y el cálculo de un **Funnel secuencial de tres etapas**, preservando íntegramente el diseño visual, el motor de audio/YIN, la lógica musical y la navegación existente.

- **Estado de la implementación:** terminada y verificada mediante 10 pruebas automatizadas nuevas (27 pruebas totales en la suite, todas en estado `OK`).
- **Estado de la prueba manual:** **realizada** el 23 de noviembre de 2026 (entre las 11:56 y las 12:07), utilizando el micrófono de la aplicación y el instrumento configurado como piano.
- **Evidencia JSON:** **generada y verificada** en `analytics_events.json` con **7 eventos** reales, **2 recorridos únicos** (`funnel_id`), **3 intentos de práctica** (`practice_id`) y **2 sesiones finalizadas naturalmente**.

---

## 2. Estado inicial del proyecto

Durante la auditoría previa a la edición se verificó:

- **Control de versiones:** rama `main`, sincronizada con `origin/main` en el commit `0777179` (*Cambio de formato de texto a UTF-8 para aceptar la Ñ*), con árbol de trabajo limpio (`nothing to commit, working tree clean`).
- **Analítica previa:** inexistente (no había módulo `analytics_service.py`, `analytics_events.json` ni uso de `logging` en `main.py`, `vistas/`, `servicios/`, `nucleo/` o `audio/`).
- **Almacenamiento reutilizable:** `servicios/almacenamiento.py` ya provee `configurar_directorio()`, `ruta_dato()`, `leer_json()` y `escribir_json()` con escritura atómica (`tempfile.mkstemp` + `os.replace`) y soporte de redirección mediante `WYNIK_DATOS` o `app.user_data_dir` en Android.
- **Pruebas base:** 17 pruebas unitarias existentes en `tests/` (`test_ajustes.py`, `test_almacenamiento.py`, `test_historial.py`, `test_musica.py`, `test_progreso.py`), todas pasando.

---

## 3. Arquitectura de analítica implementada

La solución se desacopló en `servicios/analytics_service.py` sin dependencias externas ni circulares:

- **Reutilización de almacenamiento:** emplea `ruta_dato()`, `leer_json()` y `escribir_json()` de `servicios/almacenamiento.py`, heredando la escritura atómica y el aislamiento de directorio para pruebas (`configurar_directorio()`).
- **Aislamiento defensivo:** `registrar_evento()` y `cargar_eventos()` encapsulan su ejecución en bloques `try ... except Exception`, registran incidencias mediante `logging.getLogger(__name__)` y nunca propagan excepciones hacia `WynikApp` ni bloquean la interfaz.
- **Concurrencia:** las operaciones de lectura-modificación-escritura están protegidas con `threading.Lock()`.
- **Protección ante JSON corrupto:** si `analytics_events.json` existe pero es ilegible o no contiene una lista JSON, `registrar_evento()` realiza una copia de respaldo con marca temporal (`analytics_events.corrupt.<UTC>.json`) mediante `_respaldar_archivo_invalido()` antes de inicializar una lista nueva. Si el respaldo falla, aborta la escritura sin destruir el archivo original.
- **Límite de retención:** conserva como máximo los `1000` eventos más recientes (`MAXIMO_EVENTOS = 1000`).

---

## 4. Descripción de los tres eventos

| Etapa | Evento (`event_name`) | Cuándo se registra | Qué se excluye explícitamente |
| :--- | :--- | :--- | :--- |
| 1 | `partitura_cargada` | Al finalizar `_cargar_partitura()` tras leer, validar y extraer una línea de notas no vacía. | Selecciones canceladas, archivos inexistentes/inválidos, partituras sin notas y recargas internas por `cambiar_convencion_guitarra()`. |
| 2 | `practica_iniciada` | Al final de `iniciar_escucha()`, después de que `ControladorPractica.iniciar()` abra el micrófono sin lanzar `MicrofonoNoDisponibleError`. | Fallos de permiso o apertura de micrófono, espera de cola de guía y reanudación de pausas (`boton_principal()` en estado `"pausada"`). |
| 3 | `sesion_finalizada` | Al final de `_terminar()`, invocado únicamente desde `_tick()` cuando `actualizacion.terminada` es `True` (fin natural de la partitura). | Salidas anticipadas (`detener_escucha()`, `_salir_de_la_practica()`, `reiniciar_practica()`, `on_stop()`). Protegido contra doble emisión con `_analytics_practice_completed`. |

---

## 5. Ubicación exacta de cada llamada a `registrar_evento()`

Todas las llamadas residen en `vistas/app.py`, dentro de la clase `WynikApp`:

1. **Importación:** `vistas/app.py`, línea **38** (`from servicios.analytics_service import generar_id as generar_id_analitica, registrar_evento`).
2. **Evento 1 (`partitura_cargada`):** `vistas/app.py`, método `WynikApp._cargar_partitura()` (definición en línea **691**), llamada en línea **770**.
3. **Evento 2 (`practica_iniciada`):** `vistas/app.py`, método `WynikApp.iniciar_escucha()` (definición en línea **1150**), llamada en línea **1193**.
4. **Evento 3 (`sesion_finalizada`):** `vistas/app.py`, método `WynikApp._terminar()` (definición en línea **1395**), llamada en línea **1436**.

---

## 6. Archivos nuevos

1. `servicios/analytics_service.py` — Servicio defensivo de registro, carga y cálculo del Funnel.
2. `tests/test_analytics.py` — Suite de 10 pruebas unitarias e integración aislada.
3. `analytics_events.json` — Archivo de evidencia local con 7 eventos reales registrados durante la prueba física del 23 de noviembre de 2026.
4. `informe_mjv_funnel.pdf` — Microinforme académico de 3 páginas (Matriz MJV, Funnel/resultados reales y propuesta A/B Testing).
5. `DIAGNOSTICO_IMPLEMENTACION_ANALYTICS.md` — Este documento de diagnóstico técnico.

---

## 7. Archivos modificados

1. `vistas/app.py` — Únicamente instrumentación puntual de los tres eventos y sus identificadores de sesión/recorrido.

*Nota:* No fue necesario modificar `main.py` porque `servicios/analytics_service.py` utiliza `logging.getLogger(__name__)` estándar sin requerir cambios globales de configuración, ni tampoco `servicios/__init__.py` al importarse directamente `servicios.analytics_service` en `vistas/app.py`.

---

## 8. Cambios realizados en cada archivo

En `vistas/app.py` se aplicaron cinco cambios acotados:

1. **Línea 38:** importación de `generar_id` (como `generar_id_analitica`) y `registrar_evento`.
2. **Líneas 241–244 (`_inicializar_estado`):** inicialización de `_analytics_funnel_id`, `_analytics_practice_id`, `_analytics_practice_started_at` y `_analytics_practice_completed`.
3. **Líneas 691–692 y 763–784 (`_cargar_partitura`) + línea 796 (`cambiar_convencion_guitarra`):** parámetro opcional `registrar_analitica: bool = True` (desactivado al cambiar convención de guitarra) y registro de `partitura_cargada` con metadatos musicales sin rutas completas.
4. **Líneas 1188–1209 (`iniciar_escucha`):** generación de `practice_id`, marca de tiempo inicial con `self.reloj()` y registro de `practica_iniciada`.
5. **Líneas 1422–1461 (`_terminar`):** guarda `_analytics_practice_completed`, cálculo de duración real (`self.reloj() - inicio_s`) y registro de `sesion_finalizada` con métricas del resumen del controlador.

---

## 9. Funcionamiento del `funnel_id` y `practice_id`

- Cada carga válida de partitura genera un nuevo `funnel_id` (`fnl-<uuid4>`) y reinicia `_analytics_practice_id`, `_analytics_practice_started_at` y `_analytics_practice_completed`.
- Cada inicio exitoso de escucha genera un `practice_id` (`prc-<uuid4>`) asociado al `funnel_id` vigente.
- Si el usuario pausa y reanuda la práctica, conserva el mismo `practice_id`.
- Si el usuario pulsa «Repetir» tras terminar o detiene e inicia de nuevo sobre la misma partitura cargada, conserva el `funnel_id` de ese recorrido y genera un nuevo `practice_id`.
- En el cálculo del Funnel (`calcular_funnel()`), el avance se evalúa por **`funnel_id` único**, evitando que múltiples inicios o repeticiones inflen la conversión.

---

## 10. Estructura del JSON

Cada elemento almacenado en `analytics_events.json` sigue el esquema:

```json
{
  "event_id": "evt-<uuid4>",
  "event_name": "partitura_cargada | practica_iniciada | sesion_finalizada",
  "timestamp": "YYYY-MM-DDTHH:MM:SS±HH:MM",
  "funnel_id": "fnl-<uuid4>",
  "practice_id": "prc-<uuid4> | null",
  "data": { ... }
}
```

- **Privacidad:** no se almacenan rutas completas del sistema de archivos, nombres de usuario ni grabaciones de audio.
- **Retención:** máximo `1000` eventos recientes (`eventos[-MAXIMO_EVENTOS:]`).

---

## 11. Fórmulas utilizadas para el Funnel

Implementadas en `servicios/analytics_service.py` (`calcular_funnel()`):

- **Etapa 1 ($E_1$):** número de `funnel_id` únicos que registraron `partitura_cargada`.
- **Etapa 2 ($E_2$):** número de `funnel_id` únicos con `practica_iniciada` habiendo alcanzado previamente la Etapa 1.
- **Etapa 3 ($E_3$):** número de `funnel_id` únicos con `sesion_finalizada` habiendo alcanzado previamente la Etapa 2.
- **Conversión 1 → 2:** $(E_2 / E_1) \times 100$ (si $E_1 = 0$, retorna `0.0`).
- **Conversión 2 → 3:** $(E_3 / E_2) \times 100$ (si $E_2 = 0$, retorna `0.0`).
- **Conversión Total (1 → 3):** $(E_3 / E_1) \times 100$ (si $E_1 = 0$, retorna `0.0`).
- **Abandono entre etapas:** $E_1 - E_2$ (1→2), $E_2 - E_3$ (2→3) y $E_1 - E_3$ (total).
- **Eventos repetidos y huérfanos:** los eventos repetidos dentro de una etapa ya alcanzada se contabilizan en `eventos_repetidos_en_etapa` sin duplicar el conteo del `funnel_id`; los eventos que llegan sin etapa previa se contabilizan en `eventos_huerfanos_o_fuera_de_secuencia` sin sumar a las conversiones.

---

## 12. Pruebas realizadas y resultados

Comando ejecutado después de la última edición de código:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Resultado observado: **27 pruebas ejecutadas en 0.220 s — `OK`** (17 pruebas preexistentes + 10 pruebas en `tests/test_analytics.py`):

- `test_registrar_evento_estructura_y_persistencia`: **ok**
- `test_relacion_identificadores_secuencia_completa`: **ok**
- `test_archivo_inexistente`: **ok**
- `test_json_invalido_preserva_evidencia_y_loguea`: **ok** (verifica respaldo `analytics_events.corrupt.*.json` y registro en `logging`)
- `test_excepcion_en_escritura_no_interrumpe_aplicacion`: **ok**
- `test_limite_maximo_1000_eventos`: **ok**
- `test_calcular_funnel_conversiones_y_abandono`: **ok**
- `test_calcular_funnel_vacio_sin_division_por_cero`: **ok**
- `test_calcular_funnel_duplicados_y_huerfanos`: **ok**
- `test_integracion_wynik_app_sin_microfono_fisico`: **ok** (prueba flujos reales de `WynikApp` con `CapturaBase` simulada, validando exclusión de cargas fallidas, cambio de convención en guitarra, fallo de micrófono, salida anticipada y guarda contra doble finalización).

---

## 13. Evidencia de funcionamiento y resultados verificados

| Categoría | Estado | Detalle |
| :--- | :--- | :--- |
| **Implementación terminada** | Completa | `servicios/analytics_service.py` y las 3 instrumentaciones en `vistas/app.py`. |
| **Pruebas automatizadas** | Completa (`27/27 OK`) | Aisladas con `tempfile.TemporaryDirectory()` y `configurar_directorio()`. No alteran `analytics_events.json`. |
| **Prueba manual real** | **Realizada (23/11/2026)** | Ejecutada físicamente entre las 11:56 y las 12:07 con micrófono e instrumento configurado como piano. |
| **Evidencia JSON** | **Generada y verificada** | `analytics_events.json` contiene **7 eventos**: 2 `partitura_cargada`, 3 `practica_iniciada` y 2 `sesion_finalizada` (formato `mxl`, sin punto inicial). |

### Resultados oficiales del Funnel (`calcular_funnel()`)

Al ejecutar `.venv/bin/python -m servicios.analytics_service` sobre `analytics_events.json`:

- **Eventos analizados:** `7`
- **Recorridos únicos (`funnel_id`):** `2`
- **Etapa 1 (`partitura_cargada`):** `2` recorridos únicos
- **Etapa 2 (`practica_iniciada`):** `2` recorridos únicos (conversión 1 → 2: **`100.00 %`**, abandono: `0`)
- **Etapa 3 (`sesion_finalizada`):** `2` recorridos únicos (conversión 2 → 3: **`100.00 %`**, abandono: `0`)
- **Conversión total (Etapa 1 → Etapa 3):** **`100.00 %`** (`recorridos_incompletos`: `0`)
- **Eventos repetidos en etapa:** `1` (segundo `practica_iniciada` dentro del segundo `funnel_id`, sin duplicar la etapa)
- **Eventos huérfanos / fuera de secuencia:** `0`

**Diferenciación entre nivel de recorrido y nivel de intento:**

- **Nivel de recorrido (`funnel_id`):** ambos recorridos iniciados con carga de partitura alcanzaron la finalización natural (conversión oficial del Funnel: `100 %`).
- **Nivel de intento (`practice_id`):** hubo **3 intentos de práctica** distintos; **2** cuentan con finalización natural asociada y **1** (`prc-a3c3647e-3260-450e-97ca-e5fc472407e5`, iniciado a las 12:04:45 en el segundo recorrido) corresponde a un **inicio de práctica sin finalización natural asociada** (sin evidencia para clasificarlo como abandono confirmado).

### Resultados musicales registrados

- **Primer recorrido (`fnl-5073022b-02d0-4d36-9892-c99b93cb7a18`):** carga `11:56:13` (`mxl`, 121 notas, 38 acordes, 33 compases, 120,0 BPM, piano), inicio `11:56:45` (`esperar_nota`, factor `1.0`), finalización natural `12:04:11` — **83/83 notas acertadas** (`100.0 %` precisión), `0` errores de altura, `0` omitidas o sin señal, duración **`445.89 s`**.
- **Segundo recorrido (`fnl-67dff39e-7ae7-4666-9070-387a42d03198`):** carga `12:04:32` (`mxl`, piano), primer inicio `12:04:45` (`seguir_tempo`, factor `0.7`, inicio de práctica sin finalización natural asociada), segundo inicio `12:05:45` (`seguir_tempo`, factor `0.5`), finalización natural `12:07:24` — **0/83 notas acertadas** (`0.0 %` precisión), **`14` errores de altura**, **`69` notas omitidas o sin señal**, duración **`99.66 s`**.

---

## 14. Defectos, limitaciones no críticas y mejoras futuras

### Defectos detectados

- No se detectaron defectos funcionales en la instrumentación ni en el cálculo de `calcular_funnel()`. Durante la auditoría técnica se corrigieron únicamente inconsistencias documentales menores (nombre real del botón «Practicar», almacenamiento de formato como `mxl` o `musicxml` sin punto inicial, y actualización de la evidencia real).

### Limitaciones no críticas

1. **Tamaño de muestra reducido ($n = 2$ recorridos, $3$ intentos):** los datos provenientes de la prueba física del 23 de noviembre de 2026 constituyen evidencia de validación funcional y trazabilidad del Funnel, pero no representan una muestra estadísticamente significativa del comportamiento de los usuarios.
2. **Intento sin finalización natural asociada:** el primer `practice_id` del segundo recorrido no registra `sesion_finalizada`; los datos actuales no permiten determinar con certeza el motivo de término.
3. **Entorno gráfico headless en pruebas automatizadas:** en entornos sin contexto OpenGL, `test_integracion_wynik_app_sin_microfono_fisico` aísla las importaciones de UI mediante `mock.patch.dict(sys.modules, ...)` mientras ejecuta la lógica real de `vistas/app.py`, `servicios/` y `nucleo/`.

### Mejoras futuras

- Evaluar en iteraciones posteriores el registro opcional de motivos de salida anticipada o reinicio para distinguir entre cambios de configuración y abandonos reales.
- Replicar la recolección de eventos en una muestra amplia de usuarios antes de ejecutar el experimento A/B propuesto en el microinforme.

---

## 15. Funcionalidades que no se modificaron

Se respetaron estrictamente todas las restricciones de alcance:

- Vistas y estilos: `vistas/wynik.kv`, `vistas/componentes.kv`, `vistas/tema.py`, pantallas, widgets, diálogos, colores, tipografías y navegación.
- Motor musical y de audio: algoritmo YIN, detección de frecuencia, captura de micrófono, comparación de notas, evaluación de sesión (`nucleo/sesion.py`) y procesamiento MusicXML (`nucleo/importador_musicxml.py`).
- Configuración y repositorio: `main.py`, `servicios/__init__.py`, `servicios/almacenamiento.py`, `.gitignore`, `pyproject.toml` y datos previos del usuario (`ajustes_wynik.json`, `historial_partituras.json`).

---

## 16. Verificación de la prueba física realizada (23 de noviembre de 2026)

La prueba manual con micrófono e instrumento físico (piano) fue ejecutada el **23 de noviembre de 2026** siguiendo el flujo real de la aplicación: carga de partitura (formato `mxl`), acceso a la práctica mediante el botón **«Practicar»** (y **«Empezar»** en la pantalla de interpretación) y finalización natural de la partitura.

Los resultados oficiales se verifican en modo solo lectura mediante:

```bash
.venv/bin/python -m json.tool analytics_events.json
.venv/bin/python -m servicios.analytics_service
```

El microinforme `informe_mjv_funnel.pdf` queda actualizado directamente con la salida verificada de `calcular_funnel()` y el detalle de `analytics_events.json`.
