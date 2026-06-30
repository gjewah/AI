/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

// FIQ GUI Prosjekt – minimalt skjelett (placeholder). Klart for ekte funksjonalitet.
export class FiqGuiPrj extends Component {
    static template = "fiq_gui_prj.Dashboard";
    static props = ["*"];

    setup() {
        this.flate = "Prosjekt";
    }
}

registry.category("actions").add("fiq_gui_prj_dashboard", FiqGuiPrj);
