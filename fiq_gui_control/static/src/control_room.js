/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";
import { View } from "@web/views/view";

const WIDGETS = ["kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"];

export class FiqControlRoom extends Component {
    static template = "fiq_gui_control.ControlRoom";
    static props = ["*"];
    static components = { View };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        // Stable props for the embedded native Odoo Gantt (right panel). loadIrFilters stays
        // false (default) so stray default groupings are NOT applied; group by stage like native.
        this.ganttProps = {
            type: "gantt",
            resModel: "project.task",
            domain: [["project_id.active", "=", true]],
            context: { group_by: ["stage_id"] },
            display: { controlPanel: false },
            noContentHelp: _t("Ingen planlagte oppgaver."),
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
            level: "balansert",
            show,
            kpis: [],
            selectedKpi: "",
            finansLines: [],      // detaljlinjer for Finans-boksen (fakturaer som krever handling)
            collapsed: this._loadCollapsed(),
            projects: [],
            projQuery: "",        // project search over the project overview
            myTasks: [],
            komm: [],
            kommPeriod: "uke",
            kommQuery: "",
            kommDir: "alle",      // alle | mottatt | sendt (direction "sent from")
            kommSender: null,     // {id, name} – filter on a single sender
            dashboards: [],       // Odoo native dashboards/analyses (only the ones that exist)
            presence: [],         // «Til stede nå» – interne brukere + tilgjengelighets-status
            actions: {},          // {nøkkel: xmlid|false} – hvilke Odoo-handlinger som finnes (guardet)
            aiQuery: "",          // «Spør AI om hjelp»-feltet
            aiAnswer: "",         // svar fra Claude via fiq.ai
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
            progProjName: "",
            aiStageNames: [],     // navn på AI-merkede stadier (fiq_ai_stage) – for velgeren
            stageHidden: {},      // {stadienavn: true} = skjult i oppgave-drillen
        });

        onWillStart(async () => {
            await this.loadConfig();   // FIQ access/setup layer (per user, server-persisted)
            await this.loadData();
        });
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
            if (cfg.accent) this.state.accent = cfg.accent;
            if (cfg.logo) this.state.logo = cfg.logo;
            if (cfg.progress_shape) this.state.progressShape = cfg.progress_shape;
            if (cfg.progress_metric) this.state.progressMetric = cfg.progress_metric;
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
        let domain = [["active", "=", true]];
        if (q) {
            const flds = ["name", ...(pOpt.includes("sequence_code") ? ["sequence_code"] : [])];
            const ors = [];
            for (let i = 0; i < flds.length - 1; i++) ors.push("|");
            flds.forEach((f) => ors.push([f, "ilike", q]));
            domain = ["&", ["active", "=", true], ...ors];
        }
        const precs = await this._read("project.project", domain,
            ["name", "task_count", "date_start", "date", ...pOpt], { limit: q ? 30 : 8, order: "create_date desc" });
        this.state.projects = precs.map((p) => ({
            id: p.id, no: p.sequence_code || "", name: p.name,
            taskCount: p.task_count || 0,
            start: p.date_start || false, end: p.date || false,
            progress: 0, status: _t("In progress"),
        }));
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
        const tOpt = await this._optFields("project.task", ["code"]);
        const recs = await this._read("project.task", [["project_id", "=", pid]],
            ["name", "date_deadline", "planned_date_begin", "stage_id", ...tOpt],
            { limit: 60, order: "planned_date_begin asc, id asc" });
        const rows = recs.map((t) => ({
            id: t.id, no: t.code || "", name: t.name,
            start: (t.planned_date_begin || "").slice(0, 10) || false,
            end: (t.date_deadline || "").slice(0, 10) || false,
            stage: t.stage_id ? t.stage_id[1] : "",
            progress: 0,
        }));
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
        if (this.state.progLevel === "oppgave") {
            this.selectEl("project.task", row.id, row.name);
        } else {
            this.pickProject(row.id, row.name);
        }
    }

    // Kilden Prosjektfremdrift-panelet itererer over (prosjekter ELLER valgt prosjekts
    // oppgaver). På oppgave-nivå filtreres skjulte stadier bort (stadie-velgeren).
    get progRows() {
        if (this.state.progLevel !== "oppgave") { return this.state.projects; }
        const hidden = this.state.stageHidden;
        return this.state.progTasks.filter((t) => !hidden[t.stage || ""]);
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
            const nm = t.stage || "(uten stadium)";
            if (!(nm in map)) { map[nm] = { name: nm, ai: ai.has(nm), hidden: !!hidden[nm], count: 0 }; order.push(nm); }
            map[nm].count += 1;
        });
        // AI-stadier først, så resten
        return order.map((n) => map[n]).sort((a, b) => (b.ai - a.ai));
    }

    toggleStage(name) {
        this.state.stageHidden[name] = !this.state.stageHidden[name];
    }

    // Project search field (right above the project overview) - debounced server search
    setProjQuery(v) {
        this.state.projQuery = v;
        clearTimeout(this._projTmr);
        this._projTmr = setTimeout(() => this._loadProjects(v), 200);
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
        this._pOpt = await this._optFields("project.project", ["sequence_code"]);
        await this._loadProjects("");

        // My open tasks with their real number (code = "T0001") + deadline warning
        const today = new Date().toISOString().slice(0, 10);
        // Har DB-en time-feltene (hr_timesheet)? → styrer om estimat-feltet vises
        this.state.hasHours = (await this._optFields("project.task", ["allocated_hours", "effective_hours"])).length === 2;
        // AI-merkede stadier (for stadie-velgeren i oppgave-drillen)
        try { this.state.aiStageNames = await this.orm.call("fiq.gui.control.config", "get_ai_stages", []); }
        catch (e) { this.state.aiStageNames = []; }
        const tOpt = await this._optFields("project.task", ["code"]);
        const trecs = await this._read("project.task",
            [["user_ids", "in", [user.userId]]],
            ["name", "project_id", "date_deadline", "planned_date_begin", ...tOpt], { limit: 10, order: "date_deadline asc" });
        const myTasks = trecs.map((t) => ({
            id: t.id, no: t.code || "", name: t.name,
            project: t.project_id ? t.project_id[1] : "",
            deadline: t.date_deadline || "",
            pfrom: (t.planned_date_begin || "").slice(0, 10),
            pto: (t.date_deadline || "").slice(0, 10),
            overdue: !!(t.date_deadline && t.date_deadline < today),
            progress: 0,
        }));
        // Ekte, config-drevet fremdrift per oppgave (lag 2)
        await this._fillProgress("project.task", myTasks);
        try { openTasks = await this.orm.searchCount("project.task", [["user_ids", "in", [user.userId]]]); } catch (e) {}

        // Communication view (email/messages on records) – filtered by period
        let komm = [];
        try { komm = await this.orm.call("fiq.gui.control.config", "get_kommunikasjon", [this.state.kommPeriod]); } catch (e) {}

        // Salg (open opportunities, else quotations) for the category KPI – guarded
        let salg = 0;
        try { salg = await this.orm.searchCount("crm.lead", [["type", "=", "opportunity"], ["active", "=", true]]); }
        catch (e) { try { salg = await this.orm.searchCount("sale.order", [["state", "in", ["draft", "sent"]]]); } catch (e2) {} }

        // Finans: leverandørfakturaer til godkjenning (draft in_invoice) + forsinkede
        // kundefakturaer (out_invoice, ikke betalt, forfalt). Guardet – account kan mangle.
        const today0 = new Date().toISOString().slice(0, 10);
        let finLev = [], finForsinket = [];
        try {
            finLev = await this._read("account.move",
                [["move_type", "=", "in_invoice"], ["state", "=", "draft"]],
                ["name", "partner_id"], { limit: 25, order: "id desc" });
        } catch (e) {}
        try {
            finForsinket = await this._read("account.move",
                [["move_type", "=", "out_invoice"], ["state", "=", "posted"],
                 ["payment_state", "in", ["not_paid", "partial"]], ["invoice_date_due", "<", today0]],
                ["name", "partner_id", "invoice_date_due"], { limit: 25, order: "invoice_date_due asc" });
        } catch (e) {}
        this.state.finansLines = [
            ...finForsinket.map((m) => ({ text: (m.name || _t("Faktura")) + " · " + (m.partner_id ? m.partner_id[1] : "") + " (" + _t("forfalt") + " " + (m.invoice_date_due || "") + ")", model: "account.move", res_id: m.id })),
            ...finLev.map((m) => ({ text: (m.name || _t("Lev.faktura")) + " · " + (m.partner_id ? m.partner_id[1] : "") + " (" + _t("til godkjenning") + ")", model: "account.move", res_id: m.id })),
        ];

        // Category KPIs (report-up / management by exception): Kommunikasjon · Prosjekt · Salg · Finans · HMS/KS
        const received = komm.filter((k) => k.direction === "mottatt");
        const overdueN = myTasks.filter((t) => t.overdue).length;
        this.state.kpis = [
            { key: "komm", v: String(komm.length), l: _t("Kommunikasjon"), sub: received.length + " " + _t("ubesvart"), dot: received.length ? "red" : "green" },
            { key: "prosjekt", v: String(active), l: _t("Prosjekt"), sub: overdueN + " " + _t("forsinket"), dot: overdueN ? "amber" : "green" },
            { key: "salg", v: String(salg), l: _t("Salg"), sub: _t("ok"), dot: "green" },
            { key: "finans", v: String(finForsinket.length + finLev.length), l: _t("Finans"), sub: finForsinket.length + " " + _t("forsinket") + " · " + finLev.length + " " + _t("til godkj."), dot: finForsinket.length ? "red" : (finLev.length ? "amber" : "green") },
            { key: "hms", v: "—", l: _t("HMS/KS"), sub: _t("avvik"), dot: "grey" },
        ];
        if (!this.state.selectedKpi) {
            const red = this.state.kpis.find((k) => k.dot === "red");
            this.state.selectedKpi = red ? red.key : "komm";
        }

        // Native dashboards/analyses (only the ones that actually exist in the DB)
        let dashboards = [];
        try { dashboards = await this.orm.call("fiq.gui.control.config", "get_dashboards", []); } catch (e) {}

        // «Til stede nå» – interne brukere + tilgjengelighets-status
        let presence = [];
        try { presence = await this.orm.call("fiq.gui.control.config", "get_presence", []); } catch (e) {}

        // Hvilke Odoo-handlinger finnes faktisk (guardet – depends = web+project)
        let actions = {};
        try { actions = await this.orm.call("fiq.gui.control.config", "get_actions", []); } catch (e) {}

        this.state.myTasks = myTasks;
        this.state.komm = komm;
        this.state.dashboards = dashboards;
        this.state.presence = presence;
        this.state.actions = actions;
        this.state.loading = false;
    }

    // Tidsbasert hilsen (norsk)
    get hilsen() {
        const h = new Date().getHours();
        if (h < 10) return _t("God morgen");
        if (h < 18) return _t("God dag");
        return _t("God kveld");
    }

    // Krever handling nå: sammendrag PER KATEGORI (styring ved unntak – rapporter opp,
    // ikke én linje per post). Rød prikk + fet kategori + kort tekst; klikk → kategori-flate.
    get handlingsposter() {
        const out = [];
        const received = this.state.komm.filter((k) => k.direction === "mottatt");
        if (received.length) {
            out.push({
                key: "kat-komm", kategori: _t("Kommunikasjon"), type: "kommunikasjon",
                text: received.length + " " + _t("ubesvart — venter svar"),
                view: "kommunikasjon",
            });
        }
        const overdue = this.state.myTasks.filter((t) => t.overdue);
        if (overdue.length) {
            out.push({
                key: "kat-prosjekt", kategori: _t("Prosjekt"), type: "oppgave",
                text: overdue.length + " " + _t("forsinkede oppgaver"),
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

    // Kollaps-tilstand huskes per bruker/nettleser (localStorage) → nullstilles IKKE
    // ved oppfrisk/re-åpning. Defensiv: tomt objekt hvis localStorage ikke er tilgjengelig.
    _loadCollapsed() {
        try { return JSON.parse(localStorage.getItem("fiq_hm_collapsed") || "{}") || {}; }
        catch (e) { return {}; }
    }

    // Skjul/vis en seksjon (kollaps ved hovedoverskrift) for å løfte fram de andre listene
    toggleCollapse(key) {
        this.state.collapsed[key] = !this.state.collapsed[key];
        try { localStorage.setItem("fiq_hm_collapsed", JSON.stringify(this.state.collapsed)); } catch (e) {}
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

    // Simple/Full mode: "enkel" shows the essentials, "total" shows advanced widgets too
    setMode(m) {
        this.state.mode = m;
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
        try {
            this.state.komm = await this.orm.call("fiq.gui.control.config", "get_kommunikasjon", [p]);
        } catch (e) { this.state.komm = []; }
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
            name: _t("Prosjekter"),
            res_model: "project.project",
            views: [[false, "kanban"], [false, "list"], [false, "form"]],
            target: "current",
        });
    }

    // Melding når en funksjon ennå ikke er ferdig (3-ukers-estimat + 75 % buffer)
    _underUtvikling() {
        this.notification.add(
            _t("Denne funksjonen er under utvikling — forventes levert: 2026-08-07"),
            { type: "info" }
        );
    }

    // Beslutningsstøtte: kjør ekte doAction hvis handlingen finnes (guardet), ellers varsel.
    // key = nøkkel fra get_actions (nytt_prosjekt/salgsordre/nytt_leads/tilbud/kunde/dokument …)
    runAction(key) {
        const xmlid = this.state.actions[key];
        if (xmlid) {
            this.action.doAction(xmlid);
        } else {
            this._underUtvikling();
        }
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
        this.state.aiAnswer = _t("Tenker …");
        try {
            const ans = await this.orm.call("fiq.ai", "chat", [q]);
            this.state.aiAnswer = ans || _t("(tomt svar)");
        } catch (e) {
            this.state.aiAnswer = _t("AI ikke tilgjengelig ennå — installer modulen fiq_ai og sett Anthropic API-nøkkel.");
        }
    }

    clearAi() {
        this.state.aiAnswer = "";
        this.state.aiQuery = "";
    }

    // Real click-through: open a record in Odoo
    openRecord(model, id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
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
            this.notification.add(_t("Kunne ikke lagre datoen — ") + this._errMsg(e), { type: "danger" });
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
            this.notification.add(_t("Kunne ikke lagre datoen — ") + this._errMsg(e), { type: "danger" });
            return;
        }
        const t = this.state.myTasks.find((x) => x.id === id);
        if (t) { if (field === "planned_date_begin") { t.pfrom = value || ""; } else { t.pto = value || ""; } }
    }

    // Dato på en oppgave i fremdrift-drillen (progTasks bruker start/end for Gantt).
    async setProgTaskDate(id, field, value) {
        const val = value ? value + " 12:00:00" : false;
        try { await this.orm.write("project.task", [id], { [field]: val }); }
        catch (e) { this.notification.add(_t("Kunne ikke lagre datoen — ") + this._errMsg(e), { type: "danger" }); return; }
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
        catch (e) { this.notification.add(_t("Kunne ikke lagre estimatet — ") + this._errMsg(e), { type: "danger" }); return; }
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
            name: mode === "gantt" ? _t("Planlegging") : _t("Tasks"),
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
            await this.loadData();
            // Hold oppgave-drillen fersk hvis den er åpen
            if (this.state.progLevel === "oppgave" && this.state.progProjId) {
                await this._loadProgTasks(this.state.progProjId);
            }
        } finally { this.state.refreshing = false; }
    }

    setView(v) {
        this.state.view = v;
    }

    setRightView(v) {
        this.state.rightView = v;
    }

    // Velg element -> vises i inspektor-panelet (Detaljer). Henter ekte beskrivelse.
    // Full post apnes med openRecord (⤢).
    async selectEl(model, id, name) {
        this.state.selected = { model, id, name };
        this.state.selDet = { beskrivelse: "", logg: [], epost: [], dok: [] };
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

    // ---- Egen kompakt Gantt (høyre panel). Vindu styres av periode-toggle (kommPeriod). ----
    get ganttWindow() {
        const p = this.state.kommPeriod;
        const now = new Date();
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

    get ganttTicks() {
        const p = this.state.kommPeriod;
        const { start, end } = this.ganttWindow;
        const span = (end - start) || 1;
        const pct = (t) => ((t - start) / span) * 100;
        const ticks = [];
        if (p === "alle") {
            const y = new Date(start).getFullYear();
            const mn = ["Jan","Feb","Mar","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Des"];
            for (let m = 0; m < 12; m++) ticks.push({ label: mn[m], left: pct(new Date(y, m, 1).getTime()) });
        } else if (p === "maaned") {
            let d = new Date(start);
            while (d.getTime() < end) {
                ticks.push({ label: d.getDate() + ".", left: pct(d.getTime()) });
                const nx = new Date(d); nx.setDate(d.getDate() + 7); d = nx;
            }
        } else {
            const wd = ["Ma","Ti","On","To","Fr","Lø","Sø"];
            for (let i = 0; i < 7; i++) ticks.push({ label: wd[i], left: pct(start + i * 86400000) });
        }
        return ticks;
    }

    get ganttRows() {
        const { start, end } = this.ganttWindow;
        const span = (end - start) || 1;
        return this.progRows.map((p) => {
            const s = p.start ? new Date(p.start).getTime() : null;
            const e = p.end ? new Date(p.end).getTime() : null;
            if (s === null && e === null) {
                return { id: p.id, no: p.no, name: p.name, hasDates: false, start: p.start || false, end: p.end || false };
            }
            const bs = s !== null ? s : e;
            const be = e !== null ? e : s;
            let left = Math.max(0, Math.min(100, ((bs - start) / span) * 100));
            let right = Math.max(0, Math.min(100, ((be - start) / span) * 100));
            return { id: p.id, no: p.no, name: p.name, hasDates: true, start: p.start || false, end: p.end || false,
                     leftPct: left, widthPct: Math.max(1.5, right - left), progress: p.progress };
        });
    }

    // Metadata (ikon/farge + tittel) for gjeldende fagflate-visning; null for oversikt/kommunikasjon
    get area() {
        const map = {
            prosjekt: { icon: "prj.png", title: _t("Prosjekter") },
            crm: { icon: "crm.png", title: "CRM" },
            salgsmuligheter: { icon: "crm_leads.png", title: _t("Salgsmuligheter") },
            salgsordre: { icon: "crm_so.png", title: _t("Salgsordrer") },
            regnskap: { icon: "rgs.png", title: _t("Regnskap") },
            // SP-fagområder (rutenett i sidemenyen) – integrerte placeholders inntil egne flater
            omr_ledelse: { color: "#0070C0", title: _t("1 Ledelse") },
            omr_admin: { color: "#6b7280", title: _t("2 Administrasjon") },
            omr_log: { color: "#70AD47", title: _t("4 Logistikk") },
            omr_mar: { color: "#ED7D31", title: _t("5 Marked") },
            omr_salg: { color: "#CC0000", title: _t("6 Salg") },
            omr_fag: { color: "#7030A0", title: _t("8 Fag") },
        };
        return map[this.state.view] || null;
    }

    // SP-fagområder for sidemeny-rutenettet (nummer + navn + kanonisk farge)
    get fagomrader() {
        return [
            { view: "omr_ledelse", nr: "1", navn: _t("Ledelse"), farge: "#0070C0" },
            { view: "omr_admin", nr: "2", navn: _t("Admin"), farge: "#6b7280" },
            { view: "omr_log", nr: "4", navn: "LOG", farge: "#70AD47" },
            { view: "omr_mar", nr: "5", navn: "MAR", farge: "#ED7D31" },
            { view: "omr_salg", nr: "6", navn: _t("Salg"), farge: "#CC0000" },
            { view: "omr_fag", nr: "8", navn: "FAG", farge: "#7030A0" },
        ];
    }

    openOdoo() {
        // Shortcut to Odoo's native app menu
        window.location.href = "/odoo";
    }
}

registry.category("actions").add("fiq_gui_control_dashboard", FiqControlRoom);
