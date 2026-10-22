"""Programma settimanale di un report: ogni giorno può avere un orario diverso (nessun Home Assistant qui)."""
from __future__ import annotations

GIORNI = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # indice = datetime.weekday()


def giorni_attivi(data: dict) -> list[str]:
    return [g for g in GIORNI if g in (data.get("giorni") or [])]


def ora_del_giorno(data: dict, giorno: str) -> str:
    """Orario «HH:MM:SS» del giorno: quello suo, se impostato, altrimenti quello predefinito del report."""
    return (data.get("orari") or {}).get(giorno) or data.get("ora") or "14:00:00"


def orari_per_giorno(data: dict) -> dict[int, str]:
    """{weekday: 'HH:MM:SS'} dei soli giorni attivi."""
    return {GIORNI.index(g): ora_del_giorno(data, g) for g in giorni_attivi(data)}


def con_orario(data: dict, giorno: str, ora: str) -> dict:
    return {**(data.get("orari") or {}), giorno: ora}


def con_giorno(data: dict, giorno: str, attivo: bool) -> list[str]:
    attuali = set(data.get("giorni") or [])
    attuali.add(giorno) if attivo else attuali.discard(giorno)
    return [g for g in GIORNI if g in attuali]
