"""
Procesamiento de audio de Wynik: estimación de altura, nivel de señal, segmentación en
eventos, análisis en tiempo real, captura y síntesis de la guía.

Los módulos de análisis solo dependen de numpy (sin librosa, numba, scipy, sounddevice ni
Kivy) para poder compartirse entre escritorio y Android. La captura de escritorio
(`audio.captura`) importa sounddevice únicamente al abrir el micrófono.

Este paquete no importa nada al cargarse.
"""
