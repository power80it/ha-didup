"""Download dei PDF dei report con il login di Home Assistant: `/api/didup/pdf/<report>/<alunno>`.

Il PDF resta nella cartella privata del report; l'indirizzo richiede l'autenticazione (anche tramite i link firmati
di `auth/sign_path`, usati dalla card per aprirlo nel browser o nell'app) e serve solo l'ultimo PDF prodotto
dall'integrazione per quell'alunno, mai un percorso scelto da chi chiede."""
from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView

from .const import DOMAIN, R_CARTELLA
from .percorsi import trova_pdf


class PdfReportView(HomeAssistantView):
    url = "/api/didup/pdf/{subentry_id}/{slug}"
    name = "api:didup:pdf"
    requires_auth = True

    async def get(self, request: web.Request, subentry_id: str, slug: str) -> web.Response:
        hass = request.app[KEY_HASS]
        for entry in hass.config_entries.async_entries(DOMAIN):
            c = getattr(entry, "runtime_data", None)
            sub = entry.subentries.get(subentry_id)
            if c is None or sub is None:
                continue
            files = c.ultimi_report.get(subentry_id, {}).get("files", [])
            percorso = await hass.async_add_executor_job(trova_pdf, files, sub.data[R_CARTELLA], slug)
            if percorso is None:
                break
            corpo = await hass.async_add_executor_job(percorso.read_bytes)
            return web.Response(body=corpo, headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": f'inline; filename="{percorso.name}"',
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            })
        return web.Response(status=404, text="PDF non trovato")
