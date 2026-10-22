"""Registrazione della card Lovelace inclusa come risorsa «module».

Come risorsa (e non solo con ``add_extra_js_url``) Lovelace la attende prima di disegnare la dashboard: altrimenti,
aprendo una dashboard subito dopo il caricamento della pagina, la card può risultare ancora non definita e mostrare
«Errore di configurazione». Se Lovelace è in modalità YAML (risorse non modificabili) si ricade su ``add_extra_js_url``.
"""
from __future__ import annotations

import logging

from homeassistant.components.lovelace.const import CONF_RESOURCE_TYPE_WS, CONF_URL, DOMAIN as LOVELACE_DATA
from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


def _risorse(hass: HomeAssistant):
    ld = hass.data.get(LOVELACE_DATA)
    return getattr(ld, "resources", None) if ld is not None else None


async def _pronte(risorse) -> bool:
    if not callable(getattr(risorse, "async_create_item", None)):
        return False  # modalità YAML: sola lettura
    if not getattr(risorse, "loaded", True):
        await risorse.async_load()
        risorse.loaded = True
    return True


async def async_registra_risorsa(hass: HomeAssistant, path: str, url: str) -> bool:
    """Crea o aggiorna la risorsa; True se Lovelace la gestirà, False se serve il ripiego."""
    try:
        risorse = _risorse(hass)
        if risorse is None or not await _pronte(risorse):
            return False
        esistenti = [i for i in risorse.async_items() if str(i.get(CONF_URL, "")).split("?")[0] == path]
        payload = {CONF_RESOURCE_TYPE_WS: "module", CONF_URL: url}
        if not esistenti:
            await risorse.async_create_item(payload)
        else:
            for i in esistenti:
                if i.get(CONF_URL) != url or i.get("type") != "module":
                    await risorse.async_update_item(i[CONF_ID], payload)
        return True
    except Exception:  # noqa: BLE001
        _LOGGER.warning("Impossibile registrare la card DidUP come risorsa Lovelace: si usa il caricamento globale", exc_info=True)
        return False


async def async_rimuovi_risorsa(hass: HomeAssistant, path: str) -> None:
    """Toglie la risorsa (quando l'ultima configurazione dell'integrazione viene rimossa)."""
    try:
        risorse = _risorse(hass)
        if risorse is None or not await _pronte(risorse):
            return
        for i in list(risorse.async_items()):
            if str(i.get(CONF_URL, "")).split("?")[0] == path:
                await risorse.async_delete_item(i[CONF_ID])
    except Exception:  # noqa: BLE001
        _LOGGER.debug("Rimozione della risorsa Lovelace DidUP non riuscita", exc_info=True)
