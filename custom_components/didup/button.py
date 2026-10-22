"""Pulsante "Genera PDF" per ogni report configurato (sub-entry): stessa generazione dell'orario automatico."""
from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_REPORT, SUBENTRY_REPORT


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    c = entry.runtime_data
    async_add_entities([AggiornaButton(c, entry)])
    for sub in entry.subentries.values():
        if sub.subentry_type == SUBENTRY_REPORT:
            async_add_entities([ReportButton(c, entry, sub)], config_subentry_id=sub.subentry_id)


class ReportButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "genera_report"
    _attr_icon = "mdi:file-pdf-box"
    _attr_should_poll = False

    def __init__(self, coordinator, entry, sub) -> None:
        self._c = coordinator
        self._sub = sub
        self._sid = sub.subentry_id
        self._attr_unique_id = f"{entry.entry_id}_{sub.subentry_id}_report"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, f"{entry.entry_id}_report_{sub.subentry_id}")},
                                            name=f"Report {sub.title}", manufacturer="Argo Software", model="Report PDF")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_REPORT, self._aggiorna))

    @callback
    def _aggiorna(self, subentry_id: str) -> None:
        if subentry_id in (None, self._sid):
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._c.ultimi_report.get(self._sid, {}))

    async def async_press(self) -> None:
        await self._c.async_genera_report(self._sid, aggiorna=True)


class AggiornaButton(ButtonEntity):
    """Aggiornamento forzato: rilegge subito compiti, voti ecc. da Argo (dispositivo dell'account)."""

    _attr_has_entity_name = True
    _attr_translation_key = "aggiorna"
    _attr_icon = "mdi:refresh"
    _attr_should_poll = False

    def __init__(self, coordinator, entry) -> None:
        self._c = coordinator
        self._attr_unique_id = f"{entry.entry_id}_aggiorna"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
                                            manufacturer="Argo Software", model="DidUP Famiglia")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._c.async_add_listener(self.async_write_ha_state))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"ultimo_aggiornamento": self._c.ultimo_ok.isoformat() if self._c.ultimo_ok else None}

    async def async_press(self) -> None:
        await self._c.async_aggiorna_forzato()
