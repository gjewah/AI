/** @odoo-module **/

// Meldingssenter — native OWL-flate, V00.04-designet, EKTE data.
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DATA = "fiq.meldingssenter.data";

export class FiqMeldingssenter extends Component {
    static template = "fiq_gui_epost.MsgSenter";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true, firms: [], current_firm: false, presence: [], user: "", logo: "", q: "",
            basis: [], tverr: [], taks: [],
            aktivBoks: false, aktivNavn: "", meldinger: [], valgt: false, period: "alle",
            group: "avsender", kollaps: {}, kandidater: { prosjekt: [], oppgave: [] },
        });
        onWillStart(async () => {
            const cfg = await this.orm.call(DATA, "get_my_config", []);
            Object.assign(this.state, cfg, { loading: false });
            await this.lastBokser();
        });
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
        if (f && f.logo) this.state.logo = f.logo;   // bytt logo når du bytter firma
        this.state.aktivBoks = false; this.state.meldinger = []; this.state.valgt = false;
        await this.lastBokser();
    }

    async aapneBoks(kode, navn) {
        this.state.aktivBoks = kode; this.state.aktivNavn = navn;
        this.state.valgt = false; this.state.q = "";
        await this.lastMeldinger();
    }

    async lastMeldinger() {
        if (!this.state.aktivBoks) return;
        this.state.meldinger = await this.orm.call(DATA, "get_messages", [], {
            boks: this.state.aktivBoks, firm: this.state.current_firm,
            period: this.state.period, q: this.state.q || false });
    }

    sok(ev) {
        this.state.q = (ev.target.value || "").trim();
        this.lastMeldinger();
    }

    lukkDrill() { this.state.aktivBoks = false; this.state.valgt = false; }

    async velgMelding(m) {
        this.state.valgt = m;
        this.state.kandidater = { prosjekt: [], oppgave: [] };
        this.state.kandidater = await this.orm.call(DATA, "get_kandidater", [m.id]);
    }

    // Grupper etter (sortering): avsender · prosjekt/element · dato · type
    setGroup(ev) { this.state.group = ev.target.value; this.state.kollaps = {}; }
    toggleGroup(k) { this.state.kollaps[k] = !this.state.kollaps[k]; }
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

    async svar(replyAll) {
        if (!this.state.valgt) return;
        const act = await this.orm.call(DATA, "svar", [this.state.valgt.id, replyAll]);
        if (act) this.action.doAction(act);
    }

    tilbakeKR() { this.action.doAction("fiq_gui_control.action_fiq_gui_control"); }
    aapneKalender() { this.action.doAction("calendar.action_calendar_event"); }
    aapneInnstillinger() { this.action.doAction("base_setup.action_general_configuration"); }

    // Hjelpere
    initialer(navn) {
        return (navn || "?").split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
    }
    pcls(status) {
        return status === "online" ? "til" : (status === "away" ? "mote" : "fra");
    }
}

registry.category("actions").add("fiq_gui_epost_dashboard", FiqMeldingssenter);
