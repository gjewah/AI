/** @odoo-module **/

import { Component, xml } from "@odoo/owl";
import { registry } from "@web/core/registry";

// DEMO-innmat — beviser at skallet bytter innhold uten sidebytte.
// I native versjon registrerer HVER ekte flate (fiq_gui_epost, fiq_gui_prj, fiq_gui_crm …)
// sin egen innmat-komponent her i stedet for denne.
class DemoInnmat extends Component {
    static template = xml`
        <div class="fiqs-demo">
            <h2 t-esc="props.label"/>
            <p>Innmat-slot for <b t-esc="props.label"/> · valgt firma: <t t-esc="props.firm"/>.</p>
            <p class="fiqs-demo-note">
                Skallet (topplinje + sidemeny) står <b>FAST</b> — bare denne ruta byttes når du
                klikker i sidemenyen. Det er Vei C: V00.04 som delt skall.
            </p>
        </div>`;
    static props = ["*"];
}

const flates = registry.category("fiq_gui_flates");
flates.add("meldingssenter", { key: "meldingssenter", label: "Meldingssenter", color: "#2AA79E", sequence: 10, Component: DemoInnmat });
flates.add("prosjekt", { key: "prosjekt", label: "Prosjekt", color: "#4C63D2", sequence: 20, Component: DemoInnmat });
flates.add("salg", { key: "salg", label: "Salg", color: "#CC0000", sequence: 30, Component: DemoInnmat });
flates.add("regnskap", { key: "regnskap", label: "Regnskap", color: "#ED7D31", sequence: 40, Component: DemoInnmat });
