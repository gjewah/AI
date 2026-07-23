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

// Demo-innmat må ALDRI kunne velte grensesnittet for en ekte flate.
//
// Hendelse 2026-07-18: fiq_gui_rgs leverte ekte «regnskap» → registry.add() på en nøkkel
// som alt fantes → «key already exists» → BLANK Odoo. Serverloggen var helt ren (`-u` ga
// 0 ERROR); feilen levde kun i nettleseren. Meldt av Finans-økta (2.70).
//
// En `if (flates.contains(key))`-vakt er IKKE nok: den avhenger av lasterekkefølge.
// Verifisert 18.07: verken fiq_gui_rgs eller fiq_gui_fin har fiq_gui_shell i `depends`
// (de avhenger av fiq_gui_control), så rekkefølgen mellom skallet og flatene er UDEFINERT.
// Laster demoen først, ser vakten ingenting — og den ekte flaten kolliderer likevel.
//
// Derfor: demoen registreres SIST (etter at alle moduler er lastet) og bare på nøkler som
// fortsatt er ledige. Ekte flate vinner alltid, uansett rekkefølge.
function registrerLedigeDemoFlater() {
    const DEMO = [
        ["meldingssenter", "Meldingssenter", "#2AA79E", 10],
        ["prosjekt", "Prosjekt", "#4C63D2", 20],
        ["salg", "Salg", "#CC0000", 30],
        // «regnskap» er borte for godt — fiq_gui_rgs eier den (ekte flate).
    ];
    for (const [key, label, color, sequence] of DEMO) {
        if (flates.contains(key)) {
            continue; // ekte modul eier flaten — demo skal vike, aldri overskrive
        }
        flates.add(key, { key, label, color, sequence, Component: DemoInnmat });
    }
}

// Kjør etter at alle moduler har fått registrert seg (mikrotask = slutten av lastefasen).
Promise.resolve().then(registrerLedigeDemoFlater);
