"""Costanti dell'integrazione DidUP."""
from datetime import timedelta

DOMAIN = "didup"

CONF_CODICE = "codice_scuola"
CONF_UTENTE = "utente"
CONF_PASSWORD = "password"
CONF_ALUNNI_NOTI = "alunni_noti"  # {slug: "Nome Cognome"} scoperti al login, per il menu delle opzioni

OPT_ALUNNI = "alunni"
OPT_FUNZIONI = "funzioni"
OPT_INTERVALLO = "intervallo_minuti"
OPT_INCLUDI_OGGI = "includi_compiti_di_oggi"

F_COMPITI = "compiti"
F_PROMEMORIA = "promemoria"
F_VOTI = "voti"
F_MEDIE = "medie"
F_NOTE = "note"
F_BACHECA = "bacheca"
F_CALENDARIO = "calendario"
F_EVENTI = "eventi"
FUNZIONI = [F_COMPITI, F_PROMEMORIA, F_VOTI, F_MEDIE, F_NOTE, F_BACHECA, F_CALENDARIO, F_EVENTI]
FUNZIONI_DEFAULT = [F_COMPITI, F_PROMEMORIA, F_VOTI, F_CALENDARIO, F_EVENTI]

INTERVALLO_DEFAULT = 30
INTERVALLO_MIN = 15
INTERVALLO_MAX = 720
SCAN_INTERVAL_DEFAULT = timedelta(minutes=INTERVALLO_DEFAULT)

SIGNAL_EVENTO = f"{DOMAIN}_evento"
EVENTI_TIPI = ["nuovo_voto", "nuovo_compito", "nuovo_promemoria", "nuova_nota", "nuova_comunicazione"]
STORE_VERSION = 1

# Report PDF (sub-entry "report")
SUBENTRY_REPORT = "report"
R_ALUNNI = "alunni"
R_SEZIONI = "sezioni"
R_UNISCI = "unisci_alunni"
R_MAX_PAGINE = "max_pagine"
R_CARTELLA = "cartella"
R_NOME_FILE = "nome_file"
R_AUTOMATICO = "automatico"
R_ORA = "ora"
R_GIORNI = "giorni"
R_ORARI = "orari"  # {giorno: "HH:MM:SS"}: orari diversi per giorno, in aggiunta a quello predefinito (R_ORA)
SEZIONI_REPORT = ["compiti", "promemoria", "voti", "note", "comunicazioni"]
GIORNI_SETTIMANA = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]  # indice = weekday()
R_MAX_PAGINE_DEFAULT = 1
R_NOME_FILE_DEFAULT = "{report}_{alunno}_{data}"
SIGNAL_REPORT = f"{DOMAIN}_report"
EVENTO_REPORT = f"{DOMAIN}_report_generato"
