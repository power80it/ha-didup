from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DidupCoordinator


class DidupEntity(CoordinatorEntity[DidupCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DidupCoordinator, alunno: str) -> None:
        super().__init__(coordinator)
        self._alunno = alunno
        al = coordinator.data[alunno]["alunno"]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}_{alunno}")},
            name=f"{al['nome']} {al['cognome']}", manufacturer="Argo Software", model=f"Classe {al['classe']}",
            entry_type=None)

    @property
    def dati(self) -> dict:
        return self.coordinator.data.get(self._alunno, {})

    @property
    def available(self) -> bool:
        return super().available and self._alunno in self.coordinator.data


def alunni_attivi(coordinator: DidupCoordinator) -> list[str]:
    scelti = coordinator.alunni_scelti
    return [s for s in coordinator.data if scelti is None or s in scelti]


def device_report(entry, sub) -> DeviceInfo:
    """Dispositivo «Report <nome>»: raggruppa pulsante, ora e interruttore dello stesso report."""
    return DeviceInfo(identifiers={(DOMAIN, f"{entry.entry_id}_report_{sub.subentry_id}")},
                      name=f"Report {sub.title}", manufacturer="Argo Software", model="Report PDF")
