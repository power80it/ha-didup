"""Test del programma settimanale (puro, nessun Home Assistant)."""
import importlib.util
import pathlib

spec = importlib.util.spec_from_file_location("programma", pathlib.Path(__file__).parents[1] / "custom_components/didup/programma.py")
programma = importlib.util.module_from_spec(spec)
spec.loader.exec_module(programma)

DATI = {"giorni": ["mon", "wed", "fri"], "ora": "14:00:00", "orari": {"mon": "13:30:00", "wed": "14:05:00", "tue": "16:15:00"}}


def test_orari_per_giorno_solo_attivi_con_predefinito():
    assert programma.orari_per_giorno(DATI) == {0: "13:30:00", 2: "14:05:00", 4: "14:00:00"}  # martedì ha un orario ma non è attivo


def test_con_orario_non_modifica_gli_altri():
    nuovo = programma.con_orario(DATI, "fri", "13:30:00")
    assert nuovo["fri"] == "13:30:00" and nuovo["mon"] == "13:30:00" and "fri" not in DATI["orari"]


def test_con_giorno_mantiene_ordine():
    assert programma.con_giorno(DATI, "tue", True) == ["mon", "tue", "wed", "fri"]
    assert programma.con_giorno(DATI, "mon", False) == ["wed", "fri"]
    assert programma.con_giorno({}, "sun", True) == ["sun"]


def test_senza_orari_tutti_al_predefinito():
    assert programma.orari_per_giorno({"giorni": ["mon", "tue"], "ora": "16:00:00"}) == {0: "16:00:00", 1: "16:00:00"}
