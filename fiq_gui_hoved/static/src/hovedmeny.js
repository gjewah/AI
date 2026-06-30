/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

const WIDGETS = ["kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"];

export class FiqHovedmeny extends Component {
    static template = "fiq_gui_hoved.Hovedmeny";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        const show = {};
        WIDGETS.forEach((w) => (show[w] = true));

        this.state = useState({
            accent: "#38B44A",
            logo: null,
            companyName: "",
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
            kommDir: "alle",      // alle | mottatt | sendt (retning «sendt fra»)
            kommSender: null,     // {id, name} – filtrer på én avsender
            dashboards: [],       // Odoos native dashboards/analyser (kun de som finnes)
            loading: true,
        });

        onWillStart(async () => {
            await this.loadConfig();   // FIQ rettighets-/oppsett-lag (per bruker, server-persistert)
            await this.loadData();
        });
    }

    async loadConfig() {
        try {
            const cfg = await this.orm.call("fiq.gui.hoved.config", "get_my_config", []);
            this.state.show = cfg.show;
            this.state.level = cfg.level;
            this.state.isAdmin = cfg.is_admin;
            this.state.companyName = cfg.company_name || "";
            if (cfg.accent) this.state.accent = cfg.accent;
            if (cfg.logo) this.state.logo = cfg.logo;
        } catch (e) {
            // behold standard (alt synlig) hvis modellen ikke er klar
        }
    }

    async _read(model, domain, fields, opts) {
        // Defensiv lesing: faller tilbake uten valgfrie felt hvis de ikke finnes i kundens DB
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

        // Prosjekter med ekte nummer (sequence_code = «Project No.») – menneskelig syntaks
        const precs = await this._read("project.project", [["active", "=", true]],
            ["name", "sequence_code", "task_count"], { limit: 8, order: "create_date desc" });
        const projects = precs.map((p) => ({
            id: p.id, no: p.sequence_code || "", name: p.name,
            taskCount: p.task_count || 0,
            progress: Math.min(100, (p.task_count || 0) * 8), status: "Pågår",
        }));

        // Mine åpne oppgaver med ekte oppgavenr (code = «T0001») + frist-varsel
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
            { v: String(active), l: "Aktive prosjekter" },
            { v: String(openTasks), l: "Mine oppgaver" },
            { v: String(myTasks.filter((t) => t.overdue).length), l: "Forsinket" },
            { v: "—", l: "ROI (kommer)" },
        ];
        // Kommunikasjon-flate (e-post/meldinger på elementer) – filtrert på periode
        let komm = [];
        try { komm = await this.orm.call("fiq.gui.hoved.config", "get_kommunikasjon", [this.state.kommPeriod]); } catch (e) {}

        // Native dashboards/analyser (kun de som faktisk finnes i DB-en)
        let dashboards = [];
        try { dashboards = await this.orm.call("fiq.gui.hoved.config", "get_dashboards", []); } catch (e) {}

        this.state.projects = projects;
        this.state.myTasks = myTasks;
        this.state.komm = komm;
        this.state.dashboards = dashboards;
        this.state.loading = false;
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

    setKommDir(d) {
        this.state.kommDir = d;
    }

    // Klikk på avsender → vis kun denne avsenderens kommunikasjon (toggle av/på)
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
            this.state.komm = await this.orm.call("fiq.gui.hoved.config", "get_kommunikasjon", [p]);
        } catch (e) { this.state.komm = []; }
    }

    async replyTo(messageId, replyAll) {
        const act = await this.orm.call("fiq.gui.hoved.config", "action_reply", [messageId, !!replyAll]);
        this.action.doAction(act);
    }

    toggleCustomize() {
        this.state.customize = !this.state.customize;
    }

    toggleWidget(w) {
        this.state.show[w] = !this.state.show[w];
        // Lagre per bruker på serveren (governert av rettighetsgrupper + record rule)
        this.orm.call("fiq.gui.hoved.config", "set_widget", [w, this.state.show[w]]).catch(() => {});
    }

    openProjects() {
        this.action.doAction("project.open_view_project_all");
    }

    // Ekte klikk-gjennom: åpne et element (record) i Odoo
    openRecord(model, id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // Klikk prosjekt → oppgavene for det prosjektet. mode="gantt" åpner Gantt-visning.
    openProjectTasks(pid, mode) {
        const views = mode === "gantt"
            ? [[false, "gantt"], [false, "list"], [false, "form"]]
            : [[false, "list"], [false, "form"]];
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Oppgaver",
            res_model: "project.task",
            domain: [["project_id", "=", pid]],
            views: views,
            target: "current",
        });
    }

    // Åpne en av Odoos native dashboards/analyser in-page (SSOT)
    openDashboard(xmlid) {
        this.action.doAction(xmlid);
    }

    openOdoo() {
        // Snarvei til Odoos native app-meny
        window.location.href = "/odoo";
    }
}

registry.category("actions").add("fiq_gui_hoved_dashboard", FiqHovedmeny);
