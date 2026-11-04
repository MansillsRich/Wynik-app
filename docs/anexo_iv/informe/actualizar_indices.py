"""
Script auxiliar del Anexo IV (no forma parte de la aplicación Wynik).

Abre el .docx generado por construir_informe.js con LibreOffice (UNO), configura las listas
de figuras y de tablas a partir de las leyendas «Figura» y «Tabla», impide que se dividan
entre páginas las tablas que caben en una sola, actualiza todos los campos e índices y guarda
el documento final en .docx y .pdf, con las páginas reales.

Uso (desde la raíz del repositorio; requiere LibreOffice y python3-uno):
    python3 docs/anexo_iv/informe/actualizar_indices.py
"""

import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue
from lxml import etree

AQUI = Path(__file__).resolve().parent
ENTRADA = AQUI / "Anexo_IV_Wynik_v3.0_sin_indices.docx"
SALIDA_DOCX = AQUI / "Anexo_IV_Wynik_v3.0.docx"
SALIDA_PDF = AQUI / "Anexo_IV_Wynik_v3.0.pdf"


def propiedad(nombre, valor):
    p = PropertyValue()
    p.Name, p.Value = nombre, valor
    return p


W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ORDEN_PPR = ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
             "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
             "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
             "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc",
             "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle",
             "rPr", "sectPr", "pPrChange"]


def ordenar_ppr(docx: Path) -> int:
    """LibreOffice puede exportar un <w:pPr> con sus hijos fuera del orden del esquema OOXML
    (p. ej., <w:pStyle> después de <w:sectPr>). Se reordenan sin cambiar su contenido."""
    posicion = {n: i for i, n in enumerate(ORDEN_PPR)}
    with zipfile.ZipFile(docx) as z:
        arbol = etree.fromstring(z.read("word/document.xml"))
        resto = {i.filename: z.read(i.filename) for i in z.infolist() if i.filename != "word/document.xml"}
    cambiados = 0
    for ppr in arbol.iter(f"{{{W}}}pPr"):
        hijos = list(ppr)
        if not all(isinstance(h.tag, str) and etree.QName(h).localname in posicion for h in hijos):
            continue
        ordenados = sorted(hijos, key=lambda h: posicion[etree.QName(h).localname])
        if ordenados != hijos:
            for h in hijos:
                ppr.remove(h)
            ppr.extend(ordenados)
            cambiados += 1
    temporal = Path(tempfile.mkstemp(suffix=".docx")[1])
    with zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", resto.pop("[Content_Types].xml"))
        z.writestr("word/document.xml", etree.tostring(arbol, xml_declaration=True, encoding="UTF-8", standalone=True))
        for nombre, datos in resto.items():
            z.writestr(nombre, datos)
    shutil.move(temporal, docx)
    return cambiados


def primer_parrafo(tabla, celda):
    return tabla.getCellByName(celda).getText().createEnumeration().nextElement()


def tablas_enteras(documento) -> int:
    """construir_informe.js marca «conservar con el siguiente» en todas las filas (salvo la última)
    de las tablas que caben en una página; Word las mantiene juntas, y en LibreOffice se fija
    además la propiedad Split = False."""
    tablas = documento.getTextTables()
    enteras = 0
    for i in range(tablas.getCount()):
        tabla = tablas.getByIndex(i)
        filas = tabla.getRows().getCount()
        if all(primer_parrafo(tabla, f"A{r}").ParaKeepTogether for r in range(2, filas)):
            tabla.Split = False
            enteras += 1
    return enteras


def tablas_que_no_caben(documento) -> int:
    """Si una tabla marcada como entera ocupa más de una página, se vuelve a permitir su división."""
    cursor = documento.getCurrentController().getViewCursor()
    tablas = documento.getTextTables()
    liberadas = 0
    for i in range(tablas.getCount()):
        tabla = tablas.getByIndex(i)
        if tabla.Split:
            continue
        nombres = tabla.getCellNames()
        cursor.gotoRange(tabla.getCellByName(nombres[0]).getText().getStart(), False)
        inicio = cursor.getPage()
        cursor.gotoRange(tabla.getCellByName(nombres[-1]).getText().getEnd(), False)
        if cursor.getPage() != inicio:
            tabla.Split = True
            liberadas += 1
    return liberadas


def main() -> None:
    perfil = AQUI / ".lo_perfil"
    proceso = subprocess.Popen(["soffice", "--headless", "--invisible", "--nologo", "--norestore",
                                f"-env:UserInstallation=file://{perfil}",
                                "--accept=socket,host=localhost,port=2003;urp;"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    local = uno.getComponentContext()
    resolutor = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    contexto = None
    for _ in range(120):
        try:
            contexto = resolutor.resolve("uno:socket,host=localhost,port=2003;urp;StarOffice.ComponentContext")
            break
        except Exception:  # noqa: BLE001 - LibreOffice aún arranca
            time.sleep(0.5)
    if contexto is None:
        sys.exit("No se pudo conectar con LibreOffice")
    escritorio = contexto.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", contexto)
    documento = escritorio.loadComponentFromURL(uno.systemPathToFileUrl(str(ENTRADA)), "_blank", 0,
                                                (propiedad("Hidden", True),))
    enteras = tablas_enteras(documento)
    indices = documento.getDocumentIndexes()
    listas = [indices.getByIndex(i) for i in range(indices.getCount())
              if indices.getByIndex(i).supportsService("com.sun.star.text.IllustrationsIndex")]
    for indice, categoria in zip(listas, ("Figura", "Tabla")):
        indice.CreateFromLabels = True
        indice.LabelCategory = categoria
    liberadas = 0
    for _ in range(3):  # los índices cambian la paginación: se repite hasta estabilizar
        documento.getTextFields().refresh()
        for i in range(indices.getCount()):
            indices.getByIndex(i).update()
        liberadas += tablas_que_no_caben(documento)
    documento.storeToURL(uno.systemPathToFileUrl(str(SALIDA_DOCX)), (propiedad("FilterName", "MS Word 2007 XML"),))
    documento.storeToURL(uno.systemPathToFileUrl(str(SALIDA_PDF)), (propiedad("FilterName", "writer_pdf_Export"),))
    documento.close(True)
    try:
        escritorio.terminate()
    except Exception:  # noqa: BLE001 - LibreOffice se cierra al terminar
        pass
    proceso.wait(timeout=60)
    print(f"Escritos {SALIDA_DOCX.name} y {SALIDA_PDF.name}; tablas enteras: {enteras - liberadas} "
          f"(liberadas por no caber: {liberadas}); pPr reordenados: {ordenar_ppr(SALIDA_DOCX)}")


if __name__ == "__main__":
    main()
