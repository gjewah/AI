/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

// FIQ GUI E-post/Kommunikasjon – minimalt skjelett (placeholder). Klart for ekte funksjonalitet.
export class FiqGuiEpost extends Component {
    static template = "fiq_gui_epost.Dashboard";
    static props = ["*"];

    setup() {
        this.flate = "E-post/Kommunikasjon";
    }
}

registry.category("actions").add("fiq_gui_epost_dashboard", FiqGuiEpost);
