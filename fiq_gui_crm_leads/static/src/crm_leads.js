/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";

// FIQ GUI CRM salgsmuligheter – minimalt skjelett (placeholder). Klart for ekte funksjonalitet.
export class FiqGuiCrmLeads extends Component {
    static template = "fiq_gui_crm_leads.Dashboard";
    static props = ["*"];

    setup() {
        this.flate = "Salgsmuligheter";
    }
}

registry.category("actions").add("fiq_gui_crm_leads_dashboard", FiqGuiCrmLeads);
