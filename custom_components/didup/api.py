"""Client asincrono per Argo DidUP Famiglia (solo lettura).

I flussi (login OAuth2 PKCE dell'app mobile, endpoint ``appfamiglia``) sono quelli usati anche dalla libreria
``argofamiglia``; qui sono riscritti in asincrono e tengono i token di TUTTE le schede dell'account
(la libreria originale ne legge una sola).
"""
from __future__ import annotations

import asyncio
import base64
import datetime as dt
import json
import logging
import re
import secrets
from hashlib import sha256

import aiohttp

_LOGGER = logging.getLogger(__name__)

ENDPOINT = "https://www.portaleargo.it/appfamiglia/api/rest/"
CHALLENGE_URL = "https://auth.portaleargo.it/oauth2/auth"
LOGIN_URL = "https://www.portaleargo.it/auth/sso/login"
TOKEN_URL = "https://auth.portaleargo.it/oauth2/token"
REDIRECT_URI = "it.argosoft.didup.famiglia.new://login-callback"
CLIENT_ID = "72fd6dea-d0ab-4bb9-8eaa-3ac24c84886c"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/106.0.0.0 Safari/537.36")

DASHBOARD_OPTIONS = {
    "ARGOMENTI_LEZIONE": True, "ASSENZE_PER_DATA": True, "COMPITI_ASSEGNATI": True,
    "CONSIGLIO_DI_CLASSE": True, "DISABILITA_ACCESSO_FAMIGLIA": True, "DOCENTI_CLASSE": True,
    "GIUSTIFICAZIONI_ASSENZE": True, "IGNORA_OPZIONE_VOTI_DOCENTI": True, "NASCONDI_DIDUP_FAMIGLIA": True,
    "NOTE_DISCIPLINARI": True, "ORARIO_SCOLASTICO": True, "PROMEMORIA_CLASSE": True,
    "VALUTAZIONI_GIORNALIERE": True, "VALUTAZIONI_PERIODICHE": True, "VOTI_GIUDIZI": True,
}

_CHALLENGE_RE = re.compile(r"login_challenge=([0-9a-f]+)&?")
_CODE_RE = re.compile(r"code=([0-9a-zA-Z\-_.]+)&?")
TENTATIVI = 3
TIMEOUT = aiohttp.ClientTimeout(total=60)


class DidupError(Exception):
    """Errore temporaneo (rete, sessione scaduta, risposta inattesa): si riprova al prossimo giro."""


class DidupAuthError(DidupError):
    """Credenziali rifiutate: inutile riprovare, serve reauth (rischio blocco account)."""


class DidupApi:
    """Una lettura completa = un login nuovo (nessuna sessione lunga da mantenere)."""

    def __init__(self, session: aiohttp.ClientSession, codice: str, utente: str, password: str) -> None:
        self._s = session
        self._codice = codice
        self._utente = utente
        self._password = password

    async def _login(self) -> tuple[str, list[str]]:
        verifier = secrets.token_hex(64)
        challenge = base64.urlsafe_b64encode(sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        params = {
            "redirect_uri": REDIRECT_URI, "client_id": CLIENT_ID, "response_type": "code", "prompt": "login",
            "state": secrets.token_urlsafe(32), "scope": "openid offline profile user.roles argo",
            "code_challenge": challenge, "code_challenge_method": "S256",
        }
        async with self._s.get(CHALLENGE_URL, params=params, timeout=TIMEOUT) as r:
            m = _CHALLENGE_RE.search(str(r.url))
        if not m:
            raise DidupError("login_challenge non trovato")
        form = {"challenge": m.group(1), "client_id": CLIENT_ID, "prefill": "true",
                "famiglia_customer_code": self._codice, "username": self._utente,
                "password": self._password, "login": "true"}
        async with self._s.post(LOGIN_URL, data=form, allow_redirects=False, timeout=TIMEOUT) as r:
            loc = r.headers.get("Location")
        if not loc:
            raise DidupAuthError("credenziali rifiutate")
        code = None
        for _ in range(10):
            mc = _CODE_RE.search(loc)
            if mc:
                code = mc.group(1)
                break
            async with self._s.get(loc, allow_redirects=False, timeout=TIMEOUT) as r:
                loc = r.headers.get("Location")
            if not loc:
                break
        if not code:
            raise DidupError("codice di autorizzazione non trovato")
        data = {"code": code, "grant_type": "authorization_code", "redirect_uri": REDIRECT_URI,
                "code_verifier": verifier, "client_id": CLIENT_ID}
        async with self._s.post(TOKEN_URL, data=data, timeout=TIMEOUT) as r:
            tokens = await r.json(content_type=None)
        access = tokens.get("access_token")
        if not access:
            raise DidupError("access_token mancante")
        body = {"clientID": secrets.token_urlsafe(64), "lista-x-auth-token": "[]",
                "x-auth-token-corrente": "null", "lista-opzioni-notifiche": "{}"}
        hdr = {"User-Agent": USER_AGENT, "Content-Type": "Application/json",
               "Authorization": "Bearer " + access, "Accept": "Application/json"}
        async with self._s.post(ENDPOINT + "login", headers=hdr, json=body, timeout=TIMEOUT) as r:
            j = await r.json(content_type=None)
        try:
            schede = [s["token"] for s in j["data"]]
        except (KeyError, TypeError) as e:
            raise DidupError("elenco schede non valido") from e
        if not schede:
            raise DidupError("nessuna scheda sull'account")
        return access, schede

    def _headers(self, access: str, token: str) -> dict:
        return {"Content-Type": "Application/json", "Authorization": "Bearer " + access,
                "Accept": "Application/json", "x-cod-min": self._codice, "x-auth-token": token,
                "User-Agent": USER_AGENT}

    async def _profilo(self, access: str, token: str) -> dict:
        async with self._s.get(ENDPOINT + "profilo", headers=self._headers(access, token), timeout=TIMEOUT) as r:
            j = await r.json(content_type=None)
        try:
            d = j["data"]
            cl = d["scheda"]["classe"]
            return {"nome": d["alunno"]["nome"].strip().title(), "cognome": d["alunno"]["cognome"].strip().title(),
                    "classe": f"{cl['desDenominazione']}ª {cl['desSezione']}"}
        except (KeyError, TypeError, AttributeError) as e:
            raise DidupError("profilo non valido") from e

    async def _dashboard(self, access: str, token: str) -> dict:
        now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        body = {"dataultimoaggiornamento": now, "opzioni": json.dumps(DASHBOARD_OPTIONS)}
        async with self._s.post(ENDPOINT + "dashboard/dashboard", headers=self._headers(access, token),
                                json=body, timeout=TIMEOUT) as r:
            j = await r.json(content_type=None)
        try:
            if not j.get("success", True):
                raise DidupError(str(j.get("msg")))
            return j["data"]["dati"][0]
        except (KeyError, IndexError, TypeError, AttributeError) as e:
            raise DidupError("dashboard non valida") from e

    async def async_alunni(self) -> list[dict]:
        """Solo login + anagrafica (per il config flow): [{'nome','cognome','classe'}]."""
        access, schede = await self._login()
        return [await self._profilo(access, t) for t in schede]

    async def async_leggi(self) -> list[dict]:
        """Login nuovo + lettura di tutte le schede: [{'alunno': {...}, 'dashboard': {...}}].

        Le credenziali errate non si riprovano mai; ogni altro errore: fino a 3 tentativi con login nuovo.
        """
        ultimo: Exception | None = None
        for n in range(TENTATIVI):
            try:
                access, schede = await self._login()
                out = []
                for t in schede:
                    out.append({"alunno": await self._profilo(access, t), "dashboard": await self._dashboard(access, t)})
                return out
            except DidupAuthError:
                raise
            except (DidupError, aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
                ultimo = e
                _LOGGER.debug("Lettura DidUP fallita (tentativo %s): %s", n + 1, e)
                if n < TENTATIVI - 1:
                    await asyncio.sleep(5 * (n + 1))
        raise DidupError(f"lettura fallita: {ultimo}") from ultimo
