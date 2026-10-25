# Changelog

## 0.4.3
- Privacy: la cartella proposta per i PDF non è più dentro `/config/www` (pubblica, senza login) ma `/config/didup_report`, da autorizzare con `allowlist_external_dirs`; tolto ogni suggerimento di usare `/config/www` da README e testi dell'interfaccia.

## 0.4.2
- Nuovo sensore «Ultimo aggiornamento» (orario dell'ultima lettura riuscita da Argo, sia periodica sia manuale): lo stato del pulsante «Aggiorna da Argo» mostra solo l'ultima pressione.

## 0.4.1
- Controlli automatici HACS senza eccezioni (richiesto per l'inserimento nel negozio ufficiale); il marchio è incluso in `custom_components/didup/brand`.

## 0.4.0 — prima versione pubblica
- Sensori per alunno (compiti, promemoria/verifiche, ultimo voto, media, note, comunicazioni), calendario, entità evento per le automazioni, pulsante «Aggiorna da Argo».
- Card Lovelace `custom:didup-card` (riepilogo, compiti, promemoria, voti, note, comunicazioni, programma PDF) con editor visivo.
- Report PDF configurabili dalla UI: contenuto, alunni, limite di pagine, cartella, nome file, un PDF per alunno (o unito per alunni con gli stessi compiti),
  generazione automatica con un orario diverso per ogni giorno della settimana; evento `didup_report_generato` (con `origine`).
- Config flow con riautenticazione; scelta di alunni e funzioni da attivare.
