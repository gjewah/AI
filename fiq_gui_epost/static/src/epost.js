/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

// Meldingssenter V00.04.
// Den godkjente V00.04-flaten serveres av controlleren /fiq_gui_epost/v0104 og vises
// isolert (egen ramme) inne i Odoo. Gir en LEVENDE V00.04 uten å røre KR-koden (6.7xx).
// Jf. beslutnings-notatet "Skal V00.04 bli KR-master?" – Alt C (gradvis).
export class FiqMeldingssenter extends Component {
    static template = "fiq_gui_epost.MsgSenter";
    static props = ["*"];

    setup() {
        this.src = "/fiq_gui_epost/v0104";
    }
}

// Samme handling-tag som skjelettet → eksisterende ir.actions.client + KR-sidemenyen fungerer.
registry.category("actions").add("fiq_gui_epost_dashboard", FiqMeldingssenter);
