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


# --- medie per quadrimestre ---------------------------------------------------------------------------------------
PERIODI = [
    {"pkPeriodo": "a", "codPeriodo": "1Q", "descrizione": "PRIMO QUADRIMESTRE", "datInizio": "2026-09-14", "datFine": "2027-01-31"},
    {"pkPeriodo": "b", "codPeriodo": "SF", "descrizione": "SCRUTINIO FINALE", "datInizio": "2027-02-01", "datFine": "2027-06-10"},
    {"pkPeriodo": "*", "codPeriodo": "*", "descrizione": "Intero Anno", "datInizio": "2026-09-01", "datFine": "2027-08-31"},
]


def _v(valore, giorno, materia, n, **extra):
    return {"valore": valore, "datGiorno": giorno, "desMateria": materia, "prgVoto": n, **extra}


def test_periodi_nomi_per_posizione_e_senza_intero_anno():
    p = parsing.periodi({"listaPeriodi": list(reversed(PERIODI))})
    assert [(x["id"], x["nome"]) for x in p] == [("1Q", "Primo quadrimestre"), ("SF", "Secondo quadrimestre")]
    assert parsing.periodo_di(p, "2026-10-01") == "1Q" and parsing.periodo_di(p, "2027-03-01") == "SF"
    assert parsing.periodo_di(p, "2026-08-01") == ""


def test_media_e_media_delle_medie_di_materia_come_argo():
    # Giorgia (dati reali 17/11/2026, 1º quadrimestre, solo matematica e italiano): la media NON è quella di tutti i voti
    dash = {"listaPeriodi": PERIODI, "voti": [
        _v(6.85, "2026-09-25", "MATEMATICA", 1), _v(4.85, "2026-10-21", "MATEMATICA", 2), _v(7.0, "2026-11-11", "MATEMATICA", 3),
        _v(4.0, "2026-10-14", "ITALIANO", 4)]}
    q1, q2 = parsing.medie_periodi(dash)
    assert q1["materie"] == [{"materia": "Matematica", "media": 6.23, "n": 3}, {"materia": "Italiano", "media": 4.0, "n": 1}]
    assert q1["media"] == 5.12 and q1["n_voti"] == 4  # (6.2333 + 4) / 2, non 22.7 / 4 = 5.675
    assert q2["media"] is None and q2["materie"] == [] and q2["nome"] == "Secondo quadrimestre"


def test_i_quadrimestri_sono_separati_e_i_voti_fuori_periodo_o_non_numerici_non_contano():
    dash = {"listaPeriodi": PERIODI, "voti": [
        _v(8.0, "2027-01-31", "ARTE", 1), _v(6.0, "2027-02-01", "ARTE", 2), _v(None, "2026-10-02", "ARTE", 3),
        _v(9.0, "2026-08-31", "ARTE", 4)]}
    q1, q2 = parsing.medie_periodi(dash)
    assert (q1["media"], q1["n_voti"], q2["media"], q2["n_voti"]) == (8.0, 1, 6.0, 1)
    assert [v["periodo"] for v in parsing.voti(dash)] == ["SF", "1Q", ""]  # il voto di agosto non è in nessun quadrimestre


def test_voto_che_fa_meno_media_e_ordine_materie():
    dash = {"listaPeriodi": PERIODI, "voti": [
        _v(10.0, "2026-10-01", "STORIA", 1, faMenoMedia="S"), _v(7.0, "2026-10-02", "STORIA", 2),
        _v(8.0, "2026-10-03", "ARTE", 3), _v(8.0, "2026-10-04", "ARTE", 4), _v(8.0, "2026-10-05", "ALFA", 5)]}
    q1 = parsing.medie_periodi(dash)[0]
    assert [(m["materia"], m["media"]) for m in q1["materie"]] == [("Alfa", 8.0), ("Arte", 8.0), ("Storia", 7.0)]
    assert q1["media"] == 7.67
    assert [v["fa_media"] for v in parsing.voti(dash) if v["materia"] == "Storia"] == [True, False]


def test_senza_periodi_nessuna_media():
    assert parsing.medie_periodi({"voti": [_v(7.0, "2026-10-01", "ARTE", 1)]}) == []
