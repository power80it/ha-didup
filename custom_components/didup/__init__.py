"""Integrazione DidUP Famiglia (Argo): compiti, promemoria, voti, note e comunicazioni degli alunni."""
from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import json
import logging

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import DidupApi
from .frontend import async_registra_risorsa, async_rimuovi_risorsa
from .const import CONF_CODICE, CONF_PASSWORD, CONF_UTENTE, DOMAIN, R_AUTOMATICO, R_GIORNI, R_ORA, R_ORARI, SIGNAL_REPORT
from .coordinator import DidupCoordinator
from .download import PdfReportView
from .pianificatore import Pianificatore

DidupConfigEntry = ConfigEntry[DidupCoordinator]

PIATTAFORME = [Platform.BUTTON, Platform.SENSOR, Platform.CALENDAR, Platform.EVENT, Platform.SWITCH, Platform.TIME]
CAMPI_ORARIO = (R_ORA, R_ORARI, R_AUTOMATICO, R_GIORNI)  # cambiarli non richiede di ricaricare l'integrazione
_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

CARD_FILE = Path(__file__).parent / "frontend" / "didup-card.js"
CARD_URL = "/didup_static/didup-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve la card Lovelace inclusa (`custom:didup-card`) e la carica in tutte le dashboard."""
    digest = await hass.async_add_executor_job(lambda: sha256(CARD_FILE.read_bytes()).hexdigest()[:10])
    hass.http.register_view(PdfReportView())
    await hass.http.async_register_static_paths([StaticPathConfig(CARD_URL, str(CARD_FILE), False)])
    url = f"{CARD_URL}?v={digest}"
    if not await async_registra_risorsa(hass, CARD_URL, url):
        add_extra_js_url(hass, url)  # Lovelace in modalità YAML: caricamento globale
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DidupConfigEntry) -> bool:
    # sessione dedicata: i cookie del login Argo non devono mescolarsi con quelli di altre integrazioni
    session = async_create_clientsession(hass)
    api = DidupApi(session, entry.data[CONF_CODICE], entry.data[CONF_UTENTE], entry.data[CONF_PASSWORD])
    coordinator = DidupCoordinator(hass, entry, api)
    await coordinator.async_load_store()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    coordinator.firma = _firma(entry)
    coordinator.pianificatore = Pianificatore(hass, entry, coordinator)
    coordinator.pianificatore.avvia()
    entry.async_on_unload(coordinator.pianificatore.ferma)
    await hass.config_entries.async_forward_entry_setups(entry, PIATTAFORME)
    entry.async_on_unload(entry.add_update_listener(_ricarica))
    return True


def _firma(entry: DidupConfigEntry) -> str:
    """Impronta della configurazione, esclusi orario/giorni/attivazione dei report: se cambia solo quella non si ricarica."""
    subs = sorted((s.subentry_id, s.subentry_type, s.title,
                   json.dumps({k: v for k, v in s.data.items() if k not in CAMPI_ORARIO}, sort_keys=True, default=str))
                  for s in entry.subentries.values())
    return json.dumps([dict(entry.data), dict(entry.options), subs], sort_keys=True, default=str)


async def _ricarica(hass: HomeAssistant, entry: DidupConfigEntry) -> None:
    c = entry.runtime_data
    if _firma(entry) == c.firma:
        c.pianificatore.ripianifica()  # è cambiato solo l'orario/l'attivazione: basta ripianificare
        async_dispatcher_send(hass, SIGNAL_REPORT, None)
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_entry(hass: HomeAssistant, entry: DidupConfigEntry) -> None:
    if not hass.config_entries.async_entries(DOMAIN):  # era l'ultima: si toglie anche la risorsa della card
        await async_rimuovi_risorsa(hass, CARD_URL)


async def async_unload_entry(hass: HomeAssistant, entry: DidupConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PIATTAFORME)
