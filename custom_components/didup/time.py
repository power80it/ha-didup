"""Ora di generazione del PDF per ogni giorno della settimana (modificabile anche da dashboard)."""
from __future__ import annotations

import datetime as dt

from homeassistant.components.time import TimeEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import programma
from .const import R_ORARI, SIGNAL_REPORT, SUBENTRY_REPORT
from .entity import device_report


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    c = entry.runtime_data
    for sub in entry.subentries.values():
        if sub.subentry_type == SUBENTRY_REPORT:
            async_add_entities([OraGiorno(c, entry, sub, g) for g in programma.GIORNI], config_subentry_id=sub.subentry_id)


class OraGiorno(TimeEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:clock-outline"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, coordinator, entry, sub, giorno: str) -> None:
        self._c = coordinator
        self._sid = sub.subentry_id
        self._giorno = giorno
        self._attr_translation_key = f"ora_{giorno}"
        self._attr_unique_id = f"{entry.entry_id}_{sub.subentry_id}_ora_{giorno}"
        self._attr_device_info = device_report(entry, sub)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_REPORT, self._aggiorna))

    @callback
    def _aggiorna(self, subentry_id: str | None) -> None:
        if subentry_id in (None, self._sid):
            self.async_write_ha_state()

    @property
    def native_value(self) -> dt.time | None:
        try:
            return dt.time.fromisoformat(programma.ora_del_giorno(self._c.subentry(self._sid).data, self._giorno))
        except ValueError:
            return None

    async def async_set_value(self, value: dt.time) -> None:
        sub = self._c.subentry(self._sid)
        ora = value.replace(second=0, microsecond=0).strftime("%H:%M:%S")
        await self._c.async_imposta_report(self._sid, **{R_ORARI: programma.con_orario(sub.data, self._giorno, ora)})
        self.async_write_ha_state()
