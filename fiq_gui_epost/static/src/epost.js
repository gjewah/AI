/** @odoo-module **/

// Meldingssenter — tre-side-modell: OVERSIKT (hjul) → MAIL → ANSATT.
// Oversikten er lett (hjul + til stede); tungt arbeid får egen side med «tilbake».
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DATA = "fiq.meldingssenter.data";
// Fargekart → hex (til conic-gradient i hjulene)
const FARGE = {
    graa: "#7A8593", blaa: "#0070C0", lilla: "#7030A0", gronn: "#70AD47", oransje: "#ED7D31",
    rod: "#CC0000", amber: "#B4791A", slate: "#64748b", tealx: "#0D9488", crit: "#C7413B",
};

export class FiqMeldingssenter extends Component {
    static template = "fiq_gui_epost.MsgSenter";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            view: "oversikt",                       // oversikt | mail | ansatt
            loading: true, firms: [], current_firm: false, presence: [], user: "", logo: "",
            basis: [], tverr: [], taks: [],
            aktivBoks: false, aktivNavn: "", meldinger: [], valgt: false, period: "alle", q: "",
            ansatt: null,
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
        this.state.basis = b.basis; this.state.tverr = b.tverrgaende; this.state.taks = b.taksonomi;
    }

    async byttFirma(id) {
        this.state.current_firm = id;
        const f = this.state.firms.find(x => x.id === id);
        if (f && f.logo) this.state.logo = f.logo;
        await this.lastBokser();
    }

    // ---- Navigering mellom de tre sidene ----
    async aapneMail(kode, navn) {
        this.state.view = "mail"; this.state.aktivBoks = kode; this.state.aktivNavn = navn;
        this.state.valgt = false; this.state.q = "";
        await this.lastMeldinger();
    }
    async aapneAnsatt(id) {
        const a = await this.orm.call(DATA, "get_ansatt", [id]);
        if (!a || !a.id) return;                 // tom respons → ikke bytt side
        this.state.ansatt = a; this.state.view = "ansatt";
    }
    tilOversikt() {
        this.state.view = "oversikt"; this.state.aktivBoks = false;
        this.state.valgt = false; this.state.ansatt = null;
    }

    async lastMeldinger() {
        if (!this.state.aktivBoks) return;
        this.state.meldinger = await this.orm.call(DATA, "get_messages", [], {
            boks: this.state.aktivBoks, firm: this.state.current_firm,
            period: this.state.period, q: this.state.q || false });
    }
    sok(ev) { this.state.q = (ev.target.value || "").trim(); this.lastMeldinger(); }

    velgMelding(m) { this.state.valgt = m; }

    async svar(replyAll) {
        if (!this.state.valgt) return;
        const act = await this.orm.call(DATA, "svar", [this.state.valgt.id, replyAll]);
        if (act) this.action.doAction(act);
    }

    // ---- Sidemeny / native handlinger ----
    aapneKalender() { this.action.doAction("calendar.action_calendar_event"); }
    aapneInnstillinger() { this.action.doAction("base_setup.action_general_configuration"); }
    tilbakeKR() { this.action.doAction("fiq_gui_control.action_fiq_gui_control"); }

    // ---- Hjul (donut) ----
    // Bygg conic-gradient fra bokser (tomme utelatt). Returnerer style-streng.
    hjul(items) {
        const it = (items || []).filter(b => b.count > 0);
        const tot = it.reduce((s, b) => s + b.count, 0) || 1;
        let acc = 0; const stops = [];
        for (const b of it) {
            const a = acc / tot * 100, e = (acc + b.count) / tot * 100;
            stops.push(`${FARGE[b.farge] || "#888"} ${a}% ${e}%`); acc += b.count;
        }
        if (!stops.length) stops.push("var(--line) 0 100%");
        return "background:conic-gradient(" + stops.join(",") + ")";
    }
    total(items) { return (items || []).reduce((s, b) => s + (b.count || 0), 0); }
    ikkeTom(items) { return (items || []).filter(b => b.count > 0); }
    basisWheel() { return (this.state.basis || []).filter(b => b.kode !== "uleste"); }
    fargeHex(k) { return FARGE[k] || "var(--accent)"; }

    initialer(navn) {
        return (navn || "?").split(/\s+/).map(w => w[0]).join("").slice(0, 2).toUpperCase();
    }
}

registry.category("actions").add("fiq_gui_epost_dashboard", FiqMeldingssenter);
