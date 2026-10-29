# Changelog

## 0.6.0
- Nuova grafica «biglietto» per il PDF dei report: testata sfumata blu/verde acqua con taglio arancio (nome a sinistra, classe e aggiornamento a destra), promemoria come biglietti con talloncino colorato (giorno, data, ora), divisore «Compiti da fare», un biglietto per giorno con talloncino (giorno, numero, mese) e un filo del colore del giorno sul bordo superiore, caselle ▢ arrotondate. Voti, note e comunicazioni hanno lo stesso stile.
- Il contenuto del report non cambia. Nella testata non compare più il numero di compiti da fare. Nei giorni «oggi» e «domani» il talloncino dice OGGI o DOMANI al posto del giorno della settimana.
- I promemoria senza orario (Argo manda «00:00») non mostrano più l'ora.
- Il limite di pagine funziona come prima (il carattere si rimpicciolisce prima di togliere elementi); i riquadri troppo alti si spezzano fra le colonne.

## 0.5.2
- Le novità trovate nella prima lettura dopo un avvio o una ricarica non si perdono più: vengono emesse appena le entità evento sono pronte (prima si perdevano e risultavano comunque «viste»).
- Dopo 3 letture da Argo fallite di fila compare un avviso in «Riparazioni» con l'errore; sparisce da solo alla prima lettura riuscita.
- Login più tollerante con le pagine HTML di Argo (link, meta-refresh, JavaScript) e, se non trova il codice, l'errore dice a che passo si è fermato.
- I PDF già prodotti restano apribili anche se la cartella del report viene spostata (conta il nome del file, cercato nella cartella attuale).

## 0.5.1
- Correzione del login: dal 29/10/2026 Argo risponde con una pagina HTML («Accesso completato… Continua») invece di un redirect nel passo di consenso; l'integrazione ora segue il link e torna a leggere i dati (prima restava in «nuovo tentativo» con «codice di autorizzazione non trovato»).

## 0.5.0
- Nuova vista `pdf` della card: un pulsante per ogni alunno che apre nel browser o nell'app l'ultimo PDF prodotto, con login (link firmato di breve durata) e senza rendere pubblica la cartella.
- Nuovo indirizzo autenticato `/api/didup/pdf/<report>/<alunno>`: serve solo i PDF prodotti dall'integrazione, dentro la cartella del report.
- I PDF già prodotti restano apribili dopo un riavvio di Home Assistant e dopo una generazione fallita.
- L'evento `didup_report_generato` ha in più il campo `slug`.

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
