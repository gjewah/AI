/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";

// FIQ GUI Regnskap — flate 2.80. VISNINGEN av rolla «0.00 2.80 AI Regnskap-Rådgiver».
// Rolle bak, flate foran. Native-først: tallene eies av Odoo (account.move), ikke av flaten.
//
// 🛑 Rollens egen regel: «ALDRI gjett — regnskap er juridisk bindende.»
//    Bokførte tall og framskrivning holdes visuelt fra hverandre.

// Likviditets-bøttene Gjermund spesifiserte.
const BOTTER = [
    { key: "inn", label: "Inngående", kilde: "Kundefakturaer (account.move) — ikke koblet" },
    { key: "ut", label: "Utgående", kilde: "Leverandørfakturaer (account.move) — ikke koblet" },
    { key: "haster", label: "Haster", kilde: "Forfall nær / passert — ikke koblet" },
    { key: "kritisk", label: "Kritisk", kilde: "Forfalt + beløpsterskel — ikke koblet" },
    { key: "ubetalt", label: "Ubetalt", kilde: "Åpne poster — ikke koblet" },
];

// Cashflow LYVER hvis disse mangler (Gjermunds ord). Lønn er egen gate:
// aggregater slipper gjennom, individuell lønns-PII gjør det ALDRI.
const FORPLIKTELSER = [
    { key: "lonn", label: "Lønnskjøringer", gate: true },
    { key: "avgift", label: "Sosiale avgifter", gate: true },
    { key: "ferie", label: "Feriepenger", gate: true },
    { key: "pensjon", label: "Pensjon", gate: true },
];

export class FiqGuiRgs extends Component {
    static template = "fiq_gui_rgs.Flate";
    static props = ["*"];

    setup() {
        this.botter = BOTTER;
        this.forpliktelser = FORPLIKTELSER;
        this.state = useState({ visForpliktelser: true });
    }

    // Skallet sender inn valgt firma; flaten eier ALDRI firma-valget selv.
    // company_id hentes fra sesjonen i Odoo — aldri som parameter utenfra (tenant-isolasjon).
    get firma() {
        return this.props.firm || "—";
    }
}

registry.category("actions").add("fiq_gui_rgs_dashboard", FiqGuiRgs);

// Registrering i det delte skallet (fast hovedmeny, Vei C).
// Kontrakt verifisert mot fiq_gui_shell/static/src/shell.js:7 + demo_flates.js.
// Farge #4472C4 = finans-familien (2.70/2.80), jf. rollefilene + control_room.js:17.
// MERK: demo_flates.js registrerer i dag "regnskap" med demo-innmat og farge #ED7D31.
// Denne ekte flaten overtar nøkkelen — jf. demo-fila: «I native versjon registrerer HVER
// ekte flate sin egen innmat-komponent her i stedet for denne.»
registry.category("fiq_gui_flates").add("regnskap", {
    key: "regnskap",
    label: "Regnskap",
    color: "#4472C4",
    sequence: 60,
    Component: FiqGuiRgs,
}, { force: true });
