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
            view: "hjem",                    // "hjem" (forside) | "inbox" (e-post) | "kalender"
            kal: false,                      // månedsdata fra get_kalender()
            aktivBoks: false, aktivNavn: "", meldinger: [], valgt: false, period: "alle",
            group: "avsender", kandidater: { prosjekt: [], oppgave: [] },
            // Kollaps-tilstand hentes fra forrige økt (kun de FOLDEDE lagres).
            // Default = utvidet: en tom lagring skal aldri skjule noe.
            kollaps: this._lesKollaps("kollaps"),
            trekollaps: this._lesKollaps("trekollaps"),   // mappetreet: {kode: true} = foldet
            ctxTab: "rel",                                   // person-kontekst: rel | hist | week
            trad: { status: "", notater: [] }, nyNotat: "",  // arbeidsstatus + interne notater
            tverrValg: [],                    // gruppene mennesket kan overstyre til
            person: false, personOpen: false,                // person-visning (klikk «Til stede»)
            vedlegg: [], vedleggMsg: "",                      // vedlegg → element (Loym)
            redigerer: false, nyttNavn: "", fv: false,        // dokumentnavn · PDF · forhåndsvisning
            hoder: false, visHoder: false,                    // nøyaktige Fra/Til/Kopi-felter
            // Paring/tildeling — MANUELL vei når AI-forslaget ikke treffer (Gjermund 18.07.2026:
            // feltene sto som tomme skall uten funksjon). Ett åpent søkefelt om gangen.
            paring: {
                prosjekt: { nr: "", tekst: "", treff: [], valgt: false },
                oppgave: { nr: "", tekst: "", treff: [], valgt: false },
                ansvarlig: { tekst: "", treff: [], valgt: false },
                frist: "", apen: "", msg: "",
            },
        });
        onWillStart(async () => {
            const cfg = await this.orm.call(DATA, "get_my_config", []);
            Object.assign(this.state, cfg, { loading: false });
            await this.lastBokser();
            this.state.tverrValg = await this.orm.call(DATA, "get_tverr_valg", []);
            // Lander på OVERSIKTEN (forsiden) — ikke i innboksen. E-post er et underpunkt du går inn i.
            //
            // UNNTAK: kom vi hit fra en fargeboks i Kommunikasjon (paraplyen sender `fiq_boks`
            // i konteksten), skal vi åpne DEN boksen med én gang. Gjermund 18.07.2026: «viktig
            // at riktig mappe åpnes når jeg trykker på en av boksene — da åpnes f.eks. "Haster"
            // alle meldinger som haster». Uten dette lander klikket i Innboks, og filteret er tapt.
            const boks = this.props.action?.context?.fiq_boks;
            if (boks) {
                const alle = [...(this.state.basis || []), ...(this.state.tverr || []),
                              ...(this.state.taks || [])];
                const t = alle.find((b) => b.kode === boks);
                await this.aapneBoks(boks, t ? t.navn : boks);
                requestAnimationFrame(() => this.lastBredder());
            }
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
        // NB: `kollaps` nullstilles IKKE her lenger. Nøklene er prefikset med
        // grupperingsvalget, så de kolliderer ikke på tvers av bokser — og folding
        // brukeren har gjort skal overleve at hun bytter mappe.
        this.state.valgt = false; this.state.q = "";
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
    // ---- Dokumentnavn · PDF · forhåndsvisning (Gjermund 19.07.2026) ------------------

    startNavn(a) { this.state.redigerer = a.id; this.state.nyttNavn = a.navn || ""; }
    avbrytNavn() { this.state.redigerer = false; this.state.nyttNavn = ""; }

    /** Lagre nytt filnavn. Uendret navn → ingen serverkall. */
    async lagreNavn(a) {
        if (this.state.redigerer !== a.id) return;      // blur etter Escape
        const nytt = (this.state.nyttNavn || "").trim();
        this.avbrytNavn();
        if (!nytt || nytt === a.navn) return;
        const r = await this.orm.call(DATA, "gi_nytt_navn", [a.id, nytt]);
        if (r) {
            a.navn = r.navn;                            // vis med én gang
            this.state.vedleggMsg = "Navn endret til " + r.navn;
        } else {
            this.state.vedleggMsg = "Kunne ikke endre navnet — mangler du skrivetilgang?";
        }
    }

    /** Konvertér til PDF. Originalen beholdes — konvertering er ikke erstatning. */
    async tilPdf(a) {
        this.state.vedleggMsg = "Konverterer …";
        const r = await this.orm.call(DATA, "til_pdf", [a.id]);
        if (r && r.ok) {
            this.state.vedleggMsg = r.alt ? (a.navn + " " + r.alt)
                                          : ("PDF laget: " + r.navn);
            this.state.vedlegg = await this.orm.call(DATA, "get_vedlegg", [this.state.valgt.id]);
        } else {
            this.state.vedleggMsg = (r && r.feil) || "Konvertering feilet.";
        }
    }

    async visVedlegg(a) {
        this.state.fv = await this.orm.call(DATA, "forhandsvis", [a.id]);
    }
    lukkVedlegg() { this.state.fv = false; }

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
    /** Søk fra ENTEN nummerfeltet (`felt="nr"`) eller navnefeltet.
     *  Backend søker uansett på både nummer og navn — feltene er to innganger til
     *  samme kilde, ikke to ulike søk. Nummer godtar 1 tegn (prosjektnr. er korte),
     *  navn krever 2 (ellers laster «a» halve basen). */
    async sokMal(slag, ev, felt) {
        const p = this.state.paring;
        const verdi = ev.target.value;
        if (felt === "nr") { p[slag].nr = verdi; } else { p[slag].tekst = verdi; }
        p[slag].valgt = false;
        p.apen = slag;
        const term = (verdi || "").trim();
        if (term.length < (felt === "nr" ? 1 : 2)) { p[slag].treff = []; return; }
        p[slag].treff = await this.orm.call(DATA, "sok_mal", [
            term, slag, this.state.firm || false,
        ]);
    }

    // Velg et treff. Prosjekt/oppgave PARES med én gang (det er selve handlingen);
    // ansvarlig venter på «Tildel», siden frist hører sammen med den.
    async velgMal(slag, t) {
        const p = this.state.paring;
        p[slag].valgt = t;
        // Nummer og navn i HVERT SITT felt (mockup-fasit) — ikke smeltet sammen til én
        // tekst. Da ser du alltid hvilket nummer som faktisk er valgt.
        p[slag].nr = t.no || "";
        p[slag].tekst = t.navn || "";
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

    /** Overstyr tverrgående gruppe. Boksene lastes på nytt — flyttes meldingen fra
     *  «Uavklart» til «Haster», må begge tellerne endre seg med én gang. */
    async onTverrChange(ev) {
        if (!this.state.valgt) return;
        const r = await this.orm.call(DATA, "sett_tverr", [this.state.valgt.id, ev.target.value]);
        if (r === false) return;                       // ugyldig kode — backend avviste
        this.state.trad.tverr_kode = r.kode;
        this.state.trad.tverr_av = r.av;
        await this.lastBokser();
        if (this.state.aktivBoks) await this.lastMeldinger();
    }

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
    // Bytte gruppering nullstiller IKKE folding: nøklene bærer grupperingsnavnet, så
    // «avsender::Frank» og «type::Sendt» lever side om side. Bytter du fram og tilbake,
    // er foldingen din fortsatt der.
    setGroup(ev) { this.state.group = ev.target.value; }
    // ---- Kollaps-tilstand som HUSKES -----------------------------------------------
    // Krav 19.07 (via AI KR): «kollapse og utvide på alle nivåer i visninger med mange
    // elementer» + tilstand skal huskes. Uten lagring folder du sammen 40 grupper og
    // mister alt ved neste lasting.
    // 🛑 Nøkkelen er prefikset med grupperingsvalget (se grupper()) — ALDRI et bart navn.

    _lesKollaps(navn) {
        try { return JSON.parse(window.localStorage.getItem("fiq_epost_" + navn) || "{}") || {}; }
        catch (e) { return {}; }                 // korrupt lagring skal aldri velte flaten
    }
    _lagreKollaps(navn, obj) {
        try {
            // Lagre KUN de foldede. Ellers vokser lagringen med hver gruppe brukeren ser.
            const kun = {};
            for (const k in obj) { if (obj[k]) kun[k] = true; }
            window.localStorage.setItem("fiq_epost_" + navn, JSON.stringify(kun));
        } catch (e) { /* privat modus / full disk — folding virker, den huskes bare ikke */ }
    }

    toggleGroup(k) {
        this.state.kollaps[k] = !this.state.kollaps[k];
        this._lagreKollaps("kollaps", this.state.kollaps);
    }
    toggleAlle() {
        const keys = this.grupper().map(g => g.key);
        const anyOpen = keys.some(k => !this.state.kollaps[k]);
        const s = {};
        for (const k of keys) s[k] = anyOpen;
        this.state.kollaps = s;
        this._lagreKollaps("kollaps", s);
    }
    kollapsLabel() {
        const keys = this.grupper().map(g => g.key);
        return keys.some(k => !this.state.kollaps[k]) ? "Kollaps alle" : "Utvid alle";
    }

    // ---- Mappetreet i sidemenyen: kollaps per nivå ---------------------------------
    // Gjermund 19.07.2026: «Kollaps og minimer hoved på hvert nivå mangler».
    // Treet var en FLAT liste — 2 Adm med alle undermapper alltid utbrettet. Med 40+
    // koder ble sidemenyen umulig å skumme. Kodene bærer hierarkiet selv («2.30» hører
    // under «2»), så vi trenger ingen ny datastruktur — bare å lese dem.

    /** Er denne mappa skjult fordi en forelder over den er kollapset?
     *  Sjekker ALLE forfedre, ikke bare nærmeste: kollapser du «2», skal «2.30.01»
     *  også forsvinne. */
    skjult(kode) {
        const deler = (kode || "").split(".");
        for (let i = 1; i < deler.length; i++) {
            if (this.state.trekollaps[deler.slice(0, i).join(".")]) return true;
        }
        return false;
    }

    /** Har mappa barn? Kun da vises pilen — ellers ville blindveier fått en pil
     *  som ikke gjør noe. */
    harBarn(kode) {
        const p = (kode || "") + ".";
        return (this.state.taks || []).some((b) => (b.kode || "").startsWith(p));
    }

    /** Klikk på pilen: kollaps/utvid. Stopper klikket fra å åpne mappa samtidig —
     *  ellers ville ett trykk både folde sammen OG bytte visning. */
    vekslTre(kode, ev) {
        if (ev) { ev.stopPropagation(); }
        this.state.trekollaps[kode] = !this.state.trekollaps[kode];
        this._lagreKollaps("trekollaps", this.state.trekollaps);
    }

    /** Kollaps/utvid HELE treet på én gang. */
    vekslHeleTreet() {
        const foreldre = (this.state.taks || [])
            .filter((b) => this.harBarn(b.kode)).map((b) => b.kode);
        const noenApne = foreldre.some((k) => !this.state.trekollaps[k]);
        const s = {};
        for (const k of foreldre) s[k] = noenApne;
        this.state.trekollaps = s;
        this._lagreKollaps("trekollaps", s);
    }

    treLabel() {
        const foreldre = (this.state.taks || [])
            .filter((b) => this.harBarn(b.kode)).map((b) => b.kode);
        return foreldre.some((k) => !this.state.trekollaps[k]) ? "Kollaps alle" : "Utvid alle";
    }
    grupper() {
        const fnMap = {
            avsender: m => m.fra || "—",
            // «Prosjekt» skal vise PROSJEKTER — ikke emnelinjer. Gjermund 19.07.2026:
            // «Skjønner ikke igjen dette som prosjekter. Er det oppgaver??» Nei: alt som
            // ikke er paret med project.project/project.task falt før tilbake på emnet,
            // så lista viste «RE», «FACEBOOK», «IWRYRECY.JPEG». Nå samles ALT uparet i
            // én ærlig bolk, og de parede vises med nummer foran navnet.
            prosjekt: m => (m.er_paret
                ? ((m.element_nr ? m.element_nr + " " : "") + (m.element || "")).trim()
                : "Ikke paret ennå"),
            dato: m => this.datoBolk(m),
            type: m => (m.retning === "sendt" ? "Sendt" : "Mottatt"),
        };
        const fn = fnMap[this.state.group] || fnMap.avsender;
        const grp = {}, order = [];
        for (const m of this.state.meldinger) {
            const k = fn(m);
            if (!grp[k]) { grp[k] = []; order.push(k); }
            grp[k].push(m);
        }
        // `key` = STABIL nøkkel til kollaps-tilstand · `label` = det brukeren ser.
        // Nøkkelen prefikses med grupperingsvalget: ellers ville «Sendt» (type) og en
        // avsender som heter «Sendt» delt samme kollaps-tilstand, og bytte av gruppering
        // ville dratt med seg foldingen fra forrige visning.
        // (Jf. 00.03s WBS-funn: nøkle ALDRI på et navn som kan gjentas.)
        return order.map(k => ({
            key: this.state.group + "::" + k,
            label: k,
            items: grp[k],
            n: grp[k].length,
        }));
    }
    // ---- Dato-gruppering: trapp fra dag → uke → måned → kvartal → år ----------------
    // Gjermund 19.07.2026: «på gruppering på dato må man kunne ha en logikk og ikke minst
    // årstall. Logikken kan være dager på inneværende uke, deretter på uke siste 4 uker
    // (ukenummer) deretter måned (3 mnd) Kvartal og deretter År».
    //
    // Før: `m.dato.slice(0,5)` — én bolk per DATO, uten årstall. 515 e-poster ga hundrevis
    // av grupper, og «01.06» i fjor havnet sammen med «01.06» i år. Nå blir nær tid finkornet
    // og gammel tid grovkornet, slik øyet faktisk leter.

    /** ISO-8601 ukenummer. Kan ikke utledes fra dato alene i JS — må regnes ut.
     *  Torsdag-regelen: uka tilhører året som eier dens torsdag (derfor kan 31.12 være uke 1). */
    ukenummer(d) {
        const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
        t.setUTCDate(t.getUTCDate() + 4 - (t.getUTCDay() || 7));      // flytt til torsdag
        const nyttaar = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
        return { uke: Math.ceil(((t - nyttaar) / 86400000 + 1) / 7), aar: t.getUTCFullYear() };
    }

    /** Mandag i uka som datoen ligger i (norsk uke starter mandag, ikke søndag). */
    mandag(d) {
        const m = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        m.setDate(m.getDate() - ((m.getDay() + 6) % 7));
        return m;
    }

    datoBolk(m) {
        const iso = m.dato_iso || "";
        if (!iso) return "Uten dato";
        const d = new Date(iso + "T00:00:00");
        if (isNaN(d)) return "Uten dato";

        const naa = new Date();
        const idag = new Date(naa.getFullYear(), naa.getMonth(), naa.getDate());
        const dager = Math.round((idag - d) / 86400000);

        // Fremtid (møteinvitasjoner, planlagt utsending) — egen bolk, aldri «i dag».
        if (dager < 0) return "Kommende";

        // 1) INNEVÆRENDE UKE → dag for dag
        const mandagDenneUka = this.mandag(naa);
        if (d >= mandagDenneUka) {
            if (dager === 0) return "I dag";
            if (dager === 1) return "I går";
            const DAG = ["Søndag", "Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag"];
            return DAG[d.getDay()];
        }

        // 2) SISTE 4 UKER → ukenummer. Grensen regnes i HELE uker (fra mandag), ikke 28 dager,
        //    ellers ville en e-post fra mandag for 4 uker siden falt ut midt i uka si.
        const uker = Math.round((mandagDenneUka - this.mandag(d)) / (7 * 86400000));
        const u = this.ukenummer(d);
        if (uker <= 4) {
            return "Uke " + u.uke + (u.aar !== naa.getFullYear() ? " (" + u.aar + ")" : "");
        }

        // 3) SISTE 3 MÅNEDER → månedsnavn
        const MND = ["Januar", "Februar", "Mars", "April", "Mai", "Juni",
                     "Juli", "August", "September", "Oktober", "November", "Desember"];
        const mndDiff = (naa.getFullYear() - d.getFullYear()) * 12 + (naa.getMonth() - d.getMonth());
        if (mndDiff <= 3) {
            return MND[d.getMonth()] + (d.getFullYear() !== naa.getFullYear() ? " " + d.getFullYear() : "");
        }

        // 4) SAMME ÅR → kvartal
        if (d.getFullYear() === naa.getFullYear()) {
            return "Q" + (Math.floor(d.getMonth() / 3) + 1) + " " + d.getFullYear();
        }

        // 5) ELDRE → år
        return String(d.getFullYear());
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
    // ---- Kalender INNE i flaten ------------------------------------------------------
    // Gjermund 19.07.2026: «og kalenderen mangler». Den gjorde det: knappen kalte
    // doAction("calendar.action_calendar_event") → brukeren ble kastet UT av
    // Kommunikasjon. Samme feil som `view:`-fella KR fant 18.07. Nå bygges måneden her.

    async aapneKalender(aar, mnd) {
        this.state.view = "kalender";
        this.state.kal = await this.orm.call(DATA, "get_kalender", [
            aar || false, mnd || false, this.state.firm || false,
        ]);
    }

    /** Bla måned. Håndterer årsskifte: desember → januar neste år, og motsatt. */
    async blaMnd(steg) {
        const k = this.state.kal;
        if (!k) return;
        let m = k.mnd + steg, a = k.aar;
        if (m > 12) { m = 1; a += 1; }
        if (m < 1) { m = 12; a -= 1; }
        await this.aapneKalender(a, m);
    }

    /** Rutenett-celler: tomme plassholdere før den 1., så dagene. Norsk uke =
     *  mandag først (backend gir `start_ukedag` med mandag=0). */
    kalCeller() {
        const k = this.state.kal;
        if (!k) return [];
        const ut = [];
        for (let i = 0; i < k.start_ukedag; i++) ut.push({ tom: true, key: "t" + i });
        for (let d = 1; d <= k.antall_dager; d++) {
            const iso = k.aar + "-" + String(k.mnd).padStart(2, "0") + "-" + String(d).padStart(2, "0");
            ut.push({
                tom: false, key: iso, dag: d, iso,
                hendelser: (k.dager && k.dager[iso]) || [],
                i_dag: iso === k.i_dag,
            });
        }
        return ut;
    }

    /** Klikk en hendelse: åpne den native posten (møte/oppgave). Her forlater vi
     *  flaten BEVISST — brukeren ba om å se selve elementet. */
    aapneHendelse(h) {
        if (!h || !h.id) return;
        this.action.doAction({
            type: "ir.actions.act_window", res_model: h.model,
            res_id: h.id, views: [[false, "form"]], target: "current",
        });
    }

    /** Odoos egen kalender — for den som vil dit. Vi kaprer ikke native. */
    aapneNativKalender() { this.action.doAction("calendar.action_calendar_event"); }
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
