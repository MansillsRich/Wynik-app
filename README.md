# Wynik 🎵 - Práctica Musical Interactiva en Tiempo Real

Wynik es una aplicación avanzada diseñada para la práctica musical interactiva. Funciona como un entrenador personal virtual, permitiendo al usuario cargar partituras complejas (MusicXML) y recibir *feedback* inmediato sobre su rendimiento al tocar notas en instrumentos virtuales o reales a través del micrófono.

El objetivo de Wynik es cerrar la brecha entre el estudio teórico y la aplicación práctica, proporcionando una herramienta robusta y configurable para músicos de todos los niveles.

## 💡 Funcionalidades Clave

*   **Soporte MusicXML:** Carga completa de archivos MusicXML, interpretando estructuras musicales complejas (partes, eventos, tempo).
*   **Feedback en Tiempo Real:** Utiliza el micrófono del dispositivo para analizar la frecuencia y el momento exactos en que se toca una nota.
    *   Evalúa si la nota tocada es correcta.
    *   Evalúa la precisión rítmica y temporal (*timing*).
*   **Representaciones Visuales Múltiples:** Muestra la nota esperada utilizando múltiples visualizadores, adaptándose al instrumento seleccionado:
    *   Pentagrama tradicional (notación musical).
    *   Diapasón de Guitarra.
    *   Teclado de Piano.
*   **Núcleo Musical Independiente:** La lógica central del proyecto (`nucleo`) está desacoplada de la interfaz gráfica y del hardware de audio, garantizando modularidad y mantenibilidad.

## ⚙️ Arquitectura Técnica (Para Desarrolladores)

Wynik está construido con una arquitectura limpia que separa completamente las preocupaciones:

1.  **`wynik.nucleo.musica`:** El corazón teórico del sistema. Gestiona todas las reglas musicales, tolerancias de frecuencia, cálculos de tempo y la secuencia lógica de eventos sin depender de ninguna GUI o librería de audio externa (solo usa librerías estándar).
2.  **`wynik.nucleo.instrumentos`:** Define perfiles de instrumentos específicos, estableciendo los rangos sonoros válidos y las convenciones de representación gráfica para cada tipo de instrumento (piano, guitarra, flauta, etc.).
3.  **`wynik.nucleo.importador_musicxml`:** Maneja la compleja tarea de leer y parsear el formato MusicXML utilizando `music21`, traduciendo la notación en una estructura de datos usable por el núcleo.

> **Base Tecnológica:** Kivy/KivyMD para la interfaz gráfica (GUI). Python 3.13 como lenguaje principal, con un fuerte enfoque en la eficiencia y estabilidad del procesamiento de señales de audio (`sounddevice`).

## 🛠️ Instalación (Escritorio)

Wynik requiere Python 3.13 y acceso a micrófono. Sigue estos pasos para configurar tu entorno:

**Requisitos Previos:**
*   Python 3.13 instalado.
*   Un micrófono funcional conectado al sistema operativo.
*   ***[IMPORTANTE]*** **(Linux):** Puede que necesites instalar dependencias del sistema como `libcairo2-dev` y `pkg-config`.

**Pasos de Instalación:**

```bash
# 1. Crear un entorno virtual (recomendado)
python3.13 -m venv .venv

# 2. Activar el entorno
source .venv/bin/activate # En Windows: .venv\Scripts\activate

# 3. Instalar todas las dependencias necesarias
pip install -r requirements-escritorio.txt
