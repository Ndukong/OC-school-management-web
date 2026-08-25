import pytest


def _weasyprint_available() -> bool:
    try:
        import weasyprint

        weasyprint.HTML(string="<p>x</p>").write_pdf()
        return True
    except Exception:  # noqa: BLE001 - any import/render failure means PDFs unavailable
        return False


pytest.weasyprint_available = _weasyprint_available

requires_pdf = pytest.mark.skipif(
    not _weasyprint_available(),
    reason="WeasyPrint system libraries (GTK/Pango) not available on this machine",
)
