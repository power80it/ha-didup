"""Coordinator: un login per giro, tutti gli alunni, rilevamento degli elementi nuovi."""
from __future__ import annotations

import asyncio
import datetime as dt
import logging
from functools import partial
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.components import persistent_notification
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from . import parsing, report
from .api import DidupApi, DidupAuthError, DidupError
from .const import (EVENTO_REPORT, R_ALUNNI, R_CARTELLA, R_MAX_PAGINE, R_MAX_PAGINE_DEFAULT, R_NOME_FILE, R_NOME_FILE_DEFAULT,
                    R_SEZIONI, R_UNISCI, SIGNAL_REPORT, CONF_ALUNNI_NOTI, DOMAIN, F_BACHECA, F_NOTE, F_PROMEMORIA, F_VOTI, F_COMPITI, INTERVALLO_DEFAULT,
                    INTERVALLO_MIN, OPT_INCLUDI_OGGI, OPT_INTERVALLO, SIGNAL_EVENTO, STORE_VERSION, OPT_ALUNNI,
                    OPT_FUNZIONI, FUNZIONI_DEFAULT)

_LOGGER = logging.getLogger(__name__)

# (funzione che la abilita, chiave dati, tipo evento, campi che identificano l'elemento)
RILEVATORI = [
    (F_COMPITI, "compiti", "nuovo_compito", ("data", "materia", "testo")),
    (F_PROMEMORIA, "promemoria", "nuovo_promemoria", ("data", "ora", "testo")),
    (F_VOTI, "voti", "nuovo_voto", ("chiave",)),
    (F_NOTE, "note", "nuova_nota", ("chiave",)),
    (F_BACHECA, "bacheca", "nuova_comunicazione", ("chiave",)),
]


class DidupCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: DidupApi) -> None:
        minuti = max(INTERVALLO_MIN, int(entry.options.get(OPT_INTERVALLO, INTERVALLO_DEFAULT)))
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=dt.timedelta(minutes=minuti))
        self.api = api
        self._store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}_{entry.entry_id}")
        self._visti: dict[str, list[str]] | None = None  # None = mai inizializzato -> primo giro senza eventi
        self.ultimo_ok: dt.datetime | None = None
        self._lock_forzato = asyncio.Lock()
        self.firma: str = ""
        self.pianificatore = None  # impostato da async_setup_entry
        self.ultimi_report: dict[str, dict[str, Any]] = {}  # subentry_id -> esito dell'ultima generazione

    @property
    def funzioni(self) -> list[str]:
        return self.config_entry.options.get(OPT_FUNZIONI, FUNZIONI_DEFAULT)

    @property
    def alunni_scelti(self) -> list[str] | None:
        """None = tutti (nessuna scelta ancora fatta)."""
        return self.config_entry.options.get(OPT_ALUNNI)

    async def async_load_store(self) -> None:
        saved = await self._store.async_load()
        self._visti = saved.get("visti") if isinstance(saved, dict) else None

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            letti = await self.api.async_leggi()
        except DidupAuthError as e:
            raise ConfigEntryAuthFailed(str(e)) from e
        except DidupError as e:
            raise UpdateFailed(str(e)) from e

        oggi = dt.date.today()
        includi_oggi = self.config_entry.options.get(OPT_INCLUDI_OGGI, False)
        data: dict[str, dict[str, Any]] = {}
        for r in letti:
            al, dash = r["alunno"], r["dashboard"]
            s = parsing.slug(al["nome"], al["cognome"])
            data[s] = {
                "alunno": al,
                "compiti": parsing.compiti(dash, oggi, includi_oggi),
                "promemoria": parsing.promemoria(dash, oggi),
                "voti": parsing.voti(dash),
                "note": parsing.note(dash),
                "bacheca": parsing.bacheca(dash),
                "media": parsing.media_generale(dash),
            }
        self.ultimo_ok = dt_util.utcnow()
        self._aggiorna_alunni_noti(data)
        await self._rileva_nuovi(data)
        return data

    def _aggiorna_alunni_noti(self, data: dict) -> None:
        noti = {s: f"{d['alunno']['nome']} {d['alunno']['cognome']}" for s, d in data.items()}
        if noti != self.config_entry.data.get(CONF_ALUNNI_NOTI):
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, CONF_ALUNNI_NOTI: noti})

    async def _rileva_nuovi(self, data: dict) -> None:
        """Confronta con gli elementi già visti e invia un evento per ciascun elemento nuovo.

        Il primissimo giro dopo l'installazione memorizza soltanto (nessun evento per l'arretrato).
        """
        attuali: dict[str, list[str]] = {}
        nuovi: list[tuple[str, str, dict]] = []
        for s, d in data.items():
            for funzione, chiave, tipo, campi in RILEVATORI:
                if funzione not in self.funzioni:
                    continue
                lista = d[chiave]
                k = f"{s}:{chiave}"
                ora = parsing.chiavi(lista, campi)
                attuali[k] = sorted(ora)
                if self._visti is not None and k in self._visti:
                    gia = set(self._visti[k])
                    for item in lista:
                        if "|".join(str(item.get(c, "")) for c in campi) not in gia:
                            nuovi.append((s, tipo, item))
        # le funzioni appena attivate non generano eventi sull'arretrato: restano nel dizionario dopo il primo giro
        self._visti = {**(self._visti or {}), **attuali}
        await self._store.async_save({"visti": self._visti})
        for s, tipo, item in nuovi:
            async_dispatcher_send(self.hass, SIGNAL_EVENTO, s, tipo, item)

    async def async_aggiorna_forzato(self) -> None:
        """Rilegge subito da Argo (pulsante «Aggiorna da Argo»), fuori dal ritmo normale.

        Un solo aggiornamento alla volta e almeno 20 secondi fra uno e l'altro: premere il pulsante a raffica non deve
        fare decine di login ad Argo. Se la lettura fallisce solleva HomeAssistantError (visibile nella UI).
        """
        async with self._lock_forzato:
            if self.ultimo_ok and dt_util.utcnow() - self.ultimo_ok < dt.timedelta(seconds=20):
                return
            await self.async_refresh()
            if not self.last_update_success:
                raise HomeAssistantError(f"aggiornamento da Argo non riuscito: {self.last_exception}")

    def subentry(self, sub: ConfigSubentry | str) -> ConfigSubentry:
        """Il report nella sua versione attuale (le modifiche sostituiscono l'oggetto: mai tenere quello vecchio)."""
        sid = sub if isinstance(sub, str) else sub.subentry_id
        return self.config_entry.subentries.get(sid) or sub  # type: ignore[return-value]

    async def async_imposta_report(self, sub: ConfigSubentry | str, **campi: Any) -> None:
        """Cambia alcuni campi di un report (es. ora, automatico) e li salva nella configurazione."""
        s = self.subentry(sub)
        self.hass.config_entries.async_update_subentry(self.config_entry, s, data={**s.data, **campi})

    async def async_genera_report(self, sub: ConfigSubentry | str, aggiorna: bool = False,
                                  origine: str = "manuale") -> dict[str, Any]:
        """Genera il PDF del report `sub` e lo salva nella cartella scelta. Se `aggiorna`, rilegge Argo quando i dati
        hanno più di 10 minuti. `origine` («manuale» dal pulsante, «automatico» dall'orario) viaggia nell'evento
        `didup_report_generato`: chi lo ascolta può reagire solo alla produzione programmata. Solleva HomeAssistantError
        (e crea una notifica) se non riesce."""
        sub = self.subentry(sub)
        cfg = sub.data
        try:
            if aggiorna and (self.ultimo_ok is None or dt_util.utcnow() - self.ultimo_ok > dt.timedelta(minutes=10)):
                await self.async_refresh()
            if not self.last_update_success or not self.data:
                raise HomeAssistantError("dati di Argo non disponibili")
            cartella = cfg[R_CARTELLA]
            if not await self.hass.async_add_executor_job(self.hass.config.is_allowed_path, cartella):
                raise HomeAssistantError(f"cartella non consentita da Home Assistant: {cartella}")
            ora = dt_util.now()
            files = []
            for gruppo in report.raggruppa(self.data, cfg[R_ALUNNI], cfg[R_SEZIONI], cfg.get(R_UNISCI, False)):  # un PDF per gruppo
                esito = await self.hass.async_add_executor_job(partial(
                    report.genera, self.data, gruppo, cfg[R_SEZIONI],
                    int(cfg.get(R_MAX_PAGINE, R_MAX_PAGINE_DEFAULT)), sub.title, ora.replace(tzinfo=None)))
                nome_gruppo, slug_gruppo = report.etichetta_gruppo(self.data, gruppo)
                percorso = await self.hass.async_add_executor_job(
                    _scrivi, cartella,
                    report.nome_file(cfg.get(R_NOME_FILE, R_NOME_FILE_DEFAULT), sub.title, slug_gruppo, ora), esito.pdf)
                files.append({"alunno": nome_gruppo, "file": percorso, "pagine": esito.pagine,
                              "non_stampati": esito.non_stampati, "avvisi": esito.avvisi})
            if not files:
                raise HomeAssistantError("nessuno degli alunni scelti è presente nei dati di Argo")
        except (HomeAssistantError, OSError) as e:
            persistent_notification.async_create(
                self.hass, f"Report «{sub.title}»: {e}", title="DidUP: report PDF non generato",
                notification_id=f"didup_report_{sub.subentry_id}")
            self.ultimi_report[sub.subentry_id] = {"esito": f"errore: {e}", "quando": ora_iso()}
            async_dispatcher_send(self.hass, SIGNAL_REPORT, sub.subentry_id)
            raise HomeAssistantError(str(e)) from e
        persistent_notification.async_dismiss(self.hass, f"didup_report_{sub.subentry_id}")
        ris = {"esito": "ok", "quando": ora_iso(), "origine": origine, "files": files}
        self.ultimi_report[sub.subentry_id] = ris
        for f in files:
            self.hass.bus.async_fire(EVENTO_REPORT, {"report": sub.title, "origine": origine, **f})
        async_dispatcher_send(self.hass, SIGNAL_REPORT, sub.subentry_id)
        return ris


def ora_iso() -> str:
    return dt_util.now().isoformat(timespec="seconds")


def _scrivi(cartella: str, nome: str, dati: bytes) -> str:
    d = Path(cartella)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / nome
    tmp = d / (nome + ".tmp")
    tmp.write_bytes(dati)
    tmp.replace(dest)  # scrittura atomica: chi legge la cartella non vede mai un PDF a metà
    return str(dest)
