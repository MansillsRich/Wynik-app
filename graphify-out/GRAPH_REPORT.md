# Graph Report - Wynik-app  (2026-10-18)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1007 nodes · 2175 edges · 61 communities (29 shown, 32 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 169 edges (avg confidence: 0.91)
- Token cost: 5,032 input · 543 output

## Graph Freshness
- Built from commit: `c60e0640`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Musical Event Model
- UI Screen Management
- Guitar Fingering Logic
- Audio Analysis Engine
- Settings Persistence
- Pitch and Frequency
- Audio Guide Synthesis
- Audio Buffer Handling
- Instrument Noise Profiles
- Listening Engine Control
- App Main Controller
- MusicXML Import Logic
- Practice Session Logic
- Progress and Tuning Widgets
- Audio Playback Control
- Dialogs and Alerts
- Pitch Estimation Details
- Practice State Enums
- Score Rendering Widget
- UI Basic Components
- Instrument Illustrations
- Note Segmentation State
- Performance Event Data
- Practice Flow Controller
- App Entry Point
- Musical Math Utilities
- Guide Audio Interface
- Audio Capture Backend
- Signal Level Calibration
- Instrument Guide Visualization
- Reusable UI Layouts
- Score Service Interface
- App Lifecycle Management
- Signal Processing Pipeline
- Responsive Layout Components
- Tempo and Timing
- Theming and Fonts
- Practice Screen Layout
- Score Loading Service
- Musical Data Model
- Notation Compatibility Service
- Interactive Button Behaviors
- Score Structure Model
- Event Display Logic
- Styled Icon Buttons
- Pitch Comparison Results
- Note Evaluation Results
- Status Indicators
- Progress Bar Widget
- Musical Notation Metadata
- Option Group Layout
- Notification System
- File Selection Interface

## God Nodes (most connected - your core abstractions)
1. `WynikApp` - 111 edges
2. `EventoInterpretacion` - 46 edges
3. `Altura` - 44 edges
4. `MotorDeEscucha` - 30 edges
5. `SesionDePractica` - 28 edges
6. `ControladorPractica` - 27 edges
7. `disponer()` - 27 edges
8. `ErrorAltura` - 22 edges
9. `PerfilInstrumento` - 21 edges
10. `midi_mas_cercano()` - 21 edges

## Surprising Connections (you probably didn't know these)
- `refinar_fundamental()` --calls--> `NumPy`  [EXTRACTED]
  audio/estimador_yin.py → requirements-escritorio.txt
- `_niveles_db()` --calls--> `NumPy`  [EXTRACTED]
  audio/analizador.py → requirements-escritorio.txt
- `escribir_wav()` --calls--> `NumPy`  [EXTRACTED]
  audio/guia.py → requirements-escritorio.txt
- `_onda()` --calls--> `NumPy`  [EXTRACTED]
  audio/guia.py → requirements-escritorio.txt
- `sintetizar()` --calls--> `NumPy`  [EXTRACTED]
  audio/guia.py → requirements-escritorio.txt

## Import Cycles
- 3-file cycle: `vistas/__init__.py -> vistas/app.py -> vistas/widgets/ilustraciones.py -> vistas/__init__.py`
- 3-file cycle: `vistas/__init__.py -> vistas/app.py -> vistas/componentes.py -> vistas/__init__.py`
- 4-file cycle: `vistas/__init__.py -> vistas/app.py -> vistas/componentes.py -> vistas/widgets/dibujo.py -> vistas/__init__.py`
- 4-file cycle: `vistas/__init__.py -> vistas/widgets/__init__.py -> vistas/widgets/guia_instrumento_widget.py -> vistas/widgets/dibujo.py -> vistas/__init__.py`
- 5-file cycle: `vistas/__init__.py -> vistas/app.py -> vistas/widgets/__init__.py -> vistas/widgets/guia_instrumento_widget.py -> vistas/widgets/dibujo.py -> vistas/__init__.py`

## Hyperedges (group relationships)
- **Core Application Dependencies** — kivy, kivymd, music21, numpy, sounddevice [EXTRACTED 1.00]

## Communities (61 total, 32 thin omitted)

### Community 0 - "Musical Event Model"
Cohesion: 0.07
Nodes (24): Clave, Evento, NotaEvento, Parte, alteraciones_de_armadura(), altura_total(), _ancho_de_espaciado(), _Cabeza (+16 more)

### Community 1 - "UI Screen Management"
Cohesion: 0.08
Nodes (6): AjustesInicioScreen, AjustesScreen, ElegirPartituraScreen, InterpreteScreen, MenuScreen, ProgresoScreen

### Community 2 - "Guitar Fingering Logic"
Cohesion: 0.11
Nodes (15): acorde_guitarra(), _afinacion(), alternativas_guitarra(), Cejilla, _colocacion_calculada(), _con_dedo(), DiagramaAcorde, digitacion_piano() (+7 more)

### Community 3 - "Audio Analysis Engine"
Cohesion: 0.12
Nodes (3): _potencia_de_2(), refinar_fundamental(), TipoEvento

### Community 4 - "Settings Persistence"
Cohesion: 0.11
Nodes (15): AjustesPractica, cargar_ajustes(), guardar_ajustes(), configurar_directorio(), directorio_datos(), escribir_json(), leer_json(), ruta_dato() (+7 more)

### Community 6 - "Audio Guide Synthesis"
Cohesion: 0.14
Nodes (11): escribir_wav(), _frecuencias_de_nota(), GuiaSintetizada, _onda(), sintetizar(), SonidoGuia, sonidos_de_notas(), duracion_wav() (+3 more)

### Community 7 - "Audio Buffer Handling"
Cohesion: 0.08
Nodes (4): BloqueAudio, CapturaManual, ColaDeBloques, EstadisticasCaptura

### Community 8 - "Instrument Noise Profiles"
Cohesion: 0.12
Nodes (5): PerfilDeRuido, perfil_de_guitarra(), PerfilInstrumento, DetectorDeNotas, _ruido_desde_umbral_rms()

### Community 11 - "MusicXML Import Logic"
Cohesion: 0.14
Nodes (13): _altura(), _convertir(), _convertir_parte(), _desplazar_octavas(), _id_de_parte(), _intervalo_en(), _intervalos_declarados(), _mapa_tempo() (+5 more)

### Community 13 - "Progress and Tuning Widgets"
Cohesion: 0.10
Nodes (5): AnilloProgreso, _Dibujo, GraficoSesiones, MedidorCents, TiraResultados

### Community 17 - "Practice State Enums"
Cohesion: 0.15
Nodes (6): describir_estado(), EstadoNota, ModoPractica, NotaEsperada, notas_esperadas(), OpcionesPractica

### Community 18 - "Score Rendering Widget"
Cohesion: 0.17
Nodes (4): tramo_visible(), PartituraWidget, px(), X()

### Community 19 - "UI Basic Components"
Cohesion: 0.13
Nodes (10): Boton, glifo(), Icono, IconoCirculo, cerrar_dialogo(), dialogo_abierto(), mostrar_dialogo(), accion() (+2 more)

### Community 21 - "Instrument Illustrations"
Cohesion: 0.13
Nodes (5): con_alfa(), DibujoInstrumento, _Ilustracion, IlustracionPortada, _nota()

### Community 22 - "Note Segmentation State"
Cohesion: 0.22
Nodes (6): _Candidato, _NotaActiva, _salto_armonico(), Segmentador, Trama, ParametrosDeteccion

### Community 25 - "App Entry Point"
Cohesion: 0.13
Nodes (9): YIN NumPy implementation, Kivy, KivyMD, main(), music21, Wynik, requirements-desarrollo.txt, requirements-referencia.txt (+1 more)

### Community 27 - "Musical Math Utilities"
Cohesion: 0.19
Nodes (8): a_midi(), cents_entre(), comparar_frecuencia(), _entero_si_exacto(), ErrorAltura, _es_numero_finito(), frecuencia_a_midi(), midi_a_frecuencia()

### Community 29 - "Audio Capture Backend"
Cohesion: 0.15
Nodes (3): CapturaBase, CapturaSounddevice, MicrofonoNoDisponibleError

### Community 30 - "Signal Level Calibration"
Cohesion: 0.23
Nodes (8): calibrar(), cents(), es_interferencia(), nivel_dbfs(), niveles_por_ventana(), TonoEstacionario, _tonos_estacionarios(), NumPy

### Community 31 - "Instrument Guide Visualization"
Cohesion: 0.23
Nodes (5): texto(), GuiaInstrumentoWidget, posicion(), y_cuerda(), _nombre()

### Community 32 - "Reusable UI Layouts"
Cohesion: 0.17
Nodes (5): FilaPartitura, FilaPartituraProgreso, FilaSesion, Superficie, TarjetaPulsable

### Community 33 - "Score Service Interface"
Cohesion: 0.18
Nodes (4): Ataque, ataque_a_nota(), cargar_partitura(), validar_extension_partitura()

### Community 36 - "Responsive Layout Components"
Cohesion: 0.17
Nodes (4): BarraSuperior, Bloque, Columnas, Ocultable

### Community 37 - "Tempo and Timing"
Cohesion: 0.22
Nodes (4): _ataques_de_parte(), _ligadura_abierta(), MapaTempo, _Sonido

### Community 38 - "Theming and Fonts"
Cohesion: 0.23
Nodes (4): registrar_fuentes(), ruta_dejavu(), ruta_roboto(), textura()

### Community 40 - "Score Loading Service"
Cohesion: 0.20
Nodes (5): ErrorPartitura, extension_admitida(), importar_musicxml(), _resumen(), cargar_partitura_estructurada()

### Community 41 - "Musical Data Model"
Cohesion: 0.31
Nodes (3): EstadoAltura, Ligadura, OrigenTransposicion

### Community 42 - "Notation Compatibility Service"
Cohesion: 0.22
Nodes (3): comparar_alturas(), nota_coincide(), paso_diatonico()

### Community 53 - "Musical Notation Metadata"
Cohesion: 0.29
Nodes (3): _estructura_de_notacion(), Armadura, Compas

## Knowledge Gaps
- **5 isolated node(s):** `YIN NumPy implementation`, `music21`, `sounddevice`, `requirements-desarrollo.txt`, `requirements-referencia.txt`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 408 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **32 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `WynikApp` connect `App Main Controller` to `UI Screen Management`, `Guitar Fingering Logic`, `Audio Analysis Engine`, `Settings Persistence`, `Listening Engine Control`, `Progress and Tuning Widgets`, `Audio Playback Control`, `Dialogs and Alerts`, `Practice State Enums`, `Practice Setup Logic`, `Practice Flow Controller`, `App Entry Point`, `Musical Math Utilities`, `Guide Audio Interface`, `Audio Capture Backend`, `App Lifecycle Management`, `Musical Data Model`, `Event Display Logic`, `Navigation and Input`, `Status Indicators`, `Calibration Management`, `File Selection Interface`?**
  _High betweenness centrality (0.207) - this node is a cross-community bridge._
- **Are the 15 inferred relationships involving `WynikApp` (e.g. with `CapturaSounddevice` and `MicrofonoNoDisponibleError`) actually correct?**
  _`WynikApp` has 15 INFERRED edges - model-reasoned connections that need verification._
- **What connects `YIN NumPy implementation`, `music21`, `sounddevice` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Musical Event Model` be split into smaller, more focused modules?**
  _Cohesion score 0.06641604010025062 - nodes in this community are weakly interconnected._
- **Why does `Altura` connect `Pitch and Frequency` to `Musical Event Model`, `Guitar Fingering Logic`, `Audio Analysis Engine`, `Audio Guide Synthesis`, `Instrument Noise Profiles`, `Musical Data Model`, `Notation Compatibility Service`, `MusicXML Import Logic`, `Event Display Logic`, `Performance Event Data`, `Visual Feedback Widgets`, `Musical Math Utilities`, `Instrument Guide Visualization`?**
  _High betweenness centrality (0.086) - this node is a cross-community bridge._
- **Are the 10 inferred relationships involving `EventoInterpretacion` (e.g. with `Analizador` and `MotorDeEscucha`) actually correct?**
  _`EventoInterpretacion` has 10 INFERRED edges - model-reasoned connections that need verification._
- **Should `UI Screen Management` be split into smaller, more focused modules?**
  _Cohesion score 0.07827260458839407 - nodes in this community are weakly interconnected._