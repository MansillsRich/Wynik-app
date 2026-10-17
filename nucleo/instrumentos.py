"""
Perfiles de instrumento: rango sonoro, convención de escritura, afinaciones y parámetros de
detección.

Los rangos son criterios iniciales de diseño (configurables), no resultados medidos:
- Guitarra: E2–E6 (MIDI 40–88), seis cuerdas en afinación estándar hasta el traste 24.
  Se escribe una octava por encima de como suena (convención habitual).
- Piano: A0–C8 (MIDI 21–108), rango aprobado para el piano monofónico.
- Flauta: C4–C7 (MIDI 60–96), experimental: no tiene parámetros ni pruebas propias todavía.

El detector busca la altura en un rango algo más amplio que el del instrumento (`margen_*`)
para poder informar de una nota fuera de rango como tal, en lugar de confundirla con la
nota más cercana al límite o con uno de sus armónicos.

Solo usa la biblioteca estándar.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Dict, Optional, Tuple

from .musica import LA4_HZ, midi_a_frecuencia

# Frecuencias de la red eléctrica y sus primeros armónicos: un tono estable a ±20 cents de
# una de ellas se trata como zumbido, no como nota. Ninguna nota temperada (La4 = 440 Hz)
# cae a menos de 35 cents de estas frecuencias.
FRECUENCIAS_RED_HZ = (50.0, 60.0, 100.0, 120.0, 150.0, 180.0)


@dataclass(frozen=True)
class ParametrosDeteccion:
    """Parámetros del detector para un perfil. Son valores iniciales de diseño, ajustados con
    señales sintéticas; su validez con instrumentos reales está pendiente de medición.

    Estimación de altura (YIN)
    - `umbral_yin`: umbral absoluto de la diferencia normalizada (paso 4 de YIN).
    - `aperiodicidad_max`: por encima, la trama no tiene una altura fiable.
    - `margen_inferior_semitonos`, `margen_superior_semitonos`: búsqueda fuera del rango.

    Segmentación en eventos
    - `tramas_confirmacion`: tramas de 10 ms con la misma altura que confirman un ataque.
    - `confirmacion_max_s`: tiempo máximo para confirmar un ataque antes de descartarlo.
    - `subida_ataque_db`: subida de nivel que marca un ataque (respecto del mínimo reciente).
    - `flujo_relativo`, `flujo_minimo`: detección de ataques por flujo espectral.
    - `histeresis_semitonos`: cambio de altura mínimo para considerar otra nota sin ataque.
    - `separacion_minima_s`: intervalo mínimo entre dos ataques.
    - `refinar_fundamental`: tras YIN, busca la fundamental en el espectro. Las cuerdas rígidas
      del piano son inarmónicas (f_n = n·f1·√(1 + B·n²)): el periodo común de sus parciales
      da una altura más aguda que la fundamental (≈ +16 cents con B típico), y esa diferencia
      convierte notas afinadas en «desafinadas».

    Niveles sin calibración (dBFS RMS en ventanas de 10 ms)
    - `nivel_silencio_dbfs`: por debajo, silencio.
    - `nivel_minimo_dbfs`: nivel mínimo para evaluar una nota (por debajo: señal débil).
    """

    umbral_yin: float = 0.30
    aperiodicidad_max: float = 0.30
    margen_inferior_semitonos: int = 12
    margen_superior_semitonos: int = 12
    tramas_confirmacion: int = 3
    confirmacion_max_s: float = 0.15
    subida_ataque_db: float = 6.0
    flujo_relativo: float = 2.5
    flujo_minimo: float = 15.0
    histeresis_semitonos: float = 0.75
    separacion_minima_s: float = 0.06
    refinar_fundamental: bool = False
    nivel_silencio_dbfs: float = -65.0
    nivel_minimo_dbfs: float = -50.0
    tolerancia_interferencia_cents: float = 20.0
    frecuencias_interferencia_hz: Tuple[float, ...] = FRECUENCIAS_RED_HZ


@dataclass(frozen=True)
class PerfilInstrumento:
    """Rango sonoro (MIDI), transposición habitual de escritura (escrita → sonora), estado de
    soporte, afinaciones disponibles (cuerdas al aire, de la 1.ª a la 6.ª) y parámetros de
    detección."""

    clave: str
    nombre: str
    midi_min: int
    midi_max: int
    transposicion_escritura: int = 0
    estado: str = "disponible"  # "disponible" o "experimental"
    afinaciones: Dict[str, Tuple[int, ...]] = field(default_factory=dict, compare=False)
    deteccion: ParametrosDeteccion = field(default_factory=ParametrosDeteccion, compare=False)

    def contiene(self, midi) -> bool:
        return self.midi_min <= midi <= self.midi_max

    @property
    def experimental(self) -> bool:
        return self.estado != "disponible"

    @property
    def rango_texto(self) -> str:
        from .musica import Altura
        return f"{Altura.desde_midi(self.midi_min).nombre}–{Altura.desde_midi(self.midi_max).nombre}"

    def con_rango(self, midi_min: int, midi_max: int) -> "PerfilInstrumento":
        """El mismo perfil con otro rango (afinaciones alternativas, instrumentos concretos)."""
        if midi_min >= midi_max:
            raise ValueError("El rango del instrumento debe tener al menos dos notas")
        return replace(self, midi_min=int(midi_min), midi_max=int(midi_max))

    def rango_busqueda_hz(self, la4: float = LA4_HZ, frecuencia_muestreo: Optional[float] = None
                          ) -> Tuple[float, float]:
        """Rango de frecuencias en que el detector busca la altura (rango ± márgenes).

        Se limita a 20 Hz por abajo y al 45 % de la frecuencia de muestreo por arriba."""
        p = self.deteccion
        f_min = midi_a_frecuencia(self.midi_min - p.margen_inferior_semitonos, la4)
        f_max = midi_a_frecuencia(self.midi_max + p.margen_superior_semitonos, la4)
        f_min = max(f_min, 20.0)
        if frecuencia_muestreo:
            f_max = min(f_max, 0.45 * frecuencia_muestreo)
        return f_min, f_max


AFINACIONES_GUITARRA: Dict[str, Tuple[int, ...]] = {
    # Cuerdas 1.ª (aguda) a 6.ª (grave), altura sonora en MIDI.
    "estandar": (64, 59, 55, 50, 45, 40),        # E4 B3 G3 D3 A2 E2
    "re_grave": (64, 59, 55, 50, 45, 38),        # drop D: 6.ª en D2
    "medio_tono_abajo": (63, 58, 54, 49, 44, 39),  # E♭ estándar
    "re_abierta": (62, 57, 54, 50, 45, 38),      # D A D F♯ A D
}

NOMBRES_AFINACION = {
    "estandar": "Estándar (E A D G B E)",
    "re_grave": "Re grave / drop D (D A D G B E)",
    "medio_tono_abajo": "Medio tono abajo (E♭ A♭ D♭ G♭ B♭ E♭)",
    "re_abierta": "Re abierta (D A D F♯ A D)",
}

GUITARRA = PerfilInstrumento(
    "guitarra", "Guitarra", 40, 88, transposicion_escritura=-12,
    afinaciones=AFINACIONES_GUITARRA,
    deteccion=ParametrosDeteccion(margen_inferior_semitonos=12, margen_superior_semitonos=12),
)
PIANO = PerfilInstrumento(
    "piano", "Piano", 21, 108,
    # Por debajo de A0 no hay notas de piano: un margen pequeño basta y evita tramas largas.
    deteccion=ParametrosDeteccion(margen_inferior_semitonos=2, margen_superior_semitonos=4,
                                  refinar_fundamental=True),
)
FLAUTA = PerfilInstrumento("flauta", "Flauta", 60, 96, estado="experimental")

PERFILES: Dict[str, PerfilInstrumento] = {p.clave: p for p in (GUITARRA, PIANO, FLAUTA)}

_PATRONES = (
    (GUITARRA, re.compile(r"guit|gtr|chitarra|gitarre", re.IGNORECASE)),
    (PIANO, re.compile(r"piano|keyboard|teclado|klavier", re.IGNORECASE)),
    (FLAUTA, re.compile(r"flaut|flute|fl[oö]te", re.IGNORECASE)),
)


def perfil_por_nombre(*textos: Optional[str]) -> Optional[PerfilInstrumento]:
    """Perfil que corresponde a un nombre de parte o de instrumento ('Guitarra', 'Piano'…)."""
    for perfil, patron in _PATRONES:
        if any(texto and patron.search(texto) for texto in textos):
            return perfil
    return None


def perfil_de_guitarra(afinacion: str = "estandar", trastes: int = 24) -> PerfilInstrumento:
    """Perfil de guitarra con el rango de una afinación concreta: desde la 6.ª cuerda al aire
    hasta el último traste de la 1.ª."""
    if afinacion not in AFINACIONES_GUITARRA:
        raise ValueError(f"Afinación de guitarra desconocida: {afinacion!r}")
    cuerdas = AFINACIONES_GUITARRA[afinacion]
    return GUITARRA.con_rango(min(cuerdas), max(cuerdas) + trastes)
