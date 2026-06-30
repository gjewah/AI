/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

// FIQ GUI Regnskap – minimalt skjelett (placeholder). Klart for ekte funksjonalitet.
export class FiqGuiRgs extends Component {
    static template = "fiq_gui_rgs.Dashboard";
    static props = ["*"];

    setup() {
        this.flate = "Regnskap";
    }
}

registry.category("actions").add("fiq_gui_rgs_dashboard", FiqGuiRgs);
