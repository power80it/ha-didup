"""Interruttori del report: generazione automatica (generale) e attivazione di ogni giorno della settimana."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import programma
from .const import R_AUTOMATICO, R_GIORNI, SIGNAL_REPORT, SUBENTRY_REPORT
from .entity import device_report


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    c = entry.runtime_data
    for sub in entry.subentries.values():
        if sub.subentry_type == SUBENTRY_REPORT:
            ents = [AutomaticoReport(c, entry, sub)] + [GiornoAttivo(c, entry, sub, g) for g in programma.GIORNI]
            async_add_entities(ents, config_subentry_id=sub.subentry_id)


class _Base(SwitchEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_should_poll = False

    def __init__(self, coordinator, entry, sub, chiave: str) -> None:
        self._c = coordinator
        self._sid = sub.subentry_id
        self._attr_unique_id = f"{entry.entry_id}_{sub.subentry_id}_{chiave}"
        self._attr_device_info = device_report(entry, sub)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_REPORT, self._aggiorna))

    @callback
    def _aggiorna(self, subentry_id: str | None) -> None:
        if subentry_id in (None, self._sid):
            self.async_write_ha_state()

    async def _imposta(self, attivo: bool) -> None:
        raise NotImplementedError

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._imposta(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._imposta(False)
        self.async_write_ha_state()


class AutomaticoReport(_Base):
    _attr_translation_key = "automatico_report"
    _attr_icon = "mdi:clock-check-outline"

    def __init__(self, coordinator, entry, sub) -> None:
        super().__init__(coordinator, entry, sub, "automatico")

    @property
    def is_on(self) -> bool:
        return bool(self._c.subentry(self._sid).data.get(R_AUTOMATICO))

    async def _imposta(self, attivo: bool) -> None:
        await self._c.async_imposta_report(self._sid, **{R_AUTOMATICO: attivo})


class GiornoAttivo(_Base):
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, entry, sub, giorno: str) -> None:
        super().__init__(coordinator, entry, sub, f"attivo_{giorno}")
        self._giorno = giorno
        self._attr_translation_key = f"attivo_{giorno}"

    @property
    def is_on(self) -> bool:
        return self._giorno in programma.giorni_attivi(self._c.subentry(self._sid).data)

    async def _imposta(self, attivo: bool) -> None:
        sub = self._c.subentry(self._sid)
        await self._c.async_imposta_report(self._sid, **{R_GIORNI: programma.con_giorno(sub.data, self._giorno, attivo)})
