/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

// FIQ GUI CRM salgsordre – minimalt skjelett (placeholder). Klart for ekte funksjonalitet.
export class FiqGuiCrmSo extends Component {
    static template = "fiq_gui_crm_so.Dashboard";
    static props = ["*"];

    setup() {
        this.flate = "CRM salgsordre";
    }
}

registry.category("actions").add("fiq_gui_crm_so_dashboard", FiqGuiCrmSo);
