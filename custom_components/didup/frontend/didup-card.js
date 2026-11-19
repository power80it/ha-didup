/* DidUP Famiglia (Argo) — card per Lovelace. Nessuna dipendenza: web component nativo + ha-form dell'editor.
 * Trova da sola le entità dell'alunno scelto (dispositivo) tramite la translation_key, quindi funziona
 * anche se l'utente rinomina gli entity_id. Stile neutro: usa solo le variabili del tema di Home Assistant. */
const DIDUP_CARD_VERSION = "0.7.0";

const T = {
  it: {
    oggi: "Oggi", domani: "Domani", fra_n: "fra {n} giorni", nessun_compito: "Nessun compito in programma",
    nessun_promemoria: "Nessun promemoria", nessun_voto: "Nessun voto", q1: "Primo quadrimestre", q2: "Secondo quadrimestre", media_gen: "Media generale", n_voti: "{n} voti", ed_medie: "Medie per quadrimestre", nessuna_nota: "Nessuna nota",
    nessuna_comunicazione: "Nessuna comunicazione", non_attiva: "Funzione non attivata nelle opzioni dell'integrazione.",
    nessun_alunno: "Nessun alunno trovato: configura l'integrazione DidUP.", media: "Media",
    compiti: "Compiti", promemoria: "Promemoria e verifiche", voti: "Voti", note: "Note disciplinari",
    comunicazioni: "Comunicazioni", riepilogo: "Riepilogo", programma: "Programma PDF", pdf: "PDF", apri_pdf: "Apri PDF", nessun_pdf: "Nessun PDF ancora: premi «Genera PDF».", pdf_errore: "Impossibile aprire il PDF", pronto: "PDF pronto. Se il download non parte, tocca qui:", pagine_n: "{n} pag.", auto: "Generazione automatica", non_report: "Scegli un dispositivo «Report …» (non un alunno).", ultimo_voto: "Ultimo voto", prossimo: "Prossimo promemoria",
    nessuno: "Nessuno", compiti_di: "Compiti", tipo: "Tipo", docente: "Docente",
    ed_device: "Alunno (vuoto = tutti)", ed_vista: "Vista", ed_titolo: "Titolo (opzionale)",
    ed_max: "Elementi da mostrare", ed_docente: "Mostra il docente", ed_compatta: "Vista compatta",
    ed_raggruppa: "Raggruppa i compiti per", giorno: "Giorno", materia: "Materia",
    descr: "Card DidUP: compiti, verifiche, voti e comunicazioni degli alunni.",
  },
  en: {
    oggi: "Today", domani: "Tomorrow", fra_n: "in {n} days", nessun_compito: "No homework scheduled",
    nessun_promemoria: "No reminders", nessun_voto: "No grades", q1: "First term", q2: "Second term", media_gen: "Overall average", n_voti: "{n} grades", ed_medie: "Averages per term", nessuna_nota: "No notes",
    nessuna_comunicazione: "No notices", non_attiva: "Feature not enabled in the integration options.",
    nessun_alunno: "No student found: set up the DidUP integration.", media: "Average",
    compiti: "Homework", promemoria: "Reminders and tests", voti: "Grades", note: "Disciplinary notes",
    comunicazioni: "Notices", riepilogo: "Summary", programma: "PDF schedule", pdf: "PDF", apri_pdf: "Open PDF", nessun_pdf: "No PDF yet: press \"Generate PDF\".", pdf_errore: "Cannot open the PDF", pronto: "PDF ready. If the download does not start, tap here:", pagine_n: "{n} p.", auto: "Automatic generation", non_report: "Choose a \"Report …\" device (not a student).", ultimo_voto: "Latest grade", prossimo: "Next reminder",
    nessuno: "None", compiti_di: "Homework", tipo: "Type", docente: "Teacher",
    ed_device: "Student (empty = all)", ed_vista: "View", ed_titolo: "Title (optional)",
    ed_max: "Items to show", ed_docente: "Show the teacher", ed_compatta: "Compact view",
    ed_raggruppa: "Group homework by", giorno: "Day", materia: "Subject",
    descr: "DidUP card: students' homework, tests, grades and notices.",
  },
};
// app di Home Assistant (Android: «Home Assistant/…» nello user agent e window.externalApp; iOS: ponte externalBus)
const NELL_APP = () => /Home ?Assistant\//i.test(navigator.userAgent) || !!(window.externalApp || window.webkit?.messageHandlers?.externalBus);
const VISTE = ["riepilogo", "compiti", "promemoria", "voti", "note", "comunicazioni", "programma", "pdf"];
const GIORNI_KEY = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const STUDENTE = ["compiti", "promemoria", "ultimo_voto", "media_generale", "note_disciplinari", "comunicazioni", "novita", "calendario"];
const tr = (hass, k) => ((T[(hass?.language || "en").slice(0, 2)] || T.en)[k]) ?? T.en[k] ?? k;
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

function dayLabel(hass, iso) {
  const d = new Date(iso + "T00:00:00");
  const t = new Date(); t.setHours(0, 0, 0, 0);
  const diff = Math.round((d - t) / 864e5);
  const full = cap(new Intl.DateTimeFormat(hass.language || "en", { weekday: "long", day: "numeric", month: "long" }).format(d));
  if (diff === 0) return [tr(hass, "oggi"), full];
  if (diff === 1) return [tr(hass, "domani"), full];
  return [full, diff > 1 ? tr(hass, "fra_n").replace("{n}", diff) : ""];
}
// urgenza: oggi/domani = rosso, entro 7 giorni = arancio, oltre = colore primario del tema
function tono(iso) {
  const d = new Date(iso + "T00:00:00"), t = new Date(); t.setHours(0, 0, 0, 0);
  const diff = Math.round((d - t) / 864e5);
  return diff <= 1 ? "bad" : diff <= 7 ? "warn" : "info";
}
const shortDate = (hass, iso) => iso ? new Intl.DateTimeFormat(hass.language || "en", { day: "numeric", month: "short" }).format(new Date(iso + "T00:00:00")) : "";

function didupDevices(hass) {
  const ids = new Set();
  for (const reg of Object.values(hass.entities || {})) if (reg.platform === "didup" && reg.device_id) ids.add(reg.device_id);
  return [...ids];
}
function entitiesOfDevice(hass, deviceId) {
  const out = {};
  for (const [eid, reg] of Object.entries(hass.entities || {})) {
    if (reg.platform !== "didup" || reg.device_id !== deviceId) continue;
    const key = reg.translation_key || hass.states[eid]?.attributes?.tipo;
    if (key) out[key] = eid;
  }
  return out;
}
const deviceName = (hass, id) => hass.devices?.[id]?.name_by_user || hass.devices?.[id]?.name || id;
const votoClasse = (v) => (v >= 6 ? "ok" : v >= 5 ? "warn" : "bad");

const STYLE = `
:host { display: block; }
ha-card { padding: 16px; }
.titolo { font-size: 1.15rem; font-weight: 500; color: var(--primary-text-color); margin: 0 0 8px; display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.titolo small { color: var(--secondary-text-color); font-size: .8rem; font-weight: 400; }
.pdfs { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 8px; }
.pdfbtn { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid var(--divider-color); border-radius: 10px; background: var(--secondary-background-color, transparent); color: var(--primary-text-color); font: inherit; cursor: pointer; text-align: left; }
.pdfbtn:hover { border-color: var(--primary-color); }
.pdfbtn ha-icon { color: var(--error-color, #db4437); flex: none; }
.pdfbtn .pn { font-weight: 500; flex: 1; min-width: 0; overflow-wrap: anywhere; }
.pdfbtn small { color: var(--secondary-text-color); white-space: nowrap; }
.pdfbtn.err { border-color: var(--error-color, #db4437); }
.pdfok { margin-top: 10px; padding: 10px 12px; border: 1px solid var(--primary-color); border-radius: 10px; color: var(--primary-text-color); }
.pdfok a { color: var(--primary-color); font-weight: 600; overflow-wrap: anywhere; display: block; margin-top: 4px; }
.periodo + .periodo { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--divider-color); }
.ph { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 1.05rem; cursor: pointer; user-select: none; }
.ph .pt { flex: 1; }
.ph ha-icon { --mdc-icon-size: 22px; color: var(--secondary-text-color); }
.mats { margin: 6px 0 10px; }
.alunno + .alunno { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--divider-color); }
.bad { --tc: var(--error-color, #db4437); } .warn { --tc: var(--warning-color, #ffa000); } .info { --tc: var(--primary-color, #03a9f4); }
.giorno { margin-top: 14px; border-left: 3px solid var(--tc); border-radius: 3px; padding-left: 10px; }
.giorno:first-of-type { margin-top: 4px; }
.giorno h4 { margin: 0 0 2px -10px; padding: 5px 10px; font-size: .95rem; font-weight: 500; color: var(--primary-text-color);
  background: color-mix(in srgb, var(--tc) 14%, transparent); border-radius: 0 4px 4px 0; display: flex; align-items: baseline; gap: 8px; }
.giorno h4 .q { color: var(--tc); font-weight: 700; font-size: .78rem; text-transform: uppercase; letter-spacing: .03em; }
.giorno h4 .d { flex: 1; }
.giorno h4 .n { color: var(--secondary-text-color); font-weight: 400; font-size: .8rem; }
.pill { display: inline-block; padding: 1px 9px; border-radius: 10px; font-weight: 700; font-size: .82rem; margin-bottom: 2px;
  color: var(--tc, var(--primary-text-color)); background: color-mix(in srgb, var(--tc, var(--secondary-text-color)) 16%, transparent); }
.riga.tn { border-left: 3px solid var(--tc); padding-left: 10px; }
.riga .q { color: var(--tc); font-weight: 700; }
.riga { display: flex; gap: 10px; align-items: flex-start; padding: 6px 0; color: var(--primary-text-color); }
.riga + .riga { border-top: 1px solid var(--divider-color); }
.riga .corpo { flex: 1; min-width: 0; }
.riga .mat { font-weight: 500; }
.riga .txt { white-space: pre-line; overflow-wrap: anywhere; }
.riga .sec { color: var(--secondary-text-color); font-size: .85rem; }
.voto { min-width: 2.6em; text-align: center; padding: 4px 6px; border-radius: 8px; font-weight: 600; color: #fff; }
.voto.ok { background: var(--success-color, #43a047); } .voto.warn { background: var(--warning-color, #ffa000); } .voto.bad { background: var(--error-color, #db4437); }
.chip { display: inline-block; padding: 2px 8px; border-radius: 12px; background: var(--secondary-background-color); color: var(--secondary-text-color); font-size: .8rem; margin: 2px 4px 0 0; }
.chip.bad { background: var(--error-color); color: #fff; }
.vuoto, .errore { color: var(--secondary-text-color); padding: 8px 0; }
.sum { display: flex; gap: 12px; align-items: center; padding: 8px 0; }
.sum + .sum { border-top: 1px solid var(--divider-color); }
.sum ha-icon { color: var(--secondary-text-color); --mdc-icon-size: 22px; flex: none; }
.sum .e { flex: 1; min-width: 0; } .sum .l { color: var(--secondary-text-color); font-size: .8rem; }
.sum .v { color: var(--primary-text-color); overflow-wrap: anywhere; }
.prog { display: flex; align-items: center; gap: 10px; padding: 6px 0; color: var(--primary-text-color); }
.prog + .prog { border-top: 1px solid var(--divider-color); }
.prog label { flex: 1; display: flex; align-items: center; gap: 10px; cursor: pointer; }
.prog input[type=checkbox] { width: 18px; height: 18px; accent-color: var(--primary-color); }
.prog input[type=time] { font: inherit; color: var(--primary-text-color); background: var(--secondary-background-color);
  border: 1px solid var(--divider-color); border-radius: 6px; padding: 4px 8px; color-scheme: light dark; }
.prog.spento label, .prog.spento input[type=time] { opacity: .45; }
.prog-master { font-weight: 500; padding-bottom: 8px; border-bottom: 2px solid var(--divider-color); margin-bottom: 2px; }
.compatta .riga { padding: 3px 0; } .compatta .sum { padding: 4px 0; }
`;

class DidupCard extends HTMLElement {
  static getConfigElement() { return document.createElement("didup-card-editor"); }
  static getStubConfig(hass) {
    const d = didupDevices(hass || {});
    return { vista: "riepilogo", ...(d.length === 1 ? { device_id: d[0] } : {}) };
  }

  setConfig(config) {
    if (config.vista && !VISTE.includes(config.vista)) throw new Error("vista non valida: " + config.vista);
    this._config = { vista: "riepilogo", max_elementi: 10, mostra_docente: true, compatta: false, raggruppa: "giorno", ...config };
    this._sig = null;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config) this._render();
  }

  getCardSize() { return this._config?.vista === "riepilogo" ? 4 : 6; }
  getGridOptions() { return { columns: 12, min_columns: 6, rows: "auto" }; }

  _targets() {
    const hass = this._hass, c = this._config;
    const ids = c.device_id ? [c.device_id] : didupDevices(hass);
    const tutti = ids.map((id) => ({ id, nome: deviceName(hass, id), ent: entitiesOfDevice(hass, id) }));
    if (c.device_id) return tutti;  // dispositivo scelto esplicitamente: così com'è
    // senza scelta: solo i dispositivi pertinenti (alunni per le viste degli alunni, report per il programma)
    return tutti.filter((t) => (c.vista === "programma" || c.vista === "pdf" ? !!t.ent.automatico_report : STUDENTE.some((k) => t.ent[k])));
  }

  _render() {
    const hass = this._hass;
    if (!hass || !this._config) return;
    const targets = this._targets();
    const eids = targets.flatMap((t) => Object.values(t.ent));
    const sig = eids.map((e) => hass.states[e]?.last_updated).join("|") + new Date().toDateString() + hass.language + JSON.stringify(this._config);
    if (sig === this._sig) return;
    this._sig = sig;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    const c = this._config;
    const corpo = targets.length
      ? targets.map((t) => `<div class="alunno">${this._alunno(t)}</div>`).join("")
      : `<div class="errore">${esc(tr(hass, "nessun_alunno"))}</div>`;
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card class="${c.compatta ? "compatta" : ""}">${corpo}</ha-card>`;
    this._bind();
  }

  _bind() {
    const h = this._hass;
    this.shadowRoot.querySelectorAll("[data-pdf]").forEach((el) => el.addEventListener("click", async () => {
      // link firmato (valido pochi minuti): il PDF non diventa pubblico
      try {
        const r = await h.callWS({ type: "auth/sign_path", path: el.dataset.pdf, expires: 300 });
        const a = document.createElement("a");
        a.href = h.hassUrl(r.path);
        if (NELL_APP()) {
          // app di Home Assistant (WebView): non ha schede nuove né un lettore PDF, ma scarica i file con l'attributo `download`
          // (come fa il frontend per i backup); il file finisce nei download del telefono
          const nome = el.dataset.nome || "report.pdf";
          a.target = "_blank"; a.download = nome; a.style.display = "none";
          document.body.appendChild(a); a.dispatchEvent(new MouseEvent("click")); document.body.removeChild(a);
          // in più, un link da toccare (un tocco diretto su un link funziona sempre) se il download automatico non parte
          this._link = { url: a.href, nome, fino: Date.now() + 240000 };
          this._sig = null; this._render();
        } else {
          a.target = "_blank"; a.rel = "noopener";  // browser: nuova scheda con il PDF
          this.shadowRoot.appendChild(a); a.click(); a.remove();
        }
      } catch (e) { el.title = tr(h, "pdf_errore"); el.classList.add("err"); }
    }));
    this.shadowRoot.querySelectorAll("[data-per]").forEach((el) => {
      const apri = () => { this._aperti = this._aperti || {}; this._aperti[el.dataset.per] = el.dataset.aperto !== "1"; this._sig = null; this._render(); };
      el.addEventListener("click", apri);
      el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); apri(); } });
    });
    this.shadowRoot.querySelectorAll("[data-sw]").forEach((el) => el.addEventListener("change", () =>
      h.callService("switch", el.checked ? "turn_on" : "turn_off", { entity_id: el.dataset.sw })));
    this.shadowRoot.querySelectorAll("[data-t]").forEach((el) => el.addEventListener("change", () => {
      if (el.value) h.callService("time", "set_value", { entity_id: el.dataset.t, time: el.value + ":00" });
    }));
  }

  _alunno(t) {
    const hass = this._hass, c = this._config;
    const v = c.vista;
    const titolo = c.device_id && c.titolo ? c.titolo : t.nome;
    const mediaEnt = t.ent.media_generale && hass.states[t.ent.media_generale];
    const media = mediaEnt && !isNaN(parseFloat(mediaEnt.state)) && v === "voti"
      ? `<small>${esc(tr(hass, "media"))} ${esc(parseFloat(mediaEnt.state).toFixed(2))}</small>` : "";
    const head = `<div class="titolo"><span>${esc(titolo)}${v === "riepilogo" ? "" : ` · ${esc(tr(hass, v))}`}</span>${media}</div>`;
    let body;
    try { body = this["_v_" + v](t); } catch (e) { body = `<div class="errore">${esc(e.message)}</div>`; }
    return head + body;
  }

  _lista(t, chiave) {
    const ent = t.ent[chiave];
    if (!ent) return null;
    const s = this._hass.states[ent];
    if (!s) return [];
    return s.attributes.elementi || [];
  }
  _inattiva() { return `<div class="vuoto">${esc(tr(this._hass, "non_attiva"))}</div>`; }
  _vuoto(k) { return `<div class="vuoto">${esc(tr(this._hass, k))}</div>`; }

  _v_compiti(t) {
    const h = this._hass, c = this._config;
    const l = this._lista(t, "compiti");
    if (l === null) return this._inattiva();
    if (!l.length) return this._vuoto("nessun_compito");
    const items = l.slice(0, c.max_elementi);
    if (c.raggruppa === "materia") {
      const g = {};
      items.forEach((x) => (g[x.materia] = g[x.materia] || []).push(x));
      return Object.entries(g).map(([m, xs]) => `<div class="giorno info"><h4><span class="d">${esc(m)}</span><span class="n">${xs.length}</span></h4>${xs.map((x) => {
        const [a, b] = dayLabel(h, x.data);
        return `<div class="riga ${tono(x.data)}"><div class="corpo"><div class="sec"><span class="q">${esc(a)}</span>${b ? " · " + esc(b) : ""}</div><div class="txt">${esc(x.testo)}</div></div></div>`;
      }).join("")}</div>`).join("");
    }
    const g = {};
    items.forEach((x) => (g[x.data] = g[x.data] || []).push(x));
    return Object.entries(g).map(([d, xs]) => {
      const [a, b] = dayLabel(h, d);
      const vicino = a === tr(h, "oggi") || a === tr(h, "domani");
      const q = vicino ? a : b, data = vicino ? b : a;
      return `<div class="giorno ${tono(d)}"><h4><span class="q">${esc(q)}</span><span class="d">${esc(data)}</span><span class="n">${xs.length}</span></h4>${xs.map((x) =>
        `<div class="riga"><div class="corpo"><span class="pill">${esc(x.materia)}</span><div class="txt">${esc(x.testo)}</div></div></div>`).join("")}</div>`;
    }).join("");
  }

  _v_promemoria(t) {
    const h = this._hass, c = this._config;
    const l = this._lista(t, "promemoria");
    if (l === null) return this._inattiva();
    if (!l.length) return this._vuoto("nessun_promemoria");
    return l.slice(0, c.max_elementi).map((x) => {
      const [a, b] = dayLabel(h, x.data);
      const extra = [x.ora, c.mostra_docente ? x.docente : ""].filter(Boolean).join(" · ");
      return `<div class="riga tn ${tono(x.data)}"><div class="corpo"><div class="sec"><span class="q">${esc(a)}</span>${b ? " · " + esc(b) : ""}${extra ? " · " + esc(extra) : ""}</div><div class="txt">${esc(x.testo)}</div></div></div>`;
    }).join("");
  }

  _v_voti(t) {
    // Tutti i voti dell'anno (senza tetto), divisi per quadrimestre, ciascuno con la media generale e quelle di materia.
    const h = this._hass, c = this._config;
    const ent = t.ent.ultimo_voto;
    if (!ent) return this._inattiva();
    const l = (h.states[ent]?.attributes.ultimi) || [];
    const per = (c.mostra_medie !== false && h.states[ent]?.attributes.periodi) || [];
    const riga = (x) => {
      const sec = [shortDate(h, x.data), x.tipo, c.mostra_docente ? x.docente : ""].filter(Boolean).join(" · ");
      return `<div class="riga"><span class="voto ${votoClasse(x.valore)}">${esc(x.voto)}</span><div class="corpo"><span class="mat">${esc(x.materia)}</span>` +
        `<div class="sec">${esc(sec)}</div>${!c.compatta && x.descrizione ? `<div class="txt">${esc(x.descrizione)}</div>` : ""}</div></div>`;
    };
    if (!per.length) return l.length ? l.map(riga).join("") : this._vuoto("nessun_voto");
    const d = new Date(), oggi = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const num = new Intl.NumberFormat(h.language || "en", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    // il quadrimestre in corso per primo; quelli non ancora iniziati e senza voti non si mostrano
    const blocchi = per.map((p, i) => ({ p, i, v: l.filter((x) => x.periodo === p.id) })).filter((b) => b.v.length || b.p.inizio <= oggi).reverse();
    const fuori = l.filter((x) => !per.some((p) => p.id === x.periodo));
    if (!blocchi.length && !fuori.length) return this._vuoto("nessun_voto");
    // aperto di default solo il quadrimestre in corso (o, a scuole chiuse, l'ultimo con voti); un tocco sulla testata apre/chiude
    const corrente = (blocchi.find((b) => b.p.inizio <= oggi && oggi <= b.p.fine) || blocchi.find((b) => b.v.length) || blocchi[0] || {}).p?.id;
    this._aperti = this._aperti || {};
    return blocchi.map(({ p, i, v }) => {
      const chiave = `${ent}|${p.id}`;
      const aperto = chiave in this._aperti ? this._aperti[chiave] : p.id === corrente;
      const nome = i < 2 ? tr(h, i ? "q2" : "q1") : p.nome;
      const media = p.media != null ? `<span class="voto ${votoClasse(p.media)}" title="${esc(tr(h, "media_gen"))}">${esc(num.format(p.media))}</span>` : "";
      const mats = (p.materie || []).map((m) => `<span class="chip${m.media < 6 ? " bad" : ""}">${esc(m.materia)} <b>${esc(num.format(m.media))}</b> · ${m.n}</span>`).join("");
      return `<div class="periodo"><div class="ph" data-per="${esc(chiave)}" data-aperto="${aperto ? 1 : 0}" role="button" tabindex="0">` +
        `<ha-icon icon="mdi:chevron-${aperto ? "up" : "down"}"></ha-icon><span class="pt">${esc(nome)}</span>${media}</div>` +
        (p.n_voti ? `<div class="sec">${esc(tr(h, "media_gen"))} · ${esc(tr(h, "n_voti").replace("{n}", p.n_voti))}</div>` : "") +
        (mats ? `<div class="mats">${mats}</div>` : "") +
        (aperto ? (v.length ? v.map(riga).join("") : this._vuoto("nessun_voto")) : "") + `</div>`;
    }).join("") + fuori.map(riga).join("");
  }

  _v_riepilogo(t) {
    const h = this._hass;
    const rows = [];
    const riga = (icon, label, value) => rows.push(`<div class="sum"><ha-icon icon="${icon}"></ha-icon><div class="e"><div class="l">${esc(label)}</div><div class="v">${value}</div></div></div>`);
    const comp = this._lista(t, "compiti");
    if (comp !== null) {
      if (!comp.length) riga("mdi:notebook-edit", tr(h, "compiti"), esc(tr(h, "nessun_compito")));
      else {
        const primo = comp[0].data, [a] = dayLabel(h, primo);
        const mats = comp.filter((x) => x.data === primo).map((x) => `<span class="chip">${esc(x.materia)}</span>`).join("");
        riga("mdi:notebook-edit", `${tr(h, "compiti")} · ${a}`, mats);
      }
    }
    const pro = this._lista(t, "promemoria");
    if (pro !== null) {
      if (!pro.length) riga("mdi:bell-ring", tr(h, "prossimo"), esc(tr(h, "nessuno")));
      else { const p = pro[0], [a] = dayLabel(h, p.data); riga("mdi:bell-ring", `${tr(h, "prossimo")} · ${a}`, esc(p.testo.length > 120 ? p.testo.slice(0, 120) + "…" : p.testo)); }
    }
    if (t.ent.ultimo_voto) {
      const s = h.states[t.ent.ultimo_voto], l = s?.attributes.ultimi || [];
      if (!l.length) riga("mdi:school", tr(h, "ultimo_voto"), esc(tr(h, "nessuno")));
      else { const x = l[0]; riga("mdi:school", `${tr(h, "ultimo_voto")} · ${shortDate(h, x.data)}`, `<span class="voto ${votoClasse(x.valore)}" style="display:inline-block">${esc(x.voto)}</span> ${esc(x.materia)}`); }
    }
    if (t.ent.media_generale) {
      const m = parseFloat(h.states[t.ent.media_generale]?.state);
      if (!isNaN(m)) riga("mdi:chart-line", tr(h, "media"), esc(m.toFixed(2)));
    }
    const note = this._lista(t, "note_disciplinari");
    if (note && note.length) riga("mdi:alert-circle", tr(h, "note"), `<span class="chip bad">${note.length}</span>`);
    const com = this._lista(t, "comunicazioni");
    if (com && com.length) riga("mdi:bulletin-board", tr(h, "comunicazioni"), esc(com[0].testo.slice(0, 90)) + (com[0].testo.length > 90 ? "…" : ""));
    return rows.length ? rows.join("") : this._inattiva();
  }
}

class DidupCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._draw(); }
  set hass(hass) { this._hass = hass; this._draw(); }
  _schema() {
    const h = this._hass;
    return [
      { name: "device_id", selector: { device: { integration: "didup" } } },
      { name: "vista", selector: { select: { mode: "dropdown", options: VISTE.map((v) => ({ value: v, label: tr(h, v) })) } } },
      { name: "titolo", selector: { text: {} } },
      { name: "max_elementi", selector: { number: { min: 1, max: 50, mode: "box" } } },
      { name: "raggruppa", selector: { select: { mode: "dropdown", options: [{ value: "giorno", label: tr(h, "giorno") }, { value: "materia", label: tr(h, "materia") }] } } },
      { name: "mostra_docente", selector: { boolean: {} } },
      { name: "compatta", selector: { boolean: {} } },
      { name: "mostra_medie", selector: { boolean: {} } },
    ];
  }
  _draw() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => tr(this._hass, { device_id: "ed_device", vista: "ed_vista", titolo: "ed_titolo", max_elementi: "ed_max", mostra_docente: "ed_docente", compatta: "ed_compatta", raggruppa: "ed_raggruppa", mostra_medie: "ed_medie" }[s.name]);
      this._form.addEventListener("value-changed", (ev) => {
        const cfg = { ...ev.detail.value };
        Object.keys(cfg).forEach((k) => (cfg[k] === "" || cfg[k] === undefined) && delete cfg[k]);
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.schema = this._schema();
    this._form.data = { vista: "riepilogo", max_elementi: 10, mostra_docente: true, compatta: false, raggruppa: "giorno", mostra_medie: true, ...this._config };
  }
}

customElements.define("didup-card", DidupCard);
customElements.define("didup-card-editor", DidupCardEditor);
window.customCards = window.customCards || [];
window.customCards.push({ type: "didup-card", name: "DidUP", description: T.it.descr, preview: false, documentationURL: "https://github.com/power80it/ha-didup" });
console.info(`%c DIDUP-CARD %c ${DIDUP_CARD_VERSION} `, "color:#fff;background:#3f51b5;font-weight:700", "color:#3f51b5;background:#fff");
