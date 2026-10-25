"""Config flow: credenziali del genitore + scelta di alunni e funzioni (modificabili poi dalle Opzioni)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import (ConfigEntry, ConfigFlow, ConfigFlowResult, ConfigSubentryFlow, OptionsFlow,
                                          SubentryFlowResult)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (BooleanSelector, NumberSelector, NumberSelectorConfig, NumberSelectorMode,
                                            SelectOptionDict, SelectSelector, SelectSelectorConfig, TextSelector,
                                            TimeSelector)

from . import parsing
from .api import DidupApi, DidupAuthError, DidupError
from .const import (GIORNI_SETTIMANA, R_ALUNNI, R_AUTOMATICO, R_CARTELLA, R_GIORNI, R_MAX_PAGINE, R_MAX_PAGINE_DEFAULT,
                    R_NOME_FILE, R_NOME_FILE_DEFAULT, R_ORA, R_ORARI, R_SEZIONI, R_UNISCI, SEZIONI_REPORT, SUBENTRY_REPORT, CONF_ALUNNI_NOTI, CONF_CODICE, CONF_PASSWORD, CONF_UTENTE, DOMAIN, FUNZIONI, FUNZIONI_DEFAULT,
                    INTERVALLO_DEFAULT, INTERVALLO_MAX, INTERVALLO_MIN, OPT_ALUNNI, OPT_FUNZIONI, OPT_INCLUDI_OGGI,
                    OPT_INTERVALLO)

_LOGGER = logging.getLogger(__name__)

SCHEMA_LOGIN = vol.Schema({
    vol.Required(CONF_CODICE): str,
    vol.Required(CONF_UTENTE): str,
    vol.Required(CONF_PASSWORD): str,
})


def _schema_opzioni(alunni: dict[str, str], attuali: dict[str, Any]) -> vol.Schema:
    return vol.Schema({
        vol.Required(OPT_ALUNNI, default=attuali.get(OPT_ALUNNI, list(alunni))): SelectSelector(
            SelectSelectorConfig(options=[SelectOptionDict(value=k, label=v) for k, v in alunni.items()],
                                 multiple=True)),
        vol.Required(OPT_FUNZIONI, default=attuali.get(OPT_FUNZIONI, FUNZIONI_DEFAULT)): SelectSelector(
            SelectSelectorConfig(options=FUNZIONI, multiple=True, translation_key="funzioni")),
        vol.Required(OPT_INTERVALLO, default=attuali.get(OPT_INTERVALLO, INTERVALLO_DEFAULT)): NumberSelector(
            NumberSelectorConfig(min=INTERVALLO_MIN, max=INTERVALLO_MAX, step=5, unit_of_measurement="min")),
        vol.Required(OPT_INCLUDI_OGGI, default=attuali.get(OPT_INCLUDI_OGGI, False)): BooleanSelector(),
    })


def _pulisci(user_input: dict[str, Any]) -> dict[str, Any]:
    return {**user_input, OPT_INTERVALLO: int(user_input[OPT_INTERVALLO])}


class DidupConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._cred: dict[str, str] = {}
        self._alunni: dict[str, str] = {}

    async def _prova_login(self, cred: dict[str, str]) -> tuple[dict[str, str], str | None]:
        api = DidupApi(async_create_clientsession(self.hass), cred[CONF_CODICE].strip(),
                       cred[CONF_UTENTE].strip(), cred[CONF_PASSWORD])
        try:
            alunni = await api.async_alunni()
        except DidupAuthError:
            return {}, "invalid_auth"
        except (DidupError, aiohttp.ClientError, TimeoutError):
            return {}, "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Errore inatteso nel login DidUP")
            return {}, "unknown"
        return {parsing.slug(a["nome"], a["cognome"]): f"{a['nome']} {a['cognome']} ({a['classe']})"
                for a in alunni}, None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            self._cred = {k: (v.strip() if k != CONF_PASSWORD else v) for k, v in user_input.items()}
            await self.async_set_unique_id(f"{self._cred[CONF_CODICE]}_{self._cred[CONF_UTENTE]}".lower())
            self._abort_if_unique_id_configured()
            self._alunni, err = await self._prova_login(self._cred)
            if err:
                errors["base"] = err
            else:
                return await self.async_step_opzioni()
        return self.async_show_form(step_id="user", data_schema=SCHEMA_LOGIN, errors=errors)

    async def async_step_opzioni(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=f"DidUP ({self._cred[CONF_UTENTE]})",
                data={**self._cred, CONF_ALUNNI_NOTI: {k: v.split(" (")[0] for k, v in self._alunni.items()}},
                options=_pulisci(user_input))
        return self.async_show_form(step_id="opzioni", data_schema=_schema_opzioni(self._alunni, {}))

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            cred = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            _, err = await self._prova_login(cred)
            if err:
                errors["base"] = err
            else:
                return self.async_update_reload_and_abort(entry, data=cred)
        return self.async_show_form(step_id="reauth_confirm", errors=errors,
                                    data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
                                    description_placeholders={"utente": entry.data[CONF_UTENTE]})

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> OptionsFlow:
        return DidupOptionsFlow()

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry: ConfigEntry) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_REPORT: ReportSubentryFlow}


class DidupOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(data=_pulisci(user_input))
        alunni = self.config_entry.data.get(CONF_ALUNNI_NOTI, {})
        return self.async_show_form(step_id="init", data_schema=_schema_opzioni(alunni, self.config_entry.options))


class ReportSubentryFlow(ConfigSubentryFlow):
    """Un report PDF: cosa stampare, per chi, quante pagine al massimo, dove salvarlo e (opzionale) quando generarlo."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._modulo("user", user_input, None)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        return await self._modulo("reconfigure", user_input, self._get_reconfigure_subentry())

    async def _modulo(self, step_id: str, user_input: dict[str, Any] | None, sub) -> SubentryFlowResult:
        entry = self._get_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._valida(user_input)
            if not errors:
                titolo = user_input.pop("nome").strip()
                dati = {**user_input, R_MAX_PAGINE: int(user_input[R_MAX_PAGINE])}
                if sub is not None and sub.data.get(R_ORARI):
                    dati[R_ORARI] = sub.data[R_ORARI]  # gli orari per giorno si cambiano dalla dashboard: il modulo non li azzera
                if sub is None:
                    return self.async_create_entry(title=titolo, data=dati)
                return self.async_update_and_abort(entry, sub, title=titolo, data=dati)
        base = {"nome": sub.title, **sub.data} if sub else {}
        base.update(user_input or {})
        return self.async_show_form(step_id=step_id, errors=errors,
                                    data_schema=self._schema(entry.data.get(CONF_ALUNNI_NOTI, {}), base))

    async def _valida(self, ui: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        if not ui["nome"].strip():
            errors["nome"] = "nome_vuoto"
        if not ui[R_ALUNNI]:
            errors[R_ALUNNI] = "scelta_vuota"
        if not ui[R_SEZIONI]:
            errors[R_SEZIONI] = "scelta_vuota"
        if ui[R_AUTOMATICO] and not ui.get(R_GIORNI):
            errors[R_GIORNI] = "scelta_vuota"
        cartella = ui[R_CARTELLA].strip()
        ui[R_CARTELLA] = cartella
        if not cartella or not await self.hass.async_add_executor_job(self.hass.config.is_allowed_path, cartella):
            errors[R_CARTELLA] = "cartella_non_consentita"
        else:
            try:
                await self.hass.async_add_executor_job(lambda: Path(cartella).mkdir(parents=True, exist_ok=True))
            except OSError:
                errors[R_CARTELLA] = "cartella_non_scrivibile"
        return errors

    def _schema(self, alunni: dict[str, str], v: dict[str, Any]) -> vol.Schema:
        return vol.Schema({
            vol.Required("nome", default=v.get("nome", "Compiti e voti")): TextSelector(),
            vol.Required(R_ALUNNI, default=v.get(R_ALUNNI, list(alunni))): SelectSelector(SelectSelectorConfig(
                options=[SelectOptionDict(value=k, label=n) for k, n in alunni.items()], multiple=True)),
            vol.Required(R_UNISCI, default=v.get(R_UNISCI, False)): BooleanSelector(),
            vol.Required(R_SEZIONI, default=v.get(R_SEZIONI, ["compiti"])): SelectSelector(SelectSelectorConfig(
                options=SEZIONI_REPORT, multiple=True, translation_key="sezioni_report")),
            vol.Required(R_MAX_PAGINE, default=v.get(R_MAX_PAGINE, R_MAX_PAGINE_DEFAULT)): NumberSelector(
                NumberSelectorConfig(min=1, max=20, step=1, mode=NumberSelectorMode.BOX)),
            vol.Required(R_CARTELLA, default=v.get(R_CARTELLA, self.hass.config.path("didup_report"))): TextSelector(),
            vol.Required(R_NOME_FILE, default=v.get(R_NOME_FILE, R_NOME_FILE_DEFAULT)): TextSelector(),
            vol.Required(R_AUTOMATICO, default=v.get(R_AUTOMATICO, False)): BooleanSelector(),
            vol.Required(R_ORA, default=v.get(R_ORA, "14:00:00")): TimeSelector(),
            vol.Required(R_GIORNI, default=v.get(R_GIORNI, GIORNI_SETTIMANA[:5])): SelectSelector(SelectSelectorConfig(
                options=GIORNI_SETTIMANA, multiple=True, translation_key="giorni_settimana")),
        })
