/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

// FIQ GUI CRM – minimalt skjelett (placeholder). Klart for ekte funksjonalitet.
export class FiqGuiCrm extends Component {
    static template = "fiq_gui_crm.Dashboard";
    static props = ["*"];

    setup() {
        this.flate = "CRM";
    }
}

registry.category("actions").add("fiq_gui_crm_dashboard", FiqGuiCrm);
