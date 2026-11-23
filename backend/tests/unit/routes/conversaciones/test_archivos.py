"""Qué archivos se pueden mandar por WhatsApp desde el panel: se decide por el contenido, con los límites de WhatsApp."""
import pytest

from src.routes.conversaciones.archivos import ArchivoInvalidoError, clasificar, nombre_seguro


@pytest.mark.parametrize(
    "datos, nombre, tipo, mime",
    [
        (b"\xff\xd8\xff\xe0abc", "foto.jpeg", "image", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nabc", "captura.png", "image", "image/png"),
        (b"%PDF-1.4 abc", "catalogo.PDF", "document", "application/pdf"),
        (b"\x00\x00\x00\x18ftypisomabc", "v.mp4", "video", "video/mp4"),
        (b"\x00\x00\x00\x18ftyp3gp5abc", "v.3gp", "video", "video/3gpp"),
        (b"PK\x03\x04abc", "informe.docx", "document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        (b"PK\x03\x04abc", "presentacion.pptx", "document", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1abc", "viejo.xls", "document", "application/vnd.ms-excel"),
    ],
)
def test_tipos_aceptados(datos, nombre, tipo, mime):
    archivo = clasificar(datos, nombre)
    assert (archivo.tipo_whatsapp, archivo.mime) == (tipo, mime)


@pytest.mark.parametrize(
    "datos, nombre",
    [
        (b"", "vacio.pdf"),
        (b"PK\x03\x04abc", "comprimido.zip"),  # un ZIP cualquiera no es un documento de Office
        (b"MZ\x90\x00", "programa.exe"),
        (b"<svg></svg>", "logo.svg"),
        (b"\x00\x00\x00\x14ftypqt  ", "video.mov"),
    ],
)
def test_tipos_rechazados(datos, nombre):
    with pytest.raises(ArchivoInvalidoError):
        clasificar(datos, nombre)


def test_nombre_seguro():
    assert nombre_seguro("C:\\Users\\Freddy\\Catálogo (1).pdf", "pdf") == "Catálogo (1).pdf"
    assert nombre_seguro("../../etc/passwd", "pdf") == "passwd.pdf"
    assert nombre_seguro(None, "jpg") == "archivo.jpg"
    assert nombre_seguro("a" * 200 + ".pdf", "pdf") == "a" * 80 + ".pdf"
    assert nombre_seguro("<script>.pdf", "pdf") == "script.pdf"
