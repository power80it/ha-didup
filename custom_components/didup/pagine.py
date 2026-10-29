"""Passo successivo del login Argo quando la risposta è una pagina HTML e non un redirect HTTP."""
from __future__ import annotations

import html
import re

# Dal 29/10/2026 la pagina di consenso Argo non risponde più con un redirect HTTP ma con una pagina HTML
# («Accesso completato… Continua») che contiene il link al passo successivo (e un meta-refresh).
_HREF_CONSENSO_RE = re.compile(r'href="([^"]*consent_verifier=[^"]+)"')
_REFRESH_RE = re.compile(r"""http-equiv=["']refresh["'][^>]*content=["']\d+\s*;\s*url=([^"']+)""", re.I)


def prossimo_da_html(pagina: str) -> str | None:
    m = _HREF_CONSENSO_RE.search(pagina) or _REFRESH_RE.search(pagina)
    return html.unescape(m.group(1)) if m else None
