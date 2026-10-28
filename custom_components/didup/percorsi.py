"""Scelta del PDF da servire: solo file prodotti dall'integrazione, dentro la cartella del report. Nessuna dipendenza da Home Assistant."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def trova_pdf(files: list[dict[str, Any]], cartella: str, slug: str) -> Path | None:
    """Il PDF più recente del gruppo `slug` tra quelli prodotti (mai un percorso scelto da chi chiede).

    Restituisce None se non c'è, se non è un .pdf, se non esiste più o se, risolti i collegamenti simbolici,
    non sta dentro `cartella`."""
    base = Path(cartella).resolve()
    for f in files:
        if f.get("slug") != slug:
            continue
        p = Path(str(f.get("file", ""))).resolve()
        if p.suffix.lower() == ".pdf" and p.is_file() and p.is_relative_to(base):
            return p
    return None
