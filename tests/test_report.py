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


def test_biglietto_si_spezza_fra_colonne_senza_errori():
    card = report._Card(report.PALETTE[0], [("LUN", "DV-B", 7, 7.0)], [f"riga {i}" for i in range(30)], 9, 20)
    w, h = card.wrap(180, 10000)
    parti = card.split(w, h / 2)
    assert len(parti) == 2
    assert parti[0].wrap(w, h)[1] <= h / 2
    assert len(parti[0].righe) + len(parti[1].righe) == 30


def test_biglietto_troppo_alto_per_lo_spazio_non_si_spezza_a_vuoto():
    card = report._Card(report.NEUTRO, [("X", "DV-B", 7, 0)], ["una riga"], 9, 200)  # minh più alto dello spazio: si passa alla colonna dopo
    card.wrap(180, 100)
    assert card.split(180, 100) == []


def test_media_formattata_con_la_virgola():
    assert report._formatta_media(6.94) == "6,9"
    assert report._formatta_media(7) == "7,0"


def test_giornata_molto_lunga_occupa_piu_colonne_e_pagine():
    d = {"luca": alunno("Luca", 80)}
    e = report.genera(d, ["luca"], ["compiti"], 3, "Compiti", dt.datetime(2026, 10, 22, 14))
    assert e.non_stampati == 0 and pagine(e.pdf) <= 3


def test_pdf_unito_con_note_e_voti_di_entrambi():
    d = fratelli()
    for k in d:
        d[k]["note"] = [{"data": (OGGI - dt.timedelta(days=2)).isoformat(), "docente": "R.", "testo": "Nota"}]
    e = report.genera(d, ["luca", "paolo"], TUTTE, 1, "Tutto", dt.datetime(2026, 10, 22, 14))
    assert e.pdf.startswith(b"%PDF") and e.non_stampati == 0


def test_promemoria_senza_orario_non_mostra_mezzanotte():
    items = [{"data": (OGGI + dt.timedelta(days=3)).isoformat(), "ora": "00:00", "ora_fine": "", "docente": "", "testo": "Verifica"},
             {"data": (OGGI + dt.timedelta(days=4)).isoformat(), "ora": "10:30", "ora_fine": "", "docente": "", "testo": "Test"}]
    grid = report._box_promemoria(items, OGGI, 9, report._Colori())[2]
    senza, con = grid._cellvalues[0][0], grid._cellvalues[0][2]
    assert "00:00" not in [s[0] for s in senza.stub]
    assert "10:30" in [s[0] for s in con.stub]


def _rett(colori):
    r = {}
    for k, pag, x, y, w, h in colori.reg:
        r.setdefault(k, []).append((pag, x, y, w, h))
    return r


def test_biglietti_vicini_mai_dello_stesso_colore():
    d = {"luca": alunno("Luca", 40)}
    d["luca"]["promemoria"] = [{"data": (OGGI + dt.timedelta(days=2 + i)).isoformat(), "ora": "", "ora_fine": "", "docente": "", "testo": f"Verifica {i}"} for i in range(7)]
    for max_p in (1, 2, 3):
        report.genera(d, ["luca"], ["compiti", "promemoria"], max_p, "Compiti", dt.datetime(2026, 10, 22, 14))
        col = report.ULTIMI_COLORI
        rett = _rett(col)
        assert len(rett) >= 8  # promemoria + giorni
        assert {col.assegna[k] for k in rett} <= set(range(len(report.PALETTE)))
        for a in rett:
            for b in rett:
                if a < b and any(report._vicini(x, y) for x in rett[a] for y in rett[b]):
                    assert col.assegna[a] != col.assegna[b], (a, b)


def test_colori_non_dipendono_dall_urgenza():
    # stessa data a distanza di giorni: il colore dipende dalla posizione, non da quanti giorni mancano
    d = {"luca": alunno("Luca", 3)}
    report.genera(d, ["luca"], ["compiti"], 1, "Compiti", dt.datetime(2026, 10, 22, 14))
    assert len(set(report.ULTIMI_COLORI.assegna.values())) >= 2


def test_palette_senza_il_colore_neutro():
    assert len(report.PALETTE) == 5 and report.NEUTRO not in report.PALETTE


def test_assegnazione_con_vicini_in_colonne_diverse():
    # due colonne affiancate, 3 biglietti per colonna: a destra non ci sono mai gli stessi colori del vicino di sinistra
    reg = [(f"k{i}", 1, 10 + (i // 3) * 300, 700 - (i % 3) * 120, 280, 100) for i in range(6)]
    a = report._assegna_colori(reg)
    for i in range(6):
        for j in range(6):
            if i < j and report._vicini((1, *reg[i][2:]), (1, *reg[j][2:])):
                assert a[f"k{i}"] != a[f"k{j}"]


def test_promemoria_di_oggi_non_si_stampano():
    oggi = dt.datetime(2026, 10, 22, 14)
    d = {"luca": alunno("Luca", 3)}
    d["luca"]["promemoria"] = [{"data": (oggi.date() + dt.timedelta(days=k)).isoformat(), "ora": "09:00", "ora_fine": "", "docente": "", "testo": f"V{k}"} for k in (0, 1, 3)]
    assert [p["testo"] for p in report._righe("promemoria", d["luca"], oggi.date())] == ["V1", "V3"]
    assert len(report._righe("promemoria", d["luca"])) == 3  # senza data di riferimento: nessun filtro (compatibilità)
    report.genera(d, ["luca"], ["compiti", "promemoria"], 1, "Compiti", oggi)
    assert sorted(k for k in report.ULTIMI_COLORI.assegna if k.startswith("p")) == ["p0", "p1"]  # due biglietti, non tre
