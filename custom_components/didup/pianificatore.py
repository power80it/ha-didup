"""Pianificazione dei report automatici: orari diversi per giorno, modificabili senza ricaricare l'integrazione."""
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from . import programma
from .const import R_AUTOMATICO, SUBENTRY_REPORT

_LOGGER = logging.getLogger(__name__)


class Pianificatore:
    def __init__(self, hass: HomeAssistant, entry, coordinator) -> None:
        self._hass = hass
        self._entry = entry
        self._c = coordinator
        self._annulla: list[Callable[[], None]] = []

    def avvia(self) -> None:
        """Per ogni report automatico un timer per ciascun orario distinto della settimana."""
        for sub in self._entry.subentries.values():
            if sub.subentry_type != SUBENTRY_REPORT or not sub.data.get(R_AUTOMATICO):
                continue
            per_orario: dict[str, set[int]] = {}
            for giorno, ora in programma.orari_per_giorno(sub.data).items():
                per_orario.setdefault(ora, set()).add(giorno)
            for ora, giorni in per_orario.items():
                try:
                    t = dt.time.fromisoformat(ora)
                except ValueError:
                    _LOGGER.warning("Report «%s»: orario non valido %r", sub.title, ora)
                    continue

                async def _scatta(adesso: dt.datetime, sid=sub.subentry_id, giorni=frozenset(giorni), ora=ora) -> None:
                    corrente = self._entry.subentries.get(sid)  # dati di adesso, non quelli di quando è stato pianificato
                    if corrente is None or not corrente.data.get(R_AUTOMATICO):
                        return
                    if programma.orari_per_giorno(corrente.data).get(adesso.weekday()) != ora or adesso.weekday() not in giorni:
                        return
                    try:
                        await self._c.async_genera_report(sid, aggiorna=True, origine="automatico")
                    except Exception as e:  # noqa: BLE001  (già notificato dal coordinator)
                        _LOGGER.warning("Report automatico «%s» non generato: %s", corrente.title, e)

                self._annulla.append(async_track_time_change(self._hass, _scatta, hour=t.hour, minute=t.minute, second=0))

    def ferma(self) -> None:
        for a in self._annulla:
            a()
        self._annulla = []

    def ripianifica(self) -> None:
        self.ferma()
        self.avvia()
