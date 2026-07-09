/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * «Tilbake til Kontrollrommet» — uthevet knapp i Odoos topplinje (systray).
 * Synlig i ALLE native visninger så brukeren alltid finner veien hjem til skallet.
 * Tekst via template → oversettbar (nb_NO, lt_LT m.fl. — portalmeny for SDV Litauen).
 */
export class FiqControlRoomSystray extends Component {
    static template = "fiq_gui_control.Systray";
    static props = {};

    setup() {
        this.action = useService("action");
    }

    openControlRoom() {
        this.action.doAction("fiq_gui_control.action_fiq_gui_control");
    }
}

registry.category("systray").add(
    "fiq_gui_control.systray",
    { Component: FiqControlRoomSystray },
    { sequence: 1 }
);
