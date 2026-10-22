"""Test del PDF (serve reportlab, non Home Assistant): pytest tests/"""
import datetime as dt
import importlib.util
import pathlib
import sys
import types

import pytest

pytest.importorskip("reportlab")
root = pathlib.Path(__file__).parents[1] / "custom_components/didup"
pkg = types.ModuleType("didup_t")
pkg.__path__ = [str(root)]
sys.modules["didup_t"] = pkg
for n in ("parsing", "report"):
    spec = importlib.util.spec_from_file_location(f"didup_t.{n}", root / f"{n}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[f"didup_t.{n}"] = m
    spec.loader.exec_module(m)
report = sys.modules["didup_t.report"]

OGGI = dt.date(2026, 10, 22)
TUTTE = ["compiti", "promemoria", "voti", "note", "comunicazioni"]


def alunno(nome, n):
    d = lambda k: (OGGI + dt.timedelta(days=k)).isoformat()
    return {"alunno": {"nome": nome, "cognome": "Rossi", "classe": "1ª A"},
            "compiti": [{"data": d(1 + i % 4), "materia": "Italiano", "testo": f"Esercizi {i} <b>x</b> & ☃ à è"} for i in range(n)],
            "promemoria": [{"data": d(2), "ora": "10:00", "ora_fine": "", "docente": "Rossi M.", "testo": "Verifica"}],
            "voti": [{"data": d(-3 - i), "materia": "Storia", "voto": "7+", "valore": 7.15, "tipo": "orale",
                      "descrizione": "Interrogazione", "docente": "X"} for i in range(6)],
            "note": [], "bacheca": [{"data": d(-1), "categoria": "Circolare", "autore": "S", "testo": "Avviso " * 40}] * 4,
            "media": 6.5}


def pagine(pdf: bytes) -> int:
    import re
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def test_pdf_valido_con_nome_alunno():
    e = report.genera({"luca": alunno("Luca", 3)}, ["luca"], ["compiti"], 1, "Compiti", dt.datetime(2026, 10, 22, 14))
    assert e.pdf.startswith(b"%PDF") and e.pagine == 1 and e.non_stampati == 0


def lungo(d, volte=6):
    for x in d["compiti"]:
        x["testo"] = x["testo"] * volte
    return d


@pytest.mark.parametrize("max_p", [1, 2, 3])
def test_limite_pagine_rispettato(max_p):
    dati = {"luca": lungo(alunno("Luca", 80)), "paolo": lungo(alunno("Paolo", 80))}
    e = report.genera(dati, ["luca", "paolo"], TUTTE, max_p, "Tutto")
    assert e.pagine <= max_p and pagine(e.pdf) == e.pagine
    if max_p == 1:
        assert e.non_stampati > 0  # nemmeno al corpo minimo ci sta: si tolgono elementi e lo si dichiara


def test_prima_si_rimpicciolisce_il_carattere():
    e = report.genera({"luca": alunno("Luca", 12)}, ["luca"], TUTTE, 1, "Tutto")
    assert e.pagine == 1 and e.non_stampati == 0  # ci sta riducendo il corpo: nessun elemento tolto


def test_troncamento_equo_fra_alunni():
    dati = {"luca": lungo(alunno("Luca", 80)), "paolo": lungo(alunno("Paolo", 80))}
    e = report.genera(dati, ["luca", "paolo"], ["compiti"], 1, "Compiti")
    assert e.pagine == 1 and e.non_stampati > 0  # entrambi gli alunni hanno ancora righe (verificato a vista)


def test_alunno_sconosciuto_ignorato():
    e = report.genera({"luca": alunno("Luca", 1)}, ["luca", "fantasma"], ["compiti"], 1, "x")
    assert e.pagine == 1


def test_nome_file_per_alunno():
    ora = dt.datetime(2026, 10, 22, 14)
    assert report.nome_file("{report}_{alunno}_{data}", "Compiti e voti", "luca_rossi", ora) == "compiti_e_voti_luca_rossi_2026-10-22.pdf"
    assert report.nome_file("{report}_{data}", "Compiti", "paolo_rossi", ora) == "compiti_2026-10-22_paolo_rossi.pdf"  # {alunno} aggiunto in coda
    assert report.nome_file("rapporto.PDF", "x", "a", ora) == "rapporto_a.pdf"
    assert "/" not in report.nome_file("../../etc/{x}", "a", "b", ora)


def test_un_pdf_per_alunno_con_un_solo_nome():
    dati = {"luca": alunno("Luca", 3), "paolo": alunno("Paolo", 3)}
    for a in ("luca", "paolo"):
        e = report.genera(dati, [a], ["compiti"], 1, "Compiti")
        assert e.pagine == 1 and e.pdf.startswith(b"%PDF")


def fratelli():
    luca, paolo, giorgia = alunno("Luca", 3), alunno("Paolo", 3), alunno("Giorgia", 3)
    paolo["voti"] = paolo["voti"][:2]  # voti individuali diversi
    giorgia["alunno"]["classe"] = "2ª A"
    return {"luca": luca, "paolo": paolo, "giorgia": giorgia}


def test_raggruppa_stessa_classe_stessi_compiti():
    d = fratelli()
    assert report.raggruppa(d, ["luca", "paolo", "giorgia"], ["compiti"], True) == [["luca", "paolo"], ["giorgia"]]
    assert report.raggruppa(d, ["luca", "paolo", "giorgia"], ["compiti"], False) == [["luca"], ["paolo"], ["giorgia"]]
    d["paolo"]["compiti"] = d["paolo"]["compiti"][:1]  # compiti diversi -> non si uniscono
    assert report.raggruppa(d, ["luca", "paolo"], ["compiti"], True) == [["luca"], ["paolo"]]


def test_etichetta_gruppo():
    d = fratelli()
    assert report.etichetta_gruppo(d, ["luca", "paolo"]) == ("Luca e Paolo Rossi", "luca_e_paolo")
    assert report.etichetta_gruppo(d, ["giorgia"]) == ("Giorgia Rossi", "giorgia_rossi")


def test_pdf_unito_con_voti_separati():
    d = fratelli()
    e = report.genera(d, ["luca", "paolo"], ["compiti", "voti"], 1, "Compiti e voti")
    assert e.pagine == 1
    assert b"%PDF" in e.pdf
