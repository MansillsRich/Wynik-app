"""
Guía visual de cómo tocar la nota (o el acorde) esperada: diapasón de guitarra o teclado de
piano. El widget solo dibuja; las posiciones salen de `nucleo.digitacion` (calculadas por la
aplicación a partir de la altura sonora y de la afinación configurada).

`modelo` (dict):
- {"tipo": "guitarra", "afinacion": (E4 … E2), "posicion": (cuerda, traste, dedo|None) | None,
   "alternativas": [(cuerda, traste), …]}
- {"tipo": "guitarra_acorde", "afinacion": …, "trastes": (6.ª … 1.ª), "dedos": (…)|None,
   "validado": bool, "cejillas": [(traste, cuerda_desde, cuerda_hasta, dedo), …]}
  Con digitación verificada se dibujan los dedos y la cejilla como una barra sobre las cuerdas
  que cubre. Sin ella (`validado` falso) solo se marcan las posiciones, en gris y huecas: no se
  afirma ningún dedo.
- {"tipo": "piano", "rango": (midi_inicial, midi_final), "teclas": [midi…],
   "dedos": {midi: dedo}, "detectada": midi|None, "acierto": bool|None}
- {"tipo": "vacio", "mensaje": "…"}
"""

from kivy.graphics import Color, Ellipse, Line, Rectangle, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, DictProperty
from kivy.uix.widget import Widget

from nucleo.digitacion import es_tecla_negra
from nucleo.musica import Altura

from . import dibujo

INCRUSTACIONES = {3, 5, 7, 9, 15, 17, 19, 21}


def _nombre(midi: int, solfeo: bool, octava: bool = True) -> str:
    altura = Altura.desde_midi(int(midi))
    nombre = altura.nombre_solfeo if solfeo else altura.nombre
    if not octava:
        nombre = nombre.rstrip("0123456789")
    return nombre


class GuiaInstrumentoWidget(Widget):
    modelo = DictProperty({"tipo": "vacio", "mensaje": ""})
    solfeo = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.redibujar, size=self.redibujar, modelo=self.redibujar,
                  solfeo=self.redibujar)

    def redibujar(self, *args):
        self.canvas.clear()
        if self.width < dp(60) or self.height < dp(40):
            return
        tipo = self.modelo.get("tipo", "vacio")
        with self.canvas:
            Color(*dibujo.PAPEL)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            if tipo == "guitarra":
                self._diapason(self.modelo)
            elif tipo == "guitarra_acorde":
                self._acorde(self.modelo)
            elif tipo == "piano":
                self._teclado(self.modelo)
            else:
                dibujo.texto(self.modelo.get("mensaje", ""), self.center_x, self.center_y,
                             max(dp(11), min(dp(15), self.height * 0.1)), dibujo.TINTA_SUAVE)

    # ------------------------------------------------------------------------------------
    #  Guitarra
    # ------------------------------------------------------------------------------------
    def _rejilla(self, primer_traste: int, n_trastes: int, afinacion, marcas_izquierda=None):
        """Dibuja cuerdas y trastes; devuelve una función (cuerda, traste) → (x, y)."""
        # El diapasón no crece sin límite: en ventanas grandes se centra con proporciones fijas.
        separacion = min((self.height - dp(34)) / 5.0, dp(30))
        alto = 5 * separacion
        abajo = self.center_y - alto / 2 + dp(6)
        arriba = abajo + alto
        ancho_util = min(self.width - dp(48), dp(120) * n_trastes)
        izquierda = self.center_x - ancho_util / 2 + dp(14)
        derecha = izquierda + ancho_util - dp(14)
        ancho_traste = (derecha - izquierda) / n_trastes
        tam = max(dp(10), min(dp(14), separacion * 0.8))

        def y_cuerda(cuerda):
            return arriba - (cuerda - 1) * separacion

        Color(*dibujo.TINTA_SUAVE)
        for indice in range(n_trastes):
            traste = primer_traste + indice
            x = izquierda + (indice + 0.5) * ancho_traste
            if traste in INCRUSTACIONES:
                Ellipse(pos=(x - dp(3), abajo + alto / 2 - dp(3)), size=(dp(6), dp(6)))
            elif traste == 12:
                Ellipse(pos=(x - dp(3), abajo + alto * 0.3 - dp(3)), size=(dp(6), dp(6)))
                Ellipse(pos=(x - dp(3), abajo + alto * 0.7 - dp(3)), size=(dp(6), dp(6)))
            dibujo.texto(str(traste), x, abajo - dp(12), tam * 0.85, dibujo.TINTA_SUAVE)
        Color(*dibujo.TINTA)
        for indice in range(n_trastes + 1):
            x = izquierda + indice * ancho_traste
            ancho = dp(2.5) if (indice == 0 and primer_traste == 1) else dp(0.8)
            Line(points=[x, abajo, x, arriba], width=ancho)
        for cuerda in range(1, 7):
            y = y_cuerda(cuerda)
            Line(points=[izquierda, y, derecha, y], width=dp(0.5 + 0.18 * cuerda))
            nombre = _nombre(afinacion[cuerda - 1], self.solfeo, octava=False)
            dibujo.texto(nombre, izquierda - dp(24), y, tam * 0.85, dibujo.TINTA_SUAVE)

        def posicion(cuerda, traste):
            if traste == 0:
                return izquierda - dp(10), y_cuerda(cuerda)
            return izquierda + (traste - primer_traste + 0.5) * ancho_traste, y_cuerda(cuerda)

        return posicion, separacion, tam

    @staticmethod
    def _ventana(trastes):
        pisados = [t for t in trastes if t]
        if not pisados or max(pisados) <= 4:
            return 1, 5
        inicio = max(1, min(pisados) - 1)
        return inicio, max(5, max(pisados) - inicio + 2)

    def _diapason(self, modelo):
        afinacion = modelo.get("afinacion") or (64, 59, 55, 50, 45, 40)
        posicion = modelo.get("posicion")
        if not posicion:
            dibujo.texto(modelo.get("mensaje") or "Esta nota no está en la guitarra",
                         self.center_x, self.center_y, max(10, self.height * 0.12),
                         dibujo.INCORRECTO)
            return
        cuerda, traste, dedo = posicion
        alternativas = [tuple(a) for a in modelo.get("alternativas", [])]
        primer, n = self._ventana([traste])
        punto, separacion, tam = self._rejilla(primer, n, afinacion)
        radio = max(dp(6), separacion * 0.42)
        for c, t in alternativas:
            if t == 0 or primer <= t < primer + n:
                x, y = punto(c, t)
                Color(*dibujo.TINTA_SUAVE)
                Line(circle=(x, y, radio * 0.8), width=dp(1))
        x, y = punto(cuerda, traste)
        Color(*dibujo.ACTUAL)
        if traste == 0:
            Line(circle=(x, y, radio * 0.75), width=dp(1.6))
        else:
            Ellipse(pos=(x - radio, y - radio), size=(2 * radio, 2 * radio))
            if dedo:
                dibujo.texto(str(dedo), x, y, tam, dibujo.PAPEL, negrita=True)

    def _acorde(self, modelo):
        afinacion = modelo.get("afinacion") or (64, 59, 55, 50, 45, 40)
        trastes = list(modelo.get("trastes") or [])  # 6.ª … 1.ª
        dedos = modelo.get("dedos")
        validado = bool(modelo.get("validado"))
        cejillas = [tuple(c) for c in (modelo.get("cejillas") or [])] if validado else []
        primer, n = self._ventana([t for t in trastes if t is not None])
        punto, separacion, tam = self._rejilla(primer, n, afinacion)
        radio = max(dp(6), separacion * 0.42)
        color = dibujo.ACTUAL if validado else dibujo.TINTA_SUAVE
        for traste_c, desde, hasta, dedo_c in cejillas:
            if not primer <= traste_c < primer + n:
                continue
            x, y_grave = punto(desde, traste_c)
            _, y_aguda = punto(hasta, traste_c)
            Color(*color)
            RoundedRectangle(pos=(x - radio * 0.8, y_grave - radio * 0.9), size=(1.6 * radio, y_aguda - y_grave + 1.8 * radio),
                             radius=[radio * 0.8])
            dibujo.texto(str(dedo_c), x, (y_grave + y_aguda) / 2, tam, dibujo.PAPEL, negrita=True)
        for i, traste in enumerate(trastes):
            cuerda = 6 - i
            if traste is None:
                x, y = punto(cuerda, 0)
                dibujo.texto("×", x, y, tam * 1.1, dibujo.TINTA_SUAVE)
                continue
            x, y = punto(cuerda, traste)
            Color(*color)
            if traste == 0:
                Line(circle=(x, y, radio * 0.75), width=dp(1.5))
            elif any(c[0] == traste and c[2] <= cuerda <= c[1] for c in cejillas):
                continue  # la cubre la barra de la cejilla
            elif not validado:
                Line(circle=(x, y, radio * 0.85), width=dp(1.4))   # posición sin digitación verificada
            else:
                Ellipse(pos=(x - radio, y - radio), size=(2 * radio, 2 * radio))
                if dedos and dedos[i]:
                    dibujo.texto(str(dedos[i]), x, y, tam, dibujo.PAPEL, negrita=True)

    # ------------------------------------------------------------------------------------
    #  Piano
    # ------------------------------------------------------------------------------------
    def _teclado(self, modelo):
        inicial, final = modelo.get("rango", (48, 71))
        teclas = {int(m) for m in modelo.get("teclas", [])}
        dedos = {int(k): v for k, v in (modelo.get("dedos") or {}).items()}
        detectada = modelo.get("detectada")
        acierto = modelo.get("acierto")
        blancas = [m for m in range(int(inicial), int(final) + 1) if not es_tecla_negra(m)]
        if not blancas:
            return
        # Teclas con proporciones de teclado: en ventanas grandes no se estiran, se centran.
        ancho = min((self.width - dp(16)) / len(blancas), dp(42))
        alto = min(self.height - dp(34), ancho * 5.0)
        izquierda = self.center_x - ancho * len(blancas) / 2
        abajo = self.center_y - (alto + dp(22)) / 2
        arriba = abajo + alto
        tam = max(dp(9), min(dp(13), ancho * 0.5))
        x_blanca = {}
        for i, midi in enumerate(blancas):
            x = izquierda + i * ancho
            x_blanca[midi] = x
            esperada = midi in teclas
            Color(*(dibujo.ACTUAL if esperada else dibujo.PAPEL))
            Rectangle(pos=(x, abajo), size=(ancho, alto))
            Color(*dibujo.TINTA)
            Line(rectangle=(x, abajo, ancho, alto), width=dp(0.6))
            if esperada:
                dibujo.texto(_nombre(midi, self.solfeo), x + ancho / 2, abajo + dp(12), tam,
                             dibujo.PAPEL, negrita=True)
            elif midi % 12 == 0:
                dibujo.texto(_nombre(midi, self.solfeo), x + ancho / 2, abajo + dp(12), tam * 0.9,
                             dibujo.TINTA_SUAVE)
        ancho_negra = ancho * 0.6
        alto_negra = alto * 0.62
        x_negra = {}
        for midi in range(int(inicial), int(final) + 1):
            if not es_tecla_negra(midi) or (midi - 1) not in x_blanca:
                continue
            x = x_blanca[midi - 1] + ancho - ancho_negra / 2
            x_negra[midi] = x
            esperada = midi in teclas
            Color(*(dibujo.ACTUAL if esperada else dibujo.TINTA))
            Rectangle(pos=(x, arriba - alto_negra), size=(ancho_negra, alto_negra))
            if esperada:
                dibujo.texto(_nombre(midi, self.solfeo), x + ancho_negra / 2,
                             arriba - alto_negra + dp(12), tam * 0.85, dibujo.PAPEL, negrita=True)

        def caja(midi):
            if midi in x_blanca:
                return x_blanca[midi], abajo, ancho, alto
            if midi in x_negra:
                return x_negra[midi], arriba - alto_negra, ancho_negra, alto_negra
            return None

        for midi, dedo in dedos.items():
            datos = caja(midi)
            if datos:
                x, y, w, h = datos
                dibujo.texto(str(dedo), x + w / 2, arriba + dp(11), tam, dibujo.ACTUAL, negrita=True)
        if detectada is not None:
            datos = caja(int(detectada))
            color = dibujo.CORRECTO if acierto else dibujo.INCORRECTO
            if datos:
                x, y, w, h = datos
                Color(*color)
                Line(rectangle=(x + dp(2), y + dp(2), w - dp(4), h - dp(4)), width=dp(2))
            else:
                dibujo.texto(f"Oído: {_nombre(int(detectada), self.solfeo)} (fuera de este tramo)",
                             self.center_x, arriba + dp(11), tam, color)
