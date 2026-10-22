"""Generazione del PDF dei report (reportlab, nessun Home Assistant). Aspetto "classico" di DidUP.

Fascia blu col nome degli alunni, riquadri colorati per le verifiche in arrivo, un riquadro per giorno (rosso: oggi/domani,
arancio: entro 7 giorni, blu: oltre) su 2-3 colonne con le caselle ☐, e riquadri analoghi per voti, note e comunicazioni.

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
from reportlab.platypus import (BaseDocTemplate, Frame, FrameBreak, KeepTogether, NextPageTemplate, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

from . import parsing

SEZIONI = ["compiti", "promemoria", "voti", "note", "comunicazioni"]
INDIVIDUALI = ("voti", "note")  # personali: in un PDF unito restano separate per alunno (il resto è di classe)
TITOLI = {"compiti": "Compiti", "promemoria": "Promemoria e verifiche", "voti": "Voti",
          "note": "Note disciplinari", "comunicazioni": "Comunicazioni della scuola"}
MAX_VOTI = 15
MAX_COMUNICAZIONI = 10

FONTS = Path(__file__).parent / "fonts"  # DejaVu (licenza in fonts/LICENSE.txt): copre accenti, ☐ e simboli
INK = colors.HexColor("#1f2933")
GRIGIO = colors.HexColor("#6b7785")
BLU = colors.HexColor("#2f5d8a")
ROSSO, ARANCIO = colors.HexColor("#c0392b"), colors.HexColor("#d9822b")
VERDE = colors.HexColor("#2e7d32")
BG = {"rosso": colors.HexColor("#fdecea"), "arancio": colors.HexColor("#fff3e3"), "blu": colors.HexColor("#eaf1f8")}
COL = {"rosso": ROSSO, "arancio": ARANCIO, "blu": BLU}
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


def tono(giorni: int) -> str:
    return "rosso" if giorni <= 1 else "arancio" if giorni <= 7 else "blu"


def _breve(iso: str, oggi: dt.date) -> tuple[str, int]:
    d = dt.date.fromisoformat(iso[:10])
    return f"{ABBR[d.weekday()]} {d.day}/{d.month}", (d - oggi).days


def _colore_voto(v: float):
    return VERDE if v >= 6 else ARANCIO if v >= 5 else ROSSO


def _hex(c) -> str:
    return "#" + c.hexval()[2:]


# ----------------------------------------------------------------------------------------------- elementi
def _righe(sezione: str, dati: dict) -> list[dict]:
    """Elementi della sezione, già nell'ordine di stampa (i dizionari del coordinator, eventualmente accorciati)."""
    if sezione == "voti":
        return dati.get("voti", [])[:MAX_VOTI]
    if sezione == "comunicazioni":
        return dati.get("bacheca", [])[:MAX_COMUNICAZIONI]
    return list(dati.get(sezione, []))


def _box(testa_html: str, conteggio: int, righe: list, t: str, fs: float, colw: float) -> Table:
    """Riquadro con testata colorata e una riga di testo per elemento (righe = HTML già pronto)."""
    st_h = ParagraphStyle("h", fontName="DV-B", fontSize=fs + 1, leading=(fs + 1) * 1.25, textColor=COL[t])
    st_c = ParagraphStyle("hc", fontName="DV", fontSize=fs - 0.5, leading=(fs + 1) * 1.25, textColor=GRIGIO, alignment=2)
    corpo = ParagraphStyle("c", fontName="DV", fontSize=fs, leading=fs * 1.22, textColor=INK,
                           leftIndent=fs * 1.5, firstLineIndent=-fs * 1.5)
    dati = [[Paragraph(testa_html, st_h), Paragraph(str(conteggio), st_c)]]
    dati += [[Paragraph(r, corpo), ""] for r in righe]
    tab = Table(dati, colWidths=[colw - 10 * mm, 10 * mm], repeatRows=1)
    stile = [("SPAN", (0, i), (1, i)) for i in range(1, len(dati))]
    stile += [("BACKGROUND", (0, 0), (-1, 0), BG[t]), ("LINEBEFORE", (0, 0), (0, 0), 2.2, COL[t]),
              ("LEFTPADDING", (0, 0), (-1, -1), 1.8 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
              ("TOPPADDING", (0, 0), (-1, 0), 1 * mm), ("BOTTOMPADDING", (0, 0), (-1, 0), 1 * mm),
              ("TOPPADDING", (0, 1), (-1, -1), 0.9 * mm), ("BOTTOMPADDING", (0, 1), (-1, -1), 0.9 * mm),
              ("LINEBELOW", (0, 1), (-1, -2), 0.3, colors.HexColor("#d5dbe1")),
              ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd6dd")), ("VALIGN", (0, 0), (-1, -1), "TOP")]
    tab.setStyle(TableStyle(stile))
    return tab


def _box_promemoria(items: list[dict], oggi: dt.date, fs: float):
    if not items:
        return None
    n = 3 if len(items) > 2 else len(items)
    gap = 2 * mm
    cw = (W - (n - 1) * gap) / n
    pfs = max(fs - 0.5, 6)
    righe_n = (len(items) + n - 1) // n
    ncol = n * 2 - 1
    dati = [[""] * ncol for _ in range(righe_n * 2 - 1)]
    stili = []
    for i, p in enumerate(items):
        lab, delta = _breve(p["data"], oggi)
        t = tono(delta)
        quando = lab + (f" · {p['ora']}" if p.get("ora") else "") + ("  (OGGI)" if delta == 0 else "  (domani)" if delta == 1 else "")
        cella = [Paragraph(f"<b>{_h(quando)}</b>", ParagraphStyle("pd", fontName="DV-B", fontSize=pfs, leading=pfs * 1.2, textColor=COL[t])),
                 Paragraph(_h(p["testo"]), ParagraphStyle("pt", fontName="DV", fontSize=pfs, leading=pfs * 1.2, textColor=INK))]
        if p.get("docente"):
            cella.append(Paragraph(_h(p["docente"]), ParagraphStyle("pp", fontName="DV-I", fontSize=pfs - 1, leading=pfs * 1.1, textColor=GRIGIO)))
        r, c = divmod(i, n)
        col = c * 2
        dati[r * 2][col] = cella
        stili += [("BACKGROUND", (col, r * 2), (col, r * 2), BG[t]), ("LINEBEFORE", (col, r * 2), (col, r * 2), 2.2, COL[t])]
    grid = Table(dati, colWidths=[x for i in range(n) for x in ([cw] if i == n - 1 else [cw, gap])],
                 rowHeights=[None if i % 2 == 0 else 1.6 * mm for i in range(righe_n * 2 - 1)])
    grid.setStyle(TableStyle(stili + [("LEFTPADDING", (0, 0), (-1, -1), 2 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
                                      ("TOPPADDING", (0, 0), (-1, -1), 1.2 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4 * mm),
                                      ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    etichetta = Paragraph("PROMEMORIA IN ARRIVO", ParagraphStyle("pl", fontName="DV-B", fontSize=pfs, leading=pfs * 1.3, textColor=GRIGIO))
    return [etichetta, Spacer(1, 0.8 * mm), grid]


def _boxes_blocco(b: dict, righe: list[dict], oggi: dt.date, fs: float, colw: float) -> list:
    """Riquadri di un blocco: uno per giorno per i compiti, uno solo per le altre sezioni."""
    sez = b["sezione"]
    if sez == "compiti":
        out = []
        giorni: dict[str, list[dict]] = {}
        for x in righe:
            giorni.setdefault(x["data"], []).append(x)
        for d, xs in giorni.items():
            lab, delta = _breve(d, oggi)
            t = tono(delta)
            quando = {0: "OGGI", 1: "DOMANI"}.get(delta, "")
            rr = [f"☐&nbsp;<font name='DV-B' color='{_hex(COL[t])}'>{_h(x['materia'])}</font>: {_h(x['testo'])}" for x in xs]
            out.append(_box(f"{quando + ' · ' if quando else ''}{lab}", len(xs), rr, t, fs, colw))
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
        return [_box(b["titolo_box"], len(righe), rr, "blu", fs, colw)]
    if sez == "note":
        rr = []
        for x in righe:
            lab, _ = _breve(x["data"], oggi)
            doc = f" <font name='DV-I' color='#6b7785'>({_h(x['docente'])})</font>" if x.get("docente") else ""
            rr.append(f"<font name='DV-B'>{lab}</font>{doc}: {_h(x['testo'])}")
        return [_box(b["titolo_box"], len(righe), rr, "rosso", fs, colw)]
    rr = []  # comunicazioni
    for x in righe:
        lab, _ = _breve(x["data"], oggi)
        cat = f" · {_h(x['categoria'])}" if x.get("categoria") else ""
        testo = x["testo"][:200] + ("…" if len(x["testo"]) > 200 else "")
        rr.append(f"<font name='DV-B'>{lab}</font><font color='#6b7785'>{cat}</font>: {_h(testo)}")
    return [_box(b["titolo_box"], len(righe), rr, "blu", fs, colw)]


# ------------------------------------------------------------------------------------------- impaginazione
def _intestazione(nome: str, destra: str) -> Table:
    st_n = ParagraphStyle("n", fontName="DV-B", fontSize=17, leading=20, textColor=colors.white)
    st_r = ParagraphStyle("r", fontName="DV", fontSize=8.5, leading=11, textColor=colors.HexColor("#dbe6f1"), alignment=2)
    t = Table([[Paragraph(_h(nome), st_n), Paragraph(destra, st_r)]], colWidths=[W * 0.55, W * 0.45])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLU), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("LEFTPADDING", (0, 0), (0, 0), 5 * mm), ("RIGHTPADDING", (-1, 0), (-1, 0), 5 * mm),
                           ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm)]))
    return t


def _costruisci(ctx: dict, tolti: dict[str, int], cols: int, fs: float) -> tuple[bytes, int]:
    oggi, blocchi = ctx["oggi"], ctx["blocchi"]
    gap = 3 * mm
    colw = (W - (cols - 1) * gap) / cols
    tenuti = {b["id"]: b["righe"][: len(b["righe"]) - tolti.get(b["id"], 0)] for b in blocchi}
    n_comp = sum(len(tenuti[b["id"]]) for b in blocchi if b["sezione"] == "compiti")
    destra = ctx["destra"].replace("{n}", f"{n_comp} compit{'o' if n_comp == 1 else 'i'} da fare" if ctx["ha_compiti"] else "")
    testa = [_intestazione(ctx["nome"], destra), Spacer(1, 2 * mm)]
    for b in blocchi:
        if b["sezione"] == "promemoria":
            pm = _box_promemoria(tenuti[b["id"]], oggi, fs)
            if pm:
                testa += pm
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
        boxes = _boxes_blocco(b, tenuti[b["id"]], oggi, fs, colw)
        if b["sezione"] == "compiti" and not boxes:
            storia.append(Paragraph("Nessun compito in programma", ParagraphStyle(
                "v", fontName="DV-B", fontSize=14, leading=18, textColor=GRIGIO)))
        for x in boxes:
            storia += [KeepTogether([x]), Spacer(1, 2 * mm)]  # un riquadro non si spezza fra due colonne se può stare intero
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
                blocchi.append({"id": f"{a}:{sez}", "sezione": sez, "righe": _righe(sez, dati[a]),
                                "titolo_box": f"{TITOLI[sez]} — {dati[a]['alunno']['nome']}"})
        elif scelti:
            blocchi.append({"id": f"{scelti[0]}:{sez}", "sezione": sez, "righe": _righe(sez, dati[scelti[0]]),
                            "titolo_box": TITOLI[sez]})
    ctx = {"oggi": ora.date(), "blocchi": blocchi, "nome": nome, "titolo": titolo,
           "generato": ora.strftime("%d/%m/%Y %H:%M"), "ha_compiti": "compiti" in sezioni,
           "destra": "classe " + " / ".join(classi) + "<br/>{n}<br/>aggiornato " + ora.strftime("%d/%m %H:%M")}
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
