"""
Núcleo musical de Wynik: modelo de datos y reglas musicales independientes de la interfaz
y de la captura de audio.

Módulos:
- `nucleo.musica`: alturas (MIDI, hercios, grafía original), comparación con las tolerancias
  aprobadas, eventos, partes, tempo y partitura. Solo usa la biblioteca estándar.
- `nucleo.instrumentos`: perfiles de instrumento (rango sonoro y convención de escritura).
- `nucleo.importador_musicxml`: lectura de MusicXML con music21, que solo se importa al leer.

Este paquete no importa Kivy, KivyMD, librosa ni sounddevice, y su `__init__` no importa
nada: cada módulo se carga solo cuando se usa.
"""
