"""Passo successivo del login Argo quando la risposta è una pagina HTML e non un redirect HTTP."""
from __future__ import annotations

import html
import re

# Dal 29/10/2026 la pagina di consenso Argo non risponde più con un redirect HTTP ma con una pagina HTML
# («Accesso completato… Continua») che contiene il link al passo successivo (e un meta-refresh).
_HREF_CONSENSO_RE = re.compile(r'href="([^"]*consent_verifier=[^"]+)"')
_REFRESH_RE = re.compile(r"""http-equiv=["']refresh["'][^>]*content=["']\d+\s*;\s*url=([^"']+)""", re.I)
_JS_RE = re.compile(r"""location(?:\.href)?\s*=\s*["']([^"']+)["']|location\.(?:replace|assign)\(\s*["']([^"']+)["']""")
_OAUTH_RE = re.compile(r"""["'](https://auth\.portaleargo\.it/oauth2/auth\?[^"']+)["']""")


def prossimo_da_html(pagina: str) -> str | None:
    """Indirizzo del passo successivo: link «Continua», meta-refresh, JavaScript o un qualunque link al server OAuth."""
    for rx in (_HREF_CONSENSO_RE, _REFRESH_RE, _JS_RE, _OAUTH_RE):
        m = rx.search(pagina)
        if m:
            return html.unescape(next(g for g in m.groups() if g))
    return None
