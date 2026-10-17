"""
Sistema visual de Wynik: colores, tipografía, medidas y puntos de corte.

Un único sitio para los valores que comparten `wynik.kv`, los componentes (`componentes.py`)
y los dibujos (`widgets/`). No importa Kivy: las medidas están en dp y los tamaños de letra en
sp, y quien los usa los convierte.

Paleta: fondo claro cálido, superficies blancas, azul petróleo como color principal, grafito
para el texto y un ámbar discreto como acento. Los colores de evaluación (acierto, desafinada,
error, sin evaluar) van siempre acompañados de un símbolo: el color nunca es la única señal.
"""

# ------------------------------------------------------------------------------ colores (RGBA)
FONDO = (0.957, 0.949, 0.933, 1)            # #F4F2EE, gris cálido muy suave
SUPERFICIE = (1, 1, 1, 1)
SUPERFICIE_2 = (0.925, 0.937, 0.933, 1)     # #ECEFEE, superficies secundarias
BORDE = (0.855, 0.847, 0.827, 1)            # #DAD8D3
BORDE_FUERTE = (0.70, 0.71, 0.70, 1)

PRIMARIO = (0.055, 0.353, 0.384, 1)         # #0E5A62, azul petróleo
PRIMARIO_OSCURO = (0.035, 0.255, 0.282, 1)  # #094148
PRIMARIO_SUAVE = (0.851, 0.918, 0.914, 1)   # #D9EAE9
SOBRE_PRIMARIO = (1, 1, 1, 1)

ACENTO = (0.851, 0.522, 0.192, 1)           # #D98531, ámbar
ACENTO_SUAVE = (0.988, 0.925, 0.851, 1)     # #FCECD9

TINTA = (0.137, 0.153, 0.169, 1)            # #23272B, grafito
TINTA_SUAVE = (0.365, 0.396, 0.427, 1)      # #5D656D
TINTA_TENUE = (0.55, 0.57, 0.59, 1)

CORRECTO = (0.165, 0.525, 0.255, 1)         # #2A8641
CORRECTO_SUAVE = (0.882, 0.945, 0.890, 1)
DESAFINADO = (0.659, 0.443, 0.063, 1)       # #A87110
DESAFINADO_SUAVE = (0.984, 0.937, 0.839, 1)
ERROR = (0.769, 0.227, 0.176, 1)            # #C43A2D
ERROR_SUAVE = (0.980, 0.894, 0.882, 1)
NEUTRO = (0.42, 0.45, 0.48, 1)
NEUTRO_SUAVE = (0.918, 0.922, 0.925, 1)

SOMBRA = (0.10, 0.12, 0.14, 0.10)
VELO = (0.08, 0.10, 0.12, 0.45)             # fondo de los diálogos

# Estado visual del resultado → (color, fondo suave, icono, etiqueta breve)
ESTADOS = {
    "correcta": (CORRECTO, CORRECTO_SUAVE, "check-circle", "Correcta"),
    "desafinada": (DESAFINADO, DESAFINADO_SUAVE, "approximately-equal", "Desafinada"),
    "error": (ERROR, ERROR_SUAVE, "close-circle", "Error"),
    "sin_evaluar": (NEUTRO, NEUTRO_SUAVE, "circle-outline", "Sin evaluar"),
    "omitida": (NEUTRO, NEUTRO_SUAVE, "minus-circle-outline", "Sin tocar"),
    "fuera_de_rango": (ERROR, ERROR_SUAVE, "alert-circle-outline", "Fuera de rango"),
    "cuenta": (ACENTO, ACENTO_SUAVE, "timer-sand", "Prepárate"),
    "escuchando": (PRIMARIO, PRIMARIO_SUAVE, "microphone", "Escuchando"),
    "terminada": (PRIMARIO, PRIMARIO_SUAVE, "flag-checkered", "Terminada"),
    "neutro": (NEUTRO, NEUTRO_SUAVE, "music-note-outline", "Pendiente"),
}

# ------------------------------------------------------------------------------ tipografía
# DejaVu Sans tiene ♭ ♯ ♮ ♩ ✓ ✗: se usa en todo lo que puede llevar nombres de notas o de
# partituras. Roboto (incluida en KivyMD) solo en rótulos fijos sin símbolos musicales.
FUENTE_TEXTO = "WynikTexto"      # DejaVu Sans
FUENTE_TITULO = "WynikTitulo"    # Roboto Bold
FUENTE_ROTULO = "WynikRotulo"    # Roboto Medium

# tamaños en sp
T_PANTALLA = 24     # título grande (nota esperada aparte)
T_TITULO = 20
T_SUBTITULO = 16
T_CUERPO = 15
T_SECUNDARIO = 13
T_ETIQUETA = 12
T_NOTA = 44         # nota esperada en la práctica

# ------------------------------------------------------------------------------ medidas (dp)
MARGEN = 16
HUECO = 12
RADIO = 16
RADIO_PEQUENO = 12
ALTO_BARRA = 60
ALTO_BOTON = 48
ALTO_TOQUE = 44     # área mínima de pulsación
ANCHO_CONTENIDO = 760

# Puntos de corte (dp)
ANCHO_MEDIO = 600   # desde aquí, dos columnas en listas y opciones
ANCHO_AMPLIO = 900  # desde aquí, la práctica reparte partitura y guía en horizontal
ALTO_BAJO = 480     # por debajo, la práctica se reparte en dos columnas (apaisado)

DURACION_TRANSICION = 0.22
DURACION_ANIMACION = 0.16


def modo_practica(ancho_dp: float, alto_dp: float) -> str:
    """Reparto de la pantalla de práctica según el espacio disponible (en dp):
    «apaisada» (baja y más ancha que alta), «amplia» (partitura arriba, guía a la derecha) o
    «vertical» (todo apilado)."""
    if alto_dp < ALTO_BAJO and ancho_dp > alto_dp:
        return "apaisada"
    if alto_dp >= ALTO_BAJO and (ancho_dp >= ANCHO_AMPLIO or (ancho_dp >= 720 and ancho_dp > alto_dp * 1.15)):
        return "amplia"
    return "vertical"


def con_alfa(color, alfa):
    return (color[0], color[1], color[2], alfa)
