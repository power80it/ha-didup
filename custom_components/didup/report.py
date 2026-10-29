"""Generazione del PDF dei report (reportlab, nessun Home Assistant). Aspetto «biglietto» di DidUP (dalla 0.6.0).

Testata sfumata blu/verde acqua con taglio arancio (nome a sinistra, classe e aggiornamento a destra), promemoria come
biglietti con talloncino, un riquadro-biglietto per giorno su 2-3
colonne con le caselle ▢, e riquadri analoghi per voti, note e comunicazioni. Ogni biglietto ha il talloncino colorato a
sinistra e un filo dello stesso colore sul bordo superiore. I colori ruotano senza significato (palette di 5) e non sono mai uguali
fra biglietti vicini; voti, note e comunicazioni sono sempre ardesia.

Il numero massimo di pagine è un limite rigido. Per far stare tutto si prova prima a rimpicciolire il carattere (da 11 a 6 pt, 2-3
colonne); solo se nemmeno al minimo ci sta si tolgono elementi dalle sezioni più lunghe (equo fra le sezioni, partendo dagli ultimi)
e il piè di pagina indica quanti elementi non sono stati stampati.
"""
from __future__ import annotations

import datetime as dt
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, FrameBreak, KeepTogether, NextPageTemplate, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from . import parsing

SEZIONI = ["compiti", "promemoria", "voti", "note", "comunicazioni"]
INDIVIDUALI = ("voti", "note")  # personali: in un PDF unito restano separate per alunno (il resto è di classe)
TITOLI = {"compiti": "Compiti", "promemoria": "Promemoria e verifiche", "voti": "Voti",
          "note": "Note disciplinari", "comunicazioni": "Comunicazioni della scuola"}
MAX_VOTI = 15
MAX_COMUNICAZIONI = 10

FONTS = Path(__file__).parent / "fonts"  # DejaVu (licenza in fonts/LICENSE.txt): copre accenti, ▢ e simboli
INK = colors.HexColor("#1f2933")
GRIGIO = colors.HexColor("#6b7785")
ROSSO, ARANCIO = colors.HexColor("#c0392b"), colors.HexColor("#d9822b")
VERDE = colors.HexColor("#2e7d32")
# colori dei biglietti dei promemoria e dei giorni: nessun significato (non indicano l'urgenza), ruotano senza mai ripetersi fra vicini
PALETTE = [colors.HexColor("#3f8fcf"), colors.HexColor("#8f7bd0"), colors.HexColor("#e88a5c"), colors.HexColor("#3aa68a"), colors.HexColor("#c9a227")]
NEUTRO = colors.HexColor("#5f6b7a")  # ardesia: voti, note e avvisi (non è nella palette, quindi non si confonde coi giorni)
BLU_CH, VERDE_ACQUA = colors.HexColor("#1e88e5"), colors.HexColor("#12b3a8")  # sfumatura della testata
ARA_CH, ARA_SC = colors.HexColor("#fbb34a"), colors.HexColor("#f08a2b")  # taglio arancio della testata
MARG = 10 * mm
W = A4[0] - 2 * MARG
H = A4[1]
ABBR = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]
# (colonne, corpo in pt) provati in ordine: il primo che sta nel limite di pagine vince
CANDIDATI = [(2, 11.0), (2, 10.5), (2, 10.0), (2, 9.5), (2, 9.0), (2, 8.5), (2, 8.0), (2, 7.5), (2, 7.0), (3, 7.5), (3, 7.0),
             (2, 6.5), (3, 6.5), (3, 6.0)]
_font_ok = False


def _fonts() -> None:
    global _font_ok
    if _font_ok:
        return
    for nome, f in (("DV", "DejaVuSans"), ("DV-B", "DejaVuSans-Bold"), ("DV-I", "DejaVuSans-Oblique")):
        pdfmetrics.registerFont(TTFont(nome, str(FONTS / f"{f}.ttf")))
    pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-B")
    _font_ok = True


def _h(s) -> str:
    return escape(str(s or "")).replace("\n", "<br/>")


def _breve(iso: str, oggi: dt.date) -> tuple[str, int]:
    d = dt.date.fromisoformat(iso[:10])
    return f"{ABBR[d.weekday()]} {d.day}/{d.month}", (d - oggi).days


def _colore_voto(v: float):
    return VERDE if v >= 6 else ARANCIO if v >= 5 else ROSSO


def _hex(c) -> str:
    return "#" + c.hexval()[2:]


# ----------------------------------------------------------------------------------------------- elementi
def _righe(sezione: str, dati: dict, oggi: dt.date | None = None) -> list[dict]:
    """Elementi della sezione, già nell'ordine di stampa (i dizionari del coordinator, eventualmente accorciati).
    I promemoria di oggi non si stampano (restano nelle entità e nel calendario): il PDF è per quello che deve ancora venire."""
    if sezione == "promemoria" and oggi is not None:
        return [p for p in dati.get("promemoria", []) if str(p.get("data", ""))[:10] > oggi.isoformat()]
    if sezione == "voti":
        return dati.get("voti", [])[:MAX_VOTI]
    if sezione == "comunicazioni":
        return dati.get("bacheca", [])[:MAX_COMUNICAZIONI]
    return list(dati.get(sezione, []))


MESI = ["GEN", "FEB", "MAR", "APR", "MAG", "GIU", "LUG", "AGO", "SET", "OTT", "NOV", "DIC"]
GRIGIO_BORDO = colors.HexColor("#d5dbe1")


class _Colori:
    """Colore di ogni biglietto (promemoria e giorni). Prima passata: colori a rotazione e registrazione di dove finisce ogni biglietto;
    seconda passata: i colori calcolati da `_assegna_colori` sulla posizione reale, così due biglietti vicini non sono mai uguali."""

    def __init__(self, assegna: dict[str, int] | None = None):
        self.assegna, self.reg, self._n, self._dati = assegna or {}, [], 0, {}

    def colore(self, chiave: str):
        if chiave not in self._dati:
            self._dati[chiave] = self.assegna.get(chiave, self._n % len(PALETTE))
            self._n += 1
        return PALETTE[self._dati[chiave]]


ULTIMI_COLORI: _Colori | None = None  # l'ultima assegnazione (per i test)


def _vicini(a: tuple, b: tuple) -> bool:
    """a, b = (pagina, x, y, larghezza, altezza). Vicini: affiancati (anche in colonne diverse) o uno sopra l'altro a meno di 14 mm
    (il divisore «Compiti da fare» non li separa abbastanza)."""
    if a[0] != b[0]:
        return False
    _, ax, ay, aw, ah = a
    _, bx, by, bw, bh = b
    sov_x = min(ax + aw, bx + bw) - max(ax, bx)
    sov_y = min(ay + ah, by + bh) - max(ay, by)
    return (sov_x > 0 and max(ay - (by + bh), by - (ay + ah)) <= 14 * mm) or (sov_y > 0 and max(ax - (bx + bw), bx - (ax + aw)) <= 6 * mm)


def _assegna_colori(reg: list[tuple]) -> dict[str, int]:
    """Un indice di PALETTE per chiave, mai uguale fra biglietti vicini. Colori a rotazione in ordine di lettura; ricerca con ritorno
    indietro se serve (con un limite di tentativi: poi si accetta il meno peggio)."""
    n = len(PALETTE)
    rett: dict[str, list[tuple]] = {}
    for k, pag, x, y, w, h in reg:
        rett.setdefault(k, []).append((pag, x, y, w, h))
    chiavi = sorted(rett, key=lambda k: min((r[0], -(r[2] + r[4]), r[1]) for r in rett[k]))
    vic = {k: {j for j in chiavi if j != k and any(_vicini(a, b) for a in rett[k] for b in rett[j])} for k in chiavi}
    res: dict[str, int] = {}
    passi = [0]

    def prova(i: int) -> bool:
        if i == len(chiavi):
            return True
        passi[0] += 1
        if passi[0] > 20000:
            return False
        k = chiavi[i]
        usati = {res[j] for j in vic[k] if j in res}
        ultimo = res[chiavi[i - 1]] if i else -1
        for c in sorted(range(n), key=lambda c: (c - ultimo - 1) % n):
            if c not in usati:
                res[k] = c
                if prova(i + 1):
                    return True
                del res[k]
        return False

    if not prova(0):
        res = {}
        for i, k in enumerate(chiavi):  # ripiego: il colore meno usato dai vicini
            usati = [res[j] for j in vic[k] if j in res]
            res[k] = min(range(n), key=lambda c: (usati.count(c), (c - (res[chiavi[i - 1]] if i else -1) - 1) % n))
    return res


def _k(fs: float) -> float:
    """Fattore di scala dei talloncini rispetto al corpo normale (9 pt): si rimpiccioliscono col testo."""
    return min(1.15, max(0.7, fs / 9))


def _sfuma(c, x: float, y: float, w: float, h: float, a, b, n: int = 50) -> None:
    """Sfumatura orizzontale a fette (compatibile con tutte le viste PDF)."""
    for i in range(n):
        f = i / (n - 1)
        c.setFillColor(colors.Color(*[a.rgb()[j] * (1 - f) + b.rgb()[j] * f for j in range(3)]))
        c.rect(x + i * w / n, y, w / n + 0.5, h, fill=1, stroke=0)


def _talloncino(c, sw: float, h: float, col, bianco_sopra: bool = True) -> None:
    """Parte colorata a sinistra del biglietto, perforazione tratteggiata e due tacche."""
    c.setFillColor(col)
    c.rect(0, 0, sw, h, fill=1, stroke=0)
    c.setStrokeColor(colors.white)
    c.setDash(1.6, 1.6)
    c.setLineWidth(1)
    c.line(sw, 1 * mm, sw, h - 1 * mm)
    c.setDash()
    c.setFillColor(colors.white)
    c.circle(sw, h, 1.6 * mm, fill=1, stroke=0)
    c.circle(sw, 0, 1.6 * mm, fill=1, stroke=0)


def _clip_arrotondato(c, w: float, h: float, r: float) -> None:
    p = c.beginPath()
    p.roundRect(0, 0, w, h, r)
    c.clipPath(p, stroke=0, fill=0)


class _Testata(Flowable):
    """Fascia in cima: sfumatura blu/verde acqua con taglio diagonale arancio, nome a sinistra, classe e aggiornamento a destra."""
    ALTEZZA = 18 * mm

    def __init__(self, nome: str, righe: list[str]):
        super().__init__()
        self.nome, self.righe = nome, righe

    def wrap(self, aw, ah):
        self.w = aw
        return aw, self.ALTEZZA

    def draw(self):
        c, w, h = self.canv, self.w, self.ALTEZZA
        c.saveState()
        _clip_arrotondato(c, w, h, 5 * mm)
        _sfuma(c, 0, 0, w, h, BLU_CH, VERDE_ACQUA, 60)
        taglio = c.beginPath()
        taglio.moveTo(w * 0.75, h)
        taglio.lineTo(w, h)
        taglio.lineTo(w, 0)
        taglio.lineTo(w * 0.69, 0)
        taglio.close()
        c.saveState()
        c.clipPath(taglio, stroke=0, fill=0)
        _sfuma(c, w * 0.67, 0, w * 0.33, h, ARA_CH, ARA_SC, 40)
        c.restoreState()
        c.setStrokeColor(colors.Color(1, 1, 1, 0.55))
        c.setLineWidth(0.9)
        c.line(w * 0.75, h, w * 0.69, 0)
        for cx, cy, r, al in ((0.93, 0.85, 14, 0.22), (0.82, 0.02, 8, 0.2), (0.5, 0.98, 6, 0.11), (0.04, 0.0, 8, 0.10)):
            c.setFillColor(colors.Color(1, 1, 1, al))
            c.circle(w * cx, h * cy, r * mm * 0.85, fill=1, stroke=0)
        c.restoreState()
        fs = 18.0
        while fs > 11 and pdfmetrics.stringWidth(self.nome, "DV-B", fs) > w * 0.69 - 12 * mm:
            fs -= 0.5
        c.setFillColor(colors.white)
        c.setFont("DV-B", fs)
        c.drawString(6 * mm, h / 2 - 2 * mm * fs / 18, self.nome)
        n = len(self.righe)
        c.setFillColor(colors.HexColor("#111111"))
        for i, riga in enumerate(self.righe):
            f = 9.5
            while f > 6.5 and pdfmetrics.stringWidth(riga, "DV-B", f) > w * 0.28 - 6 * mm:
                f -= 0.5
            c.setFont("DV-B", f)
            c.drawRightString(w - 6 * mm, h / 2 + (n - 1) * 2.9 * mm - i * 5.8 * mm - 1.6 * mm, riga)


class _Divisore(Flowable):
    """Titoletto con un filo che prosegue fino al margine destro (separa i promemoria dai compiti)."""

    def __init__(self, testo: str, fs: float = 7.5):
        super().__init__()
        self.testo, self.fs = testo, fs

    def wrap(self, aw, ah):
        self.w = aw
        return aw, self.fs * 1.6

    def draw(self):
        c = self.canv
        c.setFillColor(GRIGIO)
        t = c.beginText(0, self.fs * 0.35)
        t.setFont("DV-B", self.fs)
        t.setCharSpace(0.6)
        t.textOut(self.testo)
        c.drawText(t)
        x = pdfmetrics.stringWidth(self.testo, "DV-B", self.fs) + 0.6 * len(self.testo) + 3 * mm
        c.setStrokeColor(colors.HexColor("#c4ccd4"))
        c.setLineWidth(0.8)
        c.line(x, self.fs * 0.35 + self.fs * 0.3, self.w, self.fs * 0.35 + self.fs * 0.3)


class _Card(Flowable):
    """Riquadro «biglietto»: talloncino colorato a sinistra (righe di `stub`), corpo bianco con una riga per elemento e filo
    colorato sul bordo superiore. Si spezza riga per riga fra colonne e pagine (il talloncino si ripete)."""
    SW = 15 * mm

    def __init__(self, colore, stub: list, righe: list[str], fs: float, minh: float, chiave: str | None = None, colori: _Colori | None = None):
        super().__init__()
        self.colore, self.stub, self.righe, self.fs, self.minh, self.chiave, self.colori = colore, stub, righe, fs, minh, chiave, colori
        self.gap = 1.0 * mm * _k(fs)

    def _layout(self, aw):
        st = ParagraphStyle("c", fontName="DV", fontSize=self.fs, leading=self.fs * 1.28, textColor=INK,
                            leftIndent=self.fs * 1.6, firstLineIndent=-self.fs * 1.6)
        self._ps = [Paragraph(r, st) for r in self.righe]
        tw = aw - self.SW - 7 * mm
        self._ph = [p.wrap(tw, 10000)[1] for p in self._ps]

    def wrap(self, aw, ah):
        self.w = aw
        self._layout(aw)
        self.h = max(self.minh, sum(h + 2 * self.gap for h in self._ph) + 3 * mm)
        return self.w, self.h

    def split(self, aw, ah):
        self.wrap(aw, ah)
        acc, n = 0.0, 0
        for h in self._ph:
            if max(self.minh, acc + h + 2 * self.gap + 3 * mm) > ah:
                break
            acc += h + 2 * self.gap
            n += 1
        if n == 0:
            return []
        if n == len(self.righe):
            return [self]
        return [_Card(self.colore, self.stub, self.righe[:n], self.fs, self.minh, self.chiave, self.colori),
                _Card(self.colore, self.stub, self.righe[n:], self.fs, self.minh, self.chiave, self.colori)]

    def draw(self):
        c, w, h, col, sw = self.canv, self.w, self.h, self.colore, self.SW
        if self.colori is not None and self.chiave:
            x0, y0 = c.absolutePosition(0, 0)
            self.colori.reg.append((self.chiave, c.getPageNumber(), x0, y0, w, h))
        c.setFillColor(colors.white)
        c.setStrokeColor(GRIGIO_BORDO)
        c.setLineWidth(0.6)
        c.roundRect(0, 0, w, h, 2 * mm, fill=1, stroke=1)
        c.saveState()
        _clip_arrotondato(c, w, h, 2 * mm)
        _talloncino(c, sw, h, col)
        c.restoreState()
        ks = min(1.1, max(0.75, self.fs / 9))
        for s, f, sz, dy in self.stub:
            c.setFillColor(colors.white)
            c.setFont(f, sz * ks)
            c.drawCentredString(sw / 2, h / 2 + dy * mm * ks, s)
        y = h - 1.5 * mm
        for p, ph in zip(self._ps, self._ph):
            p.drawOn(c, sw + 4 * mm, y - self.gap - ph)
            y -= ph + 2 * self.gap
        c.setStrokeColor(col)
        c.setLineWidth(2.4)
        c.setLineCap(1)
        c.line(3 * mm, h, w - 3 * mm, h)
        c.setLineCap(0)


class _Biglietto(Flowable):
    """Promemoria: talloncino colorato a sinistra (giorno, data, ora), testo in grassetto, docente in corsivo e barra colorata
    in cima al corpo."""
    SW = 19 * mm

    def __init__(self, colore, stub: list, testo: str, docente: str, fs: float, chiave: str | None = None, colori: _Colori | None = None):
        super().__init__()
        self.colore, self.stub, self.testo, self.docente, self.fs, self.chiave, self.colori = colore, stub, testo, docente, fs, chiave, colori
        self.k = _k(fs)

    def wrap(self, aw, ah):
        self.w = aw
        tw = aw - self.SW - 7 * mm
        self._p = [Paragraph(f"<b>{_h(self.testo)}</b>", ParagraphStyle("bt", fontName="DV-B", fontSize=self.fs + 0.2, leading=(self.fs + 0.2) * 1.25, textColor=INK))]
        if self.docente:
            self._p.append(Paragraph(_h(self.docente), ParagraphStyle("bd", fontName="DV-I", fontSize=max(self.fs - 1.5, 5.5), leading=self.fs * 1.2, textColor=GRIGIO)))
        self._ph = [p.wrap(tw, 10000)[1] for p in self._p]
        self.h = max(19 * mm * self.k, 5 * mm + sum(self._ph))
        return self.w, self.h

    def draw(self):
        c, w, h, col, sw = self.canv, self.w, self.h, self.colore, self.SW
        if self.colori is not None and self.chiave:
            x0, y0 = c.absolutePosition(0, 0)
            self.colori.reg.append((self.chiave, c.getPageNumber(), x0, y0, w, h))
        c.setFillColor(colors.white)
        c.setStrokeColor(GRIGIO_BORDO)
        c.setLineWidth(0.6)
        c.roundRect(0, 0, w, h, 2 * mm, fill=1, stroke=1)
        c.saveState()
        _clip_arrotondato(c, w, h, 2 * mm)
        _talloncino(c, sw, h, col)
        c.setFillColor(col)
        c.rect(sw, h - 1.3 * mm, w - sw, 1.3 * mm, fill=1, stroke=0)
        c.restoreState()
        ks = min(1.1, max(0.75, self.fs / 9))
        for s, f, sz, dy in self.stub:
            c.setFillColor(colors.white)
            c.setFont(f, sz * ks)
            c.drawCentredString(sw / 2, h / 2 + dy * mm * ks, s)
        y = h - 3.2 * mm
        for p, ph in zip(self._p, self._ph):
            p.drawOn(c, sw + 3 * mm, y - ph)
            y -= ph + 0.8 * mm


def _box_promemoria(items: list[dict], oggi: dt.date, fs: float, colori: _Colori):
    if not items:
        return None
    n = 3  # sempre tre colonne: con pochi promemoria i biglietti restano della stessa misura, a sinistra
    gap = 2 * mm
    cw = (W - (n - 1) * gap) / n
    pfs = max(fs - 0.5, 6)
    righe_n = (len(items) + n - 1) // n
    ncol = n * 2 - 1
    dati = [[""] * ncol for _ in range(righe_n * 2 - 1)]
    for i, p in enumerate(items):
        lab, delta = _breve(p["data"], oggi)
        gs, data = lab.split(" ", 1)
        ora = p.get("ora") if p.get("ora") not in ("", "00:00") else ""  # Argo manda 00:00 quando non c'è un orario
        stub = [({0: "OGGI", 1: "DOMANI"}.get(delta, gs.upper()), "DV-B", 7, 6.5 if ora else 4.5),
                (data, "DV-B", 11, -1.0 if ora else -2.5)]
        if ora:
            stub.append((ora, "DV", 7.5, -6.0))
        r, col = divmod(i, n)
        dati[r * 2][col * 2] = _Biglietto(colori.colore(f"p{i}"), stub, p["testo"], p.get("docente", ""), pfs, f"p{i}", colori)
    grid = Table(dati, colWidths=[x for i in range(n) for x in ([cw] if i == n - 1 else [cw, gap])],
                 rowHeights=[None if i % 2 == 0 else 1.6 * mm for i in range(righe_n * 2 - 1)])
    grid.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                              ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    etichetta = Paragraph("PROMEMORIA IN ARRIVO", ParagraphStyle("pl", fontName="DV-B", fontSize=pfs, leading=pfs * 1.3, textColor=GRIGIO, charSpace=0.6))
    return [etichetta, Spacer(1, 1.2 * mm), grid]


def _formatta_media(m) -> str:
    return f"{m:.1f}".replace(".", ",")


def _boxes_blocco(b: dict, righe: list[dict], oggi: dt.date, fs: float, colw: float, colori: _Colori) -> list:
    """Riquadri di un blocco: uno per giorno per i compiti, uno solo per le altre sezioni."""
    sez = b["sezione"]
    minh = 22 * mm * _k(fs)
    if sez == "compiti":
        out = []
        giorni: dict[str, list[dict]] = {}
        for x in righe:
            giorni.setdefault(x["data"], []).append(x)
        for d, xs in giorni.items():
            _, delta = _breve(d, oggi)
            chiave = f"{b['id']}:{d}"
            colore = colori.colore(chiave)
            data = dt.date.fromisoformat(d[:10])
            su = {0: "OGGI", 1: "DOMANI"}.get(delta, ABBR[data.weekday()].upper())
            stub = [(su, "DV-B", 6.5 if delta in (0, 1) else 7, 7.0), (str(data.day), "DV-B", 19, -1.0), (MESI[data.month - 1], "DV-B", 7.5, -5.5)]
            casella = f"<font color='{_hex(colore)}' size='{fs + 3:.1f}'>▢</font>"
            rr = [f"{casella}&nbsp;<font name='DV-B' color='{_hex(colore)}'>{_h(x['materia'])}</font>: {_h(x['testo'])}" for x in xs]
            out.append(_Card(colore, stub, rr, fs, minh, chiave, colori))
        return out
    if not righe:
        return []
    if sez == "voti":
        rr = []
        for x in righe:
            lab, _ = _breve(x["data"], oggi)
            extra = f" · {x['tipo']}" if x.get("tipo") else ""
            desc = f"<br/><font name='DV-I' color='#6b7785'>{_h(x['descrizione'])}</font>" if x.get("descrizione") else ""
            rr.append(f"<font name='DV-B' color='{_hex(_colore_voto(x['valore']))}'>{_h(x['voto'])}</font>&nbsp; "
                      f"<font name='DV-B'>{_h(x['materia'])}</font> <font color='#6b7785'>{lab}{_h(extra)}</font>{desc}")
        media = b.get("media")
        stub = [("VOTI", "DV-B", 7, 7.0), (_formatta_media(media) if media is not None else str(len(righe)), "DV-B", 13, -1.0),
                ("media" if media is not None else "voti", "DV", 6.5, -5.5)]
        if "—" in b["titolo_box"]:  # PDF unito: serve il nome di chi ha preso i voti
            stub.insert(0, (b["titolo_box"].split("—", 1)[1].strip().upper()[:9], "DV-B", 6.3, 10.5))
            return [_Card(NEUTRO, stub, rr, fs, minh * 1.15)]
        return [_Card(NEUTRO, stub, rr, fs, minh)]
    if sez == "note":
        rr = []
        for x in righe:
            lab, _ = _breve(x["data"], oggi)
            doc = f" <font name='DV-I' color='#6b7785'>({_h(x['docente'])})</font>" if x.get("docente") else ""
            rr.append(f"<font name='DV-B'>{lab}</font>{doc}: {_h(x['testo'])}")
        if "—" in b["titolo_box"]:  # PDF unito: serve il nome dell'alunno, quindi il talloncino è alto come gli altri
            stub = [(b["titolo_box"].split("—", 1)[1].strip().upper()[:9], "DV-B", 6.3, 8.0), ("NOTE", "DV-B", 7, 3.5), (str(len(righe)), "DV-B", 16, -4.5)]
            return [_Card(NEUTRO, stub, rr, fs, minh)]
        return [_Card(NEUTRO, [("NOTE", "DV-B", 7, 3.5), (str(len(righe)), "DV-B", 16, -3.5)], rr, fs, minh * 0.75)]
    rr = []  # comunicazioni
    for x in righe:
        lab, _ = _breve(x["data"], oggi)
        cat = f" · {_h(x['categoria'])}" if x.get("categoria") else ""
        testo = x["testo"][:200] + ("…" if len(x["testo"]) > 200 else "")
        rr.append(f"<font name='DV-B'>{lab}</font><font color='#6b7785'>{cat}</font>: {_h(testo)}")
    return [_Card(NEUTRO, [("AVVISI", "DV-B", 6.5, 3.5), (str(len(righe)), "DV-B", 16, -3.5)], rr, fs, minh)]


# ------------------------------------------------------------------------------------------- impaginazione
def _costruisci(ctx: dict, tolti: dict[str, int], cols: int, fs: float) -> tuple[bytes, int]:
    """Due passate: la prima fa vedere dove finiscono i biglietti, la seconda li colora in modo che i vicini siano sempre diversi."""
    global ULTIMI_COLORI
    prima = _Colori()
    _impagina(ctx, tolti, cols, fs, prima)
    ULTIMI_COLORI = _Colori(_assegna_colori(prima.reg))
    ris = _impagina(ctx, tolti, cols, fs, ULTIMI_COLORI)
    return ris


def _impagina(ctx: dict, tolti: dict[str, int], cols: int, fs: float, colori: _Colori) -> tuple[bytes, int]:
    oggi, blocchi = ctx["oggi"], ctx["blocchi"]
    gap = 3 * mm
    colw = (W - (cols - 1) * gap) / cols
    tenuti = {b["id"]: b["righe"][: len(b["righe"]) - tolti.get(b["id"], 0)] for b in blocchi}
    testa = [_Testata(ctx["nome"], ctx["destra"]), Spacer(1, 3 * mm)]
    for b in blocchi:
        if b["sezione"] == "promemoria":
            pm = _box_promemoria(tenuti[b["id"]], oggi, fs, colori)
            if pm:
                testa += pm
    if ctx["ha_compiti"]:
        testa += [Spacer(1, 2.5 * mm), _Divisore("COMPITI DA FARE", max(fs - 0.5, 6))]
    testa.append(Spacer(1, 1.5 * mm))
    hh = sum(f.wrap(W, 10000)[1] + (getattr(f, "getSpaceBefore", lambda: 0)()) for f in testa) + 1 * mm
    bottom = 12 * mm
    top_cols = H - MARG - hh
    nota = f"… altri {sum(tolti.values())} elementi non stampati (limite di pagine raggiunto)" if tolti else ""

    def colonne(y_alto, y_basso, pref):
        return [Frame(MARG + i * (colw + gap), y_basso, colw, y_alto - y_basso, id=f"{pref}{i}", leftPadding=0,
                      rightPadding=0, topPadding=0, bottomPadding=0) for i in range(cols)]

    def pie(c, d):
        c.saveState()
        c.setFont("DV", 6.5)
        c.setFillColor(GRIGIO)
        c.drawString(MARG, 6 * mm, f"{ctx['titolo']} · da Argo DidUP · generato il {ctx['generato']}")
        if nota:
            c.setFillColor(ROSSO)
            c.drawString(MARG, 9 * mm, nota)
            c.setFillColor(GRIGIO)
        if d.page > 1 or ctx.get("multi"):
            c.drawRightString(A4[0] - MARG, 6 * mm, f"pagina {d.page}")
        c.restoreState()

    buf = io.BytesIO()
    doc = BaseDocTemplate(buf, pagesize=A4, title=ctx["titolo"], author="DidUP Famiglia (Argo)")
    fr_testa = Frame(MARG, H - MARG - hh, W, hh, id="t", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="prima", frames=[fr_testa] + colonne(top_cols, bottom, "p"), onPage=pie),
                          PageTemplate(id="altre", frames=colonne(H - MARG, bottom, "a"), onPage=pie)])
    storia = list(testa) + [FrameBreak(), NextPageTemplate("altre")]
    vuoto = True
    for b in blocchi:
        if b["sezione"] == "promemoria":
            vuoto = vuoto and not tenuti[b["id"]]
            continue
        boxes = _boxes_blocco(b, tenuti[b["id"]], oggi, fs, colw, colori)
        if b["sezione"] == "compiti" and not boxes:
            storia.append(Paragraph("Nessun compito in programma", ParagraphStyle(
                "v", fontName="DV-B", fontSize=14, leading=18, textColor=GRIGIO)))
        for x in boxes:
            storia += [KeepTogether([x]), Spacer(1, 4 * mm)]  # un riquadro non si spezza fra due colonne se può stare intero
        vuoto = vuoto and not tenuti[b["id"]]
    if vuoto and not any(b["sezione"] == "compiti" for b in blocchi):
        storia.append(Paragraph("Nessun elemento da mostrare", ParagraphStyle(
            "v", fontName="DV-B", fontSize=14, leading=18, textColor=GRIGIO)))
    doc.build(storia)
    return buf.getvalue(), doc.page


@dataclass
class Esito:
    pdf: bytes
    pagine: int
    non_stampati: int = 0
    avvisi: list[str] = field(default_factory=list)


def _migliore(ctx, tolti, max_pagine) -> tuple[bytes, int] | None:
    """Il corpo più grande per cui tutto sta in `max_pagine` (None se nemmeno al minimo).
    Rimpicciolendo le pagine non aumentano: ricerca binaria sui candidati (meno impaginazioni)."""
    ultimo = _costruisci(ctx, tolti, *CANDIDATI[-1])
    if ultimo[1] > max_pagine:
        return None
    lo, hi, migliore = 0, len(CANDIDATI) - 1, ultimo
    while lo < hi:
        mid = (lo + hi) // 2
        r = _costruisci(ctx, tolti, *CANDIDATI[mid])
        if r[1] <= max_pagine:
            hi, migliore = mid, r
        else:
            lo = mid + 1
    return migliore


def genera(dati: dict[str, dict], alunni: list[str], sezioni: list[str], max_pagine: int, titolo: str,
           ora: dt.datetime | None = None) -> Esito:
    """dati: {slug: {'alunno': {...}, 'compiti': [...], ...}} come prodotto dal coordinator. Un PDF per il gruppo `alunni`."""
    _fonts()
    ora = ora or dt.datetime.now()
    sezioni = [s for s in SEZIONI if s in sezioni]
    scelti = [a for a in alunni if a in dati]
    max_pagine = max(1, int(max_pagine))
    blocchi = []
    nome, _ = etichetta_gruppo(dati, scelti) if scelti else ("", "")
    classi = sorted({dati[a]["alunno"]["classe"] for a in scelti})
    for sez in sezioni:
        if len(scelti) > 1 and sez in INDIVIDUALI:
            for a in scelti:
                blocchi.append({"id": f"{a}:{sez}", "sezione": sez, "righe": _righe(sez, dati[a], ora.date()), "media": dati[a].get("media"),
                                "titolo_box": f"{TITOLI[sez]} — {dati[a]['alunno']['nome']}"})
        elif scelti:
            blocchi.append({"id": f"{scelti[0]}:{sez}", "sezione": sez, "righe": _righe(sez, dati[scelti[0]], ora.date()),
                            "media": dati[scelti[0]].get("media"), "titolo_box": TITOLI[sez]})
    ctx = {"oggi": ora.date(), "blocchi": blocchi, "nome": nome, "titolo": titolo,
           "generato": ora.strftime("%d/%m/%Y %H:%M"), "ha_compiti": "compiti" in sezioni,
           "destra": ["classe " + " / ".join(classi), "aggiornato " + ora.strftime("%d/%m %H:%M")]}
    avvisi: list[str] = []
    ris = _migliore(ctx, {}, max_pagine)
    tolti: dict[str, int] = {}
    if ris is None:
        # nemmeno al corpo minimo ci sta: si tolgono elementi (ordine equo: dalla sezione che ne ha ancora di più, dagli ultimi)
        resto = {b["id"]: len(b["righe"]) for b in blocchi}
        ordine = []
        while any(resto.values()):
            i = max(resto, key=lambda k: (resto[k], -list(resto).index(k)))
            ordine.append(i)
            resto[i] -= 1
        minimo = CANDIDATI[-1]

        def conta(n):
            t: dict[str, int] = {}
            for i in ordine[:n]:
                t[i] = t.get(i, 0) + 1
            return t, _costruisci(ctx, t, *minimo)[1]

        lo, hi = 0, len(ordine)  # le pagine non crescono togliendo elementi: ricerca binaria sul numero di elementi tolti
        while lo < hi:
            mid = (lo + hi) // 2
            if conta(mid)[1] <= max_pagine:
                hi = mid
            else:
                lo = mid + 1
        tolti = conta(lo)[0]
        ris = _migliore(ctx, tolti, max_pagine)
        if ris is None:
            pdf, pagine = _costruisci(ctx, tolti, *minimo)
            ris = (pdf, pagine)
            avvisi.append(f"anche senza elementi servono {pagine} pagine (limite di {max_pagine})")
    pdf, pagine = ris
    return Esito(pdf=pdf, pagine=pagine, non_stampati=sum(tolti.values()), avvisi=avvisi)


def nome_file(modello: str, titolo: str, alunno: str, ora: dt.datetime) -> str:
    """Nome del PDF di UN alunno. Segnaposto: {report}, {alunno}, {data}, {ora}. Se il modello non contiene {alunno}
    lo si aggiunge in coda, così i PDF dei vari alunni non si sovrascrivono mai. Solo caratteri sicuri, sempre .pdf."""
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", titolo).strip("_").lower() or "report"
    if "{alunno}" not in modello:
        modello = re.sub(r"(?i)\.pdf$", "", modello) + "_{alunno}"
    try:
        nome = modello.format(report=base, alunno=alunno, data=ora.strftime("%Y-%m-%d"), ora=ora.strftime("%H%M"))
    except (KeyError, IndexError, ValueError):
        nome = f"{base}_{alunno}_{ora.strftime('%Y-%m-%d')}"
    nome = re.sub(r"[^A-Za-z0-9._-]+", "_", nome).strip("._") or f"{base}_{alunno}"
    return nome if nome.lower().endswith(".pdf") else nome + ".pdf"


def etichetta_gruppo(dati: dict[str, dict], gruppo: list[str]) -> tuple[str, str]:
    """('Luca e Paolo Rossi', 'luca_e_paolo'): nome da stampare e pezzo di nome file per un gruppo di alunni."""
    al = [dati[a]["alunno"] for a in gruppo if a in dati]
    if not al:
        return "", ""
    if len(al) == 1:
        return f"{al[0]['nome']} {al[0]['cognome']}", parsing.slug(al[0]["nome"], al[0]["cognome"])
    nomi = [a["nome"] for a in al]
    elenco = ", ".join(nomi[:-1]) + " e " + nomi[-1]
    cogn = {a["cognome"] for a in al}
    testo = f"{elenco} {next(iter(cogn))}" if len(cogn) == 1 else " e ".join(f"{a['nome']} {a['cognome']}" for a in al)
    return testo, "_e_".join(parsing.slug(n, "") for n in nomi)


def raggruppa(dati: dict[str, dict], alunni: list[str], sezioni: list[str], unisci: bool) -> list[list[str]]:
    """Un gruppo = un PDF. Con `unisci` finiscono insieme gli alunni della stessa classe i cui contenuti di classe
    (compiti, promemoria, comunicazioni, solo quelli scelti) sono identici; senza, uno per alunno."""
    scelti = [a for a in alunni if a in dati]
    if not unisci:
        return [[a] for a in scelti]
    chiavi = {"compiti": "compiti", "promemoria": "promemoria", "comunicazioni": "bacheca"}
    gruppi: dict[str, list[str]] = {}
    for a in scelti:
        firma = repr((dati[a]["alunno"]["classe"],
                      [dati[a].get(k) for s, k in chiavi.items() if s in sezioni]))
        gruppi.setdefault(firma, []).append(a)
    return list(gruppi.values())
