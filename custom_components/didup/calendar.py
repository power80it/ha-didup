"""Calendario per alunno: compiti (giornata intera alla data di consegna) e promemoria/verifiche."""
from __future__ import annotations

import datetime as dt

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const import F_CALENDARIO
from .entity import DidupEntity, alunni_attivi


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    c = entry.runtime_data
    if F_CALENDARIO in c.funzioni:
        async_add_entities(DidupCalendar(c, s) for s in alunni_attivi(c))


def _eventi(dati: dict) -> list[CalendarEvent]:
    out = []
    for c in dati.get("compiti", []):
        d = dt.date.fromisoformat(c["data"])
        out.append(CalendarEvent(start=d, end=d + dt.timedelta(days=1),
                                 summary=f"Compiti: {c['materia']}", description=c["testo"]))
    for p in dati.get("promemoria", []):
        d = dt.date.fromisoformat(p["data"])
        try:
            t0 = dt.time.fromisoformat(p["ora"]) if p["ora"] else None
            t1 = dt.time.fromisoformat(p["ora_fine"]) if p["ora_fine"] else None
        except ValueError:
            t0 = t1 = None
        if t0:
            ini = dt.datetime.combine(d, t0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
            fine = dt.datetime.combine(d, t1 or t0, tzinfo=dt_util.DEFAULT_TIME_ZONE)
            if fine <= ini:
                fine = ini + dt.timedelta(hours=1)
            out.append(CalendarEvent(start=ini, end=fine, summary=p["testo"][:80], description=p["testo"]))
        else:
            out.append(CalendarEvent(start=d, end=d + dt.timedelta(days=1), summary=p["testo"][:80],
                                     description=p["testo"]))
    return out


def _inizio(e: CalendarEvent) -> dt.datetime:
    s = e.start
    return s if isinstance(s, dt.datetime) else dt.datetime.combine(s, dt.time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE)


class DidupCalendar(DidupEntity, CalendarEntity):
    _attr_translation_key = "calendario"
    _attr_icon = "mdi:calendar-school"

    def __init__(self, coordinator, alunno) -> None:
        super().__init__(coordinator, alunno)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{alunno}_calendario"

    @property
    def event(self) -> CalendarEvent | None:
        oggi = dt_util.start_of_local_day()
        futuri = [e for e in _eventi(self.dati) if _inizio(e) >= oggi]
        return min(futuri, key=_inizio) if futuri else None

    async def async_get_events(self, hass, start_date: dt.datetime, end_date: dt.datetime) -> list[CalendarEvent]:
        return [e for e in _eventi(self.dati) if start_date <= _inizio(e) < end_date]
