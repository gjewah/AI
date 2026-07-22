/** @odoo-module **/

import { Component, useState, onWillStart, onWillDestroy, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { View } from "@web/views/view";
import { useFileViewer } from "@web/core/file_viewer/file_viewer_hook";
import { FileModel } from "@web/core/file_viewer/file_model";

const WIDGETS = ["kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"];

// Kanonisk fargekart per fagområde (fiq-fargekart-omrader). Underområde-unntak først.
// KANONISK FARGEKART — synket mot `brand/fiq_fargekart_omrader.md` (Gjermund 18.07.2026).
//
// 🔴 Kanon-fila pekte navngitt på DENNE koden som avvikende og utdatert: «gir ulike farger
// på samme område avhengig av flate». Åtte av ti hovedområder var feil. Rettet 20.07.2026
// etter at Gjermund ba meg sjekke fargekartet i taksonomien.
//
// 🛑 DE FIRE GRØNNE (3 · 5 · 7 · 8) MÅ KUNNE SKILLES. Ikonene ga 5 og 7 nøyaktig samme
// verdi — da blir boksene like og kartet ubrukelig. Verdiene under er MÅLT slik at alle par
// skilles på lysstyrke (≥40) eller fargetone (≥45):
//   5 Marked #26521A (69) · 8 FAG #0E7C86 (101) · 3 Drift #00A83C (124) · 7 Prosj #95D97A (196)
// Endrer du ÉN av dem: mål avstanden til de tre andre på nytt, ellers kollapser skillet.
const SP_SUB_COLOR = {
    // Finans-familien under Admin — mørk blå (ikon-verifisert)
    "2.70": "#243C6C", "2.71": "#243C6C", "2.80": "#243C6C",
    // IT-familien — lilla. AI hører HIT, ikke til 8 FAG.
    "2.90": "#7830A8", "2.91": "#7830A8", "8.50": "#7830A8", "8.51": "#7830A8",
    // 2.50 KH arver 2 Administrasjon (lys blå) — sto feilaktig som grønn før.
};
const SP_TOP_COLOR = {
    "0": "#7A8593",   // Info — grå
    "1": "#243C6C",   // Ledelse — mørk blå, SAMME som 2.70 (sto grå før)
    "2": "#0078CC",   // Administrasjon — lys blå (inkl. 2.05 JUR + 2.20 HR)
    "3": "#00A83C",   // Drift — knall grønn (sto grå før)
    "4": "#E47830",   // Logistikk — oransje
    "5": "#26521A",   // Marked — mørk kraftig grønn
    "6": "#D80000",   // Salg — rød
    "7": "#95D97A",   // Prosjekter — lysere grønn
    "8": "#0E7C86",   // FAG — grønn/blå (teal). Sto GUL før.
    "9": "#78D8D8",   // Privat — turkis (sto gul før)
};
// Hele AI-serien 8.50–8.99 er lilla som IT — ikke bare 8.50. Samme regel som
// Meldingssenteret bruker (`_AI_SERIE`, fiq_gui_epost_data.py:73), så de to flatene
// aldri viser ulik farge på samme område.
const SP_AI_SERIE = /^8\.(5\d|[6-9]\d)$/;
const SP_DARK_TEXT = ["#FFC000", "#E7E6E6"];

function spColor(nr) {
    // Rekkefølge: eksakt unntak → AI-serien 8.50–8.99 (lilla) → hovedområdets farge.
    // Samme rekkefølge som Meldingssenteret (`_omraade_farge`, fiq_gui_epost_data.py:76),
    // slik at et område ALDRI får ulik farge avhengig av hvilken flate du står i.
    const c = SP_SUB_COLOR[nr]
        || (SP_AI_SERIE.test(nr || "") ? "#7830A8" : false)
        || SP_TOP_COLOR[(nr || "").split(".")[0]] || "#6b7280";
    return { color: c, dk: SP_DARK_TEXT.includes(c) };
}

const mndNames = () => [_t("January"), _t("February"), _t("March"), _t("April"), _t("May"), _t("June"), _t("July"), _t("August"), _t("September"), _t("October"), _t("November"), _t("December")];
// 🧊 Frys tilstanden: disse state-nøklene gjenopprettes når man kommer tilbake fra native Odoo (samme dag)
const FREEZE_KEYS = ["mode", "view", "rightView", "cpFilter", "cpKunde", "cpProj", "cpMode", "cpSlag", "cpGrp",
    "kommPeriod", "anchorDate", "kommQuery", "kommDir", "projQuery", "projNoQuery", "projArea", "projAreaId",
    "taskNoQuery", "taskTextQuery", "taskStage", "taskMile", "dagVis", "aktFilter", "aktGruppe", "selectedKpi",
    "progLevel", "progProjId", "progProjName", "progSubs", "progGroup", "kalMnd", "stageHidden", "dashSel"];
// 🚨 Utdatert-GUI-vakt: bumpes ved HVER versjon — sammenlignes med installert modulversjon
// ⚠️ MÅ FØLGE __manifest__.py sin "version" — ellers tror KR at fanen kjører gammel
// kode og viser «A new version is installed»-banneret som ALDRI forsvinner, uansett
// hvor mange ganger brukeren laster på nytt. Bump denne i SAMME commit som manifestet.
const GUI_BUILD = "19.0.7.2.0";
const dayNames = () => [_t("Mon"), _t("Tue"), _t("Wed"), _t("Thu"), _t("Fri"), _t("Sat"), _t("Sun")];

function isoWeek(date) {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
}

export class FiqControlRoom extends Component {
    static template = "fiq_gui_control.ControlRoom";
    static props = ["*"];
    static components = { View };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.fileViewer = useFileViewer();

        // Stable props for the embedded native Odoo Gantt (right panel). loadIrFilters stays
        // false (default) so stray default groupings are NOT applied; group by stage like native.
        this.ganttProps = {
            type: "gantt",
            resModel: "project.task",
            domain: [["project_id.active", "=", true]],
            context: { group_by: ["stage_id"] },
            display: { controlPanel: false },
            noContentHelp: _t("No planned tasks."),
        };

        const show = {};
        WIDGETS.forEach((w) => (show[w] = true));

        this.state = useState({
            accent: "#38B44A",
            logo: null,
            companyName: "",
            companies: [],         // selectable companies (company picker)
            companyId: false,      // current active company
            mode: "total",         // Simple/Full: "enkel" (simple) | "total" (full)
            customize: false,
            isAdmin: false,
            cockpitEdit: false,    // redigerer cockpit-URL (AI Kontrollrom-flaten)
            cockpitUrlDraft: "",
            cp: null,              // AI-cockpit: grupper/oppgaver fra get_cockpit
            cpFilter: "alle",     // VIS-filter: alle | du | ai | apen
            cpScope: null,         // toppmeny-data: kunder + prosjekter (get_cockpit_scope)
            cpKunde: "",          // valgt kunde-id ("" = alle, "iq" = 0.00 IQ-serien)
            cpProj: "",           // valgt prosjekt/prosess ("" = alle i scope)
            cpMode: "fremdrift",  // fremdrift | forbruk
            cpSlag: "ai",         // ai (AI-plattformprosjekter) | interne (Coworker tagger AI-prosjektene)
            cpDiagram: [],         // diagram-rader (alle prosjekter i scope)
            cpFold: {},            // foldede cockpit-grupper {prosjektId: true}
            okter: [],             // AI Økter: øktenes status + siste rapport
            krever: [],            // KREVER HANDLING NÅ: dine åpne på tvers av AI-scopet
            oktSvar: {},           // svar-utkast per økt {taskId: tekst}
            oktSel: 0,             // åpen svarlinje (taskId)
            cpGrp: true,           // «Alle»: gruppér diagrammet på kunde/hjerne
            cpDiagFold: {},        // foldede diagram-grupper {rotId: true}
            dashSel: this._loadDashSel(),  // Mitt dashbord: valgte xmlids (huskes per nettleser)
            dashEdit: false,       // tilpassnings-modus for Mitt dashbord
            darkMap: this._loadDarkMap(),  // 🌙 mørk bakgrunn PER KONTROLLPANEL (view) — huskes
            blockOrder: ["activity", "quick", "projects", "dash", "chart"],  // 📌 flate-rekkefølge (per bruker, server-lagret)
            navOrder: [],          // 📌 Styring-menyens rekkefølge (per bruker, server-lagret)
            aktQuery: "",                  // aktivitets-søk (samme linje som filter + gruppér)
            dagVis: "begge",              // Møter og aktiviteter: begge | moter | akt
            aktGrpFold: {},                // foldede grupperingsoverskrifter {gruppenavn: true}
            level: "balansert",
            show,
            kpis: [],
            selectedKpi: "",
            finansLines: [],      // detaljlinjer for Finans-boksen (fakturaer som krever handling)
            collapsed: this._loadCollapsed(),
            projects: [],
            projQuery: "",        // project search over the project overview (fritekst)
            projNoQuery: "",      // prosjektsøk: nummer (sequence_code)
            projArea: "",         // fagområde-filter (fagområdenr, f.eks. "6" el. "2.20") – tom = alle
            projAreaId: false,    // område-PROSJEKTETS id → hierarki-filter (child_of via project_parent)
            areas: [],            // fagområde-treet fra Odoo prosjekt-hierarkiet (get_areas)
            areaOpen: {},         // {nr: true} = nedtrekk åpent i sidemenyen
            expanded: {},         // utvid-funksjon: {"model:id": true} = utvidet
            treeClosed: {},       // prosjekt-treet: {prosjektId: true} = forelderens barn foldet inn
            children: {},         // lazy-lastede barn: {"model:id": [rader]}
            myTasks: [],
            taskNoQuery: "",      // oppgavesøk: nummer (code)
            taskCols: this._loadTaskCols(),  // kolonnevalg Mine oppgaver (huskes per nettleser)
            taskColsEdit: false,  // kolonnevelger åpen
            taskSort: { key: "", dir: 1 },   // klikk på kolonneoverskrift = sortér
            taskTextQuery: "",    // oppgavesøk: fritekst
            taskStage: "",        // filter: valgt stadium ("" = alle)
            taskMile: "",         // filter: valgt milepæl ("" = alle)
            komm: [],
            kommPeriod: "uke",
            anchorDate: new Date().toISOString().slice(0, 10), // datovelger: referansedato for perioden
            kommQuery: "",
            kommDir: "alle",      // alle | mottatt | sendt (direction "sent from")
            kommSender: null,     // {id, name} – filter on a single sender
            dashboards: [],       // Odoo native dashboards/analyses (only the ones that exist)
            fiqFlater: [],        // selvregistrerte FIQ-modul-flater (get_fiq_flater) – nye moduler uten kode-endring her
            slotKey: false,       // flaten som står i sloten nå (false = forsiden). Rammen står uansett.
            slotMenyValg: false,  // valgt punkt i flatens EGEN undermeny (under hovedmenyen)
            // ── VENSTREMENYENS GRUNNSTRUKTUR (utkast 15, godkjent av Gjermund 20.07.2026) ──
            // Tre foldbare hovedpunkter: 0 INNBOKS · KR-MENYER · FAGOMRÅDER.
            // TREKKSPILL: åpner du én gruppe, lukkes forrige — MEN «0 INNBOKS» er unntatt.
            // Gjermunds begrunnelse: innboksen er stedet du tømmer FRA, så den skal kunne
            // stå åpen mens du jobber i et fagområde.
            // Default: Innboks åpen (den du tømmer fra) + Fagområder åpen (hovednavigasjonen).
            grpAapen: this._lastGrp(),
            har000: false,        // kryss-firma-innsyn (server-avgjort, fail-closed) — sendes til flater i sloten
            presence: [],         // «Til stede nå» – interne brukere + tilgjengelighets-status
            kal: { moter: [], aktiviteter: [], mnd: [] }, // Møter/aktiviteter-panelet (periode-styrt)
            selPerson: null,      // valgt person (toggle på Til stede-kort) — styrer kalender + komm
            kalMnd: new Date().toISOString().slice(0, 7), // vist måned i mini-kalenderen (YYYY-MM)
            selMote: false,       // valgt møte (rad) → «Åpne valgt møte»
            selAkt: null,         // valgt aktivitet (objekt) → «Åpne valgt aktivitet»
            aktFilter: "alle",    // aktivitets-filter: alle | skjul (uten forfalte) | kun (bare forfalte)
            aktGruppe: "",        // gruppering i panelet (som native): "" | type | element | modell | frist | status
            utsettDager: "",      // «Utsett til»: antall dager
            actions: {},          // {nøkkel: xmlid|false} – hvilke Odoo-handlinger som finnes (guardet)
            aiQuery: "",          // «Spør AI om hjelp»-feltet
            aiAnswer: "",         // svar fra Claude via fiq.ai
            verInstalled: "",     // installert modulversjon (DB — endres av «Oppgrader»)
            verFiles: "",         // fil-versjon på serveren (avvik → Oppgrader-knapp i brikken)
            upgrading: false,     // modul-oppgradering pågår (fra versjonsbrikken)
            canUpgrade: false,    // FIQ-admin el. Settings-admin → ser Oppgrader-knappen
            view: "oversikt",     // main content: oversikt (overview) | kommunikasjon (communication)
            rightView: "liste",   // right panel: liste | gantt (Liste default = safe first render)
            selected: null,       // {model,id,name} for inspektor-panel
            inspTab: "beskrivelse",
            selDet: { beskrivelse: "", logg: [], epost: [], dok: [] }, // Detaljer-panelet: ekte innhold pr fane
            progressShape: "bar", // lag 2: per-linje fremdrift – "bar" | "ring" (config-drevet)
            progressMetric: "timer", // STANDARD timer (ført ÷ estimert) | auto | deloppgaver | stadium
            hasHours: false,      // finnes allocated_hours/effective_hours (hr_timesheet)? → vis estimat-felt
            loading: true,
            refreshing: false,    // «⟳ Oppdater» – henter live data på nytt uten å blanke skjermen
            progLevel: "prosjekt", // Prosjektfremdrift-panel: "prosjekt" | "oppgave" (drill i valgt prosjekt)
            progTasks: [],        // oppgavene til valgt prosjekt (m/ fremdrift) når progLevel = "oppgave"
            progProjId: false,    // valgt prosjekt for oppgave-drill
            progSubs: false,      // vis deloppgaver i fremdrift-drillen (av = kun hovedoppgaver)
            progGroup: "ansvarlig", // grupper oppgave-fremdrift på: ansvarlig | mile (milepæl)
            progMiles: [],        // prosjektets milepæler (navn + frist) → ◆ i Gantt
            selDelt: null,        // Detaljer: deltagerliste (null = skjult)
            progProjName: "",
            puls: { idag: [], uke: [] },  // ⚡ AI KTRL-puls: dine frister i dag/denne uken
            staleGui: false,      // 🚨 lastet GUI-kode er ELDRE enn installert versjon → banner
            staleGui: false,      // 🚨 lastet GUI-kode er ELDRE enn installert versjon → banner
            recent: [],           // 📌 siste N prosjekter med aktivitet (hurtigknapper)
            oppgaver: [],         // 📋 pågående oppgaver (config-drevet, vist i AI-fanen)
            recentN: 5,           // 📌 antall (huskes per bruker, server-lagret)
            projLock: null,       // 🔒 låst gruppering {nr, id} — grunnfilter for Prosjektoversikt (server-lagret)
            vbox: null,           // 🪟 flyttbar detaljboks (Gantt-/listelinje): datoer/timer/%-fremdrift
            suggest: { open: false, name: "", description: "", category: "onske", sent: false, saving: false },  // 📮 forslagskasse
            aiStageNames: [],     // navn på AI-merkede stadier (fiq_ai_stage) – for velgeren
            stageHidden: {},      // {stadienavn: true} = skjult i oppgave-drillen
        });

        this.state.autoRefresh = this._loadAuto();
        this._frozenScroll = this._freezeRestore();

        onWillStart(async () => {
            await this.loadConfig();   // FIQ access/setup layer (per user, server-persisted)
            await this.loadData();
            await this._loadRecent();
            // 🧊 gjenopprett visnings-avhengig data etter frys
            if ((this.state.view === "airmm" || this.state.view === "prosjektkr") && !this.state.cp) { await this.loadCockpit(); }
            if (this.state.progLevel === "oppgave" && this.state.progProjId) {
                await this._loadProgTasks(this.state.progProjId);
            }
            this._applyAuto();
        });
        onMounted(() => {
            this._onHide = () => this._freezeSave();
            window.addEventListener("beforeunload", this._onHide);
            document.addEventListener("visibilitychange", this._onHide);
            if (this._frozenScroll) {
                setTimeout(() => {
                    const m = document.querySelector(".fiq_hm_main");
                    if (m) { m.scrollTop = this._frozenScroll.m || 0; }
                    window.scrollTo(0, this._frozenScroll.w || 0);
                }, 250);
            }
        });
        onWillDestroy(() => {
            clearInterval(this._autoTmr);
            this._freezeSave();
            window.removeEventListener("beforeunload", this._onHide);
            document.removeEventListener("visibilitychange", this._onHide);
        });
    }

    // 🧊 Frys/gjenopprett tilstanden (localStorage, nullstilles ved ny dag)
    _freezeSave() {
        try {
            const s = {};
            FREEZE_KEYS.forEach((k) => { s[k] = this.state[k]; });
            const m = document.querySelector(".fiq_hm_main");
            localStorage.setItem("fiq_hm_frozen", JSON.stringify({
                d: new Date().toISOString().slice(0, 10), s,
                scroll: { m: m ? m.scrollTop : 0, w: window.scrollY || 0 },
            }));
        } catch (e) { /* best-effort */ }
    }

    _freezeRestore() {
        try {
            const raw = JSON.parse(localStorage.getItem("fiq_hm_frozen") || "null");
            if (!raw || raw.d !== new Date().toISOString().slice(0, 10)) { return null; }
            FREEZE_KEYS.forEach((k) => {
                if (raw.s && raw.s[k] !== undefined && raw.s[k] !== null) { this.state[k] = raw.s[k]; }
            });
            return raw.scroll || null;
        } catch (e) { return null; }
    }

    // 📌 Serialisering av widget_order: "blokker|nav:punkter|lock:nr:id" (bakoverkompatibelt)
    _orderString() {
        const nav = this.state.navOrder.length ? "|nav:" + this.state.navOrder.join(",") : "";
        const lock = this.state.projLock
            ? "|lock:" + this.state.projLock.nr + ":" + (this.state.projLock.id || "") : "";
        const rec = "|recent:" + (this.state.recentN || 5);
        return this.state.blockOrder.join(",") + nav + lock + rec;
    }

    // 🔒 Lås prosjektvisningen til valgt gruppering — alle filtre virker innenfor (server-lagret)
    async toggleProjLock() {
        if (!this.state.projLock && !this.state.projArea) {
            this.notification.add(_t("Choose a subject area first, then lock."), { type: "info" });
            return;
        }
        this.state.projLock = this.state.projLock
            ? null : { nr: this.state.projArea, id: this.state.projAreaId || false };
        try {
            await this.orm.call("fiq.gui.control.config", "set_widget_order", [this._orderString()]);
        } catch (e) { /* låsen gjelder uansett i denne økten */ }
        await this._loadRecent();
    }

    // 📌 Siste N prosjekter med aktivitet — hurtigknapper (N i Innstillinger)
    async _loadRecent() {
        try {
            const root = this.state.projLock ? this.state.projLock.id : false;
            this.state.recent = await this.orm.call("fiq.gui.control.config", "get_recent_projects",
                [this.state.recentN || 5, root || false]);
        } catch (e) { this.state.recent = []; }
    }

    async setRecentN(v) {
        this.state.recentN = Math.max(1, Math.min(parseInt(v, 10) || 5, 12));
        try {
            await this.orm.call("fiq.gui.control.config", "set_widget_order", [this._orderString()]);
        } catch (e) { /* gjelder uansett i denne økten */ }
        await this._loadRecent();
    }

    async openRecent(r) {
        this.state.view = "oversikt";
        this.state.selected = { model: "project.project", id: r.id, name: r.name };
        this.state.progProjId = r.id;
        this.state.progProjName = r.name || "";
        await this._loadProgTasks(r.id);
        this.state.progLevel = "oppgave";
    }

    // 📮 Forslagskasse (rød postkasse): ønsker/forbedringer til løsningen
    toggleSuggest() {
        this.state.suggest.open = !this.state.suggest.open;
        if (this.state.suggest.open) { this.state.suggest.sent = false; }
    }

    async submitSuggestion() {
        const sg = this.state.suggest;
        const name = (sg.name || "").trim();
        if (!name || sg.saving) { return; }
        sg.saving = true;
        try {
            await this.orm.call("fiq.gui.suggestion", "submit", [name, sg.description, sg.category]);
            sg.sent = true;
            sg.name = ""; sg.description = ""; sg.category = "onske";
        } catch (e) {
            this.notification.add(_t("Kunne ikke sende forslaget — ") + this._errMsg(e), { type: "danger" });
        }
        sg.saving = false;
    }

    // 🪟 Flyttbar detaljboks: klikk på Gantt-/listelinje → sett variabler
    oppgSym(st) {
        return { ferdig: "✅", pagar: "⏳", apen: "⬜", venter: "⌛", parkert: "💤" }[st] || "⬜";
    }

    openVarBox(row, forceTask) {
        const task = forceTask || this.state.progLevel === "oppgave";
        this.state.vbox = {
            model: task ? "project.task" : "project.project",
            task, id: row.id, name: row.name, no: row.no || "",
            start: row.start || "", end: row.end || "",
            est: row.estH || 0, logged: row.logH || 0,
            manual: 0, mode: "av", x: 260, y: 160, saving: false,
        };
        if (task) { this._vboxLoad(row.id); }
    }

    async _vboxLoad(id) {
        try {
            const r = await this.orm.read("project.task", [id],
                ["fiq_manual_pct", "fiq_pct_mode", "allocated_hours", "effective_hours",
                 "planned_date_begin", "date_deadline"]);
            if (r.length && this.state.vbox && this.state.vbox.id === id) {
                Object.assign(this.state.vbox, {
                    manual: r[0].fiq_manual_pct || 0, mode: r[0].fiq_pct_mode || "av",
                    est: r[0].allocated_hours || 0, logged: r[0].effective_hours || 0,
                    start: this.state.vbox.start || String(r[0].planned_date_begin || "").slice(0, 10),
                    end: this.state.vbox.end || String(r[0].date_deadline || "").slice(0, 10),
                });
            }
        } catch (e) { /* feltene kommer med modul-oppgraderingen */ }
    }

    vboxDragStart(ev) {
        const v = this.state.vbox;
        if (!v || ev.target.tagName === "BUTTON") { return; }
        const dx = ev.clientX - v.x, dy = ev.clientY - v.y;
        const move = (e) => { v.x = e.clientX - dx; v.y = e.clientY - dy; };
        const up = () => {
            window.removeEventListener("pointermove", move);
            window.removeEventListener("pointerup", up);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
    }

    async saveVarBox() {
        const v = this.state.vbox;
        if (!v || v.saving) { return; }
        v.saving = true;
        const num = (x) => parseFloat(String(x === undefined || x === null ? "" : x).replace(",", ".")) || 0;
        try {
            if (v.task) {
                await this.orm.write("project.task", [v.id], {
                    planned_date_begin: v.start || false,
                    date_deadline: v.end || false,
                    allocated_hours: num(v.est),
                    fiq_manual_pct: Math.max(0, Math.min(100, num(v.manual))),
                    fiq_pct_mode: v.mode || "av",
                });
            } else {
                await this.orm.write("project.project", [v.id], {
                    date_start: v.start || false, date: v.end || false,
                });
            }
        } catch (e) {
            v.saving = false;
            this.notification.add(_t("Could not save — ") + this._errMsg(e), { type: "danger" });
            return;
        }
        this.state.vbox = null;
        await this.refresh();
    }

    // Auto-oppdatering: hent live data automatisk (intervall config-drevet, valg huskes)
    _loadAuto() {
        try { return localStorage.getItem("fiq_hm_auto") === "1"; } catch (e) { return false; }
    }

    _applyAuto() {
        clearInterval(this._autoTmr);
        if (this.state.autoRefresh) {
            this._autoTmr = setInterval(() => this.refresh(), (this._autoMin || 5) * 60000);
        }
    }

    toggleAuto() {
        this.state.autoRefresh = !this.state.autoRefresh;
        try { localStorage.setItem("fiq_hm_auto", this.state.autoRefresh ? "1" : "0"); } catch (e) {}
        this._applyAuto();
    }

    get autoMin() {
        return this._autoMin || 5;
    }

    async loadConfig() {
        try {
            const cfg = await this.orm.call("fiq.gui.control.config", "get_my_config", []);
            this.state.show = cfg.show;
            this.state.level = cfg.level;
            this.state.isAdmin = cfg.is_admin;
            this.state.companyName = cfg.company_name || "";
            this.state.companies = cfg.companies || [];
            this.state.companyId = cfg.company_id || false;
            // 000-rettigheten avgjøres SERVER-SIDE (har_000_rettighet(), fail-closed) og
            // sendes videre til flater som står i sloten — samme kilde som skallet bruker.
            // Klienten kan aldri utvide den; den bare formidler et svar den har fått.
            // 🛑 Normaltilstand er FALSE: gruppa har i dag 0 medlemmer (AI PK 19.07).
            // Bygg for begge tilstander — ikke anta at den er tildelt.
            this.state.har000 = !!cfg.har_000;
            if (cfg.accent) this.state.accent = cfg.accent;
            if (cfg.logo) this.state.logo = cfg.logo;
            if (cfg.progress_shape) this.state.progressShape = cfg.progress_shape;
            if (cfg.progress_metric) this.state.progressMetric = cfg.progress_metric;
            this.state.verInstalled = cfg.version_installed || "";
            // 🚨 fanen kjører gammel GUI-kode (typisk «… is not a function»-feil)
            this.state.staleGui = !!(cfg.version_installed && cfg.version_installed !== GUI_BUILD);
            // 🚨 fanen kjører gammel GUI-kode (typisk «… is not a function»-feil)
            this.state.staleGui = !!(cfg.version_installed && cfg.version_installed !== GUI_BUILD);
            this.state.verFiles = cfg.version_files || "";
            this._autoMin = cfg.auto_refresh_min || 5;
            this.state.canUpgrade = !!cfg.can_upgrade;
            this.state.spUrls = cfg.sp_urls || {};
            this.state.aiCockpitUrl = cfg.ai_cockpit_url || "";
            this.state.oppgaver = cfg.pagaende_oppgaver || [];
            // 📌 Rekkefølger: «blokker|nav:menypunkter» i samme felt (bakoverkompatibelt)
            const deler = (cfg.widget_order || "").split("|");
            const saved = (deler[0] || "").split(",").filter(Boolean);
            const def = ["activity", "quick", "projects", "dash", "chart"];
            this.state.blockOrder = saved.filter((k) => def.includes(k))
                .concat(def.filter((k) => !saved.includes(k)));
            const navDel = deler.find((d) => d.startsWith("nav:")) || "";
            this.state.navOrder = navDel.replace("nav:", "").split(",").filter(Boolean);
            const lockDel = deler.find((d) => d.startsWith("lock:")) || "";
            if (lockDel) {
                const [lnr, lid] = lockDel.replace("lock:", "").split(":");
                this.state.projLock = lnr ? { nr: lnr, id: parseInt(lid, 10) || false } : null;
            }
            const recDel = deler.find((d) => d.startsWith("recent:")) || "";
            if (recDel) { this.state.recentN = parseInt(recDel.replace("recent:", ""), 10) || 5; }
            // 🔒 låst gruppering = grunnfilter (med mindre frossen tilstand alt har valgt noe)
            if (this.state.projLock && !this.state.projArea) {
                this.state.projArea = this.state.projLock.nr;
                this.state.projAreaId = this.state.projLock.id || false;
            }
        } catch (e) {
            // keep defaults (everything visible) if the model is not ready
        }
    }

    async _read(model, domain, fields, opts) {
        // Defensive read: falls back without optional fields if they do not exist in the customer DB
        try {
            return await this.orm.searchRead(model, domain, fields, opts);
        } catch (e) {
            const base = fields.filter((f) => !["sequence_code", "code"].includes(f));
            try { return await this.orm.searchRead(model, domain, base, opts); } catch (e2) { return []; }
        }
    }

    async _optFields(model, candidates) {
        // Only the candidate fields that actually exist on the model (portable across
        // customer DBs). fields_get never raises for missing fields -> no server traceback.
        try {
            const meta = await this.orm.call(model, "fields_get", [candidates, ["type"]]);
            return candidates.filter((f) => f in meta);
        } catch (e) {
            return [];
        }
    }

    async _loadProjects(query) {
        // Project overview / project search. Empty query = 8 most recent active projects;
        // a query searches ALL active projects by name and (if present) sequence_code.
        const pOpt = this._pOpt || [];
        const q = (query || "").trim();
        const area = this.state.projArea;
        // Implisitt AND-liste. Fagområde-filter = HIERARKI (child_of områdets prosjekt via
        // project_parent) — fanger underprosjekter og navn uten nummer. Navn-prefiks = fallback.
        let domain = [["active", "=", true]];
        if (this.state.projAreaId) { domain.push(["id", "child_of", this.state.projAreaId]); }
        else if (area) { domain.push(["name", "=ilike", area + "%"]); }
        // Periode-filter: planlagt periode overlapper vinduet; prosjekter UTEN datoer vises alltid
        const win = this._periodWindow();
        if (win && !isNaN(win.s.getTime()) && !isNaN(win.e.getTime())) {
            const iso = (d) => d.toISOString().slice(0, 10);
            domain.push("|", "|", ["date_start", "=", false], ["date", "=", false],
                "&", ["date_start", "<", iso(win.e)], ["date", ">=", iso(win.s)]);
        }
        // To-felts søk: nummer (sequence_code, fallback navn-prefiks) + fritekst (navn)
        const no = (this.state.projNoQuery || "").trim();
        if (no) {
            domain.push([pOpt.includes("sequence_code") ? "sequence_code" : "name", "ilike", no]);
        }
        if (q) {
            const flds = ["name", ...(pOpt.includes("sequence_code") ? ["sequence_code"] : [])];
            const ors = [];
            for (let i = 0; i < flds.length - 1; i++) ors.push("|");
            flds.forEach((f) => ors.push([f, "ilike", q]));
            domain = domain.concat(ors);
        }
        const precs = await this._read("project.project", domain,
            ["name", "task_count", "date_start", "date", ...pOpt], { limit: (q || no || area) ? 40 : 8, order: "create_date desc" });
        const rows = precs.map((p) => ({
            id: p.id, no: p.sequence_code || "", name: p.name,
            taskCount: p.task_count || 0,
            start: p.date_start || false, end: p.date || false,
            hasKids: !!(p.child_ids && p.child_ids.length),
            parentId: (p.parent_id && p.parent_id[0]) || null,
            depth: 0, kidsLoaded: [], hasLoadedKids: false,
            progress: 0, status: _t("In progress"),
        }));
        // TRE utvidet som standard: barn nestes under forelderen (aldri dobbel visning
        // som egen topprad). Barn uten lastet forelder forblir toppnivå.
        const byId = {};
        rows.forEach((r) => { byId[r.id] = r; });
        const roots = [];
        rows.forEach((r) => {
            if (r.parentId && byId[r.parentId]) { byId[r.parentId].kidsLoaded.push(r); }
            else { roots.push(r); }
        });
        const byName = (x, y) => (x.name || "").localeCompare(y.name || "");
        if (q || area) { roots.sort(byName); }
        const flat = [];
        const walk = (r, d) => {
            r.depth = d;
            r.hasLoadedKids = r.kidsLoaded.length > 0;
            flat.push(r);
            r.kidsLoaded.sort(byName).forEach((k) => walk(k, d + 1));
        };
        roots.forEach((r) => walk(r, 0));
        this.state.projects = flat;
        // Ekte, config-drevet fremdrift per prosjekt (lag 2) – erstatter tidligere placeholder
        await this._fillProgress("project.project", this.state.projects);
    }

    async _fillProgress(model, rows) {
        // Config-drevet per-linje fremdrift (0-100). Defensiv: 0 ved feil (portabelt).
        const ids = rows.map((r) => r.id);
        if (!ids.length) { return; }
        let map = {};
        try {
            map = await this.orm.call("fiq.gui.control.config", "get_progress",
                [model, ids, this.state.progressMetric]);
        } catch (e) { return; }
        rows.forEach((r) => {
            const v = map[r.id] || {};
            const pct = (typeof v === "number") ? v : (v.pct || 0);
            r.progress = Math.max(0, Math.min(100, Math.round(pct)));
            r.estH = (v && typeof v === "object" && v.est) || 0;   // estimerte (antatte) timer
            r.logH = (v && typeof v === "object" && v.logged) || 0; // førte timer
        });
    }

    // Drill: last oppgavene til ETT prosjekt (m/ config-drevet fremdrift) for oppgave-nivå
    async _loadProgTasks(pid) {
        const tOpt = await this._optFields("project.task", ["code", "milestone_id"]);
        const dom = [["project_id", "=", pid]];
        if (!this.state.progSubs) { dom.push(["parent_id", "=", false]); }  // kun hovedoppgaver
        const recs = await this._read("project.task", dom,
            ["name", "date_deadline", "planned_date_begin", "stage_id", "user_ids", ...tOpt],
            { limit: 80, order: "planned_date_begin asc, id asc" });
        // Prosjektets milepæler (◆ i Gantt + gruppering) — guardet
        try {
            this.state.progMiles = await this._read("project.milestone",
                [["project_id", "=", pid]], ["name", "deadline"], { limit: 40, order: "deadline asc" });
        } catch (e) { this.state.progMiles = []; }
        // Ansvarlig-navn (user_ids gir kun id-er) — batch-oppslag
        const uidSet = new Set();
        recs.forEach((t) => (t.user_ids || []).forEach((u) => uidSet.add(u)));
        const uname = {};
        if (uidSet.size) {
            try {
                const us = await this._read("res.users", [["id", "in", [...uidSet]]], ["name"], {});
                us.forEach((u) => { uname[u.id] = u.name; });
            } catch (e) {}
        }
        const rows = recs.map((t) => {
            const uids = t.user_ids || [];
            const first = uids.length ? (uname[uids[0]] || "") : "";
            return {
                id: t.id, no: t.code || "", name: t.name,
                start: (t.planned_date_begin || "").slice(0, 10) || false,
                end: (t.date_deadline || "").slice(0, 10) || false,
                stage: t.stage_id ? t.stage_id[1] : "",
                mile: t.milestone_id ? t.milestone_id[1] : "",
                ansvarlig: first + (uids.length > 1 ? " +" + (uids.length - 1) : ""),
                progress: 0,
            };
        });
        await this._fillProgress("project.task", rows);
        this.state.progTasks = rows;
    }

    // «▸ Oppgaver»: vis oppgavefremdrift. Bruker valgt prosjekt, ellers første i lista
    // (så knappen alltid gjør noe – krever ikke at man har valgt et prosjekt først).
    async showTasksSelected() {
        const s = this.state.selected;
        const proj = (s && s.model === "project.project")
            ? s
            : (this.state.projects.length ? this.state.projects[0] : null);
        if (!proj) { return; }
        this.state.progProjId = proj.id;
        this.state.progProjName = proj.name || "";
        await this._loadProgTasks(proj.id);
        this.state.progLevel = "oppgave";
    }

    // «◂ Prosjekter»: tilbake til prosjektfremdrift
    backToProjects() {
        this.state.progLevel = "prosjekt";
    }

    // Deloppgaver av/på i fremdrift-drillen (liste + Gantt)
    async toggleProgSubs() {
        this.state.progSubs = !this.state.progSubs;
        if (this.state.progProjId) { await this._loadProgTasks(this.state.progProjId); }
    }

    // «👥 Deltagere» i Detaljer: PL + oppgave-ansvarlige (rolle-innehavere når rollemodellen er klar)
    async showDeltagere() {
        if (this.state.selDelt) { this.state.selDelt = null; return; }
        const s = this.state.selected;
        if (!s) { return; }
        try {
            this.state.selDelt = await this.orm.call("fiq.gui.control.config", "get_deltagere", [s.model, s.id]) || [];
        } catch (e) { this.state.selDelt = []; }
    }

    // Klikk på et PROSJEKT (oversikt ELLER fremdrift-liste): (1) vis i Detaljer,
    // (2) DRILL fremdriften inn i prosjektets oppgaver. Gir tydelig fremdrift-respons.
    async pickProject(pid, name) {
        this.selectEl("project.project", pid, name);   // Detaljer (async – kjører i bakgrunnen)
        this.state.progProjId = pid;
        this.state.progProjName = name || "";
        this.state.progLevel = "oppgave";
        await this._loadProgTasks(pid);
    }

    // Klikk på en rad i fremdrift-panelet: prosjekt-nivå -> drill; oppgave-nivå -> velg oppgave.
    pickRow(row) {
        if (row.isHead) { return; }
        if (this.state.progLevel === "oppgave") {
            this.selectEl("project.task", row.id, row.name);
        } else {
            this.pickProject(row.id, row.name);
        }
    }

    // Kilden Prosjektfremdrift-panelet itererer over (prosjekter ELLER valgt prosjekts
    // oppgaver). På oppgave-nivå filtreres skjulte stadier bort OG det grupperes på
    // ANSVARLIG (Gjermund 2026-07-03) — prosjekt-nivået grupperes IKKE.
    get progRows() {
        if (this.state.progLevel !== "oppgave") { return this.state.projects; }
        const hidden = this.state.stageHidden;
        const rows = this.state.progTasks.filter((t) => !hidden[t.stage || ""]);
        const byMile = this.state.progGroup === "mile";
        const icon = byMile ? "🏁" : "👤";
        const groups = {}, order = [];
        rows.forEach((t) => {
            const k = byMile ? (t.mile || _t("(no milestone)")) : (t.ansvarlig || _t("(no responsible)"));
            if (!(k in groups)) { groups[k] = []; order.push(k); }
            groups[k].push(t);
        });
        order.sort((a, b) => a.localeCompare(b));
        const out = [];
        order.forEach((k) => {
            out.push({ isHead: true, id: "h:" + k, name: k, count: groups[k].length, icon });
            out.push(...groups[k]);
        });
        return out;
    }

    setProgGroup(g) {
        this.state.progGroup = g;
    }

    // Tydelige stadium-brikker: farge etter type (AI = lilla, utført = grønn, pågående = blå)
    stageCls(name) {
        const n = (name || "").toLowerCase();
        if ((this.state.aiStageNames || []).includes(name)) { return "st_ai"; }
        if (/utf|ferdig|done|fullf/.test(n)) { return "st_done"; }
        if (/pågå|progress|arbeid/.test(n)) { return "st_prog"; }
        return "st_def";
    }

    // Milepæl-markører (◆) i Gantt-vinduet
    get ganttMiles() {
        if (this.state.progLevel !== "oppgave") { return []; }
        const { start, end } = this.ganttWindow;
        const span = (end - start) || 1;
        return (this.state.progMiles || []).map((m) => {
            if (!m.deadline) { return null; }
            const t = new Date(m.deadline).getTime();
            const left = ((t - start) / span) * 100;
            if (left < 0 || left > 100) { return null; }
            return { name: m.name, deadline: m.deadline, leftPct: left };
        }).filter(Boolean);
    }

    get progModel() {
        return this.state.progLevel === "oppgave" ? "project.task" : "project.project";
    }

    // Stadie-velger: distinkte stadier i det valgte prosjektets oppgaver, med AI-flagg,
    // antall og av/på. «Velg hvilke stadier fra prosjektene som skal vises.»
    get progStageChips() {
        const ai = new Set(this.state.aiStageNames || []);
        const hidden = this.state.stageHidden;
        const order = [], map = {};
        this.state.progTasks.forEach((t) => {
            const nm = t.stage || _t("(no stage)");
            if (!(nm in map)) { map[nm] = { name: nm, ai: ai.has(nm), hidden: !!hidden[nm], count: 0 }; order.push(nm); }
            map[nm].count += 1;
        });
        // AI-stadier først, så resten
        return order.map((n) => map[n]).sort((a, b) => (b.ai - a.ai));
    }

    toggleStage(name) {
        this.state.stageHidden[name] = !this.state.stageHidden[name];
    }

    // Mine oppgaver: server-søk (nummer + fritekst) + stadium-/milepæl-chips
    async _loadMyTasks() {
        const tOpt = this._tOpt || [];
        const no = (this.state.taskNoQuery || "").trim();
        const txt = (this.state.taskTextQuery || "").trim();
        const today = new Date().toISOString().slice(0, 10);
        const domain = [["user_ids", "in", [user.userId]]];
        if (no) { domain.push([tOpt.includes("code") ? "code" : "name", "ilike", no]); }
        if (txt) { domain.push(["name", "ilike", txt]); }
        const recs = await this._read("project.task", domain,
            ["name", "project_id", "date_deadline", "planned_date_begin", "child_ids", "stage_id", ...tOpt],
            { limit: (no || txt) ? 30 : 10, order: "date_deadline asc" });
        const rows = recs.map((t) => ({
            id: t.id, no: t.code || "", name: t.name,
            project: t.project_id ? t.project_id[1] : "",
            stage: t.stage_id ? t.stage_id[1] : "",
            mile: t.milestone_id ? t.milestone_id[1] : "",
            deadline: t.date_deadline || "",
            pfrom: (t.planned_date_begin || "").slice(0, 10),
            pto: (t.date_deadline || "").slice(0, 10),
            overdue: !!(t.date_deadline && t.date_deadline < today),
            hasKids: !!(t.child_ids && t.child_ids.length),
            progress: 0,
        }));
        await this._fillProgress("project.task", rows);
        this.state.myTasks = rows;
    }

    setTaskNoQuery(v) {
        this.state.taskNoQuery = v;
        clearTimeout(this._taskTmr);
        this._taskTmr = setTimeout(() => this._loadMyTasks(), 250);
    }

    setTaskTextQuery(v) {
        this.state.taskTextQuery = v;
        clearTimeout(this._taskTmr);
        this._taskTmr = setTimeout(() => this._loadMyTasks(), 250);
    }

    // Filter-chips for Mine oppgaver: stadium + milepæl (fra de lastede oppgavene)
    get taskStageChips() {
        const seen = [], map = {};
        this.state.myTasks.forEach((t) => {
            const nm = t.stage || "";
            if (!nm) { return; }
            if (!(nm in map)) { map[nm] = 0; seen.push(nm); }
            map[nm] += 1;
        });
        return seen.map((n) => ({ name: n, count: map[n] }));
    }

    get taskMileChips() {
        const seen = [], map = {};
        this.state.myTasks.forEach((t) => {
            const nm = t.mile || "";
            if (!nm) { return; }
            if (!(nm in map)) { map[nm] = 0; seen.push(nm); }
            map[nm] += 1;
        });
        return seen.map((n) => ({ name: n, count: map[n] }));
    }

    get filteredMyTasks() {
        const st = this.state.taskStage, mi = this.state.taskMile;
        const rows = this.state.myTasks.filter((t) => (!st || t.stage === st) && (!mi || t.mile === mi));
        const s = this.state.taskSort;
        if (s.key) {
            const k = s.key, d = s.dir;
            rows.sort((a, b) => {
                if (k === "estH" || k === "progress") { return ((+a[k] || 0) - (+b[k] || 0)) * d; }
                return String(a[k] || "").localeCompare(String(b[k] || ""), "nb", { numeric: true }) * d;
            });
        }
        return rows;
    }

    // ---- Kolonnevalg + sortering (Mine oppgaver) — huskes per nettleser ----
    _loadTaskCols() {
        const def = { project: true, hours: true, status: true, progress: true };
        try {
            const raw = JSON.parse(localStorage.getItem("fiq_hm_taskcols") || "null");
            return raw && typeof raw === "object" ? Object.assign(def, raw) : def;
        } catch (e) { return def; }
    }

    toggleTaskCol(key) {
        this.state.taskCols[key] = !this.state.taskCols[key];
        try { localStorage.setItem("fiq_hm_taskcols", JSON.stringify(this.state.taskCols)); } catch (e) { /* ok */ }
    }

    // Grid-definisjonen (CSS-variabel) følger valgte kolonner → header og rader i flukt
    get taskColsVar() {
        const c = this.state.taskCols;
        let v = "64px minmax(0, 1fr)";
        if (c.project) { v += " minmax(120px, 170px)"; }
        if (c.hours) { v += " 56px"; }
        if (c.status) { v += " 88px"; }
        if (c.progress) { v += " 100px"; }
        return v;
    }

    setTaskSort(key) {
        const s = this.state.taskSort;
        if (s.key === key) {
            if (s.dir === 1) { s.dir = -1; } else { this.state.taskSort = { key: "", dir: 1 }; }
        } else {
            this.state.taskSort = { key, dir: 1 };
        }
    }

    sortInd(key) {
        const s = this.state.taskSort;
        return s.key === key ? (s.dir > 0 ? " ▲" : " ▼") : "";
    }

    toggleTaskStage(name) {
        this.state.taskStage = (this.state.taskStage === name) ? "" : name;
    }

    toggleTaskMile(name) {
        this.state.taskMile = (this.state.taskMile === name) ? "" : name;
    }

    // Project search fields (right above the project overview) - debounced server search
    setProjQuery(v) {
        this.state.projQuery = v;
        clearTimeout(this._projTmr);
        this._projTmr = setTimeout(() => this._loadProjects(v), 200);
    }

    setProjNoQuery(v) {
        this.state.projNoQuery = v;
        clearTimeout(this._projTmr);
        this._projTmr = setTimeout(() => this._loadProjects(this.state.projQuery), 200);
    }

    // Fagområde-filter i prosjektoversikten. Klikk = hierarki-filter (child_of områdets
    // prosjekt-id); klikk på aktivt filter igjen = tilbake til alle.
    setProjArea(nr, id) {
        if (!nr && this.state.projLock) { nr = this.state.projLock.nr; id = this.state.projLock.id; }
        if (this.state.projArea === nr) {
            this.state.projArea = "";
            this.state.projAreaId = false;
        } else {
            this.state.projArea = nr;
            this.state.projAreaId = id || false;
        }
        this._loadProjects(this.state.projQuery);
    }

    // Sidemeny: fagområde-tre (fra prosjekt-hierarkiet); fallback = statisk liste.
    get sideAreas() {
        if (this.state.areas.length) { return this.state.areas; }
        return this.fagomrader.map((o) => ({ nr: o.nr, name: o.navn, color: o.farge, dk: false, subs: [] }));
    }

    // Nedtrekk i sidemenyen (åpne/lukk underområder for et fagområde)
    toggleArea(nr) {
        this.state.areaOpen[nr] = !this.state.areaOpen[nr];
    }

    // AI-cockpiten (Artifact, interim): åpnes fra AI Kontrollrom-flaten
    openCockpit() {
        if (this.state.aiCockpitUrl) { window.open(this.state.aiCockpitUrl, "_blank"); }
    }

    // Endre cockpit-adressen uten ny modulversjon (config-drevet, admin-gated server-side)
    toggleCockpitEdit() {
        this.state.cockpitUrlDraft = this.state.aiCockpitUrl || "";
        this.state.cockpitEdit = !this.state.cockpitEdit;
    }

    async saveCockpitUrl() {
        try {
            const url = await this.orm.call(
                "fiq.gui.control.config", "set_ai_cockpit_url",
                [this.state.cockpitUrlDraft || ""]);
            this.state.aiCockpitUrl = url || "";
            this.state.cockpitEdit = false;
            this.notification.add(_t("The cockpit address has been saved."), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Could not save — ") + this._errMsg(e), { type: "danger" });
        }
    }

    // SP-lenke for et fagområde (config-drevet per firma; eksakt nr vinner over toppnr)
    spUrl(nr) {
        const u = this.state.spUrls || {};
        return u[nr] || u[(nr || "").split(".")[0]] || "";
    }

    openSp(nr) {
        const url = this.spUrl(nr);
        if (url) { window.open(url, "_blank"); }
    }

    // Nedtrekksliste under SP-flisen: velg underområde («» = hele området)
    pickAreaSub(a, v) {
        if (!v) { this.pickArea(a.nr, a.id); return; }
        const s = (a.subs || []).find((x) => String(x.id) === String(v));
        if (s) { this.pickArea(s.nr, s.id); }
    }

    // Klikk på område/underområde i sidemenyen: gå til oversikten + hierarki-filtrer
    pickArea(nr, id) {
        this.state.view = "oversikt";
        if (this.state.projArea !== nr) {
            this.state.projArea = nr;
            this.state.projAreaId = id || false;
            this._loadProjects(this.state.projQuery);
        }
    }

    // Undergruppe-nedtrekk (variant C): velg underområde, eller «alle» = tilbake til toppområdet
    get isSubActive() {
        return this.chipSubs.some((s) => s.id === this.state.projAreaId);
    }

    pickSub(v) {
        if (v === "") {
            const par = this.sideAreas.find((x) => x.nr === this.chipParent);
            if (par) {
                this.state.projArea = par.nr;
                this.state.projAreaId = par.id || false;
                this._loadProjects(this.state.projQuery);
            }
            return;
        }
        const s = this.chipSubs.find((x) => String(x.id) === String(v));
        if (s) {
            this.state.projArea = s.nr;
            this.state.projAreaId = s.id || false;
            this._loadProjects(this.state.projQuery);
        }
    }

    // Aktivt toppområde for filter-chipsene ("2.20" → "2")
    get chipParent() {
        const a = this.state.projArea;
        return a && a.includes(".") ? a.split(".")[0] : a;
    }

    // Undergruppe-chips (rad 2) for det aktive toppområdet
    get chipSubs() {
        const p = this.chipParent;
        if (!p) { return []; }
        const area = this.sideAreas.find((x) => x.nr === p);
        return (area && area.subs) || [];
    }

    // Utvid/kollaps en rad → viser underprosjekter (PRJ) eller deloppgaver (Oppg).
    // Lazy-laster barn første gang. key = "model:id".
    async toggleExpand(model, id) {
        const key = model + ":" + id;
        this.state.expanded[key] = !this.state.expanded[key];
        if (this.state.expanded[key] && !this.state.children[key]) {
            try { this.state.children[key] = await this.orm.call("fiq.gui.control.config", "get_children", [model, id]); }
            catch (e) { this.state.children[key] = []; }
        }
    }
    isExp(model, id) { return !!this.state.expanded[model + ":" + id]; }
    kids(model, id) { return this.state.children[model + ":" + id] || []; }

    // Prosjekt-treet: fold-pilen sitter på FORELDEREN; lukkede foreldres barn skjules
    toggleTree(id) {
        this.state.treeClosed[id] = !this.state.treeClosed[id];
    }

    get visibleProjects() {
        const out = [];
        let skipDepth = null;
        for (const r of this.state.projects) {
            if (skipDepth !== null && r.depth > skipDepth) { continue; }
            skipDepth = null;
            out.push(r);
            if (r.hasLoadedKids && this.state.treeClosed[r.id]) { skipDepth = r.depth; }
        }
        return out;
    }

    // Klikk pa en kollega i «Til stede na» -> apne Discuss-chat (DM) med personen.
    // Bruker mail.store hvis tilgjengelig (mail er dep via project); ellers stille no-op.
    openColleagueChat(pr) {
        // Åpne Discuss-DM uten å forstyrre kontrollrommets render (feil svelges).
        try {
            const store = this.env.services["mail.store"];
            if (store && pr.partner_id) {
                store.openChat({ partnerId: pr.partner_id });
            }
        } catch (e) { /* mail ikke klar – ignorer */ }
    }

    async loadData() {
        let active = 0, openTasks = 0;
        try { active = await this.orm.searchCount("project.project", [["active", "=", true]]); } catch (e) {}

        // Projects (overview + search). Field-detect sequence_code for portability.
        this._pOpt = await this._optFields("project.project", ["sequence_code", "child_ids", "parent_id"]);
        await this._loadProjects("");

        // My open tasks with their real number (code = "T0001") + deadline warning
        const today = new Date().toISOString().slice(0, 10);
        // Har DB-en time-feltene (hr_timesheet)? → styrer om estimat-feltet vises
        this.state.hasHours = (await this._optFields("project.task", ["allocated_hours", "effective_hours"])).length === 2;
        // AI-merkede stadier (for stadie-velgeren i oppgave-drillen)
        try { this.state.aiStageNames = await this.orm.call("fiq.gui.control.config", "get_ai_stages", []); }
        catch (e) { this.state.aiStageNames = []; }
        this._tOpt = await this._optFields("project.task", ["code", "milestone_id"]);
        await this._loadMyTasks();
        const myTasks = this.state.myTasks;
        try { openTasks = await this.orm.searchCount("project.task", [["user_ids", "in", [user.userId]]]); } catch (e) {}

        // ⚡ Kommunikasjon · salg · finans hentes SAMTIDIG.
        //
        // Målt 19.07.2026 mot fiqas Staging: serveren bruker 184 ms på ALLE kallene til
        // sammen (ingen enkeltmetode over 55 ms) — men de kjørte etter hverandre, og hvert
        // kall betaler sin egen nettverksrunde. Brukeren ventet på summen av rundturer,
        // ikke på serveren. Disse fire deler ingen data, så de kan gå parallelt.
        //
        // Promise.all avbryter ved første avvisning — derfor beholder hver gren sin egen
        // catch og returnerer en tom verdi. En base uten `account` skal gi tomme
        // finanstall, ikke en tom forside.
        const today0 = new Date().toISOString().slice(0, 10);
        const [komm, salg, finLev, finForsinket] = await Promise.all([
            this.orm.call("fiq.gui.control.config", "get_kommunikasjon", [this.state.kommPeriod])
                .catch(() => []),
            this.orm.searchCount("crm.lead", [["type", "=", "opportunity"], ["active", "=", true]])
                .catch(() => this.orm.searchCount("sale.order", [["state", "in", ["draft", "sent"]]])
                    .catch(() => 0)),
            this._read("account.move",
                [["move_type", "=", "in_invoice"], ["state", "=", "draft"]],
                ["name", "partner_id"], { limit: 25, order: "id desc" }).catch(() => []),
            this._read("account.move",
                [["move_type", "=", "out_invoice"], ["state", "=", "posted"],
                 ["payment_state", "in", ["not_paid", "partial"]], ["invoice_date_due", "<", today0]],
                ["name", "partner_id", "invoice_date_due"],
                { limit: 25, order: "invoice_date_due asc" }).catch(() => []),
        ]);
        this.state.finansLines = [
            ...finForsinket.map((m) => ({ text: (m.name || _t("Invoice")) + " · " + (m.partner_id ? m.partner_id[1] : "") + " (" + _t("past due") + " " + (m.invoice_date_due || "") + ")", model: "account.move", res_id: m.id })),
            ...finLev.map((m) => ({ text: (m.name || _t("Vendor bill")) + " · " + (m.partner_id ? m.partner_id[1] : "") + " (" + _t("for approval") + ")", model: "account.move", res_id: m.id })),
        ];

        // Category KPIs (report-up / management by exception): Kommunikasjon · Prosjekt · Salg · Finans · HMS/KS
        const received = komm.filter((k) => k.direction === "mottatt");
        const overdueN = myTasks.filter((t) => t.overdue).length;
        // SP-farge per boks (venstre-aksent, jf. fargekartet — samme familie som stolpemenyen)
        const KPI_FARGE = { komm: "#8b93a1", prosjekt: "#548235", salg: "#CC0000", finans: "#4472C4", hms: "#0070C0" };
        this.state.kpis = [
            { key: "komm", v: String(komm.length), l: _t("Communication"), sub: received.length + " " + _t("unanswered"), dot: received.length ? "red" : "green" },
            { key: "prosjekt", v: String(active), l: _t("Projects"), sub: overdueN + " " + _t("overdue"), dot: overdueN ? "amber" : "green" },
            { key: "salg", v: String(salg), l: _t("Sales"), sub: _t("ok"), dot: "green" },
            { key: "finans", v: String(finForsinket.length + finLev.length), l: _t("Finance"), sub: finForsinket.length + " " + _t("overdue") + " · " + finLev.length + " " + _t("for appr."), dot: finForsinket.length ? "red" : (finLev.length ? "amber" : "green") },
            { key: "hms", v: "—", l: _t("HSE/QA"), sub: _t("deviations"), dot: "grey" },
        ].map((k) => ({ ...k, farge: KPI_FARGE[k.key] || "#e3e5e9" }));
        if (!this.state.selectedKpi) {
            const red = this.state.kpis.find((k) => k.dot === "red");
            this.state.selectedKpi = red ? red.key : "komm";
        }

        // ⚡ Andre parallelle bolk: dashbord · flater · presence · kalender · fagområder ·
        // handlinger. Ingen av dem leser hverandres resultat, så de hentes samtidig.
        // Kalenderen henger på fordi den bare fyller state selv (_loadKalender).
        const [dashboards, fiqFlater, presence, raaAreas, actions] = await Promise.all([
            this.orm.call("fiq.gui.control.config", "get_dashboards", []).catch(() => []),
            this.orm.call("fiq.gui.control.config", "get_fiq_flater", []).catch(() => []),
            this.orm.call("fiq.gui.control.config", "get_presence", []).catch(() => []),
            this.orm.call("fiq.gui.control.config", "get_areas", []).catch(() => []),
            this.orm.call("fiq.gui.control.config", "get_actions", []).catch(() => ({})),
            this._loadKalender().catch(() => {}),
        ]);
        this.state.fiqFlater = fiqFlater;
        // Fagområde-treet får kanoniske farger her, ikke i kallet — spColor er ren
        // klient-logikk og skal ikke holde nettverket åpent.
        this.state.areas = (raaAreas || []).map((a) => ({
            ...a, ...spColor(a.nr),
            subs: (a.subs || []).map((s) => ({ ...s, ...spColor(s.nr) })),
        }));

        this.state.myTasks = myTasks;
        this.state.komm = komm;
        this.state.dashboards = dashboards;
        this.state.presence = presence;
        this.state.actions = actions;
        this.state.loading = false;
    }

    // Versjonsfelt ved Oppdater-knappen: «v6.17.0» (uten 19.0-prefiks). Avvik mellom
    // installert (DB) og filene på serveren → oransje varsel «trykk Oppgrader i Apper».
    get verVis() {
        const strip = (v) => (v || "").replace(/^\d+\.\d+\./, "");
        const inst = strip(this.state.verInstalled);
        const fil = strip(this.state.verFiles);
        if (!inst && !fil) { return null; }
        const avvik = fil && inst !== fil;
        return {
            text: "v" + (inst || "?"),
            avvik,
            title: avvik
                ? _t("The files on the server are v") + fil + _t(" — press 'Upgrade' on Control room in Apps")
                : _t("Installed version"),
        };
    }

    // Oppgrader modulen rett fra versjonsbrikken (admin) — laster siden på nytt etterpå
    async upgradeModule() {
        if (this.state.upgrading) { return; }
        this.state.upgrading = true;
        try {
            await this.orm.call("fiq.gui.control.config", "action_upgrade_module", []);
            window.location.reload();
        } catch (e) {
            this.state.upgrading = false;
            this.notification.add(_t("Upgrade failed — ") + this._errMsg(e), { type: "danger" });
        }
    }

    // Tidsbasert hilsen (norsk)
    get hilsen() {
        const h = new Date().getHours();
        if (h < 10) return _t("Good morning");
        if (h < 18) return _t("Good day");
        return _t("Good evening");
    }

    // Krever handling nå: sammendrag PER KATEGORI (styring ved unntak – rapporter opp,
    // ikke én linje per post). Rød prikk + fet kategori + kort tekst; klikk → kategori-flate.
    get handlingsposter() {
        const out = [];
        const received = this.state.komm.filter((k) => k.direction === "mottatt");
        if (received.length) {
            out.push({
                key: "kat-komm", kategori: _t("Communication"), type: "kommunikasjon",
                text: received.length + " " + _t("unanswered — awaiting reply"),
                view: "kommunikasjon",
            });
        }
        const overdue = this.state.myTasks.filter((t) => t.overdue);
        if (overdue.length) {
            out.push({
                key: "kat-prosjekt", kategori: _t("Projects"), type: "oppgave",
                text: overdue.length + " " + _t("overdue tasks"),
                model: "project.task", res_id: overdue[0].id,
            });
        }
        return out;
    }

    // Klikk på en «krever handling»-linje: gå til kategori-flaten eller åpne posten
    krevClick(hp) {
        if (hp.view) { this.setView(hp.view); }
        else if (hp.model) { this.openRecord(hp.model, hp.res_id); }
    }

    selectKpi(key) {
        this.state.selectedKpi = key;
    }

    // Kollaps huskes per bruker/nettleser (localStorage), men NULLSTILLES ved NY DAG —
    // alt er synlig ved dagens start (Gjermund 2026-07-03).
    _loadCollapsed() {
        try {
            const raw = JSON.parse(localStorage.getItem("fiq_hm_collapsed") || "{}") || {};
            const today = new Date().toISOString().slice(0, 10);
            return (raw.d === today && raw.v) ? raw.v : {};
        } catch (e) { return {}; }
    }

    // Skjul/vis en seksjon (kollaps ved hovedoverskrift) for å løfte fram de andre listene
    toggleCollapse(key) {
        this.state.collapsed[key] = !this.state.collapsed[key];
        try {
            localStorage.setItem("fiq_hm_collapsed", JSON.stringify(
                { d: new Date().toISOString().slice(0, 10), v: this.state.collapsed }));
        } catch (e) {}
    }

    // Detaljlinjer for valgt status-knapp (vises i frigjort plass under statuslinja)
    get kpiDetailLines() {
        const k = this.state.selectedKpi;
        if (k === "komm") {
            return this.state.komm.filter((m) => m.direction === "mottatt")
                .map((m) => ({ text: (m.author || "") + " · " + (m.subject || ""), model: m.model, res_id: m.res_id }));
        }
        if (k === "prosjekt") {
            return this.state.myTasks.filter((t) => t.overdue)
                .map((t) => ({ text: (t.no ? t.no + " " : "") + t.name, model: "project.task", res_id: t.id }));
        }
        if (k === "finans") {
            return this.state.finansLines || [];
        }
        return [];
    }

    openDetail(dl) {
        if (dl.model && dl.res_id) { this.openRecord(dl.model, dl.res_id); }
    }

    get filteredKomm() {
        const q = (this.state.kommQuery || "").toLowerCase().trim();
        const dir = this.state.kommDir;
        const sender = this.state.kommSender;
        return this.state.komm.filter((k) => {
            if (dir !== "alle" && k.direction !== dir) return false;
            if (sender && (k.author_id ? k.author_id !== sender.id : k.author !== sender.name)) return false;
            if (q && !(k.author + " " + k.subject + " " + k.element).toLowerCase().includes(q)) return false;
            return true;
        });
    }

    // Company picker: reload the shell in the selected company (version-independent via cids)
    setCompany(id) {
        const cid = parseInt(id, 10);
        if (!cid || cid === this.state.companyId) return;
        const url = new URL(window.location.href);
        url.searchParams.set("cids", cid);
        window.location.href = url.toString();
    }

    // 🏢 Konsern-boksen: aktiver ALLE brukerens firmaer (konsern-total på tvers)
    setCompanyAll() {
        const ids = (this.state.companies || []).map((c) => c.id);
        if (!ids.length) { return; }
        const url = new URL(window.location.href);
        url.searchParams.set("cids", ids.join(","));
        window.location.href = url.toString();
    }

    get isAllCompanies() {
        try {
            const cids = new URL(window.location.href).searchParams.get("cids") || "";
            return cids.includes(",") && cids.split(",").length >= (this.state.companies || []).length;
        } catch (e) { return false; }
    }

    // 📝 Fritekst-notat (vbox + Detaljer) → chatter som internt notat
    async postNote(model, id, text, clearRef) {
        const tx = (text || "").trim();
        if (!tx) { return; }
        try {
            await this.orm.call("fiq.gui.control.config", "post_note", [model, id, tx]);
            if (clearRef) { clearRef.value = ""; }
            this.notification.add(_t("Note saved to the log."), { type: "success" });
        } catch (e) {
            this.notification.add(_t("Could not save — ") + this._errMsg(e), { type: "danger" });
        }
    }

    // Enkel/Total: Enkel = arbeider-flaten (store knapper) — hopper alltid til oversikten
    // slik at byttet er synlig uansett hvilken flate man står i
    setMode(m) {
        this.state.mode = m;
        if (m === "enkel" && this.state.view !== "oversikt") { this.setView("oversikt"); }
    }

    setKommDir(d) {
        this.state.kommDir = d;
    }

    // Click a sender → show only that sender's communication (toggle on/off)
    filterSender(k) {
        const cur = this.state.kommSender;
        if (cur && (k.author_id ? cur.id === k.author_id : cur.name === k.author)) {
            this.state.kommSender = null;
        } else {
            this.state.kommSender = { id: k.author_id || false, name: k.author };
        }
    }

    clearSender() {
        this.state.kommSender = null;
    }

    async setKommPeriod(p) {
        this.state.kommPeriod = p;
        this._loadProjects(this.state.projQuery);   // perioden gjelder også prosjektlista
        this._loadKalender();                        // … og møter/aktiviteter-panelet
        try {
            this.state.komm = await this.orm.call("fiq.gui.control.config", "get_kommunikasjon", [p]);
        } catch (e) { this.state.komm = []; }
    }

    // Datovelger: referansedato som perioden (Dag/Uke/Måned) regnes ut fra
    setAnchor(v) {
        this.state.anchorDate = v || new Date().toISOString().slice(0, 10);
        this._loadProjects(this.state.projQuery);
        this._loadKalender();
    }

    // ---- Møter/aktiviteter-panelet: periode-vindu + person + månedskalender ----
    _iso(d) {
        const p = (n) => String(n).padStart(2, "0");
        return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + " " +
               p(d.getHours()) + ":" + p(d.getMinutes()) + ":" + p(d.getSeconds());
    }

    async _loadKalender() {
        const a = this._anchorDate();
        let w = this._periodWindow();
        if (!w) { // «Alle» = hele året rundt referansedatoen
            w = { s: new Date(a.getFullYear(), 0, 1), e: new Date(a.getFullYear() + 1, 0, 1) };
        }
        // Måneds-markørene følger VIST måned (kalMnd) — bla fritt uten å endre perioden
        const kY = parseInt(this.state.kalMnd.slice(0, 4), 10);
        const kM = parseInt(this.state.kalMnd.slice(5, 7), 10) - 1;
        const ms = new Date(kY, kM, 1);
        const me = new Date(kY, kM + 1, 1);
        const uid = this.state.selPerson ? this.state.selPerson.id : false;
        try {
            this.state.kal = await this.orm.call("fiq.gui.control.config", "get_kalender",
                [this._iso(w.s), this._iso(w.e), this._iso(ms), this._iso(me), uid]);
        } catch (e) { this.state.kal = { moter: [], aktiviteter: [], mnd: [] }; }
        this.state.selMote = false;
        this.state.selAkt = null;
    }

    // Person-toggle på Til stede-kortene: kalender + kommunikasjon følger valgt person
    selectPerson(pr) {
        const cur = this.state.selPerson;
        if (cur && cur.id === pr.id) {
            this.state.selPerson = null;
            this.state.kommSender = null;
        } else {
            this.state.selPerson = { id: pr.id, partner_id: pr.partner_id, name: pr.navn };
            this.state.kommSender = { id: pr.partner_id, name: pr.navn };
        }
        this._loadKalender();
    }

    // Måned-/år-navigasjon (std kalenderfunksjoner): ◂ ▸ + nedtrekk + I dag
    get kalY() { return parseInt(this.state.kalMnd.slice(0, 4), 10); }
    get kalM() { return parseInt(this.state.kalMnd.slice(5, 7), 10) - 1; }
    get mndNavn() { return mndNames(); }
    get ukedager() { return dayNames(); }
    // Mal-uttrykk (ternary/konkat) oversettes IKKE av OWL — tr() slår opp i oversettelses-
    // ordboka ved kjøretid. Strengene ligger i i18n/*.po (vedlikeholdes ved i18n-vask).
    tr(s) { return _t(s); }
    get kalAar() {
        const y = this.kalY, out = [];
        for (let i = y - 4; i <= y + 4; i++) { out.push(i); }
        return out;
    }

    _setKalMnd(y, m) {
        const d = new Date(y, m, 1);
        this.state.kalMnd = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
        // Kalender-navigasjon flytter også PERIODEN (Gjermund 2026-07-04): møte-/aktivitets-
        // listene følger vist måned — behold dag-i-måned der det går
        const cur = this._anchorDate();
        const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
        const day = Math.min(cur.getDate(), last);
        this.state.anchorDate = this._iso(new Date(d.getFullYear(), d.getMonth(), day));
        this._loadKalender();
        this._loadProjects(this.state.projQuery);
    }

    // 🔁 Hent ny GUI-versjon: full sidelast (assets lastes bare ved sidelast, ikke ⟳ Oppdater)
    reloadGui() {
        window.location.reload();
    }

    // Enkel-flatens store arbeider-knapper: ALLTID en ekte handling (aldri bare varsel)
    async enkelDo(key) {
        if (key === "oppgaver") {
            const el = document.querySelector(".fiq_blk_projects");
            if (el) { el.scrollIntoView({ behavior: "smooth" }); }
            return;
        }
        if (key === "sha" || key === "befaring") {
            // Åpner prosjektets oppgaver direkte (SHA Byggeplass / Befaring og FDV)
            const name = key === "sha" ? "SHA Byggeplass" : "Befaring og FDV";
            try {
                const r = await this.orm.searchRead(
                    "project.project", [["name", "ilike", name]], ["id"], { limit: 1 });
                if (r.length) { this.openProjectTasks(r[0].id); return; }
            } catch (e) { /* faller til godkjenningskøen under */ }
        }
        if (key === "ks" || key === "sha" || key === "befaring") {
            this.runAction("godkjenning");
            return;
        }
        this.runAction(key);
    }

    // 📌 STYRING-menyen: rendres fra brukerens rekkefølge (server-lagret som nav:-prefiks
    // i widget_order-feltet). Punkter uten tilgjengelig handling skjules (env.ref-guard).
    get navItems() {
        const DEF = [
            { key: "kontrollrom", label: _t("Control Room"), view: "oversikt" },
            // 18.07.2026 (Gjermund): «dette er testversjonen som kom som demo for 14 dager
            // siden, ikke den nye utviklede Kommunikasjon» — og samme for Prosjekt og AI KR.
            // ROTAARSAK: disse tre hadde view: → navDo() valgte setView() = KRs EGEN gamle
            // innebygde utgave, og naadde ALDRI den ekte modulen. Modulene var installert og
            // oppdaterte hele tiden (comm 1.2.0, ai_kr 2.3.0, prj 1.9.0). view: fjernet →
            // runAction() → ekte flate. Handlingene er verifisert i basen (ir_model_data).
            { key: "kommunikasjon", label: _t("Communication"), icon: "/fiq_gui_control/static/img/epost.png" },
            { key: "hmsks", label: _t("HSE/QA"), view: "hmsks" },
            { key: "airmm", label: _t("AI Control room") },
            { key: "gui_prj", label: _t("Projects"), title: _t("Open the Project control room") },
            { key: "gui_crm", label: _t("CRM") },
            { key: "gui_leads", label: _t("Leads") },
            { key: "gui_so", label: _t("Sales orders") },
            { key: "gui_fin", label: _t("Finance") },
            // Ingen «Email» her: e-post er én KANAL inne i Kommunikasjon (Alle · E-post ·
            // WhatsApp · Teams · chat), ikke et eget toppnivå. Gjermund 17.07.2026:
            // «e-post skal ikke vises før vi er inne i kommunikasjonssenteret».
            { key: "gui_rgs", label: _t("Accounting") },
            { key: "kunnskap", label: _t("Knowledge"), title: _t("Articles, templates and documentation") },
        ];
        // Selvregistrerte flater fra andre FIQ-moduler (get_fiq_flater). En ny modul
        // kommer inn HER uten at denne fila røres — det var nettopp koblingen som manglet:
        // modulene var installert og hadde handlinger, men menyen visste ikke om dem.
        // Server-siden har alt verifisert at handlingen finnes i denne basen.
        // .skjult = brukeren har selv slått av flaten (server-lagret, per bruker+firma).
        // Serveren har alt filtrert bort det hun ikke har TILGANG til — dette er kun hennes
        // eget valg blant resten. «Sy ditt eget KR.»
        const DYN = (this.state.fiqFlater || []).filter((f) => !f.skjult).map((f) => ({
            key: f.key, label: f.label, xmlid: f.xmlid, icon: f.icon || undefined,
        }));
        // Dedup på HANDLINGEN, ikke bare nøkkelen. Den faste lista og selvregistreringen
        // bruker ulike nøkler for SAMME flate (kommunikasjon/komm · gui_rgs/rgs · gui_fin/fin ·
        // airmm/ai_kr · gui_prj/prj) → menyen fikk dubletter: «Regnskap» to ganger, «Kommunikasjon»
        // ved siden av «Communication». Gjermund 19.07.2026, med skjermbilde.
        // Den faste lista vinner: den er oversatt og har brukerens egen rekkefølge.
        const fastXmlid = new Set(
            DEF.map((d) => this.state.actions[d.key]).filter(Boolean)
        );
        const alle = DEF.concat(
            DYN.filter((d) => !DEF.some((x) => x.key === d.key) && !fastXmlid.has(d.xmlid))
        );
        const map = {};
        alle.forEach((d) => { map[d.key] = d; });
        const orden = this.state.navOrder.filter((k) => map[k])
            .concat(alle.map((d) => d.key).filter((k) => !this.state.navOrder.includes(k)));
        return orden.map((k) => map[k])
            // d.xmlid = selvregistrert flate: server-siden har ALLEREDE bekreftet at
            // handlingen finnes i denne basen, så den skal ikke filtreres bort her.
            .filter((d) => d.view || d.xmlid || this.state.actions[d.key])
            .map((d) => Object.assign({ active: d.view ? this.state.view === d.view : false }, d));
    }

    navDo(key) {
        const it = this.navItems.find((d) => d.key === key);
        if (it && it.view) { this.setView(it.view); } else { this.runAction(key); }
    }

    navLabel(key) {
        const it = this.navItems.find((d) => d.key === key);
        return it ? it.label : key;
    }

    async moveNav(key, dir) {
        const all = this.navItems.map((d) => d.key);
        const o = this.state.navOrder.filter((k) => all.includes(k))
            .concat(all.filter((k) => !this.state.navOrder.includes(k)));
        const i = o.indexOf(key);
        const j = i + dir;
        if (i === -1 || j < 0 || j >= o.length) { return; }
        o[i] = o[j];
        o[j] = key;
        this.state.navOrder = o;
        try {
            await this.orm.call("fiq.gui.control.config", "set_widget_order",
                [this._orderString()]);
        } catch (e) { /* gjelder uansett i denne økten */ }
    }

    // 📌 Blokk-rekkefølge: CSS order på flatens hovedblokker (flex-kolonnen .fiq_hm_main)
    bo(key) {
        const i = this.state.blockOrder.indexOf(key);
        return i === -1 ? 50 : i + 1;
    }

    blockLabel(k) {
        return {
            activity: _t("Present + Meetings and activities"),
            quick: _t("Decision support"),
            projects: _t("Project overview + My tasks"),
            dash: _t("My dashboard"),
            chart: _t("Progress/Gantt + Details"),
        }[k] || k;
    }

    async moveBlock(key, dir) {
        const o = this.state.blockOrder.slice();
        const i = o.indexOf(key);
        const j = i + dir;
        if (i === -1 || j < 0 || j >= o.length) { return; }
        o[i] = o[j];
        o[j] = key;
        this.state.blockOrder = o;
        try {
            await this.orm.call("fiq.gui.control.config", "set_widget_order",
                [this._orderString()]);
        } catch (e) { /* rekkefølgen gjelder uansett i denne økten */ }
    }

    // Fold en cockpit-gruppe (som i Artifact-cockpiten)
    foldCpGroup(id) {
        this.state.cpFold[id] = !this.state.cpFold[id];
    }

    stepKalMnd(dir) { this._setKalMnd(this.kalY, this.kalM + dir); }
    setKalMonth(idx) { this._setKalMnd(this.kalY, parseInt(idx, 10)); }
    setKalYear(y) { this._setKalMnd(parseInt(y, 10), this.kalM); }
    kalIdag() {
        const t = new Date().toISOString().slice(0, 10);
        this.state.kalMnd = t.slice(0, 7);
        this.pickKalDag(t);
    }

    // Mini-månedskalenderen: uker/dager for VIST måned, møtedager markert
    get kalUker() {
        const y = this.kalY, m = this.kalM;
        const first = new Date(y, m, 1);
        const offset = (first.getDay() + 6) % 7;   // mandag først
        const start = new Date(y, m, 1 - offset);
        const has = new Set(this.state.kal.mnd || []);
        const p = (n) => String(n).padStart(2, "0");
        const uker = [];
        for (let u = 0; u < 6; u++) {
            const dager = [];
            for (let d = 0; d < 7; d++) {
                const dt = new Date(start); dt.setDate(start.getDate() + u * 7 + d);
                const iso = dt.getFullYear() + "-" + p(dt.getMonth() + 1) + "-" + p(dt.getDate());
                dager.push({ d: dt.getDate(), iso, im: dt.getMonth() === m, has: has.has(iso), sel: iso === this.state.anchorDate });
            }
            uker.push({ key: "u" + u, dager });
        }
        return uker;
    }

    get kalTittel() {
        return mndNames()[this.kalM] + " " + this.kalY;
    }

    get periodeTekst() {
        const m = { dag: _t("selected day"), uke: _t("the week"), maaned: _t("the month"), alle: _t("the year") };
        return m[this.state.kommPeriod] || "";
    }

    // Klikk på dato i månedskalenderen → vis møtene den dagen
    pickKalDag(iso) {
        this.state.anchorDate = iso;
        this.state.kalMnd = iso.slice(0, 7);
        this.state.kommPeriod = "dag";
        this._loadProjects(this.state.projQuery);
        this._loadKalender();
    }

    // Aktivitets-filter: alle | uten forfalte | kun forfalte (perioden styres av Dag/Uke/Måned)
    setAktFilter(m) { this.state.aktFilter = m; this.state.selAkt = null; }

    get filtAktiviteter() {
        const f = this.state.aktFilter;
        let rows = this.state.kal.aktiviteter || [];
        if (f === "skjul") { rows = rows.filter((a) => !a.forsinket); }
        if (f === "kun") { rows = rows.filter((a) => a.forsinket); }
        // Søk (samme linje som filter + gruppér): emne, element, type, tilhørighet
        const q = (this.state.aktQuery || "").trim().toLowerCase();
        if (q) {
            rows = rows.filter((a) =>
                ((a.name || "") + " " + (a.res_name || "") + " " + (a.type || "") + " "
                    + (a.modell_navn || "")).toLowerCase().indexOf(q) !== -1);
        }
        return rows;
    }

    // Gruppering i panelet — samme funksjon som native group-by, uten å forlate Kontrollrommet
    get aktGruppert() {
        const rows = this.filtAktiviteter;
        const g = this.state.aktGruppe;
        if (!g) { return rows; }
        const key = (a) => g === "type" ? (a.type || _t("(no type)"))
            : g === "element" ? (a.res_name || _t("(no element)"))
            : g === "modell" ? (a.modell_navn || a.model || _t("(no relation)"))
            : g === "frist" ? (a.frist || _t("(no deadline)"))
            : (a.forsinket ? _t("Past due") : _t("Upcoming"));
        const map = {}, order = [];
        rows.forEach((a) => { const k = key(a); if (!(k in map)) { map[k] = []; order.push(k); } map[k].push(a); });
        order.sort((x, y) => x.localeCompare(y));
        const out = [];
        order.forEach((k) => {
            const folded = !!this.state.aktGrpFold[k];
            out.push({ isHead: true, id: "ah:" + k, name: k, count: map[k].length, folded });
            if (!folded) { out.push(...map[k]); }
        });
        return out;
    }

    // Kollaps/ekspander en grupperingsoverskrift i aktivitetslisten
    toggleAktGrp(name) {
        this.state.aktGrpFold[name] = !this.state.aktGrpFold[name];
    }

    // «Utsett til»: +N dager fra fristen ELLER eksplisitt ny dato (på valgt aktivitet)
    async utsettAkt(dager, nyDato) {
        const a = this.state.selAkt;
        if (!a) { return; }
        try {
            await this.orm.call("fiq.gui.control.config", "utsett_aktivitet", [a.id, dager || false, nyDato || false]);
            this.notification.add(_t("The activity has been postponed."), { type: "success" });
            this.state.utsettDager = "";
            await this._loadKalender();
            // Pek valgt aktivitet til den FERSKE raden (detaljboksen viser ny frist)
            const rows = this.state.kal.aktiviteter || [];
            this.state.selAkt = rows.find((r) => r.id === a.id) || null;
        } catch (e) {
            this.notification.add(_t("Could not postpone — ") + this._errMsg(e), { type: "danger" });
        }
    }

    velgMote(id) { this.state.selMote = (this.state.selMote === id) ? false : id; }
    velgAkt(ak) {
        if (ak.isHead) { return; }
        this.state.selAkt = (this.state.selAkt && this.state.selAkt.id === ak.id) ? null : ak;
    }

    openSelMote() {
        if (this.state.selMote) { this.openRecord("calendar.event", this.state.selMote); }
    }

    openSelAkt() {
        const a = this.state.selAkt;
        if (a && a.model && a.res_id) { this.openRecord(a.model, a.res_id); }
        else if (a) { this.runAction("aktivitet"); }
    }

    // ◂ ▸: hopp forrige/neste periode (dag/uke/måned/år etter valgt toggle)
    stepAnchor(dir) {
        const p = this.state.kommPeriod;
        const a = this._anchorDate();
        if (p === "dag") { a.setDate(a.getDate() + dir); }
        else if (p === "maaned") { a.setMonth(a.getMonth() + dir); }
        else if (p === "alle") { a.setFullYear(a.getFullYear() + dir); }
        else { a.setDate(a.getDate() + 7 * dir); }
        this.setAnchor(a.toISOString().slice(0, 10));
    }

    // Perioden som konkret tidsvindu (null = «Alle» → ingen datofilter)
    // Robust referansedato: ugyldig/korrupt state.anchorDate (f.eks. skjev frys-gjenoppretting)
    // faller tilbake til i dag OG normaliseres, så Date-matematikk aldri gir «Invalid time value».
    _anchorDate() {
        let a = this.state.anchorDate ? new Date(this.state.anchorDate + "T12:00:00") : new Date();
        if (isNaN(a.getTime())) { a = new Date(); this.state.anchorDate = this._iso(a); }
        return a;
    }

    _periodWindow() {
        const p = this.state.kommPeriod;
        if (p === "alle") { return null; }
        const a = this._anchorDate();
        const d0 = new Date(a.getFullYear(), a.getMonth(), a.getDate());
        if (p === "dag") { const e = new Date(d0); e.setDate(d0.getDate() + 1); return { s: d0, e }; }
        if (p === "maaned") { return { s: new Date(a.getFullYear(), a.getMonth(), 1), e: new Date(a.getFullYear(), a.getMonth() + 1, 1) }; }
        const dow = (d0.getDay() + 6) % 7;
        const s = new Date(d0); s.setDate(d0.getDate() - dow);
        const e = new Date(s); e.setDate(s.getDate() + 7);
        return { s, e };
    }

    async replyTo(messageId, replyAll) {
        const act = await this.orm.call("fiq.gui.control.config", "action_reply", [messageId, !!replyAll]);
        this.action.doAction(act);
    }

    toggleCustomize() {
        this.state.customize = !this.state.customize;
    }

    toggleWidget(w) {
        this.state.show[w] = !this.state.show[w];
        // Persist per user on the server (governed by access groups + record rule)
        this.orm.call("fiq.gui.control.config", "set_widget", [w, this.state.show[w]]).catch(() => {});
    }

    openProjects() {
        // Robust: eget act_window (ikke avhengig av en bestemt xmlid som kan mangle)
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("All projects"),
            res_model: "project.project",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            target: "current",
        });
    }

    // Melding når en funksjon ennå ikke er ferdig (3-ukers-estimat + 75 % buffer)
    _underUtvikling() {
        this.notification.add(
            _t("This function is under development — expected delivery: 2026-08-07"),
            { type: "info" }
        );
    }

    // ── SLOT: åpne flaten INNI Kontrollrommet, ikke i stedet for det ───────────────────
    //
    // Gjermund 20.07.2026: rammen (meny, firmavelger, «Til stede nå», tidslinje) skal STÅ
    // når man åpner Kommunikasjon eller AI Kontrollrom. Før byttet `doAction` HELE siden,
    // og da forsvant rammen — man var i en annen app.
    //
    // Mekanismen fantes allerede i skallet (`fiq_gui_flates`), men bare 2 av 11 flater
    // brukte den. Vi bruker SAMME register her, med vilje: da kan skallet overta rammen
    // senere uten at en eneste flate-eier må endre noe.
    //
    // `doAction` beholdes som fallback for NATIVE Odoo-handlinger (Kunnskap, dashbord) —
    // dit SKAL man forlate Kontrollrommet.
    _slotKomponent(key) {
        try {
            const reg = registry.category("fiq_gui_flates");
            const e = reg && reg.get(key, null);
            return e && e.Component ? e : null;
        } catch (_e) {
            return null;   // registeret finnes ikke (skallet ikke installert) — bruk doAction
        }
    }

    // Beslutningsstøtte: kjør ekte doAction hvis handlingen finnes (guardet), ellers varsel.
    // key = nøkkel fra get_actions (nytt_prosjekt/salgsordre/nytt_leads/tilbud/kunde/dokument …)
    runAction(key) {
        // 1) Er flaten registrert som komponent? Bytt INNMAT — rammen står.
        const slot = this._slotKomponent(key);
        if (slot) {
            // Bytter du flate, nullstilles undermeny-valget. Uten dette ville et punkt fra
            // FORRIGE flate hengt igjen som aktivt — usynlig tilstand, samme felle som
            // søkefilteret Gjermund beskrev: «du fjerner prosjektet, men det henger igjen».
            if (this.state.slotKey !== key) { this.state.slotMenyValg = false; }
            this.state.slotKey = key;
            this.state.view = "flate";
            return;
        }
        // 2) Ellers: som før. Selvregistrerte FIQ-flater bærer sin egen xmlid
        // (get_fiq_flater) — uten dette oppslaget ville en ferdig, installert modul
        // havnet i «under utvikling».
        const dyn = (this.state.fiqFlater || []).find((f) => f.key === key);
        const xmlid = this.state.actions[key] || (dyn && dyn.xmlid);
        if (xmlid) {
            this.action.doAction(xmlid);
        } else {
            this._underUtvikling();
        }
    }

    // Komponenten som skal stå i sloten nå (null = ingen).
    get slotComponent() {
        const e = this.state.slotKey ? this._slotKomponent(this.state.slotKey) : null;
        return e ? e.Component : null;
    }

    // ── FLATENS EGNE MENYPUNKTER — under hovedmenyen, ikke ved siden av ────────────────
    //
    // Gjermund 20.07.2026: «kan øktenes menyer legge seg til under hovedmenyen?»
    //
    // JA — og KJERNEN eier det. Bygger hver flate sin egen meny, får vi fem menyer som ser
    // ulike ut, oppfører seg ulikt, og som ikke kan foldes på tvers. Nøyaktig samme feil som
    // de SEKS kollaps-implementasjonene og de TO fargekartene: én sak løst fem ganger, med
    // fem ulike svar. Flaten leverer DATA; kjernen eier utseende og oppførsel.
    //
    // KONTRAKTEN — flaten legger `meny` i sin registrering (valgfritt):
    //   registry.category("fiq_gui_flates").add("salg", {
    //       key: "salg", label: "…", Component: MinFlate,
    //       meny: [{ key: "pipeline", label: "Pipeline", badge: 5 },
    //              { key: "tapt",     label: "Tapte",    badge: 0 }],
    //   });
    //
    // MENY-PUNKTENES `label` tåler tekst ELLER {en_US, nb_NO} — norsk før engelsk.
    // 📌 Gjelder også FLATENS egen `label` fra 21.07 (kontrakten i shell.js ble utvidet).
    //    Før var de to ulike: skjemaet krevde String, denne kommentaren sa «begge former».
    //    Relasjoner leste kommentaren, sendte objekt, og HELE grensesnittet ble blankt.
    //    Ett feltnavn, to kontrakter, samme fil = dokumentasjonsfelle. Nå: ÉN regel.
    // `badge` er valgfritt: tall som HASTER, ikke totalen (samme regel som samleboksene).
    //
    // Ingen `meny` = ingen undermeny. Flater som ikke trenger det, merker ingenting.
    get slotMeny() {
        const e = this.state.slotKey ? this._slotKomponent(this.state.slotKey) : null;
        const rå = (e && Array.isArray(e.meny)) ? e.meny : [];
        return rå
            .filter((m) => m && m.key)
            .map((m) => ({
                key: m.key,
                label: this._flateTekst(m.label) || m.key,
                badge: Number.isFinite(m.badge) ? m.badge : 0,
                active: this.state.slotMenyValg === m.key,
            }));
    }

    // Etikett som tåler både ren tekst og språk-oppslag. Norsk før engelsk (kanon 19.07).
    _flateTekst(l) {
        if (l && typeof l === "object") { return l[user.lang] || l.nb_NO || l.en_US || ""; }
        return l || "";
    }

    // Klikk i flatens undermeny. Kjernen HUSKER valget og sender det som prop — flaten
    // bestemmer selv hva det betyr. Vi tolker aldri innholdet i en annen økts flate.
    velgSlotMeny(key) {
        this.state.slotMenyValg = this.state.slotMenyValg === key ? false : key;
    }

    // Navnet på flaten i sloten — til overskrift og «tilbake»-linja.
    get slotLabel() {
        const e = this.state.slotKey ? this._slotKomponent(this.state.slotKey) : null;
        if (!e) { return ""; }
        // Etiketten kan være tekst ELLER {en_US, nb_NO}. Norsk før engelsk — samme
        // rekkefølge som resten av Kontrollrommet (kanon 19.07: norsk er fasit).
        const l = e.label;
        if (l && typeof l === "object") { return l[user.lang] || l.nb_NO || l.en_US || this.state.slotKey; }
        return l || this.state.slotKey;
    }

    // ── VENSTREMENYENS TRE GRUPPER (utkast 15, godkjent 20.07.2026) ───────────────────
    //
    // TREKKSPILL: åpner du én gruppe, lukkes forrige — slik at menyen aldri blir en lang
    // rulleliste. 🛑 UNNTAK: «0 INNBOKS». Gjermund: den skal kunne stå åpen mens du jobber
    // i et fagområde, fordi det er stedet du tømmer FRA.
    //
    // 🔑 Foldetilstanden lagres per bruker (localStorage), ikke i minnet: menyen skal se
    // lik ut når du kommer tilbake i morgen. Uten det ville hver sidelasting nullstilt
    // valget ditt — og da lærer man seg aldri hvor ting er.
    toggleGrp(key) {
        const aapen = this.state.grpAapen[key];
        if (!aapen && key !== "innboks") {
            // Lukk de ANDRE trekkspill-gruppene. Innboks røres aldri av dette.
            for (const k of Object.keys(this.state.grpAapen)) {
                if (k !== "innboks" && k !== key) { this.state.grpAapen[k] = false; }
            }
        }
        this.state.grpAapen[key] = !aapen;
        try {
            localStorage.setItem("fiq_hm_grp", JSON.stringify(this.state.grpAapen));
        } catch (e) { /* privat modus — valget gjelder da kun denne økta */ }
    }

    _lastGrp() {
        try {
            const r = JSON.parse(localStorage.getItem("fiq_hm_grp") || "null");
            if (r && typeof r === "object") {
                return { innboks: !!r.innboks, rom: !!r.rom, fag: !!r.fag };
            }
        } catch (e) { /* ugyldig lagret verdi — bruk standard */ }
        return { innboks: true, rom: false, fag: true };
    }

    // 0 INNBOKS — fire kilder, nummerert som i utkastet. Tallene er det som HASTER,
    // ikke totalen (samme regel som samleboksene): et tall du ikke kan handle på er støy.
    get innboksKilder() {
        // 🛑 Tallene leses fra data som FAKTISK finnes — verifisert i koden, ikke antatt.
        // Første utkast leste `komm.epost_ny` o.l.: `state.komm` er en LISTE, ikke et objekt,
        // og de feltene finnes ikke. Det ville gitt fire nuller — en meny som ser rolig ut
        // fordi den ikke måler noe. Verre enn ingen tall.
        const komm = this.state.komm || [];
        const mottatt = komm.filter((k) => k.direction === "mottatt");
        return [
            { nr: "0.1", key: "epost", label: _t("E-mail"),
              n: mottatt.filter((k) => k.ktype === "epost" || k.kind === "E-post").length },
            { nr: "0.2", key: "ai", label: _t("AI messages"),
              n: mottatt.filter((k) => k.ktype === "ai").length },
            { nr: "0.3", key: "oppgaver", label: _t("Tasks"),
              n: (this.state.cp && this.state.cp.krever ? this.state.cp.krever.length : 0) },
            { nr: "0.4", key: "aktiviteter", label: _t("Activities"),
              n: (this.state.kal && this.state.kal.aktiviteter ? this.state.kal.aktiviteter.length : 0) },
        ];
    }

    // Sum for gruppeoverskriften — «0 INNBOKS · 9». Ser du hvor det brenner uten å åpne.
    get innboksSum() {
        return this.innboksKilder.reduce((s, x) => s + (x.n || 0), 0);
    }

    // Lukk flaten og gå tilbake til forsiden. Rammen har stått hele tiden.
    lukkFlate() {
        this.state.slotKey = false;
        this.state.slotMenyValg = false;
        this.state.view = "oversikt";
    }

    // ── MERKNAD PÅ EGET KORT: «Lunsj» + fritekst (Gjermund 20.07.2026) ────────────────
    //
    // 🛑 Merknaden endrer IKKE status og IKKE farge. Gjermund: «de aller fleste må være
    // tilgjengelig i lunsjen for henvendelser og telefoner … jeg ønsker bare at det er
    // anmerket, og at det er mulig å vise hensyn.» En kollega kan velge å vente ti
    // minutter — men skal fortsatt kunne ringe. Anmerkning, aldri sperre.
    //
    // 🛑 Rører ALDRI arbeidstidskalenderen. Odoo deler dagen i to arbeidsøkter (bygget for
    // land der lunsj er en lang, fast pause). I Norge er den kort og tas når det passer —
    // arbeidstiden løper videre. Dette er kun en melding til kollegene.
    async _lagreMerknad(tekst, minutter, slutt) {
        try {
            await this.orm.call("fiq.gui.control.config", "sett_min_merknad", [], {
                tekst: tekst || false,
                minutter: minutter || false,
                slutt: slutt || false,
            });
            // Hent oppmøtelista på nytt så banneret vises umiddelbart — uten dette måtte
            // brukeren oppdatere siden for å se sin egen merknad, og da ser det ut som
            // knappen ikke virket.
            this.state.presence = await this.orm.call(
                "fiq.gui.control.config", "get_presence", []);
        } catch (e) {
            this.notification.add(this._errMsg(e), { type: "danger" });
        }
    }

    // Lunsj = fritekst med ferdig tekst + 40 min (Gjermunds tall). ÉN mekanisme, to knapper.
    settLunsj() {
        this._lagreMerknad(_t("Lunch"), 40, false);
    }

    // Fritekst: «på befaring», «hos tannlegen», «henter i barnehagen».
    // Tidspunkt er VALGFRITT — tomt betyr «står til jeg fjerner den selv».
    settFritekst() {
        const tekst = window.prompt(_t("Note (e.g. «On site», «At the dentist»):"), "");
        if (tekst === null) { return; }              // avbrutt
        if (!tekst.trim()) { this.fjernMerknad(); return; }
        const tid = window.prompt(_t("Back at (HH:MM) — leave empty for no end time:"), "");
        if (tid === null) { return; }
        this._lagreMerknad(tekst.trim(), false, tid.trim() || false);
    }

    fjernMerknad() {
        this._lagreMerknad(false, false, false);
    }

    // «Legg til knapp» (tilpass) – ennå ikke bygget
    addButton() {
        this._underUtvikling();
    }

    // «⤢ Utvidet» → åpne den NATIVE Odoo-visningen for det man ser på.
    // Oppgave-nivå (drill): prosjektets oppgaver (liste/Gantt). Prosjekt-nivå:
    // valgt prosjekt → dets oppgaver; ellers hele prosjekt-oversikten.
    openProsjektKontrollrom() {
        const mode = this.state.rightView === "gantt" ? "gantt" : undefined;
        if (this.state.progLevel === "oppgave" && this.state.progProjId) {
            this.openProjectTasks(this.state.progProjId, mode);
        } else if (this.state.selected && this.state.selected.model === "project.project") {
            this.openProjectTasks(this.state.selected.id, mode);
        } else {
            this.openProjects();
        }
    }

    // «Spør AI om hjelp» → Claude via fiq.ai-connector (krever installert fiq_ai + API-nøkkel)
    async askAi() {
        const q = (this.state.aiQuery || "").trim();
        if (!q) { return; }
        this.state.aiAnswer = _t("Thinking …");
        try {
            const ans = await this.orm.call("fiq.ai", "chat", [q]);
            this.state.aiAnswer = ans || _t("(empty reply)");
        } catch (e) {
            // Vis den EKTE feilen (ikke generisk melding) — avgjørende for feilsøking
            this.state.aiAnswer = _t("AI error: ") + this._errMsg(e);
        }
    }

    clearAi() {
        this.state.aiAnswer = "";
        this.state.aiQuery = "";
    }

    // Real click-through: open a record in Odoo
    openRecord(model, id, dialog) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: dialog ? "new" : "current",
        });
    }

    // Feilmelding fra en ORM-/RPC-feil, mest mulig lesbart
    _errMsg(e) {
        return (e && e.data && e.data.message) || (e && e.message) || String(e || "");
    }

    // Inline planlagt-dato (prosjekt: date-felt). Uavhengige fra/til-kalendere.
    // Oppdaterer skjermen KUN hvis lagringen faktisk gikk gjennom; ellers vis feilen.
    async setProjDate(id, field, value) {
        try {
            await this.orm.write("project.project", [id], { [field]: value || false });
        } catch (e) {
            this.notification.add(_t("Could not save the date — ") + this._errMsg(e), { type: "danger" });
            return;
        }
        const p = this.state.projects.find((x) => x.id === id);
        if (p) { if (field === "date_start") { p.start = value || false; } else { p.end = value || false; } }
    }

    // Inline planlagt-dato (oppgave: datetime-felt). Lagre kl. 12 for å unngå tidssone-skift.
    async setTaskDate(id, field, value) {
        const val = value ? value + " 12:00:00" : false;
        try {
            await this.orm.write("project.task", [id], { [field]: val });
        } catch (e) {
            this.notification.add(_t("Could not save the date — ") + this._errMsg(e), { type: "danger" });
            return;
        }
        const t = this.state.myTasks.find((x) => x.id === id);
        if (t) { if (field === "planned_date_begin") { t.pfrom = value || ""; } else { t.pto = value || ""; } }
    }

    // Dato på en oppgave i fremdrift-drillen (progTasks bruker start/end for Gantt).
    async setProgTaskDate(id, field, value) {
        const val = value ? value + " 12:00:00" : false;
        try { await this.orm.write("project.task", [id], { [field]: val }); }
        catch (e) { this.notification.add(_t("Could not save the date — ") + this._errMsg(e), { type: "danger" }); return; }
        const t = this.state.progTasks.find((x) => x.id === id);
        if (t) { if (field === "planned_date_begin") { t.start = value || false; } else { t.end = value || false; } }
    }

    // Felles dato-ruter for fremdrift-radene: prosjekt-nivå -> project.project (date_start/date),
    // oppgave-nivå -> project.task (planned_date_begin/date_deadline). which = "from" | "to".
    setRowDate(row, which, value) {
        if (this.state.progLevel === "oppgave") {
            this.setProgTaskDate(row.id, which === "from" ? "planned_date_begin" : "date_deadline", value);
        } else {
            this.setProjDate(row.id, which === "from" ? "date_start" : "date", value);
        }
    }

    // Juster estimerte (antatte) timer på en oppgave → skriv allocated_hours og
    // regn fremdrift på nytt (oppgave + prosjekt-rollup + evt. åpen oppgave-drill).
    async setTaskEst(id, value) {
        const h = parseFloat(String(value || "").replace(",", ".")) || 0;
        try { await this.orm.write("project.task", [id], { allocated_hours: h }); }
        catch (e) { this.notification.add(_t("Could not save the estimate — ") + this._errMsg(e), { type: "danger" }); return; }
        await this._fillProgress("project.task", this.state.myTasks);
        await this._fillProgress("project.project", this.state.projects);
        if (this.state.progLevel === "oppgave") {
            await this._fillProgress("project.task", this.state.progTasks);
        }
    }

    // Click a project → its tasks. mode="gantt" opens the Gantt view.
    openProjectTasks(pid, mode) {
        const views = mode === "gantt"
            ? [[false, "gantt"], [false, "list"], [false, "form"]]
            : [[false, "list"], [false, "form"]];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: mode === "gantt" ? _t("Planning") : _t("Tasks"),
            res_model: "project.task",
            domain: [["project_id", "=", pid]],
            views: views,
            context: { group_by: ["stage_id"] },
            target: "current",
        });
    }

    // Open one of Odoo's native dashboards/analyses in-page (SSOT)
    openDashboard(xmlid) {
        this.action.doAction(xmlid);
    }

    // «⟳ Oppdater» – hent live data på nytt (KPI, prosjekter, oppgaver, fremdrift, kommunikasjon)
    // uten å blanke hele skjermen. Ny data settes inn i state når kallene svarer.
    async refresh() {
        if (this.state.refreshing) { return; }
        this.state.refreshing = true;
        try {
            await this.loadConfig();   // versjonsbrikke + oppsett friskt uten sidelast
            await this.loadData();
            // Hold oppgave-drillen fersk hvis den er åpen
            if (this.state.progLevel === "oppgave" && this.state.progProjId) {
                await this._loadProgTasks(this.state.progProjId);
            }
        } finally { this.state.refreshing = false; }
    }

    setView(v) {
        this.state.view = v;
        if ((v === "airmm" || v === "prosjektkr") && !this.state.cp) { this.loadCockpit(); }
    }

    // ---- AI-cockpit (fremdrifts-hub): ekte project.task-data, Artifact-malen ----
    async loadCockpit() {
        try {
            this.state.puls = await this.orm.call("fiq.gui.control.config", "get_puls", []);
        } catch (e) { /* puls er valgfri pynt */ }
        try {
            this.state.cp = await this.orm.call(
                "fiq.gui.control.config", "get_cockpit", [this.state.cpProj || false]);
        } catch (e) {
            this.state.cp = { groups: [], tot: { done: 0, pag: 0, vent: 0, tot: 0, pct: 0 }, krever: [], root: "" };
        }
        try {
            this.state.okter = await this.orm.call("fiq.gui.control.config", "get_okter", []);
        } catch (e) { this.state.okter = []; }
        try {
            this.state.krever = await this.orm.call("fiq.gui.control.config", "get_krever", []);
        } catch (e) { this.state.krever = []; }
        if (!this.state.cpScope) {
            try {
                this.state.cpScope = await this.orm.call("fiq.gui.control.config", "get_cockpit_scope", []);
            } catch (e) { this.state.cpScope = { kunder: [], prosjekter: [] }; }
        }
        await this._loadCpDiagram();
    }

    // Diagram over ALLE prosjekter i valgt scope (kunde/hjerne = toppnivå-rot / 0.00 IQ / alle)
    async _loadCpDiagram() {
        const k = this.state.cpKunde;
        try {
            this.state.cpDiagram = await this.orm.call(
                "fiq.gui.control.config", "get_cockpit_diagram",
                [k && k !== "iq" ? parseInt(k) : false, k === "iq", this.state.cpSlag]);
        } catch (e) { this.state.cpDiagram = []; }
    }

    setCpSlag(s) {
        this.state.cpSlag = s;
        this._loadCpDiagram();
    }

    setCpKunde(v) {
        this.state.cpKunde = v;
        this.state.cpProj = "";
        this._loadCpDiagram();
    }

    setCpProj(v) {
        this.state.cpProj = v;
        this.loadCockpit();
    }

    setCpMode(m) {
        this.state.cpMode = m;
    }

    // Prosjektvelgeren: valgt kundes prosjekter, filtrert på AI-plattform/Interne-knappen
    get cpProjOptions() {
        const s = this.state.cpScope;
        if (!s) { return []; }
        const k = this.state.cpKunde;
        const slag = this.state.cpSlag;
        if (k && k !== "iq") {
            return this.state.cpDiagram.map((d) => ({ id: d.id, no: d.no, name: d.name }));
        }
        let rows = s.prosjekter;
        if (k === "iq") { rows = rows.filter((p) => (p.name || "").startsWith("0.")); }
        if (slag === "ai") { rows = rows.filter((p) => p.ai); }
        if (slag === "interne") { rows = rows.filter((p) => !p.ai); }
        return rows;
    }

    // Diagrammet gruppert på kunde/hjerne ved «Alle» (samlelinje + fold per rot)
    get cpDiagramView() {
        const rows = this.state.cpDiagram;
        if (this.state.cpKunde || !this.state.cpGrp) { return rows; }
        const groups = {}, order = [];
        rows.forEach((r) => {
            const k = r.root_id || r.id;
            if (!(k in groups)) {
                groups[k] = { name: r.root_name || r.name, members: [], est: 0, logged: 0, pctSum: 0 };
                order.push(k);
            }
            if (!r.is_root) { groups[k].members.push(r); }
            groups[k].est += r.est || 0;
            groups[k].logged += r.logged || 0;
            groups[k].pctSum += r.pct || 0;
        });
        const out = [];
        order.forEach((k) => {
            const g = groups[k];
            if (!g.members.length) {
                const solo = rows.find((r) => r.is_root && r.id === k);
                if (solo) { out.push(solo); }
                return;
            }
            const folded = !!this.state.cpDiagFold[k];
            const pct = g.est > 0 ? Math.min(100, Math.round(g.logged * 100 / g.est))
                : Math.round(g.pctSum / g.members.length);
            out.push({ isHead: true, id: "dh:" + k, key: k, name: g.name, count: g.members.length,
                folded, pct, est: Math.round(g.est * 10) / 10, logged: Math.round(g.logged * 10) / 10 });
            if (!folded) { out.push(...g.members); }
        });
        return out;
    }

    toggleCpDiag(k) {
        this.state.cpDiagFold[k] = !this.state.cpDiagFold[k];
    }

    get cpDiagramMax() {
        let m = 0;
        this.state.cpDiagram.forEach((d) => { if (d.logged > m) { m = d.logged; } if (d.est > m) { m = d.est; } });
        return m || 1;
    }

    setCpFilter(f) {
        this.state.cpFilter = f;
    }

    pctOf(done, total) {
        return Math.round((done || 0) * 100 / (total || 1));
    }

    // Rot-stil: accent + FERDIGREGNEDE tone-varianter (rgba) — robust i alle nettlesere
    // (color-mix i CSS viste seg upålitelig gjennom asset-kompilatoren)
    get rootStyle() {
        const accent = this.state.accent || "#38B44A";
        let hex = accent.replace("#", "");
        if (hex.length === 3) { hex = hex.split("").map((c) => c + c).join(""); }
        const n = parseInt(hex, 16) || 0;
        const r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
        return "--fiq-accent:" + accent
            + ";--fiq-accent-soft:rgba(" + r + "," + g + "," + b + ",.10)"
            + ";--fiq-accent-line:rgba(" + r + "," + g + "," + b + ",.38)"
            + ";--fiq-accent-tile:rgba(" + r + "," + g + "," + b + ",.05);";
    }

    // 🌙 Mørk bakgrunn PER KONTROLLPANEL (view): eget valg per flate (huskes);
    // standard = Odoos color_scheme-cookie. Toggle øverst + under Innstillinger.
    _loadDarkMap() {
        try {
            const raw = JSON.parse(localStorage.getItem("fiq_hm_darkmap") || "{}");
            return raw && typeof raw === "object" ? raw : {};
        } catch (e) { return {}; }
    }

    get isDark() {
        const m = this.state.darkMap, v = this.state.view;
        if (v in m) { return !!m[v]; }
        try { return document.cookie.indexOf("color_scheme=dark") !== -1; } catch (e) { return false; }
    }

    toggleDark() {
        this.state.darkMap[this.state.view] = !this.isDark;
        try { localStorage.setItem("fiq_hm_darkmap", JSON.stringify(this.state.darkMap)); } catch (e) { /* ok */ }
    }

    // ---- Mitt dashbord: valgfrie elementer/rapporter (fra get_dashboards, huskes) ----
    _loadDashSel() {
        try {
            const raw = JSON.parse(localStorage.getItem("fiq_hm_dash") || "[]");
            return Array.isArray(raw) ? raw : [];
        } catch (e) { return []; }
    }

    _saveDashSel() {
        try { localStorage.setItem("fiq_hm_dash", JSON.stringify(this.state.dashSel)); } catch (e) { /* ok */ }
    }

    get myDash() {
        const map = {};
        this.state.dashboards.forEach((d) => { map[d.xmlid] = d; });
        return this.state.dashSel.map((x) => map[x]).filter(Boolean);
    }

    get dashAvail() {
        const sel = new Set(this.state.dashSel);
        return this.state.dashboards.filter((d) => !sel.has(d.xmlid));
    }

    addDash(xmlid) {
        if (!xmlid || this.state.dashSel.includes(xmlid)) { return; }
        this.state.dashSel.push(xmlid);
        this._saveDashSel();
    }

    removeDash(xmlid) {
        this.state.dashSel = this.state.dashSel.filter((x) => x !== xmlid);
        this._saveDashSel();
    }

    openDash(xmlid) {
        this.action.doAction(xmlid);
    }

    // Grupper filtrert etter VIS-valget (Alle / Mine 👤 / AI 🤖 / Gjenstår)
    get cpGroups() {
        const cp = this.state.cp;
        if (!cp) { return []; }
        const flt = this.state.cpFilter;
        return cp.groups.map((g) => {
            const tasks = g.tasks.filter((t) =>
                (flt !== "du" || t.who === "du") &&
                (flt !== "ai" || t.who === "ai") &&
                (flt !== "apen" || t.st !== "ferdig"));
            return Object.assign({}, g, { tasks });
        }).filter((g) => g.tasks.length || flt === "alle");
    }

    // Svar til en økt: legges i øktens chatter (øktene leser ved hver synk)
    async sendOktSvar(taskId) {
        const txt = (this.state.oktSvar[taskId] || "").trim();
        if (!txt) { return; }
        try {
            await this.orm.call("fiq.gui.control.config", "post_okt_melding", [taskId, txt]);
            this.state.oktSvar[taskId] = "";
            this.state.oktSel = 0;
            this.state.okter = await this.orm.call("fiq.gui.control.config", "get_okter", []);
        } catch (e) {
            this.notification.add(_t("Could not send — ") + this._errMsg(e), { type: "danger" });
        }
    }

    async cpToggle(taskId) {
        try {
            await this.orm.call("fiq.gui.control.config", "cockpit_toggle", [taskId]);
            await this.loadCockpit();
        } catch (e) {
            this.notification.add(_t("Could not change status — ") + this._errMsg(e), { type: "danger" });
        }
    }

    setRightView(v) {
        this.state.rightView = v;
    }

    // Velg element -> vises i inspektor-panelet (Detaljer). Henter ekte beskrivelse.
    // Full post apnes med openRecord (⤢).
    async selectEl(model, id, name) {
        this.state.selected = { model, id, name };
        this.state.selDet = { beskrivelse: "", logg: [], epost: [], dok: [] };
        this.state.selDelt = null;
        this.state.inspTab = "beskrivelse";
        try {
            const d = await this.orm.call("fiq.gui.control.config", "get_detaljer", [model, id]);
            if (d) {
                d.beskrivelse = this._stripHtml(d.beskrivelse || "");
                this.state.selDet = d;
            }
        } catch (e) { /* ingen tilgang / tomt -> behold tomt objekt */ }
    }

    // Enkel HTML->tekst for beskrivelses-feltet (html) i inspektoren
    _stripHtml(html) {
        if (!html) { return ""; }
        try {
            const d = document.createElement("div");
            d.innerHTML = html;
            return (d.textContent || d.innerText || "").trim();
        } catch (e) { return String(html).replace(/<[^>]*>/g, " ").trim(); }
    }

    setInspTab(t) {
        this.state.inspTab = t;
    }

    // Dokumenter i Detaljer: KUN forhåndsvisning (FileViewer-overlegg) — ALDRI åpne/laste
    // ned (nedlasting gir versjonsproblemer; nedlastingsknappen i viseren er skjult i SCSS).
    _dokFile(d) {
        return Object.assign(new FileModel(), {
            id: d.id, name: d.name, mimetype: d.mimetype || "",
            checksum: d.checksum || false, type: "binary",
        });
    }

    openDok(d) {
        const files = (this.state.selDet.dok || []).map((x) => this._dokFile(x)).filter((f) => f.isViewable);
        const file = files.find((f) => f.id === d.id);
        if (file) {
            this.fileViewer.open(file, files);
        } else {
            this.notification.add(
                _t("This file type cannot be previewed here yet (SharePoint/M365 preview is coming). Download is turned off — version control."),
                { type: "info" }
            );
        }
    }

    // ---- Egen kompakt Gantt (høyre panel). Vindu styres av periode-toggle (kommPeriod). ----
    get ganttWindow() {
        const p = this.state.kommPeriod;
        const now = this._anchorDate();
        let start, end;
        if (p === "alle") {
            start = new Date(now.getFullYear(), 0, 1);
            end = new Date(now.getFullYear() + 1, 0, 1);
        } else if (p === "maaned") {
            start = new Date(now.getFullYear(), now.getMonth(), 1);
            end = new Date(now.getFullYear(), now.getMonth() + 1, 1);
        } else {
            // dag/uke -> inneværende uke (man..man+7)
            const d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            const dow = (d.getDay() + 6) % 7;
            start = new Date(d);
            start.setDate(d.getDate() - dow);
            end = new Date(start);
            end.setDate(start.getDate() + 7);
        }
        return { start: start.getTime(), end: end.getTime() };
    }

    // Kontekstlinje over aksen: ukenummer + måned + år (avhengig av periode)
    get ganttHeader() {
        const p = this.state.kommPeriod;
        const { start } = this.ganttWindow;
        const s = new Date(start);
        if (p === "alle") { return String(s.getFullYear()); }
        if (p === "maaned") { return mndNames()[s.getMonth()] + " " + s.getFullYear(); }
        return _t("Week") + " " + isoWeek(s) + " · " + mndNames()[s.getMonth()] + " " + s.getFullYear();
    }

    get ganttTicks() {
        const p = this.state.kommPeriod;
        const { start, end } = this.ganttWindow;
        const span = (end - start) || 1;
        const pct = (t) => ((t - start) / span) * 100;
        const ticks = [];
        if (p === "alle") {
            const y = new Date(start).getFullYear();
            const mn = [_t("Jan"), _t("Feb"), _t("Mar"), _t("Apr"), _t("May"), _t("Jun"), _t("Jul"), _t("Aug"), _t("Sep"), _t("Oct"), _t("Nov"), _t("Dec")];
            for (let m = 0; m < 12; m++) ticks.push({ label: mn[m], left: pct(new Date(y, m, 1).getTime()) });
        } else if (p === "maaned") {
            // Ukenummer per uke i måneden
            let d = new Date(start);
            while (d.getTime() < end) {
                ticks.push({ label: _t("W") + isoWeek(d), left: pct(d.getTime()) });
                const nx = new Date(d); nx.setDate(d.getDate() + 7); d = nx;
            }
        } else {
            // Ukedag + dato (Ma 29.6 …)
            const wd = dayNames();
            for (let i = 0; i < 7; i++) {
                const d = new Date(start + i * 86400000);
                ticks.push({ label: wd[i] + " " + d.getDate() + "." + (d.getMonth() + 1), left: pct(start + i * 86400000) });
            }
        }
        return ticks;
    }

    get ganttRows() {
        const { start, end } = this.ganttWindow;
        const span = (end - start) || 1;
        const nowTs = Date.now();
        return this.progRows.map((p) => {
            if (p.isHead) { return p; }
            const s = p.start ? new Date(p.start).getTime() : null;
            const e = p.end ? new Date(p.end).getTime() : null;
            if (s === null && e === null) {
                return { id: p.id, no: p.no, name: p.name, hasDates: false, start: p.start || false, end: p.end || false };
            }
            const bs = s !== null ? s : e;
            const be = e !== null ? e : s;
            let left = Math.max(0, Math.min(100, ((bs - start) / span) * 100));
            let right = Math.max(0, Math.min(100, ((be - start) / span) * 100));
            // Tids-status: grønn = i rute · gul = i fare (bak forventet) · rød = over frist · mørk grønn = utført
            const prog = p.progress || 0;
            let farge = "green";
            if (prog >= 100) { farge = "done"; }
            else if (be < nowTs) { farge = "red"; }
            else if (bs < nowTs && be > bs) {
                const forventet = ((nowTs - bs) / (be - bs)) * 100;
                farge = (prog + 10 >= forventet) ? "green" : "yellow";
            }
            const widthPct = Math.max(1.5, right - left);
            return { id: p.id, no: p.no, name: p.name, hasDates: true, start: p.start || false, end: p.end || false,
                     leftPct: left, widthPct, progress: prog, farge,
                     pctLeft: Math.min(92, left + widthPct) };
        });
    }

    // Metadata (ikon/farge + tittel) for gjeldende fagflate-visning; null for oversikt/kommunikasjon
    get area() {
        const map = {
            hmsks: { color: "#0070C0", title: _t("HSE/QA") },
            prosjekt: { icon: "prj.png", title: _t("All projects") },
            crm: { icon: "crm.png", title: _t("CRM") },
            salgsmuligheter: { icon: "crm_leads.png", title: _t("Opportunities") },
            salgsordre: { icon: "crm_so.png", title: _t("Sales Orders") },
            regnskap: { icon: "rgs.png", title: _t("Accounting") },
            // SP-fagområder (rutenett i sidemenyen) – integrerte placeholders inntil egne flater
            omr_ledelse: { color: "#0070C0", title: _t("1 Management") },
            omr_admin: { color: "#6b7280", title: _t("2 Administration") },
            omr_log: { color: "#70AD47", title: _t("4 Logistics") },
            omr_mar: { color: "#ED7D31", title: _t("5 Marketing") },
            omr_salg: { color: "#CC0000", title: _t("6 Sales") },
            omr_fag: { color: "#7030A0", title: _t("8 Subject areas") },
        };
        return map[this.state.view] || null;
    }

    // SP-fagområder for sidemeny-rutenettet (nummer + navn + kanonisk farge)
    get fagomrader() {
        return [
            { view: "omr_ledelse", nr: "1", navn: _t("Management"), farge: "#0070C0" },
            { view: "omr_admin", nr: "2", navn: _t("Admin"), farge: "#6b7280" },
            { view: "omr_log", nr: "4", navn: "LOG", farge: "#70AD47" },
            { view: "omr_mar", nr: "5", navn: "MAR", farge: "#ED7D31" },
            { view: "omr_salg", nr: "6", navn: _t("Sales"), farge: "#CC0000" },
            { view: "omr_fag", nr: "8", navn: "FAG", farge: "#7030A0" },
        ];
    }

    openOdoo() {
        // Shortcut to Odoo's native app menu
        window.location.href = "/odoo";
    }
}

registry.category("actions").add("fiq_gui_control_dashboard", FiqControlRoom);
