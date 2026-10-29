"""prossimo_da_html: il passo di consenso Argo (pagina HTML al posto del redirect)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "pagine", Path(__file__).parent.parent / "custom_components" / "didup" / "pagine.py")
pagine = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pagine)
prossimo_da_html = pagine.prossimo_da_html

URL = "https://auth.portaleargo.it/oauth2/auth?client_id=x&consent_verifier=abc123&prompt=login&state=s"


def test_link_continua():
    h = f'<a class="btn" href="{URL.replace("&", "&amp;")}">Continua</a>'
    assert prossimo_da_html(h) == URL


def test_meta_refresh():
    h = f'<meta http-equiv="refresh" content="0; url={URL}">'
    assert prossimo_da_html(h) == URL


def test_nessun_link():
    assert prossimo_da_html("<html><body>Errore</body></html>") is None
