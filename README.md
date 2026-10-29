<p align="center"><img src="docs/logo.png" width="128" alt="DidUP per Home Assistant"></p>

# DidUP Famiglia (Argo) per Home Assistant

[![HACS: custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz) ![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)

> **English summary** — Unofficial, read-only Home Assistant integration for **Argo DidUP Famiglia** (Italian school register): homework, tests/reminders, grades, disciplinary notes
> and school notices for every student on the parent account, with a Lovelace card (`custom:didup-card`), a calendar, event entities for automations and configurable
> **PDF reports** (one per student, optional schedule with a different time per weekday). The UI and docs are in Italian; the integration also ships English translations.
> Install it from HACS as a *custom repository* (`https://github.com/power80it/ha-didup`, category *Integration*). Not affiliated with Argo Software; it uses the same API as the mobile app, which may change without notice.

Integrazione **non ufficiale** per leggere da Argo **DidUP Famiglia** compiti, promemoria/verifiche, voti, note
disciplinari e comunicazioni della scuola, per tutti gli alunni dell'account del genitore. Sola lettura.

> Non affiliata né approvata da Argo Software. Usa le stesse API dell'app mobile: possono cambiare senza preavviso.

## Installazione (HACS)
1. HACS → ⋮ → *Repository personalizzati* → `https://github.com/power80it/ha-didup`, categoria *Integrazione*.
2. Scarica **DidUP Famiglia (Argo)** e riavvia Home Assistant.
3. *Impostazioni → Dispositivi e servizi → Aggiungi integrazione → DidUP*.
4. Inserisci **codice scuola**, **utente** e **password** del genitore (quelle dell'app DidUP Famiglia).
5. Scegli alunni e funzioni da attivare. Tutto si può cambiare dopo da *Configura*.

## Cosa si può attivare
Ogni funzione crea entità solo se la scegli. Per ogni alunno c'è un dispositivo.

| Funzione | Entità |
|---|---|
| Compiti | `sensor.<alunno>_compiti` (numero; elenco negli attributi `elementi`) |
| Promemoria e verifiche | `sensor.<alunno>_promemoria` |
| Voti | `sensor.<alunno>_ultimo_voto` (attributi: materia, data, tipo, docente, ultimi 10) |
| Media generale | `sensor.<alunno>_media_generale` |
| Note disciplinari | `sensor.<alunno>_note_disciplinari` |
| Comunicazioni | `sensor.<alunno>_comunicazioni` |
| Calendario | `calendar.<alunno>_calendario` (compiti a giornata intera, verifiche con orario) |
| Aggiornamento forzato | `button.<account>_aggiorna_da_argo`: rilegge subito tutto da Argo (max 1 volta ogni 20 s; l'attributo `ultimo_aggiornamento` dice quando) |
| Eventi | `event.<alunno>_novita`: scatta a ogni nuovo voto, compito, promemoria, nota o comunicazione |

Altre opzioni: intervallo di controllo (default 30 min, minimo 15) e se includere i compiti con consegna **oggi**
(di default no: si parte da domani).

## Card per le dashboard
L'integrazione include la card **`custom:didup-card`** (si carica da sola, niente da installare). Nell'editor delle
dashboard: *Aggiungi card → DidUP*. Dall'editor visivo scegli:

- **Alunno** (se lo lasci vuoto la card li mostra tutti);
- **Vista**: riepilogo, compiti, promemoria e verifiche, voti, note, comunicazioni;
- **Programma**: pannello per attivare i giorni e impostare l'orario di ogni giorno di un report (scegli il dispositivo «Report …»);
- **PDF**: un pulsante per ogni alunno che apre l'ultimo PDF prodotto (scegli il dispositivo «Report …»), vedi «Aprire il PDF dal browser o dall'app»;
- titolo, numero di elementi, raggruppamento dei compiti (per giorno o per materia), docente sì/no, vista compatta.

Stile neutro: usa solo i colori del tema di Home Assistant. Si possono mettere più card (una per alunno e vista).

## Report PDF
*Configura → Aggiungi report PDF* (sezione **Report PDF** dell'integrazione). Per ogni report scegli:

| Opzione | Significato |
|---|---|
| Nome | titolo del PDF |
| Alunni | **un PDF per ogni alunno** scelto, con nome, cognome e classe in testa |
| Cosa stampare | compiti, promemoria/verifiche, voti, note, comunicazioni |
| Un solo PDF per gli alunni con gli stessi compiti | opzionale (default no): alunni della **stessa classe** con compiti, promemoria e comunicazioni identici finiscono in un unico PDF con i nomi di tutti («Luca e Paolo Rossi»). Voti e note sono personali e restano separati per alunno nello stesso PDF |
| Numero massimo di pagine | **limite rigido per ogni PDF**, di default 1: prima si rimpicciolisce il carattere, poi (solo se serve) si tolgono elementi in modo equo fra le sezioni e il PDF scrive quanti non sono stati stampati |
| Cartella | dove salvarlo (deve essere consentita da Home Assistant; default `/config/didup_report`, vedi «Dove salvare i PDF»). **Non usare `/config/www`**: è pubblica |
| Nome del file | `{report}`, `{alunno}`, `{data}`, `{ora}` (default `{report}_{alunno}_{data}`); se manca `{alunno}` viene aggiunto in coda; senza `{data}` il file viene sovrascritto |
| Generazione automatica | ora e giorni della settimana |

Ogni report ha un dispositivo «Report <nome>» con il pulsante **Genera PDF**, un interruttore generale **Generazione automatica** e, **per ogni giorno della settimana, un interruttore e un orario** (entità `switch` e `time`): così puoi avere orari diversi, per esempio lun/ven 13:30, mar/gio 16:15, mer 14:05. I giorni senza un orario proprio usano quello predefinito del modulo. Si cambiano anche dalla dashboard, con la vista `programma` della card, e valgono subito, senza ricaricare l'integrazione. Ogni report ha un pulsante **Genera PDF** (stessa generazione dell'orario automatico) e a ogni PDF prodotto parte l'evento
`didup_report_generato`, **uno per ogni PDF** (`report`, `origine`, `alunno`, `file`, `pagine`, `non_stampati`; `origine` è `automatico` se l'ha prodotto l'orario e `manuale` se l'hai premuto tu: un'automazione può così reagire solo alla produzione programmata): con un'automazione puoi mandarlo alla stampante o su
un'app di messaggi. In caso di errore compare una notifica in Home Assistant. Il PDF ha lo stile «biglietto»: testata sfumata col nome degli alunni, la classe e l'ora dell'aggiornamento; i promemoria in arrivo come biglietti con talloncino (giorno, data, ora); sotto «Compiti da fare», un biglietto per giorno con le caselle ▢ su 2-3 colonne, e biglietti analoghi per voti, note e comunicazioni. I colori non indicano l'urgenza: ogni biglietto di promemoria e di giorno ha un colore diverso (azzurro, lilla, pesca, menta, ocra, al massimo 5 per pagina) scelto in modo che due biglietti vicini non abbiano mai lo stesso; voti, note e comunicazioni sono sempre grigio ardesia. Per rispettare il limite di pagine il carattere si rimpicciolisce (da 11 a 6 pt); solo se nemmeno così ci sta vengono tolti elementi, e il piè di pagina dice quanti. Font DejaVu inclusi (licenza in `fonts/LICENSE.txt`).

### Dove salvare i PDF (privacy)
I PDF contengono dati dei ragazzi (compiti, voti, note): il modulo li salva di default in una cartella **privata** accanto alla
configurazione, `/config/didup_report`. Home Assistant scrive fuori da certe cartelle solo se le autorizzi, quindi la prima volta
servono tre passaggi:

1. crea la cartella `didup_report` nella cartella di configurazione di Home Assistant (deve esistere già);
2. aggiungila a `configuration.yaml`:
   ```yaml
   homeassistant:
     allowlist_external_dirs:
       - /config/didup_report
   ```
3. *Strumenti per sviluppatori → Riavvia → Ricarica la configurazione di base* (non serve riavviare Home Assistant).

Se l'integrazione risponde «Cartella non consentita», la cartella non esiste o non è in `allowlist_external_dirs`.

> ⚠️ **Non usare `/config/www`** (né altre cartelle servite da Home Assistant): tutto ciò che c'è dentro è raggiungibile da
> `http(s)://<tuo-home-assistant>/local/…` **senza login**, e un nome di cartella difficile da indovinare non è una protezione.

### Aprire il PDF dal browser o dall'app
La card ha la vista **`pdf`**: scegli un dispositivo «Report …» e compare **un pulsante per ogni alunno** (con pagine e orario
di produzione) che apre l'ultimo PDF prodotto nel browser o nell'app. Il PDF resta nella cartella privata: la card chiede a
Home Assistant un link firmato che vale pochi minuti (`auth/sign_path`), quindi serve aver fatto il login e il file non
diventa mai pubblico. L'indirizzo `/api/didup/pdf/<report>/<alunno>` serve solo i PDF prodotti dall'integrazione, mai un
percorso scelto da chi chiede, e richiede l'autenticazione.

```yaml
type: custom:didup-card
vista: pdf
device_id: <dispositivo «Report …»>
```

## Esempio: avviso a ogni nuovo voto
```yaml
automation:
  - alias: Nuovo voto
    triggers:
      - trigger: state
        entity_id: event.mario_rossi_novita
        attribute: event_type
        to: nuovo_voto
    actions:
      - action: notify.notify
        data:
          message: >
            Nuovo voto {{ trigger.to_state.attributes.voto }} in
            {{ trigger.to_state.attributes.materia }}
```
Il primo avvio non genera eventi per quello che c'è già (nessun arretrato).

## Esempio: card dei compiti
```yaml
type: markdown
content: >
  {% for c in state_attr('sensor.mario_rossi_compiti', 'elementi') %}
  - **{{ c.materia }}** ({{ c.data }}): {{ c.testo }}
  {% endfor %}
```

## Cose da sapere
- **Password errata:** Argo può bloccare l'account dopo troppi tentativi, quindi con credenziali rifiutate
  l'integrazione smette subito di riprovare e chiede di reinserire la password (notifica di *riautenticazione*).
- Un controllo = un login nuovo; non c'è una sessione lunga da mantenere.
- Le password sono salvate da Home Assistant nella configurazione dell'integrazione, come per le altre integrazioni.
- **Stampa fisica, WhatsApp, Telegram e simili non sono inclusi:** costruiscili con le automazioni sugli eventi (compreso `didup_report_generato`).

## Sviluppo
`pip install pytest reportlab && pytest tests/` esegue i test di parsing e del PDF (non serve Home Assistant).

## Licenza e avvertenze
Rilasciata con licenza **MIT** (vedi `LICENSE`); i font DejaVu inclusi hanno la loro licenza in `custom_components/didup/fonts/LICENSE.txt`.
Progetto **non ufficiale**: non è affiliato, approvato o sponsorizzato da Argo Software. Si collega ad Argo con lo stesso accesso dell'app mobile,
quindi Argo può cambiare le API senza preavviso e potrebbe non gradire accessi automatici: usala a tuo rischio, con le tue credenziali e solo per i tuoi figli.
Il logo è originale (non usa marchi di Argo). Segnalazioni e proposte: [issue](https://github.com/power80it/ha-didup/issues).
