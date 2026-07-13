/** @odoo-module **/

// Meldingssenter — NATIVE OWL-flate (porter V00.04-designet, viser EKTE data).
// Erstatter iframe-skissen: henter bokser/meldinger/presence via fiq.meldingssenter.data
// og rendrer topplinje (firma-velger + til-stede) · bokser (basis + tverrgående + 0–8)
// · meldingsliste · lesepanel. Farger fra fargekart (scss). Dynamiske bokser (skjul tomme).

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
            loading: true,
            firms: [],
            current_firm: false,
            presence: [],
            user: "",
            basis: [],
            tverr: [],
            taks: [],
            aktivBoks: false,
            meldinger: [],
            valgt: false,
            period: "alle",
        });
        onWillStart(async () => {
            const cfg = await this.orm.call(DATA, "get_my_config", []);
            Object.assign(this.state, cfg, { loading: false });
            await this.lastBokser();
        });
    }

    async lastBokser() {
        const b = await this.orm.call(DATA, "get_boxes", [], {
            firm: this.state.current_firm, period: this.state.period,
        });
        this.state.basis = b.basis;
        this.state.tverr = b.tverrgaende;
        this.state.taks = b.taksonomi;
    }

    async byttFirma(ev) {
        this.state.current_firm = parseInt(ev.target.value) || false;
        this.state.aktivBoks = false;
        this.state.meldinger = [];
        this.state.valgt = false;
        await this.lastBokser();
    }

    async aapneBoks(kode) {
        this.state.aktivBoks = kode;
        this.state.valgt = false;
        this.state.meldinger = await this.orm.call(DATA, "get_messages", [], {
            boks: kode, firm: this.state.current_firm, period: this.state.period,
        });
    }

    velgMelding(m) {
        this.state.valgt = m;
    }

    async svar(replyAll) {
        if (!this.state.valgt) return;
        const act = await this.orm.call(DATA, "svar", [this.state.valgt.id, replyAll]);
        if (act) this.action.doAction(act);
    }

    tilbakeKR() {
        this.action.doAction("fiq_gui_control.action_fiq_gui_control");
    }
}

registry.category("actions").add("fiq_gui_epost_dashboard", FiqMeldingssenter);
