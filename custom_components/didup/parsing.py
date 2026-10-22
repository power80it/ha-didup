"""Funzioni pure che trasformano la dashboard Argo in dati semplici (senza dipendenze da Home Assistant)."""
from __future__ import annotations

import datetime as dt
import math
import re
import unicodedata

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]
TIPO_VOTO = {"S": "scritto", "N": "orale", "P": "pratico"}


def slug(nome: str, cognome: str) -> str:
    s = unicodedata.normalize("NFKD", f"{nome} {cognome}").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def data_leggibile(d: dt.date) -> str:
    return f"{GIORNI[d.weekday()]} {d.day} {MESI[d.month - 1]}"


def voto_leggibile(valore: float) -> str:
    """6.85 -> 7-, 5.15 -> 5+, 8.5 -> 8½, 4.0 -> 4 (come li mostra l'app Argo)."""
    v = float(valore)
    intero = math.floor(v + 1e-9)
    frac = v - intero
    if frac < 0.10:
        return f"{intero}"
    if frac < 0.35:
        return f"{intero}+"
    if frac < 0.65:
        return f"{intero}½"
    return f"{intero + 1}-"


def compiti(dash: dict, oggi: dt.date, includi_oggi: bool = False) -> list[dict]:
    """Compiti con consegna da domani in poi (o da oggi), senza doppioni, ordinati per data e materia."""
    visti, out = set(), []
    for riga in dash.get("registro", []):
        for c in riga.get("compiti", []):
            try:
                d = dt.date.fromisoformat(c["dataConsegna"])
            except (KeyError, ValueError):
                continue
            if d < oggi or (d == oggi and not includi_oggi):
                continue
            testo = (c.get("compito") or "").strip()
            chiave = (c["dataConsegna"], riga.get("materia"), testo)
            if not testo or chiave in visti:
                continue
            visti.add(chiave)
            out.append({"data": d.isoformat(), "materia": (riga.get("materia") or "").capitalize(),
                        "testo": testo, "assegnato": riga.get("datGiorno")})
    return sorted(out, key=lambda x: (x["data"], x["materia"]))


def promemoria(dash: dict, oggi: dt.date, includi_oggi: bool = True) -> list[dict]:
    visti, out = set(), []
    for p in dash.get("promemoria", []):
        if p.get("flgVisibileFamiglia") == "N":
            continue
        try:
            d = dt.date.fromisoformat(p["datGiorno"])
        except (KeyError, ValueError):
            continue
        testo = " ".join((p.get("desAnnotazioni") or "").split())
        if not testo or d < oggi or (d == oggi and not includi_oggi):
            continue
        chiave = (p["datGiorno"], p.get("oraInizio"), testo)
        if chiave in visti:
            continue
        visti.add(chiave)
        out.append({"data": d.isoformat(), "ora": p.get("oraInizio") or "",
                    "ora_fine": p.get("oraFine") or "",
                    "docente": (p.get("docente") or "").strip().title(), "testo": testo})
    return sorted(out, key=lambda x: (x["data"], x["ora"]))


def voti(dash: dict) -> list[dict]:
    """Tutti i voti, dal più recente."""
    out = []
    for v in dash.get("voti", []):
        try:
            valore = float(v["valore"])
        except (KeyError, TypeError, ValueError):
            continue  # giudizi senza valore numerico
        desc = (v.get("descrizioneProva") or "").strip()
        comm = (v.get("desCommento") or "").strip()
        out.append({"chiave": f"{v.get('datGiorno')}|{v.get('desMateria')}|{v.get('prgVoto')}",
                    "data": (v.get("datGiorno") or "")[:10], "materia": (v.get("desMateria") or "").capitalize(),
                    "voto": voto_leggibile(valore), "valore": valore,
                    "tipo": TIPO_VOTO.get(v.get("codVotoPratico"), ""),
                    "descrizione": f"{desc}\n{comm}" if desc and comm and desc != comm else (desc or comm),
                    "docente": (v.get("docente") or "").strip().title()})
    return sorted(out, key=lambda x: x["data"], reverse=True)


def note(dash: dict) -> list[dict]:
    out = []
    for n in dash.get("noteDisciplinari", []):
        if n.get("flgAnnullata") == "S" or n.get("isVisibile") is False:
            continue
        out.append({"chiave": str(n.get("pk")), "data": (n.get("datNota") or "")[:10],
                    "ora": n.get("oraNota") or "", "docente": (n.get("docente") or "").strip().title(),
                    "testo": " ".join((n.get("desDescrizione") or "").split())})
    return sorted(out, key=lambda x: x["data"], reverse=True)


def bacheca(dash: dict) -> list[dict]:
    out = []
    for b in dash.get("bacheca", []):
        out.append({"chiave": str(b.get("pk")), "data": (b.get("data") or "")[:10],
                    "autore": (b.get("autore") or "").strip().title(), "categoria": b.get("categoria") or "",
                    "testo": " ".join((b.get("messaggio") or "").split())[:300],
                    "url": b.get("url") or "", "letta": bool(b.get("isPresaVisione")),
                    "richiede_presa_visione": bool(b.get("pvRichiesta"))})
    return sorted(out, key=lambda x: x["data"], reverse=True)


def media_generale(dash: dict) -> float | None:
    m = dash.get("mediaGenerale")
    return round(float(m), 2) if isinstance(m, (int, float)) else None


def chiavi(item_list: list[dict], campi: tuple[str, ...]) -> set[str]:
    """Identità stabile degli elementi tra un refresh e l'altro (per gli eventi 'nuovo ...')."""
    return {"|".join(str(i.get(c, "")) for c in campi) for i in item_list}
