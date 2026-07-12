/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

// Registry-kategorien der HVER flate registrerer innmaten sin:
//   registry.category("fiq_gui_flates").add(key, {key, label, color, sequence, Component})
const FLATE_CATEGORY = "fiq_gui_flates";

// Demo-tilstede (byttes med ekte hr.attendance i native versjon).
const PRESENCE = [
    { init: "GEW", navn: "Gjermund E. Wæhre", status: "til" },
    { init: "SSK", navn: "Sindre Skåret", status: "til" },
    { init: "FOL", navn: "Frank Olsen", status: "mote" },
    { init: "KHA", navn: "Kari Hansen", status: "fra" },
    { init: "OBE", navn: "Ola Berg", status: "til" },
];

// Demo-firma (byttes med res.company + logo/IQ-farge i native versjon).
const FIRMS = [
    { code: "012", navn: "FIQ", color: "#CC0000" },
    { code: "040", navn: "Vidir", color: "#38B44A" },
    { code: "049", navn: "SDV", color: "#1F6B3B" },
    { code: "060", navn: "JPC", color: "#4C9BE0" },
    { code: "00", navn: "Alle", color: "#7030A0" },
];

// Det DELTE V00.04-skallet. Eier chromen (presence + firma-band + sidemeny) + en slot.
export class FiqGuiShell extends Component {
    static template = "fiq_gui_shell.Shell";
    static props = ["*"];

    setup() {
        this.flates = registry
            .category(FLATE_CATEGORY)
            .getAll()
            .sort((a, b) => (a.sequence || 50) - (b.sequence || 50));
        this.presence = PRESENCE;
        this.firms = FIRMS;
        this.state = useState({
            current: this.flates.length ? this.flates[0].key : false,
            firm: "012",
            theme: this._loadTheme(),
        });
    }

    get currentFlate() {
        return this.flates.find((f) => f.key === this.state.current) || false;
    }
    get currentComponent() {
        return this.currentFlate ? this.currentFlate.Component : false;
    }
    get currentFirm() {
        return this.firms.find((f) => f.code === this.state.firm) || this.firms[0];
    }

    // Klikk i sidemenyen bytter INNMAT — ikke hele siden. Det er kjernen i Vei C.
    selectFlate(key) {
        this.state.current = key;
    }
    selectFirm(code) {
        this.state.firm = code;
    }
    toggleTheme() {
        this.state.theme = this.state.theme === "dark" ? "light" : "dark";
        try {
            localStorage.setItem("fiq-theme", this.state.theme);
        } catch (e) {
            // stille — låst tema er en preferanse, ikke kritisk
        }
    }
    _loadTheme() {
        try {
            return localStorage.getItem("fiq-theme") || "light";
        } catch (e) {
            return "light";
        }
    }
}

registry.category("actions").add("fiq_gui_shell", FiqGuiShell);
