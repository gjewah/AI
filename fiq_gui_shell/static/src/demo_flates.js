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

// Registrer KUN hvis flaten ikke allerede er tatt av en ekte modul.
// Uten denne vakten kaster registry.add() «key already exists» og HELE
// grensesnittet dør (blank skjerm) i det en ekte flate leveres.
// Hendelse 2026-07-18: fiq_gui_rgs leverte ekte «regnskap» → kollisjon → blank Odoo.
function demoFlate(key, label, color, sequence) {
    if (flates.contains(key)) {
        return; // ekte modul eier flaten — demo skal vike
    }
    flates.add(key, { key, label, color, sequence, Component: DemoInnmat });
}

demoFlate("meldingssenter", "Meldingssenter", "#2AA79E", 10);
demoFlate("prosjekt", "Prosjekt", "#4C63D2", 20);
demoFlate("salg", "Salg", "#CC0000", 30);
// «regnskap» fjernet 2026-07-18 — fiq_gui_rgs eier den nå (ekte flate).
