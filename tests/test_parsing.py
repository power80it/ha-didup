"""Test delle funzioni pure (nessuna dipendenza da Home Assistant): pytest tests/"""
import datetime as dt
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("parsing", pathlib.Path(__file__).parents[1] / "custom_components/didup/parsing.py")
parsing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parsing)

OGGI = dt.date(2026, 10, 22)
DASH = {
    "registro": [
        {"materia": "ITALIANO", "datGiorno": "2026-10-20", "compiti": [
            {"dataConsegna": "2026-10-22", "compito": "per oggi"},
            {"dataConsegna": "2026-10-23", "compito": " pag. 10 "},
            {"dataConsegna": "2026-10-20", "compito": "scaduto"}]},
        {"materia": "ITALIANO", "datGiorno": "2026-10-21", "compiti": [
            {"dataConsegna": "2026-10-23", "compito": "pag. 10"}]},  # doppione
    ],
    "promemoria": [
        {"datGiorno": "2026-10-25", "oraInizio": "10:00", "desAnnotazioni": "Verifica\nmatematica", "docente": "ROSSI M."},
        {"datGiorno": "2026-10-25", "desAnnotazioni": "nascosto", "flgVisibileFamiglia": "N"},
        {"datGiorno": "2026-10-01", "desAnnotazioni": "passato"},
    ],
    "voti": [
        {"valore": 6.85, "datGiorno": "2026-10-19", "desMateria": "STORIA", "prgVoto": 1, "codVotoPratico": "N"},
        {"valore": None, "datGiorno": "2026-10-20", "desMateria": "ARTE", "prgVoto": 2},
        {"valore": 8.5, "datGiorno": "2026-10-21", "desMateria": "ARTE", "prgVoto": 3, "descrizioneProva": "x", "desCommento": "y"},
    ],
    "noteDisciplinari": [{"pk": 1, "datNota": "2026-10-10", "desDescrizione": "a  b"}, {"pk": 2, "flgAnnullata": "S"}],
    "mediaGenerale": 6.4666,
}


def test_compiti_da_domani_senza_doppioni():
    r = parsing.compiti(DASH, OGGI)
    assert [c["testo"] for c in r] == ["pag. 10"]
    assert len(parsing.compiti(DASH, OGGI, includi_oggi=True)) == 2


def test_promemoria():
    r = parsing.promemoria(DASH, OGGI)
    assert len(r) == 1 and r[0]["testo"] == "Verifica matematica" and r[0]["docente"] == "Rossi M."


def test_voti():
    r = parsing.voti(DASH)
    assert [v["voto"] for v in r] == ["8½", "7-"]  # il giudizio senza valore è scartato, dal più recente
    assert r[1]["tipo"] == "orale" and r[0]["descrizione"] == "x\ny"


def test_voto_leggibile():
    assert [parsing.voto_leggibile(x) for x in (4.0, 5.15, 6.85, 8.5)] == ["4", "5+", "7-", "8½"]


def test_note_media_slug():
    assert len(parsing.note(DASH)) == 1
    assert parsing.media_generale(DASH) == 6.47
    assert parsing.slug("Giorgia", "D'Àngelo") == "giorgia_d_angelo"
