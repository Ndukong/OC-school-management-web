from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string


class BaseReport:
    template_name: str = ""
    css_files: list[str] = []

    # Reused across renders so WeasyPrint loads fonts only once.
    _font_config = None

    @classmethod
    def _get_font_config(cls):
        if cls._font_config is None:
            from weasyprint.text.fonts import FontConfiguration

            cls._font_config = FontConfiguration()
        return cls._font_config

    def get_context_data(self) -> dict:
        return {}

    def render_html(self) -> str:
        return render_to_string(self.template_name, self.get_context_data())

    def _local_file_url(self, url: str) -> str:
        """Resolve a Django absolute URL (/media/..., /static/...) to a local
        file:// path so WeasyPrint can embed it without a running server."""
        if settings.MEDIA_URL and url.startswith(settings.MEDIA_URL):
            rel = url[len(settings.MEDIA_URL):]
            return (Path(settings.MEDIA_ROOT) / rel).as_uri()
        if settings.STATIC_URL and url.startswith(settings.STATIC_URL):
            rel = url[len(settings.STATIC_URL):]
            root = settings.STATIC_ROOT or settings.STATICFILES_DIRS[0]
            return (Path(root) / rel).as_uri()
        return url

    def _resolve_local_urls(self, html_str: str) -> str:
        import re

        def repl(m):
            attr, quote, url, end_quote = m.groups()
            return f"{attr}={quote}{self._local_file_url(url)}{end_quote}"

        return re.sub(
            r'(src|href)=(["\'])([^"\']+)(["\'])', repl, html_str
        )

    def render_pdf(self, base_url: str | None = None) -> bytes:
        try:
            from weasyprint import HTML
        except OSError as exc:
            raise RuntimeError(
                "PDF generation is unavailable on this computer: WeasyPrint "
                "could not load its GTK libraries. Install the GTK runtime "
                "(see DEPLOYMENT.md) or use Preview (HTML) instead."
            ) from exc
        html_str = self._resolve_local_urls(self.render_html())
        css_urls = []
        for css in self.css_files:
            path = Path(settings.STATICFILES_DIRS[0]) / css
            if path.exists():
                css_urls.append(str(path))
        html = HTML(string=html_str, base_url=base_url)
        return html.write_pdf(
            stylesheets=css_urls,
            presentational_hints=True,
            font_config=self._get_font_config(),
        )

    def filename(self) -> str:
        return "report.pdf"
