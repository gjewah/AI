/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// FIQ GUI Regnskap — flate 2.80. VISNINGEN av rolla «0.00 2.80 AI Regnskap-Rådgiver».
// Rolle bak, flate foran. Native-først: tallene eies av Odoo (account.move).
//
// 🛑 Rollens egen regel: «ALDRI gjett — regnskap er juridisk bindende.»
//    Alt som vises her er BOKFØRT (state=posted). Framskrivning er merket separat.

// Cashflow LYVER hvis disse mangler (Gjermunds ord). Lønn er egen gate:
// aggregater slipper gjennom, individuell lønns-PII gjør det ALDRI.
// Ingen rolle EIER lønn ennå → linjene står bevisst ukoblet, ikke gjettet.
const FORPLIKTELSER = [
    { key: "lonn", label: "Lønnskjøringer" },
    { key: "avgift", label: "Sosiale avgifter" },
    { key: "ferie", label: "Feriepenger" },
    { key: "pensjon", label: "Pensjon" },
];

export class FiqGuiRgs extends Component {
    static template = "fiq_gui_rgs.Flate";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.forpliktelser = FORPLIKTELSER;
        this.state = useState({ laster: true, data: null, kritiske: [], feil: null });

        onWillStart(async () => {
            try {
                // company_id sendes ALDRI med — serveren tar den fra sesjonen.
                const [data, kritiske] = await Promise.all([
                    this.orm.call("fiq.gui.rgs.data", "hent_grunnbilde", []),
                    this.orm.call("fiq.gui.rgs.data", "hent_kritiske_poster", []),
                ]);
                this.state.data = data;
                this.state.kritiske = kritiske;
            } catch (e) {
                // Feil skjules ALDRI bak et tomt tall — et blankt felt ville sett ut
                // som «null kroner utestående», og det er en farlig løgn i regnskap.
                this.state.feil = e.message?.data?.message || e.message || String(e);
            } finally {
                this.state.laster = false;
            }
        });
    }

    /** Beløp i hele kroner med tusenskille — norsk format, ingen desimalstøy. */
    format(verdi) {
        if (verdi === null || verdi === undefined) {
            return "—";
        }
        return new Intl.NumberFormat("nb-NO", { maximumFractionDigits: 0 }).format(verdi);
    }

    get valuta() {
        return this.state.data?.valuta || "";
    }

    // Skallet sender inn valgt firma til visning; flaten eier ALDRI firma-valget.
    // Det ekte firmaet kommer fra serveren (sesjonen) — se hent_grunnbilde().
    get firma() {
        return this.state.data?.firma || this.props.firm || "—";
    }
}

registry.category("actions").add("fiq_gui_rgs_dashboard", FiqGuiRgs);

// HENDELSE 2026-07-18: min force:true her ga Gjermund BLANK SKJERM i Odoo.
// Demo-flatene registrerte også "regnskap" → kollisjon i registeret. Gjermund fant
// rotårsaken selv i nettleser-konsollen (9968032) og fjernet demo-«regnskap».
// force er derfor FJERNET: nå er fiq_gui_rgs eneste eier av nøkkelen, og en ekte
// kollisjon SKAL kaste feil så den oppdages — ikke overskrives i stillhet.
registry.category("fiq_gui_flates").add("regnskap", {
    key: "regnskap",
    label: "Regnskap",
    color: "#4472C4",
    sequence: 60,
    Component: FiqGuiRgs,
});
