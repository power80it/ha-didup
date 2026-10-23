"""Sensori per alunno; si creano solo quelli delle funzioni attivate nelle Opzioni."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, F_BACHECA, F_COMPITI, F_MEDIE, F_NOTE, F_PROMEMORIA, F_VOTI
from .entity import DidupEntity, alunni_attivi


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    c = entry.runtime_data
    ents: list[SensorEntity] = [UltimoAggiornamentoSensor(c, entry)]
    for s in alunni_attivi(c):
        if F_COMPITI in c.funzioni:
            ents.append(ListaSensor(c, s, "compiti", "compiti", "mdi:notebook-edit", "compiti"))
        if F_PROMEMORIA in c.funzioni:
            ents.append(ListaSensor(c, s, "promemoria", "promemoria", "mdi:bell-ring", "promemoria"))
        if F_NOTE in c.funzioni:
            ents.append(ListaSensor(c, s, "note", "note_disciplinari", "mdi:alert-circle", "note"))
        if F_BACHECA in c.funzioni:
            ents.append(ListaSensor(c, s, "bacheca", "comunicazioni", "mdi:bulletin-board", "comunicazioni"))
        if F_VOTI in c.funzioni:
            ents.append(UltimoVotoSensor(c, s))
        if F_MEDIE in c.funzioni:
            ents.append(MediaSensor(c, s))
    async_add_entities(ents)


class ListaSensor(DidupEntity, SensorEntity):
    """Stato = quanti elementi; l'elenco completo è negli attributi (per card Markdown e automazioni)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, alunno, chiave: str, key: str, icona: str, unita: str) -> None:
        super().__init__(coordinator, alunno)
        self._chiave = chiave
        self._attr_translation_key = key
        self._attr_icon = icona
        self._attr_native_unit_of_measurement = unita
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{alunno}_{chiave}"

    @property
    def native_value(self) -> int:
        return len(self.dati.get(self._chiave, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        lista = self.dati.get(self._chiave, [])
        return {"tipo": self._attr_translation_key, "elementi": lista,
                "prossima_data": lista[0]["data"] if lista else None}


class UltimoVotoSensor(DidupEntity, SensorEntity):
    _attr_translation_key = "ultimo_voto"
    _attr_icon = "mdi:school"

    def __init__(self, coordinator, alunno) -> None:
        super().__init__(coordinator, alunno)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{alunno}_ultimo_voto"

    @property
    def native_value(self) -> str | None:
        v = self.dati.get("voti")
        return v[0]["voto"] if v else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v = self.dati.get("voti") or []
        return {"tipo": "ultimo_voto", **(v[0] if v else {}), "ultimi": v[:10]}


class MediaSensor(DidupEntity, SensorEntity):
    _attr_translation_key = "media_generale"
    _attr_icon = "mdi:chart-line"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(self, coordinator, alunno) -> None:
        super().__init__(coordinator, alunno)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{alunno}_media"

    @property
    def native_value(self) -> float | None:
        return self.dati.get("media")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"tipo": "media_generale"}


class UltimoAggiornamentoSensor(SensorEntity):
    """Quando Argo è stato letto con successo l'ultima volta (aggiornamento periodico o manuale)."""

    _attr_has_entity_name = True
    _attr_translation_key = "ultimo_aggiornamento"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check-outline"
    _attr_should_poll = False

    def __init__(self, coordinator, entry) -> None:
        self._c = coordinator
        self._attr_unique_id = f"{entry.entry_id}_ultimo_aggiornamento"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)}, name=entry.title,
                                            manufacturer="Argo Software", model="DidUP Famiglia")

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self._c.async_add_listener(self.async_write_ha_state))

    @property
    def native_value(self):
        return self._c.ultimo_ok
