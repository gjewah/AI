/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// FIQ GUI Finans — flate 2.70. VISNINGEN av rolla «0.00 2.70 AI Finans-Rådgiver».
// Rolle bak, flate foran: ingen finanslogikk bygges her som Odoo alt eier (native-først).
//
// TIDSAKSER (Gjermunds spesifikasjon): 01 Fortid · 02 Nåtid · 03 Fremtid.
// Nummerering er rent numerisk (aldri bokstaver) — husets regel.
const TIDSAKSER = [
    { key: "01", label: "01 Fortid", hint: "Gode og dårlige avgjørelser — hva lærte vi?" },
    { key: "02", label: "02 Nåtid", hint: "Bransje · nye reguleringer · kunder med faresignaler" },
    { key: "03", label: "03 Fremtid", hint: "3/6/12 mnd — kursen endres vs. ikke" },
];

// Datakilder er IKKE koblet i UTKAST 01. Flaten viser rammeverket + hvilken kilde
// hvert felt SKAL ha, så ingen forveksler en tom flate med et regnskapstall.
export class FiqGuiFin extends Component {
    static template = "fiq_gui_fin.Flate";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.tidsakser = TIDSAKSER;
        this.state = useState({
            akse: "03",           // Fremtid først: høyest verdi for styret.
            kpi: null,            // {rapporter: [...], antall_valgt: n}
            velgerApen: false,
            kpiFeil: null,
        });

        onWillStart(async () => {
            try {
                this.state.kpi = await this.orm.call("fiq.gui.fin.data", "hent_kpi_valg", []);
            } catch (e) {
                // Feil skjules ALDRI bak en tom liste — en tom KPI-seksjon ville
                // sett ut som «ingen rapporter finnes», ikke som «henting feilet».
                this.state.kpiFeil = e.message?.data?.message || e.message || String(e);
            }
        });
    }

    get valgtAkse() {
        return this.tidsakser.find((t) => t.key === this.state.akse) || this.tidsakser[0];
    }

    velgAkse(key) {
        this.state.akse = key;
    }

    get valgteKpier() {
        return (this.state.kpi?.rapporter || []).filter((r) => r.valgt);
    }

    /** Åpner Odoos EGEN rapport — vi viser ingen kopi. */
    async apneKpi(key) {
        const handling = await this.orm.call("fiq.gui.fin.data", "apne_kpi", [key]);
        if (handling) {
            this.action.doAction(handling);
        }
    }

    /** Huk av/på. Lagres serverside per bruker+firma, så valget følger brukeren. */
    async velgKpi(key) {
        const r = this.state.kpi.rapporter.find((x) => x.key === key);
        r.valgt = !r.valgt;
        const valgte = this.state.kpi.rapporter.filter((x) => x.valgt).map((x) => x.key);
        this.state.kpi.antall_valgt = valgte.length;
        await this.orm.call("fiq.gui.fin.data", "sett_valgte_kpier", [valgte]);
    }

    vekslVelger() {
        this.state.velgerApen = !this.state.velgerApen;
    }

    // Skallet sender inn valgt firma; flaten eier ALDRI firma-valget selv.
    // company_id hentes fra sesjonen i Odoo — aldri som parameter utenfra (tenant-isolasjon).
    get firma() {
        return this.props.firm || "—";
    }
}

registry.category("actions").add("fiq_gui_fin_dashboard", FiqGuiFin);

// Registrering i det delte skallet (fast hovedmeny, Vei C).
// Kontrakt verifisert mot fiq_gui_shell/static/src/shell.js:7 + demo_flates.js.
// Farge #4472C4 = finans-familien (2.70/2.80), jf. rollefilene + control_room.js:17.
registry.category("fiq_gui_flates").add("finans", {
    key: "finans",
    label: "Finans",
    color: "#4472C4",
    sequence: 50,
    Component: FiqGuiFin,
});
