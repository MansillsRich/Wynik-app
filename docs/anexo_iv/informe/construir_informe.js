// Construye el Anexo IV v3.0 de Wynik (.docx) con docx-js.
// Script auxiliar del anexo: no forma parte de la aplicación.
// Uso: node docs/anexo_iv/informe/construir_informe.js  (desde la raíz del repositorio)
// Después: python3 docs/anexo_iv/informe/actualizar_indices.py (actualiza índices y exporta PDF).

const fs = require("fs");
const path = require("path");
const d = require("docx");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, TableOfContents, SimpleField, PageBreak,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, AlignmentType, ImageRun,
  Footer, Header, PageNumber, LevelFormat, VerticalAlign, TabStopType,
} = d;

const RAIZ = path.resolve(__dirname, "..", "..", "..");
const AN = path.join(RAIZ, "docs", "anexo_iv");
const SALIDA = path.join(AN, "informe", "Anexo_IV_Wynik_v3.0_sin_indices.docx");

const VERSION = "3.0";
const FECHA = "04/11/2026";
const ASIGNATURA = "Taller Práctico Laboral II: Desarrollo de Soluciones";
const PROFESOR = "Henry Nelson Seguel Quilodran";
const RICHARD = "Segundo Richard Nicolás Mansilla Lleucún";
const AZUL = "1F4E79";
const AZUL2 = "2E74B5";
const GRIS = "595959";
const FUENTE = "Arial";
const MONO = "Courier New";
const ANCHO = 9360; // ancho útil en DXA (carta, márgenes de 2,5 cm aprox.)

// ------------------------------------------------------------------ numeración de figuras y tablas
const FIGS = ["arbol", "dependencias", "flujo", "navegacion", "menu", "importar", "mis_partituras",
  "preparar_a", "preparar_b", "ajustes_a", "ajustes_b", "practica_lista", "cuenta", "correcta",
  "incorrecta", "desafinada", "resumen", "progreso", "simple", "pydoc", "unittest", "ruff",
  "mac_pruebas", "mac_incorrecta", "mac_correcta", "windows_pruebas", "fedora_pruebas"];
const TABS = ["ficha", "versiones", "equivalencias", "herramientas", "estructura", "dependencias",
  "licencias", "audio", "nucleo", "servicios", "vistas", "kv", "clasificacion", "parametros",
  "simulacion", "json", "paleta", "t_menu", "t_importar", "t_mis", "t_prep_a", "t_prep_b",
  "t_ajustes_a", "t_ajustes_b", "t_practica", "t_resumen", "t_progreso", "t_simple",
  "requisitos", "pruebas", "cobertura", "ruff", "problemas", "plataformas", "android", "calidad",
  "trazabilidad", "criterios", "glosario"];
const numF = (k) => { const i = FIGS.indexOf(k); if (i < 0) throw new Error("figura " + k); return i + 1; };
const numT = (k) => { const i = TABS.indexOf(k); if (i < 0) throw new Error("tabla " + k); return i + 1; };
const F = (k) => `Figura ${numF(k)}`;
const T = (k) => `Tabla ${numT(k)}`;
const creadas = { Figura: [], Tabla: [] };
const tablasEnteras = [];

// ------------------------------------------------------------------ texto con marcas simples
// **negrita**, *cursiva*, `código`; «[POR CONFIRMAR]» se resalta.
function runs(texto, base = {}) {
  const partes = String(texto).split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|\[POR CONFIRMAR[^\]]*\])/g).filter((s) => s !== "");
  return partes.map((p) => {
    if (p.startsWith("**")) return new TextRun({ ...base, text: p.slice(2, -2), bold: true });
    if (p.startsWith("`")) return new TextRun({ ...base, text: p.slice(1, -1), font: MONO, size: base.size ? base.size - 2 : 20 });
    if (p.startsWith("[POR CONFIRMAR")) return new TextRun({ ...base, text: p, bold: true, color: "C00000", highlight: "yellow" });
    if (p.startsWith("*") && p.endsWith("*") && p.length > 2) return new TextRun({ ...base, text: p.slice(1, -1), italics: true });
    return new TextRun({ ...base, text: p });
  });
}
const P = (texto, op = {}) => new Paragraph({ children: runs(texto, op.run || {}), spacing: { after: 120, line: 276 }, ...op.par });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H1s = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const B = (texto, nivel = 0) => new Paragraph({ children: runs(texto), numbering: { reference: "vinetas", level: nivel }, spacing: { after: 60, line: 264 } });
let listaNumerada = 0;
function N(items) {
  listaNumerada += 1;
  return items.map((t) => new Paragraph({ children: runs(t), numbering: { reference: "numeros", level: 0, instance: listaNumerada }, spacing: { after: 60, line: 264 } }));
}
function codigo(lineas) {
  return lineas.map((l, i) => new Paragraph({
    children: [new TextRun({ text: l === "" ? " " : l, font: MONO, size: 17 })],
    shading: { type: ShadingType.CLEAR, fill: "F2F2F2", color: "auto" },
    spacing: { after: 0, before: i === 0 ? 60 : 0, line: 240 },
    indent: { left: 140, right: 140 },
    keepLines: true, keepNext: i < lineas.length - 1,
  })).concat([new Paragraph({ children: [], spacing: { after: 80 } })]);
}
function nota(texto) {
  return new Paragraph({
    children: runs(texto, { size: 20 }), spacing: { before: 60, after: 140, line: 264 },
    shading: { type: ShadingType.CLEAR, fill: "EAF1F8", color: "auto" },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: AZUL2, space: 6 } },
    indent: { left: 200, right: 120 },
  });
}

// ------------------------------------------------------------------ leyendas con campos SEQ
function leyenda(tipo, clave, texto, despues = true) {
  const n = tipo === "Figura" ? numF(clave) : numT(clave);
  creadas[tipo].push(clave);
  const esperado = (tipo === "Figura" ? FIGS : TABS)[creadas[tipo].length - 1];
  if (esperado !== clave) throw new Error(`Orden de ${tipo}: se esperaba ${esperado} y llegó ${clave}`);
  return new Paragraph({
    style: "Caption",
    alignment: AlignmentType.CENTER,
    keepNext: !despues,
    spacing: { before: despues ? 60 : 160, after: despues ? 200 : 80 },
    children: [new TextRun({ text: `${tipo} `, bold: true }), new SimpleField(`SEQ ${tipo} \\* ARABIC`, String(n)),
      new TextRun({ text: ". ", bold: true }), ...runs(texto)],
  });
}

// ------------------------------------------------------------------ imágenes
function tamPng(ruta) {
  const b = fs.readFileSync(ruta);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20), data: b };
}
function imagen(ruta, anchoCm) {
  const { w, h, data } = tamPng(ruta);
  const ancho = Math.round((anchoCm / 2.54) * 96);
  return new ImageRun({ type: "png", data, transformation: { width: ancho, height: Math.round((ancho * h) / w) } });
}
function figura(clave, ruta, anchoCm, texto, detalle) {
  const partes = [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 40 }, children: [imagen(ruta, anchoCm)] }),
    leyenda("Figura", clave, texto, !detalle),
  ];
  if (detalle) partes.push(detalleFigura(detalle));
  return partes;
}
function detalleFigura(texto) {
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 200 }, children: runs(texto, { italics: true, size: 16, color: GRIS }) });
}
const salto = () => new Paragraph({ pageBreakBefore: true, children: [], spacing: { before: 0, after: 0 } });
const H2p = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)], pageBreakBefore: true });
function figurasPar(a, b) { // dos figuras lado a lado en una tabla sin bordes
  const sinBorde = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const bordes = { top: sinBorde, bottom: sinBorde, left: sinBorde, right: sinBorde };
  const celda = (f) => new TableCell({
    width: { size: ANCHO / 2, type: WidthType.DXA }, borders: bordes,
    children: [new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, children: [imagen(f.ruta, f.ancho)] }), leyenda("Figura", f.clave, f.texto, true)],
  });
  return new Table({
    width: { size: ANCHO, type: WidthType.DXA }, columnWidths: [ANCHO / 2, ANCHO / 2],
    borders: { top: sinBorde, bottom: sinBorde, left: sinBorde, right: sinBorde, insideHorizontal: sinBorde, insideVertical: sinBorde },
    rows: [new TableRow({ cantSplit: true, children: [celda(a), celda(b)] })],
  });
}

// ------------------------------------------------------------------ tablas
const bordeTabla = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const ALTO_UTIL_CM = (15840 - 2 * 1300) / 567; // alto útil de la página
const sinMarcas = (t) => String(t).replace(/\*\*|`/g, "");
function altoFilaCm(celdas, anchos, tam, negrita, margenV = 50) { // estimación conservadora del alto de una fila
  const em = (tam / 2) * 0.03528, alto = (tam / 2) * 1.2 * 0.03528;
  let lineas = 1;
  celdas.forEach((t, j) => {
    const util = anchos[j] / 567 - 0.32;
    const porLinea = Math.max(4, Math.floor(util / (em * (negrita ? 0.58 : 0.52))));
    const n = String(t).split("\n").reduce((s, l) => s + Math.max(1, Math.ceil((sinMarcas(l).length * 1.1) / porLinea)), 0);
    lineas = Math.max(lineas, n);
  });
  return lineas * alto + (2 * margenV) / 567 + 0.05;
}

function tabla(clave, titulo, encabezados, filas, anchosRel, op = {}) {
  const total = anchosRel.reduce((a, b) => a + b, 0);
  const anchos = anchosRel.map((a) => Math.floor((a / total) * ANCHO));
  anchos[anchos.length - 1] += ANCHO - anchos.reduce((a, b) => a + b, 0);
  const tam = op.tam || 17;
  const margenV = op.margenV || 50;
  const altoCm = altoFilaCm(encabezados, anchos, tam, true, margenV)
    + filas.reduce((s, f) => s + (Array.isArray(f) ? altoFilaCm(f, anchos, tam, false, margenV) : altoFilaCm([f.grupo], [ANCHO], tam, true, margenV)), 0);
  const entera = op.partir === undefined ? altoCm <= ALTO_UTIL_CM - 3 : !op.partir; // si cabe, no se divide entre páginas
  let filaActual = 0;
  const ultima = filas.length; // índice de la última fila (0 = encabezado)
  const celda = (texto, j, cab, fondo) => new TableCell({
    width: { size: anchos[j], type: WidthType.DXA },
    shading: cab ? { type: ShadingType.CLEAR, fill: AZUL, color: "auto" } : (fondo ? { type: ShadingType.CLEAR, fill: fondo, color: "auto" } : undefined),
    margins: { top: margenV, bottom: margenV, left: 90, right: 90 },
    verticalAlign: VerticalAlign.TOP,
    children: String(texto).split("\n").map((linea) => new Paragraph({
      spacing: { after: 0, line: 240 },
      keepNext: cab || (entera && filaActual < ultima),
      children: runs(linea, cab ? { bold: true, color: "FFFFFF", size: tam } : { size: tam }),
    })),
  });
  const rows = [new TableRow({ tableHeader: true, cantSplit: true, children: encabezados.map((e, j) => celda(e, j, true)) })];
  filas.forEach((f, i) => {
    filaActual = i + 1;
    const grupo = Array.isArray(f) ? null : f; // {grupo: "texto"} = fila de agrupación
    if (grupo) {
      rows.push(new TableRow({ cantSplit: true, children: [new TableCell({
        columnSpan: encabezados.length, width: { size: ANCHO, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: "D9E2F3", color: "auto" }, margins: { top: 40, bottom: 40, left: 90, right: 90 },
        children: [new Paragraph({ spacing: { after: 0 }, keepNext: true, children: runs(grupo.grupo, { bold: true, size: tam }) })],
      })] }));
      return;
    }
    rows.push(new TableRow({ cantSplit: true, children: f.map((c, j) => celda(c, j, false, i % 2 === 1 ? "F7F9FC" : null)) }));
  });
  tablasEnteras.push({ clave, entera, altoCm: Math.round(altoCm * 10) / 10 });
  return [
    leyenda("Tabla", clave, titulo, false),
    new Table({ width: { size: ANCHO, type: WidthType.DXA }, columnWidths: anchos, rows,
      borders: { top: bordeTabla, bottom: bordeTabla, left: bordeTabla, right: bordeTabla, insideHorizontal: bordeTabla, insideVertical: bordeTabla } }),
    new Paragraph({ children: [], spacing: { after: 120 } }),
  ];
}

const CAP = (n) => path.join(AN, "capturas", "anotadas", n + ".png");
const TER = (n) => path.join(AN, "capturas", "terminal", n + ".png");
const DIA = (n) => path.join(AN, "diagramas", n + ".png");
const MAC = (n) => path.join(AN, "capturas", "macos", n + ".png");
const EQUIPO = (carpeta, n) => path.join(AN, "capturas", carpeta, n + ".png");
const leerJson = (n) => fs.readFileSync(path.join(AN, "_datos_demo", n), "utf8").trimEnd().split("\n");
const PIE_CAPTURA = "Captura de la aplicación: ventana de 412 × 915 dp (densidad 2), Linux x86_64, 04/11/2026; marcadores numerados añadidos con Pillow.";
const PIE_SIMULADA = PIE_CAPTURA.replace("Pillow.", "Pillow. Entrada simulada (ondas senoidales), sin micrófono.");
const ANCHO_CAP = 5.4;

// ================================================================== CONTENIDO
const c = [];

// ------------------------------------------------------------------ ficha y control de versiones
c.push(new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun("Ficha del documento y control de versiones")] }));
c.push(P(`La ${T("ficha")} identifica el documento según la plantilla del CCII y la ${T("versiones")} registra su evolución.`));
c.push(...tabla("ficha", "Ficha del documento (plantilla CCII-N2016-02)", ["Campo", "Valor"], [
  ["Proyecto", "Wynik – aplicación de práctica musical con reconocimiento de notas en tiempo real"],
  ["Documento", "Anexo IV – Documentación Técnica de Programación"],
  ["Código del documento", "WYNIK-ANX-IV"],
  ["Versión y fecha", `${VERSION} · ${FECHA}`],
  ["Asignatura", ASIGNATURA],
  ["Profesor", PROFESOR],
  ["Institución y lugar", "Universidad Católica de Temuco (UCT) · Temuco, Chile"],
  ["Autores y roles", `${RICHARD}: Scrum Master y desarrollador\nSebastián Eduardo Contreras Vergara: desarrollador y tester\nBenjamín Ignacio Saavedra Mercado: desarrollador y tester\nJaviera Alejandra Celia Muñoz Toledo: desarrolladora y tester`],
  ["Código documentado", "Repositorio github.com/MansillsRich/Wynik-app, rama main, commit 358dcaf (03/11/2026)"],
  ["Aprobación", "Sujeta a revisión del profesor de la asignatura"],
  ["Clasificación", "Uso académico"],
  ["Palabras clave", "Python, Kivy, KivyMD, MusicXML, YIN, detección de altura, JSON, unittest, Ruff, pydoc"],
], [1, 3]));
c.push(...tabla("versiones", "Control de versiones", ["Versión", "Fecha", "Autor", "Descripción del cambio"], [
  ["2.0", "03/11/2026", "Sebastián Contreras", "Versión previa: estructura de carpetas, stack, módulos, pruebas (13/13), plataformas y matriz de funcionalidades."],
  [VERSION, FECHA, "Equipo Wynik", "Actualización integral contrastada con el código (commit 358dcaf): identificación del documento, autoría y roles; índices automáticos; estructura del repositorio, dependencias y licencias; algoritmo de detección de notas y persistencia JSON; interfaz con capturas anotadas; manual del programador (instalación, pruebas, cobertura, pydoc, Ruff y depuración); plataformas, prueba con piano real y estado de Android; trazabilidad, glosario, bibliografía en APA 7 y declaración de uso de inteligencia artificial."],
], [1.05, 1.1, 1.45, 5.9]));

// ------------------------------------------------------------------ índices automáticos
c.push(new Paragraph({ heading: HeadingLevel.TITLE, pageBreakBefore: true, children: [new TextRun("Índice")] }));
c.push(new TableOfContents("Índice", { hyperlink: true, headingStyleRange: "1-3" }));
c.push(new Paragraph({ heading: HeadingLevel.TITLE, pageBreakBefore: true, children: [new TextRun("Lista de figuras")] }));
c.push(new TableOfContents("Lista de figuras", { hyperlink: true, captionLabel: "Figura" }));
c.push(new Paragraph({ heading: HeadingLevel.TITLE, pageBreakBefore: true, children: [new TextRun("Lista de tablas")] }));
c.push(new TableOfContents("Lista de tablas", { hyperlink: true, captionLabel: "Tabla" }));

// ------------------------------------------------------------------ 1. Introducción
c.push(H1("1. Introducción"));
c.push(H2("1.1 Propósito"));
c.push(P("Este anexo reúne la información técnica que necesita un programador para comprender, instalar, ejecutar, probar, depurar y mantener **Wynik**, una aplicación en Python con Kivy/KivyMD que carga partituras MusicXML, escucha al usuario por el micrófono y le indica en tiempo real si toca las notas correctas."));
c.push(P("El contenido se contrastó con el código fuente del repositorio y con la salida de los comandos ejecutados el 04/11/2026. Las salidas completas se conservan en `docs/anexo_iv/evidencias/`, junto con los scripts que las generan en `docs/anexo_iv/`."));
c.push(H2("1.2 Alcance"));
c.push(P("El anexo describe la versión del repositorio `Wynik-app` en la rama `main`, commit `358dcaf` (03/11/2026). Cubre los lenguajes y herramientas, la estructura del repositorio a nivel de archivo, la configuración y las dependencias, el código fuente por paquete, los archivos KV, el algoritmo de detección de notas, la persistencia JSON, los recursos gráficos, la interfaz con capturas anotadas, el manual del programador y la trazabilidad entre funcionalidades, código y pruebas. No incluye el análisis de requisitos ni el manual del usuario final."));
c.push(P("En su estado actual, Wynik es un **prototipo de escritorio** que se ejecuta con Python en macOS, Windows y Linux. Su arquitectura separa el análisis de audio y la lógica musical de la interfaz, lo que permite llevarlos a Android; la versión para Android, empaquetada con Buildozer, se encuentra en desarrollo (apartado 5.8)."));
c.push(H2("1.3 Destinatarios"));
c.push(P(`El documento está dirigido a los integrantes del equipo, al profesor de la asignatura ${ASIGNATURA} y a quienes continúen el desarrollo. Se asume conocimiento básico de Python, de la línea de comandos y de Git.`));
c.push(H2("1.4 Normas y referencias aplicadas"));
c.push(P("De la plantilla del CCII (norma CCII-N2016-02, v1.0) se tomaron solo los apartados aplicables a un anexo: ficha del documento y control de versiones, normas y referencias, mecanismos de control de calidad (apartado 6.1), trazabilidad requisito → implementación → prueba (apartado 6.2) y definiciones y abreviaturas (apartado 8). La estructura y el nivel de detalle toman como referencia el Anexo IV del proyecto Aikén (Rodríguez Ramírez, 2019), adaptado a las tecnologías de Wynik según la " + T("equivalencias") + ". La bibliografía sigue el formato APA 7."));
c.push(...tabla("equivalencias", "Correspondencia entre la estructura de referencia (Aikén: Android, Java y Firebase) y Wynik", ["Referencia (Aikén)", "Equivalente en Wynik", "Apartado"], [
  ["AndroidManifest.xml + build.gradle", "`pyproject.toml` + `requirements-escritorio.in` / `.txt`", "3.2"],
  ["Paquetes Java", "Paquetes Python `audio/`, `nucleo/`, `servicios/`, `vistas/`", "3.4"],
  ["res/layout (XML)", "Archivos KV: `vistas/wynik.kv` y `vistas/componentes.kv`", "3.5"],
  ["res/drawable, mipmap", "Dibujo vectorial con el canvas de Kivy, fuente de iconos y paleta de `vistas/tema.py` (sin mapas de bits)", "3.8"],
  ["JavaDoc", "Docstrings + HTML generado con pydoc", "5.4"],
  ["Firebase (Auth, Firestore, Storage)", "Persistencia local en tres archivos JSON, sin inicio de sesión ni servicios remotos", "3.7"],
  ["Depurar y probar (AVD / dispositivo físico)", "Ejecución en escritorio, pruebas unittest, entrada simulada sin micrófono y estado de la versión para Android", "5.5–5.8"],
], [2.2, 3.6, 1.2]));
c.push(H2("1.5 Convenciones"));
c.push(B("Las rutas son relativas a la raíz del repositorio (`Wynik-app/`); el código, los comandos y los nombres de archivo van en `monoespaciado`."));
c.push(B("**Validado** indica que la ejecución se comprobó con fecha, entorno y evidencia (captura o salida de comando). **Soportado por dependencias** indica que las dependencias declaran soporte para la plataforma, sin una ejecución registrada."));

// ------------------------------------------------------------------ 2. Lenguajes y entorno
c.push(H1("2. Lenguajes y entorno de desarrollo"));
c.push(H2("2.1 Lenguajes"));
c.push(B("**Python 3.13 o superior** (`requires-python = \">=3.13\"` en `pyproject.toml`; Ruff configurado con `target-version = \"py313\"`). Implementa la lógica musical, el procesamiento de audio, los servicios y la persistencia."));
c.push(B("**Lenguaje KV** de Kivy, para declarar la interfaz por separado de la lógica: `vistas/wynik.kv` (pantallas) y `vistas/componentes.kv` (componentes)."));
c.push(B("**MusicXML** (`.musicxml`, `.xml` y `.mxl`) como formato de entrada de las partituras, leído con music21."));
c.push(B("**JSON** para guardar ajustes, historial de partituras y progreso."));
c.push(H2("2.2 Framework de interfaz"));
c.push(P("**Kivy 2.3.1** aporta la ventana, los eventos, el `ScreenManager`, el canvas de dibujo, el reloj (`Clock`) y la reproducción de audio (`SoundLoader`). **KivyMD 2.0.0** se usa de forma acotada: `MDApp` como clase base de la aplicación y su tema, la fuente de iconos «Icons» (`kivymd.icon_definitions.md_icons`), las fuentes Roboto y `MDSnackbar` para los avisos emergentes. Los componentes visibles (botones, opciones, tarjetas, barras) son propios y están en `vistas/componentes.py` y `vistas/componentes.kv`; las pantallas derivan de `kivy.uix.screenmanager.Screen`."));
c.push(H2("2.3 Herramientas y entornos verificados"));
c.push(P(`La ${T("herramientas")} lista las herramientas y los entornos utilizados, con su versión y la evidencia correspondiente.`));
c.push(...tabla("herramientas", "Herramientas y entornos utilizados", ["Herramienta", "Versión", "Uso", "Evidencia"], [
  ["Python (macOS, Apple Silicon)", "3.13.16 (Homebrew)", "Desarrollo; entorno virtual `../.venv`; 13/13 pruebas", "`.venv/pyvenv.cfg`; " + F("mac_pruebas")],
  ["Python (Windows 11)", "3.12.3 (64 bits, AMD64)", "Desarrollo; 13/13 pruebas", F("windows_pruebas")],
  ["Python (Fedora Linux)", "3.14.10 (x86_64)", "Desarrollo; 13/13 pruebas", F("fedora_pruebas")],
  ["Python (Linux x86_64, Ubuntu 24.04)", "3.13.18", "Instalación, pruebas, cobertura, capturas y pydoc", "`evidencias/entorno.txt`"],
  ["pip / uv", "pip 26.2.1 (macOS); uv (Ubuntu)", "Instalación de dependencias; uv generó `requirements-escritorio.txt`", "Metadatos del `.venv`; cabecera del `.txt`"],
  ["Git y GitHub", "Remoto `github.com/MansillsRich/Wynik-app`, rama `main`, 11 commits", "Control de versiones", "`git log`, `git remote -v`"],
  ["unittest", "Biblioteca estándar", "Pruebas automatizadas (13)", "`evidencias/unittest.txt`"],
  ["Ruff", "0.17.3 (el proyecto exige ≥ 0.5.0)", "Análisis estático y orden de importaciones", "`evidencias/ruff.txt`"],
  ["coverage.py", "7.17.1", "Medición de la cobertura de las pruebas", "`evidencias/cobertura.txt`"],
  ["pydoc", "Biblioteca estándar", "Documentación HTML desde los docstrings", "`docs/`, `docs/anexo_iv/pydoc/`"],
  ["Xvfb", "Paquete del sistema (Ubuntu)", "Pantalla virtual para las capturas de la interfaz", "`capturar_pantallas.py`"],
  ["Visual Studio Code", "Última versión disponible", "Editor de código del equipo", "Configuración no versionada (`.gitignore` excluye `.vscode/`)"],
], [2.1, 1.7, 2.6, 1.7]));

// ------------------------------------------------------------------ 3. Organización
c.push(H1("3. Organización del proyecto"));
c.push(H2("3.1 Estructura del repositorio"));
c.push(P(`El repositorio contiene 111 archivos versionados (\`git ls-files\`): 54 módulos Python, 2 archivos KV, la configuración, el README y la carpeta \`docs/\` con la documentación pydoc. La ${F("arbol")} muestra el árbol y la ${T("estructura")} describe cada archivo en una línea.`));
c.push(...figura("arbol", TER("arbol_repositorio"), 15.5, "Árbol del repositorio a nivel de archivo (commit 358dcaf)", "Salida de `git ls-files` renderizada como imagen por `generar_evidencias.py`."));
c.push(P("Además de los archivos versionados, la aplicación crea en la carpeta de datos (por defecto, la raíz del proyecto) `ajustes_wynik.json`, `historial_partituras.json`, `progreso_sesiones.json` y `.cache/temp_guia.wav`. Son datos locales y `.gitignore` los excluye, junto con `.venv/`, `__pycache__/` y los archivos de herramientas de desarrollo."));
const G = (t) => ({ grupo: t });
c.push(...tabla("estructura", "Estructura del repositorio a nivel de archivo, con la responsabilidad de cada archivo", ["Archivo", "Descripción"], [
  G("Raíz"),
  ["main.py", "Punto de entrada: fija la ventana de escritorio (1040 × 720, mínimo 360 × 340), inicializa los proveedores de audio y ejecuta `WynikApp`."],
  ["pyproject.toml", "Metadatos del proyecto, `requires-python`, dependencias mínimas, dependencias opcionales de desarrollo y configuración de pytest y Ruff."],
  ["requirements-escritorio.in", "Dependencias directas fijadas (5 paquetes)."],
  ["requirements-escritorio.txt", "Resolución completa fijada (42 paquetes) generada con `uv pip compile`."],
  ["README.md", "Descripción, funcionalidades, arquitectura e instalación de escritorio."],
  [".gitignore", "Excluye entornos, cachés, datos locales (JSON, WAV) y archivos de herramientas de desarrollo."],
  G("audio/ — captura y análisis de audio (solo NumPy; sounddevice se importa al abrir el micrófono)"),
  ["__init__.py", "Descripción del paquete; no importa nada al cargarse."],
  ["captura.py", "`CapturaBase`, `CapturaSounddevice` (micrófono de escritorio), `CapturaManual` (sin dispositivo), `ColaDeBloques`, `BloqueAudio` y `dispositivos_de_entrada`."],
  ["escucha.py", "`MotorDeEscucha`: captura + cola + `Analizador` en un hilo propio; calibración del ruido."],
  ["analizador.py", "`Analizador`: bloques → saltos de 10 ms → nivel, flujo espectral y altura YIN → eventos."],
  ["estimador_yin.py", "`EstimadorYin` (YIN vectorizado), `EstimacionAltura` y `refinar_fundamental`."],
  ["segmentador.py", "`Segmentador`: máquina de estados de ataques, confirmación y fin de nota."],
  ["senal.py", "Nivel en dBFS, `PerfilDeRuido`, calibración y detección de interferencias (zumbido de red)."],
  ["guia.py", "Síntesis de la guía de audio (timbres seno, piano y guitarra) y escritura WAV con `wave`."],
  G("nucleo/ — modelo musical y reglas, sin Kivy ni audio"),
  ["__init__.py", "Descripción del paquete."],
  ["musica.py", "`Altura`, conversiones MIDI ↔ Hz, `comparar_frecuencia` (tolerancias en cents), `Evento`, `Parte`, `MapaTempo`, `Partitura`, `Ataque`."],
  ["eventos.py", "`TipoEvento` y `EventoInterpretacion`: contrato entre el análisis de audio y la sesión."],
  ["instrumentos.py", "`PerfilInstrumento` (piano, guitarra, flauta experimental), `ParametrosDeteccion` y afinaciones de guitarra."],
  ["importador_musicxml.py", "`importar_musicxml` con music21: partes, voces, ligaduras, acordes, tempo y transposición de guitarra."],
  ["sesion.py", "`SesionDePractica` (ventanas, alineación, estados por nota), `notas_esperadas` y `SesionProgreso`."],
  ["notacion.py", "`disponer`: maquetación del pentagrama (claves, armaduras, figuras, alteraciones)."],
  ["digitacion.py", "Posiciones de guitarra, diagramas de acordes y teclas de piano para la guía visual."],
  G("servicios/ — fachadas y lógica de aplicación sin Kivy"),
  ["__init__.py", "Importación bajo demanda (PEP 562) de las funciones públicas."],
  ["practica_service.py", "`ControladorPractica`: micrófono, calibración, cuenta previa y sesión; cola de eventos entre hilos."],
  ["partitura_service.py", "`cargar_partitura`, `cargar_partitura_estructurada` y `ataque_a_nota`."],
  ["audio_service.py", "`generar_guia`, `generar_audio_guia`, `duracion_wav` y `formatear_tiempo`."],
  ["reproductor_guia.py", "`ReproductorGuia`: estado de reproducción de la guía sobre `SoundLoader`."],
  ["detector_service.py", "`DetectorDeNotas` sobre `MotorDeEscucha` y `frecuencia_a_nota`."],
  ["notacion_service.py", "`nombre_para_mostrar`, `paso_diatonico` y `nota_coincide`."],
  ["almacenamiento.py", "Directorio de datos (`WYNIK_DATOS`, Android) y lectura/escritura atómica de JSON."],
  ["ajustes_service.py", "`AjustesPractica` (13 campos) con corrección de valores fuera de rango."],
  ["historial_service.py", "Historial de partituras importadas y texto de detalle para «Mis partituras»."],
  ["progreso_service.py", "Registro y lectura de sesiones terminadas; resumen por partitura."],
  G("vistas/ — interfaz Kivy/KivyMD"),
  ["__init__.py", "Exporta pantallas, widgets, `WynikApp` y `KV_PATH`."],
  ["app.py", "`WynikApp` (MDApp): navegación, propiedades que muestra el KV, tick de la práctica, guía y diálogos."],
  ["wynik.kv", "`ScreenManager` y las siete pantallas."],
  ["componentes.kv / componentes.py", "Componentes propios: `Etiqueta`, `Boton`, `Opcion`, `Superficie`, `BarraSuperior`, `MedidorCents`, `AnilloProgreso`, `DisposicionPractica`, `Ocultable`…"],
  ["dialogs.py", "Diálogos modales y selector de archivos MusicXML."],
  ["avisos.py", "`SnackbarWynik`: corrige la creación del snackbar de KivyMD en macOS."],
  ["fuentes.py", "Registro de DejaVu Sans (símbolos musicales) y Roboto."],
  ["tema.py", "Paleta, tipografía, medidas y estados visuales."],
  ["screens/ (8 archivos)", "`MenuScreen`, `ElegirPartituraScreen`, `AjustesInicioScreen`, `InterpreteScreen`, `PartituraSimpleScreen`, `AjustesScreen`, `ProgresoScreen` y su `__init__.py`."],
  ["widgets/ (6 archivos)", "`PartituraWidget`, `PartituraSimpleWidget`, `GuiaInstrumentoWidget`, `ilustraciones.py`, `dibujo.py` y `__init__.py`."],
  G("tests/ — pruebas unittest"),
  ["test_ajustes.py · test_almacenamiento.py · test_musica.py · test_progreso.py", "13 pruebas en total (detalle en la " + T("pruebas") + ")."],
  ["__init__.py", "Añade la raíz del repositorio a `sys.path`."],
  G("docs/"),
  ["49 archivos .html + _pydoc.css", "Documentación pydoc versionada en el commit 358dcaf (48 módulos e índice)."],
], [2.3, 5.7], { tam: 16 }));

c.push(H2("3.2 Configuración y dependencias"));
c.push(P("La configuración se reparte en tres archivos que cumplen papeles distintos:"));
c.push(B("`pyproject.toml` declara el proyecto (`wynik` 0.1.0), `requires-python = \">=3.13\"`, las dependencias con versión mínima (`kivy>=2.3.1`, `kivymd>=2.0.0`, `numpy>=2.5.3`, `sounddevice>=0.5.6`, `music21>=10.5.0`), las dependencias opcionales `dev` (`pytest>=8.0.0`, `ruff>=0.5.0`) y la configuración de Ruff (`line-length = 100`, reglas E, F, W e I, sin E402 ni E501)."));
c.push(B("`requirements-escritorio.in` fija con `==` las cinco dependencias directas."));
c.push(B("`requirements-escritorio.txt` es la resolución completa (42 paquetes, cinco solo para Windows mediante marcadores `sys_platform == 'win32'`), generada a partir del `.in`. Es el archivo que se instala."));
c.push(...codigo([
  "# Comando que figura en la cabecera de requirements-escritorio.txt",
  "uv pip compile requirements-escritorio.in -c requirements.txt --universal \\",
  "    --python-version 3.13 -o requirements-escritorio.txt",
]));
c.push(P("El archivo de restricciones `requirements.txt` que usa el comando no forma parte del repositorio; sin la opción `-c`, la resolución puede seleccionar versiones transitivas más recientes. Las pruebas se ejecutan con unittest; pytest figura solo como dependencia opcional de desarrollo."));
c.push(P(`La ${T("dependencias")} contrasta cada dependencia directa en los cuatro lugares donde aparece.`));
c.push(...tabla("dependencias", "Dependencias directas: versión declarada, fijada e instalada", ["Paquete", "pyproject.toml", ".in / .txt", "Instalada (macOS)", "Instalada (Ubuntu)", "Origen"], [
  ["kivy", ">= 2.3.1", "2.3.1", "2.3.1", "2.3.1", "PyPI"],
  ["kivymd", ">= 2.0.0", "2.0.0", "2.0.0", "2.0.0", "PyPI; `kivymd._version`: release = False, fecha 2026-08-06"],
  ["numpy", ">= 2.5.3", "2.5.3", "2.5.3", "2.5.3", "PyPI"],
  ["sounddevice", ">= 0.5.6", "0.5.6", "0.5.6", "0.5.6", "PyPI"],
  ["music21", ">= 10.5.0", "10.5.0", "10.5.0", "10.5.0", "PyPI"],
], [1.2, 1.6, 0.9, 1.25, 1.25, 2.6]));
c.push(P("En el entorno de macOS, la versión instalada se obtuvo de los metadatos `*.dist-info` (37 paquetes, sin los cinco exclusivos de Windows). KivyMD se instaló desde PyPI, como indica la ausencia de `direct_url.json`, y la versión 2.0.0 figura publicada en ese índice. librosa ya no forma parte del proyecto: según la cabecera del archivo `.in`, desde el «Ciclo 2» la detección usa una implementación propia de YIN con NumPy."));

c.push(H2("3.3 Librerías de terceros y licencias"));
c.push(P(`La ${T("licencias")} resume las librerías directas y las transitivas más relevantes, con la licencia declarada por cada paquete instalado.`));
c.push(...tabla("licencias", "Librerías de terceros y sus licencias", ["Librería", "Versión", "Licencia", "Uso en Wynik"], [
  ["Kivy", "2.3.1", "MIT", "Ventana, eventos, pantallas, dibujo, reloj y audio"],
  ["KivyMD", "2.0.0", "MIT", "`MDApp`, tema, fuente de iconos, Roboto y snackbar"],
  ["NumPy", "2.5.3", "BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0", "FFT, YIN, niveles y síntesis de la guía"],
  ["sounddevice", "0.5.6", "MIT", "Captura del micrófono (PortAudio)"],
  ["music21", "10.5.0", "BSD-3-Clause", "Lectura de MusicXML"],
  ["Pillow (vía KivyMD)", "12.3.0", "MIT-CMU", "Carga de imágenes en KivyMD"],
  ["materialyoucolor (vía KivyMD)", "3.0.4", "MIT", "Colores dinámicos de KivyMD"],
  ["materialshapes (vía KivyMD)", "0.3", "MIT", "Formas de KivyMD"],
  ["pycairo (vía materialshapes)", "1.29.1", "LGPL-2.1-only OR MPL-1.1", "Dibujo de formas; se compila en macOS y Linux"],
  ["asynckivy / asyncgui (vía KivyMD)", "0.6.4 / 0.6.3", "MIT", "Tareas asíncronas de KivyMD"],
  ["matplotlib (vía music21)", "3.11.2", "Licencia propia basada en la PSF", "Dependencia de music21; Wynik no la usa"],
  ["requests (vía Kivy y music21)", "2.34.2", "Apache-2.0", "Dependencia transitiva"],
], [2.2, 1, 2.6, 2.8]));

c.push(H2("3.4 Código fuente por paquete"));
c.push(P(`La ${F("dependencias")} muestra las dependencias entre paquetes obtenidas de las sentencias \`import\` del código: \`nucleo/\` no depende de ningún otro paquete del proyecto, \`audio/\` solo depende de \`nucleo/\`, \`servicios/\` une ambos y \`vistas/\` los usa a todos. music21 y sounddevice se importan solo cuando se necesitan (al leer un archivo o al abrir el micrófono). La ${F("flujo")} sigue el dato desde el micrófono hasta la interfaz y el JSON, con los tres hilos que intervienen.`));
c.push(...figura("dependencias", DIA("dependencias_paquetes"), 14, "Dependencias entre paquetes y con las librerías externas", "Obtenidas de las sentencias `import` del código. Flechas continuas: paquetes del proyecto; discontinuas: librerías externas."));
c.push(...figura("flujo", DIA("flujo_datos"), 16, "Flujo de datos: micrófono → captura → detección → comparación → puntaje → interfaz → JSON", "Cada recuadro de color es un hilo de ejecución; fuente: `diagramas/flujo_datos.dot`."));
c.push(P(`Las tablas ${numT("audio")} a ${numT("vistas")} describen las clases y funciones principales de cada paquete y quién las llama. La estadística de docstrings está en el apartado 5.4.`));
c.push(...tabla("audio", "Paquete audio/: clases y funciones principales", ["Elemento", "Responsabilidad", "Lo usa"], [
  ["`CapturaSounddevice` (captura.py)", "Abre `sounddevice.InputStream` (mono, float32, bloques de 1024 muestras, frecuencia del dispositivo) y entrega cada bloque a la cola desde el callback.", "`MotorDeEscucha`, `ControladorPractica`, `WynikApp._crear_captura`"],
  ["`CapturaManual` (captura.py)", "Misma interfaz sin dispositivo: los bloques llegan llamando a `_callback`.", "Pruebas y simulaciones sin micrófono"],
  ["`ColaDeBloques` (captura.py)", "Cola acotada segura entre hilos (64 bloques); llena, descarta el bloque más antiguo.", "`CapturaBase`, `MotorDeEscucha`"],
  ["`MotorDeEscucha` (escucha.py)", "Hilo de análisis `wynik-analisis-N`: cada 5 ms saca los bloques y los pasa al `Analizador`; calibra el ruido.", "`ControladorPractica`, `WynikApp.calibrar_ahora`"],
  ["`Analizador` (analizador.py)", "Saltos de 10 ms: nivel, flujo espectral, YIN y refinamiento; entrega tramas al `Segmentador`.", "`MotorDeEscucha`"],
  ["`EstimadorYin` (estimador_yin.py)", "YIN vectorizado por lotes con FFT; `refinar_fundamental` corrige la inarmonicidad del piano.", "`Analizador`, `calibrar`"],
  ["`Segmentador` (segmentador.py)", "Máquina de estados: ataque, confirmación, diagnóstico y fin de nota → `EventoInterpretacion`.", "`Analizador`"],
  ["`PerfilDeRuido`, `calibrar`, `es_interferencia` (senal.py)", "Niveles de silencio y mínimo, tonos estacionarios del fondo y zumbido de red.", "`Analizador`, `MotorDeEscucha`"],
  ["`sintetizar`, `escribir_wav` (guia.py)", "Guía de audio a 22 050 Hz con timbre seno, piano o guitarra; WAV mono de 16 bits.", "`servicios.audio_service`"],
], [2.4, 4.3, 2.3]));
c.push(...tabla("nucleo", "Paquete nucleo/: clases y funciones principales", ["Elemento", "Responsabilidad", "Lo usa"], [
  ["`Altura`, `midi_a_frecuencia`, `frecuencia_a_midi` (musica.py)", "Alturas con su grafía original y conversiones MIDI ↔ Hz (La4 = 440 Hz por defecto).", "Todo el proyecto"],
  ["`comparar_frecuencia`, `EstadoAltura` (musica.py)", "Clasifica la altura tocada: correcta, desafinada, octava incorrecta o nota incorrecta.", "`SesionDePractica`"],
  ["`Partitura`, `Parte`, `Evento`, `MapaTempo`, `Ataque` (musica.py)", "Modelo de la partitura; `linea_de_practica` agrupa ligaduras y acordes en ataques.", "Importador, servicios, vistas"],
  ["`importar_musicxml` (importador_musicxml.py)", "Lee MusicXML con music21 y decide la transposición de la guitarra.", "`partitura_service`"],
  ["`TipoEvento`, `EventoInterpretacion` (eventos.py)", "Eventos NOTA, FIN, SENAL_DEBIL, BAJA_CONFIANZA, INESTABLE y FUERA_DE_RANGO con instante, frecuencia, confianza y latencia.", "`Segmentador`, `SesionDePractica`, `WynikApp`"],
  ["`PerfilInstrumento`, `ParametrosDeteccion` (instrumentos.py)", "Rango, transposición, afinaciones y parámetros del detector por instrumento.", "`Analizador`, `WynikApp`"],
  ["`SesionDePractica`, `ConfiguracionSesion`, `EstadoNota` (sesion.py)", "Compara eventos con la partitura en el tiempo y produce un `Cambio` por nota; `resumen` calcula la precisión.", "`ControladorPractica`"],
  ["`SesionProgreso` (sesion.py)", "Resultado de una sesión con `to_dict` / `from_dict` para el JSON.", "`progreso_service`"],
  ["`disponer` (notacion.py) · digitacion.py", "Maquetación del pentagrama; posiciones de guitarra y teclas de piano.", "`PartituraWidget`, `GuiaInstrumentoWidget`"],
], [2.6, 4.2, 2.2]));
c.push(...tabla("servicios", "Paquete servicios/: clases y funciones principales", ["Elemento", "Responsabilidad", "Lo usa"], [
  ["`ControladorPractica` (practica_service.py)", "Secuencia Empezar → calibración (opcional, 1 s) → cuenta previa → sesión; pausa y reanudación; cola de eventos del hilo de análisis.", "`WynikApp.iniciar_escucha`, `_tick`"],
  ["`cargar_partitura_estructurada`, `ataque_a_nota` (partitura_service.py)", "Fachada del importador y conversión de cada ataque al diccionario que usa la interfaz.", "`WynikApp._cargar_partitura`"],
  ["`generar_guia` (audio_service.py) · `ReproductorGuia` (reproductor_guia.py)", "Genera la guía WAV con los tiempos de la partitura y gestiona su reproducción.", "`WynikApp.preparar_audio_guia`"],
  ["`leer_json`, `escribir_json`, `configurar_directorio` (almacenamiento.py)", "Ubicación de los datos y escritura atómica (archivo temporal + `os.replace`).", "Servicios de ajustes y progreso"],
  ["`AjustesPractica`, `cargar_ajustes`, `guardar_ajustes` (ajustes_service.py)", "Ajustes persistentes con corrección de valores fuera de rango.", "`WynikApp._cargar_ajustes`, `_guardar_ajustes`"],
  ["`cargar_historial`, `agregar_al_historial` (historial_service.py)", "Historial de partituras importadas.", "`WynikApp`"],
  ["`registrar_sesion`, `cargar_progreso`, `resumen_por_partitura` (progreso_service.py)", "Sesiones terminadas (máximo 500) y resumen por partitura.", "`WynikApp._terminar`, `refrescar_progreso`"],
], [2.8, 4.1, 2.1]));
c.push(...tabla("vistas", "Paquete vistas/: clases principales", ["Elemento", "Responsabilidad", "Lo usa"], [
  ["`WynikApp` (app.py)", "Carga los KV una sola vez en `build()`, traduce el estado de la práctica a propiedades Kivy, navega entre pantallas y ejecuta `_tick` a 30 Hz.", "`main.py`"],
  ["Pantallas (screens/)", "Siete subclases de `Screen` con poca lógica (`on_enter`, `on_leave`); el diseño está en `wynik.kv`.", "`ScreenManager` de `wynik.kv`"],
  ["`PartituraWidget`, `PartituraSimpleWidget` (widgets/)", "Dibujan el pentagrama o la cinta de notas con el estado de cada nota.", "`InterpreteScreen`, `PartituraSimpleScreen`"],
  ["`GuiaInstrumentoWidget` (widgets/)", "Teclado o diapasón con la nota esperada y la detectada.", "Pantallas de práctica"],
  ["Componentes (componentes.py / .kv)", "Controles propios: `Boton`, `Opcion`, `GrupoOpciones`, `Superficie`, `BarraSuperior`, `Chip`, `EstadoPildora`, `MedidorCents`, `TiraResultados`, `AnilloProgreso`, `GraficoSesiones`, `DisposicionPractica`.", "`wynik.kv`, `app.py`, `dialogs.py`"],
  ["`mostrar_dialogo`, `abrir_selector_de_archivo` (dialogs.py)", "Diálogos modales y selector `FileChooserListView` con filtro MusicXML.", "`WynikApp`"],
], [2.6, 4.3, 2.1]));

c.push(H2("3.5 Archivos KV"));
c.push(P(`La interfaz se declara en dos archivos KV que \`WynikApp.build()\` carga una sola vez; \`load_kv\` se anula a propósito porque Kivy cargaba \`wynik.kv\` por el nombre de la clase y cada regla se aplicaba dos veces. La ${T("kv")} resume su contenido.`));
c.push(...tabla("kv", "Archivos KV y reglas que definen", ["Archivo", "Contenido", "Reglas principales"], [
  ["`vistas/wynik.kv` (1079 líneas)", "Raíz `ScreenManager` con transición `SlideTransition` (0,22 s), fondo común de `Screen` y la disposición de las siete pantallas.", "`<MenuScreen>` (menu), `<ElegirPartituraScreen>` (elegir_partitura), `<AjustesInicioScreen>` (ajustes_inicio), `<InterpreteScreen>` (interprete), `<PartituraSimpleScreen>` (partitura_simple), `<AjustesScreen>` (ajustes), `<ProgresoScreen>` (progreso)"],
  ["`vistas/componentes.kv` (505 líneas)", "27 reglas de componentes reutilizables con los colores y medidas de `tema.py`.", "`Etiqueta`, `Rotulo`, `Seccion`, `Secundario`, `Icono`, `Boton`, `BotonIcono`, `Superficie`, `Tarjeta`, `TarjetaAjuste`, `Opcion`, `GrupoOpciones`, `Paso`, `Chip`, `EstadoPildora`, `BarraSuperior`, `BarraAccion`, `Mosaico`, `FilaPartitura`, `FilaSesion`, `FilaPartituraProgreso`…"],
], [2.1, 3.1, 3.8]));

c.push(H2("3.6 Algoritmo de detección de notas"));
c.push(P("La detección es monofónica (una nota a la vez) y se divide en cinco etapas. El código cita como base el estimador YIN (de Cheveigné y Kawahara, 2002) y, para los ataques, una versión simplificada de SuperFlux (Böck y Widmer, 2013). Ambas están implementadas con NumPy, sin librosa."));
c.push(H3("3.6.1 Captura y paso entre hilos"));
c.push(P("`CapturaSounddevice` abre el micrófono con la **frecuencia de muestreo del dispositivo** (`default_samplerate`; habitualmente 44 100 o 48 000 Hz, no una constante del código), un canal, `float32` y **bloques de 1024 muestras** (unos 21 ms a 48 kHz). El callback de PortAudio solo copia el bloque, resta la componente continua, anota el instante y el número de su primera muestra y lo deja en `ColaDeBloques`. Ningún cálculo de altura se hace dentro del callback."));
c.push(P("El hilo de análisis de `MotorDeEscucha` vacía la cola cada 5 ms y produce `EventoInterpretacion`. Cada evento llega por `ControladorPractica.encolar_evento` a una `queue.SimpleQueue`. El hilo de la interfaz ejecuta `WynikApp._tick` cada 1/30 s con `Clock.schedule_interval`; ahí `ControladorPractica.actualizar()` vacía la cola, pasa cada evento a `SesionDePractica` y aplica los cambios a las propiedades Kivy que observa el KV. Así, ningún objeto de Kivy se toca fuera del hilo de la interfaz (" + F("flujo") + ")."));
c.push(H3("3.6.2 Estimación de altura (YIN)"));
c.push(P("Por cada salto de 10 ms, `Analizador` toma la trama que termina en ese salto y `EstimadorYin` calcula: (1) la función de diferencia d(τ) mediante correlación cruzada con FFT y sumas acumuladas; (2) la diferencia media acumulada normalizada d′(τ); (3) el primer mínimo de d′(τ) bajo el umbral absoluto (0,30 en los perfiles); (4) la interpolación parabólica del mínimo; y (5) una comprobación de subarmónicos por debajo de 1 kHz que evita errores de octava en notas graves. La aperiodicidad d′(τ) da la confianza (1 − d′). En el piano, `refinar_fundamental` busca el pico espectral real entre −60 y +15 cents de la estimación (ventana de Hann, FFT de 65 536 puntos), porque la inarmonicidad de las cuerdas eleva unos 16 cents la estimación de YIN."));
c.push(P("El rango de búsqueda es el del instrumento con un margen: piano de A0 − 2 semitonos a C8 + 4 semitonos (24,50–5274,0 Hz) y guitarra de E2 − 12 a E6 + 12 semitonos (41,20–2637,0 Hz), limitado al 45 % de la frecuencia de muestreo. La trama necesaria crece con la nota más grave: 81,7 ms en piano y 48,6 ms en guitarra (" + T("parametros") + ")."));
c.push(H3("3.6.3 Segmentación en eventos"));
c.push(P("`Segmentador` convierte las tramas en eventos. Un ataque se detecta por **energía** (el nivel sube 6 dB sobre el mínimo de los 50 ms anteriores) o por **flujo espectral** (ventana de Hann de 20 ms, compresión log10(1 + 1000·|X|), filtro de máximos de 3 bandas), y también hay candidatos sin ataque cuando aparece una altura estable o la altura cambia al menos 0,75 semitonos (legato). Un candidato se **confirma** con 3 tramas periódicas seguidas dentro de ±50 cents de su mediana; si no se confirma en 150 ms (más la trama) se informa como señal débil, baja confianza o altura inestable. La nota termina tras 40 ms de silencio o 120 ms sin periodicidad (evento FIN). Los tonos estables a ±20 cents de 50/60 Hz y sus armónicos, sin ataque, se tratan como zumbido de red."));
c.push(H3("3.6.4 Conversión de frecuencia a nota y tolerancia en cents"));
c.push(P("La frecuencia confirmada se convierte a número MIDI fraccionario con m = 69 + 12·log2(f / La4), donde La4 es 440 Hz por defecto y se ajusta entre 430 y 450 Hz. La nota más cercana es ⌊m + 0,5⌋ y la desviación, (m − nota)·100 cents. `comparar_frecuencia` aplica las tolerancias de la " + T("clasificacion") + "; la precisión de la sesión es aciertos / notas evaluables, donde un acierto es una nota correcta o desafinada y los acordes no se evalúan."));
c.push(...tabla("clasificacion", "Clasificación de una nota detectada frente a la esperada (`nucleo/musica.py`)", ["Desviación respecto de la nota esperada", "Estado", "¿Cuenta como acierto?"], [
  ["|desviación| ≤ 25 cents", "CORRECTA (afinada)", "Sí"],
  ["25 < |desviación| ≤ 50 cents", "DESAFINADA (misma nota y octava)", "Sí"],
  ["> 50 cents y misma clase de altura", "OCTAVA_INCORRECTA", "No"],
  ["> 50 cents y otra clase de altura", "NOTA_INCORRECTA", "No"],
  ["Sin ataque en la ventana / solo diagnósticos", "OMITIDA, SENAL_INSUFICIENTE, BAJA_CONFIANZA o FUERA_DE_RANGO", "No"],
  ["Acorde (detector monofónico)", "SIN_EVALUAR", "No se cuenta"],
], [3.3, 3.6, 1.6]));
c.push(H3("3.6.5 Sincronización con el tempo"));
c.push(P("`notas_esperadas` toma el inicio y la duración de cada ataque en segundos según el tempo de la partitura (con sus cambios) y los divide por el factor de tempo elegido (50–150 %). En el modo **Seguir el tempo**, cada nota tiene una ventana de ±150 ms (configurable a 100, 200 o 250 ms) alrededor de su inicio esperado; la primera nota admite hasta 500 ms de retraso y el primer acierto fija el desfase entre el reloj y la partitura. Si los tres últimos aciertos llegan desplazados en el mismo sentido, el desfase se corrige con su media. La ventana se cierra 0,35 s después de su fin (`MARGEN_CIERRE_S`) para no perder ataques ya tocados que aún se están confirmando. En el modo **Esperar cada nota**, la partitura avanza solo con un acierto. Antes de empezar hay una cuenta previa visual (3 pulsos por defecto, de 60/tempo segundos acotados a 0,3–1,2 s)."));
c.push(H3("3.6.6 Parámetros efectivos"));
c.push(P(`Los valores de la ${T("parametros")} se obtuvieron instanciando las clases del código (\`generar_evidencias.py\`). Según el docstring de \`ParametrosDeteccion\`, corresponden a valores iniciales ajustados con señales sintéticas; la prueba con piano real se describe en el apartado 5.8.1.`));
c.push(...tabla("parametros", "Parámetros del detector calculados con las clases del código (`evidencias/parametros_deteccion.txt`)", ["Parámetro", "Piano", "Guitarra", "Origen en el código"], [
  ["Frecuencia de muestreo", "La del dispositivo (44 100 / 48 000 Hz)", "Ídem", "`CapturaSounddevice.abrir`"],
  ["Bloque de captura · cola", "1024 muestras · 64 bloques", "Ídem", "`TAM_BLOQUE`, `CAPACIDAD_COLA_BLOQUES`"],
  ["Salto de análisis", "10 ms (480 muestras a 48 kHz)", "Ídem", "`DURACION_SALTO_S`"],
  ["Rango de búsqueda", "24,50–5274,0 Hz", "41,20–2637,0 Hz", "`PerfilInstrumento.rango_busqueda_hz`"],
  ["Trama YIN a 48 kHz", "3923 muestras (81,7 ms)", "2333 muestras (48,6 ms)", "`EstimadorYin.longitud_trama`"],
  ["Umbral YIN · aperiodicidad máxima", "0,30 · 0,30", "0,30 · 0,30", "`ParametrosDeteccion`"],
  ["Refinamiento espectral", "Sí", "No", "`refinar_fundamental`"],
  ["Confirmación", "3 tramas a ±50 cents; máximo 150 ms", "Ídem", "`tramas_confirmacion`, `confirmacion_max_s`"],
  ["Latencia mínima de confirmación", "111,7 ms", "78,6 ms", "`Analizador.latencia_minima_s`"],
  ["Niveles sin calibrar", "Silencio −65 dBFS · mínimo −50 dBFS", "Ídem", "`nivel_silencio_dbfs`, `nivel_minimo_dbfs`"],
  ["Tolerancias de altura", "±25 cents afinada · ±50 cents misma nota", "Ídem", "`TOLERANCIA_*_CENTS`"],
  ["Ventana temporal · cierre", "±150 ms · +0,35 s", "Ídem", "`ConfiguracionSesion`"],
], [2.2, 2.3, 2.1, 2.4]));
c.push(H3("3.6.7 Verificación con señal sintética"));
c.push(P(`Para comprobar la cadena completa sin micrófono se generó una escala de Do mayor a negra = 80 con ondas senoidales a 48 kHz y tres errores a propósito: Fa4 en lugar de Re4, Fa4 desafinado +35 cents y Si4 omitido. La señal se analizó con \`Analizador\` (perfil piano) y los eventos se evaluaron con \`SesionDePractica\`. La ${T("simulacion")} muestra el resultado: los ocho estados coinciden con lo esperado, la latencia de confirmación fue de 100 ms por nota y la precisión, 6/8 (75 %). La misma secuencia se reprodujo en la interfaz de la aplicación (figuras ${numF("correcta")} a ${numF("resumen")}).`));
c.push(...tabla("simulacion", "Resultado de la cadena de detección con entrada simulada (escala de Do mayor, piano, 48 kHz)", ["Nota esperada", "Señal simulada", "Evento detectado", "Estado asignado"], [
  ["C4", "C4 afinado", "NOTA C4, 0 cents, confianza 0,994", "CORRECTA"],
  ["D4", "F4 (nota equivocada)", "NOTA F4, 0 cents", "NOTA_INCORRECTA"],
  ["E4", "E4 afinado", "NOTA E4, 0 cents", "CORRECTA"],
  ["F4", "F4 + 35 cents", "NOTA F4, +35 cents", "DESAFINADA"],
  ["G4 · A4", "Afinadas", "NOTA G4 · NOTA A4", "CORRECTA · CORRECTA"],
  ["B4", "Silencio", "—", "OMITIDA"],
  ["C5", "C5 afinado", "NOTA C5, 0 cents", "CORRECTA"],
], [1.6, 2, 3, 2.2]));

c.push(H2("3.7 Persistencia JSON"));
c.push(P("No hay base de datos, servicios remotos ni inicio de sesión. Todos los datos se guardan en archivos JSON locales dentro del **directorio de datos**, que se resuelve en este orden (`servicios/almacenamiento.py`): (1) el que fija `configurar_directorio()`, que en Android es `app.user_data_dir`; (2) la variable de entorno `WYNIK_DATOS`; y (3) por defecto, la raíz del proyecto. La guía de audio se escribe en `.cache/temp_guia.wav` dentro de ese directorio. La " + T("json") + " detalla cada archivo."));
c.push(...tabla("json", "Archivos de datos locales", ["Archivo", "Contenido", "Cuándo se escribe", "Módulo · escritura"], [
  ["`ajustes_wynik.json`", "Objeto con los 13 campos de `AjustesPractica` (instrumento, afinación, La4, modo, factor de tempo, tolerancia, notación, calibración, pulsos, dispositivo, volumen, vista, escala de fuente).", "Cada vez que cambia un ajuste (`WynikApp._ajuste_cambiado` → `_guardar_ajustes`).", "`ajustes_service` · atómica"],
  ["`historial_partituras.json`", "Lista de objetos `{nombre, ruta}` con la ruta absoluta de cada partitura.", "Al importar una partitura que no estaba (`agregar_al_historial`).", "`historial_service` · directa (no atómica)"],
  ["`progreso_sesiones.json`", "Lista de sesiones (`SesionProgreso.to_dict`), máximo 500.", "Al terminar una práctica (`WynikApp._terminar` → `registrar_sesion`).", "`progreso_service` · atómica"],
  ["`.cache/temp_guia.wav`", "Guía de audio (WAV mono, 16 bits, 22 050 Hz).", "Al preparar la práctica o cambiar un ajuste que afecta la guía.", "`audio_service` · `wave`"],
], [1.8, 3.3, 2.4, 1.6]));
c.push(P("Los ejemplos siguientes fueron escritos por la aplicación durante la sesión de captura del capítulo 4, con `WYNIK_DATOS=docs/anexo_iv/_datos_demo`; en las rutas absolutas, la carpeta del repositorio se abrevia como `<raíz>`."));
c.push(P("**progreso_sesiones.json** (una sesión con un error de nota, una nota desafinada y una omitida):", { par: { keepNext: true } }));
c.push(...codigo(leerJson("progreso_sesiones.json")));
c.push(P("**historial_partituras.json:**", { par: { keepNext: true } }));
c.push(...codigo(leerJson("historial_partituras.json")));
c.push(P("**ajustes_wynik.json:**", { par: { keepNext: true } }));
c.push(...codigo(leerJson("ajustes_wynik.json")));
c.push(P("Durante la lectura, un archivo ilegible se trata como vacío y se informa por consola (`[Wynik] No se pudo leer …`), y los ajustes fuera de rango se corrigen (`AjustesPractica.corregidos`). El historial guarda rutas absolutas, por lo que es propio de cada computador."));

c.push(H2("3.8 Recursos gráficos"));
c.push(P("El repositorio no contiene imágenes de mapa de bits. Los gráficos se dibujan con instrucciones del canvas de Kivy: las ilustraciones de instrumentos y la portada (`widgets/ilustraciones.py`, `widgets/dibujo.py`), el pentagrama (`widgets/partitura_widget.py`), la cinta simplificada y la guía de teclado o diapasón (`widgets/guia_instrumento_widget.py`). Los iconos son glifos de la fuente «Icons» de KivyMD. `vistas/fuentes.py` registra DejaVu Sans (incluida en Kivy) como fuente de texto porque contiene ♭, ♯, ♮, ✓ y ✗, que Roboto no tiene, y Roboto Medium y Bold para los rótulos. La " + T("paleta") + " resume la paleta de `vistas/tema.py`."));
c.push(...tabla("paleta", "Paleta principal de la interfaz (`vistas/tema.py`)", ["Constante", "Color", "Uso"], [
  ["`FONDO`", "#F4F2EE", "Fondo de todas las pantallas"],
  ["`PRIMARIO`", "#0E5A62 (azul petróleo)", "Barras, botones principales, nota esperada"],
  ["`CORRECTO`", "#2A8641 (verde)", "Nota correcta (✓)"],
  ["`DESAFINADO`", "#A87110 (ocre)", "Nota desafinada (≈)"],
  ["`ERROR`", "#C43A2D (rojo)", "Nota u octava equivocada (✗), fuera de rango"],
  ["`NEUTRO`", "RGB (0,42; 0,45; 0,48)", "Pendiente, sin tocar, sin evaluar"],
], [1.8, 2.4, 4]));

// ------------------------------------------------------------------ 4. Interfaz
c.push(H1("4. Interfaz de la aplicación"));
c.push(P("Las capturas de este capítulo se obtuvieron con el script `docs/anexo_iv/capturar_pantallas.py`, que importa `vistas.WynikApp` (la misma clase que ejecuta `main.py`), recorre las pantallas del `ScreenManager` con `Clock` y guarda cada una con `Window.screenshot()`. Todas usan el mismo tamaño de ventana, con proporción de teléfono: **412 × 915 dp con densidad 2 (824 × 1830 px)**. Se tomaron el 04/11/2026 en Linux x86_64 (Ubuntu 24.04) con la pantalla virtual Xvfb, usando partituras de ejemplo creadas con music21 (`docs/anexo_iv/partituras/`)."));
c.push(P("Para las capturas de la práctica en curso se utilizó **entrada simulada**: el script entrega a la aplicación ondas senoidales con la frecuencia de cada nota mediante `audio.captura.CapturaManual` y el atributo `WynikApp.fabrica_captura`, con la misma cadencia que un micrófono (bloques de 1024 muestras a 48 kHz). El análisis, la sesión y la interfaz corresponden al código de la aplicación, sin modificaciones."));
c.push(P(`Los marcadores numerados se dibujaron con Pillow (\`anotar_capturas.py\`) en la posición de cada widget, leída del árbol de widgets en el momento de la captura. Las originales están en \`capturas/originales/\` y las anotadas, en \`capturas/anotadas/\`. La ${F("navegacion")} resume la navegación.`));
c.push(...figura("navegacion", DIA("navegacion"), 13, "Navegación entre pantallas y diálogos", "Las siete pantallas del `ScreenManager` de `wynik.kv` y los dos diálogos; líneas discontinuas: retorno."));

const FILA = (n, e, q, a) => [String(n), e, q, a];
c.push(H2p("4.1 Menú principal"));
c.push(P(`La ${F("menu")} muestra la pantalla de inicio (\`menu\`) y la ${T("t_menu")} describe sus elementos.`));
c.push(...figura("menu", CAP("01_menu_principal"), ANCHO_CAP, "Menú principal con la última partitura importada", PIE_CAPTURA));
c.push(...tabla("t_menu", "Elementos del menú principal", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Ajustes generales", "Abre la pantalla de ajustes.", "`wynik.kv` <MenuScreen> · `BotonIcono` → `WynikApp.change_screen`"),
  FILA(2, "Continuar", "Muestra la última partitura y su progreso; «Continuar» la vuelve a cargar y abre la preparación.", "`portada_tarjeta` · `WynikApp.practicar_ultima` · `IlustracionPortada`"),
  FILA(3, "Importar", "Abre el selector de archivos MusicXML.", "`Mosaico` → `WynikApp.subir_partitura`"),
  FILA(4, "Mis partituras", "Abre la biblioteca; el detalle indica cuántas partituras hay.", "`Mosaico` → pantalla `elegir_partitura`"),
  FILA(5, "Progreso", "Abre el historial de sesiones; el detalle resume el avance.", "`Mosaico` → pantalla `progreso`"),
  FILA(6, "Ajustes", "Acceso alternativo a la pantalla de ajustes.", "`Mosaico` → pantalla `ajustes`"),
], [0.5, 1.8, 3.8, 3.4]));

c.push(H2p("4.2 Importación de partitura"));
c.push(P(`El diálogo de importación (${F("importar")}, ${T("t_importar")}) se abre desde el menú o desde «Mis partituras».`));
c.push(...figura("importar", CAP("02_importar_partitura"), ANCHO_CAP, "Diálogo «Importar partitura» con el archivo de ejemplo seleccionado", PIE_CAPTURA));
c.push(...tabla("t_importar", "Elementos del diálogo de importación", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Título e instrucción", "Indica los formatos admitidos: .musicxml, .xml y .mxl.", "`dialogs.mostrar_dialogo`"),
  FILA(2, "Selector de archivos", "Lista la carpeta personal (~) filtrada por extensión.", "`FileChooserListView` en `dialogs.abrir_selector_de_archivo`"),
  FILA(3, "Archivo seleccionado", "Partitura elegida; un doble toque también la abre.", "`FileChooserListView.selection` / `on_submit`"),
  FILA(4, "Cancelar", "Cierra el diálogo sin cargar nada.", "`mostrar_dialogo`"),
  FILA(5, "Abrir", "Lee la partitura con music21, la añade al historial JSON y abre «Preparar la práctica».", "`WynikApp._partitura_seleccionada` → `_cargar_partitura` → `agregar_al_historial`"),
], [0.5, 1.8, 3.6, 3.6]));

c.push(H2p("4.3 Selección de partitura (Mis partituras)"));
c.push(P(`La ${F("mis_partituras")} muestra la biblioteca construida a partir de \`historial_partituras.json\` (${T("t_mis")}).`));
c.push(...figura("mis_partituras", CAP("03_mis_partituras"), ANCHO_CAP, "Pantalla «Mis partituras» con las dos partituras importadas", PIE_CAPTURA));
c.push(...tabla("t_mis", "Elementos de «Mis partituras»", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Barra superior", "Título y botón Atrás (vuelve al menú).", "`componentes.BarraSuperior` · `WynikApp.atras`"),
  FILA(2, "Importar otra partitura", "Abre el selector de archivos.", "`BotonIcono` → `subir_partitura`"),
  FILA(3, "Partitura del historial", "Nombre, carpeta y, si ya se practicó, sesiones y mejor precisión; al tocarla se carga y se abre la preparación.", "`componentes.FilaPartitura` · `_refrescar_lista_partituras` · `detalle_de_entrada`"),
  FILA(4, "Segunda partitura", "Ídem (partitura de guitarra).", "Ídem"),
], [0.5, 1.8, 3.8, 3.4]));

c.push(H2p("4.4 Preparación de la práctica (instrumento, modo y tempo)"));
c.push(P(`La pantalla \`ajustes_inicio\` reúne los ajustes de la práctica de la partitura elegida. Se muestra en dos capturas: la parte superior (${F("preparar_a")}, ${T("t_prep_a")}) y la parte inferior, con el modo y el tempo (${F("preparar_b")}, ${T("t_prep_b")}).`));
c.push(...figura("preparar_a", CAP("04a_preparar_practica"), ANCHO_CAP, "«Preparar la práctica», parte superior", PIE_CAPTURA));
c.push(...tabla("t_prep_a", "Elementos de «Preparar la práctica» (parte superior)", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Partitura elegida", "Nombre del archivo cargado.", "`ids.titulo_partitura` en <AjustesInicioScreen>"),
  FILA(2, "Datos de la partitura", "Chips con número de notas, compases, tempo (♩) y parte.", "`WynikApp._mostrar_datos_partitura` · `componentes.Chip`"),
  FILA(3, "Escuchar la referencia", "Reproduce la guía sintetizada y muestra su duración; mientras suena, el micrófono no escucha.", "`toggle_reproduccion_audio`, `preparar_audio_guia` · `audio.guia` · `ReproductorGuia`"),
  FILA(4, "Instrumento", "Guitarra (E2–E6) o piano (A0–C8): fija el perfil y los parámetros de detección.", "`WynikApp.cambiar_instrumento` · `nucleo.instrumentos.PERFILES`"),
  FILA(5, "Practicar", "Abre la práctica con la vista elegida.", "`WynikApp.preparar_practica`"),
], [0.5, 1.8, 3.6, 3.6]));
c.push(salto());
c.push(...figura("preparar_b", CAP("04b_preparar_modo_tempo"), ANCHO_CAP, "«Preparar la práctica», parte inferior: modo, tempo, notación y vista", PIE_CAPTURA));
c.push(...tabla("t_prep_b", "Elementos de «Preparar la práctica» (parte inferior)", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Modo", "«Seguir el tempo» (la partitura avanza sola) o «Esperar cada nota» (avanza al acertar).", "`WynikApp.cambiar_modo` · `nucleo.sesion.ModoPractica`"),
  FILA(2, "Tempo", "Factor de 50 % a 150 % sobre el tempo de la partitura, en pasos de 10 %.", "`WynikApp.cambiar_factor_tempo` · regla `Paso`"),
  FILA(3, "Nombres de las notas", "Notación anglosajona (C D E…) o solfeo (Do Re Mi…).", "`WynikApp.cambiar_notacion` · `nombre_para_mostrar`"),
  FILA(4, "Vista de partitura", "Pentagrama completo o cinta simplificada.", "`WynikApp.cambiar_vista_simple`"),
  FILA(5, "Practicar", "Ídem.", "`preparar_practica`"),
], [0.5, 1.8, 3.6, 3.6]));

c.push(H2p("4.5 Ajustes generales"));
c.push(P(`La pantalla \`ajustes\` contiene los ajustes persistentes que afectan al detector y a la evaluación (${F("ajustes_a")} y ${F("ajustes_b")}; tablas ${numT("t_ajustes_a")} y ${numT("t_ajustes_b")}). Cada cambio se guarda de inmediato en \`ajustes_wynik.json\`.`));
c.push(...figura("ajustes_a", CAP("05a_ajustes"), ANCHO_CAP, "Ajustes: micrófono, ruido de fondo y afinación", PIE_CAPTURA + " El entorno de captura no tiene micrófono; por eso se lee «No se encontró ningún micrófono»."));
c.push(...tabla("t_ajustes_a", "Elementos de «Ajustes» (parte superior)", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Micrófono", "Muestra el dispositivo de entrada; «Cambiar micrófono» recorre los disponibles.", "`refrescar_dispositivo`, `siguiente_dispositivo` · `audio.captura.dispositivos_de_entrada`"),
  FILA(2, "Ruido de fondo", "Mide 1 s de silencio («Medir ahora») y decide si se mide al empezar o se usa la última medida.", "`calibrar_ahora`, `cambiar_calibracion` · `audio.senal.calibrar`"),
  FILA(3, "Afinación de referencia", "La4 entre 430 y 450 Hz; recuerda las tolerancias de ±25 y ±50 cents.", "`WynikApp.cambiar_la4` · `LA4_MIN`, `LA4_MAX`"),
  FILA(4, "Afinación de la guitarra", "Estándar, drop D, medio tono abajo o re abierta: cambia el rango de la guitarra.", "`cambiar_afinacion` · `AFINACIONES_GUITARRA`"),
], [0.5, 1.8, 3.6, 3.6]));
c.push(salto());
c.push(...figura("ajustes_b", CAP("05b_ajustes_evaluacion"), ANCHO_CAP, "Ajustes: evaluación, volumen y vista", PIE_CAPTURA));
c.push(...tabla("t_ajustes_b", "Elementos de «Ajustes» (parte inferior)", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Margen de tiempo por nota", "Tolerancia de la ventana: ±100, ±150, ±200 o ±250 ms.", "`cambiar_tolerancia` · `ConfiguracionSesion.tolerancia_s`"),
  FILA(2, "Cuenta previa", "Sin cuenta, 2, 3 o 4 pulsos visuales, sin sonido para que el micrófono no los capte.", "`cambiar_pulsos` · `OpcionesPractica.pulsos_cuenta`"),
  FILA(3, "Volumen de la referencia", "Volumen de la guía de audio (0–100 %).", "`WynikApp.ajustar_volumen`"),
  FILA(4, "Vista de partitura", "Ídem que en la preparación.", "`cambiar_vista_simple`"),
], [0.5, 1.8, 3.6, 3.6]));

c.push(H2p("4.6 Pantalla de práctica"));
c.push(P(`La ${F("practica_lista")} muestra la pantalla \`interprete\` con la partitura cargada, antes de pulsar «Empezar». La ${T("t_practica")} describe sus elementos; los mismos números se usan en las figuras ${numF("cuenta")} a ${numF("desafinada")}.`));
c.push(...figura("practica_lista", CAP("06_practica_lista"), 4.4, "Práctica preparada (estado «Lista»)", PIE_CAPTURA));
c.push(...tabla("t_practica", "Elementos de la pantalla de práctica", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Barra superior", "Título de la partitura; leyenda de marcas (?), alternar vista y volver a la preparación.", "`BarraSuperior` · `mostrar_leyenda`, `alternar_vista_practica`, `atras`"),
  FILA(2, "Nota esperada («Toca»)", "Nota que se debe tocar ahora, en la notación elegida.", "`WynikApp.texto_esperada` · `_mostrar_nota`"),
  FILA(3, "Nota oída («Oído»)", "Última nota detectada, coloreada según el resultado.", "`WynikApp.nota_detectada` · `_procesar_evento`"),
  FILA(4, "Estado de la nota", "Pendiente, Prepárate, Correcta, Desafinada, Error, Sin tocar…", "`componentes.EstadoPildora` · `tema.ESTADOS`"),
  FILA(5, "Medidor de afinación", "Desviación de −50 a +50 cents con la zona afinada (±25).", "`componentes.MedidorCents` · `cents_detectados`"),
  FILA(6, "Mensaje de resultado", "Explica el resultado: «✓ C4: correcta», «✗ nota equivocada: tocaste F4, se esperaba D4»…", "`WynikApp._aplicar_cambio`"),
  FILA(7, "Pentagrama", "Partitura con la nota actual resaltada y una marca por nota (✓ ≈ ✗ –).", "`widgets.PartituraWidget` · `nucleo.notacion.disponer`"),
  FILA(8, "Guía del instrumento", "Teclado (piano) o diapasón (guitarra) con la tecla esperada y la detectada.", "`widgets.GuiaInstrumentoWidget` · `nucleo.digitacion`"),
  FILA(9, "Progreso y controles", "«Nota n de N · aciertos», tira de resultados, estado de la escucha y botones Empezar/Pausa, detener, reiniciar y guía.", "`ids.pie` · `TiraResultados` · `boton_principal`, `detener_escucha`, `reiniciar_practica`"),
], [0.5, 1.8, 3.8, 3.4]));

c.push(H2("4.7 Práctica en curso: nota correcta, incorrecta y desafinada"));
c.push(P(`Al pulsar «Empezar» empieza la cuenta previa (${F("cuenta")}) y, al terminar, la escucha. Las figuras ${numF("correcta")} a ${numF("desafinada")} muestran tres momentos de la misma sesión con entrada simulada: la primera nota tocada correctamente, un Fa4 tocado cuando se esperaba Re4 (nota incorrecta) y un Fa4 desafinado +35 cents, que cuenta como acierto pero se marca en ocre.`));
c.push(figurasPar(
  { clave: "cuenta", ruta: CAP("07a_cuenta_previa"), ancho: 6.0, texto: "Cuenta previa («Prepárate… 2»)" },
  { clave: "correcta", ruta: CAP("07b_nota_correcta"), ancho: 6.0, texto: "Nota correcta: C4 a +0 cents (✓ verde)" },
));
c.push(detalleFigura(PIE_SIMULADA));
c.push(salto());
c.push(figurasPar(
  { clave: "incorrecta", ruta: CAP("07c_nota_incorrecta"), ancho: 6.0, texto: "Nota incorrecta: F4 cuando se esperaba D4 (✗ rojo)" },
  { clave: "desafinada", ruta: CAP("07d_nota_desafinada"), ancho: 6.0, texto: "Nota desafinada: F4 a +35 cents (≈ ocre, cuenta como acierto)" },
));
c.push(detalleFigura(PIE_SIMULADA + " Los números corresponden a la " + T("t_practica") + "."));

c.push(H2p("4.8 Resultados e historial"));
c.push(P(`Al cerrarse la última ventana, la sesión termina, se registra en \`progreso_sesiones.json\` y aparece el resumen (${F("resumen")}, ${T("t_resumen")}). La pantalla \`progreso\` (${F("progreso")}, ${T("t_progreso")}) lee ese archivo; su gráfico «Últimas sesiones» lo dibuja \`componentes.GraficoSesiones\`.`));
c.push(...figura("resumen", CAP("08_resumen_final"), ANCHO_CAP, "Diálogo «Práctica terminada»: 6 de 8 notas correctas (75 %)", PIE_SIMULADA));
c.push(...tabla("t_resumen", "Elementos del resumen final", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Resultado global", "Porcentaje de aciertos sobre las notas evaluables.", "`componentes.AnilloProgreso` · `WynikApp._mostrar_resumen_final`"),
  FILA(2, "Desglose", "Correctas, errores de nota u octava, sin tocar o sin señal y acordes no evaluados.", "`WynikApp._terminar` · `SesionDePractica.resumen`"),
  FILA(3, "Ver progreso", "Abre la pantalla de progreso.", "`change_screen(\"progreso\")`"),
  FILA(4, "Repetir", "Vuelve a empezar la misma práctica.", "`WynikApp.boton_principal`"),
], [0.5, 1.8, 3.6, 3.6]));
c.push(salto());
c.push(...figura("progreso", CAP("09_progreso"), ANCHO_CAP, "Pantalla «Progreso» con la sesión registrada", PIE_CAPTURA));
c.push(...tabla("t_progreso", "Elementos de la pantalla de progreso", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Resumen", "Número de sesiones y precisión media, con el anillo de la media.", "`WynikApp.refrescar_progreso` · `progreso_service.cargar_progreso`"),
  FILA(2, "Por partitura", "Mejor y última precisión y número de sesiones de cada partitura.", "`FilaPartituraProgreso` · `resumen_por_partitura`"),
  FILA(3, "Sesiones recientes", "Fecha, instrumento, aciertos/total, modo y tempo de cada sesión.", "`FilaSesion` · `progreso_sesiones.json`"),
], [0.5, 1.8, 3.6, 3.6]));

c.push(H2p("4.9 Vista simplificada"));
c.push(P(`Si en la preparación se elige la vista «Simplificada», la práctica usa la pantalla \`partitura_simple\` (${F("simple")}, ${T("t_simple")}), más ligera que el pentagrama completo.`));
c.push(...figura("simple", CAP("10_vista_simplificada"), ANCHO_CAP, "Práctica con la vista simplificada", PIE_CAPTURA));
c.push(...tabla("t_simple", "Elementos de la vista simplificada", ["N°", "Elemento", "Qué hace", "Archivo / clase"], [
  FILA(1, "Cinta de notas", "Notas como fichas, con la actual resaltada y el porcentaje de avance.", "`widgets.PartituraSimpleWidget`"),
  FILA(2, "Nota esperada", "Nota que se debe tocar y estado.", "`ids.nota_esperada` en <PartituraSimpleScreen>"),
  FILA(3, "Guía del instrumento", "Indicación textual de la tecla o posición.", "`GuiaInstrumentoWidget`"),
], [0.5, 1.8, 3.6, 3.6]));

// ------------------------------------------------------------------ 5. Manual del programador
c.push(H1("5. Manual del programador"));
c.push(H2("5.1 Requisitos previos"));
c.push(P(`La ${T("requisitos")} reúne los requisitos de cada sistema. Los de macOS y Linux provienen de la cabecera de \`requirements-escritorio.txt\` y del README; el de PortAudio en Linux se comprobó durante la instalación en Ubuntu 24.04.`));
c.push(...tabla("requisitos", "Requisitos previos por sistema operativo", ["Sistema", "Requisitos", "Motivo"], [
  ["Todos", "Python 3.13 o superior, Git y un micrófono para practicar", "`requires-python`; captura de audio"],
  ["macOS", "`brew install cairo pkg-config`", "pycairo (dependencia de KivyMD vía materialshapes) se compila"],
  ["Linux (Debian/Ubuntu)", "`libcairo2-dev`, `pkg-config`, compilador C y `libportaudio2`; en aarch64, además, compilador C++", "pycairo y materialyoucolor se compilan; sin PortAudio, `import sounddevice` falla con «PortAudio library not found»"],
  ["Windows 10/11 x64", "Ninguno adicional", "Todas las dependencias tienen rueda para Windows x64 (cabecera del `.txt`)"],
], [1.6, 3.6, 3.6]));
c.push(H2("5.2 Instalación paso a paso"));
c.push(...codigo([
  "git clone https://github.com/MansillsRich/Wynik-app.git",
  "cd Wynik-app",
  "python3.13 -m venv .venv",
  "source .venv/bin/activate            # Windows: .venv\\Scripts\\activate",
  "python -m pip install --upgrade pip",
  "python -m pip install -r requirements-escritorio.txt",
]));
c.push(P("En Ubuntu 24.04 la instalación se realizó con `uv pip install -r requirements-escritorio.txt` sobre Python 3.13.18 y resolvió los 37 paquetes no exclusivos de Windows, incluida la compilación de pycairo. En el computador de macOS, el entorno virtual se ubica fuera del repositorio (`../.venv`)."));
c.push(H2("5.3 Ejecución"));
c.push(...codigo([
  "python main.py",
  "",
  "# Datos en otra carpeta (pruebas, varias instalaciones):",
  "WYNIK_DATOS=/ruta/a/datos python main.py",
]));
c.push(P("La ventana de escritorio abre en 1040 × 720 y se puede reducir hasta 360 × 340 (tamaño de teléfono apaisado). La aplicación no abre el micrófono al arrancar, sino al pulsar «Empezar»; en macOS, la primera vez el sistema pide permiso de micrófono para la aplicación desde la que se ejecuta Python (por ejemplo, Terminal)."));
c.push(H2("5.4 Documentación del código"));
c.push(P("El código está documentado con docstrings en español. Según un recuento con el módulo `ast`, tienen docstring **50 de 54 módulos**, **73 de 110 clases** y **174 de 530 funciones y métodos**. Los docstrings de módulo explican el diseño (por ejemplo, las etapas de YIN o la política de estados de la sesión) y suelen citar los códigos de requisito C8–C11 y DET-01 a DET-05."));
c.push(P(`La documentación HTML se genera con **pydoc**, incluido en Python, sin dependencias nuevas. La carpeta \`docs/\` contiene 48 módulos y un índice generados con pydoc (commit 358dcaf). Para regenerarla se incluye \`docs/anexo_iv/generar_pydoc.py\`, que recorre los paquetes y escribe un HTML por módulo y un índice en \`docs/anexo_iv/pydoc/\` (${F("pydoc")}). En Linux sin pantalla se antepone \`xvfb-run -a\` al comando.`));
c.push(...codigo([
  "python docs/anexo_iv/generar_pydoc.py     # todos los módulos",
  "python -m pydoc -w audio.estimador_yin    # un solo módulo",
  "python -m pydoc -b                        # servidor local de documentación",
]));
c.push(...figura("pydoc", TER("pydoc_estimador_yin"), 11, "Documentación generada con pydoc para el módulo `audio.estimador_yin`", "Página `docs/anexo_iv/pydoc/audio.estimador_yin.html` abierta en Chromium."));
c.push(H2("5.5 Pruebas automatizadas"));
c.push(P(`Las pruebas usan \`unittest\` (biblioteca estándar) y se ejecutan desde la raíz del repositorio. El 04/11/2026 las **13 pruebas** se ejecutaron con resultado correcto en Linux (${F("unittest")}), macOS (${F("mac_pruebas")}), Windows 11 (${F("windows_pruebas")}) y Fedora Linux (${F("fedora_pruebas")}). La ${T("pruebas")} indica qué verifica cada archivo.`));
c.push(...codigo(["python -m unittest discover -s tests -v"]));
c.push(...tabla("pruebas", "Pruebas por archivo (resultado del 04/11/2026)", ["Archivo · clase", "N°", "Qué verifica", "Resultado"], [
  ["`test_ajustes.py` · `TestAjustes`", "2", "Valores por defecto de `AjustesPractica` y corrección de valores fuera de rango (instrumento, La4, factor de tempo, tolerancia).", "2/2 OK"],
  ["`test_almacenamiento.py` · `TestAlmacenamiento`", "4", "Directorio de datos configurado, creación de `.cache`, escritura y lectura de JSON y lectura de un archivo inexistente.", "4/4 OK"],
  ["`test_musica.py` · `TestMusica`", "4", "`Altura.desde_nombre`, enarmónicos, `comparar_alturas` y nombre inválido.", "4/4 OK"],
  ["`test_progreso.py` · `TestProgreso`", "3", "`SesionProgreso.to_dict`/`from_dict`, persistencia con `registrar_sesion` y `registrar_sesion_practica`.", "3/3 OK"],
  ["**Total**", "**13**", "Tiempo de ejecución en Linux: 0,008 s", "**13/13 OK**"],
], [2.6, 0.5, 4.8, 1.1]));
c.push(...figura("unittest", TER("pruebas_unittest"), 16, "Salida de `python -m unittest discover -s tests -v` en Linux", "Linux x86_64 (Ubuntu 24.04), Python 3.13.18, 04/11/2026."));
c.push(P(`La cobertura se midió con coverage.py 7.17.1 sobre los cuatro paquetes de la aplicación (${T("cobertura")}). Las pruebas cubren el **10,1 %** de las sentencias y se concentran en \`nucleo/\` y \`servicios/\` (modelo musical, almacenamiento, ajustes y progreso). El detalle por archivo está en \`evidencias/cobertura.txt\`.`));
c.push(...codigo([
  "python -m pip install coverage",
  "coverage run --source=audio,nucleo,servicios,vistas -m unittest discover -s tests",
  "coverage report",
]));
c.push(...tabla("cobertura", "Cobertura de sentencias por paquete (coverage.py 7.17.1, 04/11/2026)", ["Paquete", "Sentencias", "Cubiertas", "Cobertura", "Módulos con cobertura > 0"], [
  ["audio/", "982", "0", "0 %", "Ninguno"],
  ["nucleo/", "1618", "469", "29,0 %", "musica 63 %, instrumentos 69 %, eventos 66 %, sesion 39 %"],
  ["servicios/", "657", "111", "16,9 %", "almacenamiento 85 %, ajustes_service 77 %, progreso_service 76 %"],
  ["vistas/", "2478", "0", "0 %", "Ninguno"],
  ["**Total**", "**5735**", "**580**", "**10,1 %**", "—"],
], [1.4, 1.3, 1.2, 1.2, 4]));
c.push(H2("5.6 Calidad de código con Ruff"));
c.push(P(`Ruff usa la configuración de \`pyproject.toml\` (reglas E y W de pycodestyle, F de Pyflakes e I de orden de importaciones; ignora E402 y E501). Con Ruff 0.17.3, \`ruff check .\` informa **37 avisos**, 35 de ellos con corrección automática (${T("ruff")}, ${F("ruff")}). El archivo \`vistas/app.py\` concentra 15.`));
c.push(...codigo([
  "python -m pip install ruff",
  "ruff check .                # informe",
  "ruff check . --statistics   # resumen por regla",
  "ruff check . --fix          # aplica las correcciones automáticas",
]));
c.push(...tabla("ruff", "Avisos de Ruff por regla (`ruff check . --statistics`)", ["Regla", "Descripción", "Avisos", "Corrección automática"], [
  ["I001", "Importaciones sin ordenar", "18", "Sí"],
  ["F401", "Importación sin usar", "14", "Sí"],
  ["W292", "Falta salto de línea al final del archivo", "3", "Sí"],
  ["W291", "Espacios al final de la línea", "1", "No (manual)"],
  ["F841", "Variable asignada y no usada", "1", "No (manual)"],
  ["**Total**", "", "**37**", "35"],
], [1, 4.3, 1, 2]));
c.push(...figura("ruff", TER("ruff_estadisticas"), 11, "Salida de `ruff check . --statistics` (Ruff 0.17.3)", "Linux x86_64 (Ubuntu 24.04), 04/11/2026."));
c.push(H2("5.7 Depuración"));
c.push(H3("5.7.1 Registros"));
c.push(P("Kivy escribe su registro en la consola y en archivos dentro de `~/.kivy/logs/` (o de `KIVY_HOME/logs/` si se define esa variable). El nivel se cambia sin tocar el código con `KCFG_KIVY_LOG_LEVEL=debug python main.py`. La aplicación escribe sus propios mensajes en la consola con el prefijo `[Wynik]` (por ejemplo, «No se pudo abrir el micrófono», «No se pudo leer ajustes_wynik.json») y el historial usa `[HistorialService]`. `MotorDeEscucha.estadisticas()` y `ControladorPractica.resumen()` devuelven bloques descartados, desbordes, discontinuidades, carga del análisis y el último error del hilo."));
c.push(H3("5.7.2 Probar sin micrófono"));
c.push(P("La arquitectura permite depurar el análisis sin micrófono:"));
c.push(B("`Analizador(fs, perfil).analizar_senal(señal)` analiza una señal completa y devuelve los eventos (así se obtuvo la " + T("simulacion") + ")."));
c.push(B("`MotorDeEscucha(..., captura=CapturaManual(fs), usar_hilo=False)` y `procesar_pendientes()` hacen el análisis determinista, sin hilos."));
c.push(B("`WynikApp.fabrica_captura` sustituye el micrófono por cualquier captura con la misma interfaz; `capturar_pantallas.py` lo usa para la entrada simulada."));
c.push(H3("5.7.3 Problemas típicos"));
c.push(P(`La ${T("problemas")} resume los problemas conocidos, su causa y su solución.`));
c.push(...tabla("problemas", "Problemas típicos, causa y solución", ["Síntoma", "Causa", "Solución"], [
  ["Diálogo «No se pudo abrir el micrófono» al pulsar Empezar", "`MicrofonoNoDisponibleError`: sin permiso, sin dispositivo o dispositivo ocupado", "macOS: Ajustes del Sistema → Privacidad y seguridad → Micrófono → activar la aplicación desde la que se ejecuta Python; revisar el dispositivo en Ajustes («Cambiar micrófono»). Sin permiso, macOS también puede entregar silencio sin error."],
  ["«No se encontró ningún micrófono» en Ajustes (Linux)", "sounddevice no encuentra PortAudio («PortAudio library not found»)", "Instalar `libportaudio2`."],
  ["Falla la instalación de pycairo", "pycairo se compila y necesita cairo", "macOS: `brew install cairo pkg-config`; Linux: `libcairo2-dev pkg-config`."],
  ["Interbloqueo al cargar la guía en Linux", "Filtro de eventos de SDL2 frente a PulseAudio/PipeWire", "Resuelto en `main.py`: inicializa los proveedores de `SoundLoader` antes de crear la ventana."],
  ["Aviso «too much iteration» al redimensionar", "Las tarjetas se reajustan en más de 20 pasadas del reloj", "Resuelto: `Clock.max_iteration = 40` en `WynikApp.build`."],
  ["Textos y botones duplicados; «Ignored class … re-declaration»", "`wynik.kv` se cargaba dos veces", "Resuelto: `WynikApp.load_kv` devuelve False y `build()` carga los KV una vez."],
  ["Avisos emergentes que no aparecen en macOS", "Fbo de alto 0 incompleto en OpenGL sobre Metal", "Resuelto: `vistas/avisos.py` (`SnackbarWynik`)."],
], [2.6, 2.6, 3.8], { tam: 16 }));
c.push(H2("5.8 Plataformas"));
c.push(P(`El desarrollo se realizó en macOS, Windows 11 y Fedora Linux, y la aplicación se ejecutó en los tres sistemas. La ${T("plataformas")} resume el estado de cada plataforma y su evidencia.`));
c.push(...tabla("plataformas", "Estado de cada plataforma con su evidencia", ["Plataforma", "Estado", "Evidencia o motivo"], [
  ["Linux x86_64 (Ubuntu 24.04)", "**Validado** el 04/11/2026: instalación, 13/13 pruebas, Ruff, pydoc, interfaz completa y práctica con entrada simulada", "`evidencias/`; capítulo 4 (sin micrófono físico)"],
  ["macOS 27.2 «Golden Gate» (MacBook Air 15″, Apple M5, 16 GB)", "**Validado** el 04/11/2026: 13/13 pruebas, ejecución de la aplicación y práctica con piano real y micrófono", F("mac_pruebas") + " a " + F("mac_correcta") + "; `.venv` con Python 3.13.16 y los 37 paquetes fijados"],
  ["Windows 11 x64", "**Validado**: 13/13 pruebas el 04/11/2026; aplicación ejecutada durante el desarrollo", F("windows_pruebas") + "; Python 3.12.3 de 64 bits (AMD64)"],
  ["Windows 11 ARM (VMware Fusion en el MacBook Air M5)", "Probado por el equipo", "Las ruedas declaradas en el `.txt` son para Windows x64"],
  ["Fedora Linux x86_64", "**Validado**: 13/13 pruebas el 04/11/2026; aplicación ejecutada durante el desarrollo", F("fedora_pruebas") + "; Python 3.14.10; requiere cairo, pkg-config y PortAudio (apartado 5.1)"],
  ["Linux aarch64 (Kali en UTM)", "Soportado por dependencias, no validado", "Cabecera del `.txt`: además de pycairo, se compila materialyoucolor (necesita C++)"],
  ["Android", "En desarrollo: APK de prueba", "APK de prueba generado con Buildozer, con errores de compatibilidad entre versiones en resolución (" + T("android") + ")"],
  ["iOS", "No soportado", "Sin código ni empaquetado específicos"],
], [2.3, 2.7, 4]));
c.push(H3("5.8.1 Prueba en macOS con piano real"));
c.push(P(`El 04/11/2026 se ejecutaron las pruebas automatizadas en el entorno virtual del MacBook Air (${F("mac_pruebas")}: 13 pruebas, OK) y se practicó la partitura «Hjärtats_saga» (121 notas) en el modo «Esperar cada nota», con un piano real y el micrófono del computador. En una nota que pedía La4, primero se tocó una nota equivocada y la aplicación la marcó como error: la ${F("mac_incorrecta")} muestra Do♯1 en «Oído» y el estado «Error». El mensaje «octava incorrecta: tocaste La2» corresponde a un intento anterior de esa misma nota, porque el mensaje solo cambia cuando un intento modifica el resultado. Luego se volvió a intentar con la nota correcta y la aplicación la aceptó: la ${F("mac_correcta")} muestra el La4 reconocido como correcto a −18 cents, dentro de la tolerancia de ±25 cents. La detección distinguió así la nota pedida de una distinta.`));
c.push(...figura("mac_pruebas", MAC("pruebas_unittest_macos"), 15, "Pruebas automatizadas en macOS: 13 pruebas, OK", "MacBook Air 15″ (Apple M5, macOS 27.2), entorno `../.venv` con Python 3.13.16, 04/11/2026."));
c.push(figurasPar(
  { clave: "mac_incorrecta", ruta: MAC("practica_incorrecta_macos"), ancho: 6.0, texto: "macOS con piano real, primer intento: Do♯1 cuando se esperaba La4, marcado como error" },
  { clave: "mac_correcta", ruta: MAC("practica_correcta_macos"), ancho: 6.0, texto: "macOS con piano real, segundo intento: La4 correcto a −18 cents" },
));
c.push(detalleFigura("macOS, 04/11/2026: partitura «Hjärtats_saga», modo «Esperar cada nota», micrófono del MacBook Air y piano real."));
c.push(H3("5.8.2 Pruebas en Windows 11 y Fedora Linux"));
c.push(P(`En Windows 11 y en Fedora Linux se ejecutó \`python -m unittest discover -s tests -v\` desde la raíz del repositorio, con 13 pruebas correctas en ambos sistemas. La versión y la arquitectura de Python se obtuvieron con \`python -c "import platform, sys; print(sys.version, platform.machine())"\`: Python 3.12.3 de 64 bits (AMD64) en Windows 11 (${F("windows_pruebas")}) y Python 3.14.10 sobre x86_64 en Fedora Linux (${F("fedora_pruebas")}). Las pruebas también se ejecutan correctamente con Python 3.12.3, aunque \`pyproject.toml\` declara como versión mínima la 3.13.`));
c.push(...figura("windows_pruebas", EQUIPO("windows", "pruebas_unittest_windows"), 15, "Pruebas automatizadas en Windows 11: 13 pruebas, OK, con Python 3.12.3 (AMD64)", "PowerShell en Windows 11, 04/11/2026."));
c.push(...figura("fedora_pruebas", EQUIPO("fedora", "pruebas_unittest_fedora"), 15, "Pruebas automatizadas en Fedora Linux: 13 pruebas, OK, con Python 3.14.10 (x86_64)", "Terminal de Fedora Linux, 04/11/2026 (dos capturas consecutivas unidas)."));
c.push(H3("5.8.3 Android"));
c.push(P(`La versión para Android se empaqueta con Buildozer como un APK de prueba. En la etapa actual presenta errores de compatibilidad entre versiones de dependencias, en cuya resolución trabaja el equipo, y aún no reconoce correctamente el micrófono ni las carpetas para seleccionar partituras. La ${T("android")} resume el estado de cada aspecto.`));
c.push(...tabla("android", "Estado de Wynik en Android", ["Aspecto", "Estado actual"], [
  ["Empaquetado", "APK de prueba generado con Buildozer; presenta errores de compatibilidad entre versiones de dependencias, en los que el equipo está trabajando"],
  ["Captura de audio", "`audio/captura.py` prevé un adaptador `AudioRecord` con pyjnius y la misma interfaz que `CapturaBase`; en el APK de prueba el micrófono aún no se reconoce correctamente"],
  ["Permiso de micrófono", "El código de la aplicación no solicita `RECORD_AUDIO` en tiempo de ejecución"],
  ["Análisis", "`audio/` solo usa NumPy; `nucleo/`, la biblioteca estándar y music21 (al leer MusicXML)"],
  ["Datos locales", "`configurar_directorio(app.user_data_dir)` en Android"],
  ["Selector de archivos", "`FileChooserListView` sobre la carpeta personal; en el APK de prueba aún no accede correctamente a las carpetas de partituras"],
  ["Guía de audio", "`SoundLoader` de Kivy, el mismo código que en escritorio"],
  ["Prueba", "APK de prueba ejecutado por el equipo"],
], [2.2, 6.8]));

// ------------------------------------------------------------------ 6. Estado y trazabilidad
c.push(H1("6. Estado de funcionalidades y trazabilidad"));
c.push(H2("6.1 Mecanismos de control de calidad aplicados"));
c.push(P(`Siguiendo el apartado 5.4 de la plantilla CCII, la ${T("calidad")} enumera los mecanismos usados para asegurar la calidad del código y de este documento.`));
c.push(...tabla("calidad", "Mecanismos de control de calidad", ["Mecanismo", "Aplicación", "Resultado"], [
  ["Pruebas automatizadas (unittest)", "`python -m unittest discover -s tests -v`", "13/13 correctas en Linux, macOS, Windows 11 y Fedora Linux"],
  ["Medición de cobertura (coverage.py)", "Sobre audio, nucleo, servicios y vistas", "10,1 %"],
  ["Análisis estático (Ruff)", "`ruff check .` con la configuración del proyecto", "37 avisos, 35 automáticos"],
  ["Verificación de versiones", "`pyproject.toml`, `.in`, `.txt` y entornos instalados", "Coinciden las cinco dependencias directas"],
  ["Prueba manual con instrumento real", "macOS, piano real y micrófono, 04/11/2026", "Nota correcta e incorrecta detectadas"],
  ["Ejecución de la interfaz y capturas reproducibles", "`capturar_pantallas.py` y `anotar_capturas.py`; revisión de cada imagen", "16 capturas"],
  ["Revisión del documento", "Contraste de la versión 2.0 con el código (`docs/anexo_iv/diagnostico.md`)", "Correcciones incorporadas en la versión 3.0"],
  ["Integridad documental", "Índices automáticos, figuras y tablas numeradas y citadas, fecha y versión iguales en portada, ficha y pie", "Verificado en el PDF final"],
], [2.6, 3.8, 2.4]));
c.push(H2("6.2 Matriz de trazabilidad"));
c.push(P(`La ${T("trazabilidad")} enlaza cada funcionalidad con el código que la implementa, la prueba automatizada que la cubre y la evidencia. «Sin prueba automatizada» indica que la funcionalidad se verificó mediante ejecución. Los códigos C8–C11 y DET-xx corresponden a los requisitos citados en los docstrings.`));
c.push(...tabla("trazabilidad", "Trazabilidad funcionalidad → implementación → prueba → evidencia", ["Funcionalidad", "Módulo / clase", "Prueba que la cubre", "Evidencia", "Estado"], [
  ["Importar partituras MusicXML", "`nucleo.importador_musicxml.importar_musicxml`", "Sin prueba automatizada", F("importar") + ", " + F("preparar_a"), "Implementado"],
  ["Biblioteca e historial de partituras", "`servicios.historial_service`, `ElegirPartituraScreen`", "Sin prueba automatizada", F("mis_partituras"), "Implementado"],
  ["Captura de audio de escritorio", "`audio.captura.CapturaSounddevice`", "Sin prueba automatizada", F("mac_incorrecta") + ", " + F("mac_correcta"), "Validado en macOS (piano real)"],
  ["Detección de notas (YIN, segmentación)", "`audio.analizador`, `estimador_yin`, `segmentador`", "Sin prueba automatizada", T("simulacion") + "; " + F("correcta") + "–" + F("desafinada") + "; " + F("mac_correcta"), "Simulada y en macOS con piano"],
  ["Comparación con la nota esperada (cents)", "`nucleo.musica.comparar_frecuencia`", "`test_musica` (solo `comparar_alturas`)", T("clasificacion") + ", " + T("simulacion"), "Implementado"],
  ["Sincronización con el tempo (C8, DET-01, DET-02)", "`nucleo.sesion.SesionDePractica`", "Sin prueba automatizada", T("simulacion"), "Implementado"],
  ["Política de estados y acordes (C9, DET-03, DET-05)", "`SesionDePractica`, `EstadoNota`", "Sin prueba automatizada", F("incorrecta"), "Implementado"],
  ["Retroalimentación visual en tiempo real", "`vistas.app.WynikApp`, `PartituraWidget`, `GuiaInstrumentoWidget`", "Sin prueba automatizada", F("correcta") + "–" + F("desafinada"), "Implementado"],
  ["Guía de audio, nunca a la vez que la escucha (C10, C11)", "`audio.guia`, `servicios.reproductor_guia`", "Sin prueba automatizada", F("preparar_a"), "Implementado"],
  ["Ajustes de tempo, modo y evaluación", "`servicios.ajustes_service`, `AjustesInicioScreen`, `AjustesScreen`", "`test_ajustes` (2)", F("preparar_b") + ", " + F("ajustes_b"), "Implementado"],
  ["Persistencia local JSON", "`servicios.almacenamiento`", "`test_almacenamiento` (4)", T("json"), "Implementado"],
  ["Registro de sesiones y progreso", "`servicios.progreso_service`, `SesionProgreso`", "`test_progreso` (3)", F("resumen") + ", " + F("progreso"), "Implementado"],
  ["Vista simplificada", "`PartituraSimpleScreen`, `PartituraSimpleWidget`", "Sin prueba automatizada", F("simple"), "Implementado"],
  ["Ejecución en Android", "Ganchos en `main.py` y `vistas/app.py`; APK de prueba con Buildozer", "—", T("android"), "En desarrollo"],
  ["Importar PDF mediante OMR", "—", "—", "—", "Excluido del MVP"],
], [2.3, 2.3, 1.9, 1.7, 1.3], { tam: 15 }));

// ------------------------------------------------------------------ 7. Criterios y exclusiones
c.push(H1("7. Criterios de aceptación y exclusiones"));
c.push(H2("7.1 Criterios de aceptación del MVP"));
c.push(P(`La ${T("criterios")} presenta los criterios de aceptación del MVP y la evidencia de su cumplimiento.`));
c.push(...tabla("criterios", "Criterios de aceptación y su cumplimiento", ["Criterio", "Estado", "Evidencia"], [
  ["Ejecutar la aplicación sin registro ni inicio de sesión", "Cumplido", "Capítulo 4; no hay autenticación en el código"],
  ["Importar partituras MusicXML", "Cumplido", F("importar") + ", " + F("preparar_a")],
  ["Capturar audio con el micrófono y analizar la altura en escritorio", "Cumplido en macOS con piano real (04/11/2026)", T("simulacion") + "; " + F("mac_incorrecta") + ", " + F("mac_correcta")],
  ["Mostrar la retroalimentación durante la práctica", "Cumplido", F("correcta") + "–" + F("desafinada")],
  ["Guardar el progreso en JSON local", "Cumplido", T("json") + "; " + F("progreso")],
  ["Pasar la suite de pruebas automatizadas", "Cumplido (13/13 en Linux, macOS, Windows 11 y Fedora Linux), con cobertura del 10 %", T("pruebas") + ", " + T("cobertura") + "; " + F("windows_pruebas") + ", " + F("fedora_pruebas")],
], [3.3, 2.8, 2.7]));
c.push(H2("7.2 Exclusiones del MVP"));
c.push(B("Procesamiento de partituras PDF mediante reconocimiento óptico de música (OMR)."));
c.push(B("Servicios en la nube, autenticación remota o bases de datos externas."));
c.push(B("Funciones de red para la interacción entre profesores y alumnos."));
c.push(B("Análisis polifónico: los acordes se muestran como referencia y no se evalúan (DET-03)."));
c.push(B("Empaquetado móvil definitivo (APK para Android o paquete para iOS)."));
c.push(B("Medición sistemática de la tasa de aciertos del detector con instrumentos reales."));

// ------------------------------------------------------------------ 8. Definiciones
c.push(H1("8. Definiciones y abreviaturas"));
c.push(P(`La ${T("glosario")} define los términos y abreviaturas usados en este anexo.`));
c.push(...tabla("glosario", "Definiciones y abreviaturas", ["Término", "Definición"], [
  ["APK", "Paquete de instalación de una aplicación Android."],
  ["Ataque (onset)", "Inicio de una nota: subida brusca de energía o cambio del espectro."],
  ["AVD", "Android Virtual Device: emulador de Android."],
  ["BPM", "Pulsos por minuto; en Wynik, negras por minuto (♩ = 80)."],
  ["Buildozer / python-for-android", "Herramientas para empaquetar aplicaciones Kivy como APK."],
  ["CCII", "Consejo General de Colegios Profesionales de Ingeniería en Informática (España), autor de la plantilla usada."],
  ["Cent", "Centésima de semitono; una octava tiene 1200 cents."],
  ["CMND", "Diferencia media acumulada normalizada d′(τ), paso 3 del algoritmo YIN."],
  ["Cobertura", "Porcentaje de sentencias del código que ejecutan las pruebas."],
  ["dBFS", "Decibelios respecto de la escala completa digital (0 dBFS = valor máximo)."],
  ["Docstring", "Cadena de documentación de un módulo, clase o función de Python."],
  ["dp", "Píxel independiente de la densidad, unidad de medida de Kivy."],
  ["FFT", "Transformada rápida de Fourier."],
  ["Flujo espectral", "Aumento de energía del espectro entre dos tramas; sirve para detectar ataques."],
  ["Hilo (thread)", "Flujo de ejecución concurrente dentro del proceso."],
  ["JSON", "JavaScript Object Notation: formato de texto para datos estructurados."],
  ["KV", "Lenguaje declarativo de Kivy para describir interfaces."],
  ["La4", "Nota La de la cuarta octava; referencia de afinación (440 Hz por defecto)."],
  ["MIDI (número)", "Número entero de una altura temperada: C4 = 60, A4 = 69."],
  ["MusicXML / MXL", "Formato XML estándar para partituras; MXL es su versión comprimida."],
  ["MVP", "Producto mínimo viable."],
  ["OMR", "Reconocimiento óptico de música (partituras en imagen o PDF)."],
  ["PortAudio", "Biblioteca de entrada y salida de audio multiplataforma que usa sounddevice."],
  ["pydoc", "Generador de documentación de la biblioteca estándar de Python."],
  ["PyPI", "Python Package Index, repositorio público de paquetes de Python."],
  ["RMS", "Valor cuadrático medio de una señal (nivel)."],
  ["Rueda (wheel)", "Paquete de Python ya compilado para una plataforma."],
  ["Ruff", "Analizador estático y formateador de Python."],
  ["SDL2", "Biblioteca multimedia que Kivy usa para la ventana, la entrada y el audio."],
  ["SuperFlux", "Variante del flujo espectral con filtro de máximos que reduce los falsos ataques por vibrato."],
  ["UCT", "Universidad Católica de Temuco."],
  ["unittest", "Marco de pruebas unitarias de la biblioteca estándar de Python."],
  ["venv", "Entorno virtual de Python con sus propias dependencias."],
  ["Xvfb", "Servidor X virtual que permite ejecutar aplicaciones gráficas sin pantalla."],
  ["YIN", "Algoritmo de estimación de la frecuencia fundamental de de Cheveigné y Kawahara (2002)."],
], [2.2, 6.8], { tam: 15, margenV: 22 }));

// ------------------------------------------------------------------ 9. Bibliografía
c.push(H1("9. Bibliografía"));
const REF = (t) => new Paragraph({ children: runs(t), spacing: { after: 120, line: 264 }, indent: { left: 567, hanging: 567 } });
[
  "Astral Software. (s. f.). *Ruff documentation*. Recuperado el 4 de noviembre de 2026, de https://docs.astral.sh/ruff/",
  "Astral Software. (s. f.). *uv documentation*. Recuperado el 4 de noviembre de 2026, de https://docs.astral.sh/uv/",
  "Batchelder, N. (s. f.). *Coverage.py* (versión 7.17.1) [Software]. https://coverage.readthedocs.io/",
  "Böck, S., & Widmer, G. (2013). Maximum filter vibrato suppression for onset detection. En *Proceedings of the 16th International Conference on Digital Audio Effects (DAFx-13)*. Maynooth, Irlanda.",
  "Consejo General de Colegios Profesionales de Ingeniería en Informática. (2016). *Plantilla básica para la elaboración de la documentación de proyectos de ingeniería informática* (Norma CCII-N2016-02, versión 1.0).",
  "Cuthbert, M. S., & Ariza, C. (2010). music21: A toolkit for computer-aided musicology and symbolic music data. En *Proceedings of the 11th International Society for Music Information Retrieval Conference (ISMIR 2010)* (pp. 637–642).",
  "de Cheveigné, A., & Kawahara, H. (2002). YIN, a fundamental frequency estimator for speech and music. *The Journal of the Acoustical Society of America, 111*(4), 1917–1930. https://doi.org/10.1121/1.1458024",
  "Geier, M. (s. f.). *python-sounddevice* (versión 0.5.6) [Software]. https://python-sounddevice.readthedocs.io/",
  "Harris, C. R., Millman, K. J., van der Walt, S. J., Gommers, R., Virtanen, P., Cournapeau, D., Wieser, E., Taylor, J., Berg, S., Smith, N. J., Kern, R., Picus, M., Hoyer, S., van Kerkwijk, M. H., Brett, M., Haldane, A., Fernández del Río, J., Wiebe, M., Peterson, P., … Oliphant, T. E. (2020). Array programming with NumPy. *Nature, 585*(7825), 357–362. https://doi.org/10.1038/s41586-020-2649-2",
  "Kivy Organization. (s. f.). *Kivy documentation* (versión 2.3.1). Recuperado el 4 de noviembre de 2026, de https://kivy.org/doc/stable/",
  "KivyMD Team. (s. f.). *KivyMD documentation* (versión 2.0.0). Recuperado el 4 de noviembre de 2026, de https://kivymd.readthedocs.io/",
  "PortAudio. (s. f.). *PortAudio: Portable cross-platform audio I/O*. Recuperado el 4 de noviembre de 2026, de https://www.portaudio.com/",
  "Python Software Foundation. (s. f.). *pydoc — Documentation generator and online help system*. Python 3.13 documentation. https://docs.python.org/3.13/library/pydoc.html",
  "Python Software Foundation. (s. f.). *unittest — Unit testing framework*. Python 3.13 documentation. https://docs.python.org/3.13/library/unittest.html",
  "Rodríguez Ramírez, B. M. (2019). *Aikén: Aplicación móvil para turismo social. Anexo IV – Documentación técnica de programación* [Trabajo de fin de grado, Universidad de Salamanca].",
  "W3C Music Notation Community Group. (2021). *MusicXML 4.0* [Final community group report]. https://www.w3.org/2021/06/musicxml40/",
].forEach((r) => c.push(REF(r)));

// ------------------------------------------------------------------ Firmas y declaración de IA
c.push(H1("Firmas"));
c.push(P("Los integrantes del equipo de desarrollo suscriben el contenido de este anexo, que describe el estado del repositorio en el commit 358dcaf."));
const firma = (nombre, rol) => [
  new Paragraph({ spacing: { before: 520, after: 0 }, children: [new TextRun({ text: "_______________________________________", color: GRIS })] }),
  new Paragraph({ spacing: { after: 0 }, children: runs(`**${nombre}**`) }),
  new Paragraph({ spacing: { after: 120 }, children: runs(rol, { color: GRIS, size: 20 }) }),
];
c.push(...firma(RICHARD, "Scrum Master y desarrollador"));
c.push(...firma("Sebastián Eduardo Contreras Vergara", "Desarrollador y tester"));
c.push(...firma("Benjamín Ignacio Saavedra Mercado", "Desarrollador y tester"));
c.push(...firma("Javiera Alejandra Celia Muñoz Toledo", "Desarrolladora y tester"));
c.push(P(`Temuco, ${FECHA}.`, { par: { spacing: { before: 240 } } }));
c.push(H1s("Declaración de uso de inteligencia artificial"));
c.push(P("El equipo declara el uso de herramientas de inteligencia artificial en el proyecto, siempre bajo supervisión humana. En el desarrollo de la aplicación se utilizaron como apoyo para escribir el código. En la elaboración de esta versión del anexo se utilizó un asistente de inteligencia artificial (Claude, de Anthropic) como apoyo para contrastar la documentación con el código, ejecutar los comandos de verificación (pruebas, cobertura, Ruff y pydoc), generar las capturas mediante scripts auxiliares que no modifican la aplicación y redactar borradores de las secciones."));
c.push(P("Los datos del documento provienen del repositorio y de las salidas guardadas en `docs/anexo_iv/evidencias/`. El equipo revisó la totalidad del contenido y asume la responsabilidad sobre él."));

// ================================================================== PORTADA
const portada = [
  new Paragraph({ spacing: { before: 1200, after: 120 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "WYNIK", font: FUENTE, size: 56, bold: true, color: AZUL })] }),
  new Paragraph({ spacing: { after: 120 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Aplicación de aprendizaje musical con reconocimiento de notas en tiempo real", font: FUENTE, size: 30, bold: true, color: AZUL })] }),
  new Paragraph({ spacing: { after: 360 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Prototipo de escritorio en Python + Kivy/KivyMD con arquitectura preparada para Android", font: FUENTE, size: 22, italics: true, color: GRIS })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 6, color: "808080", space: 8 } }, spacing: { before: 120, after: 60 }, children: [new TextRun({ text: "Anexo IV – Documentación Técnica de Programación", bold: true, size: 26 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 }, children: [new TextRun({ text: "Especificación técnica, estructura del repositorio y manual del programador", italics: true, size: 22 })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: [imagen(path.join(AN, "recursos", "logo_uct.png"), 4.2)] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: runs(`**Asignatura:** ${ASIGNATURA}`) }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: runs("**Carrera:** Informática · **Institución:** Universidad Católica de Temuco (UCT)") }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: runs(`**Profesor:** ${PROFESOR}`) }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 200, after: 40 }, children: runs("**Integrantes**") }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: runs(RICHARD) }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: runs("Sebastián Eduardo Contreras Vergara") }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: runs("Benjamín Ignacio Saavedra Mercado") }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 300 }, children: runs("Javiera Alejandra Celia Muñoz Toledo") }),
  new Paragraph({ alignment: AlignmentType.CENTER, children: runs(`**Fecha de entrega:** ${FECHA} · **Versión:** ${VERSION}`) }),
];

// ================================================================== DOCUMENTO
const pie = new Footer({ children: [new Paragraph({
  border: { top: { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF", space: 4 } },
  tabStops: [{ type: TabStopType.RIGHT, position: ANCHO }],
  children: [
    new TextRun({ text: `Wynik · Anexo IV – Documentación Técnica de Programación · Versión ${VERSION} · ${FECHA}`, size: 16, color: GRIS }),
    new TextRun({ text: "\tPágina ", size: 16, color: GRIS }),
    new TextRun({ children: [PageNumber.CURRENT], size: 16, color: GRIS }),
    new TextRun({ text: " de ", size: 16, color: GRIS }),
    new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 16, color: GRIS }),
  ],
})] });
const cabecera = new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: `Universidad Católica de Temuco · ${ASIGNATURA}`, size: 16, color: GRIS })] })] });
const pagina = { size: { width: 12240, height: 15840 }, margin: { top: 1300, bottom: 1300, left: 1440, right: 1440, header: 600, footer: 600 } };

const doc = new Document({
  creator: "Equipo Wynik",
  title: "Wynik – Anexo IV – Documentación Técnica de Programación",
  description: `Versión ${VERSION}, ${FECHA}`,
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FUENTE, size: 22, language: { value: "es-CL" } } } },
    paragraphStyles: [
      { id: "Title", name: "Title", basedOn: "Normal", next: "Normal", run: { font: FUENTE, size: 30, bold: true, color: AZUL }, paragraph: { spacing: { before: 0, after: 240 }, keepNext: true } },
      { id: "Heading1", name: "heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 32, bold: true, color: AZUL }, paragraph: { spacing: { before: 120, after: 200 }, keepNext: true, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "8EAADB", space: 4 } } } },
      { id: "Heading2", name: "heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 26, bold: true, color: AZUL2 }, paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 1 } },
      { id: "Heading3", name: "heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FUENTE, size: 23, bold: true, color: "404040" }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 2 } },
      { id: "Caption", name: "caption", basedOn: "Normal", next: "Normal", run: { font: FUENTE, size: 18, color: "404040" }, paragraph: { spacing: { before: 60, after: 200 } } },
    ],
  },
  numbering: { config: [
    { reference: "vinetas", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 567, hanging: 283 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1134, hanging: 283 } } } },
    ] },
    { reference: "numeros", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 567, hanging: 340 } } } },
    ] },
  ] },
  sections: [
    { properties: { page: pagina, titlePage: true }, children: portada },
    { properties: { page: pagina }, headers: { default: cabecera }, footers: { default: pie }, children: c },
  ],
});

if (creadas.Figura.length !== FIGS.length) throw new Error(`Figuras creadas ${creadas.Figura.length} de ${FIGS.length}`);
if (creadas.Tabla.length !== TABS.length) throw new Error(`Tablas creadas ${creadas.Tabla.length} de ${TABS.length}`);
Packer.toBuffer(doc).then((b) => {
  fs.writeFileSync(SALIDA, b);
  console.log("Escrito", SALIDA, FIGS.length, "figuras,", TABS.length, "tablas;", tablasEnteras.filter((t) => t.entera).length, "tablas enteras");
});
