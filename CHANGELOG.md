# Changelog

## 0.4.0 — prima versione pubblica
- Sensori per alunno (compiti, promemoria/verifiche, ultimo voto, media, note, comunicazioni), calendario, entità evento per le automazioni, pulsante «Aggiorna da Argo».
- Card Lovelace `custom:didup-card` (riepilogo, compiti, promemoria, voti, note, comunicazioni, programma PDF) con editor visivo.
- Report PDF configurabili dalla UI: contenuto, alunni, limite di pagine, cartella, nome file, un PDF per alunno (o unito per alunni con gli stessi compiti),
  generazione automatica con un orario diverso per ogni giorno della settimana; evento `didup_report_generato` (con `origine`).
- Config flow con riautenticazione; scelta di alunni e funzioni da attivare.
