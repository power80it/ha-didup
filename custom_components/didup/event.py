"""Entità evento per alunno: scatta a ogni nuovo voto/compito/promemoria/nota/comunicazione."""
from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import EVENTI_TIPI, F_EVENTI, SIGNAL_EVENTO
from .entity import DidupEntity, alunni_attivi


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    c = entry.runtime_data
    if F_EVENTI in c.funzioni:
        async_add_entities(DidupEvento(c, s) for s in alunni_attivi(c))


class DidupEvento(DidupEntity, EventEntity):
    _attr_translation_key = "novita"
    _attr_icon = "mdi:bell-badge"
    _attr_event_types = EVENTI_TIPI

    def __init__(self, coordinator, alunno) -> None:
        super().__init__(coordinator, alunno)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{alunno}_novita"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_EVENTO, self._nuovo))

    @callback
    def _nuovo(self, alunno: str, tipo: str, item: dict) -> None:
        if alunno != self._alunno:
            return
        self._trigger_event(tipo, {k: v for k, v in item.items() if k != "chiave"})
        self.async_write_ha_state()
