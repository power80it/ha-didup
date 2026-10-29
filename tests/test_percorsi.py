"""trova_pdf: serve solo i PDF prodotti, dentro la cartella del report (niente percorsi scelti da chi chiede)."""
import importlib.util
import os
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "percorsi", Path(__file__).parent.parent / "custom_components" / "didup" / "percorsi.py")
percorsi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(percorsi)
trova_pdf = percorsi.trova_pdf


def _pdf(cartella: Path, nome: str) -> str:
    p = cartella / nome
    p.write_bytes(b"%PDF-1.4 prova")
    return str(p)


def test_trova_il_pdf_dell_alunno(tmp_path):
    files = [{"slug": "luca", "file": _pdf(tmp_path, "r_luca.pdf")}, {"slug": "paolo", "file": _pdf(tmp_path, "r_paolo.pdf")}]
    assert trova_pdf(files, str(tmp_path), "paolo") == (tmp_path / "r_paolo.pdf").resolve()


def test_alunno_sconosciuto_o_file_sparito(tmp_path):
    files = [{"slug": "luca", "file": _pdf(tmp_path, "r_luca.pdf")}]
    assert trova_pdf(files, str(tmp_path), "giorgia") is None
    (tmp_path / "r_luca.pdf").unlink()
    assert trova_pdf(files, str(tmp_path), "luca") is None


def test_rifiuta_file_fuori_dalla_cartella(tmp_path):
    cart = tmp_path / "privata"
    cart.mkdir()
    fuori = _pdf(tmp_path, "segreto.pdf")
    assert trova_pdf([{"slug": "x", "file": fuori}], str(cart), "x") is None
    assert trova_pdf([{"slug": "x", "file": str(cart / ".." / "segreto.pdf")}], str(cart), "x") is None


def test_rifiuta_collegamento_simbolico_verso_l_esterno(tmp_path):
    cart = tmp_path / "privata"
    cart.mkdir()
    fuori = _pdf(tmp_path, "segreto.pdf")
    os.symlink(fuori, cart / "link.pdf")
    assert trova_pdf([{"slug": "x", "file": str(cart / "link.pdf")}], str(cart), "x") is None


def test_rifiuta_file_non_pdf(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("ciao")
    assert trova_pdf([{"slug": "x", "file": str(p)}], str(tmp_path), "x") is None


def test_cartella_spostata_il_report_vecchio_resta_apribile(tmp_path):
    vecchia, nuova = tmp_path / "www", tmp_path / "privata"
    vecchia.mkdir(), nuova.mkdir()
    registrato = _pdf(vecchia, "r_luca.pdf")  # percorso salvato prima dello spostamento
    (vecchia / "r_luca.pdf").replace(nuova / "r_luca.pdf")
    assert trova_pdf([{"slug": "luca", "file": registrato}], str(nuova), "luca") == (nuova / "r_luca.pdf").resolve()
