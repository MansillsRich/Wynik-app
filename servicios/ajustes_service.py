"""
Ajustes de práctica persistentes (`ajustes_wynik.json` en el directorio de datos).

Solo se guardan ajustes con efecto real en el detector o en la sesión. Los valores fuera de
rango se corrigen al leerlos, para que un archivo editado a mano no rompa la aplicación.
"""

from dataclasses import asdict, dataclass, fields
from typing import Optional

from nucleo.instrumentos import AFINACIONES_GUITARRA, PERFILES

from .almacenamiento import escribir_json, leer_json

ARCHIVO_AJUSTES = "ajustes_wynik.json"
TOLERANCIAS_TEMPORALES_MS = (100, 150, 200, 250)
FACTOR_TEMPO_MIN, FACTOR_TEMPO_MAX = 0.5, 1.5
LA4_MIN, LA4_MAX = 430.0, 450.0


@dataclass
class AjustesPractica:
    instrumento: str = "piano"
    afinacion_guitarra: str = "estandar"
    la4: float = 440.0
    modo: str = "seguir_tempo"           # o "esperar_nota"
    factor_tempo: float = 1.0
    tolerancia_ms: int = 150
    notacion_solfeo: bool = False
    calibrar_al_empezar: bool = True
    pulsos_cuenta: int = 3
    dispositivo: Optional[int] = None    # índice del dispositivo de entrada (None: predeterminado)
    volumen_guia: float = 0.8
    vista_simple: bool = False
    escala_fuente: float = 1.0

    def corregidos(self) -> "AjustesPractica":
        if self.instrumento not in PERFILES or PERFILES[self.instrumento].experimental:
            self.instrumento = "piano"
        if self.afinacion_guitarra not in AFINACIONES_GUITARRA:
            self.afinacion_guitarra = "estandar"
        self.la4 = float(min(max(float(self.la4), LA4_MIN), LA4_MAX))
        if self.modo not in ("seguir_tempo", "esperar_nota"):
            self.modo = "seguir_tempo"
        self.factor_tempo = round(float(min(max(float(self.factor_tempo), FACTOR_TEMPO_MIN),
                                                FACTOR_TEMPO_MAX)), 2)
        if int(self.tolerancia_ms) not in TOLERANCIAS_TEMPORALES_MS:
            self.tolerancia_ms = 150
        self.tolerancia_ms = int(self.tolerancia_ms)
        self.pulsos_cuenta = int(min(max(int(self.pulsos_cuenta), 0), 8))
        self.volumen_guia = float(min(max(float(self.volumen_guia), 0.0), 1.0))
        if self.dispositivo is not None and not isinstance(self.dispositivo, int):
            self.dispositivo = None
        self.notacion_solfeo = bool(self.notacion_solfeo)
        self.calibrar_al_empezar = bool(self.calibrar_al_empezar)
        self.vista_simple = bool(self.vista_simple)
        self.escala_fuente = round(float(min(max(float(self.escala_fuente), 0.8), 1.6)), 2)
        return self


def cargar_ajustes() -> AjustesPractica:
    datos = leer_json(ARCHIVO_AJUSTES, {})
    if not isinstance(datos, dict):
        datos = {}
    conocidos = {f.name for f in fields(AjustesPractica)}
    try:
        ajustes = AjustesPractica(**{k: v for k, v in datos.items() if k in conocidos})
        return ajustes.corregidos()
    except (TypeError, ValueError):
        return AjustesPractica()


def guardar_ajustes(ajustes: AjustesPractica) -> bool:
    return escribir_json(ARCHIVO_AJUSTES, asdict(ajustes.corregidos()))
