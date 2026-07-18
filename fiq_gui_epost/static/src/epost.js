/** @odoo-module **/

// Meldingssenter — Outlook-utforming (tre-rute), V00.05.
// Godkjent GUI-retning (Gjermund 2026-07-14): mappetre | meldingsliste | lese-/kontekstpanel,
// taksonomi-boksene som «smarte mapper», cockpit-oversikten bak «Hjem». EKTE data via samme backend-API.
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DATA = "fiq.meldingssenter.data";

export class FiqMeldingssenter extends Component {
    static template = "fiq_gui_epost.MsgSenter";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.STATUS_NAVN = { apen: "Åpen", pagar: "Pågår", ferdig: "Ferdig" };
        this.state = useState({
            loading: true, firms: [], current_firm: false, presence: [], user: "", logo: "", q: "",
            kryss_firma: false,                              // 000-rettighet (fra sesjonen, ikke klienten)
            basis: [], tverr: [], taks: [],
            // Kommunikasjon = hovedflaten. Forsiden er OVERSIKTEN; e-post er ETT underpunkt.
            // (Gjermund 16.07.2026: «kommunikasjon er hoved KR for kommunikasjon og er din flate —
            //  e-post skal komme opp som et av underpunktene». Oversikt som forside.)
            view: "hjem",                                  // "hjem" (oversikt=forside) | "inbox" (e-post)
            aktivBoks: false, aktivNavn: "", meldinger: [], valgt: false, period: "alle",
            group: "avsender", kollaps: {}, kandidater: { prosjekt: [], oppgave: [] },
            ctxTab: "rel",                                   // person-kontekst: rel | hist | week
            trad: { status: "", notater: [] }, nyNotat: "",  // arbeidsstatus + interne notater
            person: false, personOpen: false,                // person-visning (klikk «Til stede»)
            vedlegg: [], vedleggMsg: "",                      // vedlegg → element (Loym)
            hoder: false, visHoder: false,                    // nøyaktige Fra/Til/Kopi-felter
            // Paring/tildeling — MANUELL vei når AI-forslaget ikke treffer (Gjermund 18.07.2026:
            // feltene sto som tomme skall uten funksjon). Ett åpent søkefelt om gangen.
            paring: {
                prosjekt: { tekst: "", treff: [], valgt: false },
                oppgave: { tekst: "", treff: [], valgt: false },
                ansvarlig: { tekst: "", treff: [], valgt: false },
                frist: "", apen: "", msg: "",
            },
        });
        onWillStart(async () => {
            const cfg = await this.orm.call(DATA, "get_my_config", []);
            Object.assign(this.state, cfg, { loading: false });
            await this.lastBokser();
            // Lander på OVERSIKTEN (forsiden) — ikke i innboksen. E-post er et underpunkt du går inn i.
        });
        onMounted(() => this.lastBredder());     // gjenopprett dragde kolonnebredder
    }

    async lastBokser() {
        const b = await this.orm.call(DATA, "get_boxes", [], {
            firm: this.state.current_firm, period: this.state.period });
        this.state.basis = b.basis;
        this.state.tverr = b.tverrgaende;
        this.state.taks = b.taksonomi;
    }

    async byttFirma(id) {
        this.state.current_firm = id;
        const f = this.state.firms.find(x => x.id === id);
        if (f && f.logo) this.state.logo = f.logo;
        this.state.valgt = false;
        await this.lastBokser();
        // Bli der du er: er du i e-post, last den på nytt for nytt firma; ellers behold oversikten.
        if (this.state.view === "inbox" && this.state.aktivBoks) {
            await this.lastMeldinger();
        } else {
            this.state.meldinger = [];
        }
    }

    // Oversikten = forsiden i Kommunikasjon. E-post = ett underpunkt man går inn i.
    visHjem() { this.state.view = "hjem"; this.state.valgt = false; }

    /** Åpne E-post-kanalen (lander på Innboks). Kalles fra «E-post» i sidemenyen. */
    async aapneEpost() {
        const inn = (this.state.basis || [])[0];
        if (inn) {
            await this.aapneBoks(inn.kode, inn.navn);
        } else {
            this.state.view = "inbox";
        }
        // Tre-ruta bygges først NÅ (den finnes ikke i «hjem»-visningen), så breddene
        // må settes etter at den er tegnet — ellers har .pane ingen kolonner å styre.
        requestAnimationFrame(() => this.lastBredder());
    }
    visInnboks() { this.aapneEpost(); }

    async aapneBoks(kode, navn) {
        this.state.view = "inbox";
        this.state.aktivBoks = kode; this.state.aktivNavn = navn;
        this.state.valgt = false; this.state.q = ""; this.state.kollaps = {};
        await this.lastMeldinger();
    }

    async lastMeldinger() {
        if (!this.state.aktivBoks) return;
        this.state.meldinger = await this.orm.call(DATA, "get_messages", [], {
            boks: this.state.aktivBoks, firm: this.state.current_firm,
            period: this.state.period, q: this.state.q || false });
    }

    sok(ev) { this.state.q = (ev.target.value || "").trim(); this.lastMeldinger(); }

    async velgMelding(m) {
        this.state.valgt = m;
        this.state.ctxTab = "rel";
        this.state.nyNotat = "";
        this.state.vedlegg = []; this.state.vedleggMsg = "";
        this.state.hoder = false; this.state.visHoder = false;
        this.state.kandidater = { prosjekt: [], oppgave: [] };
        this.state.trad = { status: "", notater: [] };
        this.state.hoder = await this.orm.call(DATA, "get_hoder", [m.id]);
        this.state.kandidater = await this.orm.call(DATA, "get_kandidater", [m.id]);
        this.state.trad = await this.orm.call(DATA, "get_thread", [m.id]);
        this.state.vedlegg = await this.orm.call(DATA, "get_vedlegg", [m.id]);
    }

    // Vis/skjul alle detaljer i e-posthodet (Fra/Til/Kopi/Blindkopi/Svar-til)
    toggleHoder() { this.state.visHoder = !this.state.visHoder; }
    // «Person <adresse>» — navn OG adresse, så det aldri er tvil om hvem
    navnAdr(p) {
        if (!p) return "";
        if (p.navn && p.adresse) return p.navn + " <" + p.adresse + ">";
        return p.navn || p.adresse || "";
    }

    // Vedlegg → lagre på elementet meldingen gjelder (Loym-modellen)
    async lagrePaaElement(model, resId, navn) {
        if (!this.state.valgt) return;
        const n = await this.orm.call(DATA, "lagre_paa_element", [this.state.valgt.id, model, resId]);
        this.state.vedleggMsg = n ? (n + " vedlegg lagret på " + navn) : "Ingen vedlegg å lagre.";
    }

    // ---- Paring / tildeling: den MANUELLE veien ------------------------------------
    // AI-forslagene over («Hører sannsynligvis til») var klikkbare fra før. Feltene under
    // var rene input uten binding — de så ut som et skjema, men gjorde ingenting.
    // Nå søker de mot ekte prosjekter/oppgaver/brukere og lagrer via backend.

    // Søk mens du skriver. Kort term gir ingen treff (unngå å laste halve basen på «a»).
    async sokMal(slag, ev) {
        const p = this.state.paring;
        p[slag].tekst = ev.target.value;
        p[slag].valgt = false;
        p.apen = slag;
        if ((p[slag].tekst || "").trim().length < 2) { p[slag].treff = []; return; }
        p[slag].treff = await this.orm.call(DATA, "sok_mal", [
            p[slag].tekst, slag, this.state.firm || false,
        ]);
    }

    // Velg et treff. Prosjekt/oppgave PARES med én gang (det er selve handlingen);
    // ansvarlig venter på «Tildel», siden frist hører sammen med den.
    async velgMal(slag, t) {
        const p = this.state.paring;
        p[slag].valgt = t;
        p[slag].tekst = (t.no ? t.no + " " : "") + t.navn;
        p[slag].treff = [];
        p.apen = "";
        if (slag === "ansvarlig") { p.msg = "Velg frist og trykk Tildel."; return; }
        if (!this.state.valgt) return;
        const model = slag === "oppgave" ? "project.task" : "project.project";
        const r = await this.orm.call(DATA, "par_melding", [this.state.valgt.id, model, t.id]);
        p.msg = r ? ("Paret med " + (r.navn || "")) : "Kunne ikke pare — mangler du tilgang til målet?";
        if (r) { await this.velgMelding(this.state.valgt); }   // kandidatlista er nå utdatert
    }

    // Tildel ansvarlig + frist. Backend lager en Odoo-aktivitet på elementet meldingen
    // henger på — derfor må meldingen være paret FØRST hvis den ikke alt ligger et sted.
    async tildelAnsvarlig() {
        const p = this.state.paring;
        if (!this.state.valgt || !p.ansvarlig.valgt) { p.msg = "Velg en ansvarlig først."; return; }
        const r = await this.orm.call(DATA, "tildel", [
            this.state.valgt.id, p.ansvarlig.valgt.id, p.frist || false,
        ]);
        p.msg = r ? ("Tildelt " + p.ansvarlig.valgt.navn + (p.frist ? " med frist " + p.frist : ""))
                  : "Kunne ikke tildele — meldingen må være paret med et element først.";
    }

    // Overlay-skriv: ny melding uten å forlate innboksen (v1 → Discuss-komposer)
    skrivNy() { this.action.doAction("mail.action_discuss"); }

    // Arbeidsstatus (åpen/pågår/ferdig) — persisteres + holder liste-merket i synk
    async setStatus(status) {
        if (!this.state.valgt) return;
        await this.orm.call(DATA, "set_status", [this.state.valgt.id, status]);
        this.state.trad.status = status;
        this.state.valgt.status = status;
        this.state.valgt.status_navn = this.STATUS_NAVN[status] || "";
    }
    onStatusChange(ev) { this.setStatus(ev.target.value); }

    // Internt notat (team-only)
    onNotatInput(ev) { this.state.nyNotat = ev.target.value; }
    async leggNotat() {
        const b = (this.state.nyNotat || "").trim();
        if (!b || !this.state.valgt) return;
        const note = await this.orm.call(DATA, "add_note", [this.state.valgt.id, b]);
        if (note) this.state.trad.notater.unshift(note);
        this.state.nyNotat = "";
    }

    // Gruppering + kollaps
    setGroup(ev) { this.state.group = ev.target.value; this.state.kollaps = {}; }
    toggleGroup(k) { this.state.kollaps[k] = !this.state.kollaps[k]; }
    toggleAlle() {
        const keys = this.grupper().map(g => g.key);
        const anyOpen = keys.some(k => !this.state.kollaps[k]);
        const s = {};
        for (const k of keys) s[k] = anyOpen;
        this.state.kollaps = s;
    }
    kollapsLabel() {
        const keys = this.grupper().map(g => g.key);
        return keys.some(k => !this.state.kollaps[k]) ? "Kollaps alle" : "Utvid alle";
    }
    grupper() {
        const fnMap = {
            avsender: m => m.fra || "—",
            prosjekt: m => m.element || "(uten element)",
            dato: m => (m.dato || "—").slice(0, 5),
            type: m => (m.retning === "sendt" ? "Sendt" : "Mottatt"),
        };
        const fn = fnMap[this.state.group] || fnMap.avsender;
        const grp = {}, order = [];
        for (const m of this.state.meldinger) {
            const k = fn(m);
            if (!grp[k]) { grp[k] = []; order.push(k); }
            grp[k].push(m);
        }
        return order.map(k => ({ key: k, items: grp[k], n: grp[k].length }));
    }
    harKobling() {
        const k = this.state.kandidater || {};
        return (k.prosjekt || []).length + (k.oppgave || []).length > 0;
    }
    setCtxTab(t) { this.state.ctxTab = t; }

    // Person-visning: klikk et «Til stede»-navn → e-post / chat / ukesplan / tilknyttede
    async openPerson(userId) {
        this.state.ctxTab = "rel";
        const p = await this.orm.call(DATA, "get_person", [], { user_id: userId });
        if (p && p.id) { this.state.person = p; this.state.personOpen = true; }
    }
    lukkPerson() { this.state.personOpen = false; }
    personChat() { this.action.doAction("mail.action_discuss"); }
    aapneKontakt() {
        if (!this.state.person) return;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "res.partner",
            res_id: this.state.person.id, view_mode: "form",
            views: [[false, "form"]], target: "current",
        });
    }

    async svar(replyAll) {
        if (!this.state.valgt) return;
        const act = await this.orm.call(DATA, "svar", [this.state.valgt.id, replyAll]);
        if (act) this.action.doAction(act);
    }

    tilbakeKR() { this.action.doAction("fiq_gui_control.action_fiq_gui_control"); }
    aapneKalender() { this.action.doAction("calendar.action_calendar_event"); }
    aapneInnstillinger() { this.action.doAction("base_setup.action_general_configuration"); }

    // ---- Dragbare kolonnebredder (Gjermund 18.07.2026) ------------------------------
    // Bredden settes som CSS-variabler på .pane og huskes i nettleseren, så oppsettet
    // står ved neste besøk. Grenser hindrer at en kolonne dras helt bort.
    static BREDDER = { tre: { min: 170, max: 420, std: 230, css: "--w-tre" },
                       liste: { min: 260, max: 720, std: 360, css: "--w-liste" } };

    lastBredder() {
        const pane = document.querySelector(".msapp .pane");
        if (!pane) return;
        for (const [key, cfg] of Object.entries(FiqMeldingssenter.BREDDER)) {
            let v = parseInt(window.localStorage.getItem("fiq_epost_bredde_" + key) || "", 10);
            if (!Number.isFinite(v)) v = cfg.std;
            pane.style.setProperty(cfg.css, Math.min(cfg.max, Math.max(cfg.min, v)) + "px");
        }
    }

    startDrag(ev, key) {
        const cfg = FiqMeldingssenter.BREDDER[key];
        const pane = ev.target.closest(".pane");
        if (!cfg || !pane) return;
        ev.preventDefault();                                   // ingen tekstmarkering
        const start = ev.clientX;
        const fra = parseInt(getComputedStyle(pane).getPropertyValue(cfg.css), 10) || cfg.std;
        ev.target.classList.add("on");
        ev.target.setPointerCapture?.(ev.pointerId);

        const flytt = (e) => {
            const bredde = Math.min(cfg.max, Math.max(cfg.min, fra + (e.clientX - start)));
            pane.style.setProperty(cfg.css, bredde + "px");
        };
        const slutt = () => {
            ev.target.classList.remove("on");
            const naa = parseInt(getComputedStyle(pane).getPropertyValue(cfg.css), 10);
            if (Number.isFinite(naa)) {
                try { window.localStorage.setItem("fiq_epost_bredde_" + key, String(naa)); }
                catch (e) { /* privat modus e.l. — bredden gjelder da kun denne økta */ }
            }
            window.removeEventListener("pointermove", flytt);
            window.removeEventListener("pointerup", slutt);
            window.removeEventListener("pointercancel", slutt);
        };
        window.addEventListener("pointermove", flytt);
        window.addEventListener("pointerup", slutt);
        window.addEventListener("pointercancel", slutt);       // rydder også ved avbrudd
    }

    // Hjelpere
    initialer(navn) {
        return (navn || "?").split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
    }
    pcls(status) {
        return status === "online" ? "til" : (status === "away" ? "mote" : "fra");
    }
    statuscls(s) {
        return s === "ferdig" ? "ferdig" : (s === "pagar" ? "pagar" : "apen");
    }
}

registry.category("actions").add("fiq_gui_epost_dashboard", FiqMeldingssenter);
