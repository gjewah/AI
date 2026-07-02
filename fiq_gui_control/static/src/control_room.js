/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

const WIDGETS = ["kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"];

export class FiqControlRoom extends Component {
    static template = "fiq_gui_control.ControlRoom";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

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
            projects: [],
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
            view: "oversikt",     // main content: oversikt (overview) | kommunikasjon (communication)
            loading: true,
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

    async loadData() {
        let active = 0, openTasks = 0;
        try { active = await this.orm.searchCount("project.project", [["active", "=", true]]); } catch (e) {}

        // Projects with their real number (sequence_code = "Project No.") – human syntax
        const precs = await this._read("project.project", [["active", "=", true]],
            ["name", "sequence_code", "task_count"], { limit: 8, order: "create_date desc" });
        const projects = precs.map((p) => ({
            id: p.id, no: p.sequence_code || "", name: p.name,
            taskCount: p.task_count || 0,
            progress: Math.min(100, (p.task_count || 0) * 8), status: _t("In progress"),
        }));

        // My open tasks with their real number (code = "T0001") + deadline warning
        const today = new Date().toISOString().slice(0, 10);
        const trecs = await this._read("project.task",
            [["user_ids", "in", [user.userId]]],
            ["name", "code", "project_id", "date_deadline"], { limit: 10, order: "date_deadline asc" });
        const myTasks = trecs.map((t) => ({
            id: t.id, no: t.code || "", name: t.name,
            project: t.project_id ? t.project_id[1] : "",
            deadline: t.date_deadline || "",
            overdue: !!(t.date_deadline && t.date_deadline < today),
        }));
        try { openTasks = await this.orm.searchCount("project.task", [["user_ids", "in", [user.userId]]]); } catch (e) {}

        this.state.kpis = [
            { v: String(active), l: _t("Active projects") },
            { v: String(openTasks), l: _t("My tasks") },
            { v: String(myTasks.filter((t) => t.overdue).length), l: _t("Overdue") },
            { v: "—", l: _t("ROI (soon)") },
        ];
        // Communication view (email/messages on records) – filtered by period
        let komm = [];
        try { komm = await this.orm.call("fiq.gui.control.config", "get_kommunikasjon", [this.state.kommPeriod]); } catch (e) {}

        // Native dashboards/analyses (only the ones that actually exist in the DB)
        let dashboards = [];
        try { dashboards = await this.orm.call("fiq.gui.control.config", "get_dashboards", []); } catch (e) {}

        // «Til stede nå» – interne brukere + tilgjengelighets-status
        let presence = [];
        try { presence = await this.orm.call("fiq.gui.control.config", "get_presence", []); } catch (e) {}

        // Hvilke Odoo-handlinger finnes faktisk (guardet – depends = web+project)
        let actions = {};
        try { actions = await this.orm.call("fiq.gui.control.config", "get_actions", []); } catch (e) {}

        this.state.projects = projects;
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

    // Krever handling nå: forsinkede oppgaver + siste mottatte kommunikasjon (kontekst-linjer)
    get handlingsposter() {
        const out = [];
        this.state.myTasks.filter((t) => t.overdue).forEach((t) => {
            out.push({
                key: "task-" + t.id,
                type: "oppgave",
                text: _t("Forsinket oppgave") + ": " + (t.no ? t.no + " " : "") + t.name,
                sub: t.project || "",
                model: "project.task", res_id: t.id,
            });
        });
        this.state.komm.filter((k) => k.direction === "mottatt").slice(0, 4).forEach((k) => {
            out.push({
                key: "komm-" + k.id,
                type: "kommunikasjon",
                text: _t("Ubesvart") + ": " + k.subject,
                sub: k.author + (k.element ? " · " + k.element : ""),
                model: k.model, res_id: k.res_id,
            });
        });
        return out;
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
        this.action.doAction("project.open_view_project_all");
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

    // «Spør AI om hjelp» – AI-flate ennå ikke koblet
    askAi() {
        this._underUtvikling();
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

    // Click a project → its tasks. mode="gantt" opens the Gantt view.
    openProjectTasks(pid, mode) {
        const views = mode === "gantt"
            ? [[false, "gantt"], [false, "list"], [false, "form"]]
            : [[false, "list"], [false, "form"]];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("Tasks"),
            res_model: "project.task",
            domain: [["project_id", "=", pid]],
            views: views,
            target: "current",
        });
    }

    // Open one of Odoo's native dashboards/analyses in-page (SSOT)
    openDashboard(xmlid) {
        this.action.doAction(xmlid);
    }

    setView(v) {
        this.state.view = v;
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
